"""Feature engineering for NEA-aligned rainfall classification.

This module computes all features needed for multi-class classification,
including thunderstorm indicators, temporal features, and lagged values.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any


def get_lagged_value(df: pd.DataFrame, column: str, hours_ago: int, 
                     current_idx: int) -> Optional[float]:
    """
    Get value from N hours ago for a specific observation.
    
    Args:
        df: DataFrame with timestamp column
        column: Column name to get lagged value from
        hours_ago: Number of hours to look back
        current_idx: Current row index
        
    Returns:
        Value from N hours ago, or None if not available
    """
    if current_idx < hours_ago:
        return None
    
    # Simple approach: look back N rows (assumes hourly data)
    lag_idx = current_idx - hours_ago
    if lag_idx >= 0 and lag_idx < len(df):
        value = df.iloc[lag_idx][column]
        if pd.notna(value):
            return float(value)
    
    return None


def compute_thunderstorm_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute thunderstorm indicator features for each observation.
    
    Features computed:
    - pressure_drop_3h: Pressure change over 3 hours (hPa)
    - humidity_change_1h: Humidity change over 1 hour (%)
    - temperature_drop_1h: Temperature change over 1 hour (°C)
    - wind_direction_change_1h: Wind direction change over 1 hour (degrees)
    - afternoon_period: Binary flag for 14:00-18:00 local time
    - wind_from_west: Binary flag for westerly winds (225-315°)
    
    Args:
        df: DataFrame with weather observations
        
    Returns:
        DataFrame with added thunderstorm indicator features
    """
    df = df.copy()
    
    # Ensure timestamp is datetime
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Initialize feature columns
    df['pressure_drop_3h'] = 0.0
    df['humidity_change_1h'] = 0.0
    df['temperature_drop_1h'] = 0.0
    df['wind_direction_change_1h'] = 0.0
    df['afternoon_period'] = 0
    df['wind_from_west'] = 0
    
    # Compute lagged features for each row
    for idx in range(len(df)):
        # Pressure drop over 3 hours
        if 'pressure' in df.columns:
            pressure_3h_ago = get_lagged_value(df, 'pressure', 3, idx)
            if pressure_3h_ago is not None:
                current_pressure = df.iloc[idx]['pressure']
                if pd.notna(current_pressure):
                    df.at[idx, 'pressure_drop_3h'] = pressure_3h_ago - current_pressure
        
        # Humidity change over 1 hour
        if 'humidity' in df.columns:
            humidity_1h_ago = get_lagged_value(df, 'humidity', 1, idx)
            if humidity_1h_ago is not None:
                current_humidity = df.iloc[idx]['humidity']
                if pd.notna(current_humidity):
                    df.at[idx, 'humidity_change_1h'] = current_humidity - humidity_1h_ago
        
        # Temperature drop over 1 hour
        if 'temperature' in df.columns:
            temp_1h_ago = get_lagged_value(df, 'temperature', 1, idx)
            if temp_1h_ago is not None:
                current_temp = df.iloc[idx]['temperature']
                if pd.notna(current_temp):
                    df.at[idx, 'temperature_drop_1h'] = temp_1h_ago - current_temp
        
        # Wind direction change over 1 hour (handle 360° wrap-around)
        if 'wind_direction' in df.columns:
            wind_dir_1h_ago = get_lagged_value(df, 'wind_direction', 1, idx)
            if wind_dir_1h_ago is not None:
                current_wind_dir = df.iloc[idx]['wind_direction']
                if pd.notna(current_wind_dir):
                    dir_change = abs(current_wind_dir - wind_dir_1h_ago)
                    # Handle wrap-around (e.g., 350° to 10° is 20°, not 340°)
                    dir_change = min(dir_change, 360 - dir_change)
                    df.at[idx, 'wind_direction_change_1h'] = dir_change
        
        # Afternoon period (14:00-18:00 Singapore time)
        hour = df.iloc[idx]['timestamp'].hour
        df.at[idx, 'afternoon_period'] = 1 if 14 <= hour <= 18 else 0
        
        # Wind from west (225-315°)
        if 'wind_direction' in df.columns:
            wind_dir = df.iloc[idx]['wind_direction']
            if pd.notna(wind_dir):
                df.at[idx, 'wind_from_west'] = 1 if 225 <= wind_dir <= 315 else 0
    
    return df


def compute_lagged_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute lagged rainfall features.
    
    Features computed:
    - rainfall_lag_1h: Rainfall 1 hour ago
    - rainfall_lag_3h: Rainfall 3 hours ago
    - rainfall_lag_6h: Rainfall 6 hours ago
    - rainfall_lag_24h: Rainfall 24 hours ago
    
    Args:
        df: DataFrame with rainfall observations
        
    Returns:
        DataFrame with added lagged features
    """
    df = df.copy()
    
    if 'rainfall' not in df.columns:
        raise ValueError("DataFrame must have 'rainfall' column")
    
    # Ensure sorted by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Initialize lagged feature columns
    df['rainfall_lag_1h'] = 0.0
    df['rainfall_lag_3h'] = 0.0
    df['rainfall_lag_6h'] = 0.0
    df['rainfall_lag_24h'] = 0.0
    
    # Compute lagged features for each row
    for idx in range(len(df)):
        for lag_hours, col_name in [
            (1, 'rainfall_lag_1h'),
            (3, 'rainfall_lag_3h'),
            (6, 'rainfall_lag_6h'),
            (24, 'rainfall_lag_24h')
        ]:
            lagged_value = get_lagged_value(df, 'rainfall', lag_hours, idx)
            if lagged_value is not None:
                df.at[idx, col_name] = lagged_value
    
    return df


def compute_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute temporal features for time series modeling.
    
    Features computed:
    - hour_sin, hour_cos: Cyclical encoding of hour (0-23)
    - day_sin, day_cos: Cyclical encoding of day of year (1-365)
    - month: Month (1-12)
    - is_ne_monsoon: Binary flag for NE monsoon season (Nov-Jan)
    - is_sw_monsoon: Binary flag for SW monsoon season (May-Sep)
    
    Args:
        df: DataFrame with timestamp column
        
    Returns:
        DataFrame with added temporal features
    """
    df = df.copy()
    
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Extract time components
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_year'] = df['timestamp'].dt.dayofyear
    df['month'] = df['timestamp'].dt.month
    
    # Cyclical encoding for hour (0-23)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Cyclical encoding for day of year (1-365)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    
    # Monsoon season flags
    # NE Monsoon: November to January (months 11, 12, 1)
    df['is_ne_monsoon'] = df['month'].isin([11, 12, 1]).astype(int)
    
    # SW Monsoon: May to September (months 5, 6, 7, 8, 9)
    df['is_sw_monsoon'] = df['month'].isin([5, 6, 7, 8, 9]).astype(int)
    
    # Drop intermediate columns
    df = df.drop(columns=['hour', 'day_of_year'], errors='ignore')
    
    return df


def compute_spatial_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute spatial features for location-aware predictions.
    
    Features computed:
    - latitude: Station latitude (raw coordinate)
    - longitude: Station longitude (raw coordinate)
    - distance_from_center: Distance from Singapore center (1.3521, 103.8198) in km
    - is_coastal: Binary flag for coastal stations (within 2km of coast)
    
    Args:
        df: DataFrame with latitude and longitude columns
        
    Returns:
        DataFrame with added spatial features
    """
    df = df.copy()
    
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print("⚠ Warning: No latitude/longitude columns found, skipping spatial features")
        return df
    
    # Singapore center coordinates (Orchard/CBD area)
    CENTER_LAT = 1.3521
    CENTER_LON = 103.8198
    
    # Compute distance from center using Haversine formula
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = np.sin(delta_lat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c
    
    df['distance_from_center'] = df.apply(
        lambda row: haversine_distance(CENTER_LAT, CENTER_LON, row['latitude'], row['longitude']),
        axis=1
    )
    
    # Coastal detection (Singapore is small, so coastal = within 2km of edges)
    # Approximate Singapore bounds: lat 1.15-1.47, lon 103.6-104.0
    # Coastal if near any edge
    df['is_coastal'] = (
        (df['latitude'] < 1.20) |  # South coast
        (df['latitude'] > 1.45) |  # North coast (Johor Strait)
        (df['longitude'] < 103.65) |  # West coast
        (df['longitude'] > 103.95)  # East coast (Changi)
    ).astype(int)
    
    print(f"✓ Spatial features computed: {df['latitude'].nunique()} unique locations")
    
    return df


def compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all features for ML training/prediction.
    
    This is the main entry point for feature engineering.
    Includes spatial features (latitude, longitude) for location-aware predictions.
    
    Args:
        df: DataFrame with raw weather observations
        
    Returns:
        DataFrame with all computed features
    """
    print("Computing temporal features...")
    df = compute_temporal_features(df)
    
    print("Computing lagged features...")
    df = compute_lagged_features(df)
    
    print("Computing thunderstorm indicator features...")
    df = compute_thunderstorm_features(df)
    
    print("Computing spatial features...")
    df = compute_spatial_features(df)
    
    print(f"✓ Feature engineering complete: {len(df)} observations, {len(df.columns)} features")
    
    return df


def get_feature_columns() -> list:
    """
    Get list of all feature column names for model training.
    
    Returns:
        List of feature column names
    """
    base_features = [
        'temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction'
    ]
    
    spatial_features = [
        'latitude', 'longitude', 'distance_from_center', 'is_coastal'
    ]
    
    temporal_features = [
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos', 'month',
        'is_ne_monsoon', 'is_sw_monsoon'
    ]
    
    lagged_features = [
        'rainfall_lag_1h', 'rainfall_lag_3h', 'rainfall_lag_6h', 'rainfall_lag_24h'
    ]
    
    thunderstorm_features = [
        'pressure_drop_3h', 'humidity_change_1h', 'temperature_drop_1h',
        'wind_direction_change_1h', 'afternoon_period', 'wind_from_west'
    ]
    
    return base_features + spatial_features + temporal_features + lagged_features + thunderstorm_features
