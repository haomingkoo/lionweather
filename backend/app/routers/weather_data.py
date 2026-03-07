import os
from fastapi import APIRouter, HTTPException

from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError

router = APIRouter(prefix="/weather-data", tags=["weather-data"])


def extract_station_readings(data, value_key="value"):
    """Extract station readings from API response"""
    items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
    
    if not items:
        return [], None
    
    latest_item = items[0]
    readings = latest_item.get("readings", [])
    
    # Get station metadata
    metadata = data.get("data", {}).get("metadata", {}) if isinstance(data.get("data"), dict) else data.get("metadata", {})
    stations_meta = metadata.get("stations", [])
    
    stations = []
    for reading in readings:
        station_id = reading.get("station_id")
        value = reading.get(value_key)
        
        station_info = next(
            (s for s in stations_meta if s.get("id") == station_id),
            None
        )
        
        if station_info and value is not None:
            location = station_info.get("location", {})
            stations.append({
                "id": station_id,
                "name": station_info.get("name", station_id),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "value": value,
            })
    
    return stations, latest_item.get("timestamp")


@router.get("/temperature")
def get_temperature_data():
    """Get real-time temperature data"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        data = client.fetch_temperature_data()
        stations, timestamp = extract_station_readings(data)
        
        return {
            "timestamp": timestamp,
            "stations": stations,
            "unit": "°C"
        }
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/wind")
def get_wind_data():
    """Get real-time wind data"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        wind_data = client.fetch_wind_data()
        
        speed_stations, speed_timestamp = extract_station_readings(wind_data["speed"])
        direction_stations, _ = extract_station_readings(wind_data["direction"])
        
        # Merge speed and direction by station_id
        stations = []
        for speed_station in speed_stations:
            direction_station = next(
                (d for d in direction_stations if d["id"] == speed_station["id"]),
                None
            )
            
            stations.append({
                "id": speed_station["id"],
                "name": speed_station["name"],
                "latitude": speed_station["latitude"],
                "longitude": speed_station["longitude"],
                "speed": speed_station["value"],
                "direction": direction_station["value"] if direction_station else None,
            })
        
        return {
            "timestamp": speed_timestamp,
            "stations": stations,
            "unit": "knots"
        }
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/humidity")
def get_humidity_data():
    """Get real-time humidity data"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        data = client.fetch_humidity_data()
        stations, timestamp = extract_station_readings(data)
        
        return {
            "timestamp": timestamp,
            "stations": stations,
            "unit": "%"
        }
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
