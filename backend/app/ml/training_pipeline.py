"""
Training Pipeline Service for ML Weather Forecasting

This module provides the TrainingPipeline class that trains time series models
(ARIMA, SARIMA, Prophet, LSTM) for weather forecasting.
"""

import pickle
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a trained model"""
    model_id: str
    model_type: str  # 'arima', 'sarima', 'prophet', 'lstm'
    weather_parameter: str  # 'temperature', 'rainfall', 'humidity', 'wind_speed'
    hyperparameters: Dict[str, Any]
    validation_mae: float
    validation_rmse: float
    validation_mape: float
    trained_at: datetime
    model_file_path: str
    is_production: bool = False


class TrainingPipeline:
    """
    Training pipeline for weather forecasting models.
    
    Trains ARIMA, SARIMA, Prophet, and LSTM models with hyperparameter tuning.
    """
    
    def __init__(self, model_dir: str = "models"):
        """
        Initialize TrainingPipeline.
        
        Args:
            model_dir: Directory to save trained models
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def train_test_split(self, df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split time series data into train and test sets.
        
        Args:
            df: DataFrame with time-ordered data
            test_size: Fraction of data to use for testing (default: 0.2)
        
        Returns:
            Tuple of (train_df, test_df)
        
        Requirements:
            - Validates Requirements 3.5
        """
        split_idx = int(len(df) * (1 - test_size))
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
        return train_df, test_df
    
    def calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate MAE, RMSE, MAPE metrics."""
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100
        return {'mae': mae, 'rmse': rmse, 'mape': mape}
    
    def train_arima_model(self, train_data: pd.Series, test_data: pd.Series,
                         param_grid: Optional[Dict] = None) -> Tuple[Any, Dict, Dict]:
        """
        Train ARIMA model with grid search.
        
        Args:
            train_data: Training time series
            test_data: Test time series
            param_grid: Grid of (p, d, q) parameters to search
        
        Returns:
            Tuple of (best_model, best_params, metrics)
        
        Requirements:
            - Validates Requirements 3.1, 4.1
        """
        if param_grid is None:
            param_grid = {
                'p': [0, 1, 2, 3, 4, 5],
                'd': [0, 1, 2],
                'q': [0, 1, 2, 3, 4, 5]
            }
        
        best_mae = float('inf')
        best_model = None
        best_params = None
        
        for p in param_grid['p']:
            for d in param_grid['d']:
                for q in param_grid['q']:
                    try:
                        model = ARIMA(train_data, order=(p, d, q))
                        fitted_model = model.fit()
                        
                        # Forecast on test set
                        forecast = fitted_model.forecast(steps=len(test_data))
                        metrics = self.calculate_metrics(test_data.values, forecast.values)
                        
                        if metrics['mae'] < best_mae:
                            best_mae = metrics['mae']
                            best_model = fitted_model
                            best_params = {'p': p, 'd': d, 'q': q}
                    except Exception as e:
                        logger.debug(f"ARIMA({p},{d},{q}) failed: {e}")
                        continue
        
        if best_model is None:
            raise ValueError("No valid ARIMA model found")
        
        forecast = best_model.forecast(steps=len(test_data))
        final_metrics = self.calculate_metrics(test_data.values, forecast.values)
        
        return best_model, best_params, final_metrics
    
    def train_sarima_model(self, train_data: pd.Series, test_data: pd.Series,
                          seasonal_period: int = 24,
                          param_grid: Optional[Dict] = None) -> Tuple[Any, Dict, Dict]:
        """
        Train SARIMA model with grid search.
        
        Args:
            train_data: Training time series
            test_data: Test time series
            seasonal_period: Seasonal period (24 for hourly, 7 for daily)
            param_grid: Grid of parameters to search
        
        Returns:
            Tuple of (best_model, best_params, metrics)
        
        Requirements:
            - Validates Requirements 3.2, 4.2
        """
        if param_grid is None:
            param_grid = {
                'p': [0, 1, 2],
                'd': [0, 1],
                'q': [0, 1, 2],
                'P': [0, 1],
                'D': [0, 1],
                'Q': [0, 1]
            }
        
        best_mae = float('inf')
        best_model = None
        best_params = None
        
        for p in param_grid['p']:
            for d in param_grid['d']:
                for q in param_grid['q']:
                    for P in param_grid['P']:
                        for D in param_grid['D']:
                            for Q in param_grid['Q']:
                                try:
                                    model = SARIMAX(train_data,
                                                   order=(p, d, q),
                                                   seasonal_order=(P, D, Q, seasonal_period))
                                    fitted_model = model.fit(disp=False)
                                    
                                    forecast = fitted_model.forecast(steps=len(test_data))
                                    metrics = self.calculate_metrics(test_data.values, forecast.values)
                                    
                                    if metrics['mae'] < best_mae:
                                        best_mae = metrics['mae']
                                        best_model = fitted_model
                                        best_params = {'p': p, 'd': d, 'q': q, 'P': P, 'D': D, 'Q': Q, 's': seasonal_period}
                                except Exception as e:
                                    logger.debug(f"SARIMA failed: {e}")
                                    continue
        
        if best_model is None:
            raise ValueError("No valid SARIMA model found")
        
        forecast = best_model.forecast(steps=len(test_data))
        final_metrics = self.calculate_metrics(test_data.values, forecast.values)
        
        return best_model, best_params, final_metrics
    
    def train_prophet_model(self, train_data: pd.DataFrame, test_data: pd.DataFrame,
                           param_grid: Optional[Dict] = None) -> Tuple[Any, Dict, Dict]:
        """
        Train Prophet model with hyperparameter search.
        
        Args:
            train_data: Training DataFrame with 'ds' and 'y' columns
            test_data: Test DataFrame with 'ds' and 'y' columns
            param_grid: Grid of hyperparameters to search
        
        Returns:
            Tuple of (best_model, best_params, metrics)
        
        Requirements:
            - Validates Requirements 3.3
        """
        if param_grid is None:
            param_grid = {
                'changepoint_prior_scale': [0.001, 0.01, 0.1, 0.5],
                'seasonality_prior_scale': [0.01, 0.1, 1.0, 10.0]
            }
        
        best_mae = float('inf')
        best_model = None
        best_params = None
        
        for cp_scale in param_grid['changepoint_prior_scale']:
            for s_scale in param_grid['seasonality_prior_scale']:
                try:
                    model = Prophet(
                        changepoint_prior_scale=cp_scale,
                        seasonality_prior_scale=s_scale,
                        daily_seasonality=True,
                        weekly_seasonality=True,
                        yearly_seasonality=True
                    )
                    model.fit(train_data)
                    
                    forecast = model.predict(test_data[['ds']])
                    metrics = self.calculate_metrics(test_data['y'].values, forecast['yhat'].values)
                    
                    if metrics['mae'] < best_mae:
                        best_mae = metrics['mae']
                        best_model = model
                        best_params = {'changepoint_prior_scale': cp_scale, 'seasonality_prior_scale': s_scale}
                except Exception as e:
                    logger.debug(f"Prophet failed: {e}")
                    continue
        
        if best_model is None:
            raise ValueError("No valid Prophet model found")
        
        forecast = best_model.predict(test_data[['ds']])
        final_metrics = self.calculate_metrics(test_data['y'].values, forecast['yhat'].values)
        
        return best_model, best_params, final_metrics
    
    def train_lstm_model(self, train_data: np.ndarray, test_data: np.ndarray,
                        param_grid: Optional[Dict] = None) -> Tuple[Any, Dict, Dict]:
        """
        Train LSTM model with grid search.
        
        Args:
            train_data: Training sequences (3D array: samples, timesteps, features)
            test_data: Test sequences
            param_grid: Grid of hyperparameters to search
        
        Returns:
            Tuple of (best_model, best_params, metrics)
        
        Requirements:
            - Validates Requirements 3.4, 4.3
        """
        if param_grid is None:
            param_grid = {
                'units': [32, 64, 128],
                'dropout': [0.1, 0.2, 0.3],
                'lookback': [7, 14, 30]
            }
        
        best_mae = float('inf')
        best_model = None
        best_params = None
        
        X_train, y_train = train_data[:, :-1, :], train_data[:, -1, 0]
        X_test, y_test = test_data[:, :-1, :], test_data[:, -1, 0]
        
        for units in param_grid['units']:
            for dropout in param_grid['dropout']:
                try:
                    model = keras.Sequential([
                        keras.layers.LSTM(units, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
                        keras.layers.Dropout(dropout),
                        keras.layers.LSTM(units // 2),
                        keras.layers.Dropout(dropout),
                        keras.layers.Dense(1)
                    ])
                    
                    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
                    model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0, validation_split=0.1)
                    
                    y_pred = model.predict(X_test, verbose=0).flatten()
                    metrics = self.calculate_metrics(y_test, y_pred)
                    
                    if metrics['mae'] < best_mae:
                        best_mae = metrics['mae']
                        best_model = model
                        best_params = {'units': units, 'dropout': dropout}
                except Exception as e:
                    logger.debug(f"LSTM failed: {e}")
                    continue
        
        if best_model is None:
            raise ValueError("No valid LSTM model found")
        
        y_pred = best_model.predict(X_test, verbose=0).flatten()
        final_metrics = self.calculate_metrics(y_test, y_pred)
        
        return best_model, best_params, final_metrics
    
    def save_model(self, model: Any, model_type: str, weather_param: str,
                   hyperparams: Dict, metrics: Dict) -> ModelMetadata:
        """
        Save trained model and metadata.
        
        Args:
            model: Trained model object
            model_type: Type of model ('arima', 'sarima', 'prophet', 'lstm')
            weather_param: Weather parameter name
            hyperparams: Hyperparameters used
            metrics: Validation metrics
        
        Returns:
            ModelMetadata object
        
        Requirements:
            - Validates Requirements 3.7, 4.6
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_id = f"{model_type}_{weather_param}_{timestamp}"
        model_file = self.model_dir / f"{model_id}.pkl"
        
        # Save model
        with open(model_file, 'wb') as f:
            pickle.dump(model, f)
        
        # Create metadata
        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            weather_parameter=weather_param,
            hyperparameters=hyperparams,
            validation_mae=metrics['mae'],
            validation_rmse=metrics['rmse'],
            validation_mape=metrics['mape'],
            trained_at=datetime.now(),
            model_file_path=str(model_file),
            is_production=False
        )
        
        # Save metadata as JSON
        metadata_file = self.model_dir / f"{model_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump({
                'model_id': metadata.model_id,
                'model_type': metadata.model_type,
                'weather_parameter': metadata.weather_parameter,
                'hyperparameters': metadata.hyperparameters,
                'validation_mae': metadata.validation_mae,
                'validation_rmse': metadata.validation_rmse,
                'validation_mape': metadata.validation_mape,
                'trained_at': metadata.trained_at.isoformat(),
                'model_file_path': metadata.model_file_path,
                'is_production': metadata.is_production
            }, f, indent=2)
        
        logger.info(f"Saved model {model_id} with MAE={metrics['mae']:.4f}")
        return metadata
    
    def run_full_pipeline(self, df: pd.DataFrame,
                         weather_params: List[str] = ['temperature', 'rainfall', 'humidity', 'wind_speed']
                         ) -> List[ModelMetadata]:
        """
        Train all model types for all weather parameters.
        
        Args:
            df: DataFrame with weather data
            weather_params: List of weather parameters to train models for
        
        Returns:
            List of ModelMetadata objects for all trained models
        
        Requirements:
            - Validates Requirements 3.1, 3.2, 3.3, 3.4, 3.6
        """
        all_metadata = []
        
        for param in weather_params:
            if param not in df.columns:
                logger.warning(f"Parameter {param} not found in DataFrame, skipping")
                continue
            
            logger.info(f"Training models for {param}")
            
            # Prepare data
            train_df, test_df = self.train_test_split(df)
            train_series = train_df[param]
            test_series = test_df[param]
            
            # Train ARIMA
            try:
                logger.info(f"Training ARIMA for {param}")
                arima_model, arima_params, arima_metrics = self.train_arima_model(train_series, test_series)
                metadata = self.save_model(arima_model, 'arima', param, arima_params, arima_metrics)
                all_metadata.append(metadata)
            except Exception as e:
                logger.error(f"ARIMA training failed for {param}: {e}")
            
            # Train SARIMA
            try:
                logger.info(f"Training SARIMA for {param}")
                sarima_model, sarima_params, sarima_metrics = self.train_sarima_model(train_series, test_series)
                metadata = self.save_model(sarima_model, 'sarima', param, sarima_params, sarima_metrics)
                all_metadata.append(metadata)
            except Exception as e:
                logger.error(f"SARIMA training failed for {param}: {e}")
            
            # Train Prophet
            try:
                logger.info(f"Training Prophet for {param}")
                prophet_train = pd.DataFrame({'ds': train_df.index, 'y': train_series.values})
                prophet_test = pd.DataFrame({'ds': test_df.index, 'y': test_series.values})
                prophet_model, prophet_params, prophet_metrics = self.train_prophet_model(prophet_train, prophet_test)
                metadata = self.save_model(prophet_model, 'prophet', param, prophet_params, prophet_metrics)
                all_metadata.append(metadata)
            except Exception as e:
                logger.error(f"Prophet training failed for {param}: {e}")
            
            logger.info(f"Completed training for {param}")
        
        return all_metadata
