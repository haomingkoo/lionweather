"""
Historical benchmark: NEA 2-hour forecasts vs ML models vs baseline, all evaluated
against actual observed rainfall.

FORECASTING FRAMEWORK (not current-conditions comparison):
===========================================================
For each 2-hour NEA forecast window [T, T+2h]:
  - NEA  : binary forecast issued ~30 min before T, valid for [T, T+2h]
  - ML Nh: LightGBM classifier issued N hours BEFORE T, predicting rain in [T, T+2h]
             • 1h  model → features from weather_records at T-1h
             • 3h  model → features from weather_records at T-3h
             • 6h  model → features from weather_records at T-6h
             • 12h model → features from weather_records at T-12h
  - Baseline (persistence): was it raining in the previous 2h window [T-2h, T]?
  - Ground truth: mean total mm per station across all 64 rainfall stations
                  in [T, T+2h] ≥ 1.0mm → actual rain (binary 1)

This is apples-to-apples: all models predict for the SAME target window [T, T+2h],
just issued at different lead times.

NEA only provides a binary "rain / no-rain" signal per area (text like "Thundery Showers"
or "Cloudy"). We aggregate across all 47 areas (majority vote) to get a
Singapore-wide binary signal.

Data sources (all real, no synthetic):
  nea_historical_data/Historical2hourWeatherForecast<year>.csv
  nea_historical_data/HistoricalRainfallacrossSingapore<year>.csv
  weather_records DB table (Singapore-wide hourly: temp, humidity, rain, wind)

Output: backend/models/historical_benchmark.json
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path("nea_historical_data")
OUT_PATH = Path("models/historical_benchmark.json")

# NEA forecast codes that indicate rain
RAIN_CODES = {"SH", "LS", "LR", "PS", "TL", "RA", "HT", "HS", "HG"}

# Ground truth threshold: mean mm across all stations per 2h window → rain
RAIN_THRESHOLD_MM = 1.0

# ML lead times (hours before window start)
HORIZONS = [1, 3, 6, 12]

# Years to process
YEARS = list(range(2016, 2025))


# ── NEA forecast loading ──────────────────────────────────────────────────────

def load_nea_forecasts_year(year: int) -> pd.DataFrame | None:
    """
    Load NEA 2h area forecasts for one year.
    Returns DataFrame with columns: [window_start, nea_binary]
    where nea_binary = 1 if majority (≥50%) of 47 areas predicted rain.
    """
    path = DATA_DIR / f"Historical2hourWeatherForecast{year}.csv"
    if not path.exists():
        log.warning(f"Missing: {path}")
        return None

    df = pd.read_csv(path, usecols=["valid_period_start", "forecast_code"])
    df["window_start"] = (
        pd.to_datetime(df["valid_period_start"], utc=True)
        .dt.tz_convert("Asia/Singapore")
    )
    df["nea_bin"] = df["forecast_code"].apply(
        lambda c: 1 if str(c).strip().upper() in RAIN_CODES else 0
    )
    # Singapore-wide: majority vote across all 47 areas per window
    agg = (
        df.groupby("window_start")["nea_bin"]
        .mean()
        .rename("nea_rain_fraction")
        .reset_index()
    )
    agg["nea_binary"] = (agg["nea_rain_fraction"] >= 0.5).astype(int)
    return agg[["window_start", "nea_binary"]]


# ── actual rainfall loading ───────────────────────────────────────────────────

def load_actual_rainfall_year(year: int) -> pd.DataFrame | None:
    """
    Load actual 5-minute rainfall readings for one year.
    Returns DataFrame with columns: [window_start, mean_station_mm, actual_binary]
    where:
      mean_station_mm = average total mm per station across all 64 stations in 2h window
      actual_binary   = 1 if mean_station_mm >= RAIN_THRESHOLD_MM
    """
    path = DATA_DIR / f"HistoricalRainfallacrossSingapore{year}.csv"
    if not path.exists():
        log.warning(f"Missing: {path}")
        return None

    log.info(f"Loading rainfall {year} …")
    chunks = []
    for chunk in pd.read_csv(
        path,
        usecols=["timestamp", "station_name", "reading_value"],
        chunksize=500_000,
        dtype={"reading_value": "float32"},
    ):
        chunk["ts"] = pd.to_datetime(chunk["timestamp"], utc=True).dt.tz_convert("Asia/Singapore")
        chunk["reading_value"] = pd.to_numeric(chunk["reading_value"], errors="coerce").fillna(0.0)
        # Snap 5-min readings to their 2h window (even hours: 00,02,04,…)
        chunk["window_start"] = chunk["ts"].dt.floor("2h")
        # Total mm per station per window
        agg = chunk.groupby(["window_start", "station_name"])["reading_value"].sum().reset_index()
        chunks.append(agg)

    df = pd.concat(chunks, ignore_index=True)
    # Average across stations → Singapore-wide mean mm per 2h window
    result = (
        df.groupby("window_start")["reading_value"]
        .mean()
        .rename("mean_station_mm")
        .reset_index()
    )
    result["actual_binary"] = (result["mean_station_mm"] >= RAIN_THRESHOLD_MM).astype(int)
    return result[["window_start", "mean_station_mm", "actual_binary"]]


# ── Historical weather records for ML features ────────────────────────────────
# Priority: parquet cache (2016-2024, same source as training) → DB fallback

CACHE_DIR = Path("models/cache")

def load_historical_weather() -> pd.DataFrame:
    """
    Load hourly Singapore-wide averages used for ML feature construction.

    Tries the parquet cache produced by train_full_analysis.py first
    (covers 2016-2024, same data used for training). Falls back to DB
    weather_records (live data from 2024-03-18 onwards) if cache is missing.

    Returns DataFrame with columns [temperature, rainfall, humidity, wind_speed]
    indexed by Asia/Singapore timezone timestamps.
    """
    parquet_files = {
        "rainfall":    CACHE_DIR / "rainfall_hourly.parquet",
        "temperature": CACHE_DIR / "temperature_hourly.parquet",
        "humidity":    CACHE_DIR / "humidity_hourly.parquet",
        "wind_speed":  CACHE_DIR / "wind_speed_hourly.parquet",
    }

    if all(p.exists() for p in parquet_files.values()):
        log.info("Loading weather history from parquet cache (2016-2024)…")
        series = {}
        for col, path in parquet_files.items():
            s = pd.read_parquet(path).squeeze()
            s.index = pd.DatetimeIndex(s.index)
            if s.index.tz is None:
                s.index = s.index.tz_localize("Asia/Singapore")
            else:
                s.index = s.index.tz_convert("Asia/Singapore")
            series[col] = s

        df = pd.DataFrame(series)
        df = df.resample("1h").mean().ffill().bfill()
        log.info(f"Cache: {len(df)} hourly rows  {df.index.min()} → {df.index.max()}")
        return df

    # Fallback: DB (only covers 2024-03-18 onwards)
    log.warning("Parquet cache not found — falling back to DB weather_records")
    return _load_db_weather_records()


def _load_db_weather_records() -> pd.DataFrame:
    sys.path.insert(0, str(Path(__file__).parent))
    from app.db.database import get_engine
    from sqlalchemy import text

    log.info("Loading weather_records from DB …")
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT timestamp, temperature, rainfall, humidity, wind_speed
            FROM weather_records
            WHERE country = 'singapore'
            ORDER BY timestamp ASC
        """)).fetchall()

    if not rows:
        log.warning("No weather_records in DB — ML backtest will be skipped")
        return pd.DataFrame()

    df = pd.DataFrame([{
        "timestamp": pd.to_datetime(row[0]),
        "temperature": row[1] or 0.0,
        "rainfall":    row[2] or 0.0,
        "humidity":    row[3] or 0.0,
        "wind_speed":  row[4] or 0.0,
    } for row in rows])

    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Singapore")
    df = df.set_index("timestamp").resample("1h").mean().ffill().bfill()
    log.info(f"DB: {len(df)} hourly rows  {df.index.min()} → {df.index.max()}")
    return df


# ── ML feature engineering ────────────────────────────────────────────────────

def build_features(hist: pd.DataFrame) -> dict:
    """
    Build the exact same feature vector used by /api/ml/rain-forecast.
    `hist` is the slice of DB data BEFORE the prediction time (exclusive).
    Features encode what was known at prediction time — never future data.
    """
    n = len(hist)
    if n < 1:
        return {}

    def lag(col, h):
        idx = -(1 + h)
        return float(hist[col].iloc[idx]) if abs(idx) <= n else float(hist[col].iloc[0])

    def roll_mean(col, h):
        return float(hist[col].iloc[max(0, n - h):].mean())

    def roll_std(col, h):
        s = hist[col].iloc[max(0, n - h):]
        return float(s.std()) if len(s) > 1 else 0.0

    def roll_max(col, h):
        return float(hist[col].iloc[max(0, n - h):].max())

    def roll_sum(col, h):
        return float(hist[col].iloc[max(0, n - h):].sum())

    now = hist.index[-1]
    hour, dow, month, doy = now.hour, now.dayofweek, now.month, now.dayofyear

    # Dry spell / rain streak at prediction time
    recent = [float(hist["rainfall"].iloc[-(i + 1)]) for i in range(min(n, 24))]
    dry_spell, rain_streak = 0, 0
    for r in recent:
        if r < 0.1:
            dry_spell += 1
        else:
            break
    for r in recent:
        if r >= 0.1:
            rain_streak += 1
        else:
            break

    hum = float(hist["humidity"].iloc[-1])
    temp = float(hist["temperature"].iloc[-1])
    wind_now = lag("wind_speed", 0)
    wind_3ago = lag("wind_speed", 3)

    return {
        # Lag features (PAST data only — correct for forecasting)
        **{f"rain_lag_{h}h": lag("rainfall", h) for h in [1, 2, 3, 4, 5, 6, 12, 18, 24]},
        **{f"temp_lag_{h}h": lag("temperature", h) for h in [1, 2, 3, 4, 5, 6, 12, 18, 24]},
        **{f"hum_lag_{h}h":  lag("humidity", h)    for h in [1, 2, 3, 4, 5, 6, 12, 18, 24]},
        **{f"wind_lag_{h}h": lag("wind_speed", h)  for h in [1, 2, 3, 4, 5, 6, 12, 18, 24]},
        # Rolling summaries
        "rain_roll_3h":     roll_mean("rainfall", 3),
        "rain_roll_6h":     roll_mean("rainfall", 6),
        "rain_roll_std_6h": roll_std("rainfall", 6),
        "rain_roll_max_3h": roll_max("rainfall", 3),
        "rain_sum_6h":      roll_sum("rainfall", 6),
        "temp_roll_3h":     roll_mean("temperature", 3),
        "temp_roll_6h":     roll_mean("temperature", 6),
        # Time encoding
        "hour_of_day":       hour,
        "day_of_week":       dow,
        "month":             month,
        "is_weekend":        int(dow >= 5),
        "sin_hour":          np.sin(2 * np.pi * hour / 24),
        "cos_hour":          np.cos(2 * np.pi * hour / 24),
        "sin_month":         np.sin(2 * np.pi * month / 12),
        "cos_month":         np.cos(2 * np.pi * month / 12),
        "day_of_year":       doy,
        "sin_day_of_year":   np.sin(2 * np.pi * doy / 365),
        "cos_day_of_year":   np.cos(2 * np.pi * doy / 365),
        # Derived
        "rained_last1h":     int(lag("rainfall", 1) >= 0.1),
        "rained_last3h":     int(roll_sum("rainfall", 6) > 0.3),
        "dry_spell_hours":   dry_spell,
        "rain_streak_hours": rain_streak,
        "hum_deficit":       100.0 - hum,
        "hum_temp_product":  hum * temp / 100.0,
        "wind_accel_3h":     wind_now - wind_3ago,
        "is_inter_monsoon":  int(month in [4, 5, 10, 11]),
        "is_afternoon_peak": int(13 <= hour <= 17),
        "is_morning_peak":   int(7 <= hour <= 9),
    }


# ── ML model runner ───────────────────────────────────────────────────────────

def load_ml_models() -> dict:
    import joblib
    models = {}
    for h in HORIZONS:
        p = Path("models") / f"rainfall_cls_{h}h.joblib"
        if p.exists():
            models[h] = joblib.load(p)
            log.info(f"Loaded ML {h}h model")
        else:
            log.warning(f"Missing model file: {p}")
    return models


def ml_predict_binary(bundle: dict, feat: dict) -> tuple[int, float]:
    """
    Run one LightGBM native Booster; return (binary_prediction, rain_probability).
    Native Booster.predict() returns shape (n_samples, n_classes) for multiclass.
    rain_prob = P(Light Rain) + P(Heavy Rain) + P(Thundery) = P(class >= 1)
    """
    clf = bundle["model"]
    cols = bundle["feature_cols"]
    X = pd.DataFrame([[feat.get(c, 0.0) for c in cols]], columns=cols)
    proba = clf.predict(X)[0]  # shape (n_classes,) after indexing first row
    rain_prob = float(proba[1]) + float(proba[2]) + float(proba[3])
    return int(rain_prob >= 0.5), rain_prob


# ── per-year benchmarking ─────────────────────────────────────────────────────

def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Binary classification metrics."""
    n = len(y_true)
    if n == 0:
        return {}
    acc = (y_true == y_pred).mean()
    rain_mask = y_true == 1
    norain_mask = y_true == 0
    pred_rain_mask = y_pred == 1
    tp = (rain_mask & pred_rain_mask).sum()
    tn = (norain_mask & ~pred_rain_mask).sum()
    fp = (norain_mask & pred_rain_mask).sum()
    fn = (rain_mask & ~pred_rain_mask).sum()
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    prec   = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    spec   = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1     = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0
    return {
        "n": n,
        "accuracy":       round(float(acc), 4),
        "rain_recall":    round(float(recall), 4),
        "rain_precision": round(float(prec), 4),
        "specificity":    round(float(spec), 4),
        "f1":             round(float(f1), 4),
        "rain_events":    int(rain_mask.sum()),
        "no_rain_events": int(norain_mask.sum()),
    }


def benchmark_year(year: int, db_df: pd.DataFrame, models: dict) -> dict | None:
    log.info(f"\n{'='*60}\nYear {year}\n{'='*60}")

    nea_df  = load_nea_forecasts_year(year)
    rain_df = load_actual_rainfall_year(year)
    if nea_df is None or rain_df is None:
        return None

    # Merge: each row = one 2h forecast window with NEA forecast + actual
    merged = pd.merge(nea_df, rain_df, on="window_start", how="inner")
    log.info(f"{year}: {len(merged)} matched windows, {merged['actual_binary'].mean():.1%} actual rain")
    if merged.empty:
        return None

    actual = merged["actual_binary"].values
    nea    = merged["nea_binary"].values

    # ── NEA accuracy ──────────────────────────────────────────────────────────
    nea_metrics = metrics(actual, nea)
    log.info(f"  NEA: acc={nea_metrics['accuracy']:.3f}  f1={nea_metrics['f1']:.3f}")

    # ── Persistence baseline: predict rain if it rained in PREVIOUS 2h window
    # Shift actual by 1 window (2h) → "it was raining 2h ago"
    persist_pred = np.roll(actual, 1)
    persist_pred[0] = 0  # can't know window before first
    persist_metrics = metrics(actual, persist_pred)
    log.info(f"  Persistence: acc={persist_metrics['accuracy']:.3f}  f1={persist_metrics['f1']:.3f}")

    # ── ML backtest ───────────────────────────────────────────────────────────
    ml_by_horizon: dict[int, dict] = {}

    if db_df.empty or not models:
        log.info(f"  ML: no DB data or models — skipping")
    else:
        # Only windows where we have enough DB history for the longest lag (24h)
        # For horizon h, prediction time = window_start - h hours
        for h, bundle in models.items():
            preds = []
            # For each window, the MODEL was run h hours before window_start
            # So prediction_time = window_start - h hours
            for ws in merged["window_start"]:
                pred_time = ws - pd.Timedelta(hours=h)
                # Need DB data ending at pred_time (exclusive)
                hist = db_df[db_df.index < pred_time]
                if hist.empty or hist.index.max() < pred_time - pd.Timedelta(hours=4):
                    # Not enough DB coverage for this prediction
                    preds.append(np.nan)
                    continue
                feat = build_features(hist)
                if not feat:
                    preds.append(np.nan)
                    continue
                ml_bin, _ = ml_predict_binary(bundle, feat)
                preds.append(ml_bin)

            pred_arr = np.array(preds)
            valid_mask = ~np.isnan(pred_arr)
            n_valid = valid_mask.sum()

            if n_valid < 10:
                log.info(f"  ML {h}h: only {n_valid} valid predictions — skipping")
                continue

            y_t = actual[valid_mask]
            y_p = pred_arr[valid_mask].astype(int)
            y_n = nea[valid_mask]

            ml_m = metrics(y_t, y_p)

            # Hybrid: 60% ML + 40% NEA
            hybrid_prob = 0.6 * y_p.astype(float) + 0.4 * y_n.astype(float)
            hybrid_bin  = (hybrid_prob >= 0.5).astype(int)
            hybrid_m    = metrics(y_t, hybrid_bin)

            ml_by_horizon[h] = {
                "n": n_valid,
                "lead_time_h": h,
                "ml":     ml_m,
                "hybrid": hybrid_m,
            }
            log.info(f"  ML {h}h: acc={ml_m['accuracy']:.3f}  f1={ml_m['f1']:.3f}  n={n_valid}")

    return {
        "year":                year,
        "n_windows":           len(merged),
        "actual_rain_fraction": round(float(actual.mean()), 4),
        "nea":                 nea_metrics,
        "persistence":         persist_metrics,
        "ml_by_horizon":       ml_by_horizon,
    }


# ── aggregate summary ─────────────────────────────────────────────────────────

def summarise(yearly: list[dict]) -> dict:
    def mean_field(records, *path):
        vals = []
        for r in records:
            obj = r
            try:
                for k in path:
                    obj = obj[k]
                vals.append(obj)
            except (KeyError, TypeError):
                pass
        return round(float(np.mean(vals)), 4) if vals else None

    nea_years = [r for r in yearly if "nea" in r]
    out: dict = {
        "years_benchmarked": [r["year"] for r in yearly],
        "nea": {
            "mean_accuracy": mean_field(nea_years, "nea", "accuracy"),
            "mean_f1":       mean_field(nea_years, "nea", "f1"),
        },
        "persistence": {
            "mean_accuracy": mean_field(nea_years, "persistence", "accuracy"),
            "mean_f1":       mean_field(nea_years, "persistence", "f1"),
        },
        "ml_by_horizon": {},
    }
    for h in HORIZONS:
        h_records = [r for r in yearly if h in r.get("ml_by_horizon", {})]
        if not h_records:
            continue
        out["ml_by_horizon"][str(h)] = {
            "lead_time_h": h,
            "mean_accuracy":        mean_field(h_records, "ml_by_horizon", h, "ml", "accuracy"),
            "mean_f1":              mean_field(h_records, "ml_by_horizon", h, "ml", "f1"),
            "hybrid_mean_accuracy": mean_field(h_records, "ml_by_horizon", h, "hybrid", "accuracy"),
            "hybrid_mean_f1":       mean_field(h_records, "ml_by_horizon", h, "hybrid", "f1"),
            "n_years": len(h_records),
        }
    return out


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting historical benchmark")
    db_df  = load_historical_weather()
    models = load_ml_models()

    yearly = []
    for year in YEARS:
        result = benchmark_year(year, db_df, models)
        if result:
            yearly.append(result)

    if not yearly:
        log.error("No results — check data files")
        sys.exit(1)

    output = {
        "generated_at": datetime.now().isoformat(),
        "methodology": {
            "time_unit":     "2-hour NEA forecast windows",
            "space_unit":    "Singapore-wide aggregate",
            "nea_binary":    "majority vote across all 47 NEA areas (≥50% areas predict rain → 1)",
            "actual_binary": f"mean total mm per station across all 64 rainfall stations in 2h window ≥ {RAIN_THRESHOLD_MM}mm → 1",
            "ml_prediction": (
                "LightGBM classifier run at (window_start - lead_time_h), "
                "using ONLY weather_records data before prediction time. "
                "rain_prob = P(class≥1) ≥ 0.5 → binary 1. "
                "Features: lag/rolling of rainfall, temperature, humidity, wind_speed + time encoding."
            ),
            "hybrid":        "60% ML rain_prob + 40% NEA binary, ≥ 0.5 → binary 1",
            "persistence":   "predict rain if previous 2h window had actual rain (naive baseline)",
            "note_nea":      "NEA issues a categorical area forecast (text like 'Thundery Showers', 'Cloudy'). No probability given — binary only.",
            "db_range": {
                "start": str(db_df.index.min()) if not db_df.empty else None,
                "end":   str(db_df.index.max()) if not db_df.empty else None,
            },
        },
        "summary": summarise(yearly),
        "yearly":  yearly,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)

    log.info(f"\nBenchmark written to {OUT_PATH}")
    log.info(f"NEA mean accuracy: {output['summary']['nea']['mean_accuracy']}")
    for h_str, s in output["summary"]["ml_by_horizon"].items():
        log.info(f"ML {h_str}h: acc={s['mean_accuracy']}  hybrid acc={s['hybrid_mean_accuracy']}")


if __name__ == "__main__":
    main()
