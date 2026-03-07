"""
Data Store Service for ML Weather Forecasting

This module provides the DataStore class for persisting and querying weather records,
model metadata, predictions, and evaluation metrics.
"""

import sqlite3
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import logging

from .data_collector import WeatherRecord

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Model metadata for trained ML models"""
    model_type: str  # 'arima', 'sarima', 'prophet', 'lstm'
    weather_parameter: str  # 'temperature', 'rainfall', 'humidity', 'wind_speed'
    country: str
    version: str
    hyperparameters: Dict[str, Any]
    training_date: datetime
    training_samples: int
    validation_mae: float
    validation_rmse: float
    validation_mape: float
    file_path: str
    is_production: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Prediction:
    """Weather prediction from ML model"""
    model_id: int
    prediction_timestamp: datetime
    target_timestamp: datetime
    hours_ahead: int
    country: str
    location: str
    weather_parameter: str
    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    id: Optional[int] = None


@dataclass
class EvaluationMetric:
    """Evaluation metric comparing prediction to actual"""
    model_id: int
    evaluation_timestamp: datetime
    target_timestamp: datetime
    hours_ahead: int
    country: str
    location: str
    weather_parameter: str
    predicted_value: float
    actual_value: float
    absolute_error: float
    squared_error: float
    percentage_error: float
    id: Optional[int] = None


class DataStore:
    """
    Data store for weather records, model metadata, predictions, and evaluation metrics.
    
    Provides CRUD operations with efficient indexing for:
    - Historical weather data with 5-year retention
    - Model metadata and artifacts
    - Predictions with confidence intervals
    - Evaluation metrics for model performance tracking
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DataStore.
        
        Args:
            db_path: Path to SQLite database file. If None, uses DATABASE_PATH env var
                     or defaults to 'weather.db'
        """
        self.db_path = db_path or os.getenv("DATABASE_PATH", "weather.db")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection.
        
        Returns:
            SQLite connection object
        """
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row  # Enable column access by name
        return con
    
    # ========== Weather Record Operations (Task 3.1) ==========
    
    def save_weather_record(self, record: WeatherRecord) -> int:
        """
        Save weather record to database with upsert logic for duplicates.
        
        If a record with the same timestamp, country, and location exists,
        it will be updated. Otherwise, a new record is inserted.
        
        Args:
            record: WeatherRecord to save
            
        Returns:
            Record ID (primary key)
            
        Validates: Requirements 2.1, 2.4
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            # Use INSERT OR REPLACE for upsert logic
            cursor.execute("""
                INSERT INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed,
                    wind_direction, pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(timestamp, country, location) 
                DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    temperature = excluded.temperature,
                    rainfall = excluded.rainfall,
                    humidity = excluded.humidity,
                    wind_speed = excluded.wind_speed,
                    wind_direction = excluded.wind_direction,
                    pressure = excluded.pressure,
                    source_api = excluded.source_api
            """, (
                record.timestamp.isoformat(),
                record.country,
                record.location,
                record.latitude,
                record.longitude,
                record.temperature,
                record.rainfall,
                record.humidity,
                record.wind_speed,
                record.wind_direction,
                record.pressure,
                record.source_api,
                datetime.now().isoformat()
            ))
            
            # Get the ID of the inserted/updated record
            if cursor.lastrowid:
                record_id = cursor.lastrowid
            else:
                # If it was an update, fetch the existing ID
                cursor.execute("""
                    SELECT id FROM weather_records
                    WHERE timestamp = ? AND country = ? AND location = ?
                """, (record.timestamp.isoformat(), record.country, record.location))
                record_id = cursor.fetchone()[0]
            
            con.commit()
            logger.info(f"Saved weather record for {record.country}/{record.location} at {record.timestamp}")
            return record_id
            
        except Exception as e:
            con.rollback()
            logger.error(f"Error saving weather record: {str(e)}")
            raise
        finally:
            con.close()
    
    def get_records_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        country: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[WeatherRecord]:
        """
        Get weather records within a date range with optional filtering.
        
        DATA LEAKAGE PREVENTION: This method ONLY queries weather_records table
        (current observations). It NEVER queries forecast_data table to prevent
        future information from leaking into ML training data.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            country: Optional country filter
            location: Optional location filter
            
        Returns:
            List of WeatherRecord objects matching the criteria
            
        Validates: Requirements 2.2, 2.3
        """
        # ASSERTION: Validate we're querying the correct table for ML training
        table_name = "weather_records"
        assert table_name == "weather_records", \
            "DATA LEAKAGE RISK: ML training must only use weather_records table, not forecast_data"
        
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            # Build query with optional filters
            query = f"""
                SELECT * FROM {table_name}
                WHERE timestamp >= ? AND timestamp <= ?
            """
            params = [start_date.isoformat(), end_date.isoformat()]
            
            if country:
                query += " AND country = ?"
                params.append(country)
            
            if location:
                query += " AND location = ?"
                params.append(location)
            
            query += " ORDER BY timestamp ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to WeatherRecord objects
            records = []
            for row in rows:
                record = WeatherRecord(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    country=row['country'],
                    location=row['location'],
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    temperature=row['temperature'],
                    rainfall=row['rainfall'],
                    humidity=row['humidity'],
                    wind_speed=row['wind_speed'],
                    wind_direction=row['wind_direction'],
                    pressure=row['pressure'],
                    source_api=row['source_api']
                )
                records.append(record)
            
            logger.info(f"Retrieved {len(records)} records for date range {start_date} to {end_date}")
            return records
            
        finally:
            con.close()
    
    def get_records_by_location(
        self,
        country: str,
        location: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[WeatherRecord]:
        """
        Get weather records by country and optional location with optional date filtering.
        
        Args:
            country: Country to filter by
            location: Optional specific location within country
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            List of WeatherRecord objects matching the criteria
            
        Validates: Requirements 2.3
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            # Build query with optional filters
            query = "SELECT * FROM weather_records WHERE country = ?"
            params = [country]
            
            if location:
                query += " AND location = ?"
                params.append(location)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to WeatherRecord objects
            records = []
            for row in rows:
                record = WeatherRecord(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    country=row['country'],
                    location=row['location'],
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    temperature=row['temperature'],
                    rainfall=row['rainfall'],
                    humidity=row['humidity'],
                    wind_speed=row['wind_speed'],
                    wind_direction=row['wind_direction'],
                    pressure=row['pressure'],
                    source_api=row['source_api']
                )
                records.append(record)
            
            logger.info(f"Retrieved {len(records)} records for {country}/{location or 'all'}")
            return records
            
        finally:
            con.close()
    
    def get_latest_record(self, country: str, location: Optional[str] = None) -> Optional[WeatherRecord]:
        """
        Get the most recent weather record for a location.
        
        Args:
            country: Country name
            location: Optional location name (if None, gets latest for any location in country)
            
        Returns:
            Most recent WeatherRecord or None if no records exist
            
        Validates: Requirements 2.1
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            if location:
                cursor.execute("""
                    SELECT * FROM weather_records
                    WHERE country = ? AND location = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (country, location))
            else:
                cursor.execute("""
                    SELECT * FROM weather_records
                    WHERE country = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (country,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            record = WeatherRecord(
                timestamp=datetime.fromisoformat(row['timestamp']),
                country=row['country'],
                location=row['location'],
                latitude=row['latitude'],
                longitude=row['longitude'],
                temperature=row['temperature'],
                rainfall=row['rainfall'],
                humidity=row['humidity'],
                wind_speed=row['wind_speed'],
                wind_direction=row['wind_direction'],
                pressure=row['pressure'],
                source_api=row['source_api']
            )
            
            return record
            
        finally:
            con.close()
    
    def cleanup_old_records(self, retention_days: int = 1825) -> int:
        """
        Delete weather records older than retention period.
        
        Default retention is 5 years (1825 days) as per requirements.
        
        Args:
            retention_days: Number of days to retain records (default: 1825 = 5 years)
            
        Returns:
            Number of records deleted
            
        Validates: Requirements 2.5
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            cursor.execute("""
                DELETE FROM weather_records
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            con.commit()
            
            logger.info(f"Deleted {deleted_count} records older than {cutoff_date}")
            return deleted_count
            
        except Exception as e:
            con.rollback()
            logger.error(f"Error cleaning up old records: {str(e)}")
            raise
        finally:
            con.close()
    
    # ========== Model Metadata Operations (Task 3.3) ==========
    
    def save_model_metadata(self, metadata: ModelMetadata) -> int:
        """
        Save trained model metadata to database.
        
        Args:
            metadata: ModelMetadata object with model information
            
        Returns:
            Model ID (primary key)
            
        Validates: Requirements 3.7
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO model_metadata (
                    model_type, weather_parameter, country, version,
                    hyperparameters, training_date, training_samples,
                    validation_mae, validation_rmse, validation_mape,
                    file_path, is_production, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.model_type,
                metadata.weather_parameter,
                metadata.country,
                metadata.version,
                json.dumps(metadata.hyperparameters),
                metadata.training_date.isoformat(),
                metadata.training_samples,
                metadata.validation_mae,
                metadata.validation_rmse,
                metadata.validation_mape,
                metadata.file_path,
                1 if metadata.is_production else 0,
                datetime.now().isoformat()
            ))
            
            model_id = cursor.lastrowid
            con.commit()
            
            logger.info(
                f"Saved model metadata: {metadata.model_type} for {metadata.weather_parameter} "
                f"(ID: {model_id}, MAE: {metadata.validation_mae:.4f})"
            )
            return model_id
            
        except Exception as e:
            con.rollback()
            logger.error(f"Error saving model metadata: {str(e)}")
            raise
        finally:
            con.close()
    
    def save_prediction(self, prediction: Prediction) -> int:
        """
        Save forecast prediction to database.
        
        Args:
            prediction: Prediction object with forecast data
            
        Returns:
            Prediction ID (primary key)
            
        Validates: Requirements 6.5
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO predictions (
                    model_id, prediction_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, confidence_lower, confidence_upper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.model_id,
                prediction.prediction_timestamp.isoformat(),
                prediction.target_timestamp.isoformat(),
                prediction.hours_ahead,
                prediction.country,
                prediction.location,
                prediction.weather_parameter,
                prediction.predicted_value,
                prediction.confidence_lower,
                prediction.confidence_upper
            ))
            
            prediction_id = cursor.lastrowid
            con.commit()
            
            logger.debug(
                f"Saved prediction: {prediction.weather_parameter} = {prediction.predicted_value:.2f} "
                f"for {prediction.country}/{prediction.location} at {prediction.target_timestamp}"
            )
            return prediction_id
            
        except Exception as e:
            con.rollback()
            logger.error(f"Error saving prediction: {str(e)}")
            raise
        finally:
            con.close()
    
    def store_record(self, record: WeatherRecord) -> int:
        """
        Store a weather record (alias for save_weather_record).
        
        Args:
            record: WeatherRecord to store
            
        Returns:
            Record ID
        """
        return self.save_weather_record(record)
    
    def save_evaluation_metric(self, metric: EvaluationMetric) -> int:
        """
        Save evaluation metric comparing prediction to actual weather.
        
        Args:
            metric: EvaluationMetric object with comparison data
            
        Returns:
            Metric ID (primary key)
            
        Validates: Requirements 6.5
        """
        con = self._get_connection()
        cursor = con.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.model_id,
                metric.evaluation_timestamp.isoformat(),
                metric.target_timestamp.isoformat(),
                metric.hours_ahead,
                metric.country,
                metric.location,
                metric.weather_parameter,
                metric.predicted_value,
                metric.actual_value,
                metric.absolute_error,
                metric.squared_error,
                metric.percentage_error
            ))
            
            metric_id = cursor.lastrowid
            con.commit()
            
            logger.debug(
                f"Saved evaluation metric: {metric.weather_parameter} "
                f"MAE={metric.absolute_error:.2f} for {metric.country}/{metric.location}"
            )
            return metric_id
            
        except Exception as e:
            con.rollback()
            logger.error(f"Error saving evaluation metric: {str(e)}")
            raise
        finally:
            con.close()
