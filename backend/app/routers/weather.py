"""
Weather API endpoint - serves cached weather data from database
"""
import logging

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, timezone
import httpx
from app.db.database import fetch_all
from app.services.current_conditions import (
    describe_condition,
    is_daytime_sgt,
    pick_current_reading,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["weather"])


@router.get("/weather")
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
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
        now = datetime.now(timezone.utc)
        # Loose text prefilter: NEA stores +08:00 strings, Open-Meteo naive UTC.
        # Exact freshness is checked in pick_current_reading.
        cutoff = (now - timedelta(hours=2)).replace(tzinfo=None).isoformat()

        # Find nearest weather station with recent data
        # Simple bounding-box + Manhattan distance — works in SQLite and PostgreSQL
        # Singapore fits within ±0.5° of lat 1.35, lng 103.82
        sql = """
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
            FROM weather_records
            WHERE CAST(timestamp AS TEXT) > :cutoff
              AND latitude  BETWEEN :lat - 0.5 AND :lat + 0.5
              AND longitude BETWEEN :lng - 0.5 AND :lng + 0.5
            ORDER BY approx_dist ASC, timestamp DESC
            LIMIT 300
        """

        rows = [r._mapping for r in fetch_all(sql, {"lat": lat, "lng": lng, "cutoff": cutoff})]
        row = pick_current_reading(rows, now)

        if row:
            temperature = row["temperature"]
            rainfall = row["rainfall"] or 0

            ts = row["timestamp"]
            # NEA station data lacks sky state, visibility and pressure: take them from Open-Meteo
            pressure_val = row["pressure"]
            visibility_val = None
            uv_val = None
            sky = None
            is_day = is_daytime_sgt(now)
            try:
                om = await fetch_from_open_meteo(lat, lng)
                if pressure_val is None:
                    pressure_val = om.get("pressure")
                visibility_val = om.get("visibility")
                uv_val = om.get("uv_index")
                sky = om.get("condition")
                if om.get("is_day") is not None:
                    is_day = bool(om["is_day"])
            except Exception:
                pass
            condition = describe_condition(rainfall, sky, is_day)
            return {
                "condition": condition,
                "temperature": temperature,
                "humidity": row["humidity"],
                "wind_speed": row["wind_speed"],
                "pressure": pressure_val,
                "visibility": visibility_val,
                "uv_index": uv_val,
                "area": row["location"],
                "source": f"Cached ({row['source_api']})",
                "timestamp": ts if isinstance(ts, str) else str(ts) if ts else None,
                "distance_km": round(row["approx_dist"], 4) if row["approx_dist"] else None,
                "is_day": is_day,
            }
        
        # Fallback: No cached data available, fetch from Open-Meteo
        return await fetch_from_open_meteo(lat, lng)
    
    except Exception as e:
        # If database query fails, fallback to Open-Meteo
        try:
            return await fetch_from_open_meteo(lat, lng)
        except Exception:
            logger.exception(f"Weather lookup failed ({e}) and Open-Meteo fallback also failed")
            raise HTTPException(status_code=500, detail="Failed to fetch weather data")


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
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m,surface_pressure,visibility,uv_index,is_day",
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
    visibility_m = current.get("visibility")  # in metres
    uv_index = current.get("uv_index")

    # Convert visibility from metres to km, rounded to 1 decimal
    visibility_km = round(visibility_m / 1000, 1) if visibility_m is not None else None

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
        "visibility": visibility_km,
        "uv_index": uv_index,
        "area": area,
        "source": "Open-Meteo (Live)",
        "is_day": current.get("is_day"),
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
        print(f"Reverse geocoding failed: {type(e).__name__}")  # httpx errors carry the URL with coordinates
        return "Unknown Area"
