"""
Property-based tests for FeatureEngineer class.

Tests validate temporal feature extraction, lag features, rolling statistics,
and normalization using hypothesis for comprehensive input coverage.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
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
def weather_dataframe_strategy(draw):
    """Generate a DataFrame with timestamps for testing."""
    # Generate 1-100 timestamps
    size = draw(st.integers(min_value=1, max_value=100))
    timestamps = [draw(timestamp_strategy()) for _ in range(size)]
    
    return pd.DataFrame({'timestamp': timestamps})


class TestFeatureEngineerTemporalFeatures:
    """Test suite for temporal feature extraction."""
    
    def test_create_temporal_features_basic(self):
        """Basic unit test for temporal feature creation."""
        engineer = FeatureEngineer()
        
        # Create test data with known timestamps
        df = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1, 10, 0, 0),   # Monday, January, Winter
                datetime(2024, 6, 15, 14, 30, 0),  # Saturday, June, Summer
                datetime(2024, 12, 25, 23, 45, 0), # Wednesday, December, Winter
            ]
        })
        
        result = engineer.create_temporal_features(df)
        
        # Verify all expected columns are present
        assert 'hour' in result.columns
        assert 'day_of_week' in result.columns
        assert 'month' in result.columns
        assert 'season' in result.columns
        assert 'is_weekend' in result.columns
        
        # Verify first row (Monday, January 1, 2024, 10:00)
        assert result.iloc[0]['hour'] == 10
        assert result.iloc[0]['day_of_week'] == 0  # Monday
        assert result.iloc[0]['month'] == 1
        assert result.iloc[0]['season'] == 0  # Winter
        assert result.iloc[0]['is_weekend'] == False
        
        # Verify second row (Saturday, June 15, 2024, 14:30)
        assert result.iloc[1]['hour'] == 14
        assert result.iloc[1]['day_of_week'] == 5  # Saturday
        assert result.iloc[1]['month'] == 6
        assert result.iloc[1]['season'] == 2  # Summer
        assert result.iloc[1]['is_weekend'] == True
        
        # Verify third row (Wednesday, December 25, 2024, 23:45)
        assert result.iloc[2]['hour'] == 23
        assert result.iloc[2]['day_of_week'] == 2  # Wednesday
        assert result.iloc[2]['month'] == 12
        assert result.iloc[2]['season'] == 0  # Winter
        assert result.iloc[2]['is_weekend'] == False
    
    def test_create_temporal_features_with_string_timestamps(self):
        """Test that string timestamps are properly converted."""
        engineer = FeatureEngineer()
        
        df = pd.DataFrame({
            'timestamp': [
                '2024-03-15 12:00:00',
                '2024-09-20 18:30:00',
            ]
        })
        
        result = engineer.create_temporal_features(df)
        
        # Verify conversion worked
        assert result.iloc[0]['month'] == 3
        assert result.iloc[0]['season'] == 1  # Spring
        assert result.iloc[1]['month'] == 9
        assert result.iloc[1]['season'] == 3  # Fall
    
    def test_create_temporal_features_missing_timestamp_column(self):
        """Test that missing timestamp column raises error."""
        engineer = FeatureEngineer()
        
        df = pd.DataFrame({
            'temperature': [25.0, 26.0, 27.0]
        })
        
        with pytest.raises(ValueError, match="must contain a 'timestamp' column"):
            engineer.create_temporal_features(df)
    
    # Feature: ml-weather-forecasting, Property 42: Temporal Feature Extraction
    @given(df=weather_dataframe_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_temporal_feature_extraction(self, df):
        """
        Property 42: Temporal Feature Extraction
        
        For any timestamp, the extracted day-of-week feature should be 0-6 
        (Monday-Sunday) and the month feature should be 1-12, matching the 
        timestamp's actual date.
        
        Validates: Requirements 13.3, 13.4
        """
        engineer = FeatureEngineer()
        
        result = engineer.create_temporal_features(df)
        
        # Property: All temporal features should be within valid ranges
        for idx, row in result.iterrows():
            timestamp = row['timestamp']
            
            # Hour should be 0-23
            assert 0 <= row['hour'] <= 23, f"Hour {row['hour']} out of range"
            assert row['hour'] == timestamp.hour, \
                f"Hour {row['hour']} doesn't match timestamp hour {timestamp.hour}"
            
            # Day of week should be 0-6 (Monday=0, Sunday=6)
            assert 0 <= row['day_of_week'] <= 6, \
                f"Day of week {row['day_of_week']} out of range"
            assert row['day_of_week'] == timestamp.dayofweek, \
                f"Day of week {row['day_of_week']} doesn't match timestamp {timestamp.dayofweek}"
            
            # Month should be 1-12
            assert 1 <= row['month'] <= 12, f"Month {row['month']} out of range"
            assert row['month'] == timestamp.month, \
                f"Month {row['month']} doesn't match timestamp month {timestamp.month}"
            
            # Season should be 0-3
            assert 0 <= row['season'] <= 3, f"Season {row['season']} out of range"
            
            # Verify season matches month
            expected_season = self._get_expected_season(timestamp.month)
            assert row['season'] == expected_season, \
                f"Season {row['season']} doesn't match expected {expected_season} for month {timestamp.month}"
            
            # is_weekend should be boolean
            assert isinstance(row['is_weekend'], (bool, np.bool_)), \
                f"is_weekend should be boolean, got {type(row['is_weekend'])}"
            
            # Verify is_weekend matches day_of_week
            expected_weekend = timestamp.dayofweek in [5, 6]  # Saturday or Sunday
            assert row['is_weekend'] == expected_weekend, \
                f"is_weekend {row['is_weekend']} doesn't match expected {expected_weekend} for day {timestamp.dayofweek}"
    
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
    
    def test_season_mapping_all_months(self):
        """Test that all 12 months map to correct seasons."""
        engineer = FeatureEngineer()
        
        # Test all months
        months_to_seasons = {
            1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2,
            7: 2, 8: 2, 9: 3, 10: 3, 11: 3, 12: 0
        }
        
        for month, expected_season in months_to_seasons.items():
            df = pd.DataFrame({
                'timestamp': [datetime(2024, month, 15, 12, 0, 0)]
            })
            
            result = engineer.create_temporal_features(df)
            assert result.iloc[0]['season'] == expected_season, \
                f"Month {month} should map to season {expected_season}"
    
    def test_weekend_detection_all_days(self):
        """Test that weekend detection works for all days of the week."""
        engineer = FeatureEngineer()
        
        # Start with Monday, January 1, 2024
        base_date = datetime(2024, 1, 1, 12, 0, 0)
        
        # Expected: Mon-Fri = False, Sat-Sun = True
        expected_weekend = [False, False, False, False, False, True, True]
        
        for day_offset, expected in enumerate(expected_weekend):
            date = base_date + timedelta(days=day_offset)
            df = pd.DataFrame({'timestamp': [date]})
            
            result = engineer.create_temporal_features(df)
            assert result.iloc[0]['is_weekend'] == expected, \
                f"Day {date.strftime('%A')} should have is_weekend={expected}"

class TestFeatureEngineerLagFeatures:
    """Test suite for lag feature creation."""

    def test_create_lag_features_basic(self):
        """Basic unit test for lag feature creation."""
        engineer = FeatureEngineer()

        # Create test data with sequential values
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': [20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
            'humidity': [60, 61, 62, 63, 64, 65, 66, 67, 68, 69]
        })

        result = engineer.create_lag_features(df, ['temperature'], [1, 3])

        # Verify lag columns are created
        assert 'temperature_lag_1' in result.columns
        assert 'temperature_lag_3' in result.columns

        # Verify lag_1 values (shifted by 1)
        assert pd.isna(result.iloc[0]['temperature_lag_1'])  # First value is NaN
        assert result.iloc[1]['temperature_lag_1'] == 20  # Second value is first original
        assert result.iloc[2]['temperature_lag_1'] == 21
        assert result.iloc[5]['temperature_lag_1'] == 24

        # Verify lag_3 values (shifted by 3)
        assert pd.isna(result.iloc[0]['temperature_lag_3'])
        assert pd.isna(result.iloc[1]['temperature_lag_3'])
        assert pd.isna(result.iloc[2]['temperature_lag_3'])
        assert result.iloc[3]['temperature_lag_3'] == 20  # Fourth value is first original
        assert result.iloc[4]['temperature_lag_3'] == 21
        assert result.iloc[7]['temperature_lag_3'] == 24

    def test_create_lag_features_multiple_columns(self):
        """Test lag features for multiple columns."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24],
            'humidity': [60, 65, 70, 75, 80]
        })

        result = engineer.create_lag_features(df, ['temperature', 'humidity'], [1])

        # Verify both columns have lag features
        assert 'temperature_lag_1' in result.columns
        assert 'humidity_lag_1' in result.columns

        # Verify values
        assert result.iloc[1]['temperature_lag_1'] == 20
        assert result.iloc[1]['humidity_lag_1'] == 60
        assert result.iloc[3]['temperature_lag_1'] == 22
        assert result.iloc[3]['humidity_lag_1'] == 70

    def test_create_lag_features_default_lags(self):
        """Test that default lags [1, 3, 7] are used."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': list(range(10))
        })

        result = engineer.create_lag_features(df, ['temperature'])

        # Verify default lag columns are created
        assert 'temperature_lag_1' in result.columns
        assert 'temperature_lag_3' in result.columns
        assert 'temperature_lag_7' in result.columns

    def test_create_lag_features_missing_column(self):
        """Test that missing column raises error."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24]
        })

        with pytest.raises(ValueError, match="Columns not found"):
            engineer.create_lag_features(df, ['nonexistent_column'], [1])

    def test_create_lag_features_preserves_original(self):
        """Test that original DataFrame is not modified."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24]
        })

        original_columns = df.columns.tolist()
        result = engineer.create_lag_features(df, ['temperature'], [1])

        # Original DataFrame should be unchanged
        assert df.columns.tolist() == original_columns
        assert 'temperature_lag_1' not in df.columns

        # Result should have new columns
        assert 'temperature_lag_1' in result.columns


class TestFeatureEngineerRollingFeatures:
    """Test suite for rolling feature creation."""

    def test_create_rolling_features_basic(self):
        """Basic unit test for rolling feature creation."""
        engineer = FeatureEngineer()

        # Create test data with known values
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': [20, 22, 24, 26, 28, 30, 32, 34, 36, 38]
        })

        result = engineer.create_rolling_features(df, ['temperature'], [3])

        # Verify rolling columns are created
        assert 'temperature_rolling_mean_3' in result.columns
        assert 'temperature_rolling_std_3' in result.columns
        assert 'temperature_rolling_min_3' in result.columns
        assert 'temperature_rolling_max_3' in result.columns

        # Verify rolling mean values (window=3)
        # Index 0: mean([20]) = 20
        assert result.iloc[0]['temperature_rolling_mean_3'] == 20.0
        # Index 1: mean([20, 22]) = 21
        assert result.iloc[1]['temperature_rolling_mean_3'] == 21.0
        # Index 2: mean([20, 22, 24]) = 22
        assert result.iloc[2]['temperature_rolling_mean_3'] == 22.0
        # Index 3: mean([22, 24, 26]) = 24
        assert result.iloc[3]['temperature_rolling_mean_3'] == 24.0

        # Verify rolling min/max
        assert result.iloc[2]['temperature_rolling_min_3'] == 20.0
        assert result.iloc[2]['temperature_rolling_max_3'] == 24.0
        assert result.iloc[3]['temperature_rolling_min_3'] == 22.0
        assert result.iloc[3]['temperature_rolling_max_3'] == 26.0

    def test_create_rolling_features_multiple_windows(self):
        """Test rolling features with multiple window sizes."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': list(range(10, 20))
        })

        result = engineer.create_rolling_features(df, ['temperature'], [3, 5])

        # Verify both window sizes create columns
        assert 'temperature_rolling_mean_3' in result.columns
        assert 'temperature_rolling_mean_5' in result.columns
        assert 'temperature_rolling_std_3' in result.columns
        assert 'temperature_rolling_std_5' in result.columns

    def test_create_rolling_features_default_windows(self):
        """Test that default windows [7, 30] are used."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=35, freq='D'),
            'temperature': list(range(35))
        })

        result = engineer.create_rolling_features(df, ['temperature'])

        # Verify default window columns are created
        assert 'temperature_rolling_mean_7' in result.columns
        assert 'temperature_rolling_mean_30' in result.columns
        assert 'temperature_rolling_std_7' in result.columns
        assert 'temperature_rolling_std_30' in result.columns

    def test_create_rolling_features_multiple_columns(self):
        """Test rolling features for multiple columns."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': list(range(20, 30)),
            'humidity': list(range(60, 70))
        })

        result = engineer.create_rolling_features(df, ['temperature', 'humidity'], [3])

        # Verify both columns have rolling features
        assert 'temperature_rolling_mean_3' in result.columns
        assert 'humidity_rolling_mean_3' in result.columns
        assert 'temperature_rolling_std_3' in result.columns
        assert 'humidity_rolling_std_3' in result.columns

    def test_create_rolling_features_missing_column(self):
        """Test that missing column raises error."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24]
        })

        with pytest.raises(ValueError, match="Columns not found"):
            engineer.create_rolling_features(df, ['nonexistent_column'], [3])

    def test_create_rolling_features_preserves_original(self):
        """Test that original DataFrame is not modified."""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24]
        })

        original_columns = df.columns.tolist()
        result = engineer.create_rolling_features(df, ['temperature'], [3])

        # Original DataFrame should be unchanged
        assert df.columns.tolist() == original_columns
        assert 'temperature_rolling_mean_3' not in df.columns

        # Result should have new columns
        assert 'temperature_rolling_mean_3' in result.columns

    def test_create_rolling_features_std_calculation(self):
        """Test that rolling standard deviation is calculated correctly."""
        engineer = FeatureEngineer()

        # Use values with known std
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [10, 10, 10, 10, 10]  # Constant values, std should be 0
        })

        result = engineer.create_rolling_features(df, ['temperature'], [3])

        # Standard deviation of constant values should be 0
        assert result.iloc[2]['temperature_rolling_std_3'] == 0.0
        assert result.iloc[4]['temperature_rolling_std_3'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
