"""
Regional Weather Service for fetching weather data from Malaysian and Indonesian cities.

This service integrates:
- Malaysian Weather API (data.gov.my) for ~10-12 Malaysian cities
- WeatherAPI for ~15-18 Indonesian cities

Total coverage: 25-30 cities across Singapore, Malaysia, and Indonesia.
Cache TTL: 30 minutes
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class RegionalAPIError(Exception):
    """Exception raised when regional API requests fail"""
    pass


@dataclass
class CityWeather:
    """Data model for city weather information"""
    id: str
    name: str
    country: str
    temperature: float
    condition: str
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    last_updated: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "temperature": self.temperature,
            "condition": self.condition,
            "humidity": self.humidity,
            "windSpeed": self.wind_speed,
            "lastUpdated": self.last_updated.isoformat() if self.last_updated else None
        }


class RegionalWeatherService:
    """
    Service for fetching weather data from Malaysian and Indonesian cities.
    
    Integrates two APIs:
    - Malaysian Weather API (data.gov.my) - free, no key required
    - WeatherAPI - requires free API key
    
    Implements 30-minute caching to minimize API calls.
    """
    
    def __init__(
        self,
        cache_ttl_seconds: int = 1800,  # 30 minutes
        timeout_seconds: float = 10.0,
        weatherapi_key: Optional[str] = None
    ):
        self.malaysian_api_url = "https://api.data.gov.my/weather/forecast"
        self.weatherapi_url = "https://api.weatherapi.com/v1/current.json"
        self.weatherapi_key = weatherapi_key or os.getenv("WEATHERAPI_KEY")
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.timeout = timeout_seconds
        
        # In-memory cache
        self.city_cache: list[CityWeather] = []
        self.cache_timestamp: Optional[datetime] = None
        
        # Curated city lists (~10-12 Malaysian cities)
        self.malaysian_cities = [
            "Kuala Lumpur",
            "George Town",
            "Johor Bahru",
            "Ipoh",
            "Kuching",
            "Kota Kinabalu",
            "Shah Alam",
            "Malacca",
            "Alor Setar",
            "Miri",
            "Petaling Jaya",
            "Seremban"
        ]
        
        # Curated city lists (~15-18 Indonesian cities)
        self.indonesian_cities = [
            "Jakarta",
            "Surabaya",
            "Bandung",
            "Medan",
            "Semarang",
            "Makassar",
            "Palembang",
            "Tangerang",
            "Depok",
            "Batam",
            "Pekanbaru",
            "Bandar Lampung",
            "Padang",
            "Denpasar",
            "Samarinda",
            "Balikpapan",
            "Pontianak",
            "Manado"
        ]
    
    def is_cache_valid(self) -> bool:
        """Check if cached city data is still valid based on TTL"""
        if not self.cache_timestamp or not self.city_cache:
            return False
        
        age = datetime.now() - self.cache_timestamp
        return age < self.cache_ttl
    
    async def get_regional_cities(self) -> list[CityWeather]:
        """
        Get regional city weather data from cache or fetch if cache is invalid.
        
        Returns:
            List of CityWeather objects for Malaysian and Indonesian cities
        """
        # If cache is valid, return cached data
        if self.is_cache_valid():
            logger.info("Returning cached regional city data")
            return self.city_cache
        
        # Fetch fresh data from both APIs
        try:
            logger.info("Fetching fresh regional weather data")
            malaysian_data = await self.fetch_malaysian_data()
            indonesian_data = await self.fetch_indonesian_data()
            
            # Combine results
            cities = malaysian_data + indonesian_data
            
            # Update cache
            self.city_cache = cities
            self.cache_timestamp = datetime.now()
            
            logger.info(f"Successfully cached {len(cities)} regional cities "
                       f"({len(malaysian_data)} Malaysian, {len(indonesian_data)} Indonesian)")
            return cities
            
        except Exception as e:
            logger.error(f"Regional weather fetch failed: {e}")
            # Return stale cache if available
            if self.city_cache:
                logger.info("Returning stale cached city data")
                return self.city_cache
            raise RegionalAPIError("Weather data unavailable") from e
    
    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict] = None,
        max_retries: int = 3
    ) -> httpx.Response:
        """
        Fetch data with exponential backoff retry logic.
        
        Args:
            client: HTTP client instance
            url: URL to fetch
            params: Optional query parameters
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, Exception) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = delays[attempt]
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
        
        # Raise the last exception if all retries failed
        if last_exception:
            raise last_exception
    
    async def fetch_malaysian_data(self) -> list[CityWeather]:
        """
        Fetch weather data from Malaysian Weather API (data.gov.my) with retry logic.
        
        Returns:
            List of CityWeather objects for Malaysian cities
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await self._fetch_with_retry(client, self.malaysian_api_url)
                data = response.json()
                return self.transform_malaysian_response(data)
        except httpx.HTTPError as e:
            logger.error(f"Malaysian Weather API error: {e}")
            raise RegionalAPIError("Failed to fetch Malaysian weather data") from e
    
    async def fetch_indonesian_data(self) -> list[CityWeather]:
        """
        Fetch weather data from WeatherAPI for Indonesian cities with batch processing.
        
        Uses asyncio.gather to fetch all cities concurrently with individual error handling.
        Each city fetch includes retry logic with exponential backoff.
        
        Returns:
            List of CityWeather objects for Indonesian cities
        """
        if not self.weatherapi_key:
            logger.warning("WeatherAPI key not configured, skipping Indonesian cities")
            return []
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                self.fetch_indonesian_city_with_retry(client, city)
                for city in self.indonesian_cities
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and return successful results
            cities = [r for r in results if isinstance(r, CityWeather)]
            failed = len(results) - len(cities)
            
            if failed > 0:
                logger.warning(f"Failed to fetch {failed}/{len(self.indonesian_cities)} Indonesian cities")
            else:
                logger.info(f"Successfully fetched all {len(cities)} Indonesian cities")
            
            return cities
    
    async def fetch_indonesian_city_with_retry(
        self,
        client: httpx.AsyncClient,
        city: str,
        max_retries: int = 3
    ) -> CityWeather:
        """
        Fetch weather data for a single Indonesian city with retry logic.
        
        Args:
            client: HTTP client instance
            city: City name
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            CityWeather object
            
        Raises:
            Exception: If all retries fail
        """
        delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
        
        for attempt in range(max_retries):
            try:
                params = {
                    "key": self.weatherapi_key,
                    "q": city,
                    "aqi": "no"
                }
                response = await client.get(self.weatherapi_url, params=params)
                response.raise_for_status()
                data = response.json()
                return self.transform_weatherapi_response(city, data)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = delays[attempt]
                    logger.warning(
                        f"Failed to fetch {city} (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to fetch {city} after {max_retries} attempts: {e}")
                    raise
    
    def transform_malaysian_response(self, raw_data: dict) -> list[CityWeather]:
        """
        Transform Malaysian Weather API response to internal format.
        
        Args:
            raw_data: Raw JSON response from Malaysian Weather API
            
        Returns:
            List of CityWeather objects
        """
        cities = []
        
        try:
            # Malaysian API returns array of location forecasts
            for item in raw_data:
                location = item.get("location", {})
                location_name = location.get("location_name", "")
                
                # Filter for our curated cities
                if location_name not in self.malaysian_cities:
                    continue
                
                # Extract forecast data (use first forecast period)
                forecasts = item.get("forecasts", [])
                if not forecasts:
                    continue
                
                forecast = forecasts[0]
                
                # Extract temperature (use max temp as current temp approximation)
                temp_max = forecast.get("temperature", {}).get("max")
                if temp_max is None:
                    continue
                
                # Extract condition
                condition = forecast.get("summary", {}).get("text", "Unknown")
                
                # Create city ID
                city_id = location_name.lower().replace(" ", "-")
                
                city = CityWeather(
                    id=city_id,
                    name=location_name,
                    country="Malaysia",
                    temperature=float(temp_max),
                    condition=condition,
                    humidity=None,  # Not provided by Malaysian API
                    wind_speed=None,  # Not provided by Malaysian API
                    last_updated=datetime.now()
                )
                cities.append(city)
                
        except Exception as e:
            logger.error(f"Error transforming Malaysian API response: {e}")
        
        return cities
    
    def transform_weatherapi_response(self, city_name: str, raw_data: dict) -> CityWeather:
        """
        Transform WeatherAPI response to internal format.
        
        Args:
            city_name: Name of the city
            raw_data: Raw JSON response from WeatherAPI
            
        Returns:
            CityWeather object
        """
        current = raw_data.get("current", {})
        location = raw_data.get("location", {})
        
        # Extract data
        temperature = current.get("temp_c")
        condition = current.get("condition", {}).get("text", "Unknown")
        humidity = current.get("humidity")
        wind_speed = current.get("wind_kph")
        
        # Parse last updated timestamp
        last_updated_str = current.get("last_updated")
        last_updated = None
        if last_updated_str:
            try:
                last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        # Create city ID
        city_id = city_name.lower().replace(" ", "-")
        
        return CityWeather(
            id=city_id,
            name=city_name,
            country="Indonesia",
            temperature=float(temperature) if temperature is not None else 0.0,
            condition=condition,
            humidity=float(humidity) if humidity is not None else None,
            wind_speed=float(wind_speed) if wind_speed is not None else None,
            last_updated=last_updated or datetime.now()
        )


# Global singleton instance
_regional_weather_service_instance: Optional[RegionalWeatherService] = None


def get_regional_weather_service() -> RegionalWeatherService:
    """
    Get the global RegionalWeatherService instance.
    
    Returns:
        RegionalWeatherService singleton instance
    """
    global _regional_weather_service_instance
    if _regional_weather_service_instance is None:
        _regional_weather_service_instance = RegionalWeatherService()
    return _regional_weather_service_instance
