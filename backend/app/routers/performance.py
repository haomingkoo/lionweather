from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict

from sqlalchemy import text

from app.admin_auth import admin_header
from app.db.database import get_engine

router = APIRouter(prefix="/performance", tags=["performance"])

def get_db():
    return get_engine().connect()


@router.post("/record-prediction", dependencies=[Depends(admin_header)])
def record_prediction(prediction_data: dict):
    """
    Record a prediction for future benchmarking
    
    Stores:
    - ML prediction
    - Official prediction
    - Timestamp
    - Location
    
    Later we'll compare against actual weather
    """
    con = get_db()
    
    fields = [
        "location_id", "prediction_timestamp", "target_timestamp", "hours_ahead",
        "ml_temperature", "ml_condition", "ml_rain_probability", "ml_confidence",
        "official_temperature", "official_condition",
    ]
    params = {f: prediction_data.get(f) for f in fields}
    params["official_source"] = prediction_data.get("official_source", "data.gov.sg")
    prediction_id = con.execute(text("""
        INSERT INTO forecast_performance (
            location_id, prediction_timestamp, target_timestamp, hours_ahead,
            ml_temperature, ml_condition, ml_rain_probability, ml_confidence,
            official_temperature, official_condition, official_source
        ) VALUES (:location_id, :prediction_timestamp, :target_timestamp, :hours_ahead,
            :ml_temperature, :ml_condition, :ml_rain_probability, :ml_confidence,
            :official_temperature, :official_condition, :official_source)
        RETURNING id
    """), params).scalar()
    
    con.commit()
    con.close()
    
    return {"id": prediction_id, "status": "recorded"}


@router.post("/record-actual", dependencies=[Depends(admin_header)])
def record_actual_weather(actual_data: dict):
    """
    Record actual weather and calculate performance metrics
    
    Compares actual weather against all predictions made for this time
    Updates performance metrics
    """
    con = get_db()
    
    timestamp = actual_data.get("timestamp")
    temperature = actual_data.get("temperature")
    condition = actual_data.get("condition")
    rainfall = actual_data.get("rainfall", 0)
    
    # Find all predictions for this timestamp (within 30 min window)
    target_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    window_start = (target_time - timedelta(minutes=30)).isoformat()
    window_end = (target_time + timedelta(minutes=30)).isoformat()
    
    predictions = con.execute(text("""
        SELECT * FROM forecast_performance
        WHERE target_timestamp BETWEEN :window_start AND :window_end
        AND actual_temperature IS NULL
    """), {"window_start": window_start, "window_end": window_end}).mappings().all()
    
    updated_count = 0
    
    for pred in predictions:
        # Calculate errors
        ml_temp_error = abs(pred["ml_temperature"] - temperature) if pred["ml_temperature"] else None
        official_temp_error = abs(pred["official_temperature"] - temperature) if pred["official_temperature"] else None
        
        # Check condition accuracy
        ml_condition_correct = 1 if pred["ml_condition"] == condition else 0
        official_condition_correct = 1 if pred["official_condition"] == condition else 0
        
        # Determine winner
        ml_wins = 0
        if ml_temp_error is not None and official_temp_error is not None:
            if ml_temp_error < official_temp_error:
                ml_wins = 1
            elif ml_temp_error > official_temp_error:
                ml_wins = -1
        
        # Update record
        con.execute(text("""
            UPDATE forecast_performance
            SET actual_temperature = :temperature,
                actual_condition = :condition,
                actual_rainfall = :rainfall,
                actual_recorded_at = :timestamp,
                ml_temp_error = :ml_temp_error,
                official_temp_error = :official_temp_error,
                ml_condition_correct = :ml_condition_correct,
                official_condition_correct = :official_condition_correct,
                ml_wins = :ml_wins
            WHERE id = :id
        """), {
            "temperature": temperature, "condition": condition, "rainfall": rainfall,
            "timestamp": timestamp, "ml_temp_error": ml_temp_error,
            "official_temp_error": official_temp_error,
            "ml_condition_correct": ml_condition_correct,
            "official_condition_correct": official_condition_correct,
            "ml_wins": ml_wins, "id": pred["id"],
        })
        
        updated_count += 1
    
    con.commit()
    con.close()
    
    return {
        "status": "recorded",
        "predictions_evaluated": updated_count,
        "timestamp": timestamp
    }


@router.get("/stats")
def get_performance_stats():
    """
    Get overall performance statistics
    
    Returns:
    - Total predictions made
    - ML vs Official accuracy
    - Win rate
    - Average errors
    - Trend over time
    """
    con = get_db()
    
    # Get all evaluated predictions
    stats = con.execute(text("""
        SELECT 
            COUNT(*) as total,
            AVG(ml_temp_error) as ml_avg_error,
            AVG(official_temp_error) as official_avg_error,
            AVG(ml_condition_correct) as ml_condition_accuracy,
            AVG(official_condition_correct) as official_condition_accuracy,
            SUM(CASE WHEN ml_wins = 1 THEN 1 ELSE 0 END) as ml_wins,
            SUM(CASE WHEN ml_wins = -1 THEN 1 ELSE 0 END) as official_wins,
            SUM(CASE WHEN ml_wins = 0 THEN 1 ELSE 0 END) as ties
        FROM forecast_performance
        WHERE actual_temperature IS NOT NULL
    """)).mappings().first()
    
    if not stats or stats["total"] == 0:
        con.close()
        return {
            "status": "no_data",
            "message": "No predictions have been evaluated yet",
            "total_predictions": 0
        }
    
    total = stats["total"]
    ml_wins = stats["ml_wins"] or 0
    official_wins = stats["official_wins"] or 0
    ties = stats["ties"] or 0
    
    ml_win_rate = (ml_wins / total * 100) if total > 0 else 0
    
    # Get recent trend (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent_stats = con.execute(text("""
        SELECT 
            AVG(ml_temp_error) as recent_ml_error,
            AVG(official_temp_error) as recent_official_error,
            SUM(CASE WHEN ml_wins = 1 THEN 1 ELSE 0 END) as recent_ml_wins,
            COUNT(*) as recent_total
        FROM forecast_performance
        WHERE actual_temperature IS NOT NULL
        AND actual_recorded_at > :since
    """), {"since": seven_days_ago}).mappings().first()
    
    con.close()
    
    improvement = (stats["official_avg_error"] - stats["ml_avg_error"]) if stats["official_avg_error"] else 0
    improvement_pct = (improvement / stats["official_avg_error"] * 100) if stats["official_avg_error"] and stats["official_avg_error"] > 0 else 0
    
    return {
        "status": "active",
        "total_predictions": total,
        "ml_performance": {
            "avg_temperature_error": round(stats["ml_avg_error"], 2) if stats["ml_avg_error"] else None,
            "condition_accuracy": round(stats["ml_condition_accuracy"] * 100, 1) if stats["ml_condition_accuracy"] else None,
            "wins": ml_wins,
            "win_rate": round(ml_win_rate, 1),
        },
        "official_performance": {
            "avg_temperature_error": round(stats["official_avg_error"], 2) if stats["official_avg_error"] else None,
            "condition_accuracy": round(stats["official_condition_accuracy"] * 100, 1) if stats["official_condition_accuracy"] else None,
            "wins": official_wins,
        },
        "comparison": {
            "improvement_degrees": round(improvement, 2),
            "improvement_pct": round(improvement_pct, 1),
            "ties": ties,
            "verdict": _get_verdict(ml_win_rate, improvement),
        },
        "recent_trend": {
            "last_7_days": {
                "predictions": recent_stats["recent_total"] if recent_stats else 0,
                "ml_error": round(recent_stats["recent_ml_error"], 2) if recent_stats and recent_stats["recent_ml_error"] else None,
                "official_error": round(recent_stats["recent_official_error"], 2) if recent_stats and recent_stats["recent_official_error"] else None,
                "ml_wins": recent_stats["recent_ml_wins"] if recent_stats else 0,
            }
        }
    }


@router.get("/leaderboard")
def get_leaderboard():
    """
    Get leaderboard showing best performing models/timeframes
    
    Shows:
    - Best hours ahead (1hr, 3hr, 6hr, 12hr, 24hr)
    - Best conditions (sunny, rainy, etc)
    - Best locations
    """
    con = get_db()
    
    # Performance by hours ahead
    by_hours = con.execute(text("""
        SELECT 
            hours_ahead,
            COUNT(*) as predictions,
            AVG(ml_temp_error) as ml_error,
            AVG(official_temp_error) as official_error,
            SUM(CASE WHEN ml_wins = 1 THEN 1 ELSE 0 END) as ml_wins
        FROM forecast_performance
        WHERE actual_temperature IS NOT NULL
        GROUP BY hours_ahead
        ORDER BY hours_ahead
    """)).mappings().all()
    
    # Performance by condition
    by_condition = con.execute(text("""
        SELECT 
            actual_condition,
            COUNT(*) as predictions,
            AVG(ml_temp_error) as ml_error,
            AVG(ml_condition_correct) as ml_accuracy
        FROM forecast_performance
        WHERE actual_temperature IS NOT NULL
        GROUP BY actual_condition
        ORDER BY predictions DESC
    """)).mappings().all()
    
    con.close()
    
    return {
        "by_forecast_horizon": [dict(row) for row in by_hours],
        "by_weather_condition": [dict(row) for row in by_condition],
    }


@router.get("/history")
def get_prediction_history(limit: int = 100):
    """
    Get recent prediction history with outcomes
    """
    con = get_db()
    
    history = con.execute(text("""
        SELECT 
            id, location_id, prediction_timestamp, target_timestamp, hours_ahead,
            ml_temperature, ml_condition, ml_confidence,
            official_temperature, official_condition,
            actual_temperature, actual_condition,
            ml_temp_error, official_temp_error, ml_wins
        FROM forecast_performance
        WHERE actual_temperature IS NOT NULL
        ORDER BY actual_recorded_at DESC
        LIMIT :limit
    """), {"limit": limit}).mappings().all()
    
    con.close()
    
    return {
        "predictions": [dict(row) for row in history]
    }


def _get_verdict(ml_win_rate: float, improvement: float) -> str:
    """Get human-readable verdict"""
    if ml_win_rate > 60 and improvement > 0.5:
        return "🏆 ML model significantly outperforms official forecasts!"
    elif ml_win_rate > 55:
        return "✅ ML model performs better than official forecasts"
    elif ml_win_rate > 45:
        return "⚖️ ML and official forecasts perform similarly"
    else:
        return "📊 Official forecasts currently more accurate - model needs more training"
