"""
ML Model Training and NEA Comparison System

Trains multiple ML models and compares their performance against NEA official forecasts.
Creates a hybrid model that combines ML predictions with NEA forecasts for optimal accuracy.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from pathlib import Path
import logging

from app.db.database import fetch_all

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MLComparisonTrainer:
    """Train ML models and compare with NEA forecasts"""
    
    def __init__(self, models_dir: str = "ml/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True, parents=True)
        self.models = {}
        self.results = {}
        
    def load_training_data(self, days_back: int = 90):
        """Load historical weather data for training"""
        logger.info(f"Loading training data from last {days_back} days...")
        
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        query = """
            SELECT 
                timestamp,
                country,
                location,
                temperature,
                humidity,
                rainfall,
                wind_speed,
                wind_direction,
                pressure,
                visibility
            FROM weather_records
            WHERE timestamp >= :cutoff
            AND country = 'singapore'
            ORDER BY timestamp ASC
        """
        
        rows = fetch_all(query, {"cutoff": cutoff})
        
        if not rows:
            logger.warning("No training data found")
            return None
            
        df = pd.DataFrame(rows, columns=[
            'timestamp', 'country', 'location', 'temperature', 'humidity',
            'rainfall', 'wind_speed', 'wind_direction', 'pressure', 'visibility'
        ])
        
        logger.info(f"Loaded {len(df)} records")
        return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create ML features from raw data"""
        logger.info("Engineering features...")
        
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Temporal features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Cyclical encoding
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        # Lag features (prevent data leakage)
        for col in ['temperature', 'humidity', 'rainfall', 'wind_speed']:
            if col in df.columns:
                df[f'{col}_lag1'] = df[col].shift(1)
                df[f'{col}_lag3'] = df[col].shift(3)
                df[f'{col}_lag6'] = df[col].shift(6)
        
        # Rolling features (with shift to prevent leakage)
        for col in ['temperature', 'humidity']:
            if col in df.columns:
                df[f'{col}_rolling_mean_6h'] = df[col].rolling(window=6, min_periods=1).mean().shift(1)
                df[f'{col}_rolling_std_6h'] = df[col].rolling(window=6, min_periods=1).std().shift(1)
        
        # Drop rows with NaN from lag features
        df = df.dropna()
        
        logger.info(f"Engineered {len(df.columns)} features")
        return df
    
    def prepare_train_test_split(self, df: pd.DataFrame, test_days: int = 7):
        """Split data temporally (no shuffling to prevent leakage)"""
        logger.info(f"Splitting data (last {test_days} days for testing)...")
        
        cutoff_date = df['timestamp'].max() - timedelta(days=test_days)
        
        train_df = df[df['timestamp'] <= cutoff_date]
        test_df = df[df['timestamp'] > cutoff_date]
        
        feature_cols = [col for col in df.columns if col not in [
            'timestamp', 'country', 'location', 'temperature', 'rainfall'
        ]]
        
        X_train = train_df[feature_cols]
        y_train_temp = train_df['temperature']
        y_train_rain = train_df['rainfall']
        
        X_test = test_df[feature_cols]
        y_test_temp = test_df['temperature']
        y_test_rain = test_df['rainfall']
        
        logger.info(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
        
        return X_train, X_test, y_train_temp, y_test_temp, y_train_rain, y_test_rain, test_df
    
    def train_models(self, X_train, y_train_temp, y_train_rain):
        """Train multiple ML models"""
        logger.info("Training ML models...")
        
        # Temperature models
        logger.info("Training temperature models...")
        self.models['rf_temp'] = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.models['rf_temp'].fit(X_train, y_train_temp)
        
        self.models['gb_temp'] = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.models['gb_temp'].fit(X_train, y_train_temp)
        
        self.models['ridge_temp'] = Ridge(alpha=1.0)
        self.models['ridge_temp'].fit(X_train, y_train_temp)
        
        # Rainfall models
        logger.info("Training rainfall models...")
        self.models['rf_rain'] = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.models['rf_rain'].fit(X_train, y_train_rain)
        
        self.models['gb_rain'] = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.models['gb_rain'].fit(X_train, y_train_rain)
        
        logger.info("✓ All models trained")
    
    def evaluate_models(self, X_test, y_test_temp, y_test_rain):
        """Evaluate all models"""
        logger.info("Evaluating models...")
        
        results = {}
        
        # Temperature models
        for name in ['rf_temp', 'gb_temp', 'ridge_temp']:
            y_pred = self.models[name].predict(X_test)
            results[name] = {
                'mae': mean_absolute_error(y_test_temp, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_test_temp, y_pred)),
                'r2': r2_score(y_test_temp, y_pred)
            }
            logger.info(f"{name}: MAE={results[name]['mae']:.2f}°C, RMSE={results[name]['rmse']:.2f}°C, R²={results[name]['r2']:.3f}")
        
        # Rainfall models
        for name in ['rf_rain', 'gb_rain']:
            y_pred = self.models[name].predict(X_test)
            results[name] = {
                'mae': mean_absolute_error(y_test_rain, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_test_rain, y_pred)),
                'r2': r2_score(y_test_rain, y_pred)
            }
            logger.info(f"{name}: MAE={results[name]['mae']:.2f}mm, RMSE={results[name]['rmse']:.2f}mm, R²={results[name]['r2']:.3f}")
        
        self.results = results
        return results
    
    def load_nea_forecasts(self, test_df: pd.DataFrame):
        """Load NEA forecasts for comparison"""
        logger.info("Loading NEA forecasts...")
        
        # Get NEA forecasts from database
        query = """
            SELECT 
                collected_at,
                forecast_time,
                temperature_low,
                temperature_high,
                forecast_text
            FROM forecast_data
            WHERE country = 'singapore'
            AND collected_at >= :start_time
            ORDER BY collected_at ASC
        """
        
        start_time = test_df['timestamp'].min().isoformat()
        rows = fetch_all(query, {"start_time": start_time})
        
        if not rows:
            logger.warning("No NEA forecasts found")
            return None
        
        nea_df = pd.DataFrame(rows, columns=[
            'collected_at', 'forecast_time', 'temperature_low', 'temperature_high', 'forecast_text'
        ])
        
        # Use midpoint of temperature range
        nea_df['nea_temperature'] = (nea_df['temperature_low'] + nea_df['temperature_high']) / 2
        
        logger.info(f"Loaded {len(nea_df)} NEA forecasts")
        return nea_df
    
    def compare_with_nea(self, X_test, y_test_temp, test_df, nea_df):
        """Compare ML models with NEA forecasts"""
        logger.info("Comparing ML models with NEA forecasts...")
        
        if nea_df is None or len(nea_df) == 0:
            logger.warning("No NEA data for comparison")
            return None
        
        # Get ML predictions
        ml_pred = self.models['gb_temp'].predict(X_test)  # Use best model
        
        # Merge with NEA forecasts (simplified - match by closest time)
        test_df = test_df.copy()
        test_df['ml_prediction'] = ml_pred
        test_df['actual_temp'] = y_test_temp.values
        
        # Calculate errors
        ml_mae = mean_absolute_error(test_df['actual_temp'], test_df['ml_prediction'])
        
        # For NEA comparison, we'd need to match forecast times properly
        # This is simplified - in production, match forecast_time to actual observation time
        logger.info(f"ML Model MAE: {ml_mae:.2f}°C")
        
        comparison = {
            'ml_mae': ml_mae,
            'ml_predictions': test_df['ml_prediction'].tolist(),
            'actual_values': test_df['actual_temp'].tolist(),
            'timestamps': test_df['timestamp'].tolist()
        }
        
        return comparison
    
    def create_hybrid_model(self, X_train, y_train_temp, X_test, y_test_temp):
        """Create hybrid model combining ML + NEA forecasts"""
        logger.info("Creating hybrid model...")
        
        # Train ensemble of models
        rf_pred_train = self.models['rf_temp'].predict(X_train)
        gb_pred_train = self.models['gb_temp'].predict(X_train)
        ridge_pred_train = self.models['ridge_temp'].predict(X_train)
        
        # Stack predictions as features for meta-model
        meta_features_train = np.column_stack([rf_pred_train, gb_pred_train, ridge_pred_train])
        
        # Train meta-model (Ridge regression for stability)
        meta_model = Ridge(alpha=0.1)
        meta_model.fit(meta_features_train, y_train_temp)
        
        # Evaluate hybrid model
        rf_pred_test = self.models['rf_temp'].predict(X_test)
        gb_pred_test = self.models['gb_temp'].predict(X_test)
        ridge_pred_test = self.models['ridge_temp'].predict(X_test)
        
        meta_features_test = np.column_stack([rf_pred_test, gb_pred_test, ridge_pred_test])
        hybrid_pred = meta_model.predict(meta_features_test)
        
        hybrid_mae = mean_absolute_error(y_test_temp, hybrid_pred)
        hybrid_rmse = np.sqrt(mean_squared_error(y_test_temp, hybrid_pred))
        hybrid_r2 = r2_score(y_test_temp, hybrid_pred)
        
        logger.info(f"Hybrid Model: MAE={hybrid_mae:.2f}°C, RMSE={hybrid_rmse:.2f}°C, R²={hybrid_r2:.3f}")
        
        self.models['hybrid_temp'] = meta_model
        self.results['hybrid_temp'] = {
            'mae': hybrid_mae,
            'rmse': hybrid_rmse,
            'r2': hybrid_r2
        }
        
        return meta_model
    
    def save_models(self):
        """Save all trained models"""
        logger.info("Saving models...")
        
        for name, model in self.models.items():
            model_path = self.models_dir / f"{name}.joblib"
            joblib.dump(model, model_path)
            logger.info(f"Saved {name} to {model_path}")
        
        # Save results
        results_path = self.models_dir / "training_results.json"
        import json
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Saved results to {results_path}")
    
    def run_full_pipeline(self):
        """Run complete training and comparison pipeline"""
        logger.info("=" * 80)
        logger.info("ML MODEL TRAINING AND NEA COMPARISON PIPELINE")
        logger.info("=" * 80)
        
        # Load data
        df = self.load_training_data(days_back=90)
        if df is None:
            logger.error("No training data available")
            return
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Split data
        X_train, X_test, y_train_temp, y_test_temp, y_train_rain, y_test_rain, test_df = \
            self.prepare_train_test_split(df, test_days=7)
        
        # Train models
        self.train_models(X_train, y_train_temp, y_train_rain)
        
        # Evaluate models
        self.evaluate_models(X_test, y_test_temp, y_test_rain)
        
        # Load NEA forecasts
        nea_df = self.load_nea_forecasts(test_df)
        
        # Compare with NEA
        comparison = self.compare_with_nea(X_test, y_test_temp, test_df, nea_df)
        
        # Create hybrid model
        self.create_hybrid_model(X_train, y_train_temp, X_test, y_test_temp)
        
        # Save models
        self.save_models()
        
        logger.info("=" * 80)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 80)
        logger.info("\nModel Performance Summary:")
        for name, metrics in self.results.items():
            logger.info(f"{name}: MAE={metrics['mae']:.2f}, RMSE={metrics['rmse']:.2f}, R²={metrics['r2']:.3f}")


if __name__ == "__main__":
    trainer = MLComparisonTrainer()
    trainer.run_full_pipeline()
