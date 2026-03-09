"""
Fast re-benchmark script.
Loads existing trained models + cached parquet data, re-runs both NEA benchmarks:
  - 6h regional (island-wide majority vote, apples-to-apples)
  - 2h per-area (NEA area-level accuracy + island-wide aggregation for ML comparison)

Updates full_analysis.json with corrected results.

Run from backend/:
    source .venv/bin/activate && python rebenchmark.py
"""
import json
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))

import joblib
import pandas as pd
import numpy as np

from ml.train_full_analysis import (
    load_hourly_series,
    make_features,
    load_regional_rainfall_6h,
    load_nea_forecasts_6h,
    load_nea_forecasts_2h,
    load_station_rainfall_2h,
    compute_nea_regional_benchmark,
    compute_nea_2h_area_benchmark,
    TRAIN_YEARS, VAL_YEAR, TEST_YEAR, BOUNDS, HORIZONS,
)

MODELS_DIR = "models"
JSON_PATH  = os.path.join(MODELS_DIR, "full_analysis.json")


def load_existing_models():
    cls4_models = {}
    cls3_models = {}
    for h in HORIZONS:
        p4 = os.path.join(MODELS_DIR, f"rainfall_cls_{h}h.joblib")
        p3 = os.path.join(MODELS_DIR, f"rainfall_cls3_{h}h.joblib")
        if os.path.exists(p4):
            obj = joblib.load(p4)
            cls4_models[h] = obj["model"] if isinstance(obj, dict) else obj
            logger.info(f"  Loaded 4-class h={h}h model")
        if os.path.exists(p3):
            obj = joblib.load(p3)
            cls3_models[h] = obj["model"] if isinstance(obj, dict) else obj
            logger.info(f"  Loaded 3-class h={h}h model")
    return cls4_models, cls3_models


def main():
    all_years = TRAIN_YEARS + [VAL_YEAR, TEST_YEAR]

    logger.info("Loading station data from parquet cache...")
    rain_h = load_hourly_series("rainfall",    "HistoricalRainfallacrossSingapore{year}.csv",        all_years, BOUNDS["rainfall"],    agg="sum")
    temp_h = load_hourly_series("temperature", "HistoricalAirTemperatureacrossSingapore{year}.csv",  all_years, BOUNDS["temperature"], agg="mean")
    hum_h  = load_hourly_series("humidity",    "HistoricalRelativeHumidityacrossSingapore{year}.csv",all_years, BOUNDS["humidity"],    agg="mean")
    wind_h = load_hourly_series("wind_speed",  "HistoricalWindSpeedacrossSingapore{year}.csv",       all_years, BOUNDS["wind_speed"],  agg="mean")

    logger.info("Loading external features...")
    ext_df = None
    try:
        from fetch_external_features import load_all_external_features
        ext_df = load_all_external_features()
        logger.info(f"  External features: {len(ext_df)} rows, {len(ext_df.columns)} cols")
    except Exception as e:
        logger.warning(f"  External features unavailable ({e}) — continuing without them")

    logger.info("Building feature matrix...")
    feat_df = make_features(rain_h, temp_h, hum_h, wind_h, HORIZONS, ext_df=ext_df)

    # Feature columns: same logic as training
    feature_cols = [c for c in feat_df.columns
                    if not c.startswith("target_")
                    and c not in ("rainfall", "temperature", "humidity", "wind_speed")]

    logger.info("Loading existing trained models...")
    cls4_models, cls3_models = load_existing_models()
    if not cls4_models or not cls3_models:
        logger.error("No models found in models/. Run train_full_analysis first.")
        sys.exit(1)

    # ---- 6h regional benchmark ----
    logger.info("\nRunning NEA 6h regional benchmark...")
    regional_rain = load_regional_rainfall_6h(all_years)
    nea_6h        = load_nea_forecasts_6h(all_years)
    benchmark_6h  = compute_nea_regional_benchmark(
        regional_rain, nea_6h, feat_df, cls4_models, cls3_models, feature_cols, TEST_YEAR
    )

    for cls_key in ["class3", "class4"]:
        iw = benchmark_6h["overall"].get(cls_key, {}).get("island_wide", {})
        n  = iw.get("n_samples", "?")
        nea_acc = iw.get("nea", {}).get("accuracy")
        ml_acc  = iw.get("ml_island_wide", {}).get("accuracy")
        ens_acc = iw.get("ensemble_60ml_40nea", {}).get("accuracy")
        nea_f1  = iw.get("nea", {}).get("report", {}).get("macro avg", {}).get("f1-score")
        ml_f1   = iw.get("ml_island_wide", {}).get("report", {}).get("macro avg", {}).get("f1-score")
        logger.info(f"[6h {cls_key} island-wide | n={n}]")
        logger.info(f"  NEA acc={nea_acc} macro_f1={nea_f1:.3f}" if nea_f1 else f"  NEA acc={nea_acc}")
        logger.info(f"  ML  acc={ml_acc}  macro_f1={ml_f1:.3f}" if ml_f1 else f"  ML  acc={ml_acc}")
        logger.info(f"  Ens acc={ens_acc}")

    # ---- 2h area benchmark ----
    logger.info("\nRunning NEA 2h per-area benchmark...")
    nea_2h          = load_nea_forecasts_2h(all_years)
    station_rain_2h = load_station_rainfall_2h(all_years)
    benchmark_2h    = compute_nea_2h_area_benchmark(
        nea_2h, station_rain_2h, feat_df, cls4_models, cls3_models, feature_cols, TEST_YEAR
    )

    for cls_key in ["class3", "class4"]:
        ov = benchmark_2h["overall"].get(cls_key, {})
        per_area = ov.get("per_area_nea", {})
        iw       = ov.get("island_wide", {})
        n_area   = ov.get("n_area_period_samples", "?")
        nea_area_acc = per_area.get("accuracy")
        iw_nea_acc   = iw.get("nea", {}).get("accuracy")
        iw_ml_acc    = iw.get("ml_island_wide", {}).get("accuracy")
        logger.info(f"[2h {cls_key}]")
        logger.info(f"  NEA per-area acc={nea_area_acc} (n={n_area})")
        logger.info(f"  NEA island-wide acc={iw_nea_acc} | ML island-wide acc={iw_ml_acc}")

    # Update full_analysis.json
    with open(JSON_PATH) as f:
        analysis = json.load(f)
    analysis["nea_benchmark"]    = benchmark_6h
    analysis["nea_2h_benchmark"] = benchmark_2h
    with open(JSON_PATH, "w") as f:
        json.dump(analysis, f, indent=2)
    logger.info(f"\nUpdated {JSON_PATH}")


if __name__ == "__main__":
    main()
