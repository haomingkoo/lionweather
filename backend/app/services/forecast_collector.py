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
    
    # NEA region → approximate centroid coordinates for Singapore's 5 regions
    # Used to associate forecasts with weather stations for benchmarking
    _NEA_REGION_COORDS = {
        "north":   {"lat": 1.4184, "lon": 103.8200},
        "south":   {"lat": 1.2700, "lon": 103.8198},
        "east":    {"lat": 1.3236, "lon": 103.9600},
        "west":    {"lat": 1.3500, "lon": 103.7000},
        "central": {"lat": 1.3521, "lon": 103.8198},
    }

    async def fetch_singapore_forecast(self) -> List[Dict]:
        """
        Fetch Singapore NEA 24-hour weather forecast — per region.

        The v1 public API (api.data.gov.sg/v1) returns 3 time periods × 5 regions
        (north/south/east/west/central), each with its own forecast condition.
        We store all 15 records so the NEA benchmark can compare per-region.

        Falls back to v2 (requires no auth for now) if v1 fails.

        Returns:
            List of forecast dictionaries (~15 per call)
        """
        logger.info("🌤️ Fetching Singapore NEA 24h forecast (per region)...")

        # v1 API is public and returns per-region data
        url = "https://api.data.gov.sg/v1/environment/24-hour-weather-forecast"

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()

                forecasts = self._parse_singapore_forecast(data)
                logger.info(f"Parsed {len(forecasts)} Singapore NEA per-region forecast records")
                return forecasts

            except Exception as e:
                logger.error(f"Failed to fetch Singapore forecast: {e}")
                return []

    def _parse_singapore_forecast(self, data: dict) -> List[Dict]:
        """
        Parse Singapore NEA v1 24-hour forecast API response.

        Extracts per-region forecasts (north/south/east/west/central) for each
        time period. Each region + period → one forecast record.

        Response structure:
            items[0].general   → overall Singapore temp/humidity/wind/condition
            items[0].periods[] → list of time windows, each with .regions dict
        """
        forecasts = []

        try:
            items = data.get("items", [])
            if not items:
                logger.warning("No items in Singapore NEA v1 forecast response")
                return forecasts

            item = items[0]
            prediction_time = datetime.utcnow()

            # General (Singapore-wide) metadata
            general = item.get("general", {})
            temp       = general.get("temperature", {})
            humidity   = general.get("relative_humidity", {})
            wind       = general.get("wind", {})
            wind_speed = wind.get("speed", {})

            temp_low       = temp.get("low", 0)
            temp_high      = temp.get("high", 0)
            humidity_low   = humidity.get("low", 0)
            humidity_high  = humidity.get("high", 0)
            wind_speed_low = wind_speed.get("low", 0)
            wind_speed_high= wind_speed.get("high", 0)
            wind_direction = wind.get("direction", "")

            periods = item.get("periods", [])
            if not periods:
                logger.warning("No periods in NEA forecast response")
                return forecasts

            for period in periods:
                time_info = period.get("time", {})
                start_str = time_info.get("start")
                end_str   = time_info.get("end")
                if not start_str or not end_str:
                    continue

                try:
                    target_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    target_end   = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                regions = period.get("regions", {})

                # One record per region per period (5 regions × 3 periods = 15 records per call)
                for region_name, region_forecast in regions.items():
                    coords = self._NEA_REGION_COORDS.get(region_name, {"lat": 1.3521, "lon": 103.8198})
                    forecasts.append({
                        "country": "singapore",
                        "location": f"Singapore ({region_name.capitalize()})",
                        "latitude": coords["lat"],
                        "longitude": coords["lon"],
                        "nea_region": region_name,
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
                        "forecast_description": region_forecast,
                        "source_api": "nea",
                    })
        
        except Exception as e:
            logger.error(f"Error parsing Singapore forecast: {e}")
        
        return forecasts
    
    # Malay forecast descriptions → English
    _MALAY_FORECAST_MAP = {
        "Berjerebu": "Hazy",
        "Tiada hujan": "No Rain",
        "Hujan": "Rain",
        "Hujan di beberapa tempat": "Scattered Rain",
        "Hujan di satu dua tempat": "Isolated Rain",
        "Hujan di satu dua tempat di kawasan pantai": "Isolated Rain (Coastal)",
        "Hujan di satu dua tempat di kawasan pedalaman": "Isolated Rain (Inland)",
        "Ribut petir": "Thunderstorm",
        "Ribut petir di beberapa tempat": "Scattered Thunderstorms",
        "Ribut petir di beberapa tempat di kawasan pedalaman": "Scattered Thunderstorms (Inland)",
        "Ribut petir di satu dua tempat": "Isolated Thunderstorms",
        "Ribut petir di satu dua tempat di kawasan pantai": "Isolated Thunderstorms (Coastal)",
        "Ribut petir di satu dua tempat di kawasan pedalaman": "Isolated Thunderstorms (Inland)",
    }

    async def fetch_malaysia_forecast(self) -> List[Dict]:
        """
        Fetch Malaysia 7-day general forecast from data.gov.my (MET Malaysia).

        Endpoint: GET https://api.data.gov.my/weather/forecast
        Free, no authentication required. Updated daily.
        Returns per-district forecasts (morning / afternoon / night + temp range).

        Returns:
            List of forecast dictionaries
        """
        logger.info("🌤️ Fetching Malaysia forecast from data.gov.my (MET Malaysia)...")

        forecasts = []
        prediction_time = datetime.utcnow()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            # Fetch all state + district forecasts in one call (limit 500 covers full dataset)
            url = "https://api.data.gov.my/weather/forecast?limit=500"
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
            except Exception as e:
                logger.error(f"Failed to fetch Malaysia data.gov.my forecast: {e}")
                return []

        # API returns a list directly
        items = data if isinstance(data, list) else data.get("data", [])
        logger.info(f"Received {len(items)} Malaysia forecast records from data.gov.my")

        for item in items:
            try:
                loc = item.get("location", {})
                location_name = loc.get("location_name") or item.get("location_name", "Unknown")
                date_str = item.get("date")
                if not date_str:
                    continue

                target_start = datetime.fromisoformat(date_str)
                target_end = target_start + timedelta(hours=24)

                # Translate Malay forecast text to English
                raw_summary = item.get("summary_forecast") or item.get("morning_forecast") or ""
                description = self._MALAY_FORECAST_MAP.get(raw_summary, raw_summary)

                forecasts.append({
                    "country": "malaysia",
                    "location": location_name,
                    "latitude": 0.0,   # data.gov.my doesn't provide coordinates per location
                    "longitude": 0.0,
                    "prediction_time": prediction_time.isoformat(),
                    "target_time_start": target_start.isoformat(),
                    "target_time_end": target_end.isoformat(),
                    "temperature_low": item.get("min_temp"),
                    "temperature_high": item.get("max_temp"),
                    "humidity_low": None,
                    "humidity_high": None,
                    "wind_speed_low": None,
                    "wind_speed_high": None,
                    "wind_direction": None,
                    "forecast_description": description,
                    "morning_forecast": self._MALAY_FORECAST_MAP.get(
                        item.get("morning_forecast", ""), item.get("morning_forecast", "")
                    ),
                    "afternoon_forecast": self._MALAY_FORECAST_MAP.get(
                        item.get("afternoon_forecast", ""), item.get("afternoon_forecast", "")
                    ),
                    "night_forecast": self._MALAY_FORECAST_MAP.get(
                        item.get("night_forecast", ""), item.get("night_forecast", "")
                    ),
                    "source_api": "data.gov.my (MET Malaysia)",
                })
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Malaysia forecast parse error for item: {e}")

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
