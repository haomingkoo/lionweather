#!/usr/bin/env python3
"""
Model Registration Script

Registers trained ML models in the database with versioning support.
Stores model metadata, metrics, and configuration for tracking and comparison.
"""

import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_connection


def calculate_training_data_hash(training_data_path: Optional[str] = None) -> str:
    """
    Calculate SHA256 hash of training data.
    
    Used to detect when retraining is needed (data has changed).
    """
    if not training_data_path or not Path(training_data_path).exists():
        # Use timestamp as fallback
        return hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:16]
    
    # Calculate hash of file
    sha256 = hashlib.sha256()
    with open(training_data_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def register_model_version(
    model_name: str,
    semantic_version: str,
    model_path: str,
    config: Dict,
    metrics: Dict,
    features: List[str],
    notes: str = "",
    status: str = "testing"
) -> int:
    """
    Register a trained model version in the database.
    
    Args:
        model_name: Model identifier (e.g., "rainfall_classifier", "rainfall_regressor")
        semantic_version: Semantic version (e.g., "v1.0.0", "v1.2.3")
        model_path: Path to saved model file (.pkl)
        config: Model configuration (hyperparameters, settings)
        metrics: Performance metrics (MAE, RMSE, F1, etc.)
        features: List of features used
        notes: What changed in this version
        status: Model status ("testing", "active", "archived", "deprecated")
    
    Returns:
        model_id: Database ID of registered model
    """
    con = get_connection()
    cursor = con.cursor()
    
    # Calculate training data hash
    training_data_hash = calculate_training_data_hash()
    
    # Extract metrics
    mae = metrics.get('mae', metrics.get('test_set', {}).get('mae', 0))
    rmse = metrics.get('rmse', metrics.get('test_set', {}).get('rmse', 0))
    mape = metrics.get('mape', metrics.get('test_set', {}).get('mape', 0))
    
    # Insert model metadata
    cursor.execute("""
        INSERT INTO model_metadata (
            semantic_version, model_name, model_type, weather_parameter, country,
            version, hyperparameters, training_date, training_samples,
            validation_mae, validation_rmse, validation_mape, file_path,
            is_production, status, training_data_hash, feature_list,
            config_json, metrics_json, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        semantic_version,
        model_name,
        config.get('model_type', 'Prophet'),
        config.get('weather_parameter', 'rainfall'),
        config.get('country', 'Singapore'),
        semantic_version,  # version (legacy field)
        json.dumps(config.get('hyperparameters', {})),
        datetime.now().isoformat(),
        config.get('training_samples', 0),
        mae,
        rmse,
        mape if mape else 0,
        model_path,
        1 if status == 'active' else 0,
        status,
        training_data_hash,
        json.dumps(features),
        json.dumps(config),
        json.dumps(metrics),
        notes,
        datetime.now().isoformat()
    ))
    
    model_id = cursor.lastrowid
    con.commit()
    con.close()
    
    print(f"✓ Registered model: {model_name} {semantic_version} (ID: {model_id})")
    return model_id


def log_model_performance(
    model_version: str,
    model_name: str,
    horizon_hours: int,
    metrics: Dict
):
    """
    Log model performance metrics for time-series tracking.
    
    Args:
        model_version: Semantic version (e.g., "v1.0.0")
        model_name: Model identifier
        horizon_hours: Forecast horizon
        metrics: Performance metrics
    """
    con = get_connection()
    cursor = con.cursor()
    
    cursor.execute("""
        INSERT INTO model_performance_log (
            model_version, model_name, evaluation_date, horizon_hours,
            mae, rmse, f1_score, accuracy, precision, recall,
            n_samples, rain_events
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        model_version,
        model_name,
        datetime.now().isoformat(),
        horizon_hours,
        metrics.get('mae'),
        metrics.get('rmse'),
        metrics.get('f1_score'),
        metrics.get('accuracy'),
        metrics.get('precision'),
        metrics.get('recall'),
        metrics.get('n_samples'),
        metrics.get('rain_events')
    ))
    
    con.commit()
    con.close()
    
    print(f"✓ Logged performance: {model_name} {model_version} ({horizon_hours}h)")


def activate_model_version(model_version: str, model_name: str):
    """
    Set a model version as the active production model.
    
    Deactivates all other versions of the same model.
    """
    con = get_connection()
    cursor = con.cursor()
    
    # Deactivate all versions of this model
    cursor.execute("""
        UPDATE model_metadata
        SET is_production = 0, status = 'archived'
        WHERE model_name = ?
    """, (model_name,))
    
    # Activate the specified version
    cursor.execute("""
        UPDATE model_metadata
        SET is_production = 1, status = 'active'
        WHERE semantic_version = ? AND model_name = ?
    """, (model_version, model_name))
    
    con.commit()
    con.close()
    
    print(f"✓ Activated model: {model_name} {model_version}")


if __name__ == "__main__":
    print("Model Registration Script")
    print("=" * 60)
    print()
    print("This script registers trained ML models in the database.")
    print("Use this after training models with train_rainfall_*.py scripts.")
    print()
    print("Example usage:")
    print("  from ml.register_model import register_model_version")
    print("  register_model_version(...)")
