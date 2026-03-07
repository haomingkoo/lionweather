import os
import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional, List, Dict
from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError
from app.db.database import get_connection

logger = logging.getLogger(__name__)

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



@router.get("/latest")
def get_latest_forecasts(
    country: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 100
):
    """
    Get latest official forecasts from forecast_data table.
    
    Args:
        country: Optional country filter (e.g., 'singapore', 'malaysia', 'indonesia')
        location: Optional location filter
        limit: Maximum number of forecasts to return (default: 100)
    
    Returns:
        List of latest forecasts with prediction and target times
    """
    con = get_connection()
    cursor = con.cursor()
    
    try:
        # Build query with optional filters
        query = """
            SELECT 
                id,
                prediction_time,
                target_time_start,
                target_time_end,
                country,
                location,
                latitude,
                longitude,
                temperature_low,
                temperature_high,
                humidity_low,
                humidity_high,
                wind_speed_low,
                wind_speed_high,
                wind_direction,
                forecast_description,
                source_api,
                created_at
            FROM forecast_data
            WHERE 1=1
        """
        params = []
        
        if country:
            query += " AND country = ?"
            params.append(country.lower())
        
        if location:
            query += " AND location = ?"
            params.append(location)
        
        query += " ORDER BY prediction_time DESC, target_time_start ASC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        forecasts = []
        for row in rows:
            forecasts.append({
                "id": row["id"],
                "prediction_time": row["prediction_time"],
                "target_time_start": row["target_time_start"],
                "target_time_end": row["target_time_end"],
                "country": row["country"],
                "location": row["location"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "temperature_low": row["temperature_low"],
                "temperature_high": row["temperature_high"],
                "humidity_low": row["humidity_low"],
                "humidity_high": row["humidity_high"],
                "wind_speed_low": row["wind_speed_low"],
                "wind_speed_high": row["wind_speed_high"],
                "wind_direction": row["wind_direction"],
                "forecast_description": row["forecast_description"],
                "source_api": row["source_api"],
                "created_at": row["created_at"]
            })
        
        return {
            "count": len(forecasts),
            "forecasts": forecasts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch forecasts: {str(e)}")
    finally:
        con.close()


@router.get("/compare")
def compare_ml_vs_official_forecasts(
    country: str = "singapore",
    location: Optional[str] = None,
    days_back: int = 7
):
    """
    Compare ML predictions vs official forecasts.
    
    This endpoint compares ML model predictions against official weather forecasts
    to evaluate ML model accuracy and identify areas for improvement.
    
    Args:
        country: Country to compare (default: 'singapore')
        location: Optional specific location
        days_back: Number of days to look back (default: 7)
    
    Returns:
        Comparison metrics and data for ML vs official forecasts
    """
    con = get_connection()
    cursor = con.cursor()
    
    try:
        # Get official forecasts from the past N days
        cursor.execute("""
            SELECT 
                prediction_time,
                target_time_start,
                target_time_end,
                location,
                temperature_low,
                temperature_high,
                humidity_low,
                humidity_high,
                wind_speed_low,
                wind_speed_high
            FROM forecast_data
            WHERE country = ?
                AND prediction_time >= datetime('now', '-' || ? || ' days')
            ORDER BY prediction_time DESC, target_time_start ASC
        """, (country.lower(), days_back))
        
        official_forecasts = cursor.fetchall()
        
        # TODO: Get ML predictions for the same time periods
        # This would require querying ML prediction history
        # For now, return structure showing what comparison would look like
        
        comparison_data = {
            "country": country,
            "location": location,
            "days_analyzed": days_back,
            "official_forecast_count": len(official_forecasts),
            "ml_prediction_count": 0,  # TODO: Implement ML prediction history
            "comparison_metrics": {
                "temperature": {
                    "mae": None,  # Mean Absolute Error
                    "rmse": None,  # Root Mean Square Error
                    "bias": None,  # Average difference (ML - Official)
                },
                "humidity": {
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                },
                "wind_speed": {
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                }
            },
            "official_forecasts": [
                {
                    "prediction_time": row["prediction_time"],
                    "target_time_start": row["target_time_start"],
                    "target_time_end": row["target_time_end"],
                    "location": row["location"],
                    "temperature_range": [row["temperature_low"], row["temperature_high"]],
                    "humidity_range": [row["humidity_low"], row["humidity_high"]],
                    "wind_speed_range": [row["wind_speed_low"], row["wind_speed_high"]]
                }
                for row in official_forecasts[:50]  # Limit to 50 for response size
            ],
            "note": "ML prediction comparison will be available once ML models generate prediction history"
        }
        
        return comparison_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare forecasts: {str(e)}")
    finally:
        con.close()

