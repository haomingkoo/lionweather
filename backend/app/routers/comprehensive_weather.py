import os
from fastapi import APIRouter, HTTPException
from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/comprehensive/{location_id}")
def get_comprehensive_weather(location_id: int):
    """Get comprehensive weather data including temperature, humidity, wind, etc."""
    import sqlite3
    
    DB_PATH = os.getenv("DATABASE_PATH", "weather.db")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    con.close()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")
    
    latitude = row["latitude"]
    longitude = row["longitude"]
    
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
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
    
    # Fetch temperature
    try:
        temp_data = client._fetch_json(
            client._get_client(),
            f"{client.base_url}{client.temperature_path}"
        )
        result["temperature"] = _find_nearest_reading(temp_data, latitude, longitude)
    except:
        pass
    
    # Fetch humidity
    try:
        humidity_data = client._fetch_json(
            client._get_client(),
            f"{client.base_url}{client.humidity_path}"
        )
        result["humidity"] = _find_nearest_reading(humidity_data, latitude, longitude)
    except:
        pass
    
    # Fetch wind speed
    try:
        wind_speed_data = client._fetch_json(
            client._get_client(),
            f"{client.base_url}{client.wind_speed_path}"
        )
        result["wind_speed"] = _find_nearest_reading(wind_speed_data, latitude, longitude)
    except:
        pass
    
    # Fetch wind direction
    try:
        wind_dir_data = client._fetch_json(
            client._get_client(),
            f"{client.base_url}{client.wind_direction_path}"
        )
        result["wind_direction"] = _find_nearest_reading(wind_dir_data, latitude, longitude)
    except:
        pass
    
    return result


def _find_nearest_reading(data: dict, target_lat: float, target_lon: float):
    """Find the nearest weather station reading to the target coordinates"""
    items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
    
    if not items:
        return None
    
    latest_item = items[0]
    readings = latest_item.get("readings", [])
    metadata = data.get("data", {}).get("metadata", {}) if isinstance(data.get("data"), dict) else data.get("metadata", {})
    stations = metadata.get("stations", [])
    
    nearest_value = None
    nearest_distance = None
    
    for reading in readings:
        station_id = reading.get("station_id")
        value = reading.get("value")
        
        # Find station metadata
        station = next((s for s in stations if s.get("id") == station_id), None)
        if not station or value is None:
            continue
        
        location = station.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")
        
        if lat is None or lon is None:
            continue
        
        # Calculate distance
        distance = (float(lat) - target_lat) ** 2 + (float(lon) - target_lon) ** 2
        
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_value = value
    
    return nearest_value
