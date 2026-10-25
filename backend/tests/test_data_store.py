"""
Unit tests for DataStore service.

Tests basic CRUD operations for weather records, model metadata,
predictions, and evaluation metrics.
"""

import pytest
from datetime import datetime, timedelta

from app.db import database
from app.db.migrations import migrate_ml_tables
from app.services.data_store import (
    DataStore,
    Prediction,
    EvaluationMetric
)
from app.services.data_collector import WeatherRecord


@pytest.fixture
def data_store(tmp_path, monkeypatch):
    """Create DataStore instance backed by a fresh SQLite database with the real schema."""
    monkeypatch.setattr(database, "_database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "_engine", None)
    migrate_ml_tables()
    return DataStore()


@pytest.fixture
def sample_weather_record():
    """Create a sample weather record for testing."""
    return WeatherRecord(
        timestamp=datetime(2024, 1, 15, 12, 0, 0),
        country="singapore",
        location="Changi",
        latitude=1.3644,
        longitude=103.9915,
        temperature=28.5,
        rainfall=0.5,
        humidity=75.0,
        wind_speed=12.5,
        wind_direction=180.0,
        pressure=1013.25,
        source_api="api-open.data.gov.sg"
    )


# ========== Weather Record Tests ==========

def test_save_weather_record(data_store, sample_weather_record):
    """Test saving a weather record."""
    record_id = data_store.save_weather_record(sample_weather_record)
    assert record_id > 0


def test_save_duplicate_weather_record_updates(data_store, sample_weather_record):
    """Test that saving a duplicate record updates the existing one."""
    # Save first time
    record_id_1 = data_store.save_weather_record(sample_weather_record)
    
    # Modify and save again with same timestamp/country/location
    sample_weather_record.temperature = 30.0
    record_id_2 = data_store.save_weather_record(sample_weather_record)
    
    # Should update, not create new record
    assert record_id_1 == record_id_2
    
    # Verify temperature was updated
    retrieved = data_store.get_latest_record("singapore", "Changi")
    assert retrieved.temperature == 30.0


def test_get_records_by_date_range(data_store):
    """Test retrieving records by date range."""
    # Create records with different timestamps
    base_time = datetime(2024, 1, 15, 12, 0, 0)
    
    for i in range(5):
        record = WeatherRecord(
            timestamp=base_time + timedelta(hours=i),
            country="singapore",
            location="Changi",
            latitude=1.3644,
            longitude=103.9915,
            temperature=28.0 + i,
            rainfall=0.0,
            humidity=75.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        data_store.save_weather_record(record)
    
    # Query for middle 3 records
    start = base_time + timedelta(hours=1)
    end = base_time + timedelta(hours=3)
    
    records = data_store.get_records_by_date_range(start, end)
    
    assert len(records) == 3
    assert all(start <= r.timestamp <= end for r in records)


def test_get_records_by_date_range_with_filters(data_store):
    """Test date range query with country and location filters."""
    base_time = datetime(2024, 1, 15, 12, 0, 0)
    
    # Create records for different countries/locations
    locations = [
        ("singapore", "Changi"),
        ("singapore", "Jurong"),
        ("malaysia", "Kuala Lumpur")
    ]
    
    for country, location in locations:
        record = WeatherRecord(
            timestamp=base_time,
            country=country,
            location=location,
            latitude=0.0,
            longitude=0.0,
            temperature=28.0,
            rainfall=0.0,
            humidity=75.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        data_store.save_weather_record(record)
    
    # Query with country filter
    records = data_store.get_records_by_date_range(
        base_time - timedelta(hours=1),
        base_time + timedelta(hours=1),
        country="singapore"
    )
    assert len(records) == 2
    assert all(r.country == "singapore" for r in records)
    
    # Query with country and location filter
    records = data_store.get_records_by_date_range(
        base_time - timedelta(hours=1),
        base_time + timedelta(hours=1),
        country="singapore",
        location="Changi"
    )
    assert len(records) == 1
    assert records[0].location == "Changi"


def test_get_records_by_location(data_store):
    """Test retrieving records by location."""
    base_time = datetime(2024, 1, 15, 12, 0, 0)
    
    # Create multiple records for same location
    for i in range(3):
        record = WeatherRecord(
            timestamp=base_time + timedelta(hours=i),
            country="singapore",
            location="Changi",
            latitude=1.3644,
            longitude=103.9915,
            temperature=28.0,
            rainfall=0.0,
            humidity=75.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        data_store.save_weather_record(record)
    
    records = data_store.get_records_by_location("singapore", "Changi")
    assert len(records) == 3
    assert all(r.country == "singapore" and r.location == "Changi" for r in records)


def test_get_latest_record(data_store):
    """Test retrieving the most recent record for a location."""
    base_time = datetime(2024, 1, 15, 12, 0, 0)
    
    # Create records with different timestamps
    for i in range(3):
        record = WeatherRecord(
            timestamp=base_time + timedelta(hours=i),
            country="singapore",
            location="Changi",
            latitude=1.3644,
            longitude=103.9915,
            temperature=28.0 + i,
            rainfall=0.0,
            humidity=75.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        data_store.save_weather_record(record)
    
    latest = data_store.get_latest_record("singapore", "Changi")
    
    assert latest is not None
    assert latest.timestamp == base_time + timedelta(hours=2)
    assert latest.temperature == 30.0


def test_get_latest_record_none_when_empty(data_store):
    """Test that get_latest_record returns None when no records exist."""
    latest = data_store.get_latest_record("singapore", "Changi")
    assert latest is None


def test_cleanup_old_records(data_store):
    """Test deleting old records based on retention policy."""
    now = datetime.now()
    
    # Create old and recent records
    old_record = WeatherRecord(
        timestamp=now - timedelta(days=2000),  # Older than 5 years
        country="singapore",
        location="Changi",
        latitude=1.3644,
        longitude=103.9915,
        temperature=28.0,
        rainfall=0.0,
        humidity=75.0,
        wind_speed=10.0,
        wind_direction=None,
        pressure=None,
        source_api="test"
    )
    
    recent_record = WeatherRecord(
        timestamp=now - timedelta(days=100),  # Recent
        country="singapore",
        location="Changi",
        latitude=1.3644,
        longitude=103.9915,
        temperature=29.0,
        rainfall=0.0,
        humidity=75.0,
        wind_speed=10.0,
        wind_direction=None,
        pressure=None,
        source_api="test"
    )
    
    data_store.save_weather_record(old_record)
    data_store.save_weather_record(recent_record)
    
    # Cleanup with 5-year retention (1825 days)
    deleted_count = data_store.cleanup_old_records(retention_days=1825)
    
    assert deleted_count == 1
    
    # Verify only recent record remains
    records = data_store.get_records_by_location("singapore", "Changi")
    assert len(records) == 1
    assert records[0].temperature == 29.0


# ========== Prediction Tests ==========

def test_save_prediction(data_store):
    """Test saving a prediction."""
    model_id = 1
    
    # Create prediction
    prediction = Prediction(
        model_id=model_id,
        prediction_timestamp=datetime(2024, 1, 15, 12, 0, 0),
        target_timestamp=datetime(2024, 1, 15, 13, 0, 0),
        hours_ahead=1,
        country="singapore",
        location="Changi",
        weather_parameter="temperature",
        predicted_value=28.5,
        confidence_lower=27.0,
        confidence_upper=30.0
    )
    
    prediction_id = data_store.save_prediction(prediction)
    assert prediction_id > 0


# ========== Evaluation Metric Tests ==========

def test_save_evaluation_metric(data_store):
    """Test saving an evaluation metric."""
    model_id = 1
    
    # Create evaluation metric
    metric = EvaluationMetric(
        model_id=model_id,
        evaluation_timestamp=datetime(2024, 1, 15, 13, 0, 0),
        target_timestamp=datetime(2024, 1, 15, 13, 0, 0),
        hours_ahead=1,
        country="singapore",
        location="Changi",
        weather_parameter="temperature",
        predicted_value=28.5,
        actual_value=29.0,
        absolute_error=0.5,
        squared_error=0.25,
        percentage_error=1.72
    )
    
    metric_id = data_store.save_evaluation_metric(metric)
    assert metric_id > 0
