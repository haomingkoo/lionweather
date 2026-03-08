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
        self.malaysia_base_url = "https://api.data.gov.my"
        self.indonesia_base_url = "https://data.bmkg.go.id"
        
        # Create rate limiters for each API (100 requests/hour)
        self.singapore_rate_limiter = RateLimiter(max_requests=100, time_window_seconds=3600)
        self.malaysia_rate_limiter = RateLimiter(max_requests=100, time_window_seconds=3600)
        self.indonesia_rate_limiter = RateLimiter(max_requests=100, time_window_seconds=3600)
        
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
    
    async def fetch_malaysia_data(self) -> List[WeatherRecord]:
        """
        Fetch real-time weather data for Malaysia using Open-Meteo API.

        The official api.data.gov.my/weather endpoint only returns temperature
        forecast ranges (min/max) with no rainfall, humidity, or wind — useless
        for ML training.  We instead query Open-Meteo for ~30 Malaysian cities,
        matching the Indonesia station count so the training set is geographically
        balanced.

        Returns:
            List of WeatherRecord objects for Malaysia (~30 records)
        """
        malaysia_cities = [
            {"name": "Kuala Lumpur",      "lat": 3.1390,  "lon": 101.6869},
            {"name": "George Town",        "lat": 5.4141,  "lon": 100.3288},
            {"name": "Johor Bahru",        "lat": 1.4927,  "lon": 103.7414},
            {"name": "Ipoh",               "lat": 4.5975,  "lon": 101.0901},
            {"name": "Kuching",            "lat": 1.5497,  "lon": 110.3592},
            {"name": "Kota Kinabalu",      "lat": 5.9804,  "lon": 116.0735},
            {"name": "Shah Alam",          "lat": 3.0733,  "lon": 101.5185},
            {"name": "Petaling Jaya",      "lat": 3.1073,  "lon": 101.6067},
            {"name": "Subang Jaya",        "lat": 3.0462,  "lon": 101.5816},
            {"name": "Klang",              "lat": 3.0380,  "lon": 101.4450},
            {"name": "Miri",               "lat": 4.3995,  "lon": 113.9914},
            {"name": "Sibu",               "lat": 2.3064,  "lon": 111.8259},
            {"name": "Sandakan",           "lat": 5.8402,  "lon": 118.1179},
            {"name": "Tawau",              "lat": 4.2456,  "lon": 117.8912},
            {"name": "Kota Bharu",         "lat": 6.1254,  "lon": 102.2381},
            {"name": "Kuala Terengganu",   "lat": 5.3296,  "lon": 103.1370},
            {"name": "Kuantan",            "lat": 3.8077,  "lon": 103.3260},
            {"name": "Alor Setar",         "lat": 6.1248,  "lon": 100.3673},
            {"name": "Seremban",           "lat": 2.7297,  "lon": 101.9381},
            {"name": "Malacca City",       "lat": 2.1896,  "lon": 102.2501},
            {"name": "Batu Pahat",         "lat": 1.8535,  "lon": 102.9323},
            {"name": "Muar",               "lat": 2.0441,  "lon": 102.5689},
            {"name": "Segamat",            "lat": 2.5126,  "lon": 102.8159},
            {"name": "Bintulu",            "lat": 3.1667,  "lon": 113.0333},
            {"name": "Lahad Datu",         "lat": 5.0274,  "lon": 118.3251},
            {"name": "Beaufort",           "lat": 5.3667,  "lon": 115.7500},
            {"name": "Keningau",           "lat": 5.3378,  "lon": 116.1630},
            {"name": "Taiping",            "lat": 4.8556,  "lon": 100.7333},
            {"name": "Teluk Intan",        "lat": 4.0226,  "lon": 101.0194},
            {"name": "Temerloh",           "lat": 3.4500,  "lon": 102.4167},
        ]

        logger.info(f"Fetching Malaysia data via Open-Meteo for {len(malaysia_cities)} cities...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
        ) as session:
            records = []
            now = datetime.utcnow()

            for city in malaysia_cities:
                try:
                    url = (
                        "https://api.open-meteo.com/v1/forecast"
                        f"?latitude={city['lat']}&longitude={city['lon']}"
                        "&current=temperature_2m,relative_humidity_2m,precipitation,"
                        "wind_speed_10m,wind_direction_10m,surface_pressure,weather_code"
                        "&timezone=Asia/Kuala_Lumpur"
                    )
                    data = await self._fetch_json(session, url)
                    current = data.get("current", {})

                    record = WeatherRecord(
                        timestamp=now,
                        country="malaysia",
                        location=city["name"],
                        latitude=city["lat"],
                        longitude=city["lon"],
                        temperature=float(current.get("temperature_2m") or 0),
                        rainfall=float(current.get("precipitation") or 0),
                        humidity=float(current.get("relative_humidity_2m") or 0),
                        wind_speed=float(current.get("wind_speed_10m") or 0),
                        wind_direction=current.get("wind_direction_10m"),
                        pressure=current.get("surface_pressure"),
                        source_api="open-meteo (malaysia)",
                    )
                    if self.validate_record(record):
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Malaysia Open-Meteo failed for {city['name']}: {e}")

            logger.info(f"Malaysia data collection complete: {len(records)} valid records")
            return records
    
    async def fetch_indonesia_data(self) -> List[WeatherRecord]:
        """
        Fetch weather data for Indonesia using Open-Meteo API.
        
        NOTE: The original BMKG XML API (data.bmkg.go.id) is no longer publicly accessible.
        This implementation uses Open-Meteo as a reliable alternative source for Indonesian weather data.
        
        Open-Meteo provides current weather observations for major Indonesian cities including:
        temperature, humidity, precipitation, wind speed, and wind direction.
        
        Returns:
            List of WeatherRecord objects for Indonesia locations (~30 records)
        """
        async def _fetch_with_rate_limit():
            # Apply rate limiting
            await self.indonesia_rate_limiter.acquire()
            
            logger.info("🇮🇩 Starting Indonesia data collection (Open-Meteo API)...")
            
            # Major Indonesian cities with coordinates
            # Covers major population centers across the archipelago
            indonesia_cities = [
                {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456},
                {"name": "Surabaya", "lat": -7.2575, "lon": 112.7521},
                {"name": "Bandung", "lat": -6.9175, "lon": 107.6191},
                {"name": "Medan", "lat": 3.5952, "lon": 98.6722},
                {"name": "Semarang", "lat": -6.9667, "lon": 110.4167},
                {"name": "Makassar", "lat": -5.1477, "lon": 119.4327},
                {"name": "Palembang", "lat": -2.9761, "lon": 104.7754},
                {"name": "Tangerang", "lat": -6.1783, "lon": 106.6319},
                {"name": "Depok", "lat": -6.4025, "lon": 106.7942},
                {"name": "Bekasi", "lat": -6.2349, "lon": 106.9896},
                {"name": "Bogor", "lat": -6.5950, "lon": 106.8167},
                {"name": "Batam", "lat": 1.0456, "lon": 104.0305},
                {"name": "Pekanbaru", "lat": 0.5071, "lon": 101.4478},
                {"name": "Bandar Lampung", "lat": -5.4292, "lon": 105.2619},
                {"name": "Padang", "lat": -0.9471, "lon": 100.4172},
                {"name": "Malang", "lat": -7.9797, "lon": 112.6304},
                {"name": "Denpasar", "lat": -8.6705, "lon": 115.2126},
                {"name": "Samarinda", "lat": -0.5022, "lon": 117.1536},
                {"name": "Banjarmasin", "lat": -3.3194, "lon": 114.5906},
                {"name": "Manado", "lat": 1.4748, "lon": 124.8421},
                {"name": "Balikpapan", "lat": -1.2379, "lon": 116.8529},
                {"name": "Pontianak", "lat": -0.0263, "lon": 109.3425},
                {"name": "Jambi", "lat": -1.6101, "lon": 103.6131},
                {"name": "Cirebon", "lat": -6.7063, "lon": 108.5571},
                {"name": "Yogyakarta", "lat": -7.7956, "lon": 110.3695},
                {"name": "Surakarta", "lat": -7.5755, "lon": 110.8243},
                {"name": "Mataram", "lat": -8.5833, "lon": 116.1167},
                {"name": "Kupang", "lat": -10.1718, "lon": 123.6075},
                {"name": "Ambon", "lat": -3.6954, "lon": 128.1814},
                {"name": "Jayapura", "lat": -2.5489, "lon": 140.7182},
            ]
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                records = []
                
                # Fetch data for each city
                for city in indonesia_cities:
                    try:
                        url = (
                            f"https://api.open-meteo.com/v1/forecast"
                            f"?latitude={city['lat']}"
                            f"&longitude={city['lon']}"
                            f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure"
                            f"&timezone=Asia/Jakarta"
                        )
                        
                        data = await self._fetch_json(session, url)
                        current = data.get('current', {})
                        
                        # Create WeatherRecord from Open-Meteo data
                        record = WeatherRecord(
                            timestamp=datetime.now(),
                            country="indonesia",
                            location=city['name'],
                            latitude=city['lat'],
                            longitude=city['lon'],
                            temperature=current.get('temperature_2m', 0.0),
                            rainfall=current.get('precipitation', 0.0),
                            humidity=current.get('relative_humidity_2m', 0.0),
                            wind_speed=current.get('wind_speed_10m', 0.0),
                            wind_direction=current.get('wind_direction_10m'),
                            pressure=current.get('surface_pressure'),
                            source_api="open-meteo.com"
                        )
                        
                        records.append(record)
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch data for {city['name']}: {str(e)}")
                        continue
                
                logger.info(f"Fetched {len(records)} Indonesia weather records")
                
                # Validate records
                valid_records = []
                for record in records:
                    if self.validate_record(record):
                        valid_records.append(record)
                    else:
                        logger.warning(f"Excluding invalid record for {record.location}")
                
                logger.info(f"✓ Indonesia data collection complete: {len(valid_records)} valid records")
                return valid_records
        
        try:
            return await self.retry_with_backoff(_fetch_with_rate_limit)
        except Exception as e:
            logger.error(f"❌ Failed to fetch Indonesia data after retries: {str(e)}", exc_info=True)
            # Gracefully continue - return empty list
            return []
    
    async def collect_all_sources(self) -> List[WeatherRecord]:
        """
        Collect weather data from all sources in parallel.
        
        Fetches data from Singapore, Malaysia, and Indonesia APIs concurrently
        and combines the results into a single list.
        
        Returns:
            Combined list of WeatherRecord objects from all sources
        """
        # Fetch from all sources in parallel
        tasks = [
            self.fetch_singapore_data(),
            self.fetch_malaysia_data(),
            self.fetch_indonesia_data(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results, filtering out exceptions
        all_records = []
        for result in results:
            if isinstance(result, Exception):
                # Log the error but continue with other sources
                # TODO: Add proper logging
                continue
            all_records.extend(result)
        
        return all_records
    
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
    
    def _parse_malaysia_data(self, data: dict | list) -> List[WeatherRecord]:
        """
        Parse Malaysian Meteorological Department API response.
        
        The Malaysia API can return data in two formats:
        1. Direct array: [{"location": {...}, ...}, ...]
        2. Wrapped in data key: {"data": [{"location": {...}, ...}, ...]}
        
        The forecast API returns data with nested location and forecast information.
        
        IMPORTANT: This method filters to only the FIRST/CURRENT forecast period (period 0)
        to avoid mixing current observations with forecast data in the weather_data table.
        Future forecast periods (1-6) should be handled separately in a forecast_data table.
        
        Args:
            data: API response (can be dict or list)
            
        Returns:
            List of WeatherRecord objects (only current observations, ~284 records)
        """
        records = []
        
        # Handle both list and dict response formats
        if isinstance(data, list):
            data_items = data
        else:
            data_items = data.get("data", [])
        
        if not data_items:
            logger.warning("No data items found in Malaysia API response")
            return records
        
        # Get current timestamp
        current_time = datetime.now()
        
        # Group data by location to filter only the first/current forecast period
        # Malaysia API returns multiple forecast periods per location (7 periods)
        # We only want the first period (current observation) for weather_data table
        location_first_records = {}
        
        # Process each location
        for location_data in data_items:
            if not isinstance(location_data, dict):
                logger.warning(f"Invalid location data type: {type(location_data)}")
                continue
                
            try:
                # Extract location info (handle nested location object)
                location_obj = location_data.get("location", {})
                if isinstance(location_obj, dict):
                    location_name = location_obj.get("location_name", "Unknown")
                    latitude = float(location_obj.get("latitude", 0.0))
                    longitude = float(location_obj.get("longitude", 0.0))
                else:
                    # Fallback: location fields at top level
                    location_name = location_data.get("location_name", "Unknown")
                    latitude = float(location_data.get("latitude", 0.0))
                    longitude = float(location_data.get("longitude", 0.0))
                
                # Parse timestamp if available
                date_str = location_data.get("date")
                if date_str:
                    try:
                        timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = current_time
                else:
                    timestamp = current_time
                
                # Create a unique key for this location
                location_key = f"{location_name}_{latitude}_{longitude}"
                
                # Only keep the first record for each location (earliest timestamp = current observation)
                # If we haven't seen this location yet, or this record is earlier, store it
                if location_key not in location_first_records:
                    location_first_records[location_key] = {
                        'data': location_data,
                        'timestamp': timestamp,
                        'location_name': location_name,
                        'latitude': latitude,
                        'longitude': longitude
                    }
                elif timestamp < location_first_records[location_key]['timestamp']:
                    # This record is earlier (more current), replace the stored one
                    location_first_records[location_key] = {
                        'data': location_data,
                        'timestamp': timestamp,
                        'location_name': location_name,
                        'latitude': latitude,
                        'longitude': longitude
                    }
                
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error processing Malaysia location data: {str(e)}")
                continue
        
        # Now process only the first/current record for each location
        for location_key, location_info in location_first_records.items():
            try:
                location_data = location_info['data']
                location_name = location_info['location_name']
                latitude = location_info['latitude']
                longitude = location_info['longitude']
                timestamp = location_info['timestamp']
                
                # Get forecast data - Malaysia API provides min/max temp, not current
                # We'll use the average of min and max as current temperature
                min_temp = location_data.get("min_temp")
                max_temp = location_data.get("max_temp")
                
                if min_temp is not None and max_temp is not None:
                    temperature = (float(min_temp) + float(max_temp)) / 2.0
                else:
                    temperature = 0.0
                
                # Malaysia API doesn't provide real-time rainfall, humidity, wind speed
                # These would need to come from a different endpoint
                # For now, use default values
                rainfall = 0.0
                humidity = 0.0
                wind_speed = 0.0
                wind_direction = None
                pressure = None
                
                # Create WeatherRecord
                record = WeatherRecord(
                    timestamp=timestamp,
                    country="malaysia",
                    location=location_name,
                    latitude=latitude,
                    longitude=longitude,
                    temperature=temperature,
                    rainfall=rainfall,
                    humidity=humidity,
                    wind_speed=wind_speed,
                    wind_direction=wind_direction,
                    pressure=pressure,
                    source_api="api.data.gov.my"
                )
                
                records.append(record)
                
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error parsing Malaysia location data: {str(e)}")
                continue
        
        logger.info(f"Parsed {len(records)} Malaysia weather records (current observations only)")
        return records
    
    def _parse_indonesia_data(self, xml_data: str) -> List[WeatherRecord]:
        """
        Parse BMKG XML API response.
        
        BMKG provides weather data in XML format. This method parses the XML
        structure to extract weather observations for various Indonesian locations.
        
        Expected XML structure:
        <data>
            <forecast>
                <area id="..." description="..." latitude="..." longitude="...">
                    <parameter id="t" description="Temperature">
                        <timerange datetime="...">
                            <value>...</value>
                        </timerange>
                    </parameter>
                    <parameter id="hu" description="Humidity">
                        <timerange datetime="...">
                            <value>...</value>
                        </timerange>
                    </parameter>
                    ...
                </area>
            </forecast>
        </data>
        
        Args:
            xml_data: XML response string
            
        Returns:
            List of WeatherRecord objects
        """
        import xml.etree.ElementTree as ET
        import re
        
        records = []
        
        try:
            # Log raw XML response for debugging (first 1000 characters)
            logger.info(f"📄 Raw Indonesia XML (first 1000 chars): {xml_data[:1000]}")
            logger.debug(f"📄 Full XML length: {len(xml_data)} characters")
            
            # Attempt to repair common XML issues before parsing
            cleaned_xml = xml_data
            
            # Strip BOM (Byte Order Mark) if present
            if cleaned_xml.startswith('\ufeff'):
                cleaned_xml = cleaned_xml[1:]
                logger.info("Stripped BOM from XML")
            
            # Strip leading/trailing whitespace
            cleaned_xml = cleaned_xml.strip()
            
            # Fix common tag mismatches (e.g., </areas> instead of </area>)
            cleaned_xml = re.sub(r'</areas>', '</area>', cleaned_xml)
            cleaned_xml = re.sub(r'</parameters>', '</parameter>', cleaned_xml)
            cleaned_xml = re.sub(r'</timeranges>', '</timerange>', cleaned_xml)
            cleaned_xml = re.sub(r'</values>', '</value>', cleaned_xml)
            
            # Fix unclosed tags (basic pattern)
            cleaned_xml = re.sub(r'<(\w+)([^>]*)>([^<]*)<\/(?!\1)', r'<\1\2>\3</\1></', cleaned_xml)
            
            # Strip invalid XML characters (control characters except tab, newline, carriage return)
            cleaned_xml = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned_xml)
            
            # Handle encoding issues - replace common problematic characters
            cleaned_xml = cleaned_xml.replace('\x00', '')
            
            # Add XML validation - check if XML is well-formed
            if not cleaned_xml.startswith('<?xml') and not cleaned_xml.startswith('<'):
                logger.error("XML does not start with valid XML declaration or root element")
                return records
            
            # Parse XML
            try:
                root = ET.fromstring(cleaned_xml)
                logger.info(f"✓ XML parsed successfully. Root element: <{root.tag}>")
                
                # Log XML root element and immediate children
                immediate_children = [child.tag for child in root]
                logger.info(f"📊 XML structure - Root: <{root.tag}>, Immediate children: {immediate_children}")
                logger.debug(f"  Root attributes: {root.attrib}")
                
            except ET.ParseError as e:
                logger.error(f"Failed to parse Indonesia XML even after cleaning: {str(e)}")
                logger.error(f"  Error at line {e.position[0] if hasattr(e, 'position') else 'unknown'}")
                logger.debug(f"  Cleaned XML (first 500 chars): {cleaned_xml[:500]}")
                return records
            
            # Get current timestamp
            current_time = datetime.now()
            
            # Use flexible XPath queries to find area elements
            # Try multiple patterns to handle different XML structures
            areas = root.findall(".//area")
            if not areas:
                logger.warning("No areas found with './/area', trying '//area'")
                areas = root.findall("//area")
            if not areas:
                logger.warning("No areas found with '//area', trying './forecast/area'")
                forecast = root.find("forecast")
                if forecast is not None:
                    areas = forecast.findall("area")
            if not areas:
                logger.warning("No areas found with './forecast/area', trying direct children")
                areas = root.findall("area")
            
            logger.info(f"🔍 Found {len(areas)} area elements in XML")
            
            # Collect all unique parameter IDs for debugging
            all_param_ids = set()
            
            # Find all area elements (locations)
            for area in areas:
                try:
                    # Extract location information
                    location_id = area.get("id", "")
                    location_name = area.get("description", "Unknown")
                    
                    # Handle latitude/longitude parsing
                    try:
                        latitude = float(area.get("latitude", 0.0))
                        longitude = float(area.get("longitude", 0.0))
                    except (ValueError, TypeError):
                        latitude = 0.0
                        longitude = 0.0
                    
                    # Initialize weather parameters
                    temperature = 0.0
                    rainfall = 0.0
                    humidity = 0.0
                    wind_speed = 0.0
                    wind_direction = None
                    pressure = None
                    timestamp = current_time
                    
                    # Extract parameters
                    for param in area.findall("parameter"):
                        param_id = param.get("id", "")
                        param_desc = param.get("description", "")
                        
                        # Log parameter ID for debugging
                        all_param_ids.add(f"{param_id} ({param_desc})")
                        
                        # Get the first timerange (current/latest data)
                        timerange = param.find("timerange")
                        if timerange is None:
                            continue
                        
                        # Get timestamp from timerange if available
                        datetime_str = timerange.get("datetime")
                        if datetime_str:
                            try:
                                timestamp = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                            except (ValueError, AttributeError):
                                pass
                        
                        # Get value
                        value_elem = timerange.find("value")
                        if value_elem is None or value_elem.text is None:
                            continue
                        
                        try:
                            value = float(value_elem.text)
                        except ValueError:
                            continue
                        
                        # Map parameter IDs to weather fields
                        # Extended BMKG parameter IDs with Indonesian language names and numeric IDs:
                        # Temperature: t, temp, temperature, suhu, 1
                        # Humidity: hu, humidity, kelembapan, kelembaban, rh, 2
                        # Wind Speed: ws, wind_speed, kecepatan_angin, kec_angin, 3
                        # Wind Direction: wd, wind_direction, arah_angin, 4
                        # Rainfall: tp, rainfall, hujan, ch, curah_hujan, 5
                        # Pressure: p, pressure, tekanan, 6
                        
                        param_id_lower = param_id.lower()
                        
                        if param_id_lower in ["t", "temp", "temperature", "suhu", "1"]:
                            temperature = value
                        elif param_id_lower in ["hu", "humidity", "kelembapan", "kelembaban", "rh", "2"]:
                            humidity = value
                        elif param_id_lower in ["ws", "wind_speed", "kecepatan_angin", "kec_angin", "3"]:
                            # Convert m/s to km/h if needed (BMKG often uses m/s)
                            # Assuming the value is in m/s, convert to km/h
                            wind_speed = value * 3.6 if value < 100 else value
                        elif param_id_lower in ["wd", "wind_direction", "arah_angin", "4"]:
                            wind_direction = value
                        elif param_id_lower in ["tp", "rainfall", "hujan", "ch", "curah_hujan", "5"]:
                            rainfall = value
                        elif param_id_lower in ["p", "pressure", "tekanan", "6"]:
                            pressure = value
                    
                    # Create WeatherRecord
                    record = WeatherRecord(
                        timestamp=timestamp,
                        country="indonesia",
                        location=location_name,
                        latitude=latitude,
                        longitude=longitude,
                        temperature=temperature,
                        rainfall=rainfall,
                        humidity=humidity,
                        wind_speed=wind_speed,
                        wind_direction=wind_direction,
                        pressure=pressure,
                        source_api="data.bmkg.go.id"
                    )
                    
                    records.append(record)
                    
                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"Error parsing Indonesia area data: {str(e)}")
                    continue
            
            # Log all parameter IDs found in XML for debugging
            logger.info(f"🔍 All parameter IDs found in XML: {sorted(all_param_ids)}")
            logger.info(f"Parsed {len(records)} Indonesia weather records")
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse Indonesia XML data: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing Indonesia data: {str(e)}")
        
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

