import os
from fastapi import APIRouter, HTTPException
from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/twenty-four-hour")
def get_twenty_four_hour_forecast():
    """Get 24-hour weather forecast"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        headers = {
            "Accept": "application/json",
            "User-Agent": client.user_agent,
        }
        if api_key:
            headers["x-api-key"] = api_key
        
        import httpx
        with httpx.Client(timeout=client.timeout_seconds, headers=headers) as http_client:
            response = http_client.get(f"{client.base_url}/v2/real-time/api/twenty-four-hr-forecast")
            response.raise_for_status()
            data = response.json()
        
        # Extract forecast data
        items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
        
        if not items:
            return {"periods": []}
        
        latest = items[0]
        periods = latest.get("periods", [])
        
        # Format periods for frontend
        formatted_periods = []
        for period in periods:
            formatted_periods.append({
                "time": period.get("time", {}).get("text", ""),
                "regions": period.get("regions", {}),
                "timestamp": period.get("time", {}).get("timestamp", ""),
            })
        
        return {
            "timestamp": latest.get("timestamp"),
            "valid_period": latest.get("valid_period", {}),
            "periods": formatted_periods,
            "general": latest.get("general", {}),
        }
        
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/four-day")
def get_four_day_forecast():
    """Get 4-day weather outlook"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        headers = {
            "Accept": "application/json",
            "User-Agent": client.user_agent,
        }
        if api_key:
            headers["x-api-key"] = api_key
        
        import httpx
        with httpx.Client(timeout=client.timeout_seconds, headers=headers) as http_client:
            response = http_client.get(f"{client.base_url}/v2/real-time/api/four-day-outlook")
            response.raise_for_status()
            data = response.json()
        
        # Extract forecast data
        items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
        
        if not items:
            return {"forecasts": []}
        
        latest = items[0]
        forecasts = latest.get("forecasts", [])
        
        return {
            "timestamp": latest.get("timestamp"),
            "forecasts": forecasts,
        }
        
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/two-hour")
def get_two_hour_forecast():
    """Get 2-hour weather forecast with area details"""
    api_key = os.getenv("WEATHER_API_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    
    try:
        data = client.fetch_latest_forecast_payload()
        
        items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
        
        if not items:
            return {"forecasts": [], "area_metadata": []}
        
        latest = items[0]
        
        return {
            "timestamp": latest.get("timestamp"),
            "valid_period": latest.get("valid_period", {}),
            "forecasts": latest.get("forecasts", []),
            "area_metadata": data.get("data", {}).get("area_metadata", []) if isinstance(data.get("data"), dict) else data.get("area_metadata", []),
        }
        
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
