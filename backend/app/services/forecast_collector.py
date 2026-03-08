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
        Fetch Malaysia forecast data via Open-Meteo (daily, 7-day) for 30 cities.

        api.met.gov.my requires authentication and is not publicly accessible.
        Open-Meteo provides free, reliable 7-day daily forecasts — same source
        used for Malaysia current observations.

        Returns:
            List of forecast dictionaries (~30 cities × 7 days = ~210 records)
        """
        malaysia_cities = [
            {"name": "Kuala Lumpur",    "lat": 3.1390,  "lon": 101.6869},
            {"name": "George Town",      "lat": 5.4141,  "lon": 100.3288},
            {"name": "Johor Bahru",      "lat": 1.4927,  "lon": 103.7414},
            {"name": "Ipoh",             "lat": 4.5975,  "lon": 101.0901},
            {"name": "Kuching",          "lat": 1.5497,  "lon": 110.3592},
            {"name": "Kota Kinabalu",    "lat": 5.9804,  "lon": 116.0735},
            {"name": "Shah Alam",        "lat": 3.0733,  "lon": 101.5185},
            {"name": "Petaling Jaya",    "lat": 3.1073,  "lon": 101.6067},
            {"name": "Klang",            "lat": 3.0380,  "lon": 101.4450},
            {"name": "Miri",             "lat": 4.3995,  "lon": 113.9914},
            {"name": "Kota Bharu",       "lat": 6.1254,  "lon": 102.2381},
            {"name": "Kuala Terengganu", "lat": 5.3296,  "lon": 103.1370},
            {"name": "Kuantan",          "lat": 3.8077,  "lon": 103.3260},
            {"name": "Alor Setar",       "lat": 6.1248,  "lon": 100.3673},
            {"name": "Seremban",         "lat": 2.7297,  "lon": 101.9381},
            {"name": "Malacca City",     "lat": 2.1896,  "lon": 102.2501},
        ]

        logger.info(f"🌤️ Fetching Malaysia 7-day forecast via Open-Meteo for {len(malaysia_cities)} cities...")

        forecasts = []
        prediction_time = datetime.utcnow()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            for city in malaysia_cities:
                try:
                    url = (
                        "https://api.open-meteo.com/v1/forecast"
                        f"?latitude={city['lat']}&longitude={city['lon']}"
                        "&daily=temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,"
                        "relative_humidity_2m_max,relative_humidity_2m_min,weather_code"
                        "&forecast_days=7&timezone=Asia/Kuala_Lumpur"
                    )
                    async with session.get(url) as response:
                        response.raise_for_status()
                        data = await response.json()

                    daily = data.get("daily", {})
                    times = daily.get("time", [])

                    for i, date_str in enumerate(times):
                        try:
                            target_start = datetime.fromisoformat(date_str)
                            target_end = target_start + timedelta(hours=24)

                            wind_deg = daily.get("wind_direction_10m_dominant", [None] * len(times))[i]
                            wind_dir = self._degrees_to_direction(wind_deg) if wind_deg is not None else None

                            forecasts.append({
                                "country": "malaysia",
                                "location": city["name"],
                                "latitude": city["lat"],
                                "longitude": city["lon"],
                                "prediction_time": prediction_time.isoformat(),
                                "target_time_start": target_start.isoformat(),
                                "target_time_end": target_end.isoformat(),
                                "temperature_low": daily.get("temperature_2m_min", [None] * len(times))[i],
                                "temperature_high": daily.get("temperature_2m_max", [None] * len(times))[i],
                                "humidity_low": daily.get("relative_humidity_2m_min", [None] * len(times))[i],
                                "humidity_high": daily.get("relative_humidity_2m_max", [None] * len(times))[i],
                                "wind_speed_low": None,
                                "wind_speed_high": daily.get("wind_speed_10m_max", [None] * len(times))[i],
                                "wind_direction": wind_dir,
                                "forecast_description": str(daily.get("weather_code", [None] * len(times))[i]),
                                "source_api": "open-meteo (malaysia)",
                            })
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Malaysia forecast parse error for {city['name']} day {i}: {e}")

                except Exception as e:
                    logger.warning(f"Malaysia Open-Meteo forecast failed for {city['name']}: {e}")

        logger.info(f"✓ Malaysia forecast collection complete: {len(forecasts)} records")
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
