#!/usr/bin/env python3
"""
Train Prophet baseline ML model for RAINFALL CLASSIFICATION (will it rain?).

PRIMARY TARGET: RAINFALL PREDICTION
- Binary classification: Will it rain? (yes/no)
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
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
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

# Rainfall threshold for classification (mm/hour)
RAINFALL_THRESHOLD = 0.5  # >0.5mm/hour = "raining"

# Model directory
MODEL_DIR = Path(__file__).parent.parent / "models" / "rainfall_classifier"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Metrics directory
METRICS_DIR = Path(__file__).parent.parent / "metrics" / "rainfall_classifier"
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
    Create features for rainfall prediction.
    
    Features for RAINFALL PREDICTION:
    - Current conditions: humidity (CRITICAL!), pressure, wind_speed, wind_direction, temperature
    - Historical rainfall: rainfall_lag_1h, rainfall_lag_3h, rainfall_lag_6h, rainfall_lag_24h
    - Time patterns: hour_of_day (cyclical), day_of_year (cyclical), month
    - Monsoon indicators: is_monsoon_season (Nov-Jan: NE, May-Sep: SW)
    - Humidity/pressure trends: humidity_change_1h, pressure_drop_3h
    
    CRITICAL: Features must only use data available at prediction time.
    NO future data leakage.
    """
    logger.info("🔧 Creating features for rainfall prediction...")
    
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
    Prepare data for Prophet rainfall classification model.
    
    Prophet requires:
    - 'ds': datetime column
    - 'y': target column (binary: will it rain at horizon_hours ahead?)
    - Additional regressors as separate columns
    
    Args:
        df: DataFrame with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        DataFrame ready for Prophet training
    """
    logger.info(f"📋 Preparing data for {horizon_hours}h horizon...")
    
    df = df.copy()
    
    # Create binary target: will it rain at horizon_hours ahead?
    # CRITICAL: This ensures we're predicting FUTURE rainfall, not current
    future_rainfall = df['rainfall'].shift(-horizon_hours)
    df['y'] = (future_rainfall > RAINFALL_THRESHOLD).astype(int)
    
    # Rename timestamp to 'ds' (Prophet requirement)
    df['ds'] = df['timestamp']
    
    # Drop rows with NaN values (first few rows for lags, last few for target)
    df = df.dropna()
    
    # Calculate class distribution
    rain_count = df['y'].sum()
    no_rain_count = len(df) - rain_count
    rain_pct = rain_count / len(df) * 100
    
    logger.info(f"✓ Prepared {len(df)} samples for {horizon_hours}h horizon")
    logger.info(f"  Rain: {rain_count} ({rain_pct:.1f}%), No rain: {no_rain_count} ({100-rain_pct:.1f}%)")
    
    return df


def train_prophet_classifier(train_df: pd.DataFrame, horizon_hours: int) -> Prophet:
    """
    Train Prophet model for rainfall classification.
    
    Args:
        train_df: Training data (must have 'ds', 'y', and regressor columns)
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Trained Prophet model
    """
    logger.info(f"🤖 Training Prophet classifier for {horizon_hours}h horizon...")
    
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


def evaluate_classifier(model: Prophet, test_df: pd.DataFrame, horizon_hours: int) -> dict:
    """
    Evaluate Prophet classifier on test data.
    
    Args:
        model: Trained Prophet model
        test_df: Test data
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Dictionary with evaluation metrics
    """
    logger.info(f"📊 Evaluating classifier for {horizon_hours}h horizon...")
    
    # Make predictions
    forecast = model.predict(test_df)
    
    # Extract predictions and actuals
    y_true = test_df['y'].values
    y_pred_prob = forecast['yhat'].values
    
    # Convert probabilities to binary predictions (threshold = 0.5)
    y_pred = (y_pred_prob > 0.5).astype(int)
    
    # Calculate metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    # ROC-AUC (if we have both classes)
    try:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
    except ValueError:
        roc_auc = None
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    metrics = {
        'horizon_hours': horizon_hours,
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'roc_auc': float(roc_auc) if roc_auc is not None else None,
        'confusion_matrix': {
            'true_negative': int(tn),
            'false_positive': int(fp),
            'false_negative': int(fn),
            'true_positive': int(tp),
        },
        'n_samples': len(y_true),
        'rain_events': int(y_true.sum()),
        'predicted_rain': int(y_pred.sum()),
    }
    
    logger.info(f"✓ Accuracy: {accuracy:.3f}, Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
    
    return metrics


def cross_validate_classifier(df: pd.DataFrame, horizon_hours: int, n_splits: int = 5) -> dict:
    """
    Perform time series cross-validation for rainfall classifier.
    
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
    logger.info(f"🔄 Cross-validating classifier for {horizon_hours}h horizon with {n_splits} splits...")
    
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
        model = train_prophet_classifier(train_df, horizon_hours)
        
        # Evaluate model
        metrics = evaluate_classifier(model, val_df, horizon_hours)
        metrics['fold'] = fold
        fold_metrics.append(metrics)
        
        logger.info(f"    Fold {fold} F1: {metrics['f1_score']:.3f}")
    
    # Calculate average metrics across folds
    avg_metrics = {
        'horizon_hours': horizon_hours,
        'n_splits': n_splits,
        'accuracy_mean': float(np.mean([m['accuracy'] for m in fold_metrics])),
        'accuracy_std': float(np.std([m['accuracy'] for m in fold_metrics])),
        'precision_mean': float(np.mean([m['precision'] for m in fold_metrics])),
        'precision_std': float(np.std([m['precision'] for m in fold_metrics])),
        'recall_mean': float(np.mean([m['recall'] for m in fold_metrics])),
        'recall_std': float(np.std([m['recall'] for m in fold_metrics])),
        'f1_mean': float(np.mean([m['f1_score'] for m in fold_metrics])),
        'f1_std': float(np.std([m['f1_score'] for m in fold_metrics])),
        'fold_metrics': fold_metrics,
    }
    
    logger.info(f"✓ Cross-validation complete: F1 = {avg_metrics['f1_mean']:.3f} ± {avg_metrics['f1_std']:.3f}")
    
    return avg_metrics


def train_final_classifier(df: pd.DataFrame, horizon_hours: int) -> tuple:
    """
    Train final classifier on all available data.
    
    Args:
        df: Full dataset with features
        horizon_hours: Forecast horizon in hours
    
    Returns:
        Tuple of (trained_model, metrics)
    """
    logger.info(f"🎯 Training final classifier for {horizon_hours}h horizon on all data...")
    
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
    model = train_prophet_classifier(train_df, horizon_hours)
    
    # Evaluate on test set
    metrics = evaluate_classifier(model, test_df, horizon_hours)
    
    return model, metrics


def save_model(model: Prophet, horizon_hours: int, metrics: dict, version: str = "v1.0.0"):
    """
    Save trained model and metrics to disk, and register in database.
    
    Args:
        model: Trained Prophet model
        horizon_hours: Forecast horizon in hours
        metrics: Evaluation metrics
        version: Semantic version for this model
    """
    # Save model
    model_path = MODEL_DIR / f"prophet_rainfall_classifier_{horizon_hours}h.pkl"
    joblib.dump(model, model_path)
    logger.info(f"💾 Saved model to {model_path}")
    
    # Save metrics
    metrics_path = METRICS_DIR / f"prophet_rainfall_classifier_{horizon_hours}h_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"💾 Saved metrics to {metrics_path}")
    
    # Register model in database
    try:
        features = [
            'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
            'humidity', 'pressure', 'wind_speed', 'temperature',
            'is_ne_monsoon', 'is_sw_monsoon',
            'rainfall_lag_1h', 'rainfall_lag_3h', 'rainfall_lag_6h', 'rainfall_lag_24h',
            'humidity_change_1h', 'pressure_drop_3h', 'wind_from_west'
        ]
        
        config = {
            'model_type': 'Prophet',
            'weather_parameter': 'rainfall_probability',
            'country': 'Singapore',
            'horizon_hours': horizon_hours,
            'threshold': RAINFALL_THRESHOLD,
            'hyperparameters': {
                'daily_seasonality': True,
                'weekly_seasonality': True,
                'yearly_seasonality': True,
                'changepoint_prior_scale': 0.05,
                'seasonality_prior_scale': 10.0,
            },
            'training_samples': metrics.get('test_set', {}).get('n_samples', 0)
        }
        
        # Extract test set metrics for registration
        test_metrics = metrics.get('test_set', {})
        registration_metrics = {
            'mae': 0,  # Not applicable for classifier
            'rmse': 0,  # Not applicable for classifier
            'accuracy': test_metrics.get('accuracy', 0),
            'precision': test_metrics.get('precision', 0),
            'recall': test_metrics.get('recall', 0),
            'f1_score': test_metrics.get('f1_score', 0),
            'roc_auc': test_metrics.get('roc_auc'),
            'confusion_matrix': test_metrics.get('confusion_matrix', {}),
            'test_set': test_metrics,
            'cross_validation': metrics.get('cross_validation', {})
        }
        
        model_id = register_model_version(
            model_name='rainfall_classifier',
            semantic_version=f"{version}_{horizon_hours}h",
            model_path=str(model_path),
            config=config,
            metrics=registration_metrics,
            features=features,
            notes=f"Prophet rainfall classifier for {horizon_hours}h horizon. Trained on Singapore data.",
            status='testing'  # Set to 'active' manually after validation
        )
        
        # Log performance metrics
        log_model_performance(
            model_version=f"{version}_{horizon_hours}h",
            model_name='rainfall_classifier',
            horizon_hours=horizon_hours,
            metrics={
                'mae': None,
                'rmse': None,
                'f1_score': test_metrics.get('f1_score'),
                'accuracy': test_metrics.get('accuracy'),
                'precision': test_metrics.get('precision'),
                'recall': test_metrics.get('recall'),
                'n_samples': test_metrics.get('n_samples'),
                'rain_events': test_metrics.get('rain_events')
            }
        )
        
        logger.info(f"✅ Registered model in database (ID: {model_id})")
        
    except Exception as e:
        logger.error(f"⚠️  Failed to register model in database: {e}")
        logger.info("Model and metrics saved to disk, but not registered in database")


def main():
    """
    Main training pipeline for rainfall classification.
    
    Steps:
    1. Load historical data from database
    2. Validate no mock data
    3. Create features for rainfall prediction
    4. For each horizon:
       a. Cross-validate classifier
       b. Train final classifier
       c. Save model and metrics
    """
    logger.info("=" * 60)
    logger.info("PROPHET RAINFALL CLASSIFIER TRAINING")
    logger.info("=" * 60)
    logger.info("")
    logger.info("🎯 PRIMARY TARGET: RAINFALL PREDICTION")
    logger.info("   Binary classification: Will it rain? (yes/no)")
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
    
    # Train classifiers for each horizon
    all_metrics = {}
    
    for horizon_hours in HORIZONS:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"TRAINING CLASSIFIER FOR {horizon_hours}H HORIZON")
        logger.info("=" * 60)
        
        # Cross-validate
        cv_metrics = cross_validate_classifier(df, horizon_hours, n_splits=5)
        
        # Train final model
        model, test_metrics = train_final_classifier(df, horizon_hours)
        
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
    logger.info("TRAINING SUMMARY - RAINFALL CLASSIFIER")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Horizon | CV F1   | Test F1 | Test Acc | Test Prec | Test Rec | Success")
    logger.info("-" * 80)
    
    for horizon_hours in HORIZONS:
        cv_f1 = all_metrics[f"{horizon_hours}h"]['cross_validation']['f1_mean']
        test_f1 = all_metrics[f"{horizon_hours}h"]['test_set']['f1_score']
        test_acc = all_metrics[f"{horizon_hours}h"]['test_set']['accuracy']
        test_prec = all_metrics[f"{horizon_hours}h"]['test_set']['precision']
        test_rec = all_metrics[f"{horizon_hours}h"]['test_set']['recall']
        
        # Success criteria: Accuracy > 75%, Precision > 0.70, Recall > 0.70, F1 > 0.70
        success = test_acc > 0.75 and test_prec > 0.70 and test_rec > 0.70 and test_f1 > 0.70
        status = "✅" if success else "❌"
        
        logger.info(f"{horizon_hours:2d}h     | {cv_f1:.3f}   | {test_f1:.3f}   | {test_acc:.3f}    | {test_prec:.3f}     | {test_rec:.3f}    | {status}")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ RAINFALL CLASSIFIER TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
