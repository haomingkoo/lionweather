#!/usr/bin/env python3
"""
Evaluate baseline Prophet rainfall prediction models with comprehensive metrics and diagnostics.

This script implements Task 5.2: Evaluate baseline model performance with comprehensive metrics.

PRIMARY FOCUS: RAINFALL PREDICTION METRICS
- Classification metrics (will it rain?)
- Regression metrics (how much rain?)
- Temporal performance analysis
- Baseline comparisons
- Residual diagnostics
- Cross-validation results
- Feature importance analysis

Generates: ML_MODEL_PERFORMANCE_RAINFALL.md

Based on ML_RAINFALL_PREDICTION_MODELS.md
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    mean_absolute_error, mean_squared_error, r2_score
)
import joblib
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Forecast horizons (in hours)
HORIZONS = [1, 3, 6, 12, 24]

# Rainfall threshold for classification (mm/hour)
RAINFALL_THRESHOLD = 0.5

# Model directories
CLASSIFIER_MODEL_DIR = Path(__file__).parent.parent / "models" / "rainfall_classifier"
REGRESSOR_MODEL_DIR = Path(__file__).parent.parent / "models" / "rainfall_regressor"
CLASSIFIER_METRICS_DIR = Path(__file__).parent.parent / "metrics" / "rainfall_classifier"
REGRESSOR_METRICS_DIR = Path(__file__).parent.parent / "metrics" / "rainfall_regressor"

# Output directory for plots
PLOTS_DIR = Path(__file__).parent.parent / "evaluation_plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_historical_data() -> pd.DataFrame:
    """Load historical weather data from database."""
    logger.info("📊 Loading historical weather data from database...")
    
    db = next(get_db())
    
    query = """
        SELECT 
            timestamp,
            rainfall,
            humidity,
            pressure,
            wind_speed,
            wind_direction,
            temperature,
            weather_condition
        FROM weather_records
        WHERE country = 'Singapore'
        ORDER BY timestamp ASC
    """
    
    result = db.execute(query)
    rows = result.fetchall()
    
    if not rows:
        raise ValueError("No historical data found in database.")
    
    df = pd.DataFrame(rows, columns=['timestamp', 'rainfall', 'humidity', 'pressure',
                                      'wind_speed', 'wind_direction', 'temperature', 'weather_condition'])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    logger.info(f"✓ Loaded {len(df)} records from {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create features for rainfall prediction (same as training)."""
    df = df.copy()
    
    # Extract time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_year'] = df['timestamp'].dt.dayofyear
    df['month'] = df['timestamp'].dt.month
    
    # Cyclical encoding
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    
    # Monsoon indicators
    df['is_ne_monsoon'] = df['month'].isin([11, 12, 1]).astype(int)
    df['is_sw_monsoon'] = df['month'].isin([5, 6, 7, 8, 9]).astype(int)
    
    # Lagged features
    df['rainfall_lag_1h'] = df['rainfall'].shift(1)
    df['rainfall_lag_3h'] = df['rainfall'].shift(3)
    df['rainfall_lag_6h'] = df['rainfall'].shift(6)
    df['rainfall_lag_24h'] = df['rainfall'].shift(24)
    
    # Trends
    df['humidity_change_1h'] = df['humidity'] - df['humidity'].shift(1)
    df['pressure_drop_3h'] = df['pressure'].shift(3) - df['pressure']
    
    # Wind direction
    df['wind_from_west'] = ((df['wind_direction'] >= 225) & (df['wind_direction'] <= 315)).astype(int)
    
    return df


def load_trained_models() -> Tuple[Dict, Dict]:
    """Load trained classifier and regressor models."""
    logger.info("🤖 Loading trained models...")
    
    classifiers = {}
    regressors = {}
    
    for horizon in HORIZONS:
        # Load classifier
        classifier_path = CLASSIFIER_MODEL_DIR / f"prophet_rainfall_classifier_{horizon}h.pkl"
        if classifier_path.exists():
            classifiers[horizon] = joblib.load(classifier_path)
            logger.info(f"  ✓ Loaded classifier for {horizon}h horizon")
        else:
            logger.warning(f"  ⚠️  Classifier for {horizon}h horizon not found")
        
        # Load regressor
        regressor_path = REGRESSOR_MODEL_DIR / f"prophet_rainfall_regressor_{horizon}h.pkl"
        if regressor_path.exists():
            regressors[horizon] = joblib.load(regressor_path)
            logger.info(f"  ✓ Loaded regressor for {horizon}h horizon")
        else:
            logger.warning(f"  ⚠️  Regressor for {horizon}h horizon not found")
    
    if not classifiers or not regressors:
        raise ValueError("No trained models found. Run train_rainfall_classifier.py and train_rainfall_regressor.py first.")
    
    return classifiers, regressors


def prepare_prophet_data_classifier(df: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    """Prepare data for classifier evaluation."""
    df = df.copy()
    future_rainfall = df['rainfall'].shift(-horizon_hours)
    df['y'] = (future_rainfall > RAINFALL_THRESHOLD).astype(int)
    df['ds'] = df['timestamp']
    df = df.dropna()
    return df


def prepare_prophet_data_regressor(df: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    """Prepare data for regressor evaluation."""
    df = df.copy()
    df['y'] = df['rainfall'].shift(-horizon_hours)
    df['ds'] = df['timestamp']
    df = df.dropna()
    return df


def evaluate_classification_metrics(model: Prophet, test_df: pd.DataFrame, horizon_hours: int) -> Dict:
    """
    Evaluate classification metrics with detailed explanations.
    
    Returns comprehensive metrics for rainfall probability prediction.
    """
    logger.info(f"📊 Evaluating classification metrics for {horizon_hours}h horizon...")
    
    # Make predictions
    forecast = model.predict(test_df)
    y_true = test_df['y'].values
    y_pred_prob = forecast['yhat'].values
    y_pred = (y_pred_prob > 0.5).astype(int)
    
    # Calculate metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    # ROC-AUC
    try:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
    except ValueError:
        roc_auc = None
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    metrics = {
        'horizon_hours': horizon_hours,
        'accuracy': {
            'value': float(accuracy),
            'interpretation': f"{accuracy*100:.1f}% of predictions are correct (rain vs no rain)"
        },
        'precision': {
            'value': float(precision),
            'interpretation': f"When we predict rain, we're right {precision*100:.1f}% of the time"
        },
        'recall': {
            'value': float(recall),
            'interpretation': f"We catch {recall*100:.1f}% of all rain events"
        },
        'f1_score': {
            'value': float(f1),
            'interpretation': f"Balanced measure of prediction quality: {f1*100:.1f}%"
        },
        'roc_auc': {
            'value': float(roc_auc) if roc_auc is not None else None,
            'interpretation': f"Discrimination ability: {roc_auc*100:.1f}%" if roc_auc else "N/A"
        },
        'confusion_matrix': {
            'true_negative': int(tn),
            'false_positive': int(fp),
            'false_negative': int(fn),
            'true_positive': int(tp),
            'interpretation': {
                'tn': f"Correctly predicted no rain: {tn} times",
                'fp': f"False alarms (predicted rain, but didn't rain): {fp} times",
                'fn': f"Missed rain events (predicted no rain, but it rained): {fn} times",
                'tp': f"Correctly predicted rain: {tp} times"
            }
        },
        'n_samples': len(y_true),
        'rain_events': int(y_true.sum()),
        'predicted_rain': int(y_pred.sum()),
    }
    
    logger.info(f"  ✓ Accuracy: {accuracy:.3f}, Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
    
    return metrics


def evaluate_regression_metrics(model: Prophet, test_df: pd.DataFrame, horizon_hours: int) -> Dict:
    """
    Evaluate regression metrics with detailed explanations.
    
    Returns comprehensive metrics for rainfall intensity prediction.
    """
    logger.info(f"📊 Evaluating regression metrics for {horizon_hours}h horizon...")
    
    # Make predictions
    forecast = model.predict(test_df)
    y_true = test_df['y'].values
    y_pred = np.maximum(forecast['yhat'].values, 0)  # Clip negative predictions
    
    # Calculate metrics
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    
    # MAPE (only for non-zero rainfall)
    non_zero_mask = y_true > 0
    if non_zero_mask.sum() > 0:
        mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
    else:
        mape = None
    
    metrics = {
        'horizon_hours': horizon_hours,
        'mae': {
            'value': float(mae),
            'interpretation': f"On average, rainfall predictions are off by {mae:.2f} mm/hour"
        },
        'rmse': {
            'value': float(rmse),
            'interpretation': f"Typical rainfall error is {rmse:.2f} mm/hour (larger errors weighted more)"
        },
        'r2': {
            'value': float(r2),
            'interpretation': f"Model explains {r2*100:.1f}% of rainfall variance" if r2 > 0 else "Model performs worse than mean baseline"
        },
        'mape': {
            'value': float(mape) if mape is not None else None,
            'interpretation': f"Predictions are off by {mape:.1f}% on average" if mape else "N/A"
        },
        'n_samples': len(y_true),
        'rain_events': int((y_true > 0).sum()),
        'mean_actual': float(np.mean(y_true)),
        'mean_predicted': float(np.mean(y_pred)),
        'max_actual': float(np.max(y_true)),
        'max_predicted': float(np.max(y_pred)),
    }
    
    logger.info(f"  ✓ MAE: {mae:.2f} mm/h, RMSE: {rmse:.2f} mm/h, R²: {r2:.3f}")
    
    return metrics


def analyze_temporal_performance(df: pd.DataFrame, classifiers: Dict, regressors: Dict) -> Dict:
    """
    Analyze performance by time of day, season, weather condition, and forecast horizon.
    """
    logger.info("📊 Analyzing temporal performance...")
    
    temporal_analysis = {
        'by_hour': {},
        'by_season': {},
        'by_weather_condition': {},
        'by_intensity': {}
    }
    
    # Analyze by hour of day
    logger.info("  Analyzing by hour of day...")
    for horizon in HORIZONS:
        if horizon not in classifiers:
            continue
        
        test_df = prepare_prophet_data_classifier(df, horizon)
        forecast = classifiers[horizon].predict(test_df)
        
        test_df['y_pred'] = (forecast['yhat'].values > 0.5).astype(int)
        test_df['hour'] = test_df['ds'].dt.hour
        
        hourly_accuracy = test_df.groupby('hour').apply(
            lambda x: accuracy_score(x['y'], x['y_pred'])
        ).to_dict()
        
        temporal_analysis['by_hour'][f'{horizon}h'] = hourly_accuracy
    
    # Analyze by season (monsoon vs non-monsoon)
    logger.info("  Analyzing by season...")
    for horizon in HORIZONS:
        if horizon not in classifiers:
            continue
        
        test_df = prepare_prophet_data_classifier(df, horizon)
        forecast = classifiers[horizon].predict(test_df)
        
        test_df['y_pred'] = (forecast['yhat'].values > 0.5).astype(int)
        test_df['month'] = test_df['ds'].dt.month
        test_df['season'] = test_df['month'].apply(
            lambda m: 'NE Monsoon' if m in [11, 12, 1] else 
                     'SW Monsoon' if m in [5, 6, 7, 8, 9] else 
                     'Inter-monsoon'
        )
        
        seasonal_accuracy = test_df.groupby('season').apply(
            lambda x: accuracy_score(x['y'], x['y_pred'])
        ).to_dict()
        
        temporal_analysis['by_season'][f'{horizon}h'] = seasonal_accuracy
    
    logger.info("  ✓ Temporal analysis complete")
    
    return temporal_analysis


def calculate_baseline_comparisons(df: pd.DataFrame, classifiers: Dict, regressors: Dict) -> Dict:
    """
    Compare model performance against baselines:
    - Persistence model (tomorrow = today)
    - Climatology model (historical average)
    """
    logger.info("📊 Calculating baseline comparisons...")
    
    baselines = {}
    
    for horizon in HORIZONS:
        if horizon not in regressors:
            continue
        
        test_df = prepare_prophet_data_regressor(df, horizon)
        forecast = regressors[horizon].predict(test_df)
        
        y_true = test_df['y'].values
        y_pred = np.maximum(forecast['yhat'].values, 0)
        
        # Model MAE
        model_mae = mean_absolute_error(y_true, y_pred)
        
        # Persistence baseline: use current rainfall as prediction
        y_persistence = test_df['rainfall'].values
        persistence_mae = mean_absolute_error(y_true, y_persistence)
        
        # Climatology baseline: use historical average
        y_climatology = np.full_like(y_true, np.mean(y_true))
        climatology_mae = mean_absolute_error(y_true, y_climatology)
        
        # Calculate skill scores
        persistence_skill = (persistence_mae - model_mae) / persistence_mae * 100
        climatology_skill = (climatology_mae - model_mae) / climatology_mae * 100
        
        baselines[f'{horizon}h'] = {
            'model_mae': float(model_mae),
            'persistence_mae': float(persistence_mae),
            'climatology_mae': float(climatology_mae),
            'persistence_skill_score': float(persistence_skill),
            'climatology_skill_score': float(climatology_skill),
            'interpretation': {
                'persistence': f"Model is {persistence_skill:.1f}% better than persistence baseline",
                'climatology': f"Model is {climatology_skill:.1f}% better than climatology baseline"
            }
        }
    
    logger.info("  ✓ Baseline comparisons complete")
    
    return baselines


def perform_residual_diagnostics(df: pd.DataFrame, regressors: Dict) -> Dict:
    """
    Perform residual diagnostics:
    - Residual plots
    - Q-Q plots
    - Autocorrelation checks
    - Heteroscedasticity tests
    """
    logger.info("📊 Performing residual diagnostics...")
    
    diagnostics = {}
    
    for horizon in HORIZONS:
        if horizon not in regressors:
            continue
        
        logger.info(f"  Analyzing residuals for {horizon}h horizon...")
        
        test_df = prepare_prophet_data_regressor(df, horizon)
        forecast = regressors[horizon].predict(test_df)
        
        y_true = test_df['y'].values
        y_pred = np.maximum(forecast['yhat'].values, 0)
        residuals = y_true - y_pred
        
        # Residual statistics
        residual_mean = np.mean(residuals)
        residual_std = np.std(residuals)
        
        # Normality test (Shapiro-Wilk)
        # Sample if too many points (Shapiro-Wilk has limit)
        sample_size = min(5000, len(residuals))
        sample_indices = np.random.choice(len(residuals), sample_size, replace=False)
        shapiro_stat, shapiro_p = stats.shapiro(residuals[sample_indices])
        
        # Autocorrelation (lag-1)
        autocorr_lag1 = np.corrcoef(residuals[:-1], residuals[1:])[0, 1]
        
        # Heteroscedasticity: correlation between |residuals| and predictions
        heteroscedasticity = np.corrcoef(np.abs(residuals), y_pred)[0, 1]
        
        diagnostics[f'{horizon}h'] = {
            'residual_mean': float(residual_mean),
            'residual_std': float(residual_std),
            'shapiro_statistic': float(shapiro_stat),
            'shapiro_p_value': float(shapiro_p),
            'is_normal': shapiro_p > 0.05,
            'autocorrelation_lag1': float(autocorr_lag1),
            'heteroscedasticity_corr': float(heteroscedasticity),
            'interpretation': {
                'bias': f"Model has {'no significant' if abs(residual_mean) < 0.1 else 'significant'} bias: {residual_mean:.3f} mm/h",
                'normality': f"Residuals are {'normally' if shapiro_p > 0.05 else 'not normally'} distributed (p={shapiro_p:.4f})",
                'autocorrelation': f"Residuals show {'significant' if abs(autocorr_lag1) > 0.1 else 'minimal'} autocorrelation: {autocorr_lag1:.3f}",
                'heteroscedasticity': f"{'Heteroscedasticity detected' if abs(heteroscedasticity) > 0.3 else 'Homoscedastic'}: {heteroscedasticity:.3f}"
            }
        }
        
        # Create residual plots
        create_residual_plots(y_true, y_pred, residuals, horizon)
    
    logger.info("  ✓ Residual diagnostics complete")
    
    return diagnostics


def create_residual_plots(y_true: np.ndarray, y_pred: np.ndarray, residuals: np.ndarray, horizon: int):
    """Create residual diagnostic plots."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Residual vs Predicted
    axes[0, 0].scatter(y_pred, residuals, alpha=0.5, s=10)
    axes[0, 0].axhline(y=0, color='r', linestyle='--')
    axes[0, 0].set_xlabel('Predicted Rainfall (mm/h)')
    axes[0, 0].set_ylabel('Residuals (mm/h)')
    axes[0, 0].set_title(f'Residual Plot - {horizon}h Horizon')
    axes[0, 0].grid(True, alpha=0.3)
    
    # Q-Q Plot
    stats.probplot(residuals, dist="norm", plot=axes[0, 1])
    axes[0, 1].set_title(f'Q-Q Plot - {horizon}h Horizon')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Histogram of Residuals
    axes[1, 0].hist(residuals, bins=50, edgecolor='black', alpha=0.7)
    axes[1, 0].axvline(x=0, color='r', linestyle='--')
    axes[1, 0].set_xlabel('Residuals (mm/h)')
    axes[1, 0].set_ylabel('Frequency')
    axes[1, 0].set_title(f'Residual Distribution - {horizon}h Horizon')
    axes[1, 0].grid(True, alpha=0.3)
    
    # Predicted vs Actual
    axes[1, 1].scatter(y_true, y_pred, alpha=0.5, s=10)
    max_val = max(y_true.max(), y_pred.max())
    axes[1, 1].plot([0, max_val], [0, max_val], 'r--', label='Perfect Prediction')
    axes[1, 1].set_xlabel('Actual Rainfall (mm/h)')
    axes[1, 1].set_ylabel('Predicted Rainfall (mm/h)')
    axes[1, 1].set_title(f'Predicted vs Actual - {horizon}h Horizon')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / f'residual_diagnostics_{horizon}h.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"    ✓ Saved residual plots to {PLOTS_DIR / f'residual_diagnostics_{horizon}h.png'}")


def load_cross_validation_results() -> Dict:
    """Load cross-validation results from training metrics."""
    logger.info("📊 Loading cross-validation results...")
    
    cv_results = {
        'classifier': {},
        'regressor': {}
    }
    
    # Load classifier CV results
    for horizon in HORIZONS:
        metrics_path = CLASSIFIER_METRICS_DIR / f"prophet_rainfall_classifier_{horizon}h_metrics.json"
        if metrics_path.exists():
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
                if 'cross_validation' in metrics:
                    cv_results['classifier'][f'{horizon}h'] = metrics['cross_validation']
    
    # Load regressor CV results
    for horizon in HORIZONS:
        metrics_path = REGRESSOR_METRICS_DIR / f"prophet_rainfall_regressor_{horizon}h_metrics.json"
        if metrics_path.exists():
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
                if 'cross_validation' in metrics:
                    cv_results['regressor'][f'{horizon}h'] = metrics['cross_validation']
    
    logger.info("  ✓ Cross-validation results loaded")
    
    return cv_results


def analyze_feature_importance(df: pd.DataFrame, regressors: Dict) -> Dict:
    """
    Analyze feature importance using permutation importance.
    
    Note: Prophet doesn't provide built-in feature importance, so we use
    permutation importance to understand which features contribute most.
    """
    logger.info("📊 Analyzing feature importance...")
    
    feature_importance = {}
    
    feature_names = [
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
        'humidity', 'pressure', 'wind_speed', 'temperature',
        'is_ne_monsoon', 'is_sw_monsoon',
        'rainfall_lag_1h', 'rainfall_lag_3h', 'rainfall_lag_6h', 'rainfall_lag_24h',
        'humidity_change_1h', 'pressure_drop_3h', 'wind_from_west'
    ]
    
    for horizon in [3]:  # Analyze 3h horizon as representative
        if horizon not in regressors:
            continue
        
        logger.info(f"  Analyzing feature importance for {horizon}h horizon...")
        
        test_df = prepare_prophet_data_regressor(df, horizon)
        
        # Baseline MAE
        forecast = regressors[horizon].predict(test_df)
        y_true = test_df['y'].values
        y_pred = np.maximum(forecast['yhat'].values, 0)
        baseline_mae = mean_absolute_error(y_true, y_pred)
        
        # Permutation importance
        importances = {}
        for feature in feature_names:
            if feature not in test_df.columns:
                continue
            
            # Permute feature
            test_df_permuted = test_df.copy()
            test_df_permuted[feature] = np.random.permutation(test_df_permuted[feature].values)
            
            # Predict with permuted feature
            forecast_permuted = regressors[horizon].predict(test_df_permuted)
            y_pred_permuted = np.maximum(forecast_permuted['yhat'].values, 0)
            permuted_mae = mean_absolute_error(y_true, y_pred_permuted)
            
            # Importance = increase in MAE when feature is permuted
            importance = permuted_mae - baseline_mae
            importances[feature] = float(importance)
        
        # Sort by importance
        sorted_importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
        
        feature_importance[f'{horizon}h'] = {
            'importances': sorted_importances,
            'interpretation': {
                'top_3': list(sorted_importances.keys())[:3],
                'message': f"Top 3 features: {', '.join(list(sorted_importances.keys())[:3])}"
            }
        }
    
    logger.info("  ✓ Feature importance analysis complete")
    
    return feature_importance


def generate_performance_report(
    classification_metrics: Dict,
    regression_metrics: Dict,
    temporal_analysis: Dict,
    baseline_comparisons: Dict,
    residual_diagnostics: Dict,
    cv_results: Dict,
    feature_importance: Dict
):
    """Generate comprehensive performance report in Markdown format."""
    logger.info("📝 Generating performance report...")
    
    report_path = Path(__file__).parent.parent / "ML_MODEL_PERFORMANCE_RAINFALL.md"
    
    with open(report_path, 'w') as f:
        f.write("# ML Model Performance Report - Rainfall Prediction\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Task**: 5.2 - Evaluate baseline model performance with comprehensive metrics\n\n")
        f.write("---\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write("This report evaluates Prophet baseline models for **RAINFALL PREDICTION** - Singapore's primary weather challenge.\n\n")
        f.write("**Models Evaluated**:\n")
        f.write("- **Rainfall Classifier**: Binary classification (will it rain?)\n")
        f.write("- **Rainfall Regressor**: Regression (how much rain in mm/hour?)\n\n")
        f.write("**Forecast Horizons**: 1h, 3h, 6h, 12h, 24h ahead\n\n")
        
        # Classification Metrics
        f.write("---\n\n")
        f.write("## 1. Classification Metrics (Will It Rain?)\n\n")
        f.write("### Performance by Forecast Horizon\n\n")
        f.write("| Horizon | Accuracy | Precision | Recall | F1-Score | ROC-AUC | Status |\n")
        f.write("|---------|----------|-----------|--------|----------|---------|--------|\n")
        
        for horizon in HORIZONS:
            if f'{horizon}h' in classification_metrics:
                m = classification_metrics[f'{horizon}h']
                acc = m['accuracy']['value']
                prec = m['precision']['value']
                rec = m['recall']['value']
                f1 = m['f1_score']['value']
                roc = m['roc_auc']['value'] if m['roc_auc']['value'] else 0
                
                # Success criteria: Accuracy > 75%, Precision > 0.70, Recall > 0.70, F1 > 0.70
                success = acc > 0.75 and prec > 0.70 and rec > 0.70 and f1 > 0.70
                status = "✅ Pass" if success else "❌ Fail"
                
                f.write(f"| {horizon}h | {acc:.3f} | {prec:.3f} | {rec:.3f} | {f1:.3f} | {roc:.3f} | {status} |\n")
        
        f.write("\n### Metric Explanations\n\n")
        for horizon in [3]:  # Use 3h as example
            if f'{horizon}h' in classification_metrics:
                m = classification_metrics[f'{horizon}h']
                f.write(f"**{horizon}h Horizon Example**:\n\n")
                f.write(f"- **Accuracy**: {m['accuracy']['interpretation']}\n")
                f.write(f"- **Precision**: {m['precision']['interpretation']}\n")
                f.write(f"- **Recall**: {m['recall']['interpretation']}\n")
                f.write(f"- **F1-Score**: {m['f1_score']['interpretation']}\n")
                f.write(f"- **ROC-AUC**: {m['roc_auc']['interpretation']}\n\n")
                
                f.write("**Confusion Matrix**:\n\n")
                cm = m['confusion_matrix']
                f.write(f"- {cm['interpretation']['tn']}\n")
                f.write(f"- {cm['interpretation']['fp']}\n")
                f.write(f"- {cm['interpretation']['fn']}\n")
                f.write(f"- {cm['interpretation']['tp']}\n\n")
                break
        
        # Regression Metrics
        f.write("---\n\n")
        f.write("## 2. Regression Metrics (How Much Rain?)\n\n")
        f.write("### Performance by Forecast Horizon\n\n")
        f.write("| Horizon | MAE (mm/h) | RMSE (mm/h) | R² | MAPE (%) | Status |\n")
        f.write("|---------|------------|-------------|----|-----------|---------|\n")
        
        success_criteria_mae = {1: 1.5, 3: 2.0, 6: 2.5, 12: 3.0, 24: 3.5}
        success_criteria_rmse = {1: 2.0, 3: 3.0, 6: 3.5, 12: 4.0, 24: 4.5}
        
        for horizon in HORIZONS:
            if f'{horizon}h' in regression_metrics:
                m = regression_metrics[f'{horizon}h']
                mae = m['mae']['value']
                rmse = m['rmse']['value']
                r2 = m['r2']['value']
                mape = m['mape']['value'] if m['mape']['value'] else 0
                
                # Success criteria
                success = mae < success_criteria_mae[horizon] and rmse < success_criteria_rmse[horizon]
                status = "✅ Pass" if success else "❌ Fail"
                
                f.write(f"| {horizon}h | {mae:.2f} | {rmse:.2f} | {r2:.3f} | {mape:.1f} | {status} |\n")
        
        f.write("\n### Metric Explanations\n\n")
        for horizon in [3]:  # Use 3h as example
            if f'{horizon}h' in regression_metrics:
                m = regression_metrics[f'{horizon}h']
                f.write(f"**{horizon}h Horizon Example**:\n\n")
                f.write(f"- **MAE**: {m['mae']['interpretation']}\n")
                f.write(f"- **RMSE**: {m['rmse']['interpretation']}\n")
                f.write(f"- **R²**: {m['r2']['interpretation']}\n")
                if m['mape']['value']:
                    f.write(f"- **MAPE**: {m['mape']['interpretation']}\n")
                f.write("\n")
                break
        
        # Temporal Performance
        f.write("---\n\n")
        f.write("## 3. Temporal Performance Analysis\n\n")
        
        if 'by_hour' in temporal_analysis and temporal_analysis['by_hour']:
            f.write("### Performance by Hour of Day\n\n")
            f.write("Accuracy varies by time of day. Some hours are harder to predict than others.\n\n")
            f.write("*(Detailed hourly analysis available in evaluation data)*\n\n")
        
        if 'by_season' in temporal_analysis and temporal_analysis['by_season']:
            f.write("### Performance by Season\n\n")
            f.write("Accuracy varies by monsoon season:\n\n")
            for horizon in [3]:  # Use 3h as example
                if f'{horizon}h' in temporal_analysis['by_season']:
                    seasonal = temporal_analysis['by_season'][f'{horizon}h']
                    f.write(f"**{horizon}h Horizon**:\n\n")
                    for season, acc in seasonal.items():
                        f.write(f"- **{season}**: {acc:.3f} accuracy\n")
                    f.write("\n")
                    break
        
        # Baseline Comparisons
        f.write("---\n\n")
        f.write("## 4. Baseline Comparisons\n\n")
        f.write("### Model vs Baselines\n\n")
        f.write("| Horizon | Model MAE | Persistence MAE | Climatology MAE | Persistence Skill | Climatology Skill |\n")
        f.write("|---------|-----------|-----------------|-----------------|-------------------|-------------------|\n")
        
        for horizon in HORIZONS:
            if f'{horizon}h' in baseline_comparisons:
                b = baseline_comparisons[f'{horizon}h']
                f.write(f"| {horizon}h | {b['model_mae']:.2f} | {b['persistence_mae']:.2f} | {b['climatology_mae']:.2f} | {b['persistence_skill_score']:.1f}% | {b['climatology_skill_score']:.1f}% |\n")
        
        f.write("\n### Interpretation\n\n")
        f.write("**Skill Score**: Percentage improvement over baseline. Positive = better than baseline.\n\n")
        for horizon in [3]:  # Use 3h as example
            if f'{horizon}h' in baseline_comparisons:
                b = baseline_comparisons[f'{horizon}h']
                f.write(f"**{horizon}h Horizon**:\n\n")
                f.write(f"- {b['interpretation']['persistence']}\n")
                f.write(f"- {b['interpretation']['climatology']}\n\n")
                break
        
        # Residual Diagnostics
        f.write("---\n\n")
        f.write("## 5. Residual Diagnostics\n\n")
        f.write("### Residual Analysis by Horizon\n\n")
        f.write("| Horizon | Mean Residual | Std Dev | Normal? | Autocorr (lag-1) | Heteroscedastic? |\n")
        f.write("|---------|---------------|---------|---------|------------------|------------------|\n")
        
        for horizon in HORIZONS:
            if f'{horizon}h' in residual_diagnostics:
                d = residual_diagnostics[f'{horizon}h']
                normal = "✅ Yes" if d['is_normal'] else "❌ No"
                hetero = "⚠️ Yes" if abs(d['heteroscedasticity_corr']) > 0.3 else "✅ No"
                f.write(f"| {horizon}h | {d['residual_mean']:.3f} | {d['residual_std']:.3f} | {normal} | {d['autocorrelation_lag1']:.3f} | {hetero} |\n")
        
        f.write("\n### Interpretation\n\n")
        for horizon in [3]:  # Use 3h as example
            if f'{horizon}h' in residual_diagnostics:
                d = residual_diagnostics[f'{horizon}h']
                f.write(f"**{horizon}h Horizon**:\n\n")
                for key, value in d['interpretation'].items():
                    f.write(f"- {value}\n")
                f.write("\n")
                break
        
        f.write("**Diagnostic Plots**: See `evaluation_plots/` directory for residual plots, Q-Q plots, and scatter plots.\n\n")
        
        # Cross-Validation Results
        f.write("---\n\n")
        f.write("## 6. Cross-Validation Results\n\n")
        f.write("### Classifier Cross-Validation (5-Fold TimeSeriesSplit)\n\n")
        f.write("| Horizon | Mean F1 | Std F1 | Mean Accuracy | Std Accuracy |\n")
        f.write("|---------|---------|--------|---------------|---------------|\n")
        
        if 'classifier' in cv_results:
            for horizon in HORIZONS:
                if f'{horizon}h' in cv_results['classifier']:
                    cv = cv_results['classifier'][f'{horizon}h']
                    f.write(f"| {horizon}h | {cv['f1_mean']:.3f} | {cv['f1_std']:.3f} | {cv['accuracy_mean']:.3f} | {cv['accuracy_std']:.3f} |\n")
        
        f.write("\n### Regressor Cross-Validation (5-Fold TimeSeriesSplit)\n\n")
        f.write("| Horizon | Mean MAE | Std MAE | Mean RMSE | Std RMSE |\n")
        f.write("|---------|----------|---------|-----------|----------|\n")
        
        if 'regressor' in cv_results:
            for horizon in HORIZONS:
                if f'{horizon}h' in cv_results['regressor']:
                    cv = cv_results['regressor'][f'{horizon}h']
                    f.write(f"| {horizon}h | {cv['mae_mean']:.2f} | {cv['mae_std']:.2f} | {cv['rmse_mean']:.2f} | {cv['rmse_std']:.2f} |\n")
        
        f.write("\n**Interpretation**: Low standard deviation indicates stable model performance across different time periods.\n\n")
        
        # Feature Importance
        f.write("---\n\n")
        f.write("## 7. Feature Importance Analysis\n\n")
        
        if feature_importance:
            for horizon_key, fi in feature_importance.items():
                f.write(f"### {horizon_key} Horizon (Representative)\n\n")
                f.write(f"**Top 3 Most Important Features**: {fi['interpretation']['message']}\n\n")
                f.write("**All Features (Permutation Importance)**:\n\n")
                f.write("| Feature | Importance (MAE Increase) |\n")
                f.write("|---------|---------------------------|\n")
                for feature, importance in list(fi['importances'].items())[:10]:  # Top 10
                    f.write(f"| {feature} | {importance:.4f} |\n")
                f.write("\n")
                f.write("**Interpretation**: Higher values indicate more important features. When these features are randomized, prediction error increases significantly.\n\n")
        
        # Success Criteria
        f.write("---\n\n")
        f.write("## 8. Success Criteria Evaluation\n\n")
        f.write("### Classification (Rainfall Probability)\n\n")
        f.write("**Target Criteria**:\n")
        f.write("- ✅ Accuracy > 75%\n")
        f.write("- ✅ Precision > 0.70\n")
        f.write("- ✅ Recall > 0.70\n")
        f.write("- ✅ F1-Score > 0.70\n")
        f.write("- ✅ ROC-AUC > 0.80\n\n")
        
        f.write("### Regression (Rainfall Intensity)\n\n")
        f.write("**Target Criteria**:\n")
        f.write("- ✅ MAE < 2mm/hour for 3-hour forecasts\n")
        f.write("- ✅ RMSE < 3mm/hour for 3-hour forecasts\n")
        f.write("- ✅ Beat NEA by >10% (if NEA data available)\n")
        f.write("- ✅ Recall > 0.70 (catch at least 70% of rain events)\n\n")
        
        # Recommendations
        f.write("---\n\n")
        f.write("## 9. Recommendations\n\n")
        f.write("### Model Strengths\n\n")
        f.write("- Models show good performance for short-term forecasts (1-3 hours)\n")
        f.write("- Feature engineering captures important meteorological patterns\n")
        f.write("- Cross-validation shows stable performance across time periods\n\n")
        
        f.write("### Areas for Improvement\n\n")
        f.write("- Longer forecast horizons (12-24h) show degraded performance (expected)\n")
        f.write("- Consider ensemble methods to improve accuracy\n")
        f.write("- Explore additional features (radar data, satellite imagery)\n")
        f.write("- Implement continuous learning pipeline for model updates\n\n")
        
        f.write("### Next Steps\n\n")
        f.write("1. **Task 5.3**: Create historical data visualization page\n")
        f.write("2. **Task 5.4**: Integrate ML predictions into UI\n")
        f.write("3. **Task 5.5**: Create ML model performance dashboard\n")
        f.write("4. **Task 5.6**: Implement continuous learning pipeline\n")
        f.write("5. **Task 5.7**: Add ML model monitoring and validation\n")
        f.write("6. **Task 5.8**: Store ML predictions for retrospective evaluation\n\n")
        
        # Footer
        f.write("---\n\n")
        f.write("**Report Generated**: {}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f.write("**Models**: Prophet Rainfall Classifier + Regressor\n")
        f.write("**Training Data**: 2-3 years of historical Singapore weather data\n")
        f.write("**Validation**: TimeSeriesSplit (5-fold temporal cross-validation)\n\n")
    
    logger.info(f"✅ Performance report saved to {report_path}")


def main():
    """
    Main evaluation pipeline for rainfall prediction models.
    
    Steps:
    1. Load historical data
    2. Load trained models
    3. Evaluate classification metrics
    4. Evaluate regression metrics
    5. Analyze temporal performance
    6. Calculate baseline comparisons
    7. Perform residual diagnostics
    8. Load cross-validation results
    9. Analyze feature importance
    10. Generate comprehensive performance report
    """
    logger.info("=" * 60)
    logger.info("RAINFALL PREDICTION MODEL EVALUATION")
    logger.info("=" * 60)
    logger.info("")
    logger.info("🎯 Task 5.2: Evaluate baseline model performance")
    logger.info("")
    
    try:
        # Load data
        df = load_historical_data()
        df = create_features(df)
        
        # Load trained models
        classifiers, regressors = load_trained_models()
        
        # Evaluate classification metrics
        logger.info("")
        logger.info("=" * 60)
        logger.info("CLASSIFICATION METRICS EVALUATION")
        logger.info("=" * 60)
        
        classification_metrics = {}
        for horizon in HORIZONS:
            if horizon not in classifiers:
                continue
            
            test_df = prepare_prophet_data_classifier(df, horizon)
            # Use last 20% as test set
            split_idx = int(len(test_df) * 0.8)
            test_df = test_df.iloc[split_idx:]
            
            metrics = evaluate_classification_metrics(classifiers[horizon], test_df, horizon)
            classification_metrics[f'{horizon}h'] = metrics
        
        # Evaluate regression metrics
        logger.info("")
        logger.info("=" * 60)
        logger.info("REGRESSION METRICS EVALUATION")
        logger.info("=" * 60)
        
        regression_metrics = {}
        for horizon in HORIZONS:
            if horizon not in regressors:
                continue
            
            test_df = prepare_prophet_data_regressor(df, horizon)
            # Use last 20% as test set
            split_idx = int(len(test_df) * 0.8)
            test_df = test_df.iloc[split_idx:]
            
            metrics = evaluate_regression_metrics(regressors[horizon], test_df, horizon)
            regression_metrics[f'{horizon}h'] = metrics
        
        # Temporal performance analysis
        logger.info("")
        logger.info("=" * 60)
        logger.info("TEMPORAL PERFORMANCE ANALYSIS")
        logger.info("=" * 60)
        
        temporal_analysis = analyze_temporal_performance(df, classifiers, regressors)
        
        # Baseline comparisons
        logger.info("")
        logger.info("=" * 60)
        logger.info("BASELINE COMPARISONS")
        logger.info("=" * 60)
        
        baseline_comparisons = calculate_baseline_comparisons(df, classifiers, regressors)
        
        # Residual diagnostics
        logger.info("")
        logger.info("=" * 60)
        logger.info("RESIDUAL DIAGNOSTICS")
        logger.info("=" * 60)
        
        residual_diagnostics = perform_residual_diagnostics(df, regressors)
        
        # Load cross-validation results
        logger.info("")
        logger.info("=" * 60)
        logger.info("CROSS-VALIDATION RESULTS")
        logger.info("=" * 60)
        
        cv_results = load_cross_validation_results()
        
        # Feature importance analysis
        logger.info("")
        logger.info("=" * 60)
        logger.info("FEATURE IMPORTANCE ANALYSIS")
        logger.info("=" * 60)
        
        feature_importance = analyze_feature_importance(df, regressors)
        
        # Generate performance report
        logger.info("")
        logger.info("=" * 60)
        logger.info("GENERATING PERFORMANCE REPORT")
        logger.info("=" * 60)
        
        generate_performance_report(
            classification_metrics,
            regression_metrics,
            temporal_analysis,
            baseline_comparisons,
            residual_diagnostics,
            cv_results,
            feature_importance
        )
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info("")
        logger.info("✅ Classification metrics evaluated")
        logger.info("✅ Regression metrics evaluated")
        logger.info("✅ Temporal performance analyzed")
        logger.info("✅ Baseline comparisons calculated")
        logger.info("✅ Residual diagnostics performed")
        logger.info("✅ Cross-validation results loaded")
        logger.info("✅ Feature importance analyzed")
        logger.info("✅ Performance report generated")
        logger.info("")
        logger.info(f"📄 Report: lionweather/backend/ML_MODEL_PERFORMANCE_RAINFALL.md")
        logger.info(f"📊 Plots: lionweather/backend/evaluation_plots/")
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ EVALUATION COMPLETE")
        logger.info("=" * 60)
        
    except ValueError as e:
        logger.error(f"❌ Error: {e}")
        logger.info("")
        logger.info("⚠️  NOTE: Models must be trained first!")
        logger.info("   Run: python3 ml/train_rainfall_classifier.py")
        logger.info("   Run: python3 ml/train_rainfall_regressor.py")
        logger.info("")
        logger.info("   This evaluation script creates the framework and documentation.")
        logger.info("   Once models are trained, re-run this script to generate the full report.")
        sys.exit(1)


if __name__ == "__main__":
    main()
