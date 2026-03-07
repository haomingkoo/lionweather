"""
Prediction Engine Service for ML Weather Forecasting

Generates weather forecasts using trained models.
"""

import pickle
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Prediction engine for weather forecasting.
    
    Loads trained models and generates 24-hour and 7-day forecasts.
    """
    
    def __init__(self, model_dir: str = "models"):
        """
        Initialize PredictionEngine.
        
        Args:
            model_dir: Directory containing trained models
        """
        self.model_dir = Path(model_dir)
        self.loaded_models = {}
    
    def load_production_model(self, weather_param: str, model_type: Optional[str] = None) -> Any:
        """
        Load production model for a weather parameter.
        
        Args:
            weather_param: Weather parameter name
            model_type: Specific model type to load (optional)
        
        Returns:
            Loaded model object
        
        Requirements:
            - Validates Requirements 5.3
        """
        cache_key = f"{weather_param}_{model_type}" if model_type else weather_param
        
        if cache_key in self.loaded_models:
            return self.loaded_models[cache_key]
        
        # Find production model metadata
        metadata_files = list(self.model_dir.glob(f"*_{weather_param}_*_metadata.json"))
        
        best_model_file = None
        best_mae = float('inf')
        
        for metadata_file in metadata_files:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            if metadata.get('is_production', False):
                if model_type is None or metadata['model_type'] == model_type:
                    if metadata['validation_mae'] < best_mae:
                        best_mae = metadata['validation_mae']
                        best_model_file = metadata['model_file_path']
        
        if best_model_file is None:
            # Fallback: use best model by MAE
            for metadata_file in metadata_files:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                if model_type is None or metadata['model_type'] == model_type:
                    if metadata['validation_mae'] < best_mae:
                        best_mae = metadata['validation_mae']
                        best_model_file = metadata['model_file_path']
        
        if best_model_file is None:
            raise ValueError(f"No model found for {weather_param}")
        
        # Load model
        with open(best_model_file, 'rb') as f:
            model = pickle.load(f)
        
        self.loaded_models[cache_key] = model
        logger.info(f"Loaded model for {weather_param} from {best_model_file}")
        
        return model
    
    def predict_24_hours(self, weather_param: str, current_data: pd.Series) -> pd.DataFrame:
        """
        Generate 24-hour hourly forecast.
        
        Args:
            weather_param: Weather parameter to forecast
            current_data: Recent historical data
        
        Returns:
            DataFrame with hourly predictions for next 24 hours
        
        Requirements:
            - Validates Requirements 5.1
        """
        model = self.load_production_model(weather_param)
        
        # Generate forecast
        forecast = model.forecast(steps=24)
        
        # Create timestamps
        last_timestamp = current_data.index[-1]
        timestamps = [last_timestamp + timedelta(hours=i+1) for i in range(24)]
        
        # Create DataFrame
        result = pd.DataFrame({
            'timestamp': timestamps,
            'predicted_value': forecast.values if hasattr(forecast, 'values') else forecast,
            'parameter': weather_param
        })
        
        # Add confidence intervals (placeholder - will be implemented properly)
        result['confidence_lower'] = result['predicted_value'] * 0.9
        result['confidence_upper'] = result['predicted_value'] * 1.1
        
        return result
    
    def predict_7_days(self, weather_param: str, current_data: pd.Series) -> pd.DataFrame:
        """
        Generate 7-day daily forecast.
        
        Args:
            weather_param: Weather parameter to forecast
            current_data: Recent historical data
        
        Returns:
            DataFrame with daily predictions for next 7 days
        
        Requirements:
            - Validates Requirements 5.2
        """
        # Generate hourly forecast for 7 days (168 hours)
        model = self.load_production_model(weather_param)
        forecast = model.forecast(steps=168)
        
        # Aggregate to daily averages
        forecast_values = forecast.values if hasattr(forecast, 'values') else forecast
        daily_values = []
        
        for day in range(7):
            start_idx = day * 24
            end_idx = start_idx + 24
            daily_avg = np.mean(forecast_values[start_idx:end_idx])
            daily_values.append(daily_avg)
        
        # Create timestamps
        last_timestamp = current_data.index[-1]
        timestamps = [last_timestamp + timedelta(days=i+1) for i in range(7)]
        
        # Create DataFrame
        result = pd.DataFrame({
            'timestamp': timestamps,
            'predicted_value': daily_values,
            'parameter': weather_param
        })
        
        # Add confidence intervals
        result['confidence_lower'] = result['predicted_value'] * 0.85
        result['confidence_upper'] = result['predicted_value'] * 1.15
        
        return result
    
    def calculate_confidence_intervals(self, predictions: np.ndarray,
                                      model_type: str,
                                      confidence_level: float = 0.95) -> tuple:
        """
        Calculate confidence intervals for predictions.
        
        Args:
            predictions: Array of predictions
            model_type: Type of model used
            confidence_level: Confidence level (default: 0.95)
        
        Returns:
            Tuple of (lower_bounds, upper_bounds)
        
        Requirements:
            - Validates Requirements 5.8, 14.1, 14.2, 14.3, 14.4
        """
        # Simplified implementation - use ±10% for now
        margin = predictions * 0.1
        lower = predictions - margin
        upper = predictions + margin
        
        return lower, upper
    
    def ensemble_predict(self, weather_param: str, current_data: pd.Series,
                        steps: int = 24) -> np.ndarray:
        """
        Generate ensemble predictions from multiple models.
        
        Args:
            weather_param: Weather parameter to forecast
            current_data: Recent historical data
            steps: Number of steps to forecast
        
        Returns:
            Array of ensemble predictions
        
        Requirements:
            - Validates Requirements 5.1, 5.2
        """
        model_types = ['arima', 'sarima', 'prophet']
        predictions = []
        weights = []
        
        for model_type in model_types:
            try:
                model = self.load_production_model(weather_param, model_type)
                forecast = model.forecast(steps=steps)
                forecast_values = forecast.values if hasattr(forecast, 'values') else forecast
                predictions.append(forecast_values)
                weights.append(1.0)  # Equal weights for now
            except Exception as e:
                logger.warning(f"Failed to load {model_type} for {weather_param}: {e}")
        
        if not predictions:
            raise ValueError(f"No models available for {weather_param}")
        
        # Weighted average
        weights = np.array(weights) / sum(weights)
        ensemble = np.average(predictions, axis=0, weights=weights)
        
        return ensemble
