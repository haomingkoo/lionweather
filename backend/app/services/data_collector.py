"""
Data Collector Service for ML Weather Forecasting

This module provides the DataCollector class that fetches weather data from
Singapore, Malaysia, and Indonesia APIs and normalizes them into a unified format.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Callable, Any
import asyncio
import logging
import time

import aiohttp
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class WeatherRecord:
    """Unified weather record format for all data sources"""
    timestamp: datetime
    country: str
    location: str
    latitude: float
    longitude: float
    temperature: float  # Celsius
    rainfall: float  # mm
    humidity: float  # percentage
    wind_speed: float  # km/h
    wind_direction: Optional[float]  # degrees
    pressure: Optional[float]  # hPa
    source_api: str


class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    Implements a token bucket algorithm to limit requests to a specified rate.
    When the rate limit is reached, requests are queued until tokens become available.
    """
    
    def __init__(self, max_requests: int = 100, time_window_seconds: int = 3600):
        """
        Initialize RateLimiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window_seconds: Time window in seconds (default: 3600 = 1 hour)
        """
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds
        self.tokens = max_requests
        self.last_refill_time = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """
        Acquire a token for making a request.
        
        If no tokens are available, this method will wait until a token becomes available.
        Tokens are refilled at a constant rate based on the time window.
        """
        async with self.lock:
            # Refill tokens based on elapsed time
            now = time.time()
            elapsed = now - self.last_refill_time
            
            # Calculate how many tokens to add based on elapsed time
            tokens_to_add = (elapsed / self.time_window_seconds) * self.max_requests
            self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
            self.last_refill_time = now
            
            # If no tokens available, wait until we can get one
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.time_window_seconds / self.max_requests)
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                self.tokens = 1
                self.last_refill_time = time.time()
            
            # Consume one token
            self.tokens -= 1


class DataCollector:
    """
    Collects weather data from multiple country APIs and normalizes to WeatherRecord format.
    
    Supports:
    - Singapore: api-open.data.gov.sg
    - Malaysia: Malaysian Meteorological Department API
    - Indonesia: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika) API
    """
    
    def __init__(self, timeout_seconds: float = 10.0):
        """
        Initialize DataCollector.
        
        Args:
            timeout_seconds: HTTP request timeout in seconds
        """
        self.timeout_seconds = timeout_seconds
        self.singapore_base_url = "https://api-open.data.gov.sg"

        # Create rate limiter for Singapore API (100 requests/hour)
        self.singapore_rate_limiter = RateLimiter(max_requests=100, time_window_seconds=3600)
        
        # Store historical data for outlier detection
        self._historical_data = {
            'temperature': [],
            'rainfall': [],
            'humidity': [],
            'wind_speed': []
        }
    
    async def retry_with_backoff(
        self, 
        func: Callable, 
        max_retries: int = 3,
        *args,
        **kwargs
    ) -> Any:
        """
        Retry a function with exponential backoff.
        
        Implements retry logic with delays of 1s, 2s, 4s for up to 3 attempts.
        Logs errors for failed attempts and raises the last exception if all retries fail.
        
        Args:
            func: Async function to retry
            max_retries: Maximum number of retry attempts (default: 3)
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
            
        Returns:
            Result from successful function call
            
        Raises:
            Exception: The last exception if all retries fail
        """
        delays = [1, 2, 4]  # Exponential backoff delays in seconds
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Retry successful on attempt {attempt + 1}")
                return result
            except Exception as e:
                last_exception = e
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    delay = delays[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(f"All {max_retries} attempts failed. Last error: {str(last_exception)}")
        raise last_exception
    
    def normalize_record(self, raw_data: dict, source: str) -> WeatherRecord:
        """
        Normalize raw API response data into WeatherRecord format.
        
        Converts different API response formats into a unified WeatherRecord structure.
        
        Args:
            raw_data: Raw data dictionary from API
            source: Source identifier ('singapore', 'malaysia', 'indonesia')
            
        Returns:
            Normalized WeatherRecord object
        """
        # This is a generic normalization method
        # Specific parsing is handled by _parse_*_data methods
        return WeatherRecord(
            timestamp=raw_data.get('timestamp', datetime.now()),
            country=source,
            location=raw_data.get('location', 'Unknown'),
            latitude=raw_data.get('latitude', 0.0),
            longitude=raw_data.get('longitude', 0.0),
            temperature=raw_data.get('temperature', 0.0),
            rainfall=raw_data.get('rainfall', 0.0),
            humidity=raw_data.get('humidity', 0.0),
            wind_speed=raw_data.get('wind_speed', 0.0),
            wind_direction=raw_data.get('wind_direction'),
            pressure=raw_data.get('pressure'),
            source_api=raw_data.get('source_api', f'{source}_api')
        )
    
    def validate_record(self, record: WeatherRecord) -> bool:
        """
        Validate weather record data ranges.
        
        Checks that all weather parameters are within valid ranges:
        - Temperature: -50 to 60°C
        - Rainfall: >= 0 mm
        - Humidity: 0 to 100%
        - Wind speed: >= 0 km/h
        
        Args:
            record: WeatherRecord to validate
            
        Returns:
            True if record is valid, False otherwise
        """
        # Range validation
        if record.temperature < -50 or record.temperature > 60:
            logger.warning(
                f"Invalid temperature {record.temperature}°C for {record.location}. "
                f"Valid range: -50 to 60°C"
            )
            return False
        
        if record.rainfall < 0:
            logger.warning(
                f"Invalid rainfall {record.rainfall}mm for {record.location}. "
                f"Must be non-negative"
            )
            return False
        
        if record.humidity < 0 or record.humidity > 100:
            logger.warning(
                f"Invalid humidity {record.humidity}% for {record.location}. "
                f"Valid range: 0 to 100%"
            )
            return False
        
        if record.wind_speed < 0:
            logger.warning(
                f"Invalid wind speed {record.wind_speed} km/h for {record.location}. "
                f"Must be non-negative"
            )
            return False
        
        # Statistical outlier detection (3 standard deviations)
        if self._is_outlier(record):
            logger.warning(
                f"Statistical outlier detected for {record.location}: "
                f"temp={record.temperature}, rainfall={record.rainfall}, "
                f"humidity={record.humidity}, wind_speed={record.wind_speed}"
            )
            # Note: We still return True for outliers, just flag them
            # The spec says to "flag" outliers, not reject them
        
        return True
    
    def _is_outlier(self, record: WeatherRecord) -> bool:
        """
        Detect statistical outliers using 3 standard deviations method.
        
        Args:
            record: WeatherRecord to check
            
        Returns:
            True if any parameter is an outlier, False otherwise
        """
        parameters = {
            'temperature': record.temperature,
            'rainfall': record.rainfall,
            'humidity': record.humidity,
            'wind_speed': record.wind_speed
        }
        
        for param_name, value in parameters.items():
            historical = self._historical_data[param_name]
            
            # Need at least 10 samples for meaningful statistics
            if len(historical) < 10:
                # Add to historical data
                historical.append(value)
                if len(historical) > 1000:  # Keep last 1000 samples
                    historical.pop(0)
                continue
            
            # Calculate mean and standard deviation
            mean = np.mean(historical)
            std = np.std(historical)
            
            # Check if value is beyond 3 standard deviations
            if std > 0 and abs(value - mean) > 3 * std:
                return True
            
            # Add to historical data
            historical.append(value)
            if len(historical) > 1000:  # Keep last 1000 samples
                historical.pop(0)
        
        return False
    
    async def fetch_singapore_data(self) -> List[WeatherRecord]:
        """
        Fetch weather data from Singapore weather.gov.sg API.
        
        Uses the existing Singapore API integration to fetch temperature, rainfall,
        humidity, and wind data from multiple stations. Includes retry logic with
        exponential backoff and rate limiting.
        
        Returns:
            List of WeatherRecord objects for Singapore locations
        """
        async def _fetch_with_rate_limit():
            # Apply rate limiting
            await self.singapore_rate_limiter.acquire()
            
            logger.info("🇸🇬 Starting Singapore data collection...")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                # Fetch all required data in parallel
                endpoints = [
                    "air-temperature",
                    "rainfall",
                    "relative-humidity",
                    "wind-speed",
                    "wind-direction"
                ]
                
                tasks = [
                    self._fetch_json(session, f"{self.singapore_base_url}/v2/real-time/api/{endpoint}")
                    for endpoint in endpoints
                ]
                
                logger.info(f"Fetching data from {len(endpoints)} Singapore API endpoints...")
                results = await asyncio.gather(*tasks, return_exceptions=True)
                temp_data, rainfall_data, humidity_data, wind_speed_data, wind_dir_data = results
                
                # Check for errors and log response structure
                for i, (result, endpoint) in enumerate(zip(results, endpoints)):
                    if isinstance(result, Exception):
                        logger.error(f"❌ Singapore {endpoint} API failed: {str(result)}")
                        raise result
                    else:
                        logger.info(f"✓ Singapore {endpoint} API success: {type(result).__name__}")
                        # Log response structure for debugging
                        if isinstance(result, dict):
                            logger.debug(f"  Response keys: {list(result.keys())}")
                            if 'data' in result:
                                logger.debug(f"  data keys: {list(result['data'].keys())}")
                                if 'records' in result['data']:
                                    logger.debug(f"  records count: {len(result['data']['records'])}")
                
                # Parse and normalize data
                logger.info("Parsing Singapore API responses...")
                records = self._parse_singapore_data(
                    temp_data, rainfall_data, humidity_data, 
                    wind_speed_data, wind_dir_data
                )
                
                logger.info(f"Parsed {len(records)} Singapore weather records")
                
                # Validate records
                valid_records = []
                for record in records:
                    if self.validate_record(record):
                        valid_records.append(record)
                    else:
                        logger.warning(f"Excluding invalid record for {record.location}")
                
                logger.info(f"✓ Singapore data collection complete: {len(valid_records)} valid records")
                return valid_records
        
        try:
            return await self.retry_with_backoff(_fetch_with_rate_limit)
        except Exception as e:
            logger.error(f"❌ Failed to fetch Singapore data after retries: {str(e)}", exc_info=True)
            # Gracefully continue - return empty list
            return []
    
    async def collect_all_sources(self) -> List[WeatherRecord]:
        """
        Collect weather data from Singapore NEA API.

        Returns:
            List of WeatherRecord objects for Singapore
        """
        return await self.fetch_singapore_data()
    
    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> dict | list:
        """
        Fetch JSON data from a URL.
        
        Args:
            session: aiohttp client session
            url: URL to fetch
            
        Returns:
            Parsed JSON response as dictionary or list (Malaysia API returns list)
            
        Raises:
            aiohttp.ClientError: If request fails
        """
        headers = {
            "Accept": "application/json",
            "User-Agent": "weather-ml-forecasting/1.0 (educational project)",
        }
        
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
    
    async def _fetch_xml(self, session: aiohttp.ClientSession, url: str) -> str:
        """
        Fetch XML data from a URL.
        
        Args:
            session: aiohttp client session
            url: URL to fetch
            
        Returns:
            XML response as string
            
        Raises:
            aiohttp.ClientError: If request fails
        """
        headers = {
            "Accept": "application/xml, text/xml",
            "User-Agent": "weather-ml-forecasting/1.0 (educational project)",
        }
        
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.text()
    
    def _parse_singapore_data(
        self,
        temp_data: dict,
        rainfall_data: dict,
        humidity_data: dict,
        wind_speed_data: dict,
        wind_dir_data: dict,
    ) -> List[WeatherRecord]:
        """
        Parse Singapore API responses into WeatherRecord objects.
        
        Singapore API v2 returns data in format:
        {
            "code": 0,
            "data": {
                "stations": [
                    {
                        "id": "S50",
                        "deviceId": "S50",
                        "name": "Clementi Road",
                        "location": {"latitude": 1.3337, "longitude": 103.7768}
                    }
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 28.5}
                        ]
                    }
                ]
            }
        }
        
        This method combines data from different endpoints by matching station IDs.
        
        Args:
            temp_data: Temperature API response
            rainfall_data: Rainfall API response
            humidity_data: Humidity API response
            wind_speed_data: Wind speed API response
            wind_dir_data: Wind direction API response
            
        Returns:
            List of WeatherRecord objects
        """
        records = []
        
        # Extract data from v2 API format: data.stations and data.readings
        temp_data_obj = temp_data.get("data", {})
        stations = temp_data_obj.get("stations", [])
        temp_readings_list = temp_data_obj.get("readings", [])
        
        if not stations:
            logger.warning("No stations found in Singapore API response")
            return records
        
        if not temp_readings_list:
            logger.warning("No temperature readings found in Singapore API response")
            return records
        
        # Get the latest reading set (usually just one)
        latest_temp_reading = temp_readings_list[0]
        timestamp_str = latest_temp_reading.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.now()
        
        # Build station map from stations list
        station_map = {}
        for station in stations:
            station_id = station.get("id")
            if station_id:
                location = station.get("location", {})
                station_map[station_id] = {
                    "name": station.get("name", "Unknown"),
                    "latitude": float(location.get("latitude", 0.0)),
                    "longitude": float(location.get("longitude", 0.0)),
                }
        
        # Build lookup dictionaries for temperature
        # v2 format: readings[0].data = [{"stationId": "S50", "value": 28.5}, ...]
        temp_readings = {}
        for reading in latest_temp_reading.get("data", []):
            station_id = reading.get("stationId")
            if station_id:
                temp_readings[station_id] = reading.get("value", 0.0)
        
        # Build lookup dictionaries for other parameters
        rainfall_readings = {}
        rainfall_data_obj = rainfall_data.get("data", {})
        rainfall_readings_list = rainfall_data_obj.get("readings", [])
        if rainfall_readings_list:
            for reading in rainfall_readings_list[0].get("data", []):
                station_id = reading.get("stationId")
                if station_id:
                    rainfall_readings[station_id] = reading.get("value", 0.0)
        
        humidity_readings = {}
        humidity_data_obj = humidity_data.get("data", {})
        humidity_readings_list = humidity_data_obj.get("readings", [])
        if humidity_readings_list:
            for reading in humidity_readings_list[0].get("data", []):
                station_id = reading.get("stationId")
                if station_id:
                    humidity_readings[station_id] = reading.get("value", 0.0)
        
        wind_speed_readings = {}
        wind_speed_data_obj = wind_speed_data.get("data", {})
        wind_speed_readings_list = wind_speed_data_obj.get("readings", [])
        if wind_speed_readings_list:
            for reading in wind_speed_readings_list[0].get("data", []):
                station_id = reading.get("stationId")
                if station_id:
                    wind_speed_readings[station_id] = reading.get("value", 0.0)
        
        wind_dir_readings = {}
        wind_dir_data_obj = wind_dir_data.get("data", {})
        wind_dir_readings_list = wind_dir_data_obj.get("readings", [])
        if wind_dir_readings_list:
            for reading in wind_dir_readings_list[0].get("data", []):
                station_id = reading.get("stationId")
                if station_id:
                    wind_dir_readings[station_id] = reading.get("value")
        
        # Create WeatherRecord for each station with temperature data
        for station_id, temp in temp_readings.items():
            if station_id not in station_map:
                logger.warning(f"Station {station_id} not found in station map")
                continue
            
            station_info = station_map[station_id]
            
            record = WeatherRecord(
                timestamp=timestamp,
                country="singapore",
                location=station_info["name"],
                latitude=station_info["latitude"],
                longitude=station_info["longitude"],
                temperature=temp,
                rainfall=rainfall_readings.get(station_id, 0.0),
                humidity=humidity_readings.get(station_id, 0.0),
                wind_speed=wind_speed_readings.get(station_id, 0.0),
                wind_direction=wind_dir_readings.get(station_id),
                pressure=None,  # Singapore API doesn't provide pressure data
                source_api="api-open.data.gov.sg",
            )
            
            records.append(record)
        
        logger.info(f"Parsed {len(records)} Singapore weather records")
        return records
    

    async def fetch_nea_forecast(self) -> List[dict]:
        """
        Fetch NEA (National Environment Agency) 24-hour weather forecast.

        Fetches official NEA forecasts from Singapore's data.gov.sg API for comparison
        against ML predictions. The forecast includes temperature ranges, weather conditions,
        and forecast periods.

        API: https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hour-weather-forecast

        Returns:
            List of forecast dictionaries containing:
            - prediction_time: When the forecast was made
            - target_time_start: Start of forecast period
            - target_time_end: End of forecast period
            - temperature_low: Minimum temperature forecast
            - temperature_high: Maximum temperature forecast
            - forecast: Weather condition description
            - relative_humidity_low: Minimum humidity forecast
            - relative_humidity_high: Maximum humidity forecast
            - wind_speed_low: Minimum wind speed forecast
            - wind_speed_high: Maximum wind speed forecast
            - wind_direction: Wind direction forecast
        """
        async def _fetch_with_rate_limit():
            # Apply rate limiting
            await self.singapore_rate_limiter.acquire()

            logger.info("🌤️ Starting NEA forecast collection...")

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                url = f"{self.singapore_base_url}/v2/real-time/api/twenty-four-hour-weather-forecast"
                logger.info(f"Fetching NEA forecast from: {url}")

                try:
                    data = await self._fetch_json(session, url)
                    logger.info(f"✓ NEA forecast API success: {type(data).__name__}")
                    if isinstance(data, dict):
                        logger.debug(f"  Response keys: {list(data.keys())}")
                except Exception as e:
                    logger.error(f"❌ NEA forecast API failed: {str(e)}")
                    raise

                logger.info("Parsing NEA forecast response...")
                forecasts = self._parse_nea_forecast(data)
                logger.info(f"Parsed {len(forecasts)} NEA forecast records")

                logger.info(f"✓ NEA forecast collection complete: {len(forecasts)} forecasts")
                return forecasts

        try:
            return await self.retry_with_backoff(_fetch_with_rate_limit)
        except Exception as e:
            logger.error(f"❌ Failed to fetch NEA forecast after retries: {str(e)}", exc_info=True)
            # Gracefully continue - return empty list
            return []

    def _parse_nea_forecast(self, data: dict) -> List[dict]:
        """
        Parse NEA 24-hour forecast API response.

        NEA API v2 returns data in format:
        {
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T14:00:00+08:00",
                        "general": {
                            "forecast": "Partly Cloudy (Day)",
                            "relative_humidity": {"low": 60, "high": 90},
                            "temperature": {"low": 25, "high": 33},
                            "wind": {
                                "speed": {"low": 10, "high": 20},
                                "direction": "NE"
                            }
                        },
                        "periods": [
                            {
                                "time": {"start": "2024-01-15T18:00:00+08:00", "end": "2024-01-16T06:00:00+08:00"},
                                "regions": {...}
                            }
                        ]
                    }
                ]
            }
        }

        Args:
            data: NEA forecast API response

        Returns:
            List of forecast dictionaries
        """
        forecasts = []

        try:
            records = data.get("data", {}).get("records", [])
            if not records:
                logger.warning("No forecast records found in NEA API response")
                return forecasts

            # Get the latest forecast record
            latest_record = records[0]

            # Parse prediction timestamp
            timestamp_str = latest_record.get("timestamp")
            if timestamp_str:
                try:
                    prediction_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    prediction_time = datetime.now()
            else:
                prediction_time = datetime.now()

            # Parse general forecast
            general = latest_record.get("general", {})
            forecast_text = general.get("forecast", "")

            # Parse temperature
            temp = general.get("temperature", {})
            temp_low = temp.get("low", 0)
            temp_high = temp.get("high", 0)

            # Parse humidity
            humidity = general.get("relative_humidity", {})
            humidity_low = humidity.get("low", 0)
            humidity_high = humidity.get("high", 0)

            # Parse wind
            wind = general.get("wind", {})
            wind_speed = wind.get("speed", {})
            wind_speed_low = wind_speed.get("low", 0)
            wind_speed_high = wind_speed.get("high", 0)
            wind_direction = wind.get("direction", "")

            # Parse forecast periods
            periods = latest_record.get("periods", [])

            if periods:
                # Create a forecast entry for each period
                for period in periods:
                    time_info = period.get("time", {})
                    start_str = time_info.get("start")
                    end_str = time_info.get("end")

                    if start_str and end_str:
                        try:
                            target_time_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            target_time_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            continue

                        forecast_entry = {
                            "prediction_time": prediction_time,
                            "target_time_start": target_time_start,
                            "target_time_end": target_time_end,
                            "temperature_low": temp_low,
                            "temperature_high": temp_high,
                            "forecast": forecast_text,
                            "relative_humidity_low": humidity_low,
                            "relative_humidity_high": humidity_high,
                            "wind_speed_low": wind_speed_low,
                            "wind_speed_high": wind_speed_high,
                            "wind_direction": wind_direction,
                        }

                        forecasts.append(forecast_entry)
            else:
                # No periods, create a single forecast entry for 24 hours ahead
                target_time_start = prediction_time
                target_time_end = prediction_time + timedelta(hours=24)

                forecast_entry = {
                    "prediction_time": prediction_time,
                    "target_time_start": target_time_start,
                    "target_time_end": target_time_end,
                    "temperature_low": temp_low,
                    "temperature_high": temp_high,
                    "forecast": forecast_text,
                    "relative_humidity_low": humidity_low,
                    "relative_humidity_high": humidity_high,
                    "wind_speed_low": wind_speed_low,
                    "wind_speed_high": wind_speed_high,
                    "wind_direction": wind_direction,
                }

                forecasts.append(forecast_entry)

            logger.info(f"Parsed {len(forecasts)} NEA forecast periods")

        except Exception as e:
            logger.error(f"Error parsing NEA forecast data: {str(e)}")

        return forecasts

