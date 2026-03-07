import os
from fastapi import APIRouter, HTTPException

from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError

router = APIRouter(prefix="/rainfall", tags=["rainfall"])


@router.get("")
def get_rainfall_data():
    """Get real-time rainfall data from Singapore weather stations"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        data = client.fetch_rainfall_data()
        
        # Handle new API format (v2)
        if "data" in data and isinstance(data["data"], dict):
            api_data = data["data"]
            stations_meta = api_data.get("stations", [])
            readings_list = api_data.get("readings", [])
            
            if not readings_list:
                return {"stations": []}
            
            # Get latest reading
            latest_reading = readings_list[0]
            timestamp = latest_reading.get("timestamp")
            station_readings = latest_reading.get("data", [])
            
            # Format for frontend
            stations = []
            for reading in station_readings:
                station_id = reading.get("stationId")
                value = reading.get("value")
                
                # Find station metadata
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
                        "rainfall": value,
                    })
            
            return {
                "timestamp": timestamp,
                "stations": stations
            }
        
        # Fallback to old format handling
        items = data.get("items", [])
        if not items:
            return {"stations": []}
        
        latest_item = items[0]
        readings = latest_item.get("readings", [])
        
        # Format for frontend
        stations = []
        for reading in readings:
            station_id = reading.get("station_id")
            value = reading.get("value")
            
            # Get station metadata (lat/lon)
            metadata = data.get("metadata", {})
            stations_meta = metadata.get("stations", [])
            
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
                    "rainfall": value,
                })
        
        return {
            "timestamp": latest_item.get("timestamp"),
            "stations": stations
        }
        
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
