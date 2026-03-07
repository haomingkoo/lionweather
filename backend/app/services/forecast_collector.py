"""
Forecast Collector Service

Collects official weather forecasts from Singapore, Malaysia, and Indonesia APIs.
This is separate from current observation collection to enable benchmarking
ML predictions against official forecasts.

Phase 2 of the two-system architecture:
- System 1: Current observations (weather_data table) for ML training
- System 2: Official forecasts (forecast_data table) for benchmarking
"""

import logging
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class ForecastCollector:
    """Collects official weather forecasts from multiple sources."""
    
    def __init__(self, timeout_seconds: float = 10.0):
        """
        Initialize ForecastCollector.
        
        Args:
            timeout_seconds: HTTP request timeout
        """
        self.timeout_seconds = timeout_seconds
        self.singapore_base_url = "https://api-open.data.gov.sg"
        self.malaysia_base_url = "https://api.met.gov.my/v2.1"
        
    async def collect_all_forecasts(self) -> List[Dict]:
        """
        Collect forecasts from all sources (Singapore, Malaysia, Indonesia).
        
        Returns:
            List of forecast dictionaries
        """
        all_forecasts = []
        
        # Collect Singapore forecasts
        try:
            singapore_forecasts = await self.fetch_singapore_forecast()
            all_forecasts.extend(singapore_forecasts)
            logger.info(f"✓ Collected {len(singapore_forecasts)} Singapore forecasts")
        except Exception as e:
            logger.error(f"❌ Singapore forecast collection failed: {e}")
        
        # Collect Malaysia forecasts
        try:
            malaysia_forecasts = await self.fetch_malaysia_forecast()
            all_forecasts.extend(malaysia_forecasts)
            logger.info(f"✓ Collected {len(malaysia_forecasts)} Malaysia forecasts")
        except Exception as e:
            logger.error(f"❌ Malaysia forecast collection failed: {e}")
        
        # Collect Indonesia forecasts
        try:
            indonesia_forecasts = await self.fetch_indonesia_forecast()
            all_forecasts.extend(indonesia_forecasts)
            logger.info(f"✓ Collected {len(indonesia_forecasts)} Indonesia forecasts")
        except Exception as e:
            logger.error(f"❌ Indonesia forecast collection failed: {e}")
        
        logger.info(f"Total forecasts collected: {len(all_forecasts)}")
        return all_forecasts
    
    async def fetch_singapore_forecast(self) -> List[Dict]:
        """
        Fetch Singapore NEA 24-hour weather forecast.
        
        Uses the existing fetch_nea_forecast() logic from DataCollector.
        
        Returns:
            List of forecast dictionaries with standardized format
        """
        logger.info("🌤️ Fetching Singapore NEA forecast...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            url = f"{self.singapore_base_url}/v2/real-time/api/twenty-four-hour-weather-forecast"
            
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                forecasts = self._parse_singapore_forecast(data)
                logger.info(f"Parsed {len(forecasts)} Singapore forecast periods")
                return forecasts
                
            except Exception as e:
                logger.error(f"Failed to fetch Singapore forecast: {e}")
                return []
    
    def _parse_singapore_forecast(self, data: dict) -> List[Dict]:
        """
        Parse Singapore NEA forecast API response.
        
        Args:
            data: NEA API response
            
        Returns:
            List of forecast dictionaries
        """
        forecasts = []
        
        try:
            records = data.get("data", {}).get("records", [])
            if not records:
                logger.warning("No forecast records in Singapore API response")
                return forecasts
            
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
                        
                        forecast = {
                            "country": "singapore",
                            "location": "Singapore",
                            "latitude": 1.3521,
                            "longitude": 103.8198,
                            "prediction_time": prediction_time.isoformat(),
                            "target_time_start": target_time_start.isoformat(),
                            "target_time_end": target_time_end.isoformat(),
                            "temperature_low": temp_low,
                            "temperature_high": temp_high,
                            "humidity_low": humidity_low,
                            "humidity_high": humidity_high,
                            "wind_speed_low": wind_speed_low,
                            "wind_speed_high": wind_speed_high,
                            "wind_direction": wind_direction,
                            "forecast_description": forecast_text,
                            "source_api": "nea"
                        }
                        
                        forecasts.append(forecast)
            else:
                # No periods, create single 24-hour forecast
                target_time_start = prediction_time
                target_time_end = prediction_time + timedelta(hours=24)
                
                forecast = {
                    "country": "singapore",
                    "location": "Singapore",
                    "latitude": 1.3521,
                    "longitude": 103.8198,
                    "prediction_time": prediction_time.isoformat(),
                    "target_time_start": target_time_start.isoformat(),
                    "target_time_end": target_time_end.isoformat(),
                    "temperature_low": temp_low,
                    "temperature_high": temp_high,
                    "humidity_low": humidity_low,
                    "humidity_high": humidity_high,
                    "wind_speed_low": wind_speed_low,
                    "wind_speed_high": wind_speed_high,
                    "wind_direction": wind_direction,
                    "forecast_description": forecast_text,
                    "source_api": "nea"
                }
                
                forecasts.append(forecast)
        
        except Exception as e:
            logger.error(f"Error parsing Singapore forecast: {e}")
        
        return forecasts
    
    async def fetch_malaysia_forecast(self) -> List[Dict]:
        """
        Fetch Malaysia forecast data (all 7 forecast periods).
        
        Unlike current observations which only use the first period,
        this method collects ALL 7 forecast periods for benchmarking.
        
        Returns:
            List of forecast dictionaries
        """
        logger.info("🌤️ Fetching Malaysia forecast (all 7 periods)...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            url = f"{self.malaysia_base_url}/data"
            
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                forecasts = self._parse_malaysia_forecast(data)
                logger.info(f"Parsed {len(forecasts)} Malaysia forecast records")
                return forecasts
                
            except Exception as e:
                logger.error(f"Failed to fetch Malaysia forecast: {e}")
                return []
    
    def _parse_malaysia_forecast(self, data: dict) -> List[Dict]:
        """
        Parse Malaysia forecast API response (all 7 periods).
        
        Args:
            data: Malaysia API response
            
        Returns:
            List of forecast dictionaries
        """
        forecasts = []
        
        try:
            # Handle both list and dict response formats
            if isinstance(data, list):
                data_items = data
            else:
                data_items = data.get("data", [])
            
            if not data_items:
                logger.warning("No data items in Malaysia API response")
                return forecasts
            
            prediction_time = datetime.now()
            
            # Process each location and ALL forecast periods
            for location_data in data_items:
                if not isinstance(location_data, dict):
                    continue
                
                try:
                    # Extract location info
                    location_obj = location_data.get("location", {})
                    if isinstance(location_obj, dict):
                        location_name = location_obj.get("location_name", "Unknown")
                        latitude = float(location_obj.get("latitude", 0.0))
                        longitude = float(location_obj.get("longitude", 0.0))
                    else:
                        location_name = location_data.get("location_name", "Unknown")
                        latitude = float(location_data.get("latitude", 0.0))
                        longitude = float(location_data.get("longitude", 0.0))
                    
                    # Parse date/time
                    date_str = location_data.get("date")
                    if date_str:
                        try:
                            base_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            base_time = prediction_time
                    else:
                        base_time = prediction_time
                    
                    # Get forecast data
                    min_temp = location_data.get("min_temp")
                    max_temp = location_data.get("max_temp")
                    weather_desc = location_data.get("weather", "")
                    
                    # Malaysia API provides 7 forecast periods
                    # Each period is typically 3-4 hours
                    # For simplicity, we'll create 7 periods of 3 hours each
                    for period_idx in range(7):
                        target_start = base_time + timedelta(hours=period_idx * 3)
                        target_end = target_start + timedelta(hours=3)
                        
                        forecast = {
                            "country": "malaysia",
                            "location": location_name,
                            "latitude": latitude,
                            "longitude": longitude,
                            "prediction_time": prediction_time.isoformat(),
                            "target_time_start": target_start.isoformat(),
                            "target_time_end": target_end.isoformat(),
                            "temperature_low": float(min_temp) if min_temp is not None else None,
                            "temperature_high": float(max_temp) if max_temp is not None else None,
                            "humidity_low": None,
                            "humidity_high": None,
                            "wind_speed_low": None,
                            "wind_speed_high": None,
                            "wind_direction": None,
                            "forecast_description": weather_desc,
                            "source_api": "malaysia_met"
                        }
                        
                        forecasts.append(forecast)
                
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error processing Malaysia forecast location: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing Malaysia forecast: {e}")
        
        return forecasts
    
    async def fetch_indonesia_forecast(self) -> List[Dict]:
        """
        Fetch Indonesia forecast using Open-Meteo API.
        
        Open-Meteo provides free weather forecast API with good coverage
        for Indonesia locations.
        
        Returns:
            List of forecast dictionaries
        """
        logger.info("🌤️ Fetching Indonesia forecast from Open-Meteo...")
        
        # Major Indonesian cities for forecast collection
        indonesia_locations = [
            {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456},
            {"name": "Surabaya", "lat": -7.2575, "lon": 112.7521},
            {"name": "Bandung", "lat": -6.9175, "lon": 107.6191},
            {"name": "Medan", "lat": 3.5952, "lon": 98.6722},
            {"name": "Semarang", "lat": -6.9667, "lon": 110.4167},
        ]
        
        forecasts = []
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            for location in indonesia_locations:
                try:
                    # Open-Meteo API endpoint
                    url = (
                        f"https://api.open-meteo.com/v1/forecast"
                        f"?latitude={location['lat']}"
                        f"&longitude={location['lon']}"
                        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
                        f"&forecast_days=3"
                    )
                    
                    async with session.get(url) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        location_forecasts = self._parse_indonesia_forecast(
                            data, 
                            location["name"],
                            location["lat"],
                            location["lon"]
                        )
                        forecasts.extend(location_forecasts)
                        
                except Exception as e:
                    logger.error(f"Failed to fetch Indonesia forecast for {location['name']}: {e}")
                    continue
        
        logger.info(f"Parsed {len(forecasts)} Indonesia forecast records")
        return forecasts
    
    def _parse_indonesia_forecast(self, data: dict, location_name: str, lat: float, lon: float) -> List[Dict]:
        """
        Parse Open-Meteo forecast API response.
        
        Args:
            data: Open-Meteo API response
            location_name: Location name
            lat: Latitude
            lon: Longitude
            
        Returns:
            List of forecast dictionaries
        """
        forecasts = []
        
        try:
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            humidities = hourly.get("relative_humidity_2m", [])
            wind_speeds = hourly.get("wind_speed_10m", [])
            wind_directions = hourly.get("wind_direction_10m", [])
            
            if not times:
                logger.warning(f"No forecast times for {location_name}")
                return forecasts
            
            prediction_time = datetime.now()
            
            # Create forecast entries for each hour
            # Group into 3-hour periods for consistency with other sources
            for i in range(0, len(times), 3):
                if i >= len(times):
                    break
                
                try:
                    target_start = datetime.fromisoformat(times[i])
                    target_end = target_start + timedelta(hours=3)
                    
                    # Get values for this period (average of 3 hours)
                    period_temps = temperatures[i:i+3]
                    period_humidity = humidities[i:i+3]
                    period_wind_speed = wind_speeds[i:i+3]
                    period_wind_dir = wind_directions[i:i+3]
                    
                    if period_temps:
                        temp_low = min(period_temps)
                        temp_high = max(period_temps)
                    else:
                        temp_low = temp_high = None
                    
                    if period_humidity:
                        humidity_low = min(period_humidity)
                        humidity_high = max(period_humidity)
                    else:
                        humidity_low = humidity_high = None
                    
                    if period_wind_speed:
                        wind_speed_low = min(period_wind_speed)
                        wind_speed_high = max(period_wind_speed)
                    else:
                        wind_speed_low = wind_speed_high = None
                    
                    if period_wind_dir:
                        wind_direction = self._degrees_to_direction(sum(period_wind_dir) / len(period_wind_dir))
                    else:
                        wind_direction = None
                    
                    forecast = {
                        "country": "indonesia",
                        "location": location_name,
                        "latitude": lat,
                        "longitude": lon,
                        "prediction_time": prediction_time.isoformat(),
                        "target_time_start": target_start.isoformat(),
                        "target_time_end": target_end.isoformat(),
                        "temperature_low": temp_low,
                        "temperature_high": temp_high,
                        "humidity_low": humidity_low,
                        "humidity_high": humidity_high,
                        "wind_speed_low": wind_speed_low,
                        "wind_speed_high": wind_speed_high,
                        "wind_direction": wind_direction,
                        "forecast_description": None,
                        "source_api": "open_meteo"
                    }
                    
                    forecasts.append(forecast)
                
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing Indonesia forecast period: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing Indonesia forecast for {location_name}: {e}")
        
        return forecasts
    
    @staticmethod
    def _degrees_to_direction(degrees: float) -> str:
        """Convert wind direction in degrees to compass direction."""
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(degrees / 45) % 8
        return directions[index]
