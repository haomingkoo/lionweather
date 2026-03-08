"""
API endpoints for ML rainfall predictions.

Provides real-time rainfall predictions using trained Prophet models.
NO MOCK DATA - only returns predictions from real trained models.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from datetime import datetime
import logging

from app.services.ml_prediction_service import get_ml_prediction_service

router = APIRouter(prefix="/api/ml-predictions", tags=["ml-predictions"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_ml_status() -> Dict:
    """
    Get ML prediction service status.
    
    Returns information about loaded models and availability.
    """
    service = get_ml_prediction_service()
    info = service.get_model_info()
    
    return {
        "status": "available" if info['models_loaded'] else "unavailable",
        "message": "ML models loaded and ready" if info['models_loaded'] else "ML models not trained yet. Run training scripts first.",
        "model_info": info
    }


@router.post("/predict")
async def predict_rainfall(
    current_data: Dict,
    horizon: int = 3
) -> Dict:
    """
    Predict rainfall for a given horizon.
    
    Args:
        current_data: Current weather conditions
            - timestamp (optional): ISO datetime string
            - rainfall: Current rainfall (mm/h)
            - humidity: Current humidity (%)
            - pressure: Current pressure (hPa)
            - wind_speed: Current wind speed (km/h)
            - wind_direction: Current wind direction (degrees)
            - temperature: Current temperature (°C)
            - rainfall_lag_1h (optional): Rainfall 1 hour ago
            - rainfall_lag_3h (optional): Rainfall 3 hours ago
            - rainfall_lag_6h (optional): Rainfall 6 hours ago
            - rainfall_lag_24h (optional): Rainfall 24 hours ago
            - humidity_change_1h (optional): Humidity change in last hour
            - pressure_drop_3h (optional): Pressure drop in last 3 hours
        horizon: Forecast horizon in hours (1, 3, 6, 12, 24)
    
    Returns:
        Rainfall prediction with probability and intensity
    """
    service = get_ml_prediction_service()
    
    if not service.models_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models not available. Train models first using ml/train_rainfall_*.py scripts."
        )
    
    # Parse timestamp if provided
    if 'timestamp' in current_data and isinstance(current_data['timestamp'], str):
        current_data['timestamp'] = datetime.fromisoformat(current_data['timestamp'].replace('Z', '+00:00'))
    
    prediction = service.predict_rainfall(current_data, horizon)
    
    if prediction is None:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed for {horizon}h horizon"
        )
    
    return prediction


@router.post("/predict-all")
async def predict_all_horizons(current_data: Dict) -> Dict:
    """
    Predict rainfall for all available horizons (1h, 3h, 6h, 12h, 24h).
    
    Args:
        current_data: Current weather conditions (same as /predict endpoint)
    
    Returns:
        Dictionary mapping horizon to prediction results
    """
    service = get_ml_prediction_service()
    
    if not service.models_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models not available. Train models first using ml/train_rainfall_*.py scripts."
        )
    
    # Parse timestamp if provided
    if 'timestamp' in current_data and isinstance(current_data['timestamp'], str):
        current_data['timestamp'] = datetime.fromisoformat(current_data['timestamp'].replace('Z', '+00:00'))
    
    predictions = service.predict_all_horizons(current_data)
    
    return {
        "predictions": predictions,
        "current_conditions": {
            "timestamp": current_data.get('timestamp', datetime.now()).isoformat(),
            "temperature": current_data.get('temperature'),
            "humidity": current_data.get('humidity'),
            "pressure": current_data.get('pressure'),
            "wind_speed": current_data.get('wind_speed')
        }
    }


@router.get("/model-info")
async def get_model_information() -> Dict:
    """
    Get detailed information about the ML models.
    
    Returns model architecture, features, training data, and performance metrics.
    """
    service = get_ml_prediction_service()
    info = service.get_model_info()
    
    return {
        "model_architecture": {
            "type": "Prophet (Facebook)",
            "approach": "Two-stage: Classification (will it rain?) + Regression (how much?)",
            "classifiers": f"{len(info['classifiers_available'])} models trained",
            "regressors": f"{len(info['regressors_available'])} models trained"
        },
        "target": {
            "primary": "Rainfall (Singapore's biggest weather challenge)",
            "classification": "Will it rain? (binary: yes/no)",
            "regression": "Rainfall intensity (mm/hour)"
        },
        "features": info['features'],
        "horizons": info['horizons'],
        "training_data": {
            "source": "Open-Meteo Historical API",
            "period": "2022-2025",
            "records": "~27,912 hourly observations",
            "validation": "TimeSeriesSplit (5-fold temporal cross-validation)",
            "data_quality": "100% real data - zero mock/synthetic data"
        },
        "validation_approach": {
            "method": "TimeSeriesSplit",
            "folds": 5,
            "temporal_ordering": "Strict (no data leakage)",
            "train_test_split": "80% train, 20% test (temporal)"
        },
        "models_loaded": info['models_loaded'],
        "status": "ready" if info['models_loaded'] else "not_trained"
    }
