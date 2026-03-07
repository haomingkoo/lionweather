"""
Preservation Property Tests - Non-Rolling ML Features

**Property 2: Preservation** - Lag and Temporal Features Unchanged

This test suite validates that non-rolling features (lag features and temporal features)
continue to produce correct results after the ML data leakage fix.

IMPORTANT: Follow observation-first methodology
- Observe behavior on UNFIXED code: lag features and temporal features produce correct results
- Write property-based test: for all feature engineering executions with non-rolling features,
  results match original implementation (from Preservation Requirements in design)
- Property-based testing generates many test cases for stronger guarantees
- Run tests on UNFIXED code
- **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)

Validates: Requirements 3.4, 3.5
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.extra.pandas import column, data_frames

import sys
from pathlib import Path
# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.feature_engineer import FeatureEngineer


# Custom strategies for generating test data
@st.composite
def timestamp_strategy(draw):
    """Generate random timestamps for testing."""
    year = draw(st.integers(min_value=2020, max_value=2024))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    
    return datetime(year, month, day, hour, minute, second)


@st.composite
def weather_dataframe_with_values_strategy(draw):
    """Generate a DataFrame with timestamps and weather values for testing."""
    # Generate 10-100 rows for meaningful lag testing
    size = draw(st.integers(min_value=10, max_value=100))
    
    # Generate sequential timestamps (sorted)
    base_timestamp = draw(timestamp_strategy())
    timestamps = [base_timestamp + timedelta(hours=i) for i in range(size)]
    
    # Generate weather values
    temperatures = [draw(st.floats(min_value=-10.0, max_value=45.0, allow_nan=False, allow_infinity=False)) 
                   for _ in range(size)]
    humidity = [draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)) 
               for _ in range(size)]
    
    return pd.DataFrame({
        'timestamp': timestamps,
        'temperature': temperatures,
        'humidity': humidity
    })


class TestLagFeaturesPreservation:
    """
    Test suite for lag feature preservation.
    
    Validates that lag features continue to work correctly after the rolling features fix.
    """
    
    # Feature: ml-weather-forecasting, Property 43: Lag Feature Correctness
    @given(df=weather_dataframe_with_values_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_lag_features_correctness(self, df):
        """
        **Validates: Requirements 3.4, 3.5**
        
        Property: Lag Feature Correctness
        
        For all feature engineering executions with lag features, the lag feature at index i
        should equal the original value at index (i - lag), and the first 'lag' values should be NaN.
        
        This property ensures that lag features continue to work correctly and are not affected
        by the rolling features data leakage fix.
        """
        engineer = FeatureEngineer()
        
        # Test with default lags [1, 3, 7]
        result = engineer.create_lag_features(df, ['temperature', 'humidity'])
        
        # Property 1: Lag columns should be created
        assert 'temperature_lag_1' in result.columns
        assert 'temperature_lag_3' in result.columns
        assert 'temperature_lag_7' in result.columns
        assert 'humidity_lag_1' in result.columns
        assert 'humidity_lag_3' in result.columns
        assert 'humidity_lag_7' in result.columns
        
        # Property 2: Lag features should have correct values
        for col in ['temperature', 'humidity']:
            for lag in [1, 3, 7]:
                lag_col = f"{col}_lag_{lag}"
                
                # First 'lag' values should be NaN
                for i in range(min(lag, len(result))):
                    assert pd.isna(result.iloc[i][lag_col]), \
                        f"First {lag} values of {lag_col} should be NaN, but index {i} is {result.iloc[i][lag_col]}"
                
                # Subsequent values should match original values shifted by 'lag'
                for i in range(lag, len(result)):
                    expected_value = result.iloc[i - lag][col]
                    actual_value = result.iloc[i][lag_col]
                    
                    # Handle NaN comparison
                    if pd.isna(expected_value):
                        assert pd.isna(actual_value), \
                            f"{lag_col} at index {i} should be NaN but is {actual_value}"
                    else:
                        assert abs(actual_value - expected_value) < 1e-6, \
                            f"{lag_col} at index {i} should be {expected_value} but is {actual_value}"
        
        # Property 3: Original DataFrame should not be modified
        assert 'temperature_lag_1' not in df.columns
        assert 'humidity_lag_1' not in df.columns
    
    def test_lag_features_with_custom_lags(self):
        """
        Test that lag features work correctly with custom lag values.
        
        **Validates: Requirements 3.4, 3.5**
        """
        engineer = FeatureEngineer()
        
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=20, freq='h'),
            'temperature': list(range(20, 40)),
            'humidity': list(range(60, 80))
        })
        
        # Test with custom lags [2, 5, 10]
        result = engineer.create_lag_features(df, ['temperature'], [2, 5, 10])
        
        # Verify lag_2
        assert pd.isna(result.iloc[0]['temperature_lag_2'])
        assert pd.isna(result.iloc[1]['temperature_lag_2'])
        assert result.iloc[2]['temperature_lag_2'] == 20
        assert result.iloc[5]['temperature_lag_2'] == 23
        
        # Verify lag_5
        for i in range(5):
            assert pd.isna(result.iloc[i]['temperature_lag_5'])
        assert result.iloc[5]['temperature_lag_5'] == 20
        assert result.iloc[10]['temperature_lag_5'] == 25
        
        # Verify lag_10
        for i in range(10):
            assert pd.isna(result.iloc[i]['temperature_lag_10'])
        assert result.iloc[10]['temperature_lag_10'] == 20
        assert result.iloc[15]['temperature_lag_10'] == 25


class TestTemporalFeaturesPreservation:
    """
    Test suite for temporal feature preservation.
    
    Validates that temporal features continue to work correctly after the rolling features fix.
    """
    
    # Feature: ml-weather-forecasting, Property 42: Temporal Feature Extraction
    @given(df=weather_dataframe_with_values_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_temporal_features_correctness(self, df):
        """
        **Validates: Requirements 3.4, 3.5**
        
        Property: Temporal Feature Extraction Correctness
        
        For all feature engineering executions with temporal features, the extracted features
        should match the timestamp's actual date/time components:
        - hour should be 0-23 and match timestamp.hour
        - day_of_week should be 0-6 and match timestamp.dayofweek
        - month should be 1-12 and match timestamp.month
        - season should be 0-3 and match the expected season for the month
        - is_weekend should be True for Saturday/Sunday, False otherwise
        
        This property ensures that temporal features continue to work correctly and are not
        affected by the rolling features data leakage fix.
        """
        engineer = FeatureEngineer()
        
        result = engineer.create_temporal_features(df)
        
        # Property 1: All temporal feature columns should be created
        assert 'hour' in result.columns
        assert 'day_of_week' in result.columns
        assert 'month' in result.columns
        assert 'season' in result.columns
        assert 'is_weekend' in result.columns
        
        # Property 2: All temporal features should have correct values
        for idx, row in result.iterrows():
            timestamp = row['timestamp']
            
            # Hour should be 0-23 and match timestamp
            assert 0 <= row['hour'] <= 23, f"Hour {row['hour']} out of range"
            assert row['hour'] == timestamp.hour, \
                f"Hour {row['hour']} doesn't match timestamp hour {timestamp.hour}"
            
            # Day of week should be 0-6 and match timestamp
            assert 0 <= row['day_of_week'] <= 6, f"Day of week {row['day_of_week']} out of range"
            assert row['day_of_week'] == timestamp.dayofweek, \
                f"Day of week {row['day_of_week']} doesn't match timestamp {timestamp.dayofweek}"
            
            # Month should be 1-12 and match timestamp
            assert 1 <= row['month'] <= 12, f"Month {row['month']} out of range"
            assert row['month'] == timestamp.month, \
                f"Month {row['month']} doesn't match timestamp month {timestamp.month}"
            
            # Season should be 0-3 and match expected season
            assert 0 <= row['season'] <= 3, f"Season {row['season']} out of range"
            expected_season = self._get_expected_season(timestamp.month)
            assert row['season'] == expected_season, \
                f"Season {row['season']} doesn't match expected {expected_season} for month {timestamp.month}"
            
            # is_weekend should be boolean and match day_of_week
            assert isinstance(row['is_weekend'], (bool, np.bool_)), \
                f"is_weekend should be boolean, got {type(row['is_weekend'])}"
            expected_weekend = timestamp.dayofweek in [5, 6]
            assert row['is_weekend'] == expected_weekend, \
                f"is_weekend {row['is_weekend']} doesn't match expected {expected_weekend}"
        
        # Property 3: Original DataFrame should not be modified
        assert 'hour' not in df.columns
        assert 'day_of_week' not in df.columns
    
    @staticmethod
    def _get_expected_season(month: int) -> int:
        """Helper to calculate expected season from month."""
        if month in [12, 1, 2]:
            return 0  # Winter
        elif month in [3, 4, 5]:
            return 1  # Spring
        elif month in [6, 7, 8]:
            return 2  # Summer
        else:  # month in [9, 10, 11]
            return 3  # Fall
    
    def test_temporal_features_all_seasons(self):
        """
        Test that temporal features correctly identify all four seasons.
        
        **Validates: Requirements 3.4, 3.5**
        """
        engineer = FeatureEngineer()
        
        # Test one month from each season
        test_cases = [
            (datetime(2024, 1, 15, 12, 0, 0), 0),   # January -> Winter
            (datetime(2024, 4, 15, 12, 0, 0), 1),   # April -> Spring
            (datetime(2024, 7, 15, 12, 0, 0), 2),   # July -> Summer
            (datetime(2024, 10, 15, 12, 0, 0), 3),  # October -> Fall
        ]
        
        for timestamp, expected_season in test_cases:
            df = pd.DataFrame({'timestamp': [timestamp]})
            result = engineer.create_temporal_features(df)
            
            assert result.iloc[0]['season'] == expected_season, \
                f"Month {timestamp.month} should map to season {expected_season}"
    
    def test_temporal_features_weekend_detection(self):
        """
        Test that temporal features correctly detect weekends.
        
        **Validates: Requirements 3.4, 3.5**
        """
        engineer = FeatureEngineer()
        
        # Test a full week (Monday to Sunday)
        # January 1, 2024 is a Monday
        base_date = datetime(2024, 1, 1, 12, 0, 0)
        expected_weekend = [False, False, False, False, False, True, True]
        
        for day_offset, expected in enumerate(expected_weekend):
            date = base_date + timedelta(days=day_offset)
            df = pd.DataFrame({'timestamp': [date]})
            result = engineer.create_temporal_features(df)
            
            assert result.iloc[0]['is_weekend'] == expected, \
                f"Day {date.strftime('%A')} should have is_weekend={expected}"


class TestCombinedFeaturesPreservation:
    """
    Test suite for combined feature preservation.
    
    Validates that lag and temporal features work correctly together.
    """
    
    def test_combined_lag_and_temporal_features(self):
        """
        Test that lag and temporal features can be applied together without conflicts.
        
        **Validates: Requirements 3.4, 3.5**
        """
        engineer = FeatureEngineer()
        
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=20, freq='h'),
            'temperature': list(range(20, 40)),
            'humidity': list(range(60, 80))
        })
        
        # Apply temporal features first
        result = engineer.create_temporal_features(df)
        
        # Then apply lag features
        result = engineer.create_lag_features(result, ['temperature', 'humidity'], [1, 3])
        
        # Verify all features are present
        assert 'hour' in result.columns
        assert 'day_of_week' in result.columns
        assert 'month' in result.columns
        assert 'season' in result.columns
        assert 'is_weekend' in result.columns
        assert 'temperature_lag_1' in result.columns
        assert 'temperature_lag_3' in result.columns
        assert 'humidity_lag_1' in result.columns
        assert 'humidity_lag_3' in result.columns
        
        # Verify temporal features are correct
        for idx, row in result.iterrows():
            timestamp = row['timestamp']
            assert row['hour'] == timestamp.hour
            assert row['day_of_week'] == timestamp.dayofweek
            assert row['month'] == timestamp.month
        
        # Verify lag features are correct
        assert pd.isna(result.iloc[0]['temperature_lag_1'])
        assert result.iloc[1]['temperature_lag_1'] == 20
        assert result.iloc[5]['temperature_lag_3'] == 22
