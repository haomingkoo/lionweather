"""Training data preparation for NEA-aligned rainfall classification.

This script extracts historical weather data, computes features, and labels data
for training the 4-model ensemble system.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from app.db.database import get_connection
from ml.data_validation import validate_training_data, check_data_completeness
from ml.feature_engineer import compute_all_features
from ml.nea_classification import label_training_data


def extract_historical_data(country: str = "singapore", 
                            min_observations: int = 1000,
                            source_filter: str = None) -> pd.DataFrame:
    """
    Extract historical weather data from database.
    
    Supports multi-station data from NEA historical imports.
    Each row includes station coordinates (latitude, longitude) for spatial features.
    
    Args:
        country: Country to extract data for
        min_observations: Minimum number of observations required
        source_filter: Optional filter for source_api (e.g., "data.gov.sg/nea" for NEA data only)
        
    Returns:
        DataFrame with historical weather observations including spatial coordinates
        
    Raises:
        ValueError: If insufficient data or mock data detected
    """
    print(f"Extracting historical data for {country}...")
    if source_filter:
        print(f"  Filtering for source: {source_filter}")
    
    con = get_connection()
    
    # Query weather_records table
    # Include latitude and longitude for spatial features
    query = """
        SELECT 
            timestamp,
            country,
            location,
            latitude,
            longitude,
            temperature,
            rainfall,
            humidity,
            wind_speed,
            wind_direction,
            pressure,
            weather_code,
            source_api,
            created_at
        FROM weather_records
        WHERE country = ?
    """
    
    params = [country]
    
    # Add source filter if specified
    if source_filter:
        query += " AND source_api LIKE ?"
        params.append(f"%{source_filter}%")
    
    query += " ORDER BY timestamp ASC, location ASC"
    
    df = pd.read_sql_query(query, con, params=params)
    con.close()
    
    print(f"✓ Extracted {len(df)} observations")
    
    # Show station breakdown if multi-station data
    if 'location' in df.columns:
        station_counts = df['location'].value_counts()
        if len(station_counts) > 1:
            print(f"  Multi-station data: {len(station_counts)} stations")
            print(f"  Stations: {', '.join(station_counts.head(10).index.tolist())}")
            if len(station_counts) > 10:
                print(f"  ... and {len(station_counts) - 10} more")
    
    # Check minimum sample size
    if len(df) < min_observations:
        raise ValueError(
            f"Insufficient data: {len(df)} observations "
            f"(minimum required: {min_observations})"
        )
    
    # Validate no mock data
    print("Validating data authenticity...")
    validate_training_data(df)
    
    # Check data completeness
    is_complete, warnings = check_data_completeness(df)
    if not is_complete:
        print("\nData completeness warnings:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print()
    
    return df


def filter_complete_observations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter for observations with complete critical features.
    
    Critical features: pressure, humidity, temperature, wind_speed
    
    Args:
        df: DataFrame with weather observations
        
    Returns:
        DataFrame with only complete observations
    """
    print("Filtering for complete observations...")
    
    initial_count = len(df)
    
    # Critical features that must not be missing
    critical_features = ['pressure', 'humidity', 'temperature', 'wind_speed']
    
    # Filter out rows with missing critical features
    for feature in critical_features:
        if feature in df.columns:
            df = df[df[feature].notna()]
    
    final_count = len(df)
    removed = initial_count - final_count
    
    print(f"✓ Filtered: {final_count} complete observations "
          f"({removed} removed due to missing critical features)")
    
    return df


def prepare_training_dataset(country: str = "singapore", 
                            source: str = None) -> pd.DataFrame:
    """
    Prepare complete training dataset with features and labels.
    
    This is the main entry point for training data preparation.
    Supports multi-station NEA historical data with spatial features.
    
    Steps:
    1. Extract historical data from database (optionally filtered by source)
    2. Filter for complete observations
    3. Compute all features (temporal, lagged, thunderstorm indicators, spatial)
    4. Label data with NEA rainfall classes
    
    Args:
        country: Country to prepare data for
        source: Optional source filter ("nea" for NEA data, "open-meteo" for Open-Meteo, None for all)
        
    Returns:
        DataFrame ready for model training with features and labels
    """
    print("=" * 80)
    print("PREPARING TRAINING DATASET FOR NEA-ALIGNED RAINFALL CLASSIFICATION")
    print("=" * 80)
    print()
    
    # Step 1: Extract historical data
    source_filter = None
    if source == "nea":
        source_filter = "data.gov.sg/nea"
        print("Using NEA historical data (multi-station)")
    elif source == "open-meteo":
        source_filter = "open-meteo.com"
        print("Using Open-Meteo historical data")
    else:
        print("Using all available historical data")
    
    df = extract_historical_data(country=country, source_filter=source_filter)
    
    # Step 2: Filter for complete observations
    df = filter_complete_observations(df)
    
    # Step 3: Compute all features (includes spatial features if available)
    print()
    print("Computing features...")
    df = compute_all_features(df)
    
    # Step 4: Label data with NEA classes
    print()
    print("Labeling data with NEA rainfall classes...")
    df = label_training_data(df)
    
    # Summary statistics
    print()
    print("=" * 80)
    print("TRAINING DATASET SUMMARY")
    print("=" * 80)
    print(f"Total observations: {len(df)}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Features: {len(df.columns)} columns")
    
    # Show spatial coverage if multi-station
    if 'latitude' in df.columns and 'longitude' in df.columns:
        unique_locations = df.groupby(['latitude', 'longitude']).size()
        if len(unique_locations) > 1:
            print(f"Spatial coverage: {len(unique_locations)} unique locations")
            print(f"  Latitude range: {df['latitude'].min():.4f} to {df['latitude'].max():.4f}")
            print(f"  Longitude range: {df['longitude'].min():.4f} to {df['longitude'].max():.4f}")
    
    print()
    
    # Check for class imbalance
    if 'rainfall_class' in df.columns:
        class_counts = df['rainfall_class'].value_counts().sort_index()
        print("Rainfall class distribution:")
        class_names = ["No Rain", "Light Showers", "Moderate Showers", 
                      "Heavy Showers", "Thundery Showers", "Very Heavy Rain"]
        for class_id, count in class_counts.items():
            if class_id < len(class_names):
                pct = count / len(df) * 100
                print(f"  Class {class_id} ({class_names[class_id]}): {count} ({pct:.1f}%)")
        
        min_class_count = class_counts.min()
        max_class_count = class_counts.max()
        imbalance_ratio = max_class_count / min_class_count if min_class_count > 0 else float('inf')
        
        if imbalance_ratio > 10:
            print()
            print(f"⚠ WARNING: Class imbalance detected (ratio: {imbalance_ratio:.1f}:1)")
            print("  Consider using stratified sampling or class weighting during training")
    
    print()
    print("✓ Training dataset preparation complete")
    print("=" * 80)
    
    return df


def save_training_dataset(df: pd.DataFrame, output_path: str = "training_data.csv"):
    """
    Save prepared training dataset to CSV file.
    
    Args:
        df: Prepared training dataset
        output_path: Path to save CSV file
    """
    df.to_csv(output_path, index=False)
    print(f"✓ Training dataset saved to {output_path}")


if __name__ == "__main__":
    import sys
    
    # Get source from command line argument
    # Usage: python prepare_training_data.py [nea|open-meteo]
    source = sys.argv[1] if len(sys.argv) > 1 else "nea"
    
    if source not in ["nea", "open-meteo", "all"]:
        print(f"Invalid source: {source}")
        print("Usage: python prepare_training_data.py [nea|open-meteo|all]")
        print("  nea: Use NEA historical data (multi-station)")
        print("  open-meteo: Use Open-Meteo historical data")
        print("  all: Use all available data")
        sys.exit(1)
    
    # Prepare training dataset
    df = prepare_training_dataset(country="singapore", source=source if source != "all" else None)
    
    # Save to file
    output_filename = f"ml/training_data_{source}.csv"
    save_training_dataset(df, output_filename)
