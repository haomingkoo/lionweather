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


@router.get("/full-analysis")
async def get_full_analysis() -> Dict:
    """
    Return the full ML analysis JSON produced by train_full_analysis.py.

    Includes: EDA, ACF/PACF, FFT, spurious correlations, SHAP, loss curves,
    classification & regression benchmarks for all forecast horizons.

    Populated by running: python -m ml.train_full_analysis
    """
    from pathlib import Path

    analysis_path = Path(__file__).parent.parent.parent / "models" / "full_analysis.json"

    if not analysis_path.exists():
        return {
            "status": "not_trained",
            "message": "Full analysis not available yet. Run: cd backend && python -m ml.train_full_analysis",
            "data": None,
        }

    try:
        with open(analysis_path) as f:
            data = json.load(f)
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read full analysis: {e}")


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


# ---------------------------------------------------------------------------
# NEA text → 4-class rain category (same thresholds as ML training)
# ---------------------------------------------------------------------------
_NEA_TEXT_TO_CLASS = {
    # class 0 — No Rain
    "fair": 0, "fine": 0, "sunny": 0, "clear": 0,
    "fair and warm": 0, "partly cloudy": 0, "mostly cloudy": 0,
    "hazy": 0, "windy": 0, "breezy": 0,
    # class 1 — Light Rain
    "light rain": 1, "light showers": 1, "drizzle": 1, "mist": 1,
    "passing showers": 1, "isolated showers": 1,
    "showers": 1, "rain": 1,
    # class 2 — Heavy Rain
    "heavy rain": 2, "heavy showers": 2, "moderate rain": 2,
    # class 3 — Thundery Showers
    "thundery showers": 3, "heavy thundery showers": 3,
    "thunderstorm": 3, "thunderstorms": 3,
    "occasional showers with thunder": 3,
}

def _nea_text_to_class(description: str) -> Optional[int]:
    """Map NEA forecast text → rain category (0-3). Returns None if unknown."""
    if not description:
        return None
    d = description.lower().strip()
    # Exact match first
    if d in _NEA_TEXT_TO_CLASS:
        return _NEA_TEXT_TO_CLASS[d]
    # Keyword match
    if "thunder" in d:
        return 3
    if "heavy" in d and ("rain" in d or "shower" in d):
        return 2
    if "rain" in d or "shower" in d or "drizzle" in d:
        return 1
    if "fair" in d or "sunny" in d or "clear" in d or "fine" in d:
        return 0
    return None

def _mm_to_class(rainfall_mm: float) -> int:
    """Same thresholds as ML training script."""
    if rainfall_mm < 0.1:
        return 0
    elif rainfall_mm < 7.6:
        return 1
    elif rainfall_mm < 30.0:
        return 2
    else:
        return 3


@router.get("/nea-benchmark")
async def get_nea_benchmark() -> Dict:
    """
    Compare NEA official 24-hour forecasts against actual observed rainfall.

    Methodology (apples-to-apples):
    - Pull NEA forecasts from forecast_data (source_api = 'nea')
    - For each forecast period [target_time_start, target_time_end]:
        - Find ALL Singapore weather_records in that window
        - Take MAX rainfall across stations → actual rain category
    - Map NEA text description → rain category (same 4-class + binary thresholds as ML model)
    - Compute accuracy, precision, recall on both 4-class and binary (rain vs no-rain)

    Note: Requires forecast_data and weather_records to have overlapping timestamps.
    This accumulates as the app runs — more data = more reliable benchmark.
    """
    try:
        # 1. Pull NEA forecast periods
        forecasts = fetch_all("""
            SELECT target_time_start, target_time_end, forecast_description
            FROM forecast_data
            WHERE source_api = 'nea'
              AND forecast_description IS NOT NULL
            ORDER BY target_time_start
        """)

        if not forecasts:
            return {
                "status": "no_data",
                "message": (
                    "No NEA forecast records found in forecast_data. "
                    "The app needs to run for a while to accumulate forecast data. "
                    "Check /status to verify the forecast collector is running."
                ),
                "n_forecast_periods": 0,
            }

        # 2. For each forecast period, find actual max rainfall from weather_records
        matched = []
        skipped = 0

        for row in forecasts:
            t_start = row["target_time_start"]
            t_end   = row["target_time_end"]
            nea_text = row["forecast_description"]

            nea_class = _nea_text_to_class(nea_text)
            if nea_class is None:
                skipped += 1
                continue

            # Actual: max rainfall across ALL Singapore stations in this window
            actual_row = fetch_one("""
                SELECT MAX(rainfall) as max_rain
                FROM weather_records
                WHERE country = 'singapore'
                  AND timestamp >= :t_start
                  AND timestamp <  :t_end
            """, {"t_start": t_start, "t_end": t_end})

            if not actual_row or actual_row["max_rain"] is None:
                skipped += 1
                continue

            actual_class = _mm_to_class(float(actual_row["max_rain"]))
            matched.append((nea_class, actual_class))

        if not matched:
            return {
                "status": "insufficient_overlap",
                "message": (
                    "NEA forecasts found but no matching weather_records in the same time windows. "
                    f"Skipped {skipped} periods. Check that both collectors are running and "
                    "the database has data from the same time range."
                ),
                "n_forecast_periods": len(forecasts),
                "n_skipped": skipped,
            }

        # 3. Compute metrics
        n = len(matched)
        y_nea    = [x[0] for x in matched]
        y_actual = [x[1] for x in matched]

        # 4-class accuracy
        four_class_correct = sum(a == b for a, b in zip(y_nea, y_actual))
        four_class_accuracy = four_class_correct / n

        # Binary: 0 = no rain, 1 = any rain
        y_nea_bin    = [1 if c > 0 else 0 for c in y_nea]
        y_actual_bin = [1 if c > 0 else 0 for c in y_actual]
        binary_correct = sum(a == b for a, b in zip(y_nea_bin, y_actual_bin))
        binary_accuracy = binary_correct / n

        # Binary rain recall (did NEA predict rain when it actually rained?)
        actual_rain_periods = sum(1 for c in y_actual_bin if c == 1)
        nea_caught_rain = sum(1 for a, b in zip(y_nea_bin, y_actual_bin) if a == 1 and b == 1)
        rain_recall = nea_caught_rain / actual_rain_periods if actual_rain_periods > 0 else None

        # Binary rain precision (when NEA said rain, was it right?)
        nea_said_rain = sum(1 for c in y_nea_bin if c == 1)
        rain_precision = nea_caught_rain / nea_said_rain if nea_said_rain > 0 else None

        # False negative rate (NEA said dry, actually rained)
        false_negatives = sum(1 for a, b in zip(y_nea_bin, y_actual_bin) if a == 0 and b == 1)
        false_negative_rate = false_negatives / actual_rain_periods if actual_rain_periods > 0 else None

        # Per-class breakdown
        from collections import Counter
        nea_dist    = dict(Counter(y_nea))
        actual_dist = dict(Counter(y_actual))

        # 2×2 binary confusion matrix [[TN, FP], [FN, TP]]
        tn = sum(1 for a, b in zip(y_nea_bin, y_actual_bin) if a == 0 and b == 0)
        fp = sum(1 for a, b in zip(y_nea_bin, y_actual_bin) if a == 1 and b == 0)
        fn = false_negatives
        tp = nea_caught_rain
        binary_cm = [[tn, fp], [fn, tp]]

        return {
            "status": "ok",
            "n_matched_periods": n,
            "n_skipped": skipped,
            "note": (
                "Actual = MAX rainfall across all Singapore stations per NEA forecast window. "
                "This is the most conservative comparison: NEA predicts 'dry' but ANY station "
                "recording rain counts as actual rain."
            ),
            "four_class": {
                "accuracy": round(four_class_accuracy, 4),
                "correct": four_class_correct,
                "total": n,
                "nea_class_distribution": {str(k): v for k, v in sorted(nea_dist.items())},
                "actual_class_distribution": {str(k): v for k, v in sorted(actual_dist.items())},
            },
            "binary": {
                "accuracy": round(binary_accuracy, 4),
                "rain_precision": round(rain_precision, 4) if rain_precision is not None else None,
                "rain_recall": round(rain_recall, 4) if rain_recall is not None else None,
                "false_negative_rate": round(false_negative_rate, 4) if false_negative_rate is not None else None,
                "confusion_matrix": binary_cm,
                "n_actual_rain_periods": actual_rain_periods,
                "n_nea_predicted_rain": nea_said_rain,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NEA benchmark failed: {e}")
