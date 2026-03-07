"""
Preservation Property Tests - Existing ML Infrastructure

**Property 2: Preservation** - Existing ML Components Unchanged

IMPORTANT: Follow observation-first methodology.
Observe behavior on UNFIXED code: existing ML infrastructure works correctly.
Write property-based test: for all ML operations using existing infrastructure,
results match original implementation.

EXPECTED OUTCOME ON UNFIXED CODE: Tests PASS (confirms baseline behavior to preserve)

**Validates: Requirements 3.4, 3.5**
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from pathlib import Path

from app.ml.prediction_engine import PredictionEngine
from app.ml.evaluation_service import EvaluationService
from app.ml.feature_engineer import FeatureEngineer
from app.ml.training_pipeline import TrainingPipeline


class TestExistingMLInfrastructurePreservation:
    """
    Test that existing ML infrastructure continues to work correctly after fixes.
    
    These tests capture the baseline behavior that must be preserved.
    """

    @given(
        y_true=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100),
        y_pred=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_evaluation_service_mae_calculation_preserved(self, y_true, y_pred):
        """
        Property: EvaluationService.calculate_mae() produces consistent results.
        
        For any valid y_true and y_pred arrays, MAE calculation should work correctly.
        This ensures the evaluation service continues to function after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Ensure arrays are same length
        min_len = min(len(y_true), len(y_pred))
        y_true = np.array(y_true[:min_len])
        y_pred = np.array(y_pred[:min_len])
        
        eval_service = EvaluationService()
        
        # Calculate MAE
        mae = eval_service.calculate_mae(y_true, y_pred)
        
        # Verify MAE is valid
        assert isinstance(mae, float), "MAE should be a float"
        assert mae >= 0, "MAE should be non-negative"
        assert not np.isnan(mae), "MAE should not be NaN"
        assert not np.isinf(mae), "MAE should not be infinite"
        
        # Verify MAE matches manual calculation
        expected_mae = np.mean(np.abs(y_true - y_pred))
        assert np.isclose(mae, expected_mae, rtol=1e-5), (
            f"MAE calculation mismatch: got {mae}, expected {expected_mae}"
        )

    @given(
        y_true=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100),
        y_pred=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_evaluation_service_rmse_calculation_preserved(self, y_true, y_pred):
        """
        Property: EvaluationService.calculate_rmse() produces consistent results.
        
        For any valid y_true and y_pred arrays, RMSE calculation should work correctly.
        This ensures the evaluation service continues to function after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Ensure arrays are same length
        min_len = min(len(y_true), len(y_pred))
        y_true = np.array(y_true[:min_len])
        y_pred = np.array(y_pred[:min_len])
        
        eval_service = EvaluationService()
        
        # Calculate RMSE
        rmse = eval_service.calculate_rmse(y_true, y_pred)
        
        # Verify RMSE is valid
        assert isinstance(rmse, float), "RMSE should be a float"
        assert rmse >= 0, "RMSE should be non-negative"
        assert not np.isnan(rmse), "RMSE should not be NaN"
        assert not np.isinf(rmse), "RMSE should not be infinite"
        
        # Verify RMSE matches manual calculation
        expected_rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        assert np.isclose(rmse, expected_rmse, rtol=1e-5), (
            f"RMSE calculation mismatch: got {rmse}, expected {expected_rmse}"
        )

    @given(
        num_rows=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_feature_engineer_temporal_features_preserved(self, num_rows):
        """
        Property: FeatureEngineer.create_temporal_features() produces consistent results.
        
        For any DataFrame with timestamp column, temporal features should be created correctly.
        This ensures temporal feature extraction continues to work after rolling feature fixes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Create sample DataFrame with timestamps
        start_date = datetime(2024, 1, 1)
        timestamps = [start_date + timedelta(hours=i) for i in range(num_rows)]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'temperature': np.random.uniform(20, 35, num_rows)
        })
        
        feature_engineer = FeatureEngineer()
        
        # Create temporal features
        result_df = feature_engineer.create_temporal_features(df)
        
        # Verify temporal features are created
        expected_columns = ['hour', 'day_of_week', 'month', 'season', 'is_weekend']
        for col in expected_columns:
            assert col in result_df.columns, f"Temporal feature '{col}' should be created"
        
        # Verify temporal features are correct
        assert result_df['hour'].min() >= 0, "Hour should be >= 0"
        assert result_df['hour'].max() <= 23, "Hour should be <= 23"
        assert result_df['day_of_week'].min() >= 0, "Day of week should be >= 0"
        assert result_df['day_of_week'].max() <= 6, "Day of week should be <= 6"
        assert result_df['month'].min() >= 1, "Month should be >= 1"
        assert result_df['month'].max() <= 12, "Month should be <= 12"
        assert result_df['season'].min() >= 0, "Season should be >= 0"
        assert result_df['season'].max() <= 3, "Season should be <= 3"
        assert result_df['is_weekend'].isin([0, 1]).all(), "is_weekend should be 0 or 1"

    @given(
        num_rows=st.integers(min_value=20, max_value=100),
        lag_periods=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_feature_engineer_lag_features_preserved(self, num_rows, lag_periods):
        """
        Property: FeatureEngineer.create_lag_features() produces consistent results.
        
        For any DataFrame and lag periods, lag features should be created correctly.
        This ensures lag feature creation continues to work after rolling feature fixes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Create sample DataFrame
        df = pd.DataFrame({
            'temperature': np.random.uniform(20, 35, num_rows),
            'humidity': np.random.uniform(50, 90, num_rows)
        })
        
        feature_engineer = FeatureEngineer()
        
        # Create lag features
        result_df = feature_engineer.create_lag_features(
            df, 
            columns=['temperature', 'humidity'], 
            lags=lag_periods
        )
        
        # Verify lag features are created
        for col in ['temperature', 'humidity']:
            for lag in lag_periods:
                lag_col = f"{col}_lag_{lag}"
                assert lag_col in result_df.columns, f"Lag feature '{lag_col}' should be created"
                
                # Verify lag values are correct (shifted by lag periods)
                # First 'lag' rows should be NaN
                assert result_df[lag_col].iloc[:lag].isna().all(), (
                    f"First {lag} rows of {lag_col} should be NaN"
                )
                
                # Verify lag relationship for non-NaN values
                if num_rows > lag:
                    # Check a few values to ensure lag is correct
                    for i in range(lag, min(lag + 5, num_rows)):
                        expected_value = df[col].iloc[i - lag]
                        actual_value = result_df[lag_col].iloc[i]
                        assert np.isclose(expected_value, actual_value, rtol=1e-5), (
                            f"Lag feature {lag_col} at index {i} should equal "
                            f"{col} at index {i - lag}"
                        )

    @given(
        num_rows=st.integers(min_value=50, max_value=200),
        test_size=st.floats(min_value=0.1, max_value=0.4)
    )
    @settings(max_examples=20, deadline=None)
    def test_training_pipeline_train_test_split_preserved(self, num_rows, test_size):
        """
        Property: TrainingPipeline.train_test_split() produces consistent results.
        
        For any DataFrame and test_size, train/test split should maintain temporal order.
        This ensures the training pipeline continues to work after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Create sample DataFrame with timestamps
        start_date = datetime(2024, 1, 1)
        timestamps = [start_date + timedelta(hours=i) for i in range(num_rows)]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'temperature': np.random.uniform(20, 35, num_rows)
        })
        
        pipeline = TrainingPipeline()
        
        # Perform train/test split
        train_df, test_df = pipeline.train_test_split(df, test_size=test_size)
        
        # Verify split sizes (allow for rounding differences)
        assert len(train_df) + len(test_df) == num_rows, (
            f"Train + test should equal total rows: {len(train_df)} + {len(test_df)} != {num_rows}"
        )
        
        # Verify test size is approximately correct (within 1 row due to rounding)
        expected_test_size = int(num_rows * test_size)
        assert abs(len(test_df) - expected_test_size) <= 1, (
            f"Test set size should be approximately {expected_test_size}, got {len(test_df)}"
        )
        
        # Verify temporal order is maintained (train comes before test)
        if 'timestamp' in train_df.columns and 'timestamp' in test_df.columns:
            last_train_time = train_df['timestamp'].max()
            first_test_time = test_df['timestamp'].min()
            assert last_train_time <= first_test_time, (
                "Train set should come before test set in temporal order"
            )

    @given(
        y_true=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100),
        y_pred=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=10, max_size=100)
    )
    @settings(max_examples=20, deadline=None)
    def test_training_pipeline_calculate_metrics_preserved(self, y_true, y_pred):
        """
        Property: TrainingPipeline.calculate_metrics() produces consistent results.
        
        For any y_true and y_pred arrays, metrics calculation should work correctly.
        This ensures the training pipeline metrics continue to work after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Ensure arrays are same length
        min_len = min(len(y_true), len(y_pred))
        y_true = np.array(y_true[:min_len])
        y_pred = np.array(y_pred[:min_len])
        
        pipeline = TrainingPipeline()
        
        # Calculate metrics
        metrics = pipeline.calculate_metrics(y_true, y_pred)
        
        # Verify metrics dictionary structure
        assert isinstance(metrics, dict), "Metrics should be a dictionary"
        assert 'mae' in metrics, "Metrics should include MAE"
        assert 'rmse' in metrics, "Metrics should include RMSE"
        assert 'mape' in metrics, "Metrics should include MAPE"
        
        # Verify metrics are valid
        for metric_name, metric_value in metrics.items():
            assert isinstance(metric_value, (int, float)), (
                f"Metric {metric_name} should be numeric"
            )
            assert not np.isnan(metric_value), (
                f"Metric {metric_name} should not be NaN"
            )
            assert not np.isinf(metric_value), (
                f"Metric {metric_name} should not be infinite"
            )

    def test_prediction_engine_initialization_preserved(self):
        """
        Property: PredictionEngine can be initialized without errors.
        
        This ensures the prediction engine continues to work after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Initialize prediction engine
        engine = PredictionEngine()
        
        # Verify initialization
        assert engine is not None, "PredictionEngine should initialize"
        assert hasattr(engine, 'model_dir'), "PredictionEngine should have model_dir attribute"
        assert hasattr(engine, 'load_production_model'), (
            "PredictionEngine should have load_production_model method"
        )
        assert hasattr(engine, 'predict_24_hours'), (
            "PredictionEngine should have predict_24_hours method"
        )
        assert hasattr(engine, 'predict_7_days'), (
            "PredictionEngine should have predict_7_days method"
        )

    def test_training_pipeline_initialization_preserved(self):
        """
        Property: TrainingPipeline can be initialized without errors.
        
        This ensures the training pipeline continues to work after infrastructure changes.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Initialize training pipeline
        pipeline = TrainingPipeline()
        
        # Verify initialization
        assert pipeline is not None, "TrainingPipeline should initialize"
        assert hasattr(pipeline, 'model_dir'), "TrainingPipeline should have model_dir attribute"
        assert hasattr(pipeline, 'train_test_split'), (
            "TrainingPipeline should have train_test_split method"
        )
        assert hasattr(pipeline, 'calculate_metrics'), (
            "TrainingPipeline should have calculate_metrics method"
        )
