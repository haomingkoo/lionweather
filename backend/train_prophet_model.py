#!/usr/bin/env python3
"""
Train Prophet baseline ML model for weather forecasting.

This script implements a research-based approach with:
- ZERO data leakage (strict temporal ordering)
- TimeSeriesSplit for cross-validation
- Multiple forecast horizons (1h, 3h, 6h, 12h, 24h)
- Proper feature engineering (cyclical encoding)
- Real data only (no mock/synthetic data)

Based on ML_FORECASTING_STRATEGY.md
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import json

import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Forecast horizons (in hours)
HORIZONS = [1, 3, 6, 12, 24]

# Model directory
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Metrics directory
METRICS_DIR = Path(__file__).parent / "metrics"
METRICS_DIR.mkdir(exist_ok=True)


def validate_no_mock_data(df: pd.DataFrame) -> bool:
    """
    Validate that training data contains NO mock/synthetic data.
    
    CRITICAL: This function enforces ZERO tolerance for mock data.
    """
    logger.info("🔍 Validating training data for mock/synthetic data...")
    
    # Check source API
    if 'source_api' in df.columns:
        mock_sources = df[df['source_api'].str.contains('mock|fake|test', case=False, na=False)]
        if len(mock_sources) > 0:
            logger.error(f"❌ Found {len(mock_sources)} records with mock source API")
            return False
    
    # Check for suspicious repeated values (>100 identical consecutive values)
    for col in ['temperature', 'humidity', 'wind_speed']:
        if col in df.columns:
            # Check for runs of identical values
            runs = (df[col] != df[col].shift()).cumsum()
            run_lengths = runs.value_counts()
            if run_lengths.max() > 100:
                logger.error(f"❌ Found suspicious repeated values in {col}: {run_lengths.max()} consecutive identical values")
                return False
    
    # Check for unrealistic temperature patterns (constant for >24 hours)
    if 'temperature' in df.columns:
        temp_std_24h = df['temperature'].rolling(window=24).std()
        if (temp_std_24h < 0.1).sum() > 0:
            logger.error("❌ Found unrealistic temperature patterns (constant for >24 hours)")
            return False
    
    logger.info("✅ No mock/synthetic data detected")
    return True


def load_historical_data() -> pd.DataFrame:
    """
    Load historical weather data from database.
    
    Returns:
        DataFrame with columns: timestamp, temperature, humidity, wind_speed, rainfall, etc.
    """
    logger.info("📊 Loading historical weather data from database...")
    
    db = next(get_db())
    
    # Query all weather records, ordered by timestamp (CRITICAL for temporal integrity)
    query = """
        SELECT 
            timestamp,
            temperature,
            humidity,
            wind_speed,
            wind_direction,
            rainfall,
            pressure,
            source_api
        FROM weather_records
        WHERE country = 'Singapore'
        ORDER BY timestamp ASC
    """
    
    result = db.execute(query)
    rows = result.fetchall()
    
    if not rows:
        raise ValueError("No historical data found in database. Run seed_historical_data.py first.")
    
    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=['timestamp', 'temperature', 'humidity', 'wind_speed', 
                                      'wind_direction', 'rainfall', 'pressure', 'source_api'])
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp (CRITICAL: ensure temporal ordering)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    logger.info(f"✓ Loaded {len(df)} records from {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Validate no mock data
    if not validate_no_mock_data(df):
        raise ValueError("CRITICAL: Mock/synthetic data detected in training dataset. Aborting.")
    
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create features for Prophet model.
    
    Features:
    - Hour of day (cyclical encoding)
    - Day of year (cyclical encoding)
    - Humidity
    - Wind speed
    - Rainfall
    
    CRITICAL: Features must only use data available at prediction time.
    NO future data leakage.
    """
    logger.info("🔧 Creating features...")
    
    df = df.copy()
    
    # Extract time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_year'] = df['timestamp'].dt.dayofyear
    
    # Cyclical encoding for hour (0-23)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Cyclical encoding for day of year (1-365)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    
    logger.info(f"✓ Created features: hour_sin, hour_cos, day_sin, day_cos, humidity, wind_speed, rainfall")
    
    return df


def prepare_prophet_data(df: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    """
    Prepare data for Prophet model.
    
    Prophet requires:
    - 'ds': datetime column
    - 'y': target column (temperature at horizon_hours ahead)
    - Additional regressors as separate columns
    
    Args:
        df: DataFrame with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        DataFrame ready for Prophet training
    """
    logger.info(f"📋 Preparing data for {horizon_hours}h horizon...")
    
    df = df.copy()
    
    # Create target: temperature at horizon_hours ahead
    # CRITICAL: This ensures we're predicting FUTURE temperature, not current
    df['y'] = df['temperature'].shift(-horizon_hours)
    
    # Rename timestamp to 'ds' (Prophet requirement)
    df['ds'] = df['timestamp']
    
    # Drop rows with NaN target (last horizon_hours rows)
    df = df.dropna(subset=['y'])
    
    logger.info(f"✓ Prepared {len(df)} samples for {horizon_hours}h horizon")
    
    return df


def train_prophet_model(train_df: pd.DataFrame, horizon_hours: int) -> Prophet:
    """
    Train Prophet model for a specific forecast horizon.
    
    Args:
        train_df: Training data (must have 'ds', 'y', and regressor columns)
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Trained Prophet model
    """
    logger.info(f"🤖 Training Prophet model for {horizon_hours}h horizon...")
    
    # Initialize Prophet with daily and weekly seasonality
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,  # Flexibility for trend changes
        seasonality_prior_scale=10.0,  # Strength of seasonality
    )
    
    # Add regressors (additional features)
    model.add_regressor('hour_sin')
    model.add_regressor('hour_cos')
    model.add_regressor('day_sin')
    model.add_regressor('day_cos')
    model.add_regressor('humidity')
    model.add_regressor('wind_speed')
    model.add_regressor('rainfall')
    
    # Fit model
    model.fit(train_df)
    
    logger.info(f"✓ Model trained on {len(train_df)} samples")
    
    return model


def evaluate_model(model: Prophet, test_df: pd.DataFrame, horizon_hours: int) -> dict:
    """
    Evaluate Prophet model on test data.
    
    Args:
        model: Trained Prophet model
        test_df: Test data
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Dictionary with evaluation metrics
    """
    logger.info(f"📊 Evaluating model for {horizon_hours}h horizon...")
    
    # Make predictions
    forecast = model.predict(test_df)
    
    # Extract predictions and actuals
    y_true = test_df['y'].values
    y_pred = forecast['yhat'].values
    
    # Calculate metrics
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    
    metrics = {
        'horizon_hours': horizon_hours,
        'mae': float(mae),
        'rmse': float(rmse),
        'mape': float(mape),
        'n_samples': len(y_true),
        'mean_actual': float(np.mean(y_true)),
        'mean_predicted': float(np.mean(y_pred)),
    }
    
    logger.info(f"✓ MAE: {mae:.2f}°C, RMSE: {rmse:.2f}°C, MAPE: {mape:.2f}%")
    
    return metrics


def cross_validate_model(df: pd.DataFrame, horizon_hours: int, n_splits: int = 5) -> dict:
    """
    Perform time series cross-validation using TimeSeriesSplit.
    
    CRITICAL: TimeSeriesSplit ensures NO data leakage by:
    - Always training on past data
    - Always validating on future data
    - NO random shuffling
    - Expanding window approach
    
    Args:
        df: Full dataset with features
        horizon_hours: Forecast horizon in hours
        n_splits: Number of CV splits
    
    Returns:
        Dictionary with cross-validation metrics
    """
    logger.info(f"🔄 Cross-validating model for {horizon_hours}h horizon with {n_splits} splits...")
    
    # Prepare data for this horizon
    prophet_df = prepare_prophet_data(df, horizon_hours)
    
    # Initialize TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    # Store metrics for each fold
    fold_metrics = []
    
    for fold, (train_idx, val_idx) in enumerate(tscv.split(prophet_df), 1):
        logger.info(f"  Fold {fold}/{n_splits}...")
        
        # Split data (CRITICAL: train_idx < val_idx always, ensuring temporal ordering)
        train_df = prophet_df.iloc[train_idx]
        val_df = prophet_df.iloc[val_idx]
        
        # Verify temporal ordering (sanity check)
        assert train_df['ds'].max() < val_df['ds'].min(), "CRITICAL: Data leakage detected! Train data overlaps with validation data."
        
        # Train model
        model = train_prophet_model(train_df, horizon_hours)
        
        # Evaluate model
        metrics = evaluate_model(model, val_df, horizon_hours)
        metrics['fold'] = fold
        fold_metrics.append(metrics)
        
        logger.info(f"    Fold {fold} MAE: {metrics['mae']:.2f}°C")
    
    # Calculate average metrics across folds
    avg_metrics = {
        'horizon_hours': horizon_hours,
        'n_splits': n_splits,
        'mae_mean': float(np.mean([m['mae'] for m in fold_metrics])),
        'mae_std': float(np.std([m['mae'] for m in fold_metrics])),
        'rmse_mean': float(np.mean([m['rmse'] for m in fold_metrics])),
        'rmse_std': float(np.std([m['rmse'] for m in fold_metrics])),
        'mape_mean': float(np.mean([m['mape'] for m in fold_metrics])),
        'mape_std': float(np.std([m['mape'] for m in fold_metrics])),
        'fold_metrics': fold_metrics,
    }
    
    logger.info(f"✓ Cross-validation complete: MAE = {avg_metrics['mae_mean']:.2f} ± {avg_metrics['mae_std']:.2f}°C")
    
    return avg_metrics


def train_final_model(df: pd.DataFrame, horizon_hours: int) -> tuple:
    """
    Train final model on all available data.
    
    Args:
        df: Full dataset with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Tuple of (trained_model, metrics)
    """
    logger.info(f"🎯 Training final model for {horizon_hours}h horizon on all data...")
    
    # Prepare data
    prophet_df = prepare_prophet_data(df, horizon_hours)
    
    # Use last 20% as test set (temporal split)
    split_idx = int(len(prophet_df) * 0.8)
    train_df = prophet_df.iloc[:split_idx]
    test_df = prophet_df.iloc[split_idx:]
    
    # Verify temporal ordering
    assert train_df['ds'].max() < test_df['ds'].min(), "CRITICAL: Data leakage detected!"
    
    logger.info(f"  Train: {len(train_df)} samples ({train_df['ds'].min()} to {train_df['ds'].max()})")
    logger.info(f"  Test: {len(test_df)} samples ({test_df['ds'].min()} to {test_df['ds'].max()})")
    
    # Train model
    model = train_prophet_model(train_df, horizon_hours)
    
    # Evaluate on test set
    metrics = evaluate_model(model, test_df, horizon_hours)
    
    return model, metrics


def save_model(model: Prophet, horizon_hours: int, metrics: dict):
    """
    Save trained model and metrics to disk.
    
    Args:
        model: Trained Prophet model
        horizon_hours: Forecast horizon in hours
        metrics: Evaluation metrics
    """
    # Save model
    model_path = MODEL_DIR / f"prophet_{horizon_hours}h.pkl"
    joblib.dump(model, model_path)
    logger.info(f"💾 Saved model to {model_path}")
    
    # Save metrics
    metrics_path = METRICS_DIR / f"prophet_{horizon_hours}h_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"💾 Saved metrics to {metrics_path}")


def main():
    """
    Main training pipeline.
    
    Steps:
    1. Load historical data from database
    2. Validate no mock data
    3. Create features
    4. For each horizon:
       a. Cross-validate model
       b. Train final model
       c. Save model and metrics
    """
    logger.info("=" * 60)
    logger.info("PROPHET BASELINE ML MODEL TRAINING")
    logger.info("=" * 60)
    logger.info("")
    logger.info("⚠️  CRITICAL REQUIREMENTS:")
    logger.info("  - ZERO data leakage (strict temporal ordering)")
    logger.info("  - TimeSeriesSplit for cross-validation")
    logger.info("  - Real data only (no mock/synthetic data)")
    logger.info("")
    
    # Load data
    df = load_historical_data()
    
    # Create features
    df = create_features(df)
    
    # Train models for each horizon
    all_metrics = {}
    
    for horizon_hours in HORIZONS:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"TRAINING MODEL FOR {horizon_hours}H HORIZON")
        logger.info("=" * 60)
        
        # Cross-validate
        cv_metrics = cross_validate_model(df, horizon_hours, n_splits=5)
        
        # Train final model
        model, test_metrics = train_final_model(df, horizon_hours)
        
        # Combine metrics
        combined_metrics = {
            'cross_validation': cv_metrics,
            'test_set': test_metrics,
            'trained_at': datetime.now().isoformat(),
        }
        
        # Save model and metrics
        save_model(model, horizon_hours, combined_metrics)
        
        all_metrics[f"{horizon_hours}h"] = combined_metrics
    
    # Save summary metrics
    summary_path = METRICS_DIR / "training_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    logger.info(f"💾 Saved training summary to {summary_path}")
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Horizon | CV MAE (°C) | Test MAE (°C) | Success Criteria")
    logger.info("-" * 60)
    
    success_criteria = {1: 1.5, 3: 2.0, 6: 2.5, 12: 3.0, 24: 3.5}
    
    for horizon_hours in HORIZONS:
        cv_mae = all_metrics[f"{horizon_hours}h"]['cross_validation']['mae_mean']
        test_mae = all_metrics[f"{horizon_hours}h"]['test_set']['mae']
        criteria = success_criteria[horizon_hours]
        status = "✅" if test_mae < criteria else "❌"
        
        logger.info(f"{horizon_hours:2d}h     | {cv_mae:11.2f} | {test_mae:13.2f} | < {criteria:.1f}°C {status}")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
