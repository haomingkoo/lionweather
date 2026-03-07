import os
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/environmental", tags=["environmental"])

BASE_URL = "https://api-open.data.gov.sg"
TIMEOUT = 8.0


def fetch_api_data(endpoint: str, api_key: str = None):
    """Helper to fetch data from Singapore API"""
    headers = {
        "Accept": "application/json",
        "User-Agent": "weather-starter/0.1 (educational project)",
    }
    if api_key:
        headers["x-api-key"] = api_key
    
    try:
        with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
            response = client.get(f"{BASE_URL}{endpoint}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return None


@router.get("/air-quality")
def get_air_quality():
    """Get PM2.5 and PSI (air quality) data"""
    api_key = os.getenv("WEATHER_API_KEY")
    
    # Fetch PM2.5
    pm25_data = fetch_api_data("/v2/real-time/api/pm25", api_key)
    
    # Fetch PSI
    psi_data = fetch_api_data("/v2/real-time/api/psi", api_key)
    
    result = {
        "pm25": None,
        "psi": None,
        "timestamp": None,
    }
    
    # Extract PM2.5
    if pm25_data:
        items = pm25_data.get("data", {}).get("items", []) if isinstance(pm25_data.get("data"), dict) else pm25_data.get("items", [])
        if items:
            latest = items[0]
            result["pm25"] = latest.get("readings", {})
            result["timestamp"] = latest.get("timestamp")
    
    # Extract PSI
    if psi_data:
        items = psi_data.get("data", {}).get("items", []) if isinstance(psi_data.get("data"), dict) else psi_data.get("items", [])
        if items:
            latest = items[0]
            result["psi"] = latest.get("readings", {})
            if not result["timestamp"]:
                result["timestamp"] = latest.get("timestamp")
    
    return result


@router.get("/uv-index")
def get_uv_index():
    """Get UV index data"""
    api_key = os.getenv("WEATHER_API_KEY")
    
    uv_data = fetch_api_data("/v2/real-time/api/uv", api_key)
    
    if not uv_data:
        return {"uv_index": None, "timestamp": None}
    
    items = uv_data.get("data", {}).get("items", []) if isinstance(uv_data.get("data"), dict) else uv_data.get("items", [])
    
    if not items:
        return {"uv_index": None, "timestamp": None}
    
    latest = items[0]
    
    return {
        "uv_index": latest.get("index", []),
        "timestamp": latest.get("timestamp"),
    }


@router.get("/lightning")
def get_lightning():
    """Get lightning strike data"""
    api_key = os.getenv("WEATHER_API_KEY")
    
    lightning_data = fetch_api_data("/v2/real-time/api/weather?api=lightning", api_key)
    
    if not lightning_data:
        return {"strikes": [], "timestamp": None}
    
    items = lightning_data.get("data", {}).get("items", []) if isinstance(lightning_data.get("data"), dict) else lightning_data.get("items", [])
    
    if not items:
        return {"strikes": [], "timestamp": None}
    
    latest = items[0]
    
    return {
        "strikes": latest.get("lightning", []),
        "timestamp": latest.get("timestamp"),
    }


@router.get("/all-sensors")
def get_all_sensor_data():
    """Get ALL environmental sensor data for ML training"""
    api_key = os.getenv("WEATHER_API_KEY")
    
    # Fetch all data in parallel
    endpoints = {
        "temperature": "/v2/real-time/api/air-temperature",
        "humidity": "/v2/real-time/api/relative-humidity",
        "rainfall": "/v2/real-time/api/rainfall",
        "wind_speed": "/v2/real-time/api/wind-speed",
        "wind_direction": "/v2/real-time/api/wind-direction",
        "pm25": "/v2/real-time/api/pm25",
        "psi": "/v2/real-time/api/psi",
        "uv": "/v2/real-time/api/uv",
    }
    
    result = {
        "timestamp": None,
        "sensors": {},
    }
    
    for key, endpoint in endpoints.items():
        data = fetch_api_data(endpoint, api_key)
        if data:
            items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
            if items:
                latest = items[0]
                result["sensors"][key] = {
                    "readings": latest.get("readings", latest.get("index", [])),
                    "timestamp": latest.get("timestamp"),
                }
                if not result["timestamp"]:
                    result["timestamp"] = latest.get("timestamp")
    
    return result
