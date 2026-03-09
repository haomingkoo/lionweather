"""
ML Forecasting API endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Header, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import os

from ..ml.prediction_engine import PredictionEngine
from ..ml.evaluation_service import EvaluationService
from ..services.data_store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ml"])

# Initialize services
prediction_engine = PredictionEngine()
evaluation_service = EvaluationService()
data_store = DataStore()


@router.get("/predictions/24h")
async def get_24h_predictions(
    country: str = Query(..., description="Country name"),
    location: Optional[str] = Query(None, description="Location name"),
    parameter: str = Query("temperature", description="Weather parameter")
):
    """
    Get 24-hour hourly forecast.
    
    Requirements: 8.1, 8.2, 8.3
    """
    try:
        # Get recent historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        records = data_store.get_records_by_location(
            country=country,
            location=location,
            start_date=start_date,
            end_date=end_date
        )
        
        if not records:
            raise HTTPException(status_code=404, detail="No historical data found for this location")
        
        # Convert to series
        import pandas as pd
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            parameter: getattr(r, parameter)
        } for r in records])
        df.set_index('timestamp', inplace=True)
        
        # Generate forecast
        forecast_df = prediction_engine.predict_24_hours(parameter, df[parameter])
        
        # Format response
        response = {
            "country": country,
            "location": location or "All",
            "parameter": parameter,
            "forecast_type": "24h",
            "generated_at": datetime.now().isoformat(),
            "forecasts": [
                {
                    "timestamp": row['timestamp'].isoformat(),
                    "predicted_value": float(row['predicted_value']),
                    "confidence_lower": float(row['confidence_lower']),
                    "confidence_upper": float(row['confidence_upper'])
                }
                for _, row in forecast_df.iterrows()
            ]
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating 24h forecast: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate forecast: {str(e)}")


@router.get("/predictions/7d")
async def get_7d_predictions(
    country: str = Query(..., description="Country name"),
    location: Optional[str] = Query(None, description="Location name"),
    parameter: str = Query("temperature", description="Weather parameter")
):
    """
    Get 7-day daily forecast.
    
    Requirements: 8.1, 8.2, 8.3
    """
    try:
        # Get recent historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        records = data_store.get_records_by_location(
            country=country,
            location=location,
            start_date=start_date,
            end_date=end_date
        )
        
        if not records:
            raise HTTPException(status_code=404, detail="No historical data found for this location")
        
        # Convert to series
        import pandas as pd
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            parameter: getattr(r, parameter)
        } for r in records])
        df.set_index('timestamp', inplace=True)
        
        # Generate forecast
        forecast_df = prediction_engine.predict_7_days(parameter, df[parameter])
        
        # Format response
        response = {
            "country": country,
            "location": location or "All",
            "parameter": parameter,
            "forecast_type": "7d",
            "generated_at": datetime.now().isoformat(),
            "forecasts": [
                {
                    "timestamp": row['timestamp'].isoformat(),
                    "predicted_value": float(row['predicted_value']),
                    "confidence_lower": float(row['confidence_lower']),
                    "confidence_upper": float(row['confidence_upper'])
                }
                for _, row in forecast_df.iterrows()
            ]
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating 7d forecast: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate forecast: {str(e)}")


@router.get("/predictions/current")
async def get_current_weather(
    country: str = Query(..., description="Country name"),
    location: Optional[str] = Query(None, description="Location name")
):
    """
    Get current weather from latest record.
    
    Requirements: 8.1, 8.2, 8.3
    """
    try:
        record = data_store.get_latest_record(country=country, location=location)
        
        if not record:
            raise HTTPException(status_code=404, detail="No current weather data found for this location")
        
        return {
            "country": record.country,
            "location": record.location,
            "timestamp": record.timestamp.isoformat(),
            "current": {
                "temperature": record.temperature,
                "rainfall": record.rainfall,
                "humidity": record.humidity,
                "wind_speed": record.wind_speed,
                "wind_direction": record.wind_direction,
                "pressure": record.pressure
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current weather: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get current weather: {str(e)}")


@router.get("/metrics/accuracy")
async def get_accuracy_metrics(
    parameter: str = Query("temperature", description="Weather parameter"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)")
):
    """
    Get accuracy metrics for models.
    
    Requirements: 9.1, 9.2
    """
    try:
        rankings = evaluation_service.rank_models(parameter)
        
        return {
            "parameter": parameter,
            "rankings": rankings
        }
        
    except Exception as e:
        logger.error(f"Error getting accuracy metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/comparison")
async def get_model_comparison(
    parameter: str = Query("temperature", description="Weather parameter"),
    window_days: int = Query(30, description="Rolling window in days")
):
    """
    Get model comparison report.
    
    Requirements: 9.3, 9.4
    """
    try:
        comparison = evaluation_service.get_model_comparison(parameter, window_days)
        return comparison
        
    except Exception as e:
        logger.error(f"Error getting model comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/trigger")
async def trigger_training():
    """
    Manually trigger model training.
    
    Requirements: 11.1
    """
    try:
        # This would trigger the training pipeline
        return {"status": "Training triggered", "message": "Training job queued"}
        
    except Exception as e:
        logger.error(f"Error triggering training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/status")
async def get_training_status():
    """
    Get training status.
    
    Requirements: 11.1
    """
    return {"status": "idle", "last_training": None}


@router.get("/models/list")
async def list_models():
    """
    List all trained models.

    Requirements: 11.1
    """
    try:
        from pathlib import Path
        import json

        model_dir = Path("models")
        metadata_files = list(model_dir.glob("*_metadata.json"))

        models = []
        for metadata_file in metadata_files:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                models.append(metadata)

        return {"models": models}

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rain-forecast")
async def get_rain_forecast():
    """
    Live rain category forecast for Singapore using pre-trained LightGBM classifiers.

    Aggregates recent weather_records to hourly resolution, computes lag features,
    and runs the 1h / 3h / 6h / 12h classifiers.
    Returns predictions even with as little as 1-2 hours of live data
    (missing lags are filled with the earliest available value).
    """
    import pandas as pd
    import numpy as np
    import joblib
    from pathlib import Path
    from datetime import datetime, timedelta
    from sqlalchemy import text
    from app.db.database import get_engine

    HORIZONS = [1, 3, 6, 12]
    MODEL_DIR = Path("models")
    CATEGORIES = {0: "No Rain", 1: "Light Rain", 2: "Heavy Rain", 3: "Thundery Showers"}

    # ── 1. Load records ────────────────────────────────────────────────────────
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT timestamp, temperature, rainfall, humidity, wind_speed
            FROM weather_records
            WHERE country = 'singapore'
              AND timestamp >= :cutoff
            ORDER BY timestamp ASC
        """), {"cutoff": cutoff}).fetchall()

    if not rows:
        raise HTTPException(status_code=503, detail="No Singapore weather data collected yet. Check back in a few hours.")

    # ── 2. Build hourly series (mean across stations) ──────────────────────────
    df = pd.DataFrame([{
        "timestamp": pd.to_datetime(row[0]),
        "rainfall": row[2] or 0.0,
        "temperature": row[1] or 0.0,
        "humidity": row[3] or 0.0,
        "wind_speed": row[4] or 0.0,
    } for row in rows])

    df = df.set_index("timestamp").resample("1h").mean().dropna(how="all")
    df = df.ffill().bfill()   # fill any gap hours

    n_hours = len(df)
    if n_hours < 1:
        raise HTTPException(status_code=503, detail="Not enough data yet. Check back soon.")

    # ── 3. Compute features for the LATEST row ─────────────────────────────────
    def lag(col, h):
        idx = -(1 + h)
        if abs(idx) <= n_hours:
            return float(df[col].iloc[idx])
        return float(df[col].iloc[0])   # repeat earliest if not enough history

    def roll_mean(col, h):
        return float(df[col].iloc[max(0, n_hours - h):].mean())

    def roll_std(col, h):
        s = df[col].iloc[max(0, n_hours - h):]
        return float(s.std()) if len(s) > 1 else 0.0

    def roll_max(col, h):
        return float(df[col].iloc[max(0, n_hours - h):].max())

    def roll_sum(col, h):
        return float(df[col].iloc[max(0, n_hours - h):].sum())

    now = df.index[-1]
    hour = now.hour
    dow = now.dayofweek
    month = now.month
    doy = now.dayofyear

    # Singapore monsoon seasons
    is_inter_monsoon = int(month in [4, 5, 10, 11])
    is_afternoon_peak = int(13 <= hour <= 17)
    is_morning_peak = int(7 <= hour <= 9)

    # Dry spell / rain streak
    recent_rain = [float(df["rainfall"].iloc[-(i+1)]) for i in range(min(n_hours, 24))]
    dry_spell = 0
    for r in recent_rain:
        if r < 0.1:
            dry_spell += 1
        else:
            break
    rain_streak = 0
    for r in recent_rain:
        if r >= 0.1:
            rain_streak += 1
        else:
            break

    current_hum = float(df["humidity"].iloc[-1])
    current_temp = float(df["temperature"].iloc[-1])
    wind_1h = lag("wind_speed", 0)
    wind_3h_ago = lag("wind_speed", 3)
    wind_accel = wind_1h - wind_3h_ago

    feat = {
        # lag features
        **{f"rain_lag_{h}h": lag("rainfall", h) for h in [1,2,3,4,5,6,12,18,24]},
        **{f"temp_lag_{h}h": lag("temperature", h) for h in [1,2,3,4,5,6,12,18,24]},
        **{f"hum_lag_{h}h": lag("humidity", h) for h in [1,2,3,4,5,6,12,18,24]},
        **{f"wind_lag_{h}h": lag("wind_speed", h) for h in [1,2,3,4,5,6,12,18,24]},
        # rolling
        "rain_roll_3h": roll_mean("rainfall", 3),
        "rain_roll_6h": roll_mean("rainfall", 6),
        "rain_roll_std_6h": roll_std("rainfall", 6),
        "rain_roll_max_3h": roll_max("rainfall", 3),
        "rain_sum_6h": roll_sum("rainfall", 6),
        "temp_roll_3h": roll_mean("temperature", 3),
        "temp_roll_6h": roll_mean("temperature", 6),
        # time
        "hour_of_day": hour,
        "day_of_week": dow,
        "month": month,
        "is_weekend": int(dow >= 5),
        "sin_hour": np.sin(2 * np.pi * hour / 24),
        "cos_hour": np.cos(2 * np.pi * hour / 24),
        "sin_month": np.sin(2 * np.pi * month / 12),
        "cos_month": np.cos(2 * np.pi * month / 12),
        "day_of_year": doy,
        "sin_day_of_year": np.sin(2 * np.pi * doy / 365),
        "cos_day_of_year": np.cos(2 * np.pi * doy / 365),
        # derived
        "rained_last1h": int(lag("rainfall", 1) >= 0.1),
        "rained_last3h": int(any(lag("rainfall", i) >= 0.1 for i in range(1, 4))),
        "dry_spell_hours": dry_spell,
        "rain_streak_hours": rain_streak,
        "hum_deficit": max(0.0, 80.0 - current_hum),
        "hum_temp_product": current_hum * current_temp,
        "wind_accel_3h": wind_accel,
        "is_inter_monsoon": is_inter_monsoon,
        "is_afternoon_peak": is_afternoon_peak,
        "is_morning_peak": is_morning_peak,
    }

    # ── 4. Run classifiers ─────────────────────────────────────────────────────
    predictions = []
    model_performance = []

    # Try to load detailed performance from full_analysis.json
    full_analysis_perf = {}
    try:
        import json
        fa_path = MODEL_DIR / "full_analysis.json"
        if fa_path.exists():
            with open(fa_path) as _f:
                _fa = json.load(_f)
            for _mr in _fa.get("model_results", []):
                _h = _mr.get("horizon_h")
                _bc = _mr.get("binary_classification", {})
                full_analysis_perf[_h] = {
                    "binary_accuracy": _bc.get("accuracy"),
                    "rain_precision": _bc.get("rain_precision"),
                    "rain_recall": _bc.get("rain_recall"),
                    "rain_f1": _bc.get("rain_f1"),
                    "no_rain_recall": _bc.get("no_rain_recall"),
                }
    except Exception:
        pass

    for h in HORIZONS:
        model_path = MODEL_DIR / f"rainfall_cls_{h}h.joblib"
        if not model_path.exists():
            continue
        bundle = joblib.load(model_path)
        clf = bundle["model"]
        feature_cols = bundle["feature_cols"]
        X = pd.DataFrame([[feat.get(f, 0.0) for f in feature_cols]], columns=feature_cols)
        proba = clf.predict_proba(X)[0]
        pred_class = int(np.argmax(proba))
        target_time = (now + pd.Timedelta(hours=h)).isoformat()
        predictions.append({
            "horizon_h": h,
            "target_time": target_time,
            "predicted_class": pred_class,
            "predicted_label": CATEGORIES[pred_class],
            "probabilities": {CATEGORIES[i]: round(float(p), 3) for i, p in enumerate(proba)},
            "confidence": round(float(proba[pred_class]), 3),
        })

        perf_entry = {
            "horizon_h": h,
            "test_accuracy": round(bundle.get("test_accuracy", 0), 4),
            "trained_at": bundle.get("trained_at", ""),
        }
        if h in full_analysis_perf:
            perf_entry.update(full_analysis_perf[h])
        model_performance.append(perf_entry)

    # ── 5. Current conditions summary ──────────────────────────────────────────
    current = {
        "temperature": round(float(df["temperature"].iloc[-1]), 1),
        "rainfall": round(float(df["rainfall"].iloc[-1]), 2),
        "humidity": round(float(df["humidity"].iloc[-1]), 1),
        "wind_speed": round(float(df["wind_speed"].iloc[-1]), 1),
        "timestamp": now.isoformat(),
        "hours_of_data": n_hours,
    }

    return {
        "current": current,
        "predictions": predictions,
        "model_performance": model_performance,
        "data_note": "Live predictions from LightGBM classifiers trained on NEA 2016-2024 data." if n_hours >= 24
                     else f"Predictions based on {n_hours}h of live data (lags padded). Accuracy improves after 24h.",
    }
