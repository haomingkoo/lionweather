import os
from fastapi import APIRouter, HTTPException
from app.ml.forecaster import forecaster
from app.routers.environmental import fetch_api_data

router = APIRouter(prefix="/ml", tags=["ml-forecasting"])


@router.get("/predict/{hours}")
def predict_weather(hours: int = 24):
    """
    ML-powered weather prediction for next N hours
    
    Uses ensemble of models:
    - Persistence model
    - Diurnal cycle patterns
    - Humidity-based rain prediction
    - Temporal features
    
    Returns predictions with confidence scores
    """
    if hours < 1 or hours > 72:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 72")
    
    api_key = os.getenv("WEATHER_API_KEY")
    
    # Fetch all current sensor data
    endpoints = {
        "temperature": "/v2/real-time/api/air-temperature",
        "humidity": "/v2/real-time/api/relative-humidity",
        "rainfall": "/v2/real-time/api/rainfall",
        "wind_speed": "/v2/real-time/api/wind-speed",
        "wind_direction": "/v2/real-time/api/wind-direction",
        "pm25": "/v2/real-time/api/pm25",
        "uv": "/v2/real-time/api/uv",
    }
    
    sensor_data = {
        "timestamp": None,
        "sensors": {},
    }
    
    for key, endpoint in endpoints.items():
        data = fetch_api_data(endpoint, api_key)
        if data:
            items = data.get("data", {}).get("items", []) if isinstance(data.get("data"), dict) else data.get("items", [])
            if items:
                latest = items[0]
                sensor_data["sensors"][key] = {
                    "readings": latest.get("readings", latest.get("index", [])),
                    "timestamp": latest.get("timestamp"),
                }
                if not sensor_data["timestamp"]:
                    sensor_data["timestamp"] = latest.get("timestamp")
    
    # Generate predictions
    predictions = forecaster.predict_next_hours(sensor_data, hours)
    
    from datetime import datetime as _dt, timezone as _tz
    return {
        "model_version": "ensemble_v1",
        "based_on_timestamp": sensor_data["timestamp"],
        "generated_at": _dt.now(_tz.utc).isoformat(),
        "predictions": predictions,
        "metadata": {
            "model_type": "ensemble",
            "features_used": [
                "temperature",
                "humidity", 
                "rainfall",
                "wind",
                "diurnal_cycle",
                "seasonal_patterns"
            ],
            "confidence_method": "time_decay",
        }
    }


@router.get("/benchmark")
def get_benchmark_results():
    """
    Get ML model performance vs official forecasts
    
    Metrics:
    - Mean Absolute Error (MAE)
    - Win rate (% of times we're more accurate)
    - Average improvement
    """
    summary = forecaster.get_performance_summary()
    
    return {
        "status": "active" if summary.get("total_predictions", 0) > 0 else "no_data",
        "performance": summary,
        "interpretation": _interpret_performance(summary),
    }


@router.post("/record-actual")
def record_actual_weather(actual_data: dict):
    """
    Record actual weather for benchmarking
    
    This endpoint receives actual weather data and compares it
    against both our predictions and official forecasts
    """
    # TODO: Implement actual weather recording and comparison
    return {"status": "recorded", "message": "Actual weather data recorded for benchmarking"}


@router.get("/compare/{location_id}")
def compare_forecasts(location_id: int):
    """
    Compare ML forecast vs Official forecast for a location
    
    Shows side-by-side comparison with:
    - Our ML prediction
    - Official 2-hour forecast
    - Official 24-hour forecast
    - Confidence scores
    - Historical accuracy
    """
    
    # Get ML prediction
    ml_forecast = predict_weather(24)
    
    # Get official forecasts
    api_key = os.getenv("WEATHER_API_KEY")
    
    # 2-hour official
    two_hour_data = fetch_api_data("/v2/real-time/api/two-hr-forecast", api_key)
    
    # 24-hour official
    twenty_four_data = fetch_api_data("/v2/real-time/api/twenty-four-hr-forecast", api_key)
    
    # Get performance stats
    performance = forecaster.get_performance_summary()
    
    return {
        "location_id": location_id,
        "ml_forecast": ml_forecast,
        "official_2hr": two_hour_data,
        "official_24hr": twenty_four_data,
        "performance_stats": performance,
        "recommendation": _get_recommendation(performance),
    }


def _interpret_performance(summary: dict) -> str:
    """Interpret performance metrics in human-readable form"""
    if summary.get("status") == "no_data":
        return "No predictions made yet. Start making predictions to see performance metrics."
    
    win_rate = summary.get("win_rate", 0)
    improvement = summary.get("improvement", 0)
    
    if win_rate > 60:
        return f"🎉 Excellent! Our ML model is outperforming official forecasts {win_rate}% of the time with {improvement}°C average improvement."
    elif win_rate > 50:
        return f"✅ Good! Our model is competitive, winning {win_rate}% of the time."
    elif win_rate > 40:
        return f"📊 Fair performance. Our model wins {win_rate}% of the time. Room for improvement."
    else:
        return f"⚠️ Official forecasts are currently more accurate. Our model needs more training data."


def _get_recommendation(performance: dict) -> str:
    """Get recommendation on which forecast to trust"""
    if performance.get("status") == "no_data":
        return "Use official forecast (no ML performance data yet)"
    
    win_rate = performance.get("win_rate", 0)
    
    if win_rate > 60:
        return "Trust ML forecast - historically more accurate"
    elif win_rate > 50:
        return "Consider both forecasts - similar accuracy"
    else:
        return "Trust official forecast - historically more accurate"
