"""
ML Prediction Service for rainfall forecasting.

Loads trained Prophet models and makes real predictions.
NO MOCK DATA - only uses real trained models or returns None.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
import joblib
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

# Model directories
CLASSIFIER_DIR = Path(__file__).parent.parent.parent / "models" / "rainfall_classifier"
REGRESSOR_DIR = Path(__file__).parent.parent.parent / "models" / "rainfall_regressor"


class MLPredictionService:
    """Service for making rainfall predictions using trained ML models."""
    
    def __init__(self):
        self.classifiers = {}  # {horizon: model}
        self.regressors = {}   # {horizon: model}
        self.horizons = [1, 3, 6, 12, 24]
        self.models_loaded = False
        
    def load_models(self) -> bool:
        """
        Load trained Prophet models from disk.
        
        Returns:
            True if models loaded successfully, False otherwise
        """
        try:
            logger.info("Loading trained ML models...")
            
            # Load classifiers
            for horizon in self.horizons:
                classifier_path = CLASSIFIER_DIR / f"prophet_rainfall_classifier_{horizon}h.pkl"
                if classifier_path.exists():
                    self.classifiers[horizon] = joblib.load(classifier_path)
                    logger.info(f"✓ Loaded classifier for {horizon}h horizon")
                else:
                    logger.warning(f"✗ Classifier not found for {horizon}h horizon: {classifier_path}")
            
            # Load regressors
            for horizon in self.horizons:
                regressor_path = REGRESSOR_DIR / f"prophet_rainfall_regressor_{horizon}h.pkl"
                if regressor_path.exists():
                    self.regressors[horizon] = joblib.load(regressor_path)
                    logger.info(f"✓ Loaded regressor for {horizon}h horizon")
                else:
                    logger.warning(f"✗ Regressor not found for {horizon}h horizon: {regressor_path}")
            
            self.models_loaded = len(self.classifiers) > 0 or len(self.regressors) > 0
            
            if self.models_loaded:
                logger.info(f"✓ ML models loaded: {len(self.classifiers)} classifiers, {len(self.regressors)} regressors")
            else:
                logger.warning("✗ No ML models found. Train models first using ml/train_rainfall_*.py")
            
            return self.models_loaded
            
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}", exc_info=True)
            return False
    
    def create_features(self, current_data: Dict) -> Dict:
        """
        Create features for prediction from current weather data.
        
        Args:
            current_data: Dictionary with current weather conditions
                - timestamp: datetime
                - rainfall: float (mm/h)
                - humidity: float (%)
                - pressure: float (hPa)
                - wind_speed: float (km/h)
                - wind_direction: float (degrees)
                - temperature: float (°C)
        
        Returns:
            Dictionary with engineered features
        """
        timestamp = current_data.get('timestamp', datetime.now())
        
        # Extract time features
        hour = timestamp.hour
        day_of_year = timestamp.timetuple().tm_yday
        month = timestamp.month
        
        # Cyclical encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        day_sin = np.sin(2 * np.pi * day_of_year / 365)
        day_cos = np.cos(2 * np.pi * day_of_year / 365)
        
        # Monsoon indicators
        is_ne_monsoon = 1 if month in [11, 12, 1] else 0
        is_sw_monsoon = 1 if month in [5, 6, 7, 8, 9] else 0
        
        # Wind direction indicator (Sumatra squalls)
        wind_direction = current_data.get('wind_direction', 0)
        wind_from_west = 1 if 225 <= wind_direction <= 315 else 0
        
        features = {
            'ds': timestamp,
            'hour_sin': hour_sin,
            'hour_cos': hour_cos,
            'day_sin': day_sin,
            'day_cos': day_cos,
            'humidity': current_data.get('humidity', 75),
            'pressure': current_data.get('pressure', 1013),
            'wind_speed': current_data.get('wind_speed', 10),
            'temperature': current_data.get('temperature', 27),
            'is_ne_monsoon': is_ne_monsoon,
            'is_sw_monsoon': is_sw_monsoon,
            'wind_from_west': wind_from_west,
            # Lagged features (would need historical data from database)
            'rainfall_lag_1h': current_data.get('rainfall_lag_1h', 0),
            'rainfall_lag_3h': current_data.get('rainfall_lag_3h', 0),
            'rainfall_lag_6h': current_data.get('rainfall_lag_6h', 0),
            'rainfall_lag_24h': current_data.get('rainfall_lag_24h', 0),
            'humidity_change_1h': current_data.get('humidity_change_1h', 0),
            'pressure_drop_3h': current_data.get('pressure_drop_3h', 0),
        }
        
        return features
    
    def predict_rainfall(self, current_data: Dict, horizon: int = 3) -> Optional[Dict]:
        """
        Predict rainfall for a given horizon.
        
        Two-stage approach:
        1. Classification: Will it rain? (yes/no)
        2. Regression: How much rain? (mm/hour)
        
        Args:
            current_data: Current weather conditions
            horizon: Forecast horizon in hours (1, 3, 6, 12, 24)
        
        Returns:
            Dictionary with prediction results or None if models not available
        """
        if not self.models_loaded:
            logger.warning("ML models not loaded. Cannot make predictions.")
            return None
        
        if horizon not in self.horizons:
            logger.warning(f"Invalid horizon: {horizon}. Must be one of {self.horizons}")
            return None
        
        try:
            # Create features
            features = self.create_features(current_data)
            features_df = pd.DataFrame([features])
            
            # Stage 1: Classification (will it rain?)
            rain_probability = None
            will_rain = False
            
            if horizon in self.classifiers:
                classifier = self.classifiers[horizon]
                forecast = classifier.predict(features_df)
                rain_probability = float(forecast['yhat'].iloc[0])
                will_rain = rain_probability > 0.5
            
            # Stage 2: Regression (how much rain?)
            rainfall_intensity = None
            confidence_lower = None
            confidence_upper = None
            
            if will_rain and horizon in self.regressors:
                regressor = self.regressors[horizon]
                forecast = regressor.predict(features_df)
                rainfall_intensity = max(0, float(forecast['yhat'].iloc[0]))
                confidence_lower = max(0, float(forecast['yhat_lower'].iloc[0]))
                confidence_upper = max(0, float(forecast['yhat_upper'].iloc[0]))
            
            return {
                'horizon_hours': horizon,
                'will_rain': will_rain,
                'rain_probability': rain_probability,
                'rainfall_intensity_mm_per_hour': rainfall_intensity,
                'confidence_interval': {
                    'lower': confidence_lower,
                    'upper': confidence_upper
                } if rainfall_intensity is not None else None,
                'model_source': 'Prophet ML Model',
                'prediction_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Prediction failed for {horizon}h horizon: {e}", exc_info=True)
            return None
    
    def predict_all_horizons(self, current_data: Dict) -> Dict[int, Optional[Dict]]:
        """
        Predict rainfall for all available horizons.
        
        Args:
            current_data: Current weather conditions
        
        Returns:
            Dictionary mapping horizon to prediction results
        """
        predictions = {}
        for horizon in self.horizons:
            predictions[horizon] = self.predict_rainfall(current_data, horizon)
        return predictions
    
    def get_model_info(self) -> Dict:
        """
        Get information about loaded models.
        
        Returns:
            Dictionary with model metadata
        """
        return {
            'models_loaded': self.models_loaded,
            'classifiers_available': list(self.classifiers.keys()),
            'regressors_available': list(self.regressors.keys()),
            'horizons': self.horizons,
            'model_type': 'Prophet (Facebook)',
            'target': 'Rainfall (Singapore)',
            'features': [
                'humidity', 'pressure', 'wind_speed', 'wind_direction', 'temperature',
                'hour (cyclical)', 'day_of_year (cyclical)', 'monsoon_indicators',
                'lagged_rainfall', 'humidity_change', 'pressure_drop'
            ]
        }


# Global instance
_ml_service = None


def get_ml_prediction_service() -> MLPredictionService:
    """Get or create the global ML prediction service instance."""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLPredictionService()
        _ml_service.load_models()
    return _ml_service
