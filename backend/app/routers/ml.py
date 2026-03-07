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
