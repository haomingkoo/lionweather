"""
Bug Condition Exploration Test - Missing ML Training Infrastructure

**Property 1: Bug Condition** - ML Training Infrastructure Missing

This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

GOAL: Surface counterexamples that demonstrate ML training infrastructure is missing:
- Training script does NOT exist
- NEA forecast collection is NOT implemented
- ML Dashboard does NOT have methodology and metrics tabs

Expected Behavior (from design):
- Training script exists
- NEA forecast collection implemented
- ML Dashboard has methodology and metrics tabs

**Validates: Requirements 2.5, 2.6, 2.7, 2.8**
"""

import os
import pytest
from pathlib import Path


class TestMLTrainingInfrastructureBugCondition:
    """Test that demonstrates missing ML training infrastructure on unfixed code."""

    def test_training_script_exists(self):
        """
        Test that training script exists.
        
        Bug Condition: training_script_exists == false
        Expected Behavior: training script exists at lionweather/backend/train_initial_models.py
        
        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (proves training script is missing)
        """
        # Get the project root (lionweather directory)
        current_file = Path(__file__)
        backend_dir = current_file.parent.parent
        training_script_path = backend_dir / "train_initial_models.py"
        
        # Check if training script exists
        assert training_script_path.exists(), (
            f"Training script not found at {training_script_path}. "
            "Expected: training script exists to create initial ARIMA, SARIMA, Prophet models"
        )
        
        # Verify it's a valid Python file
        assert training_script_path.suffix == ".py", (
            f"Training script is not a Python file: {training_script_path}"
        )

    def test_nea_forecast_collection_implemented(self):
        """
        Test that NEA forecast collection is implemented in DataCollector.
        
        Bug Condition: nea_forecast_collection == false
        Expected Behavior: DataCollector has fetch_nea_forecast() method
        
        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (proves NEA forecast collection is missing)
        """
        from app.services.data_collector import DataCollector
        
        # Check if DataCollector has fetch_nea_forecast method
        assert hasattr(DataCollector, 'fetch_nea_forecast'), (
            "DataCollector does not have fetch_nea_forecast() method. "
            "Expected: method to fetch NEA 24-hour forecasts from "
            "https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hour-weather-forecast"
        )
        
        # Verify it's a callable method
        assert callable(getattr(DataCollector, 'fetch_nea_forecast')), (
            "fetch_nea_forecast is not a callable method"
        )

    def test_ml_dashboard_methodology_tab_exists(self):
        """
        Test that ML Dashboard has methodology tab component.
        
        Bug Condition: ml_dashboard_methodology_tab == false
        Expected Behavior: ML Dashboard has methodology tab showing data leakage prevention
        
        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (proves methodology tab is missing)
        """
        # Get the frontend directory
        current_file = Path(__file__)
        backend_dir = current_file.parent.parent
        project_root = backend_dir.parent
        frontend_dir = project_root / "frontend" / "src"
        
        # Look for methodology tab component (could be in components or pages)
        possible_paths = [
            frontend_dir / "components" / "MLMethodologyTab.jsx",
            frontend_dir / "components" / "MethodologyTab.jsx",
            frontend_dir / "pages" / "MLDashboard" / "MethodologyTab.jsx",
            frontend_dir / "components" / "ml" / "MethodologyTab.jsx",
        ]
        
        methodology_tab_exists = any(path.exists() for path in possible_paths)
        
        assert methodology_tab_exists, (
            f"ML Dashboard methodology tab component not found. Checked paths: "
            f"{[str(p) for p in possible_paths]}. "
            "Expected: component showing data leakage prevention techniques, "
            "train/test split dates, and temporal validation approach"
        )

    def test_ml_dashboard_performance_metrics_tab_exists(self):
        """
        Test that ML Dashboard has performance metrics tab component.
        
        Bug Condition: ml_dashboard_metrics_tab == false
        Expected Behavior: ML Dashboard has performance metrics tab showing MAE, RMSE, MAPE
        
        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (proves metrics tab is missing)
        """
        # Get the frontend directory
        current_file = Path(__file__)
        backend_dir = current_file.parent.parent
        project_root = backend_dir.parent
        frontend_dir = project_root / "frontend" / "src"
        
        # Look for performance metrics tab component
        possible_paths = [
            frontend_dir / "components" / "MLPerformanceMetricsTab.jsx",
            frontend_dir / "components" / "PerformanceMetricsTab.jsx",
            frontend_dir / "pages" / "MLDashboard" / "PerformanceMetricsTab.jsx",
            frontend_dir / "components" / "ml" / "PerformanceMetricsTab.jsx",
        ]
        
        metrics_tab_exists = any(path.exists() for path in possible_paths)
        
        assert metrics_tab_exists, (
            f"ML Dashboard performance metrics tab component not found. Checked paths: "
            f"{[str(p) for p in possible_paths]}. "
            "Expected: component showing MAE, RMSE, MAPE for each model, "
            "model rankings, and NEA comparison metrics"
        )

    def test_all_infrastructure_components_missing(self):
        """
        Comprehensive test that all ML training infrastructure components are missing.
        
        This test documents the complete bug condition state.
        
        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (proves all infrastructure is missing)
        """
        from app.services.data_collector import DataCollector
        
        # Get paths
        current_file = Path(__file__)
        backend_dir = current_file.parent.parent
        project_root = backend_dir.parent
        frontend_dir = project_root / "frontend" / "src"
        
        training_script_path = backend_dir / "train_initial_models.py"
        
        # Collect all missing components
        missing_components = []
        
        # Check training script
        if not training_script_path.exists():
            missing_components.append("Training script (train_initial_models.py)")
        
        # Check NEA forecast collection
        if not hasattr(DataCollector, 'fetch_nea_forecast'):
            missing_components.append("NEA forecast collection (DataCollector.fetch_nea_forecast)")
        
        # Check methodology tab
        methodology_paths = [
            frontend_dir / "components" / "MLMethodologyTab.jsx",
            frontend_dir / "components" / "MethodologyTab.jsx",
            frontend_dir / "pages" / "MLDashboard" / "MethodologyTab.jsx",
            frontend_dir / "components" / "ml" / "MethodologyTab.jsx",
        ]
        if not any(path.exists() for path in methodology_paths):
            missing_components.append("ML Dashboard Methodology Tab")
        
        # Check performance metrics tab
        metrics_paths = [
            frontend_dir / "components" / "MLPerformanceMetricsTab.jsx",
            frontend_dir / "components" / "PerformanceMetricsTab.jsx",
            frontend_dir / "pages" / "MLDashboard" / "PerformanceMetricsTab.jsx",
            frontend_dir / "components" / "ml" / "PerformanceMetricsTab.jsx",
        ]
        if not any(path.exists() for path in metrics_paths):
            missing_components.append("ML Dashboard Performance Metrics Tab")
        
        # Assert all components exist
        assert len(missing_components) == 0, (
            f"Missing ML training infrastructure components:\n" +
            "\n".join(f"  - {comp}" for comp in missing_components) +
            "\n\nExpected: All components should exist for complete ML training infrastructure"
        )
