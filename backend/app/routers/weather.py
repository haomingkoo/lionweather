"""
Weather API endpoint - fetches current weather from Open-Meteo
"""
from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/api", tags=["weather"])


@router.get("/weather")
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """
    Get current weather for a location using Open-Meteo API
    
    Returns:
        - condition: Weather condition description
        - temperature: Temperature in Celsius
        - area: Location name (reverse geocoded)
        - source: Data source identifier
    """
    try:
        # Fetch weather from Open-Meteo
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
                    "timezone": "Asia/Singapore",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        
        current = data.get("current", {})
        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code", 0)
        humidity = current.get("relative_humidity_2m")
        wind_speed = current.get("wind_speed_10m")
        
        # Map WMO weather codes to conditions
        condition = map_weather_code(weather_code)
        
        # Reverse geocode for area name
        area = await reverse_geocode(lat, lng)
        
        return {
            "condition": condition,
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "area": area,
            "source": "Open-Meteo",
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch weather data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def map_weather_code(code: int) -> str:
    """Map WMO weather codes to human-readable conditions"""
    weather_codes = {
        0: "Clear",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Foggy",
        51: "Light Drizzle",
        53: "Drizzle",
        55: "Heavy Drizzle",
        61: "Light Rain",
        63: "Rain",
        65: "Heavy Rain",
        71: "Light Snow",
        73: "Snow",
        75: "Heavy Snow",
        77: "Snow Grains",
        80: "Light Showers",
        81: "Showers",
        82: "Heavy Showers",
        85: "Light Snow Showers",
        86: "Snow Showers",
        95: "Thunderstorm",
        96: "Thunderstorm with Hail",
        99: "Thunderstorm with Hail",
    }
    return weather_codes.get(code, "Unknown")


async def reverse_geocode(lat: float, lng: float) -> str:
    """Reverse geocode coordinates to location name"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lng,
                    "zoom": 10,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "LionWeather/1.0"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        
        address = data.get("address", {})
        area = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("county")
            or address.get("state")
            or address.get("country")
            or "Unknown Area"
        )
        return area
    
    except Exception as e:
        print(f"Reverse geocoding failed: {e}")
        return "Unknown Area"
