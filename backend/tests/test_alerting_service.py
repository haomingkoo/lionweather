"""
Unit tests for AlertingService.

Tests model accuracy monitoring, prediction drift detection,
and data quality monitoring.
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import numpy as np

from app.ml.alerting_service import (
    AlertingService,
    Alert,
    AlertConfig
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize database schema
    con = sqlite3.connect(path)
    cursor = con.cursor()
    
    # Create evaluation_metrics table
    cursor.execute("""
        CREATE TABLE evaluation_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            evaluation_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            weather_parameter TEXT NOT NULL,
            predicted_value REAL NOT NULL,
            actual_value REAL NOT NULL,
            absolute_error REAL NOT NULL,
            squared_error REAL NOT NULL,
            percentage_error REAL NOT NULL
        )
    """)
    
    # Create predictions table
    cursor.execute("""
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            prediction_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            weather_parameter TEXT NOT NULL,
            predicted_value REAL NOT NULL,
            confidence_lower REAL NOT NULL,
            confidence_upper REAL NOT NULL
        )
    """)
    
    # Create weather_records table
    cursor.execute("""
        CREATE TABLE weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            temperature REAL NOT NULL,
            rainfall REAL NOT NULL,
            humidity REAL NOT NULL,
            wind_speed REAL NOT NULL,
            wind_direction REAL,
            pressure REAL,
            source_api TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(timestamp, country, location)
        )
    """)
    
    con.commit()
    con.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)


@pytest.fixture
def alerting_service(temp_db):
    """Create AlertingService with test database."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        config = AlertConfig(
            mae_threshold=5.0,
            rmse_threshold=7.0,
            mape_threshold=20.0,
            drift_threshold=0.3,
            missing_data_threshold=0.1,
            outlier_threshold=0.05,
            alert_cooldown_hours=1  # Short cooldown for testing
        )
        service = AlertingService(config)
        yield service


def test_alerting_service_initialization(alerting_service):
    """Test that AlertingService initializes correctly."""
    assert alerting_service.config is not None
    assert alerting_service.config.mae_threshold == 5.0
    assert alerting_service.alert_history == []


def test_alert_table_creation(temp_db):
    """Test that alerts table is created on initialization."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        service = AlertingService()
        
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='alerts'
        """)
        assert cursor.fetchone() is not None
        
        # Check indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_alerts_created'
        """)
        assert cursor.fetchone() is not None
        
        con.close()


def test_check_model_accuracy_no_data(alerting_service, temp_db):
    """Test accuracy check with no evaluation data."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        alert = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is None


def test_check_model_accuracy_below_threshold(alerting_service, temp_db):
    """Test accuracy check when metrics are below threshold."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert evaluation metrics below threshold
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 28.5, 0.5, 0.25, 1.8
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is None


def test_check_model_accuracy_exceeds_mae_threshold(alerting_service, temp_db):
    """Test accuracy check when MAE exceeds threshold."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert evaluation metrics above MAE threshold
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 34.0, 6.0, 36.0, 21.4  # MAE=6.0 > threshold=5.0
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is not None
        assert alert.alert_type == 'accuracy'
        assert alert.severity in ['warning', 'critical']
        assert 'MAE' in alert.message
        assert alert.model_id == 'test_model'
        assert alert.weather_parameter == 'temperature'
        assert alert.details['mae'] > 5.0


def test_check_model_accuracy_exceeds_rmse_threshold(alerting_service, temp_db):
    """Test accuracy check when RMSE exceeds threshold."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert evaluation metrics above RMSE threshold
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 36.0, 4.0, 64.0, 14.3  # RMSE=8.0 > threshold=7.0
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is not None
        assert alert.alert_type == 'accuracy'
        assert 'RMSE' in alert.message
        assert alert.details['rmse'] > 7.0


def test_check_model_accuracy_cooldown(alerting_service, temp_db):
    """Test that cooldown prevents duplicate alerts."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert evaluation metrics above threshold
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 34.0, 6.0, 36.0, 21.4
            ))
        
        con.commit()
        con.close()
        
        # First alert should be created
        alert1 = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        assert alert1 is not None
        
        # Second alert should be suppressed (cooldown)
        alert2 = alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        assert alert2 is None


def test_check_prediction_drift_no_data(alerting_service, temp_db):
    """Test drift check with insufficient data."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        alert = alerting_service.check_prediction_drift(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is None


def test_check_prediction_drift_no_drift(alerting_service, temp_db):
    """Test drift check when distributions are similar."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert predictions with similar distributions
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        
        # Baseline predictions (7 days ago to 1 day ago)
        for i in range(168, 24, -1):  # 168 hours = 7 days
            timestamp = (now - timedelta(hours=i)).isoformat()
            predicted_value = np.random.normal(28.0, 2.0)  # Mean=28, std=2
            cursor.execute("""
                INSERT INTO predictions (
                    model_id, prediction_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, confidence_lower, confidence_upper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                predicted_value, predicted_value - 2, predicted_value + 2
            ))
        
        # Recent predictions (last 24 hours) - similar distribution
        for i in range(24, 0, -1):
            timestamp = (now - timedelta(hours=i)).isoformat()
            predicted_value = np.random.normal(28.0, 2.0)  # Same distribution
            cursor.execute("""
                INSERT INTO predictions (
                    model_id, prediction_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, confidence_lower, confidence_upper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                predicted_value, predicted_value - 2, predicted_value + 2
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_prediction_drift(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        # Should not detect drift (distributions are similar)
        assert alert is None


def test_check_prediction_drift_detected(alerting_service, temp_db):
    """Test drift check when distribution shift is detected."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert predictions with different distributions
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        
        # Baseline predictions (7 days ago to 1 day ago) - Mean=28
        for i in range(168, 24, -1):
            timestamp = (now - timedelta(hours=i)).isoformat()
            predicted_value = np.random.normal(28.0, 2.0)
            cursor.execute("""
                INSERT INTO predictions (
                    model_id, prediction_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, confidence_lower, confidence_upper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                predicted_value, predicted_value - 2, predicted_value + 2
            ))
        
        # Recent predictions (last 24 hours) - Mean=35 (significant shift)
        for i in range(24, 0, -1):
            timestamp = (now - timedelta(hours=i)).isoformat()
            predicted_value = np.random.normal(35.0, 2.0)  # Shifted distribution
            cursor.execute("""
                INSERT INTO predictions (
                    model_id, prediction_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, confidence_lower, confidence_upper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                predicted_value, predicted_value - 2, predicted_value + 2
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_prediction_drift(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        # Should detect drift (distributions are different)
        assert alert is not None
        assert alert.alert_type == 'drift'
        assert alert.severity in ['warning', 'critical']
        assert 'drift' in alert.message.lower()
        assert alert.model_id == 'test_model'
        assert alert.weather_parameter == 'temperature'
        assert 'p_value' in alert.details
        assert 'mean_shift' in alert.details


def test_check_data_quality_no_issues(alerting_service, temp_db):
    """Test data quality check with good data."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert complete, valid weather records
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        locations = ['Changi', 'Jurong', 'Woodlands']
        
        for location in locations:
            for i in range(24):  # 24 hours of data
                timestamp = (now - timedelta(hours=i)).isoformat()
                cursor.execute("""
                    INSERT INTO weather_records (
                        timestamp, country, location, latitude, longitude,
                        temperature, rainfall, humidity, wind_speed,
                        wind_direction, pressure, source_api, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, 'singapore', location, 1.35, 103.82,
                    28.0, 0.5, 75.0, 12.0,
                    180.0, 1013.0, 'weather.gov.sg', timestamp
                ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_data_quality(
            country='singapore',
            window_hours=24
        )
        
        assert alert is None


def test_check_data_quality_missing_data(alerting_service, temp_db):
    """Test data quality check with missing data."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert incomplete weather records (missing some locations)
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        
        # Add historical data for all locations
        for location in ['Changi', 'Jurong', 'Woodlands']:
            timestamp = (now - timedelta(days=30)).isoformat()
            cursor.execute("""
                INSERT INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed,
                    wind_direction, pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, 'singapore', location, 1.35, 103.82,
                28.0, 0.5, 75.0, 12.0,
                180.0, 1013.0, 'weather.gov.sg', timestamp
            ))
        
        # Only add recent data for one location (others are missing)
        for i in range(24):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed,
                    wind_direction, pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, 'singapore', 'Changi', 1.35, 103.82,
                28.0, 0.5, 75.0, 12.0,
                180.0, 1013.0, 'weather.gov.sg', timestamp
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_data_quality(
            country='singapore',
            window_hours=24
        )
        
        assert alert is not None
        assert alert.alert_type == 'data_quality'
        assert 'missing' in alert.message.lower() or 'insufficient' in alert.message.lower()
        assert 'country' in alert.details
        assert alert.details['country'] == 'singapore'


def test_check_data_quality_outliers(alerting_service, temp_db):
    """Test data quality check with outliers."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Insert weather records with outliers
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        
        # Add mostly valid data
        for i in range(20):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed,
                    wind_direction, pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, 'singapore', 'Changi', 1.35, 103.82,
                28.0, 0.5, 75.0, 12.0,
                180.0, 1013.0, 'weather.gov.sg', timestamp
            ))
        
        # Add outliers (invalid values)
        for i in range(20, 24):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed,
                    wind_direction, pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, 'singapore', 'Changi', 1.35, 103.82,
                150.0, -10.0, 150.0, -5.0,  # Invalid outliers
                180.0, 1013.0, 'weather.gov.sg', timestamp
            ))
        
        con.commit()
        con.close()
        
        alert = alerting_service.check_data_quality(
            country='singapore',
            window_hours=24
        )
        
        # Should detect outliers
        assert alert is not None
        assert alert.alert_type == 'data_quality'
        assert 'outlier' in alert.message.lower()


def test_get_recent_alerts(alerting_service, temp_db):
    """Test retrieving recent alerts."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Create some alerts
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 34.0, 6.0, 36.0, 21.4
            ))
        
        con.commit()
        con.close()
        
        # Trigger alert
        alerting_service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        # Retrieve alerts
        alerts = alerting_service.get_recent_alerts(hours=24)
        
        assert len(alerts) > 0
        assert all(isinstance(alert, Alert) for alert in alerts)


def test_alert_config_defaults():
    """Test that AlertConfig has sensible defaults."""
    config = AlertConfig()
    
    assert config.mae_threshold == 5.0
    assert config.rmse_threshold == 7.0
    assert config.mape_threshold == 20.0
    assert config.drift_threshold == 0.3
    assert config.missing_data_threshold == 0.1
    assert config.outlier_threshold == 0.05
    assert config.alert_cooldown_hours == 24
    assert 'accuracy' in config.enabled_alerts
    assert 'drift' in config.enabled_alerts
    assert 'data_quality' in config.enabled_alerts


def test_disabled_alert_types(temp_db):
    """Test that disabled alert types are not triggered."""
    with patch('app.ml.alerting_service.DB_PATH', temp_db):
        # Create config with accuracy alerts disabled
        config = AlertConfig(
            enabled_alerts=['drift', 'data_quality']  # accuracy disabled
        )
        service = AlertingService(config)
        
        # Insert evaluation metrics above threshold
        con = sqlite3.connect(temp_db)
        cursor = con.cursor()
        
        now = datetime.now()
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO evaluation_metrics (
                    model_id, evaluation_timestamp, target_timestamp,
                    hours_ahead, country, location, weather_parameter,
                    predicted_value, actual_value, absolute_error,
                    squared_error, percentage_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_model', timestamp, timestamp,
                1, 'singapore', 'Changi', 'temperature',
                28.0, 34.0, 6.0, 36.0, 21.4
            ))
        
        con.commit()
        con.close()
        
        # Should not trigger alert (disabled)
        alert = service.check_model_accuracy(
            model_id='test_model',
            weather_parameter='temperature'
        )
        
        assert alert is None
