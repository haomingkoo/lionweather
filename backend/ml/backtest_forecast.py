"""Backtest rainfall forecasts against historical data and NEA predictions.

This module performs honest evaluation of our forecasting models by:
1. Predicting N hours ahead (not current conditions)
2. Comparing against actual observed rainfall
3. Benchmarking against NEA's official forecasts
4. Testing ensemble (our model + NEA) performance
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.db.database import get_connection
from ml.nea_classification import classify_rainfall, NEA_CLASS_NAMES
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
import json


def load_nea_forecasts(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load NEA forecast data from database.
    
    Args:
        start_date: Start date for evaluation period
        end_date: End date for evaluation period
        
    Returns:
        DataFrame with NEA forecasts
    """
    con = get_connection()
    
    query = """
        SELECT 
            prediction_time,
            target_time_start,
            target_time_end,
            temperature_low,
            temperature_high,
            humidity_low,
            humidity_high,
            wind_speed_low,
            wind_speed_high,
            forecast_description
        FROM forecast_data
        WHERE country = 'singapore'
        AND prediction_time >= ?
        AND prediction_time <= ?
        ORDER BY prediction_time, target_time_start
    """
    
    df = pd.read_sql_query(query, con, params=(start_date, end_date))
    con.close()
    
    return df


def load_actual_observations(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load actual observed weather data from database.
    
    Args:
        start_date: Start date for evaluation period
        end_date: End date for evaluation period
        
    Returns:
        DataFrame with actual observations
    """
    con = get_connection()
    
    query = """
        SELECT 
            timestamp,
            temperature,
            rainfall,
            humidity,
            wind_speed,
            wind_direction,
            pressure,
            weather_code
        FROM weather_records
        WHERE country = 'singapore'
        AND timestamp >= ?
        AND timestamp <= ?
        ORDER BY timestamp
    """
    
    df = pd.read_sql_query(query, con, params=(start_date, end_date))
    con.close()
    
    return df


def parse_nea_forecast_to_rainfall_class(forecast_desc: str) -> int:
    """
    Parse NEA forecast description to rainfall class.
    
    NEA uses descriptions like:
    - "Fair", "Partly Cloudy" -> No Rain (0)
    - "Cloudy", "Light Rain" -> Light Showers (1)
    - "Showers", "Rain" -> Moderate Showers (2)
    - "Heavy Showers", "Heavy Rain" -> Heavy Showers (3)
    - "Thundery Showers" -> Thundery Showers (4)
    
    Args:
        forecast_desc: NEA forecast description text
        
    Returns:
        NEA rainfall class ID (0-5)
    """
    if pd.isna(forecast_desc):
        return 0
    
    desc_lower = forecast_desc.lower()
    
    # Thundery showers (highest priority)
    if 'thunder' in desc_lower:
        return 4
    
    # Heavy rain
    if 'heavy' in desc_lower:
        return 3
    
    # Moderate rain/showers
    if 'shower' in desc_lower or 'rain' in desc_lower:
        if 'light' in desc_lower:
            return 1
        return 2
    
    # Cloudy but no rain
    if 'cloud' in desc_lower or 'overcast' in desc_lower:
        return 0
    
    # Fair/clear
    return 0


def backtest_model_forecast(model_data: dict, 
                            test_df: pd.DataFrame,
                            horizon: int) -> pd.DataFrame:
    """
    Generate model forecasts for backtesting.
    
    Args:
        model_data: Loaded model with class_mapping and feature_names
        test_df: Test dataset with features
        horizon: Forecast horizon in hours
        
    Returns:
        DataFrame with predictions
    """
    model = model_data['model']
    reverse_mapping = model_data['reverse_mapping']
    feature_names = model_data['feature_names']
    
    # Prepare features
    X = test_df[feature_names].values
    
    # Predict
    y_pred_mapped = model.predict(X)
    y_pred_proba = model.predict_proba(X)
    
    # Remap to NEA classes
    y_pred = np.array([reverse_mapping[c] for c in y_pred_mapped])
    
    # Create results dataframe
    results = pd.DataFrame({
        'timestamp': test_df['timestamp'],
        'forecast_timestamp': pd.to_datetime(test_df['timestamp']) + pd.Timedelta(hours=horizon),
        'predicted_class': y_pred,
        'predicted_class_name': [NEA_CLASS_NAMES[c] for c in y_pred],
        'confidence': [y_pred_proba[i].max() for i in range(len(y_pred_proba))]
    })
    
    return results


def match_forecasts_to_actuals(forecasts: pd.DataFrame, 
                               actuals: pd.DataFrame,
                               time_tolerance_hours: int = 1) -> pd.DataFrame:
    """
    Match forecast predictions to actual observations.
    
    Args:
        forecasts: DataFrame with forecast_timestamp and predicted_class
        actuals: DataFrame with timestamp and actual rainfall
        time_tolerance_hours: Allow matching within N hours
        
    Returns:
        DataFrame with matched forecast-actual pairs
    """
    matched = []
    
    actuals['timestamp'] = pd.to_datetime(actuals['timestamp'])
    forecasts['forecast_timestamp'] = pd.to_datetime(forecasts['forecast_timestamp'])
    
    for _, forecast_row in forecasts.iterrows():
        target_time = forecast_row['forecast_timestamp']
        
        # Find actual observation within tolerance window
        time_diff = (actuals['timestamp'] - target_time).abs()
        closest_idx = time_diff.idxmin()
        
        if time_diff[closest_idx] <= pd.Timedelta(hours=time_tolerance_hours):
            actual_row = actuals.loc[closest_idx]
            
            # Classify actual rainfall
            actual_class = classify_rainfall(
                actual_row['rainfall'],
                0.0  # No thunderstorm detection for actuals
            )
            
            matched.append({
                'forecast_time': forecast_row.get('timestamp', target_time),
                'target_time': target_time,
                'actual_time': actual_row['timestamp'],
                'predicted_class': forecast_row['predicted_class'],
                'actual_class': actual_class,
                'actual_rainfall': actual_row['rainfall'],
                'confidence': forecast_row.get('confidence', None)
            })
    
    return pd.DataFrame(matched)


def evaluate_forecast_performance(matched_df: pd.DataFrame, 
                                  model_name: str) -> dict:
    """
    Calculate comprehensive forecast performance metrics.
    
    Args:
        matched_df: DataFrame with predicted_class and actual_class
        model_name: Name of the model being evaluated
        
    Returns:
        Dictionary with performance metrics
    """
    y_true = matched_df['actual_class'].values
    y_pred = matched_df['predicted_class'].values
    
    # Overall metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, average='weighted', zero_division=0
    )
    
    # Binary rain detection (rain vs no rain)
    y_true_binary = (y_true > 0).astype(int)
    y_pred_binary = (y_pred > 0).astype(int)
    
    rain_accuracy = accuracy_score(y_true_binary, y_pred_binary)
    rain_precision, rain_recall, rain_f1, _ = precision_recall_fscore_support(
        y_true_binary, y_pred_binary, average='binary', zero_division=0
    )
    
    # Per-class metrics
    per_class_precision, per_class_recall, per_class_f1, per_class_support = \
        precision_recall_fscore_support(y_true, y_pred, average=None, zero_division=0)
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    
    return {
        'model_name': model_name,
        'samples': len(matched_df),
        'overall_accuracy': float(accuracy),
        'weighted_precision': float(precision),
        'weighted_recall': float(recall),
        'weighted_f1': float(f1),
        'rain_detection_accuracy': float(rain_accuracy),
        'rain_precision': float(rain_precision),
        'rain_recall': float(rain_recall),
        'rain_f1': float(rain_f1),
        'per_class_metrics': {
            int(class_id): {
                'precision': float(per_class_precision[class_id]),
                'recall': float(per_class_recall[class_id]),
                'f1': float(per_class_f1[class_id]),
                'support': int(per_class_support[class_id])
            }
            for class_id in range(len(per_class_precision))
            if per_class_support[class_id] > 0
        },
        'confusion_matrix': cm.tolist()
    }


def create_ensemble_forecast(our_predictions: pd.DataFrame,
                             nea_predictions: pd.DataFrame,
                             our_weight: float = 0.5) -> pd.DataFrame:
    """
    Create ensemble forecast combining our model and NEA predictions.
    
    Args:
        our_predictions: Our model predictions
        nea_predictions: NEA forecast predictions
        our_weight: Weight for our model (0.0-1.0), NEA gets (1-our_weight)
        
    Returns:
        DataFrame with ensemble predictions
    """
    # Merge on forecast timestamp
    merged = pd.merge(
        our_predictions,
        nea_predictions,
        on='forecast_timestamp',
        suffixes=('_our', '_nea'),
        how='inner'
    )
    
    # Ensemble: weighted average of class predictions
    # If classes differ significantly, use the one with higher confidence
    ensemble_class = []
    
    for _, row in merged.iterrows():
        our_class = row['predicted_class_our']
        nea_class = row['predicted_class_nea']
        our_conf = row.get('confidence_our', 0.5)
        
        # If both agree, use that class
        if our_class == nea_class:
            ensemble_class.append(our_class)
        else:
            # Weight by confidence and model weight
            if our_conf * our_weight > (1 - our_weight):
                ensemble_class.append(our_class)
            else:
                ensemble_class.append(nea_class)
    
    merged['predicted_class'] = ensemble_class
    merged['predicted_class_name'] = [NEA_CLASS_NAMES[c] for c in ensemble_class]
    
    return merged[['timestamp_our', 'forecast_timestamp', 'predicted_class', 'predicted_class_name']]


def run_comprehensive_backtest(model_path: str,
                               test_start: str,
                               test_end: str,
                               horizon: int = 3) -> dict:
    """
    Run comprehensive backtest comparing our model, NEA, and ensemble.
    
    Args:
        model_path: Path to trained model
        test_start: Start date for test period
        test_end: End date for test period
        horizon: Forecast horizon in hours
        
    Returns:
        Dictionary with all results
    """
    import joblib
    
    print("=" * 80)
    print(f"COMPREHENSIVE FORECAST BACKTEST - {horizon}H AHEAD")
    print("=" * 80)
    print()
    
    # Load model
    print("Loading trained model...")
    model_data = joblib.load(model_path)
    print("✓ Model loaded")
    print()
    
    # Load actual observations
    print("Loading actual observations...")
    actuals = load_actual_observations(test_start, test_end)
    print(f"✓ Loaded {len(actuals)} actual observations")
    print()
    
    # Load NEA forecasts
    print("Loading NEA forecasts...")
    nea_forecasts_raw = load_nea_forecasts(test_start, test_end)
    print(f"✓ Loaded {len(nea_forecasts_raw)} NEA forecasts")
    print()
    
    # TODO: Generate our model forecasts
    # This requires preparing test data with features
    print("⚠ Model forecast generation not yet implemented")
    print("  Need to prepare test features and generate predictions")
    print()
    
    # Parse NEA forecasts
    print("Parsing NEA forecasts...")
    nea_forecasts = pd.DataFrame({
        'timestamp': pd.to_datetime(nea_forecasts_raw['prediction_time']),
        'forecast_timestamp': pd.to_datetime(nea_forecasts_raw['target_time_start']),
        'predicted_class': nea_forecasts_raw['forecast_description'].apply(parse_nea_forecast_to_rainfall_class),
        'predicted_class_name': nea_forecasts_raw['forecast_description'].apply(
            lambda x: NEA_CLASS_NAMES[parse_nea_forecast_to_rainfall_class(x)]
        )
    })
    print(f"✓ Parsed {len(nea_forecasts)} NEA forecasts")
    print()
    
    # Match NEA forecasts to actuals
    print("Matching NEA forecasts to actual observations...")
    nea_matched = match_forecasts_to_actuals(nea_forecasts, actuals)
    print(f"✓ Matched {len(nea_matched)} forecast-actual pairs")
    print()
    
    # Evaluate NEA performance
    print("Evaluating NEA forecast performance...")
    nea_results = evaluate_forecast_performance(nea_matched, "NEA Official Forecast")
    print(f"✓ NEA Accuracy: {nea_results['overall_accuracy']:.3f}")
    print(f"✓ NEA Rain F1: {nea_results['rain_f1']:.3f}")
    print()
    
    return {
        'horizon': horizon,
        'test_period': {'start': test_start, 'end': test_end},
        'nea_performance': nea_results,
        'our_performance': None,  # TODO: Implement
        'ensemble_performance': None  # TODO: Implement
    }


def save_backtest_results(results: dict, output_path: str = "ml/BACKTEST_RESULTS.json"):
    """
    Save backtest results to JSON file.
    
    Args:
        results: Backtest results dictionary
        output_path: Path to save results
    """
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Results saved to {output_path}")


if __name__ == "__main__":
    # Run backtest on validation period
    results = run_comprehensive_backtest(
        model_path="ml/models/multiclass_classifier_v2.pkl",
        test_start="2026-02-18",
        test_end="2026-03-08",
        horizon=3
    )
    
    save_backtest_results(results)
