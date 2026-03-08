#!/usr/bin/env python3
"""
Train Prophet baseline ML model for RAINFALL REGRESSION (how much rain?).

PRIMARY TARGET: RAINFALL INTENSITY PREDICTION
- Regression: How much rain? (mm/hour)
- Singapore's biggest weather challenge (temperature is stable, rainfall is variable)

This script implements a research-based approach with:
- ZERO data leakage (strict temporal ordering)
- TimeSeriesSplit for cross-validation
- Multiple forecast horizons (1h, 3h, 6h, 12h, 24h)
- Proper feature engineering (humidity, pressure, wind patterns)
- Real data only (no mock/synthetic data)

Based on ML_FORECASTING_STRATEGY.md and HISTORICAL_DATA_ANALYSIS_2022_2025.md
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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db

# Import model registration
from ml.register_model import register_model_version, log_model_performance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Forecast horizons (in hours)
HORIZONS = [1, 3, 6, 12, 24]

# Model directory
MODEL_DIR = Path(__file__).parent.parent / "models" / "rainfall_regressor"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Metrics directory
METRICS_DIR = Path(__file__).parent.parent / "metrics" / "rainfall_regressor"
METRICS_DIR.mkdir(parents=True, exist_ok=True)


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
    for col in ['rainfall', 'humidity', 'pressure']:
        if col in df.columns:
            # Check for runs of identical values
            runs = (df[col] != df[col].shift()).cumsum()
            run_lengths = runs.value_counts()
            if run_lengths.max() > 100:
                logger.error(f"❌ Found suspicious repeated values in {col}: {run_lengths.max()} consecutive identical values")
                return False
    
    # Check for unrealistic rainfall patterns (constant for >24 hours)
    if 'rainfall' in df.columns:
        rainfall_std_24h = df['rainfall'].rolling(window=24).std()
        # Allow constant zero rainfall (dry periods), but not constant non-zero
        non_zero_constant = ((rainfall_std_24h < 0.01) & (df['rainfall'] > 0)).sum()
        if non_zero_constant > 0:
            logger.error("❌ Found unrealistic rainfall patterns (constant non-zero for >24 hours)")
            return False
    
    logger.info("✅ No mock/synthetic data detected")
    return True


def load_historical_data() -> pd.DataFrame:
    """
    Load historical weather data from database.
    
    Returns:
        DataFrame with columns: timestamp, rainfall, humidity, pressure, wind_speed, etc.
    """
    logger.info("📊 Loading historical weather data from database...")
    
    db = next(get_db())
    
    # Query all weather records, ordered by timestamp (CRITICAL for temporal integrity)
    query = """
        SELECT 
            timestamp,
            rainfall,
            humidity,
            pressure,
            wind_speed,
            wind_direction,
            temperature,
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
    df = pd.DataFrame(rows, columns=['timestamp', 'rainfall', 'humidity', 'pressure',
                                      'wind_speed', 'wind_direction', 'temperature', 'source_api'])
    
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
    Create features for rainfall intensity prediction.
    
    Features for RAINFALL INTENSITY PREDICTION:
    - Current conditions: humidity (CRITICAL!), pressure, wind_speed, wind_direction, temperature
    - Historical rainfall: rainfall_lag_1h, rainfall_lag_3h, rainfall_lag_6h, rainfall_lag_24h
    - Time patterns: hour_of_day (cyclical), day_of_year (cyclical), month
    - Monsoon indicators: is_monsoon_season (Nov-Jan: NE, May-Sep: SW)
    - Humidity/pressure trends: humidity_change_1h, pressure_drop_3h
    
    CRITICAL: Features must only use data available at prediction time.
    NO future data leakage.
    """
    logger.info("🔧 Creating features for rainfall intensity prediction...")
    
    df = df.copy()
    
    # Extract time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_year'] = df['timestamp'].dt.dayofyear
    df['month'] = df['timestamp'].dt.month
    
    # Cyclical encoding for hour (0-23)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Cyclical encoding for day of year (1-365)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    
    # Monsoon season indicators
    # NE Monsoon: November-January (11, 12, 1)
    # SW Monsoon: May-September (5, 6, 7, 8, 9)
    df['is_ne_monsoon'] = df['month'].isin([11, 12, 1]).astype(int)
    df['is_sw_monsoon'] = df['month'].isin([5, 6, 7, 8, 9]).astype(int)
    
    # Lagged rainfall features (CRITICAL: use past data only)
    df['rainfall_lag_1h'] = df['rainfall'].shift(1)
    df['rainfall_lag_3h'] = df['rainfall'].shift(3)
    df['rainfall_lag_6h'] = df['rainfall'].shift(6)
    df['rainfall_lag_24h'] = df['rainfall'].shift(24)
    
    # Humidity change (rapid increase → rain likely)
    df['humidity_change_1h'] = df['humidity'] - df['humidity'].shift(1)
    
    # Pressure drop (pressure drop → rain likely)
    df['pressure_drop_3h'] = df['pressure'].shift(3) - df['pressure']
    
    # Wind direction indicators (Sumatra squalls from west/southwest)
    # Wind direction: 0° = North, 90° = East, 180° = South, 270° = West
    df['wind_from_west'] = ((df['wind_direction'] >= 225) & (df['wind_direction'] <= 315)).astype(int)
    
    logger.info(f"✓ Created features: cyclical time, monsoon indicators, lagged rainfall, humidity/pressure trends")
    
    return df


def prepare_prophet_data(df: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    """
    Prepare data for Prophet rainfall regression model.
    
    Prophet requires:
    - 'ds': datetime column
    - 'y': target column (rainfall intensity at horizon_hours ahead in mm/hour)
    - Additional regressors as separate columns
    
    Args:
        df: DataFrame with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        DataFrame ready for Prophet training
    """
    logger.info(f"📋 Preparing data for {horizon_hours}h horizon...")
    
    df = df.copy()
    
    # Create target: rainfall intensity at horizon_hours ahead
    # CRITICAL: This ensures we're predicting FUTURE rainfall, not current
    df['y'] = df['rainfall'].shift(-horizon_hours)
    
    # Rename timestamp to 'ds' (Prophet requirement)
    df['ds'] = df['timestamp']
    
    # Drop rows with NaN values (first few rows for lags, last few for target)
    df = df.dropna()
    
    # Calculate rainfall statistics
    rain_events = (df['y'] > 0).sum()
    rain_pct = rain_events / len(df) * 100
    mean_rainfall = df[df['y'] > 0]['y'].mean() if rain_events > 0 else 0
    
    logger.info(f"✓ Prepared {len(df)} samples for {horizon_hours}h horizon")
    logger.info(f"  Rain events: {rain_events} ({rain_pct:.1f}%), Mean rainfall: {mean_rainfall:.2f} mm/h")
    
    return df


def train_prophet_regressor(train_df: pd.DataFrame, horizon_hours: int) -> Prophet:
    """
    Train Prophet model for rainfall intensity regression.
    
    Args:
        train_df: Training data (must have 'ds', 'y', and regressor columns)
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Trained Prophet model
    """
    logger.info(f"🤖 Training Prophet regressor for {horizon_hours}h horizon...")
    
    # Initialize Prophet with seasonality
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
    )
    
    # Add regressors (features for rainfall prediction)
    model.add_regressor('hour_sin')
    model.add_regressor('hour_cos')
    model.add_regressor('day_sin')
    model.add_regressor('day_cos')
    model.add_regressor('humidity')
    model.add_regressor('pressure')
    model.add_regressor('wind_speed')
    model.add_regressor('temperature')
    model.add_regressor('is_ne_monsoon')
    model.add_regressor('is_sw_monsoon')
    model.add_regressor('rainfall_lag_1h')
    model.add_regressor('rainfall_lag_3h')
    model.add_regressor('rainfall_lag_6h')
    model.add_regressor('rainfall_lag_24h')
    model.add_regressor('humidity_change_1h')
    model.add_regressor('pressure_drop_3h')
    model.add_regressor('wind_from_west')
    
    # Fit model
    model.fit(train_df)
    
    logger.info(f"✓ Model trained on {len(train_df)} samples")
    
    return model


def evaluate_regressor(model: Prophet, test_df: pd.DataFrame, horizon_hours: int) -> dict:
    """
    Evaluate Prophet regressor on test data.
    
    Args:
        model: Trained Prophet model
        test_df: Test data
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Dictionary with evaluation metrics
    """
    logger.info(f"📊 Evaluating regressor for {horizon_hours}h horizon...")
    
    # Make predictions
    forecast = model.predict(test_df)
    
    # Extract predictions and actuals
    y_true = test_df['y'].values
    y_pred = forecast['yhat'].values
    
    # Clip negative predictions to 0 (rainfall can't be negative)
    y_pred = np.maximum(y_pred, 0)
    
    # Calculate metrics
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    # Calculate R² (may be negative if model is worse than mean)
    r2 = r2_score(y_true, y_pred)
    
    # Calculate MAPE only for non-zero rainfall (avoid division by zero)
    non_zero_mask = y_true > 0
    if non_zero_mask.sum() > 0:
        mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
    else:
        mape = None
    
    metrics = {
        'horizon_hours': horizon_hours,
        'mae': float(mae),
        'rmse': float(rmse),
        'r2': float(r2),
        'mape': float(mape) if mape is not None else None,
        'n_samples': len(y_true),
        'rain_events': int((y_true > 0).sum()),
        'mean_actual': float(np.mean(y_true)),
        'mean_predicted': float(np.mean(y_pred)),
        'max_actual': float(np.max(y_true)),
        'max_predicted': float(np.max(y_pred)),
    }
    
    logger.info(f"✓ MAE: {mae:.2f} mm/h, RMSE: {rmse:.2f} mm/h, R²: {r2:.3f}")
    
    return metrics


def cross_validate_regressor(df: pd.DataFrame, horizon_hours: int, n_splits: int = 5) -> dict:
    """
    Perform time series cross-validation for rainfall regressor.
    
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
    logger.info(f"🔄 Cross-validating regressor for {horizon_hours}h horizon with {n_splits} splits...")
    
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
        assert train_df['ds'].max() < val_df['ds'].min(), "CRITICAL: Data leakage detected!"
        
        # Train model
        model = train_prophet_regressor(train_df, horizon_hours)
        
        # Evaluate model
        metrics = evaluate_regressor(model, val_df, horizon_hours)
        metrics['fold'] = fold
        fold_metrics.append(metrics)
        
        logger.info(f"    Fold {fold} MAE: {metrics['mae']:.2f} mm/h")
    
    # Calculate average metrics across folds
    avg_metrics = {
        'horizon_hours': horizon_hours,
        'n_splits': n_splits,
        'mae_mean': float(np.mean([m['mae'] for m in fold_metrics])),
        'mae_std': float(np.std([m['mae'] for m in fold_metrics])),
        'rmse_mean': float(np.mean([m['rmse'] for m in fold_metrics])),
        'rmse_std': float(np.std([m['rmse'] for m in fold_metrics])),
        'r2_mean': float(np.mean([m['r2'] for m in fold_metrics])),
        'r2_std': float(np.std([m['r2'] for m in fold_metrics])),
        'fold_metrics': fold_metrics,
    }
    
    logger.info(f"✓ Cross-validation complete: MAE = {avg_metrics['mae_mean']:.2f} ± {avg_metrics['mae_std']:.2f} mm/h")
    
    return avg_metrics


def train_final_regressor(df: pd.DataFrame, horizon_hours: int) -> tuple:
    """
    Train final regressor on all available data.
    
    Args:
        df: Full dataset with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Tuple of (trained_model, metrics)
    """
    logger.info(f"🎯 Training final regressor for {horizon_hours}h horizon on all data...")
    
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
    model = train_prophet_regressor(train_df, horizon_hours)
    
    # Evaluate on test set
    metrics = evaluate_regressor(model, test_df, horizon_hours)
    
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
    model_path = MODEL_DIR / f"prophet_rainfall_regressor_{horizon_hours}h.pkl"
    joblib.dump(model, model_path)
    logger.info(f"💾 Saved model to {model_path}")
    
    # Save metrics
    metrics_path = METRICS_DIR / f"prophet_rainfall_regressor_{horizon_hours}h_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"💾 Saved metrics to {metrics_path}")


def main():
    """
    Main training pipeline for rainfall intensity regression.
    
    Steps:
    1. Load historical data from database
    2. Validate no mock data
    3. Create features for rainfall prediction
    4. For each horizon:
       a. Cross-validate regressor
       b. Train final regressor
       c. Save model and metrics
    """
    logger.info("=" * 60)
    logger.info("PROPHET RAINFALL REGRESSOR TRAINING")
    logger.info("=" * 60)
    logger.info("")
    logger.info("🎯 PRIMARY TARGET: RAINFALL INTENSITY PREDICTION")
    logger.info("   Regression: How much rain? (mm/hour)")
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
    
    # Train regressors for each horizon
    all_metrics = {}
    
    for horizon_hours in HORIZONS:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"TRAINING REGRESSOR FOR {horizon_hours}H HORIZON")
        logger.info("=" * 60)
        
        # Cross-validate
        cv_metrics = cross_validate_regressor(df, horizon_hours, n_splits=5)
        
        # Train final model
        model, test_metrics = train_final_regressor(df, horizon_hours)
        
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
    logger.info("TRAINING SUMMARY - RAINFALL REGRESSOR")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Horizon | CV MAE (mm/h) | Test MAE (mm/h) | Test RMSE (mm/h) | Success")
    logger.info("-" * 75)
    
    # Success criteria: MAE < 2mm/hour for 3h, RMSE < 3mm/hour for 3h
    success_criteria_mae = {1: 1.5, 3: 2.0, 6: 2.5, 12: 3.0, 24: 3.5}
    success_criteria_rmse = {1: 2.0, 3: 3.0, 6: 3.5, 12: 4.0, 24: 4.5}
    
    for horizon_hours in HORIZONS:
        cv_mae = all_metrics[f"{horizon_hours}h"]['cross_validation']['mae_mean']
        test_mae = all_metrics[f"{horizon_hours}h"]['test_set']['mae']
        test_rmse = all_metrics[f"{horizon_hours}h"]['test_set']['rmse']
        
        mae_criteria = success_criteria_mae[horizon_hours]
        rmse_criteria = success_criteria_rmse[horizon_hours]
        success = test_mae < mae_criteria and test_rmse < rmse_criteria
        status = "✅" if success else "❌"
        
        logger.info(f"{horizon_hours:2d}h     | {cv_mae:13.2f} | {test_mae:15.2f} | {test_rmse:17.2f} | {status}")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ RAINFALL REGRESSOR TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
