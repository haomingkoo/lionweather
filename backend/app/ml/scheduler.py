"""
Automated Training Scheduler for ML Weather Forecasting

Schedules weekly model retraining and evaluation.
"""

import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .training_pipeline import TrainingPipeline
from ..services.data_store import DataStore

logger = logging.getLogger(__name__)


class TrainingScheduler:
    """
    Automated training scheduler.
    
    Runs weekly training on Sunday at 2 AM.
    """
    
    def __init__(self):
        """Initialize TrainingScheduler."""
        self.scheduler = AsyncIOScheduler()
        self.training_pipeline = TrainingPipeline()
        self.data_store = DataStore()
    
    async def run_training_job(self):
        """
        Run weekly training job.
        
        Requirements: 11.1
        """
        try:
            logger.info("Starting weekly training job")
            
            # Get last 2 years of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            
            # DATA LEAKAGE PREVENTION: Only query weather_records table (current observations)
            # NEVER query forecast_data table - that would leak future information into training
            records = await self.data_store.get_records_by_date_range(start_date, end_date)
            
            if not records:
                logger.warning("No training data available")
                return
            
            # Convert to DataFrame
            import pandas as pd
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'temperature': r.temperature,
                'rainfall': r.rainfall,
                'humidity': r.humidity,
                'wind_speed': r.wind_speed
            } for r in records])
            df.set_index('timestamp', inplace=True)
            
            # Train models
            metadata_list = self.training_pipeline.run_full_pipeline(df)
            
            logger.info(f"Training completed. Trained {len(metadata_list)} models")
            
            # Evaluate and promote models
            await self.evaluate_and_promote_models(metadata_list)
            
        except Exception as e:
            logger.error(f"Training job failed: {e}")
    
    async def evaluate_and_promote_models(self, metadata_list):
        """
        Evaluate new models and promote if better than current production.
        
        Requirements: 11.2, 11.3, 11.4
        """
        for metadata in metadata_list:
            # Compare with current production model
            # If new model has lower MAE, promote it
            # This is a simplified implementation
            logger.info(f"Evaluating model {metadata.model_id}")
            
            # TODO: Implement actual comparison logic
            # For now, just log
            logger.info(f"Model {metadata.model_id} MAE: {metadata.validation_mae}")
    
    def start(self):
        """Start the scheduler."""
        # Schedule weekly training on Sunday at 2 AM
        self.scheduler.add_job(
            self.run_training_job,
            CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='weekly_training',
            name='Weekly Model Training',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Training scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Training scheduler stopped")
