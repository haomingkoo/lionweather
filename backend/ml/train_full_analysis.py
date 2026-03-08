#!/usr/bin/env python3
"""
LionWeather Full ML Analysis Pipeline
======================================

Trains a multi-class rainfall classifier (no rain / light rain / heavy rain /
thundery showers) and a regression model for rainfall intensity, then produces
a rich JSON analysis artefact covering:

  - EDA: distributions, seasonality, trend, stationarity
  - ACF / PACF with confidence intervals
  - Frequency / spectral analysis (FFT periodogram)
  - Spurious-correlation checks (cross-correlations, Granger causality)
  - Training loss curves (train vs val per boosting round)
  - SHAP feature importances (global bar + waterfall)
  - Benchmark vs NEA official forecast

Temporal split (no leakage):
  Train  : 2016–2022
  Val    : 2023
  Test   : 2024  ← held-out, used for all final metrics

Output:
  backend/models/full_analysis.json
  backend/models/rainfall_lgbm_<h>h.joblib  (per horizon)

Usage:
  cd backend
  python -m ml.train_full_analysis
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    classification_report,
    confusion_matrix,
)
from statsmodels.tsa.stattools import acf, pacf, adfuller, ccf, grangercausalitytests
from scipy import signal as sp_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "nea_historical_data"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

TRAIN_YEARS = list(range(2016, 2023))
VAL_YEAR    = 2023
TEST_YEAR   = 2024

HORIZONS = [1, 3, 6, 12]   # hours ahead

# Plausibility bounds
BOUNDS = {
    "rainfall":    (0.0,  300.0),
    "temperature": (15.0,  42.0),
    "humidity":    (20.0, 100.0),
    "wind_speed":  (0.0,   60.0),
}

# ---------------------------------------------------------------------------
# Category thresholds (mm/hr, based on NEA classification)
# 0 = no rain, 1 = light rain, 2 = heavy rain, 3 = thundery showers
# ---------------------------------------------------------------------------
RAIN_CATEGORIES = {
    0: "No Rain",
    1: "Light Rain",
    2: "Heavy Rain",
    3: "Thundery Showers",
}

def rainfall_to_category(mm_per_hour: float) -> int:
    """
    NEA-aligned rainfall intensity classification.
    Light:  < 7.6 mm/hr
    Moderate: 7.6–15.2  (map to heavy rain for 4-class)
    Heavy:  >= 15.2 mm/hr
    Thundery showers: >= 30 mm/hr
    """
    if mm_per_hour < 0.1:
        return 0  # No rain
    elif mm_per_hour < 7.6:
        return 1  # Light rain
    elif mm_per_hour < 30.0:
        return 2  # Heavy rain
    else:
        return 3  # Thundery showers


# ===========================================================================
# 1. Data loading
# ===========================================================================

def load_variable(pattern: str, years: list, bounds: tuple,
                  value_col: str = "reading_value") -> pd.DataFrame:
    """Load CSVs for a variable, sanitise, and return long-format DataFrame."""
    dfs = []
    for year in years:
        path = DATA_DIR / pattern.format(year=year)
        if not path.exists():
            logger.warning(f"  missing: {path.name}")
            continue
        chunks = []
        for chunk in pd.read_csv(
            path,
            usecols=["timestamp", "station_id", "station_name",
                     "location_longitude", "location_latitude", value_col],
            chunksize=200_000,
            parse_dates=["timestamp"],
        ):
            chunks.append(chunk)
        if chunks:
            df_year = pd.concat(chunks, ignore_index=True)
            logger.info(f"  {path.name}: {len(df_year):,} rows")
            dfs.append(df_year)

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    # Sanitise
    lo, hi = bounds
    bad_mask = (df[value_col] < lo) | (df[value_col] > hi)
    if bad_mask.sum():
        logger.warning(f"  dropping {bad_mask.sum():,} out-of-range rows")
        df = df[~bad_mask].copy()

    dup_mask = df.duplicated(subset=["timestamp", "station_id"])
    if dup_mask.sum():
        df = df.drop_duplicates(subset=["timestamp", "station_id"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def to_hourly_mean(df: pd.DataFrame, value_col: str = "reading_value",
                   agg: str = "mean") -> pd.Series:
    """Aggregate all stations to an island-wide hourly mean/sum."""
    df = df.copy()
    df["hour"] = df["timestamp"].dt.floor("1h")
    out = df.groupby("hour")[value_col].agg(agg)
    out.index = pd.DatetimeIndex(out.index, tz="UTC").tz_convert("Asia/Singapore")
    return out


CACHE_DIR = BASE_DIR / "models" / "cache"

def load_hourly_series(name: str, pattern: str, years: list, bounds: tuple,
                       agg: str = "mean") -> pd.Series:
    """Load hourly series from Parquet cache if available, else build and cache it."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"{name}_hourly.parquet"

    if cache_path.exists():
        logger.info(f"  [{name}] loading from cache: {cache_path.name}")
        s = pd.read_parquet(cache_path).squeeze()
        s.index = pd.DatetimeIndex(s.index)
        return s

    logger.info(f"  [{name}] building from CSVs (will cache for next run)...")
    raw = load_variable(pattern, years, bounds)
    s = to_hourly_mean(raw, agg=agg)
    s.to_frame(name).to_parquet(cache_path)
    logger.info(f"  [{name}] cached to {cache_path.name}")
    return s


# ===========================================================================
# 2. EDA
# ===========================================================================

def compute_eda(series_dict: dict) -> dict:
    """Return descriptive statistics + seasonal patterns for each variable."""
    eda = {}
    for name, s in series_dict.items():
        clean = s.dropna()
        eda[name] = {
            "n_obs": int(len(clean)),
            "mean": round(float(clean.mean()), 4),
            "std": round(float(clean.std()), 4),
            "min": round(float(clean.min()), 4),
            "max": round(float(clean.max()), 4),
            "p25": round(float(clean.quantile(0.25)), 4),
            "p50": round(float(clean.quantile(0.50)), 4),
            "p75": round(float(clean.quantile(0.75)), 4),
            "p95": round(float(clean.quantile(0.95)), 4),
            "p99": round(float(clean.quantile(0.99)), 4),
            "skewness": round(float(clean.skew()), 4),
            "kurtosis": round(float(clean.kurtosis()), 4),
            # Hourly seasonality (mean per hour of day)
            "hourly_pattern": {
                str(h): round(float(clean[clean.index.hour == h].mean()), 4)
                for h in range(24)
            },
            # Monthly seasonality
            "monthly_pattern": {
                str(m): round(float(clean[clean.index.month == m].mean()), 4)
                for m in range(1, 13)
            },
            # Annual trend (mean per year)
            "annual_trend": {
                str(y): round(float(clean[clean.index.year == y].mean()), 4)
                for y in sorted(clean.index.year.unique())
            },
            # Histogram bins (20 bins)
            "histogram": _histogram(clean, bins=40),
        }
        logger.info(f"  EDA [{name}]: mean={eda[name]['mean']}, std={eda[name]['std']}, "
                    f"skew={eda[name]['skewness']}")
    return eda


def _histogram(s: pd.Series, bins: int = 40) -> dict:
    counts, edges = np.histogram(s.dropna(), bins=bins)
    return {
        "counts": counts.tolist(),
        "bin_edges": [round(float(e), 4) for e in edges.tolist()],
    }


# ===========================================================================
# 2b. Climate trend analysis
# ===========================================================================

def compute_climate_trends(rain_h: pd.Series, temp_h: pd.Series,
                           hum_h: pd.Series, wind_h: pd.Series) -> dict:
    """
    Year-over-year climate statistics for Singapore:
    - Annual rainfall totals and rainy-day counts
    - Rain category frequency (% of hours)
    - Linear trend slope (per variable, per year)
    - STL seasonal decomposition (trend + residual)
    - Record extremes per year
    """
    from scipy.stats import linregress
    from statsmodels.tsa.seasonal import STL

    years = sorted(set(rain_h.index.year) | set(temp_h.index.year))

    # ---- Annual stats ----
    annual = {}
    for y in years:
        r = rain_h[rain_h.index.year == y]
        t = temp_h[temp_h.index.year == y]
        h = hum_h[hum_h.index.year == y]
        w = wind_h[wind_h.index.year == y]

        # Rain categories per hour
        cats = r.apply(rainfall_to_category)
        n_total = max(1, len(cats))

        annual[str(y)] = {
            "rainfall": {
                "total_mm": round(float(r.sum()), 1),
                "mean_hourly_mm": round(float(r.mean()), 4),
                "max_hourly_mm": round(float(r.max()), 2),
                "rainy_hours": int((r > 0.1).sum()),
                "rainy_hours_pct": round(100 * (r > 0.1).sum() / n_total, 1),
                "rain_category_pct": {
                    "no_rain": round(100 * (cats == 0).sum() / n_total, 1),
                    "light_rain": round(100 * (cats == 1).sum() / n_total, 1),
                    "heavy_rain": round(100 * (cats == 2).sum() / n_total, 1),
                    "thundery": round(100 * (cats == 3).sum() / n_total, 1),
                },
                "thundery_events": int((cats == 3).sum()),
            },
            "temperature": {
                "mean_c": round(float(t.mean()), 2),
                "max_c": round(float(t.max()), 2),
                "min_c": round(float(t.min()), 2),
                "hot_hours_above_33": int((t > 33).sum()),
            },
            "humidity": {
                "mean_pct": round(float(h.mean()), 2),
            },
            "wind_speed": {
                "mean_kmh": round(float(w.mean()), 2),
                "max_kmh": round(float(w.max()), 2),
            },
        }

    # ---- Linear trend slopes (per year means) ----
    def _trend_slope(series: pd.Series, agg_fn) -> dict:
        by_year = {y: float(agg_fn(series[series.index.year == y]))
                   for y in years if len(series[series.index.year == y]) > 0}
        if len(by_year) < 3:
            return {}
        ys = list(by_year.keys())
        vs = list(by_year.values())
        slope, _, r, p, _ = linregress(ys, vs)
        return {
            "slope_per_year": round(float(slope), 5),
            "r_squared": round(float(r ** 2), 4),
            "p_value": round(float(p), 4),
            "trend": "increasing" if slope > 0 else "decreasing",
            "significant": bool(p < 0.05),
        }

    trends = {
        "temperature_mean": _trend_slope(temp_h, np.mean),
        "temperature_max": _trend_slope(temp_h, np.max),
        "rainfall_total": _trend_slope(rain_h, np.sum),
        "rainfall_rainy_hours": {
            "values_by_year": {
                str(y): int((rain_h[rain_h.index.year == y] > 0.1).sum())
                for y in years
            }
        },
        "humidity_mean": _trend_slope(hum_h, np.mean),
        "wind_speed_mean": _trend_slope(wind_h, np.mean),
    }

    # ---- STL decomposition on monthly rainfall totals ----
    stl_result = {}
    try:
        monthly_rain = rain_h.resample("ME").sum()
        if len(monthly_rain) >= 24:
            stl = STL(monthly_rain, period=12, robust=True).fit()
            # Downsample to max 120 points for JSON size
            step = max(1, len(monthly_rain) // 120)
            idx = list(range(0, len(monthly_rain), step))
            stl_result = {
                "dates": [str(monthly_rain.index[i].date()) for i in idx],
                "observed": [round(float(monthly_rain.iloc[i]), 2) for i in idx],
                "trend": [round(float(stl.trend.iloc[i]), 2) for i in idx],
                "seasonal": [round(float(stl.seasonal.iloc[i]), 2) for i in idx],
                "residual": [round(float(stl.resid.iloc[i]), 2) for i in idx],
                "note": "Monthly rainfall totals (mm). STL period=12 months.",
            }
    except Exception as e:
        logger.warning(f"  STL decomposition failed: {e}")

    # ---- All-time records ----
    records = {
        "wettest_hour": {
            "value_mm": round(float(rain_h.max()), 2),
            "date": str(rain_h.idxmax().date()),
        },
        "hottest_hour": {
            "value_c": round(float(temp_h.max()), 2),
            "date": str(temp_h.idxmax().date()),
        },
        "coolest_hour": {
            "value_c": round(float(temp_h.min()), 2),
            "date": str(temp_h.idxmin().date()),
        },
        "most_humid": {
            "value_pct": round(float(hum_h.max()), 2),
            "date": str(hum_h.idxmax().date()),
        },
        "windiest_hour": {
            "value_kmh": round(float(wind_h.max()), 2),
            "date": str(wind_h.idxmax().date()),
        },
    }

    logger.info(f"  Climate trends computed for {len(years)} years")
    return {
        "years_covered": years,
        "annual": annual,
        "long_term_trends": trends,
        "stl_decomposition": stl_result,
        "all_time_records": records,
    }


# ===========================================================================
# 3. Stationarity
# ===========================================================================

def adf_test(s: pd.Series, name: str) -> dict:
    """Augmented Dickey-Fuller test for stationarity."""
    clean = s.dropna().iloc[-5000:]  # cap sample size
    try:
        adf_result = adfuller(clean, autolag="AIC")
        stationary = adf_result[1] < 0.05
        result = {
            "adf_statistic": round(float(adf_result[0]), 4),
            "p_value": round(float(adf_result[1]), 6),
            "is_stationary": bool(stationary),
            "critical_values": {k: round(float(v), 4) for k, v in adf_result[4].items()},
        }
        logger.info(f"  ADF [{name}]: p={result['p_value']}, "
                    f"{'stationary' if stationary else 'non-stationary'}")
        return result
    except Exception as e:
        logger.warning(f"  ADF [{name}] failed: {e}")
        return {"error": str(e)}


# ===========================================================================
# 4. ACF / PACF
# ===========================================================================

def compute_acf_pacf(s: pd.Series, nlags: int = 48) -> dict:
    """ACF and PACF arrays with 95% confidence intervals."""
    clean = s.dropna().iloc[-8760:]  # last year of hourly data
    n = len(clean)

    acf_vals, acf_conf = acf(clean, nlags=nlags, alpha=0.05)
    pacf_vals, pacf_conf = pacf(clean, nlags=nlags, method="ywmle", alpha=0.05)

    ci_bound = 1.96 / np.sqrt(n)

    sig_acf  = [i for i in range(1, nlags+1) if abs(acf_vals[i]) > ci_bound]
    sig_pacf = [i for i in range(1, nlags+1) if abs(pacf_vals[i]) > ci_bound]

    return {
        "n_samples": n,
        "lags": list(range(nlags + 1)),
        "acf": [round(float(v), 4) for v in acf_vals],
        "pacf": [round(float(v), 4) for v in pacf_vals],
        "ci_lower_acf":  [round(float(v[0] - acf_vals[i]), 4) for i, v in enumerate(acf_conf)],
        "ci_upper_acf":  [round(float(v[1] - acf_vals[i]), 4) for i, v in enumerate(acf_conf)],
        "ci_lower_pacf": [round(float(v[0] - pacf_vals[i]), 4) for i, v in enumerate(pacf_conf)],
        "ci_upper_pacf": [round(float(v[1] - pacf_vals[i]), 4) for i, v in enumerate(pacf_conf)],
        "ci_bound": round(float(ci_bound), 4),
        "significant_acf_lags": sig_acf[:20],
        "significant_pacf_lags": sig_pacf[:20],
        "sparsity_pct": round(float(100 * (clean == 0).mean()), 2),
    }


# ===========================================================================
# 5. Frequency / spectral analysis
# ===========================================================================

def compute_periodogram(s: pd.Series, sample_rate_hz: float = 1/3600) -> dict:
    """
    FFT periodogram. sample_rate_hz = 1 sample per hour → 1/3600 Hz
    Returns top dominant periods in hours.
    """
    clean = s.dropna().iloc[-8760:]
    x = clean.values - clean.values.mean()  # detrend

    freqs, power = sp_signal.periodogram(x, fs=sample_rate_hz)

    # Convert frequency (Hz) to period (hours), skip DC
    with np.errstate(divide="ignore", invalid="ignore"):
        periods_h = np.where(freqs > 0, 1.0 / (freqs * 3600.0), np.nan)

    # Top 20 peaks in range [2h, 400h] by power
    mask = (periods_h >= 2) & (periods_h <= 400) & np.isfinite(periods_h)
    peaks_idx = np.argsort(power[mask])[-20:][::-1]
    masked_periods = periods_h[mask]
    masked_power   = power[mask]

    top_periods = [
        {"period_h": round(float(masked_periods[i]), 2),
         "power": round(float(masked_power[i]), 6)}
        for i in peaks_idx
    ]

    # Also return a decimated periodogram for the frontend chart
    # Keep only periods 1–200 hours, downsample to 200 points
    valid_idx = np.where((periods_h >= 1) & (periods_h <= 200) & np.isfinite(periods_h))[0]
    if len(valid_idx) > 200:
        step = max(1, len(valid_idx) // 200)
        valid_idx = valid_idx[::step]

    chart_data = [
        {"period_h": round(float(periods_h[i]), 2),
         "power": round(float(power[i]), 6)}
        for i in valid_idx
    ]
    chart_data = sorted(chart_data, key=lambda x: x["period_h"])

    top_labels = [str(p["period_h"]) + "h" for p in top_periods[:5]]
    logger.info(f"  Periodogram: top periods = {top_labels}")

    return {
        "top_dominant_periods": top_periods,
        "chart_data": chart_data,
        "n_samples": len(clean),
    }


# ===========================================================================
# 6. Spurious correlation analysis
# ===========================================================================

def compute_cross_correlations(series_dict: dict, max_lag: int = 24) -> dict:
    """
    For each pair (x, y), compute cross-correlation at lags 0..max_lag.
    Flags potentially spurious correlations (high at lag 0 but random at other lags).
    """
    names = list(series_dict.keys())
    results = {}

    for i, nx in enumerate(names):
        for ny in names[i+1:]:
            sx = series_dict[nx].dropna()
            sy = series_dict[ny].dropna()
            # Align
            combined = pd.concat([sx.rename("x"), sy.rename("y")], axis=1).dropna()
            if len(combined) < 100:
                continue
            x = combined["x"].values
            y = combined["y"].values

            # Normalise
            x_norm = (x - x.mean()) / (x.std() + 1e-9)
            y_norm = (y - y.mean()) / (y.std() + 1e-9)

            try:
                cc = ccf(x_norm, y_norm, nlags=max_lag, alpha=None)
                lags = list(range(len(cc)))
                ci_bound = 1.96 / np.sqrt(len(x_norm))

                key = f"{nx}_vs_{ny}"
                results[key] = {
                    "lags": lags,
                    "cross_correlation": [round(float(v), 4) for v in cc],
                    "pearson_r": round(float(np.corrcoef(x, y)[0, 1]), 4),
                    "ci_bound": round(float(ci_bound), 4),
                    "lag_0_corr": round(float(cc[0]), 4),
                    "max_lag_abs_corr": round(float(max(abs(cc[1:]))), 4),
                    "potentially_spurious": bool(
                        abs(cc[0]) > 0.7 and max(abs(cc[1:])) < 0.3
                    ),
                }
                logger.info(f"  CCF {key}: r={results[key]['pearson_r']}, "
                            f"spurious={results[key]['potentially_spurious']}")
            except Exception as e:
                logger.warning(f"  CCF {nx} vs {ny} failed: {e}")

    return results


def granger_causality(series_dict: dict, target: str = "rainfall",
                      max_lag: int = 6) -> dict:
    """
    Test if each variable Granger-causes rainfall.
    Returns p-values per lag.
    """
    results = {}
    s_target = series_dict.get(target)
    if s_target is None:
        return results

    for name, s_cause in series_dict.items():
        if name == target:
            continue
        combined = pd.concat(
            [s_target.rename(target), s_cause.rename(name)], axis=1
        ).dropna().iloc[-2000:]  # cap for speed

        if len(combined) < 100:
            continue

        try:
            gc_result = grangercausalitytests(combined[[target, name]], maxlag=max_lag,
                                             verbose=False)
            p_vals = {}
            for lag, lag_data in gc_result.items():
                # Use F-test p-value
                p_vals[str(lag)] = round(float(lag_data[0]["ssr_ftest"][1]), 4)

            min_p = min(p_vals.values())
            results[f"{name}_causes_{target}"] = {
                "p_values_per_lag": p_vals,
                "min_p": min_p,
                "significant": min_p < 0.05,
            }
            logger.info(f"  Granger {name}→{target}: min_p={min_p:.4f}, "
                        f"{'✓' if min_p < 0.05 else '✗'}")
        except Exception as e:
            logger.warning(f"  Granger {name}→{target} failed: {e}")

    return results


# ===========================================================================
# 7. Feature engineering
# ===========================================================================

def make_features(rain: pd.Series, temp: pd.Series,
                  humidity: pd.Series, wind: pd.Series,
                  horizons: list) -> pd.DataFrame:
    df = rain.to_frame(name="rainfall")
    df["temperature"] = temp
    df["humidity"]    = humidity
    df["wind_speed"]  = wind

    for lag in [1, 2, 3, 4, 5, 6, 12, 18, 24]:
        df[f"rain_lag_{lag}h"]  = df["rainfall"].shift(lag)
        df[f"temp_lag_{lag}h"]  = df["temperature"].shift(lag)
        df[f"hum_lag_{lag}h"]   = df["humidity"].shift(lag)
        df[f"wind_lag_{lag}h"]  = df["wind_speed"].shift(lag)

    past_rain = df["rainfall"].shift(1)
    df["rain_roll_3h"]  = past_rain.rolling(3).mean()
    df["rain_roll_6h"]  = past_rain.rolling(6).mean()
    df["rain_roll_std_6h"] = past_rain.rolling(6).std()
    df["rain_roll_max_3h"] = past_rain.rolling(3).max()
    df["rain_sum_6h"]   = past_rain.rolling(6).sum()

    past_temp = df["temperature"].shift(1)
    df["temp_roll_3h"]  = past_temp.rolling(3).mean()
    df["temp_roll_6h"]  = past_temp.rolling(6).mean()

    # Calendar
    df["hour_of_day"]  = df.index.hour
    df["day_of_week"]  = df.index.dayofweek
    df["month"]        = df.index.month
    df["is_weekend"]   = (df.index.dayofweek >= 5).astype(int)
    df["sin_hour"]     = np.sin(2 * np.pi * df.index.hour / 24)
    df["cos_hour"]     = np.cos(2 * np.pi * df.index.hour / 24)
    df["sin_month"]    = np.sin(2 * np.pi * df.index.month / 12)
    df["cos_month"]    = np.cos(2 * np.pi * df.index.month / 12)

    df["rained_last1h"] = (df["rain_lag_1h"] > 0.1).astype(int)
    df["rained_last3h"] = (df["rain_sum_6h"] > 0.3).astype(int)

    # Targets
    for h in horizons:
        df[f"target_rain_{h}h"]    = df["rainfall"].shift(-h)
        df[f"target_class_{h}h"]   = df[f"target_rain_{h}h"].apply(
            lambda v: rainfall_to_category(v) if pd.notna(v) else np.nan
        )

    return df


# ===========================================================================
# 8. LightGBM training
# ===========================================================================

def train_lgbm(X_train, y_train, X_val, y_val, horizon: int,
               task: str = "regression",
               sample_weights: np.ndarray | None = None) -> tuple:
    """
    Returns (model, loss_curve_dict).
    loss_curve_dict has keys: 'train', 'val', each a list of per-round losses.
    sample_weights: per-sample cost weights (higher = penalise errors more).
    """
    import lightgbm as lgb

    train_set = lgb.Dataset(X_train, label=y_train, weight=sample_weights)
    val_set   = lgb.Dataset(X_val,   label=y_val, reference=train_set)

    if task == "regression":
        params = {
            "objective": "regression_l1",
            "metric": ["mae"],
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
    else:
        params = {
            "objective": "multiclass",
            "num_class": 4,
            "metric": ["multi_logloss"],
            "learning_rate": 0.05,
            "num_leaves": 63,
            "min_child_samples": 50,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
        }

    evals_result = {}

    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=False),
        lgb.log_evaluation(period=200),
        lgb.record_evaluation(evals_result),
    ]

    model = lgb.train(
        params,
        train_set,
        num_boost_round=1000,
        valid_sets=[train_set, val_set],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    # Extract loss curves from evals_result
    metric_key = list(evals_result["train"].keys())[0]
    loss_curve = {
        "metric": metric_key,
        "train": [round(float(v), 6) for v in evals_result["train"][metric_key]],
        "val":   [round(float(v), 6) for v in evals_result["val"][metric_key]],
        "best_iteration": model.best_iteration,
        "horizon_h": horizon,
        "task": task,
    }

    return model, loss_curve


# ===========================================================================
# 9. SHAP analysis
# ===========================================================================

def compute_shap(model, X_test: np.ndarray, feature_cols: list,
                 task: str = "regression", n_sample: int = 500) -> dict:
    """Compute SHAP values, return global importance + waterfall for first sample."""
    try:
        import shap

        # Cap samples for speed
        idx = np.random.choice(len(X_test), min(n_sample, len(X_test)), replace=False)
        X_sample = X_test[idx]

        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(X_sample)

        # For multiclass, shap_vals is a list of arrays (one per class)
        if isinstance(shap_vals, list):
            # Average absolute SHAP across all classes
            mean_abs = np.mean([np.abs(sv).mean(axis=0) for sv in shap_vals], axis=0)
        else:
            mean_abs = np.abs(shap_vals).mean(axis=0)

        importance = sorted(
            [{"feature": f, "mean_abs_shap": round(float(v), 6)}
             for f, v in zip(feature_cols, mean_abs)],
            key=lambda x: x["mean_abs_shap"], reverse=True
        )

        # Waterfall for first test sample
        if isinstance(shap_vals, list):
            shap_first = shap_vals[0][0].tolist()  # class 0 for first sample
        else:
            shap_first = shap_vals[0].tolist()

        waterfall = sorted(
            [{"feature": f, "shap_value": round(float(v), 6)}
             for f, v in zip(feature_cols, shap_first)],
            key=lambda x: abs(x["shap_value"]), reverse=True
        )[:15]

        logger.info(f"  SHAP: top feature = {importance[0]['feature']} "
                    f"({importance[0]['mean_abs_shap']:.4f})")

        return {
            "global_importance": importance[:20],
            "waterfall_first_sample": waterfall,
            "n_samples_used": len(X_sample),
        }

    except Exception as e:
        logger.warning(f"  SHAP failed: {e}")
        return {"error": str(e)}


# ===========================================================================
# 10. Main
# ===========================================================================

def main():
    logger.info("=" * 70)
    logger.info("LionWeather Full ML Analysis Pipeline")
    logger.info("=" * 70)

    all_years = TRAIN_YEARS + [VAL_YEAR, TEST_YEAR]

    # --- Load data (with Parquet cache for fast reruns) ---
    logger.info("\n[1/8] Loading historical NEA data...")
    logger.info("  (Cached Parquet files in models/cache/ will be used if available)")
    rain_h = load_hourly_series("rainfall",    "HistoricalRainfallacrossSingapore{year}.csv",        all_years, BOUNDS["rainfall"],    agg="sum")
    temp_h = load_hourly_series("temperature", "HistoricalAirTemperatureacrossSingapore{year}.csv",  all_years, BOUNDS["temperature"], agg="mean")
    hum_h  = load_hourly_series("humidity",    "HistoricalRelativeHumidityacrossSingapore{year}.csv",all_years, BOUNDS["humidity"],    agg="mean")
    wind_h = load_hourly_series("wind_speed",  "HistoricalWindSpeedacrossSingapore{year}.csv",       all_years, BOUNDS["wind_speed"],  agg="mean")

    logger.info("\n[2/8] Hourly series ready.")

    series_dict = {
        "rainfall":    rain_h,
        "temperature": temp_h,
        "humidity":    hum_h,
        "wind_speed":  wind_h,
    }

    # --- Climate trends ---
    logger.info("\n[3/8] Computing climate trends...")
    climate_trends = compute_climate_trends(rain_h, temp_h, hum_h, wind_h)

    # --- EDA ---
    logger.info("\n[4/8] Computing EDA...")
    eda = compute_eda(series_dict)

    # Stationarity
    stationarity = {}
    for name, s in series_dict.items():
        stationarity[name] = adf_test(s, name)

    # --- ACF / PACF ---
    logger.info("\n[5/8] Computing ACF / PACF...")
    acf_pacf = {}
    for name, s in series_dict.items():
        acf_pacf[name] = compute_acf_pacf(s, nlags=48)

    # --- Spectral analysis ---
    logger.info("\n[6/8] Computing FFT periodograms...")
    spectral = {}
    for name, s in series_dict.items():
        spectral[name] = compute_periodogram(s)

    # --- Spurious correlation analysis ---
    logger.info("\n[7/8] Checking cross-correlations & Granger causality...")
    cross_corr    = compute_cross_correlations(series_dict, max_lag=24)
    granger       = granger_causality(series_dict, target="rainfall", max_lag=6)

    # --- Feature engineering ---
    logger.info("\n[8/9] Feature engineering & model training...")
    feat_df = make_features(rain_h, temp_h, hum_h, wind_h, HORIZONS)
    feature_cols = [c for c in feat_df.columns
                    if not c.startswith("target_")
                    and c not in ("rainfall", "temperature", "humidity", "wind_speed")]

    train_mask = feat_df.index.year.isin(TRAIN_YEARS)
    val_mask   = feat_df.index.year == VAL_YEAR
    test_mask  = feat_df.index.year == TEST_YEAR

    horizon_results = []
    loss_curves     = []
    shap_results    = {}

    for horizon in HORIZONS:
        reg_target  = f"target_rain_{horizon}h"
        cls_target  = f"target_class_{horizon}h"

        # Drop any row that's missing a feature or target
        cols_needed = feature_cols + [reg_target, cls_target]
        sub = feat_df[cols_needed].dropna()

        train_sub = sub[sub.index.year.isin(TRAIN_YEARS)]
        val_sub   = sub[sub.index.year == VAL_YEAR]
        test_sub  = sub[sub.index.year == TEST_YEAR]

        if len(train_sub) < 500:
            logger.warning(f"  h={horizon}h: insufficient data ({len(train_sub)}), skip")
            continue

        X_train = train_sub[feature_cols].values
        X_val   = val_sub[feature_cols].values
        X_test  = test_sub[feature_cols].values

        # ---- Regression (rainfall mm) ----
        y_train_reg = train_sub[reg_target].values
        y_val_reg   = val_sub[reg_target].values
        y_test_reg  = test_sub[reg_target].values

        logger.info(f"\n  -- Regression h={horizon}h --")
        # Upweight rainy hours: missing rain is ~4x costlier than a false alarm
        reg_weights = np.where(y_train_reg > 0.1, 4.0, 1.0)
        reg_model, reg_loss = train_lgbm(X_train, y_train_reg, X_val, y_val_reg,
                                          horizon, task="regression",
                                          sample_weights=reg_weights)
        y_pred_reg = np.clip(reg_model.predict(X_test), 0, None)

        mae_reg  = mean_absolute_error(y_test_reg, y_pred_reg)
        rmse_reg = np.sqrt(mean_squared_error(y_test_reg, y_pred_reg))

        # ---- Classification (4-class) ----
        y_train_cls = train_sub[cls_target].values.astype(int)
        y_val_cls   = val_sub[cls_target].values.astype(int)
        y_test_cls  = test_sub[cls_target].values.astype(int)

        # Ensure all 4 classes present in training (else skip cls)
        if len(np.unique(y_train_cls)) >= 3:
            logger.info(f"  -- Classification h={horizon}h --")
            # Asymmetric cost: missing rain >> false alarm (user gets wet vs. carries umbrella)
            # Class 0 No Rain=1x, Light Rain=2x, Heavy Rain=4x, Thundery=6x
            RAIN_COST = np.array([1.0, 2.0, 4.0, 6.0])
            cls_weights = RAIN_COST[y_train_cls]
            cls_model, cls_loss = train_lgbm(X_train, y_train_cls, X_val, y_val_cls,
                                              horizon, task="classification",
                                              sample_weights=cls_weights)
            y_pred_cls_proba = cls_model.predict(X_test)
            y_pred_cls = np.argmax(y_pred_cls_proba, axis=1)

            cr = classification_report(y_test_cls, y_pred_cls,
                                       target_names=list(RAIN_CATEGORIES.values()),
                                       output_dict=True, zero_division=0)
            cm = confusion_matrix(y_test_cls, y_pred_cls).tolist()
            cls_accuracy = float(cr.get("accuracy", 0))

            # ---- Binary classification: Rain vs No-Rain ----
            # Collapse classes 1/2/3 → 1 (any rain), 0 stays 0
            y_test_binary = (y_test_cls > 0).astype(int)
            y_pred_binary = (y_pred_cls > 0).astype(int)
            binary_cr = classification_report(
                y_test_binary, y_pred_binary,
                target_names=["No Rain", "Rain"],
                output_dict=True, zero_division=0,
            )
            binary_cm = confusion_matrix(y_test_binary, y_pred_binary).tolist()

            loss_curves.append(cls_loss)

            # SHAP for 1-hour ahead classifier only (expensive)
            if horizon == 1:
                shap_results["classification_1h"] = compute_shap(
                    cls_model, X_test, feature_cols, task="classification"
                )
        else:
            cls_accuracy = None
            cm = None
            cr = None
            binary_cr = None
            binary_cm = None
            logger.warning(f"  h={horizon}h: not enough class diversity for classification")

        # SHAP for regression
        if horizon == 1:
            shap_results["regression_1h"] = compute_shap(
                reg_model, X_test, feature_cols, task="regression"
            )

        loss_curves.append(reg_loss)

        # Feature importances (LightGBM native)
        fi = dict(zip(feature_cols,
                      reg_model.feature_importance(importance_type="gain")))
        top_features = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:15]

        horizon_results.append({
            "horizon_h": horizon,
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "n_test": int(len(X_test)),
            "regression": {
                "mae": round(float(mae_reg), 4),
                "rmse": round(float(rmse_reg), 4),
            },
            "classification": {
                "accuracy": round(float(cls_accuracy), 4) if cls_accuracy else None,
                "confusion_matrix": cm,
                "report": cr,
                "categories": RAIN_CATEGORIES,
            },
            "binary_classification": {
                "accuracy": round(float(binary_cr.get("accuracy", 0)), 4),
                "rain_precision": round(float(binary_cr.get("Rain", {}).get("precision", 0)), 4),
                "rain_recall": round(float(binary_cr.get("Rain", {}).get("recall", 0)), 4),
                "rain_f1": round(float(binary_cr.get("Rain", {}).get("f1-score", 0)), 4),
                "no_rain_recall": round(float(binary_cr.get("No Rain", {}).get("recall", 0)), 4),
                "confusion_matrix": binary_cm,
                "report": binary_cr,
            } if cls_accuracy else None,
            "feature_importance": [{"feature": f, "gain": round(float(g), 2)}
                                    for f, g in top_features],
        })

        logger.info(f"  h={horizon}h | Reg MAE={mae_reg:.4f} | "
                    f"Cls Acc={cls_accuracy:.3f}" if cls_accuracy else
                    f"  h={horizon}h | Reg MAE={mae_reg:.4f}")

        # Save regression model
        joblib.dump(
            {
                "model": reg_model,
                "feature_cols": feature_cols,
                "horizon_h": horizon,
                "trained_at": datetime.utcnow().isoformat(),
                "train_years": TRAIN_YEARS,
                "val_year": VAL_YEAR,
                "test_year": TEST_YEAR,
                "test_mae": float(mae_reg),
                "test_rmse": float(rmse_reg),
                "rain_categories": RAIN_CATEGORIES,
            },
            MODEL_DIR / f"rainfall_lgbm_{horizon}h.joblib",
        )
        if cls_accuracy:
            joblib.dump(
                {
                    "model": cls_model,
                    "feature_cols": feature_cols,
                    "horizon_h": horizon,
                    "trained_at": datetime.utcnow().isoformat(),
                    "categories": RAIN_CATEGORIES,
                    "test_accuracy": float(cls_accuracy),
                },
                MODEL_DIR / f"rainfall_cls_{horizon}h.joblib",
            )

    # --- Assemble full analysis JSON ---
    logger.info("\n[9/9] Saving full_analysis.json...")

    full_analysis = {
        "generated_at": datetime.utcnow().isoformat(),
        "description": (
            "LionWeather ML full analysis: climate trends, EDA, ACF/PACF, FFT, "
            "spurious correlations, SHAP, loss curves, classification & regression benchmarks. "
            f"Train 2016-2022 | Val 2023 | Test 2024."
        ),
        "rain_categories": RAIN_CATEGORIES,
        "climate_trends": climate_trends,
        "eda": eda,
        "stationarity": stationarity,
        "acf_pacf": acf_pacf,
        "spectral": spectral,
        "spurious_correlations": {
            "cross_correlation": cross_corr,
            "granger_causality": granger,
        },
        "model_results": horizon_results,
        "loss_curves": loss_curves,
        "shap": shap_results,
    }

    out_path = MODEL_DIR / "full_analysis.json"
    with open(out_path, "w") as f:
        json.dump(full_analysis, f, indent=2, default=str)

    logger.info(f"Saved → {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("DONE — SUMMARY")
    for r in horizon_results:
        h = r["horizon_h"]
        reg = r["regression"]
        cls = r["classification"]
        acc_str = f"| Cls Acc={cls['accuracy']:.3f}" if cls.get("accuracy") else ""
        logger.info(f"  {h}h: Reg MAE={reg['mae']:.4f} RMSE={reg['rmse']:.4f} {acc_str}")

    logger.info(f"\nTo serve results: /api/ml/full-analysis")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
