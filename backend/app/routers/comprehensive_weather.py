import os
import logging
from fastapi import APIRouter, HTTPException
from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError
from app.db.database import fetch_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/comprehensive/{location_id}")
def get_comprehensive_weather(location_id: str, lat: float = None, lng: float = None):
    """Get comprehensive weather data from NEA real-time API."""

    if lat is not None and lng is not None:
        latitude = lat
        longitude = lng
    else:
        row = fetch_one(
            "SELECT latitude, longitude FROM locations WHERE id = :id",
            {"id": location_id},
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Location not found. Provide lat and lng parameters.",
            )
        latitude = row[0]
        longitude = row[1]

    api_key = os.getenv("WEATHERAPI_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    http_client = client._get_client()

    result = {
        "location_id": location_id,
        "latitude": latitude,
        "longitude": longitude,
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "wind_direction": None,
        "rainfall": None,
    }

    endpoints = [
        ("temperature", client.temperature_path),
        ("humidity", client.humidity_path),
        ("wind_speed", client.wind_speed_path),
        ("wind_direction", client.wind_direction_path),
    ]

    for field, path in endpoints:
        try:
            raw = client._fetch_json(http_client, f"{client.base_url}{path}")
            result[field] = _find_nearest_value(raw, latitude, longitude)
        except Exception as e:
            logger.warning(f"Failed to fetch {field} from NEA: {e}")

    http_client.close()
    return result


def _find_nearest_value(raw: dict, target_lat: float, target_lon: float):
    """Find nearest station value from NEA v2 real-time API response.

    Response format:
    {
      "data": {
        "stations": [{"id": "S109", "location": {"latitude": 1.37, "longitude": 103.84}}, ...],
        "readings": [{"timestamp": "...", "data": [{"stationId": "S109", "value": 25.9}, ...]}]
      }
    }
    """
    data = raw.get("data", {})
    stations = data.get("stations", [])
    readings = data.get("readings", [])

    if not stations or not readings:
        return None

    # Build station location lookup
    station_locs = {}
    for s in stations:
        loc = s.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is not None and lon is not None:
            station_locs[s["id"]] = (float(lat), float(lon))

    # Get latest readings
    latest = readings[0].get("data", []) if readings else []

    nearest_value = None
    nearest_dist = None

    for entry in latest:
        sid = entry.get("stationId")
        value = entry.get("value")
        if sid not in station_locs or value is None:
            continue

        slat, slon = station_locs[sid]
        dist = (slat - target_lat) ** 2 + (slon - target_lon) ** 2

        if nearest_dist is None or dist < nearest_dist:
            nearest_dist = dist
            nearest_value = value

    return nearest_value
