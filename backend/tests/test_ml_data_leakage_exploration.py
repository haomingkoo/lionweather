"""
Bug Condition Exploration Test - ML Data Leakage

This test demonstrates the data leakage bug in create_rolling_features().
CRITICAL: This test is EXPECTED TO FAIL on unfixed code - failure confirms the bug exists.

The bug: Rolling features at time t include the value at time t, causing future data
to leak into training features and violating temporal causality.

Expected behavior: Rolling features at time t should only use data from times < t.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.feature_engineer import FeatureEngineer


class TestMLDataLeakageExploration:
    """
    Bug Condition Exploration Test for ML Data Leakage (Bug 3)
    
    **Property 1: Bug Condition** - Rolling Features Leak Future Data
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists
    DO NOT attempt to fix the test or the code when it fails
    NOTE: This test encodes the expected behavior - it will validate the fix when it passes
    
    GOAL: Surface counterexamples that demonstrate rolling features include current value
    at time t (data leakage)
    
    Validates: Requirements 2.4
    """
    
    def test_rolling_features_data_leakage_simple_case(self):
        """
        Test that rolling features do NOT include the current value at time t.
        
        This is a scoped property test using a simple DataFrame with known values
        [20, 21, 22, 23, 24] to demonstrate the data leakage bug.
        
        EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
        - rolling_mean at index 2 includes value at index 2 (22)
        - rolling_mean at index 0 is NOT NaN (should be NaN due to shift)
        
        EXPECTED OUTCOME ON FIXED CODE: Test PASSES
        - rolling_mean at index 2 only uses values from indices 0, 1 (times < t)
        - rolling_mean at index 0 is NaN (due to shift(1))
        """
        engineer = FeatureEngineer()
        
        # Create simple DataFrame with known values
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
            'temperature': [20, 21, 22, 23, 24]
        })
        
        # Calculate 3-period rolling mean
        result = engineer.create_rolling_features(df, ['temperature'], [3])
        
        # CRITICAL ASSERTION 1: Rolling feature at index 0 should be NaN due to shift(1)
        # Without shift(1), this would be 20.0 (the value at index 0)
        # With shift(1), this should be NaN (no previous values to use)
        assert pd.isna(result.iloc[0]['temperature_rolling_mean_3']), \
            f"COUNTEREXAMPLE: rolling_mean at index 0 is {result.iloc[0]['temperature_rolling_mean_3']}, " \
            f"expected NaN. This indicates no shift(1) was applied (DATA LEAKAGE!)"
        
        # CRITICAL ASSERTION 2: Rolling feature at time t should only use data from times < t
        # At index 2 (time t=2):
        # - WITHOUT shift(1): rolling_mean uses [20, 21, 22] = 21.0 (includes current value 22 - LEAKAGE!)
        # - WITH shift(1): rolling_mean uses [20, 21] = 20.5 (only uses values from times < 2 - CORRECT!)
        
        # Calculate expected value WITH shift(1): mean of values at indices 0 and 1
        expected_mean_at_index_2 = (20 + 21) / 2  # = 20.5
        
        actual_mean_at_index_2 = result.iloc[2]['temperature_rolling_mean_3']
        
        assert actual_mean_at_index_2 == expected_mean_at_index_2, \
            f"COUNTEREXAMPLE: rolling_mean at index 2 is {actual_mean_at_index_2}, " \
            f"expected {expected_mean_at_index_2}. " \
            f"If actual is 21.0, it means the rolling mean includes the current value (22) at time t=2, " \
            f"which is DATA LEAKAGE! The rolling feature should only use values from times < t."
        
        # CRITICAL ASSERTION 3: Verify shift is applied to all rolling statistics
        # At index 1:
        # - WITHOUT shift(1): rolling_mean uses [20, 21] = 20.5
        # - WITH shift(1): rolling_mean uses [20] = 20.0
        expected_mean_at_index_1 = 20.0
        actual_mean_at_index_1 = result.iloc[1]['temperature_rolling_mean_3']
        
        assert actual_mean_at_index_1 == expected_mean_at_index_1, \
            f"COUNTEREXAMPLE: rolling_mean at index 1 is {actual_mean_at_index_1}, " \
            f"expected {expected_mean_at_index_1}. " \
            f"If actual is 20.5, it means shift(1) was not applied (DATA LEAKAGE!)"
        
        # CRITICAL ASSERTION 4: Verify shift is applied to std, min, max as well
        assert pd.isna(result.iloc[0]['temperature_rolling_std_3']), \
            "rolling_std at index 0 should be NaN due to shift(1)"
        assert pd.isna(result.iloc[0]['temperature_rolling_min_3']), \
            "rolling_min at index 0 should be NaN due to shift(1)"
        assert pd.isna(result.iloc[0]['temperature_rolling_max_3']), \
            "rolling_max at index 0 should be NaN due to shift(1)"
    
    def test_rolling_features_temporal_causality_violation(self):
        """
        Test that demonstrates temporal causality violation in rolling features.
        
        Temporal causality principle: Predictions at time t can only use data from times < t,
        never from t or future times.
        
        EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
        - Rolling features at time t include the value at time t (violates temporal causality)
        
        EXPECTED OUTCOME ON FIXED CODE: Test PASSES
        - Rolling features at time t only use data from times < t (maintains temporal causality)
        """
        engineer = FeatureEngineer()
        
        # Create DataFrame with sequential values for easy verification
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'temperature': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        })
        
        # Calculate 3-period rolling mean
        result = engineer.create_rolling_features(df, ['temperature'], [3])
        
        # At index 3 (time t=3, temperature=40):
        # - WITHOUT shift(1): rolling_mean uses [20, 30, 40] = 30.0 (includes current value 40 - LEAKAGE!)
        # - WITH shift(1): rolling_mean uses [10, 20, 30] = 20.0 (only uses values from times < 3 - CORRECT!)
        
        expected_mean_at_index_3 = (10 + 20 + 30) / 3  # = 20.0
        actual_mean_at_index_3 = result.iloc[3]['temperature_rolling_mean_3']
        
        assert actual_mean_at_index_3 == expected_mean_at_index_3, \
            f"COUNTEREXAMPLE: Temporal causality violation! " \
            f"rolling_mean at index 3 (time t=3, temperature=40) is {actual_mean_at_index_3}, " \
            f"expected {expected_mean_at_index_3}. " \
            f"If actual is 30.0, it means the rolling mean includes the current value (40) at time t=3, " \
            f"which violates temporal causality. The model would be using future data to predict the future!"
        
        # At index 5 (time t=5, temperature=60):
        # - WITHOUT shift(1): rolling_mean uses [40, 50, 60] = 50.0 (includes current value 60 - LEAKAGE!)
        # - WITH shift(1): rolling_mean uses [30, 40, 50] = 40.0 (only uses values from times < 5 - CORRECT!)
        
        expected_mean_at_index_5 = (30 + 40 + 50) / 3  # = 40.0
        actual_mean_at_index_5 = result.iloc[5]['temperature_rolling_mean_3']
        
        assert actual_mean_at_index_5 == expected_mean_at_index_5, \
            f"COUNTEREXAMPLE: Temporal causality violation! " \
            f"rolling_mean at index 5 (time t=5, temperature=60) is {actual_mean_at_index_5}, " \
            f"expected {expected_mean_at_index_5}. " \
            f"If actual is 50.0, it means the rolling mean includes the current value (60) at time t=5, " \
            f"which violates temporal causality."
    
    def test_rolling_features_min_max_leakage(self):
        """
        Test that rolling min and max also prevent data leakage.
        
        EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS
        - rolling_min and rolling_max at time t include the value at time t
        
        EXPECTED OUTCOME ON FIXED CODE: Test PASSES
        - rolling_min and rolling_max at time t only use data from times < t
        """
        engineer = FeatureEngineer()
        
        # Create DataFrame with values that make min/max easy to verify
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=6, freq='D'),
            'temperature': [15, 10, 25, 20, 30, 5]  # Varying values
        })
        
        # Calculate 3-period rolling min and max
        result = engineer.create_rolling_features(df, ['temperature'], [3])
        
        # At index 3 (time t=3, temperature=20):
        # - WITHOUT shift(1): rolling_min uses [10, 25, 20] = 10, rolling_max uses [10, 25, 20] = 25
        # - WITH shift(1): rolling_min uses [15, 10, 25] = 10, rolling_max uses [15, 10, 25] = 25
        
        # At index 4 (time t=4, temperature=30):
        # - WITHOUT shift(1): rolling_min uses [25, 20, 30] = 20, rolling_max uses [25, 20, 30] = 30 (LEAKAGE!)
        # - WITH shift(1): rolling_min uses [10, 25, 20] = 10, rolling_max uses [10, 25, 20] = 25 (CORRECT!)
        
        expected_min_at_index_4 = 10  # min of [10, 25, 20]
        expected_max_at_index_4 = 25  # max of [10, 25, 20]
        
        actual_min_at_index_4 = result.iloc[4]['temperature_rolling_min_3']
        actual_max_at_index_4 = result.iloc[4]['temperature_rolling_max_3']
        
        assert actual_min_at_index_4 == expected_min_at_index_4, \
            f"COUNTEREXAMPLE: rolling_min at index 4 is {actual_min_at_index_4}, " \
            f"expected {expected_min_at_index_4}. " \
            f"If actual is 20, it means the rolling min includes the current value (30) at time t=4 (DATA LEAKAGE!)"
        
        assert actual_max_at_index_4 == expected_max_at_index_4, \
            f"COUNTEREXAMPLE: rolling_max at index 4 is {actual_max_at_index_4}, " \
            f"expected {expected_max_at_index_4}. " \
            f"If actual is 30, it means the rolling max includes the current value (30) at time t=4 (DATA LEAKAGE!)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
