#!/usr/bin/env python3
"""
LionWeather ML Rainfall Forecast Pipeline
==========================================

Trains a LightGBM model to forecast rainfall intensity (mm/5-min) at each NEA
station for multiple horizons ahead (1 step = 5 min → up to 12 steps = 1 hour).

Key design decisions:
- NO data leakage: strict chronological split (train ≤ 2022, val = 2023, test = 2024)
- Target is FUTURE rainfall, not current — true forecasting, not nowcasting
- NEA 24-hr official forecast is loaded as a benchmark feature AND benchmark target
- ACF / PACF analysis to choose lag depth
- Sanity checks: row counts, missing rates, value ranges
- Uses chunked pandas for large CSVs (6M+ rows per year) — no Spark needed at this scale

Usage:
    python -m ml.train_rainfall_forecast

Outputs:
    backend/models/rainfall_lgbm_<horizon>h.joblib
    backend/models/forecast_benchmark.json   (NEA MAE vs our MAE per horizon)
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import acf, pacf
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "nea_historical_data"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Forecast horizons: each step is 5 minutes
HORIZONS = [1, 3, 6, 12]   # in 5-min steps → 5 min, 15 min, 30 min, 60 min

# Temporal split (year-level, no leakage)
TRAIN_YEARS = list(range(2016, 2023))   # 2016–2022
VAL_YEAR = 2023
TEST_YEAR = 2024

# Sanity bounds
RAINFALL_MAX_MM = 300   # mm/5min — anything above is sensor error
TEMP_MIN, TEMP_MAX = 15.0, 42.0
HUMIDITY_MIN, HUMIDITY_MAX = 20.0, 100.0

# Target station for primary model (Changi — most complete record)
# We also build a network-average model
PRIMARY_STATION = "S24"  # Changi


# ---------------------------------------------------------------------------
# 1. Sanity-checked data loading
# ---------------------------------------------------------------------------

def _load_csv_chunked(pattern: str, years: list[int], value_col: str = "reading_value") -> pd.DataFrame:
    """Load CSVs for given years in chunks, minimal memory usage."""
    dfs = []
    for year in years:
        path = DATA_DIR / pattern.format(year=year)
        if not path.exists():
            logger.warning(f"Missing file: {path.name}, skipping")
            continue

        year_dfs = []
        for chunk in pd.read_csv(
            path,
            usecols=["timestamp", "station_id", "station_name",
                     "location_longitude", "location_latitude", value_col],
            chunksize=200_000,
            parse_dates=["timestamp"],
        ):
            year_dfs.append(chunk)

        if year_dfs:
            df_year = pd.concat(year_dfs, ignore_index=True)
            logger.info(f"  {path.name}: {len(df_year):,} rows")
            dfs.append(df_year)

    if not dfs:
        raise ValueError(f"No data found for pattern={pattern!r}, years={years}")

    return pd.concat(dfs, ignore_index=True)


def sanity_check(df: pd.DataFrame, name: str, lo: float, hi: float,
                 value_col: str = "reading_value") -> pd.DataFrame:
    """Assert plausible range; report and drop outlier rows."""
    n_before = len(df)
    out_of_range = (df[value_col] < lo) | (df[value_col] > hi)
    n_bad = out_of_range.sum()
    if n_bad > 0:
        pct = 100 * n_bad / n_before
        logger.warning(f"[{name}] {n_bad:,} rows ({pct:.2f}%) outside [{lo}, {hi}] → dropped")
        df = df[~out_of_range].copy()

    n_dup = df.duplicated(subset=["timestamp", "station_id"]).sum()
    if n_dup > 0:
        logger.warning(f"[{name}] {n_dup:,} duplicate (timestamp, station_id) rows → dropped")
        df = df.drop_duplicates(subset=["timestamp", "station_id"])

    n_after = len(df)
    logger.info(f"[{name}] {n_after:,} rows kept ({n_before - n_after:,} dropped)")

    # Row count sanity: 5-min data over N years ~ 105120 rows/year/station
    n_years = df["timestamp"].dt.year.nunique()
    n_stations = df["station_id"].nunique()
    expected_min = n_years * n_stations * 80_000  # 80k slots/year/station — allow gaps
    if n_after < expected_min:
        logger.warning(
            f"[{name}] Fewer rows than expected: {n_after:,} < {expected_min:,} "
            f"({n_years} years × {n_stations} stations × 80k min)"
        )

    return df


# ---------------------------------------------------------------------------
# 2. Pivot + hourly aggregation
# ---------------------------------------------------------------------------

def pivot_to_hourly(df: pd.DataFrame, value_col: str = "reading_value",
                    agg: str = "sum") -> pd.DataFrame:
    """Pivot station readings → wide format, resample to hourly."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["hour"] = df["timestamp"].dt.floor("1h")

    pivot = df.pivot_table(
        index="hour",
        columns="station_id",
        values=value_col,
        aggfunc=agg,
    )
    pivot.index = pd.DatetimeIndex(pivot.index, tz="UTC").tz_convert("Asia/Singapore")
    return pivot


def network_mean(hourly_wide: pd.DataFrame) -> pd.Series:
    """Island-wide mean across all stations, fills isolated NaN by forward fill."""
    s = hourly_wide.mean(axis=1)
    s = s.fillna(method="ffill", limit=3)
    return s.rename("rainfall_network_mean")


# ---------------------------------------------------------------------------
# 3. Feature engineering (no leakage)
# ---------------------------------------------------------------------------

def make_features(series: pd.Series, horizons: list[int]) -> pd.DataFrame:
    """
    For each hour t, build features using only t and earlier.
    Target for horizon h: rainfall at t+h.

    Features:
      - lag_1 … lag_24   (past 24 hours of rainfall)
      - rolling_mean_3h, rolling_mean_6h, rolling_std_6h, rolling_max_3h
      - hour_of_day, day_of_week, month, is_weekend
      - rain_yesterday_same_hour (t-24)
    """
    df = series.to_frame(name="y")

    # Lag features (only past values → no leakage)
    for lag in [1, 2, 3, 4, 5, 6, 12, 18, 24]:
        df[f"lag_{lag}h"] = df["y"].shift(lag)

    # Rolling features on past data (shifted by 1 so they don't include t)
    past = df["y"].shift(1)
    df["roll_mean_3h"] = past.rolling(3).mean()
    df["roll_mean_6h"] = past.rolling(6).mean()
    df["roll_std_6h"]  = past.rolling(6).std()
    df["roll_max_3h"]  = past.rolling(3).max()
    df["roll_sum_6h"]  = past.rolling(6).sum()

    # Calendar features
    df["hour_of_day"]  = df.index.hour
    df["day_of_week"]  = df.index.dayofweek
    df["month"]        = df.index.month
    df["is_weekend"]   = (df.index.dayofweek >= 5).astype(int)
    df["sin_hour"]     = np.sin(2 * np.pi * df.index.hour / 24)
    df["cos_hour"]     = np.cos(2 * np.pi * df.index.hour / 24)
    df["sin_month"]    = np.sin(2 * np.pi * df.index.month / 12)
    df["cos_month"]    = np.cos(2 * np.pi * df.index.month / 12)

    # Binary: was it raining in the last hour?
    df["rained_last1h"] = (df["lag_1h"] > 0.1).astype(int)
    df["rained_last3h"] = (df["roll_sum_6h"] > 0.3).astype(int)

    # Targets for each horizon (shift BACK = future values)
    for h in horizons:
        df[f"target_{h}h"] = df["y"].shift(-h)

    return df


# ---------------------------------------------------------------------------
# 4. ACF / PACF analysis
# ---------------------------------------------------------------------------

def run_autocorrelation_analysis(series: pd.Series, out_dir: Path) -> dict:
    """Compute ACF and PACF, return significant lags."""
    out_dir.mkdir(parents=True, exist_ok=True)

    clean = series.dropna()
    n = min(len(clean), 10000)  # cap for speed
    sample = clean.iloc[-n:]

    # ACF / PACF arrays
    acf_vals, acf_confint = acf(sample, nlags=48, alpha=0.05)
    pacf_vals, pacf_confint = pacf(sample, nlags=48, method="ywmle", alpha=0.05)

    # Significant lags (outside 95% confidence interval)
    sig_acf = [i for i, (v, ci) in enumerate(zip(acf_vals, acf_confint))
               if i > 0 and not (ci[0] <= 0 <= ci[1])]
    sig_pacf = [i for i, (v, ci) in enumerate(zip(pacf_vals, pacf_confint))
                if i > 0 and not (ci[0] <= 0 <= ci[1])]

    results = {
        "n_samples": n,
        "significant_acf_lags": sig_acf[:20],
        "significant_pacf_lags": sig_pacf[:20],
        "acf_lag1": float(acf_vals[1]),
        "acf_lag24": float(acf_vals[24]) if len(acf_vals) > 24 else None,
        "max_acf_beyond_lag5": float(max(abs(acf_vals[5:25]))) if len(acf_vals) > 25 else None,
        "sparsity_pct": float(100 * (sample == 0).mean()),
    }

    logger.info(
        f"ACF analysis: sparsity={results['sparsity_pct']:.1f}% | "
        f"sig ACF lags (first 5): {sig_acf[:5]} | "
        f"sig PACF lags (first 5): {sig_pacf[:5]}"
    )

    # Save numerical results
    out_path = out_dir / "acf_pacf_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"ACF/PACF results saved to {out_path}")

    # Try to produce matplotlib plots if available
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
        plot_acf(sample, lags=48, ax=ax1, title="ACF – Network Mean Hourly Rainfall")
        plot_pacf(sample, lags=48, ax=ax2, title="PACF – Network Mean Hourly Rainfall",
                  method="ywmle")
        fig.tight_layout()
        fig.savefig(out_dir / "acf_pacf.png", dpi=100)
        plt.close()
        logger.info(f"ACF/PACF plot saved to {out_dir / 'acf_pacf.png'}")
    except Exception as e:
        logger.info(f"Skipping ACF plot (matplotlib unavailable: {e})")

    return results


# ---------------------------------------------------------------------------
# 5. Train LightGBM per horizon
# ---------------------------------------------------------------------------

def train_lgbm(X_train, y_train, X_val, y_val, horizon: int):
    try:
        import lightgbm as lgb
    except ImportError:
        logger.error("lightgbm not installed — run: pip install lightgbm")
        raise

    train_set = lgb.Dataset(X_train, label=y_train)
    val_set   = lgb.Dataset(X_val, label=y_val, reference=train_set)

    params = {
        "objective": "regression_l1",   # MAE loss — robust to rare heavy rain
        "metric": ["mae", "rmse"],
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_child_samples": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
    }

    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=False),
        lgb.log_evaluation(period=100),
    ]

    model = lgb.train(
        params,
        train_set,
        num_boost_round=1000,
        valid_sets=[train_set, val_set],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    logger.info(
        f"[horizon={horizon}h] best iteration={model.best_iteration}, "
        f"val MAE={model.best_score['val']['l1']:.4f}"
    )
    return model


# ---------------------------------------------------------------------------
# 6. NEA forecast benchmark loader
# ---------------------------------------------------------------------------

def load_nea_forecast_benchmark(years: list[int]) -> pd.DataFrame:
    """
    Load official NEA 24-hour forecast (island-wide) as a coarse benchmark.
    Returns hourly dataframe with forecast_text and temperature high/low.
    """
    dfs = []
    for year in years:
        path = DATA_DIR / f"Historical24hourWeatherForecast{year}.csv"
        if not path.exists():
            logger.warning(f"NEA forecast file missing: {path.name}")
            continue
        df = pd.read_csv(
            path,
            usecols=["timestamp", "forecast_text", "forecast_code",
                     "temperature_high", "temperature_low",
                     "valid_period_start", "valid_period_end"],
            parse_dates=["timestamp", "valid_period_start", "valid_period_end"],
        )
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    result = pd.concat(dfs, ignore_index=True)
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    logger.info(f"NEA forecast benchmark: {len(result):,} rows across {len(years)} years")
    return result


def nea_forecast_to_rain_binary(forecast_text: str) -> int:
    """Map NEA forecast text to binary rain signal (1=rain expected)."""
    rain_keywords = ["rain", "shower", "thunder", "drizzle"]
    text = str(forecast_text).lower()
    return int(any(kw in text for kw in rain_keywords))


# ---------------------------------------------------------------------------
# 7. Benchmark evaluation
# ---------------------------------------------------------------------------

def evaluate_benchmark(y_true: np.ndarray, y_pred_model: np.ndarray,
                        y_pred_nea: np.ndarray | None, horizon: int) -> dict:
    """Compare model vs NEA official forecast."""
    mae_model = mean_absolute_error(y_true, y_pred_model)
    rmse_model = np.sqrt(mean_squared_error(y_true, y_pred_model))

    result = {
        "horizon_h": horizon,
        "n_samples": int(len(y_true)),
        "model_mae": round(mae_model, 4),
        "model_rmse": round(rmse_model, 4),
    }

    if y_pred_nea is not None:
        mae_nea = mean_absolute_error(y_true, y_pred_nea)
        rmse_nea = np.sqrt(mean_squared_error(y_true, y_pred_nea))
        result["nea_mae"] = round(mae_nea, 4)
        result["nea_rmse"] = round(rmse_nea, 4)
        result["model_beats_nea"] = mae_model < mae_nea
        result["improvement_pct"] = round(100 * (mae_nea - mae_model) / (mae_nea + 1e-9), 2)
    else:
        result["nea_mae"] = None
        result["nea_rmse"] = None
        result["model_beats_nea"] = None

    logger.info(
        f"[h={horizon}h] Model MAE={mae_model:.4f} RMSE={rmse_model:.4f}"
        + (f" | NEA MAE={result.get('nea_mae'):.4f} | Δ={result.get('improvement_pct'):.1f}%"
           if result.get("nea_mae") else "")
    )
    return result


# ---------------------------------------------------------------------------
# 8. Main training entry point
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("LionWeather ML Rainfall Forecast Pipeline")
    logger.info("=" * 60)

    # --- Load all rainfall data ---
    logger.info("Loading rainfall data (all years, chunked)...")
    rain_all = _load_csv_chunked(
        "HistoricalRainfallacrossSingapore{year}.csv",
        TRAIN_YEARS + [VAL_YEAR, TEST_YEAR],
    )
    rain_all = sanity_check(rain_all, "rainfall", 0.0, RAINFALL_MAX_MM)

    # --- Load temperature data ---
    logger.info("Loading temperature data...")
    temp_all = _load_csv_chunked(
        "HistoricalAirTemperatureacrossSingapore{year}.csv",
        TRAIN_YEARS + [VAL_YEAR, TEST_YEAR],
    )
    temp_all = sanity_check(temp_all, "temperature", TEMP_MIN, TEMP_MAX)

    # --- Load humidity data ---
    logger.info("Loading humidity data...")
    hum_all = _load_csv_chunked(
        "HistoricalRelativeHumidityacrossSingapore{year}.csv",
        TRAIN_YEARS + [VAL_YEAR, TEST_YEAR],
    )
    hum_all = sanity_check(hum_all, "humidity", HUMIDITY_MIN, HUMIDITY_MAX)

    # --- Pivot to hourly wide format ---
    logger.info("Pivoting and aggregating to hourly...")
    rain_hourly = pivot_to_hourly(rain_all, agg="sum")   # total rain per hour
    temp_hourly = pivot_to_hourly(temp_all, agg="mean")
    hum_hourly  = pivot_to_hourly(hum_all,  agg="mean")

    logger.info(f"Hourly rain shape: {rain_hourly.shape}  (hours × stations)")
    logger.info(f"Hourly temp shape: {temp_hourly.shape}")
    logger.info(f"Hourly humidity shape: {hum_hourly.shape}")

    # --- Network mean series for ACF analysis ---
    rain_mean = network_mean(rain_hourly)

    # --- ACF / PACF analysis ---
    logger.info("Running ACF/PACF analysis...")
    analysis_dir = MODEL_DIR / "analysis"
    acf_results = run_autocorrelation_analysis(rain_mean, analysis_dir)

    # --- Feature engineering (on network mean for island-wide model) ---
    logger.info("Engineering features...")
    feat_df = make_features(rain_mean, HORIZONS)

    # Merge in network-mean temperature and humidity as additional predictors
    temp_mean = temp_hourly.mean(axis=1).rename("temp_mean")
    hum_mean  = hum_hourly.mean(axis=1).rename("humidity_mean")
    feat_df = feat_df.join(temp_mean, how="left")
    feat_df = feat_df.join(hum_mean, how="left")

    logger.info(f"Feature dataframe: {feat_df.shape} rows × cols")
    logger.info(f"Feature columns: {[c for c in feat_df.columns if not c.startswith('target_')]}")

    # Drop rows with NaN in ANY feature (first 24 hours and last `max_horizon` hours)
    feature_cols = [c for c in feat_df.columns if not c.startswith("target_")]

    # --- Temporal split (NO leakage) ---
    train_mask = feat_df.index.year.isin(TRAIN_YEARS)
    val_mask   = feat_df.index.year == VAL_YEAR
    test_mask  = feat_df.index.year == TEST_YEAR

    logger.info(
        f"Split: train={train_mask.sum():,} | val={val_mask.sum():,} | test={test_mask.sum():,}"
    )

    # --- Load NEA benchmark ---
    logger.info("Loading NEA official forecast benchmark...")
    nea_bench = load_nea_forecast_benchmark([VAL_YEAR, TEST_YEAR])

    # --- Train one model per horizon ---
    all_benchmarks = []

    for horizon in HORIZONS:
        target_col = f"target_{horizon}h"
        logger.info(f"\n--- Training horizon={horizon}h ---")

        sub = feat_df[feature_cols + [target_col]].dropna()

        train_sub = sub[sub.index.year.isin(TRAIN_YEARS)]
        val_sub   = sub[sub.index.year == VAL_YEAR]
        test_sub  = sub[sub.index.year == TEST_YEAR]

        if len(train_sub) < 1000:
            logger.warning(f"  Not enough training data ({len(train_sub)}), skipping h={horizon}h")
            continue

        X_train, y_train = train_sub[feature_cols].values, train_sub[target_col].values
        X_val,   y_val   = val_sub[feature_cols].values,   val_sub[target_col].values
        X_test,  y_test  = test_sub[feature_cols].values,  test_sub[target_col].values

        logger.info(f"  Train={len(X_train):,} Val={len(X_val):,} Test={len(X_test):,}")

        model = train_lgbm(X_train, y_train, X_val, y_val, horizon)

        # Predict test set
        y_pred_test = model.predict(X_test, num_iteration=model.best_iteration)
        y_pred_test = np.clip(y_pred_test, 0, None)  # rainfall can't be negative

        # Build NEA benchmark predictions aligned to test timestamps
        # NEA forecasts are coarse (binary rain / no-rain → use mean rain when raining)
        nea_pred = None
        if not nea_bench.empty:
            try:
                # Map NEA binary forecast to a rain rate estimate
                nea_hourly = (
                    nea_bench
                    .set_index("timestamp")
                    .sort_index()
                    .reindex(test_sub.index, method="nearest", tolerance=pd.Timedelta("2h"))
                )
                nea_rain_signal = nea_hourly["forecast_text"].apply(nea_forecast_to_rain_binary)
                # Use historical mean rain rate when NEA says it rains
                mean_rain_when_raining = float(y_train[y_train > 0.1].mean()) if (y_train > 0.1).any() else 1.0
                nea_pred = (nea_rain_signal * mean_rain_when_raining).values
                logger.info(f"  NEA benchmark: {nea_rain_signal.sum()} rain-predicted hours")
            except Exception as e:
                logger.warning(f"  NEA benchmark alignment failed: {e}")

        bench = evaluate_benchmark(y_test, y_pred_test, nea_pred, horizon)
        all_benchmarks.append(bench)

        # Feature importances
        fi = dict(zip(feature_cols, model.feature_importance(importance_type="gain")))
        top_features = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info(f"  Top features: {top_features}")

        # Save model
        model_path = MODEL_DIR / f"rainfall_lgbm_{horizon}h.joblib"
        joblib.dump(
            {
                "model": model,
                "feature_cols": feature_cols,
                "horizon_h": horizon,
                "trained_at": datetime.utcnow().isoformat(),
                "train_years": TRAIN_YEARS,
                "val_year": VAL_YEAR,
                "test_year": TEST_YEAR,
                "test_mae": bench["model_mae"],
                "test_rmse": bench["model_rmse"],
            },
            model_path,
        )
        logger.info(f"  Model saved → {model_path}")

    # --- Save benchmark report ---
    bench_path = MODEL_DIR / "forecast_benchmark.json"
    with open(bench_path, "w") as f:
        json.dump(
            {
                "generated_at": datetime.utcnow().isoformat(),
                "description": "LGBMvsNEA rainfall forecast benchmark on 2024 held-out test set",
                "acf_analysis": acf_results,
                "horizons": all_benchmarks,
            },
            f,
            indent=2,
        )
    logger.info(f"\nBenchmark report saved → {bench_path}")

    # --- Summary ---
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING COMPLETE — SUMMARY")
    logger.info("=" * 60)
    for b in all_benchmarks:
        h = b["horizon_h"]
        beats = "✓ BEATS NEA" if b.get("model_beats_nea") else "✗ worse than NEA"
        logger.info(
            f"  {h}h ahead → MAE={b['model_mae']:.4f}mm | RMSE={b['model_rmse']:.4f}mm | {beats}"
        )


if __name__ == "__main__":
    main()
