#!/usr/bin/env python3
"""
Initial ML Model Training Script

This script trains ARIMA, SARIMA, and Prophet models on collected weather data.
It should be run after sufficient data has been collected (>1000 records).

Usage:
    python train_initial_models.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.data_store import DataStore
from app.ml.training_pipeline import TrainingPipeline
from app.ml.feature_engineer import FeatureEngineer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main training function"""
    logger.info("=" * 60)
    logger.info("STARTING ML MODEL TRAINING")
    logger.info("=" * 60)
    
    # Initialize services
    data_store = DataStore()
    training_pipeline = TrainingPipeline(model_dir="models")
    feature_engineer = FeatureEngineer()
    
    # Load weather data from database
    logger.info("Loading weather data from database...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Fetch Malaysia data (currently the only country with data)
    records = data_store.get_records_by_date_range(
        start_date=start_date,
        end_date=end_date,
        country="malaysia"
    )
    
    logger.info(f"Loaded {len(records)} weather records")
    
    if len(records) < 100:
        logger.error(f"Insufficient data for training. Need at least 100 records, got {len(records)}")
        logger.info("Please wait for more data to be collected before training.")
        return
    
    # Convert to DataFrame
    logger.info("Converting records to DataFrame...")
    data = []
    for record in records:
        data.append({
            'timestamp': record.timestamp,
            'temperature': record.temperature,
            'rainfall': record.rainfall,
            'humidity': record.humidity,
            'wind_speed': record.wind_speed,
            'location': record.location
        })
    
    df = pd.DataFrame(data)
    df = df.sort_values('timestamp')
    df = df.set_index('timestamp')
    
    logger.info(f"DataFrame shape: {df.shape}")
    logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
    logger.info(f"Columns: {list(df.columns)}")
    
    # Check data quality
    logger.info("\nData Quality Check:")
    logger.info(f"  Temperature: {df['temperature'].notna().sum()}/{len(df)} non-null ({df['temperature'].notna().mean()*100:.1f}%)")
    logger.info(f"  Rainfall: {df['rainfall'].notna().sum()}/{len(df)} non-null ({df['rainfall'].notna().mean()*100:.1f}%)")
    logger.info(f"  Humidity: {df['humidity'].notna().sum()}/{len(df)} non-null ({df['humidity'].notna().mean()*100:.1f}%)")
    logger.info(f"  Wind Speed: {df['wind_speed'].notna().sum()}/{len(df)} non-null ({df['wind_speed'].notna().mean()*100:.1f}%)")
    
    # Train models for temperature (most complete data)
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING MODELS FOR TEMPERATURE")
    logger.info("=" * 60)
    
    # Prepare temperature data
    temp_df = df[['temperature']].dropna()
    logger.info(f"Temperature data: {len(temp_df)} records")
    
    if len(temp_df) < 50:
        logger.error("Insufficient temperature data for training")
        return
    
    # Train models
    try:
        all_metadata = training_pipeline.run_full_pipeline(
            df=temp_df,
            weather_params=['temperature']
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trained {len(all_metadata)} models:")
        for metadata in all_metadata:
            logger.info(f"  - {metadata.model_type.upper()}: MAE={metadata.validation_mae:.4f}, RMSE={metadata.validation_rmse:.4f}, MAPE={metadata.validation_mape:.2f}%")
            logger.info(f"    Saved to: {metadata.model_file_path}")
        
        # Find best model
        best_model = min(all_metadata, key=lambda m: m.validation_mae)
        logger.info(f"\n🏆 Best Model: {best_model.model_type.upper()} (MAE={best_model.validation_mae:.4f})")
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return
    
    logger.info("\n✓ Training script completed successfully")


if __name__ == "__main__":
    main()
