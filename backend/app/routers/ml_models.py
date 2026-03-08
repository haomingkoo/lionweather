"""
API endpoints for ML model versioning and performance tracking.

Provides web-hosted access to:
- Model versions and metadata
- Performance metrics history
- Model comparison
- Version activation

All endpoints are publicly accessible (read-only, no auth required).
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
import json
import logging

from app.db.database import fetch_all, fetch_one, execute_sql

router = APIRouter(prefix="/api/ml", tags=["ml-models"])
logger = logging.getLogger(__name__)


@router.get("/versions")
async def list_model_versions(
    model_name: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict]:
    """
    List all model versions with metadata.
    
    Args:
        model_name: Filter by model name (optional)
        status: Filter by status (optional): "active", "testing", "archived", "deprecated"
    
    Returns:
        List of model versions with metadata
    """
    query = "SELECT * FROM model_metadata WHERE 1=1"
    params = []
    
    if model_name:
        query += " AND model_name = ?"
        params.append(model_name)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    
    rows = fetch_all(query, params if params else None)
    
    versions = []
    for row in rows:
        versions.append({
            "id": row[0],
            "semantic_version": row[1],
            "model_name": row[2],
            "model_type": row[3],
            "weather_parameter": row[4],
            "country": row[5],
            "training_date": row[7],
            "training_samples": row[8],
            "validation_mae": row[9],
            "validation_rmse": row[10],
            "validation_mape": row[11],
            "status": row[14],
            "notes": row[19],
            "created_at": row[20]
        })
    
    return versions


@router.get("/versions/{version}")
async def get_model_version(version: str, model_name: Optional[str] = None) -> Dict:
    """
    Get detailed information for a specific model version.
    
    Args:
        version: Semantic version (e.g., "v1.0.0")
        model_name: Model name (optional, for disambiguation)
    
    Returns:
        Full model metadata including config, metrics, and features
    """
    query = "SELECT * FROM model_metadata WHERE semantic_version = ?"
    params = [version]
    
    if model_name:
        query += " AND model_name = ?"
        params.append(model_name)
    
    row = fetch_one(query, params)
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")
    
    return {
        "id": row[0],
        "semantic_version": row[1],
        "model_name": row[2],
        "model_type": row[3],
        "weather_parameter": row[4],
        "country": row[5],
        "hyperparameters": json.loads(row[6]) if row[6] else {},
        "training_date": row[7],
        "training_samples": row[8],
        "validation_mae": row[9],
        "validation_rmse": row[10],
        "validation_mape": row[11],
        "file_path": row[12],
        "is_production": bool(row[13]),
        "status": row[14],
        "training_data_hash": row[15],
        "feature_list": json.loads(row[16]) if row[16] else [],
        "config": json.loads(row[17]) if row[17] else {},
        "metrics": json.loads(row[18]) if row[18] else {},
        "notes": row[19],
        "created_at": row[20]
    }


@router.get("/versions/{version}/metrics")
async def get_version_metrics(version: str, model_name: Optional[str] = None) -> Dict:
    """
    Get performance metrics for a specific model version.
    
    Returns metrics by horizon from the performance log.
    """
    query = """
        SELECT horizon_hours, mae, rmse, f1_score, accuracy, precision, recall,
               n_samples, rain_events, evaluation_date
        FROM model_performance_log
        WHERE model_version = ?
    """
    params = [version]
    
    if model_name:
        query += " AND model_name = ?"
        params.append(model_name)
    
    query += " ORDER BY horizon_hours, evaluation_date DESC"
    
    rows = fetch_all(query, params)
    
    if not rows:
        # Try to get metrics from model_metadata
        version_data = await get_model_version(version, model_name)
        return {
            "version": version,
            "metrics_source": "model_metadata",
            "metrics": version_data.get("metrics", {})
        }
    
    # Group by horizon
    by_horizon = {}
    for row in rows:
        horizon = row[0]
        if horizon not in by_horizon:
            by_horizon[horizon] = []
        
        by_horizon[horizon].append({
            "mae": row[1],
            "rmse": row[2],
            "f1_score": row[3],
            "accuracy": row[4],
            "precision": row[5],
            "recall": row[6],
            "n_samples": row[7],
            "rain_events": row[8],
            "evaluation_date": row[9]
        })
    
    return {
        "version": version,
        "metrics_by_horizon": by_horizon
    }


@router.get("/performance-history")
async def get_performance_history(
    model_name: Optional[str] = None,
    horizon_hours: Optional[int] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Get historical performance data across all versions.
    
    Returns time series of metrics for charting and comparison.
    
    Args:
        model_name: Filter by model name (optional)
        horizon_hours: Filter by horizon (optional)
        limit: Maximum number of records to return
    """
    query = """
        SELECT model_version, model_name, evaluation_date, horizon_hours,
               mae, rmse, f1_score, accuracy, precision, recall
        FROM model_performance_log
        WHERE 1=1
    """
    params = []
    
    if model_name:
        query += " AND model_name = ?"
        params.append(model_name)
    
    if horizon_hours:
        query += " AND horizon_hours = ?"
        params.append(horizon_hours)
    
    query += " ORDER BY evaluation_date DESC LIMIT ?"
    params.append(limit)
    
    rows = fetch_all(query, params if params else None)
    
    history = []
    for row in rows:
        history.append({
            "model_version": row[0],
            "model_name": row[1],
            "evaluation_date": row[2],
            "horizon_hours": row[3],
            "mae": row[4],
            "rmse": row[5],
            "f1_score": row[6],
            "accuracy": row[7],
            "precision": row[8],
            "recall": row[9]
        })
    
    return history


@router.get("/current-model")
async def get_current_model(model_name: str) -> Dict:
    """
    Get the currently active production model.
    
    Args:
        model_name: Model name (e.g., "rainfall_classifier", "rainfall_regressor")
    
    Returns:
        Active model metadata
    """
    row = fetch_one("""
        SELECT * FROM model_metadata
        WHERE model_name = ? AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    """, [model_name])
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No active model found for {model_name}. Train and activate a model first."
        )
    
    return {
        "semantic_version": row[1],
        "model_name": row[2],
        "model_type": row[3],
        "training_date": row[7],
        "training_samples": row[8],
        "validation_mae": row[9],
        "validation_rmse": row[10],
        "status": row[14],
        "notes": row[19],
        "created_at": row[20]
    }


@router.post("/versions/{version}/activate")
async def activate_model(version: str, model_name: str) -> Dict:
    """
    Set a model version as the active production model.
    
    Deactivates all other versions of the same model.
    
    Args:
        version: Semantic version to activate
        model_name: Model name
    
    Returns:
        Success message
    """
    # Check if version exists
    row = fetch_one("""
        SELECT id FROM model_metadata
        WHERE semantic_version = ? AND model_name = ?
    """, [version, model_name])
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Model version {version} for {model_name} not found"
        )
    
    # Deactivate all versions
    execute_sql("""
        UPDATE model_metadata
        SET is_production = 0, status = 'archived'
        WHERE model_name = ?
    """, [model_name])
    
    # Activate specified version
    execute_sql("""
        UPDATE model_metadata
        SET is_production = 1, status = 'active'
        WHERE semantic_version = ? AND model_name = ?
    """, [version, model_name])
    
    logger.info(f"Activated model: {model_name} {version}")
    
    return {
        "success": True,
        "message": f"Model {model_name} {version} is now active",
        "model_name": model_name,
        "version": version
    }


@router.get("/compare/{version1}/{version2}")
async def compare_models(
    version1: str,
    version2: str,
    model_name: Optional[str] = None
) -> Dict:
    """
    Compare two model versions side-by-side.
    
    Args:
        version1: First version to compare
        version2: Second version to compare
        model_name: Model name (optional)
    
    Returns:
        Side-by-side comparison of metrics and configuration
    """
    model1 = await get_model_version(version1, model_name)
    model2 = await get_model_version(version2, model_name)
    
    # Calculate performance delta
    mae_delta = model2['validation_mae'] - model1['validation_mae']
    rmse_delta = model2['validation_rmse'] - model1['validation_rmse']
    
    mae_improvement = (mae_delta / model1['validation_mae']) * 100 if model1['validation_mae'] > 0 else 0
    rmse_improvement = (rmse_delta / model1['validation_rmse']) * 100 if model1['validation_rmse'] > 0 else 0
    
    return {
        "version1": {
            "version": version1,
            "mae": model1['validation_mae'],
            "rmse": model1['validation_rmse'],
            "training_samples": model1['training_samples'],
            "training_date": model1['training_date'],
            "features": model1['feature_list']
        },
        "version2": {
            "version": version2,
            "mae": model2['validation_mae'],
            "rmse": model2['validation_rmse'],
            "training_samples": model2['training_samples'],
            "training_date": model2['training_date'],
            "features": model2['feature_list']
        },
        "delta": {
            "mae_delta": mae_delta,
            "rmse_delta": rmse_delta,
            "mae_improvement_pct": mae_improvement,
            "rmse_improvement_pct": rmse_improvement,
            "better_model": version2 if mae_delta < 0 else version1,
            "interpretation": f"Version {version2} is {'better' if mae_delta < 0 else 'worse'} by {abs(mae_improvement):.1f}%"
        }
    }


@router.get("/benchmark")
async def get_forecast_benchmark() -> Dict:
    """
    Return the latest forecast benchmark report comparing our ML model against
    NEA official forecast on the 2024 held-out test set.

    Also includes ACF/PACF analysis results and training metadata.
    Populated after running: python -m ml.train_rainfall_forecast
    """
    import os
    from pathlib import Path

    bench_path = Path(__file__).parent.parent.parent / "models" / "forecast_benchmark.json"

    if not bench_path.exists():
        return {
            "status": "not_trained",
            "message": "Benchmark not available yet. Run: python -m ml.train_rainfall_forecast",
            "data": None,
        }

    try:
        with open(bench_path) as f:
            data = json.load(f)
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read benchmark: {e}")


@router.get("/data-sanity")
async def get_data_sanity_check() -> Dict:
    """
    Run a sanity check on the weather_data table:
    - Row counts per country (expect roughly equal if polling is balanced)
    - Latest timestamp per country
    - Missing variable rates (null temperature, rainfall, humidity)
    - Suspicious consecutive identical values
    """
    try:
        # Count per country
        country_counts = fetch_all(
            "SELECT country, COUNT(*) as cnt FROM weather_data GROUP BY country ORDER BY cnt DESC"
        )

        # Latest timestamp per country
        latest_ts = fetch_all(
            "SELECT country, MAX(CAST(timestamp AS TEXT)) as latest FROM weather_data GROUP BY country"
        )

        # Missing rates
        missing_temp = fetch_one(
            "SELECT COUNT(*) FROM weather_data WHERE temperature IS NULL OR temperature = 0"
        )
        missing_rain = fetch_one(
            "SELECT COUNT(*) FROM weather_data WHERE rainfall IS NULL"
        )
        total = fetch_one("SELECT COUNT(*) FROM weather_data")

        total_rows = total[0] if total else 0

        result = {
            "total_rows": total_rows,
            "by_country": {r[0]: r[1] for r in (country_counts or [])},
            "latest_by_country": {r[0]: r[1] for r in (latest_ts or [])},
            "missing_rates": {
                "temperature_null_or_zero": round(100 * (missing_temp[0] if missing_temp else 0) / max(1, total_rows), 2),
                "rainfall_null": round(100 * (missing_rain[0] if missing_rain else 0) / max(1, total_rows), 2),
            },
            "balance_check": {},
        }

        # Balance: flag if any country has <10% of max country's count
        if result["by_country"]:
            max_count = max(result["by_country"].values())
            for country, count in result["by_country"].items():
                pct = 100 * count / max_count
                result["balance_check"][country] = {
                    "count": count,
                    "pct_of_max": round(pct, 1),
                    "status": "ok" if pct >= 10 else "WARNING: under-represented",
                }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sanity check failed: {e}")
