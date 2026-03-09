"""
Fast re-benchmark script.
Loads existing trained models + cached parquet data, re-runs only the NEA benchmark
with the corrected island-wide aggregation methodology, and updates full_analysis.json.

Run from backend/:
    source .venv/bin/activate && python rebenchmark.py
"""
import json
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add backend root to path so ml.train_full_analysis imports work
sys.path.insert(0, os.path.dirname(__file__))

import joblib
import pandas as pd
import numpy as np

from ml.train_full_analysis import (
    load_hourly_series,
    load_external_features,
    load_nea_forecast_csvs,
    load_regional_rainfall,
    make_features,
    compute_nea_benchmark,
    TRAIN_YEARS, VAL_YEAR, TEST_YEAR, BOUNDS,
)

MODELS_DIR = "models"
JSON_PATH  = os.path.join(MODELS_DIR, "full_analysis.json")

def load_existing_models():
    models4 = {}
    models3 = {}
    for h in [1, 3, 6, 12]:
        p4 = os.path.join(MODELS_DIR, f"rainfall_cls_{h}h.joblib")
        p3 = os.path.join(MODELS_DIR, f"rainfall_cls3_{h}h.joblib")
        if os.path.exists(p4):
            models4[h] = joblib.load(p4)
            logger.info(f"  Loaded 4-class h={h}h model")
        if os.path.exists(p3):
            models3[h] = joblib.load(p3)
            logger.info(f"  Loaded 3-class h={h}h model")
    return models4, models3


def main():
    all_years = TRAIN_YEARS + [VAL_YEAR, TEST_YEAR]

    logger.info("Loading station data from parquet cache...")
    rain_h = load_hourly_series("rainfall",    "HistoricalRainfallacrossSingapore{year}.csv",        all_years, BOUNDS["rainfall"],    agg="sum")
    temp_h = load_hourly_series("temperature", "HistoricalAirTemperatureacrossSingapore{year}.csv",  all_years, BOUNDS["temperature"], agg="mean")
    hum_h  = load_hourly_series("humidity",    "HistoricalRelativeHumidityacrossSingapore{year}.csv",all_years, BOUNDS["humidity"],    agg="mean")
    wind_h = load_hourly_series("wind_speed",  "HistoricalWindSpeedacrossSingapore{year}.csv",       all_years, BOUNDS["wind_speed"],  agg="mean")

    logger.info("Loading external features...")
    ext_df = load_external_features()

    logger.info("Building feature matrix for test year...")
    feat_df = make_features(rain_h, temp_h, hum_h, wind_h, ext_df=ext_df)
    feat_df = feat_df[feat_df.index.year == TEST_YEAR].copy()

    # Get feature columns (same logic as training: drop target/non-feature cols)
    drop_cols = [c for c in feat_df.columns if c.startswith("target_")]
    feature_cols = [c for c in feat_df.columns if c not in drop_cols and feat_df[c].dtype in [float, int, "float64", "int64"]]

    logger.info("Loading regional rainfall and NEA forecasts...")
    regional_rain = load_regional_rainfall(all_years)
    nea_fcst      = load_nea_forecast_csvs(all_years)

    logger.info("Loading existing trained models...")
    cls4_models, cls3_models = load_existing_models()
    if not cls4_models or not cls3_models:
        logger.error("No models found in models/. Run train_full_analysis first.")
        sys.exit(1)

    logger.info("Running corrected island-wide benchmark...")
    benchmark = compute_nea_benchmark(
        regional_rain, nea_fcst, feat_df, cls4_models, cls3_models, feature_cols, TEST_YEAR
    )

    # Print summary
    for cls_key in ["class3", "class4"]:
        iw = benchmark["overall"].get(cls_key, {}).get("island_wide", {})
        nea_acc = iw.get("nea", {}).get("accuracy")
        ml_acc  = iw.get("ml_island_wide", {}).get("accuracy")
        ens_acc = iw.get("ensemble_60ml_40nea", {}).get("accuracy")
        n       = iw.get("n_samples", "?")
        nea_f1  = iw.get("nea", {}).get("report", {}).get("macro avg", {}).get("f1-score")
        ml_f1   = iw.get("ml_island_wide", {}).get("report", {}).get("macro avg", {}).get("f1-score")
        ens_f1  = iw.get("ensemble_60ml_40nea", {}).get("report", {}).get("macro avg", {}).get("f1-score")
        logger.info(f"[{cls_key} island-wide | n={n}]")
        logger.info(f"  NEA      acc={nea_acc} macro_f1={nea_f1:.3f}" if nea_f1 else f"  NEA acc={nea_acc}")
        logger.info(f"  ML       acc={ml_acc}  macro_f1={ml_f1:.3f}" if ml_f1 else f"  ML  acc={ml_acc}")
        logger.info(f"  Ensemble acc={ens_acc} macro_f1={ens_f1:.3f}" if ens_f1 else f"  Ens acc={ens_acc}")

    # Update full_analysis.json
    with open(JSON_PATH) as f:
        analysis = json.load(f)
    analysis["nea_benchmark"] = benchmark
    with open(JSON_PATH, "w") as f:
        json.dump(analysis, f, indent=2)
    logger.info(f"Updated {JSON_PATH}")


if __name__ == "__main__":
    main()
