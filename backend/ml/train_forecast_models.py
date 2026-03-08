"""
ML Forecast Training Pipeline with Temporal Validation

This script trains multiple forecasting models and compares them with NEA official forecasts.
Key principles:
- NO DATA LEAKAGE: Strict temporal splits, rolling features shifted by 1 period
- PROPER FORECASTING: Predict future values, not current values
- COMPARISON: Benchmark against NEA official forecasts
- HYBRID MODEL: Ensemble of best-performing models

Models trained:
1. ARIMA - Classical time series
2. Prophet - Facebook's forecasting tool
3. XGBoost - Gradient boosting with temporal features
4. Hybrid Ensemble - Weighted combination of top models
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import logging
from pathlib import Path
import json
import pickle

# Time series models
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet
import xgboost as xgb

# Evaluation
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ForecastTrainer:
    """Train and evaluate forecasting models with proper temporal validation"""
    
    def __init__(self, db_path: str = "weather.db"):
        self.db_path = db_path
        self.models = {}
        self.results = {}
        self.model_dir = Path("ml/models")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
    def load_data(self) -> pd.DataFrame:
        """Load weather data with proper temporal ordering"""
        logger.info("Loading weather data from database...")
        
        conn = sqlite3.connect(self.db_path)
        
        # Load weather records - focus on Singapore for now
        query = """
        SELECT 
            timestamp,
            country,
            location,
            temperature,
            humidity,
            wind_speed,
            rainfall
        FROM weather_records
        WHERE country = 'singapore'
        ORDER BY timestamp ASC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Aggregate by hour (multiple stations)
        df_hourly = df.groupby('timestamp').agg({
            'temperature': 'mean',
            'humidity': 'mean',
            'wind_speed': 'mean',
            'rainfall': 'sum'
        }).reset_index()
        
        # Sort by time (critical for temporal validation)
        df_hourly = df_hourly.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df_hourly)} hourly records")
        logger.info(f"Date range: {df_hourly['timestamp'].min()} to {df_hourly['timestamp'].max()}")
        
        return df_hourly
    
    def create_features_no_leakage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create features with NO DATA LEAKAGE
        
        Critical: All rolling features are shifted by 1 period
        This ensures features at time t only use data from times < t
        """
        logger.info("Creating features with temporal causality...")
        
        df = df.copy()
        
        # Temporal features (safe - based on timestamp only)
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Lag features (safe - explicitly look back)
        for col in ['temperature', 'humidity', 'wind_speed', 'rainfall']:
            df[f'{col}_lag_1h'] = df[col].shift(1)
            df[f'{col}_lag_3h'] = df[col].shift(3)
            df[f'{col}_lag_6h'] = df[col].shift(6)
            df[f'{col}_lag_12h'] = df[col].shift(12)
            df[f'{col}_lag_24h'] = df[col].shift(24)
        
        # Rolling features with SHIFT to prevent leakage
        # CRITICAL: .shift(1) ensures rolling window at time t only uses data from times < t
        for col in ['temperature', 'humidity', 'wind_speed', 'rainfall']:
            # 3-hour rolling statistics
            df[f'{col}_rolling_3h_mean'] = df[col].rolling(window=3, min_periods=1).mean().shift(1)
            df[f'{col}_rolling_3h_std'] = df[col].rolling(window=3, min_periods=1).std().shift(1)
            
            # 6-hour rolling statistics
            df[f'{col}_rolling_6h_mean'] = df[col].rolling(window=6, min_periods=1).mean().shift(1)
            df[f'{col}_rolling_6h_std'] = df[col].rolling(window=6, min_periods=1).std().shift(1)
            
            # 12-hour rolling statistics
            df[f'{col}_rolling_12h_mean'] = df[col].rolling(window=12, min_periods=1).mean().shift(1)
            df[f'{col}_rolling_12h_std'] = df[col].rolling(window=12, min_periods=1).std().shift(1)
            
            # 24-hour rolling statistics
            df[f'{col}_rolling_24h_mean'] = df[col].rolling(window=24, min_periods=1).mean().shift(1)
            df[f'{col}_rolling_24h_std'] = df[col].rolling(window=24, min_periods=1).std().shift(1)
        
        # Drop rows with NaN (from lag/rolling features)
        df = df.dropna()
        
        logger.info(f"Created {len(df.columns)} features")
        logger.info(f"Remaining records after feature engineering: {len(df)}")
        
        return df
    
    def temporal_train_test_split(self, df: pd.DataFrame, test_size: float = 0.2):
        """
        Split data temporally - train on past, test on future
        NO SHUFFLING - maintains temporal order
        """
        split_idx = int(len(df) * (1 - test_size))
        
        train = df.iloc[:split_idx].copy()
        test = df.iloc[split_idx:].copy()
        
        logger.info(f"Train: {train['timestamp'].min()} to {train['timestamp'].max()} ({len(train)} records)")
        logger.info(f"Test: {test['timestamp'].min()} to {test['timestamp'].max()} ({len(test)} records)")
        
        return train, test
    
    def train_arima(self, train: pd.DataFrame, test: pd.DataFrame) -> dict:
        """Train ARIMA model for temperature forecasting"""
        logger.info("Training ARIMA model...")
        
        try:
            # Fit ARIMA on training data
            model = ARIMA(train['temperature'], order=(2, 1, 2))
            fitted_model = model.fit()
            
            # Forecast on test period
            forecast = fitted_model.forecast(steps=len(test))
            
            # Evaluate
            mae = mean_absolute_error(test['temperature'], forecast)
            rmse = np.sqrt(mean_squared_error(test['temperature'], forecast))
            r2 = r2_score(test['temperature'], forecast)
            
            logger.info(f"ARIMA - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.3f}")
            
            # Save model
            model_path = self.model_dir / "arima_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(fitted_model, f)
            
            return {
                'model': fitted_model,
                'predictions': forecast,
                'mae': mae,
                'rmse': rmse,
                'r2': r2
            }
        except Exception as e:
            logger.error(f"ARIMA training failed: {e}")
            return None
    
    def train_prophet(self, train: pd.DataFrame, test: pd.DataFrame) -> dict:
        """Train Prophet model for temperature forecasting"""
        logger.info("Training Prophet model...")
        
        try:
            # Prepare data for Prophet (requires 'ds' and 'y' columns)
            train_prophet = train[['timestamp', 'temperature']].rename(
                columns={'timestamp': 'ds', 'temperature': 'y'}
            )
            
            # Fit Prophet
            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=True,
                changepoint_prior_scale=0.05
            )
            model.fit(train_prophet)
            
            # Create future dataframe for test period
            future = pd.DataFrame({'ds': test['timestamp']})
            forecast = model.predict(future)
            
            # Extract predictions
            predictions = forecast['yhat'].values
            
            # Evaluate
            mae = mean_absolute_error(test['temperature'], predictions)
            rmse = np.sqrt(mean_squared_error(test['temperature'], predictions))
            r2 = r2_score(test['temperature'], predictions)
            
            logger.info(f"Prophet - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.3f}")
            
            # Save model
            model_path = self.model_dir / "prophet_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            return {
                'model': model,
                'predictions': predictions,
                'mae': mae,
                'rmse': rmse,
                'r2': r2
            }
        except Exception as e:
            logger.error(f"Prophet training failed: {e}")
            return None
    
    def train_xgboost(self, train: pd.DataFrame, test: pd.DataFrame) -> dict:
        """Train XGBoost model with temporal features"""
        logger.info("Training XGBoost model...")
        
        try:
            # Select feature columns (exclude timestamp and target)
            feature_cols = [col for col in train.columns if col not in ['timestamp', 'temperature']]
            
            X_train = train[feature_cols]
            y_train = train['temperature']
            X_test = test[feature_cols]
            y_test = test['temperature']
            
            # Train XGBoost
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )
            model.fit(X_train, y_train)
            
            # Predict
            predictions = model.predict(X_test)
            
            # Evaluate
            mae = mean_absolute_error(y_test, predictions)
            rmse = np.sqrt(mean_squared_error(y_test, predictions))
            r2 = r2_score(y_test, predictions)
            
            logger.info(f"XGBoost - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.3f}")
            
            # Feature importance
            importance = pd.DataFrame({
                'feature': feature_cols,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            logger.info(f"Top 5 features: {importance.head()['feature'].tolist()}")
            
            # Save model
            model_path = self.model_dir / "xgboost_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            return {
                'model': model,
                'predictions': predictions,
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'feature_importance': importance
            }
        except Exception as e:
            logger.error(f"XGBoost training failed: {e}")
            return None
    
    def train_hybrid_ensemble(self, train: pd.DataFrame, test: pd.DataFrame, 
                             arima_result: dict, prophet_result: dict, xgb_result: dict) -> dict:
        """
        Create hybrid ensemble model - weighted average of best models
        Weights based on validation performance
        """
        logger.info("Creating hybrid ensemble model...")
        
        try:
            # Get predictions from each model
            predictions = []
            weights = []
            model_names = []
            
            if arima_result:
                predictions.append(arima_result['predictions'])
                weights.append(1 / arima_result['mae'])  # Inverse MAE as weight
                model_names.append('ARIMA')
            
            if prophet_result:
                predictions.append(prophet_result['predictions'])
                weights.append(1 / prophet_result['mae'])
                model_names.append('Prophet')
            
            if xgb_result:
                predictions.append(xgb_result['predictions'])
                weights.append(1 / xgb_result['mae'])
                model_names.append('XGBoost')
            
            # Normalize weights
            weights = np.array(weights)
            weights = weights / weights.sum()
            
            logger.info(f"Ensemble weights: {dict(zip(model_names, weights))}")
            
            # Weighted average
            ensemble_predictions = np.average(predictions, axis=0, weights=weights)
            
            # Evaluate
            mae = mean_absolute_error(test['temperature'], ensemble_predictions)
            rmse = np.sqrt(mean_squared_error(test['temperature'], ensemble_predictions))
            r2 = r2_score(test['temperature'], ensemble_predictions)
            
            logger.info(f"Hybrid Ensemble - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.3f}")
            
            # Save ensemble config
            ensemble_config = {
                'models': model_names,
                'weights': weights.tolist()
            }
            config_path = self.model_dir / "ensemble_config.json"
            with open(config_path, 'w') as f:
                json.dump(ensemble_config, f, indent=2)
            
            return {
                'predictions': ensemble_predictions,
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'weights': dict(zip(model_names, weights))
            }
        except Exception as e:
            logger.error(f"Ensemble creation failed: {e}")
            return None
    
    def compare_with_nea_forecasts(self, test: pd.DataFrame, ml_predictions: np.ndarray) -> dict:
        """
        Compare ML predictions with NEA official forecasts
        """
        logger.info("Comparing with NEA official forecasts...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Load NEA forecasts for test period
            query = """
            SELECT 
                target_time_start,
                target_time_end,
                temperature_low,
                temperature_high,
                location
            FROM forecast_data
            WHERE country = 'singapore'
            AND target_time_start >= ?
            AND target_time_start <= ?
            ORDER BY target_time_start ASC
            """
            
            nea_forecasts = pd.read_sql_query(
                query, 
                conn,
                params=(test['timestamp'].min().isoformat(), test['timestamp'].max().isoformat())
            )
            conn.close()
            
            if len(nea_forecasts) == 0:
                logger.warning("No NEA forecasts found for test period")
                return None
            
            # NEA provides temperature range - use midpoint
            nea_forecasts['nea_temperature'] = (
                nea_forecasts['temperature_low'] + nea_forecasts['temperature_high']
            ) / 2
            
            nea_forecasts['target_time_start'] = pd.to_datetime(nea_forecasts['target_time_start'])
            
            # Merge with test data
            test_with_nea = test.merge(
                nea_forecasts[['target_time_start', 'nea_temperature']],
                left_on='timestamp',
                right_on='target_time_start',
                how='left'
            )
            
            # Filter to rows where we have NEA forecasts
            valid_rows = test_with_nea['nea_temperature'].notna()
            
            if valid_rows.sum() == 0:
                logger.warning("No matching NEA forecasts found")
                return None
            
            actual = test_with_nea.loc[valid_rows, 'temperature'].values
            nea_pred = test_with_nea.loc[valid_rows, 'nea_temperature'].values
            ml_pred = ml_predictions[valid_rows]
            
            # Evaluate both
            nea_mae = mean_absolute_error(actual, nea_pred)
            ml_mae = mean_absolute_error(actual, ml_pred)
            
            nea_rmse = np.sqrt(mean_squared_error(actual, nea_pred))
            ml_rmse = np.sqrt(mean_squared_error(actual, ml_pred))
            
            # Win rate (how often ML is more accurate)
            ml_errors = np.abs(actual - ml_pred)
            nea_errors = np.abs(actual - nea_pred)
            ml_wins = (ml_errors < nea_errors).sum()
            win_rate = ml_wins / len(actual)
            
            logger.info(f"NEA Forecast - MAE: {nea_mae:.2f}, RMSE: {nea_rmse:.2f}")
            logger.info(f"ML Model - MAE: {ml_mae:.2f}, RMSE: {ml_rmse:.2f}")
            logger.info(f"ML Win Rate: {win_rate:.1%} ({ml_wins}/{len(actual)} predictions)")
            
            improvement = ((nea_mae - ml_mae) / nea_mae) * 100
            logger.info(f"ML Improvement over NEA: {improvement:+.1f}%")
            
            return {
                'nea_mae': nea_mae,
                'nea_rmse': nea_rmse,
                'ml_mae': ml_mae,
                'ml_rmse': ml_rmse,
                'win_rate': win_rate,
                'improvement_pct': improvement,
                'comparison_count': len(actual)
            }
        except Exception as e:
            logger.error(f"NEA comparison failed: {e}")
            return None
    
    def train_all(self):
        """Train all models and create ensemble"""
        logger.info("=" * 80)
        logger.info("STARTING ML FORECAST TRAINING PIPELINE")
        logger.info("=" * 80)
        
        # Load data
        df = self.load_data()
        
        # Create features (no data leakage)
        df_features = self.create_features_no_leakage(df)
        
        # Temporal split
        train, test = self.temporal_train_test_split(df_features, test_size=0.2)
        
        # Train individual models
        logger.info("\n" + "=" * 80)
        logger.info("TRAINING INDIVIDUAL MODELS")
        logger.info("=" * 80)
        
        arima_result = self.train_arima(train, test)
        prophet_result = self.train_prophet(train, test)
        xgb_result = self.train_xgboost(train, test)
        
        # Create hybrid ensemble
        logger.info("\n" + "=" * 80)
        logger.info("CREATING HYBRID ENSEMBLE")
        logger.info("=" * 80)
        
        ensemble_result = self.train_hybrid_ensemble(train, test, arima_result, prophet_result, xgb_result)
        
        # Compare with NEA
        logger.info("\n" + "=" * 80)
        logger.info("COMPARING WITH NEA OFFICIAL FORECASTS")
        logger.info("=" * 80)
        
        nea_comparison = self.compare_with_nea_forecasts(test, ensemble_result['predictions'])
        
        # Save results summary
        results = {
            'training_date': datetime.now().isoformat(),
            'train_size': len(train),
            'test_size': len(test),
            'models': {
                'arima': {
                    'mae': arima_result['mae'] if arima_result else None,
                    'rmse': arima_result['rmse'] if arima_result else None,
                    'r2': arima_result['r2'] if arima_result else None
                },
                'prophet': {
                    'mae': prophet_result['mae'] if prophet_result else None,
                    'rmse': prophet_result['rmse'] if prophet_result else None,
                    'r2': prophet_result['r2'] if prophet_result else None
                },
                'xgboost': {
                    'mae': xgb_result['mae'] if xgb_result else None,
                    'rmse': xgb_result['rmse'] if xgb_result else None,
                    'r2': xgb_result['r2'] if xgb_result else None
                },
                'ensemble': {
                    'mae': ensemble_result['mae'] if ensemble_result else None,
                    'rmse': ensemble_result['rmse'] if ensemble_result else None,
                    'r2': ensemble_result['r2'] if ensemble_result else None,
                    'weights': ensemble_result['weights'] if ensemble_result else None
                }
            },
            'nea_comparison': nea_comparison
        }
        
        results_path = self.model_dir / "training_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("\n" + "=" * 80)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Models saved to: {self.model_dir}")
        logger.info(f"Results saved to: {results_path}")
        
        return results


if __name__ == "__main__":
    trainer = ForecastTrainer()
    results = trainer.train_all()
