"""Create forecast targets for time series prediction.

This module creates training data where features at time T are used to predict
rainfall at time T+N hours (where N = 1, 3, 6, 12, or 24 hours ahead).
"""

import pandas as pd
import numpy as np
from typing import List


def create_forecast_dataset(df: pd.DataFrame, 
                            forecast_horizons: List[int] = [1, 3, 6, 12, 24]) -> dict:
    """
    Create forecast datasets for multiple time horizons.
    
    For each horizon H, creates a dataset where:
    - Features at time T are used to predict
    - Rainfall class at time T+H hours
    
    Args:
        df: DataFrame with features and current rainfall labels
        forecast_horizons: List of hours ahead to forecast (e.g., [1, 3, 6, 12, 24])
        
    Returns:
        Dictionary mapping horizon -> forecast dataset
    """
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    forecast_datasets = {}
    
    for horizon in forecast_horizons:
        print(f"Creating forecast dataset for {horizon}h ahead...")
        
        # Shift target labels forward by horizon hours
        # This means: features at row i predict target at row i+horizon
        df_forecast = df.copy()
        
        # Shift all target columns forward
        df_forecast['target_rainfall'] = df['rainfall'].shift(-horizon)
        df_forecast['target_rainfall_class'] = df['rainfall_class'].shift(-horizon)
        df_forecast['target_thunderstorm_present'] = df['thunderstorm_present'].shift(-horizon)
        
        if 'weather_code' in df.columns:
            df_forecast['target_weather_code'] = df['weather_code'].shift(-horizon)
        
        # Remove rows where we don't have future data
        df_forecast = df_forecast.dropna(subset=['target_rainfall', 'target_rainfall_class'])
        
        # Calculate actual forecast time
        df_forecast['forecast_timestamp'] = pd.to_datetime(df_forecast['timestamp']) + pd.Timedelta(hours=horizon)
        
        print(f"  ✓ Created {len(df_forecast)} samples for {horizon}h forecast")
        print(f"    Predicting from {df_forecast['timestamp'].min()} to {df_forecast['forecast_timestamp'].max()}")
        
        forecast_datasets[horizon] = df_forecast
    
    return forecast_datasets


def evaluate_forecast_vs_persistence(df_forecast: pd.DataFrame, horizon: int) -> dict:
    """
    Compare forecast against persistence baseline.
    
    Persistence baseline: assume weather at T+H will be same as weather at T.
    
    Args:
        df_forecast: Forecast dataset with current and target labels
        horizon: Forecast horizon in hours
        
    Returns:
        Dictionary with persistence baseline metrics
    """
    # Persistence prediction: current class = future class
    persistence_pred = df_forecast['rainfall_class'].values
    actual = df_forecast['target_rainfall_class'].values
    
    # Calculate accuracy
    persistence_accuracy = (persistence_pred == actual).mean()
    
    # Rain detection (binary: rain vs no rain)
    persistence_rain = (persistence_pred > 0).astype(int)
    actual_rain = (actual > 0).astype(int)
    
    # True positives, false positives, false negatives
    tp = ((persistence_rain == 1) & (actual_rain == 1)).sum()
    fp = ((persistence_rain == 1) & (actual_rain == 0)).sum()
    fn = ((persistence_rain == 0) & (actual_rain == 1)).sum()
    tn = ((persistence_rain == 0) & (actual_rain == 0)).sum()
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'horizon': horizon,
        'accuracy': persistence_accuracy,
        'rain_precision': precision,
        'rain_recall': recall,
        'rain_f1': f1,
        'samples': len(df_forecast)
    }


def print_forecast_summary(forecast_datasets: dict):
    """
    Print summary of forecast datasets.
    
    Args:
        forecast_datasets: Dictionary mapping horizon -> forecast dataset
    """
    print()
    print("=" * 80)
    print("FORECAST DATASET SUMMARY")
    print("=" * 80)
    
    for horizon in sorted(forecast_datasets.keys()):
        df = forecast_datasets[horizon]
        
        print(f"\n{horizon}h Forecast:")
        print(f"  Samples: {len(df)}")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"  Forecast range: {df['forecast_timestamp'].min()} to {df['forecast_timestamp'].max()}")
        
        # Class distribution in targets
        print(f"  Target class distribution:")
        class_counts = df['target_rainfall_class'].value_counts().sort_index()
        for class_id, count in class_counts.items():
            pct = (count / len(df)) * 100
            print(f"    Class {int(class_id)}: {count} ({pct:.1f}%)")
        
        # Persistence baseline
        baseline = evaluate_forecast_vs_persistence(df, horizon)
        print(f"  Persistence baseline (assume no change):")
        print(f"    Accuracy: {baseline['accuracy']:.3f}")
        print(f"    Rain F1: {baseline['rain_f1']:.3f}")
    
    print()
    print("=" * 80)
