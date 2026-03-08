"""
Weather API endpoint - serves cached weather data from database
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import httpx
from app.db.database import get_db

router = APIRouter(prefix="/api", tags=["weather"])


@router.get("/weather")
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    db: Session = Depends(get_db),
):
    """
    Get current weather for a location from cached database
    
    Returns cached weather data from the nearest location in the database.
    Falls back to Open-Meteo API if no cached data is available.
    
    Returns:
        - condition: Weather condition description
        - temperature: Temperature in Celsius
        - humidity: Humidity percentage
        - wind_speed: Wind speed in km/h
        - pressure: Atmospheric pressure in hPa
        - area: Location name
        - source: Data source identifier
    """
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()

        # Find nearest weather station with recent data (within last 2 hours)
        # Simple bounding-box + Manhattan distance — works in SQLite and PostgreSQL
        # Singapore fits within ±0.5° of lat 1.35, lng 103.82
        query = text("""
            SELECT
                location,
                temperature,
                humidity,
                wind_speed,
                pressure,
                rainfall,
                country,
                source_api,
                timestamp,
                (abs(latitude - :lat) + abs(longitude - :lng)) AS approx_dist
            FROM weather_data
            WHERE CAST(timestamp AS TEXT) > :cutoff
              AND latitude  BETWEEN :lat - 0.5 AND :lat + 0.5
              AND longitude BETWEEN :lng - 0.5 AND :lng + 0.5
            ORDER BY approx_dist ASC
            LIMIT 1
        """)

        result = db.execute(query, {"lat": lat, "lng": lng, "cutoff": cutoff}).fetchone()
        
        if result:
            # Map temperature to weather condition (simplified)
            # In production, you'd want to store actual conditions in the database
            temperature = result[1]
            rainfall = result[5]
            
            if rainfall > 5:
                condition = "Rainy"
            elif rainfall > 0:
                condition = "Light Rain"
            elif temperature > 30:
                condition = "Sunny"
            elif temperature > 25:
                condition = "Partly Cloudy"
            else:
                condition = "Cloudy"
            
            return {
                "condition": condition,
                "temperature": result[1],
                "humidity": result[2],
                "wind_speed": result[3],
                "pressure": result[4],
                "area": result[0],
                "source": f"Cached ({result[7]})",
                "timestamp": result[8].isoformat() if result[8] else None,
                "distance_km": round(result[9], 2) if result[9] else None,
            }
        
        # Fallback: No cached data available, fetch from Open-Meteo
        return await fetch_from_open_meteo(lat, lng)
    
    except Exception as e:
        # If database query fails, fallback to Open-Meteo
        try:
            return await fetch_from_open_meteo(lat, lng)
        except Exception as fallback_error:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch weather data: {str(e)}. Fallback also failed: {str(fallback_error)}"
            )


async def fetch_from_open_meteo(lat: float, lng: float) -> dict:
    """
    Fallback function to fetch weather from Open-Meteo API
    Used when no cached data is available
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lng,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m,surface_pressure",
                "timezone": "auto",
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
    pressure = current.get("surface_pressure")
    
    # Map WMO weather codes to conditions
    condition = map_weather_code(weather_code)
    
    # Reverse geocode for area name
    area = await reverse_geocode(lat, lng)
    
    return {
        "condition": condition,
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "pressure": pressure,
        "area": area,
        "source": "Open-Meteo (Live)",
    }


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
                    "zoom": 16,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "LionWeather/1.0"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        address = data.get("address", {})
        area = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("quarter")
            or address.get("village")
            or address.get("town")
            or address.get("city_district")
            or address.get("city")
            or address.get("county")
            or address.get("state")
            or address.get("country")
            or "Unknown Area"
        )
        return area
    
    except Exception as e:
        print(f"Reverse geocoding failed: {e}")
        return "Unknown Area"
