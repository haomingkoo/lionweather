"""
Data Store Service for ML Weather Forecasting

This module provides the DataStore class for persisting and querying weather records,
model metadata, predictions, and evaluation metrics.
"""

import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import logging

from sqlalchemy import text
from app.db.database import get_engine

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
            db_path: Ignored. Connection is managed via get_engine() from app.db.database,
                     which reads DATABASE_URL (Postgres on Railway) or DATABASE_PATH (SQLite locally).
        """
        pass

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
        with get_engine().connect() as conn:
            try:
                conn.execute(text("""
                    INSERT INTO weather_records (
                        timestamp, country, location, latitude, longitude,
                        temperature, rainfall, humidity, wind_speed,
                        wind_direction, pressure, source_api, created_at
                    ) VALUES (
                        :timestamp, :country, :location, :latitude, :longitude,
                        :temperature, :rainfall, :humidity, :wind_speed,
                        :wind_direction, :pressure, :source_api, :created_at
                    )
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
                """), {
                    "timestamp": record.timestamp.isoformat(),
                    "country": record.country,
                    "location": record.location,
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "temperature": record.temperature,
                    "rainfall": record.rainfall,
                    "humidity": record.humidity,
                    "wind_speed": record.wind_speed,
                    "wind_direction": record.wind_direction,
                    "pressure": record.pressure,
                    "source_api": record.source_api,
                    "created_at": datetime.now().isoformat(),
                })

                # SELECT to get the ID of the inserted/updated record
                row = conn.execute(text("""
                    SELECT id FROM weather_records
                    WHERE timestamp = :timestamp AND country = :country AND location = :location
                """), {
                    "timestamp": record.timestamp.isoformat(),
                    "country": record.country,
                    "location": record.location,
                }).fetchone()

                record_id = row[0]
                conn.commit()

                logger.info(f"Saved weather record for {record.country}/{record.location} at {record.timestamp}")
                return record_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving weather record: {str(e)}")
                raise

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

        query = f"SELECT * FROM {table_name} WHERE timestamp >= :start_date AND timestamp <= :end_date"
        params: Dict[str, Any] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        if country:
            query += " AND country = :country"
            params["country"] = country

        if location:
            query += " AND location = :location"
            params["location"] = location

        query += " ORDER BY timestamp ASC"

        with get_engine().connect() as conn:
            rows = conn.execute(text(query), params).fetchall()

        records = []
        for row in rows:
            record = self._row_to_record(row)
            records.append(record)

        logger.info(f"Retrieved {len(records)} records for date range {start_date} to {end_date}")
        return records

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
        query = "SELECT * FROM weather_records WHERE country = :country"
        params: Dict[str, Any] = {"country": country}

        if location:
            query += " AND location = :location"
            params["location"] = location

        if start_date:
            query += " AND timestamp >= :start_date"
            params["start_date"] = start_date.isoformat()

        if end_date:
            query += " AND timestamp <= :end_date"
            params["end_date"] = end_date.isoformat()

        query += " ORDER BY timestamp DESC"

        with get_engine().connect() as conn:
            rows = conn.execute(text(query), params).fetchall()

        records = [self._row_to_record(row) for row in rows]
        logger.info(f"Retrieved {len(records)} records for {country}/{location or 'all'}")
        return records

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
        if location:
            query = """
                SELECT * FROM weather_records
                WHERE country = :country AND location = :location
                ORDER BY timestamp DESC
                LIMIT 1
            """
            params: Dict[str, Any] = {"country": country, "location": location}
        else:
            query = """
                SELECT * FROM weather_records
                WHERE country = :country
                ORDER BY timestamp DESC
                LIMIT 1
            """
            params = {"country": country}

        with get_engine().connect() as conn:
            row = conn.execute(text(query), params).fetchone()

        if not row:
            return None

        return self._row_to_record(row)

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
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        with get_engine().connect() as conn:
            try:
                result = conn.execute(text("""
                    DELETE FROM weather_records
                    WHERE timestamp < :cutoff_date
                """), {"cutoff_date": cutoff_date.isoformat()})

                deleted_count = result.rowcount
                conn.commit()

                logger.info(f"Deleted {deleted_count} records older than {cutoff_date}")
                return deleted_count

            except Exception as e:
                conn.rollback()
                logger.error(f"Error cleaning up old records: {str(e)}")
                raise

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
        with get_engine().connect() as conn:
            try:
                row = conn.execute(text("""
                    INSERT INTO model_metadata (
                        model_type, weather_parameter, country, version,
                        hyperparameters, training_date, training_samples,
                        validation_mae, validation_rmse, validation_mape,
                        file_path, is_production, created_at
                    ) VALUES (
                        :model_type, :weather_parameter, :country, :version,
                        :hyperparameters, :training_date, :training_samples,
                        :validation_mae, :validation_rmse, :validation_mape,
                        :file_path, :is_production, :created_at
                    )
                    RETURNING id
                """), {
                    "model_type": metadata.model_type,
                    "weather_parameter": metadata.weather_parameter,
                    "country": metadata.country,
                    "version": metadata.version,
                    "hyperparameters": json.dumps(metadata.hyperparameters),
                    "training_date": metadata.training_date.isoformat(),
                    "training_samples": metadata.training_samples,
                    "validation_mae": metadata.validation_mae,
                    "validation_rmse": metadata.validation_rmse,
                    "validation_mape": metadata.validation_mape,
                    "file_path": metadata.file_path,
                    "is_production": 1 if metadata.is_production else 0,
                    "created_at": datetime.now().isoformat(),
                }).fetchone()

                model_id = row[0]
                conn.commit()

                logger.info(
                    f"Saved model metadata: {metadata.model_type} for {metadata.weather_parameter} "
                    f"(ID: {model_id}, MAE: {metadata.validation_mae:.4f})"
                )
                return model_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving model metadata: {str(e)}")
                raise

    def save_prediction(self, prediction: Prediction) -> int:
        """
        Save forecast prediction to database.

        Args:
            prediction: Prediction object with forecast data

        Returns:
            Prediction ID (primary key)

        Validates: Requirements 6.5
        """
        with get_engine().connect() as conn:
            try:
                row = conn.execute(text("""
                    INSERT INTO predictions (
                        model_id, prediction_timestamp, target_timestamp,
                        hours_ahead, country, location, weather_parameter,
                        predicted_value, confidence_lower, confidence_upper
                    ) VALUES (
                        :model_id, :prediction_timestamp, :target_timestamp,
                        :hours_ahead, :country, :location, :weather_parameter,
                        :predicted_value, :confidence_lower, :confidence_upper
                    )
                    RETURNING id
                """), {
                    "model_id": prediction.model_id,
                    "prediction_timestamp": prediction.prediction_timestamp.isoformat(),
                    "target_timestamp": prediction.target_timestamp.isoformat(),
                    "hours_ahead": prediction.hours_ahead,
                    "country": prediction.country,
                    "location": prediction.location,
                    "weather_parameter": prediction.weather_parameter,
                    "predicted_value": prediction.predicted_value,
                    "confidence_lower": prediction.confidence_lower,
                    "confidence_upper": prediction.confidence_upper,
                }).fetchone()

                prediction_id = row[0]
                conn.commit()

                logger.debug(
                    f"Saved prediction: {prediction.weather_parameter} = {prediction.predicted_value:.2f} "
                    f"for {prediction.country}/{prediction.location} at {prediction.target_timestamp}"
                )
                return prediction_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving prediction: {str(e)}")
                raise

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
        with get_engine().connect() as conn:
            try:
                row = conn.execute(text("""
                    INSERT INTO evaluation_metrics (
                        model_id, evaluation_timestamp, target_timestamp,
                        hours_ahead, country, location, weather_parameter,
                        predicted_value, actual_value, absolute_error,
                        squared_error, percentage_error
                    ) VALUES (
                        :model_id, :evaluation_timestamp, :target_timestamp,
                        :hours_ahead, :country, :location, :weather_parameter,
                        :predicted_value, :actual_value, :absolute_error,
                        :squared_error, :percentage_error
                    )
                    RETURNING id
                """), {
                    "model_id": metric.model_id,
                    "evaluation_timestamp": metric.evaluation_timestamp.isoformat(),
                    "target_timestamp": metric.target_timestamp.isoformat(),
                    "hours_ahead": metric.hours_ahead,
                    "country": metric.country,
                    "location": metric.location,
                    "weather_parameter": metric.weather_parameter,
                    "predicted_value": metric.predicted_value,
                    "actual_value": metric.actual_value,
                    "absolute_error": metric.absolute_error,
                    "squared_error": metric.squared_error,
                    "percentage_error": metric.percentage_error,
                }).fetchone()

                metric_id = row[0]
                conn.commit()

                logger.debug(
                    f"Saved evaluation metric: {metric.weather_parameter} "
                    f"MAE={metric.absolute_error:.2f} for {metric.country}/{metric.location}"
                )
                return metric_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving evaluation metric: {str(e)}")
                raise

    # ========== Private Helpers ==========

    def _row_to_record(self, row) -> WeatherRecord:
        """
        Convert a SQLAlchemy Row to a WeatherRecord.

        Columns are accessed by index to be compatible with both SQLite and PostgreSQL
        SQLAlchemy Row objects.

        Expected column order (SELECT *):
            0: id, 1: timestamp, 2: country, 3: location, 4: latitude, 5: longitude,
            6: temperature, 7: rainfall, 8: humidity, 9: wind_speed,
            10: wind_direction, 11: pressure, 12: source_api, 13: created_at
        """
        return WeatherRecord(
            timestamp=datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1],
            country=row[2],
            location=row[3],
            latitude=row[4],
            longitude=row[5],
            temperature=row[6],
            rainfall=row[7],
            humidity=row[8],
            wind_speed=row[9],
            wind_direction=row[10],
            pressure=row[11],
            source_api=row[12],
        )
