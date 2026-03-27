import logging
from fastapi import APIRouter, HTTPException
from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError
from app.db.database import fetch_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/comprehensive/{location_id}")
def get_comprehensive_weather(location_id: str, lat: float = None, lng: float = None):
    """Get comprehensive weather data including temperature, humidity, wind, etc."""

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

    client = SingaporeWeatherClient()

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

    fetch_tasks = [
        ("temperature", client.temperature_path),
        ("humidity", client.humidity_path),
        ("wind_speed", client.wind_speed_path),
        ("wind_direction", client.wind_direction_path),
    ]

    for field, path in fetch_tasks:
        try:
            http_client = client._get_client()
            data = client._fetch_json(http_client, f"{client.base_url}{path}")
            result[field] = _find_nearest_reading(data, latitude, longitude)
        except Exception as e:
            logger.warning(f"Failed to fetch {field} from NEA: {e}")

    return result


def _find_nearest_reading(data: dict, target_lat: float, target_lon: float):
    """Find the nearest weather station reading to the target coordinates."""
    items = (
        data.get("data", {}).get("items", [])
        if isinstance(data.get("data"), dict)
        else data.get("items", [])
    )

    if not items:
        return None

    latest_item = items[0]
    readings = latest_item.get("readings", [])
    metadata = (
        data.get("data", {}).get("metadata", {})
        if isinstance(data.get("data"), dict)
        else data.get("metadata", {})
    )
    stations = metadata.get("stations", [])

    nearest_value = None
    nearest_distance = None

    for reading in readings:
        station_id = reading.get("station_id")
        value = reading.get("value")

        station = next((s for s in stations if s.get("id") == station_id), None)
        if not station or value is None:
            continue

        location = station.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")

        if lat is None or lon is None:
            continue

        distance = (float(lat) - target_lat) ** 2 + (float(lon) - target_lon) ** 2

        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_value = value

    return nearest_value
