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

RAIN_CATEGORIES_3 = {0: "No Rain", 1: "Light Rain", 2: "Heavy + Thundery"}

# NEA forecast code → 4-class and 3-class
_NEA_CODE_4 = {
    "CL": 0, "FA": 0, "FN": 0, "FW": 0, "PC": 0, "PN": 0, "WD": 0,
    "LR": 1, "LS": 1, "SH": 1, "PS": 1,
    "RA": 2,
    "TL": 3, "HT": 3, "HG": 3,
}
_NEA_CODE_3 = {k: (0 if v == 0 else (1 if v == 1 else 2)) for k, v in _NEA_CODE_4.items()}

# Region station bounding boxes (lat_min, lat_max, lon_min, lon_max)
REGION_BOUNDS = {
    "north":   (1.38, 1.50, 103.75, 103.90),
    "south":   (1.22, 1.32, 103.75, 103.87),
    "east":    (1.30, 1.38, 103.87, 104.02),
    "west":    (1.30, 1.43, 103.62, 103.80),
    "central": (1.30, 1.38, 103.80, 103.87),
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


def rainfall_to_3class(mm_per_hour: float) -> int:
    """3-class: No Rain / Light Rain / Heavy+Thundery (deployed in app)"""
    if mm_per_hour < 0.1:
        return 0
    elif mm_per_hour < 7.6:
        return 1
    else:
        return 2


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
                  horizons: list,
                  ext_df: "pd.DataFrame | None" = None) -> pd.DataFrame:
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

    # ---- Singapore-specific meteorological features ----

    # Dry spell length: consecutive hours with no rain (reset on any rain > 0.1mm)
    # Long dry spells followed by rain tend to produce higher intensity events
    is_dry = (df["rainfall"] < 0.1).astype(int)
    dry_groups = (is_dry != is_dry.shift()).cumsum()
    df["dry_spell_hours"] = is_dry.groupby(dry_groups).cumsum() * is_dry

    # Rain streak length: consecutive rainy hours
    is_wet = (df["rainfall"] >= 0.1).astype(int)
    wet_groups = (is_wet != is_wet.shift()).cumsum()
    df["rain_streak_hours"] = is_wet.groupby(wet_groups).cumsum() * is_wet

    # Humidity deficit from saturation: lower = closer to rain-forming conditions
    df["hum_deficit"] = 100.0 - df["humidity"]

    # Humidity × temperature: proxy for wet-bulb / latent heat, predicts convection
    df["hum_temp_product"] = df["humidity"] * df["temperature"] / 100.0

    # Wind acceleration: rising wind speed is associated with approaching squall lines
    df["wind_accel_3h"] = df["wind_speed"] - df[f"wind_lag_3h"]

    # Singapore inter-monsoon peak indicator (Oct-Nov and Mar-Apr)
    # These months have highest thunderstorm frequency per NEA climatology
    df["is_inter_monsoon"] = df.index.month.isin([3, 4, 10, 11]).astype(int)

    # Afternoon convective peak (13:00-18:00 SGT = 05:00-10:00 UTC)
    # Morning secondary peak (06:00-09:00 SGT = 22:00-01:00 UTC previous day)
    hour_sgt = (df.index.hour + 8) % 24
    df["is_afternoon_peak"] = ((hour_sgt >= 13) & (hour_sgt <= 18)).astype(int)
    df["is_morning_peak"]   = ((hour_sgt >= 6)  & (hour_sgt <= 9)).astype(int)

    # Day of year (seasonal signal beyond just month)
    df["day_of_year"]    = df.index.dayofyear
    df["sin_day_of_year"] = np.sin(2 * np.pi * df.index.dayofyear / 365)
    df["cos_day_of_year"] = np.cos(2 * np.pi * df.index.dayofyear / 365)

    # ---- External features (cloud cover, radiation, wind dir, MJO) ----
    if ext_df is not None and not ext_df.empty:
        ext_aligned = ext_df.reindex(df.index).ffill()  # forward-fill only (no bfill — no future leakage)
        ext_cols = [
            "cloud_cover", "shortwave_radiation", "wind_direction_10m",
            "wind_dir_sin", "wind_dir_cos", "surface_pressure",
            "mjo_amplitude", "mjo_sin_phase", "mjo_cos_phase",
        ]
        for col in ext_cols:
            if col in ext_aligned.columns:
                df[col] = ext_aligned[col].values
                # Lag versions for cloud cover and radiation (key instability proxies)
                if col in ("cloud_cover", "shortwave_radiation"):
                    df[f"{col}_lag_1h"] = df[col].shift(1)
                    df[f"{col}_lag_3h"] = df[col].shift(3)
                    df[f"{col}_roll_6h"] = df[col].shift(1).rolling(6).mean()

    # Targets
    for h in horizons:
        df[f"target_rain_{h}h"]     = df["rainfall"].shift(-h)
        df[f"target_class_{h}h"]    = df[f"target_rain_{h}h"].apply(
            lambda v: rainfall_to_category(v) if pd.notna(v) else np.nan
        )
        df[f"target_class3_{h}h"]   = df[f"target_rain_{h}h"].apply(
            lambda v: rainfall_to_3class(v) if pd.notna(v) else np.nan
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
# 10. NEA forecast benchmark (from historical CSV)
# ===========================================================================

def _assign_region(lat: float, lon: float) -> str | None:
    """Assign a station to one of the 5 NEA regions based on coordinates."""
    for region, (lat_min, lat_max, lon_min, lon_max) in REGION_BOUNDS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return region
    return None


def load_regional_rainfall_6h(years: list) -> pd.DataFrame:
    """
    Load per-station rainfall, assign to NEA regions, aggregate to 6h regional sums.
    Returns a DataFrame indexed by (period_start, region) with column 'rainfall_mm'.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / "regional_6h_rainfall.parquet"
    if cache_path.exists():
        logger.info("  [regional] loading 6h regional rainfall from cache")
        return pd.read_parquet(cache_path)

    logger.info("  [regional] building 6h regional rainfall from station CSVs...")
    records = []
    for year in years:
        path = DATA_DIR / f"HistoricalRainfallacrossSingapore{year}.csv"
        if not path.exists():
            continue
        for chunk in pd.read_csv(
            path,
            usecols=["timestamp", "station_id", "location_latitude", "location_longitude", "reading_value"],
            chunksize=500_000,
            parse_dates=["timestamp"],
        ):
            chunk["region"] = chunk.apply(
                lambda r: _assign_region(r["location_latitude"], r["location_longitude"]), axis=1
            )
            chunk = chunk.dropna(subset=["region"])
            lo, hi = BOUNDS["rainfall"]
            chunk = chunk[(chunk["reading_value"] >= lo) & (chunk["reading_value"] <= hi)]
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], utc=True).dt.tz_convert("Asia/Singapore")
            # 6h buckets aligned to 0,6,12,18 SGT
            chunk["period_start"] = chunk["timestamp"].dt.floor("6h")
            records.append(chunk[["period_start", "region", "station_id", "reading_value"]])

    if not records:
        return pd.DataFrame()

    df = pd.concat(records, ignore_index=True)
    # Sum readings per station per period, then average across stations in region
    # (rainfall values are 5-min readings in mm, sum per station per 6h = total mm for that station)
    station_period = (
        df.groupby(["period_start", "region", "station_id"])["reading_value"]
        .sum()
        .reset_index()
        .rename(columns={"reading_value": "station_total_mm"})
    )
    regional = (
        station_period.groupby(["period_start", "region"])["station_total_mm"]
        .mean()  # mean across stations in region (mm per station per 6h)
        .reset_index()
        .rename(columns={"station_total_mm": "rainfall_mm"})
    )
    regional.to_parquet(cache_path)
    logger.info(f"  [regional] {len(regional)} region-period rows cached")
    return regional


def load_nea_forecasts_6h(years: list) -> pd.DataFrame:
    """
    Load NEA 24h forecast CSVs. Returns DataFrame with columns:
    period_start (SGT tz-aware), region, nea_class4, nea_class3
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / "nea_forecasts_6h.parquet"
    if cache_path.exists():
        logger.info("  [nea] loading NEA forecasts from cache")
        df = pd.read_parquet(cache_path)
        df["period_start"] = pd.to_datetime(df["period_start"]).dt.tz_localize("Asia/Singapore")
        return df

    logger.info("  [nea] parsing NEA forecast CSVs...")
    rows = []
    regions = ["north", "south", "east", "west", "central"]
    for year in years:
        path = DATA_DIR / f"Historical24hourWeatherForecast{year}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["time_period_start", "time_period_end"])
        df["time_period_start"] = pd.to_datetime(df["time_period_start"], utc=True).dt.tz_convert("Asia/Singapore")

        for _, row in df.iterrows():
            for region in regions:
                code = row.get(f"{region}_forecast_code")
                if pd.isna(code):
                    continue
                code = str(code).strip()
                cls4 = _NEA_CODE_4.get(code)
                cls3 = _NEA_CODE_3.get(code)
                if cls4 is None:
                    continue
                rows.append({
                    "period_start": row["time_period_start"].replace(tzinfo=None),
                    "region": region,
                    "nea_code": code,
                    "nea_class4": cls4,
                    "nea_class3": cls3,
                })

    result = pd.DataFrame(rows)
    # Drop duplicate (period_start, region) — keep last (most recent forecast update)
    result = result.drop_duplicates(subset=["period_start", "region"], keep="last")
    result.to_parquet(cache_path)
    logger.info(f"  [nea] {len(result)} region-period forecast rows cached")
    result["period_start"] = pd.to_datetime(result["period_start"]).dt.tz_localize("Asia/Singapore")
    return result


# ---------------------------------------------------------------------------
# NEA 2-hour per-area benchmark
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def load_nea_forecasts_2h(years: list) -> pd.DataFrame:
    """
    Load NEA 2-hour area forecast CSVs.
    Returns DataFrame with columns:
      period_start (SGT tz-aware), area_name, latitude, longitude, nea_class4, nea_class3
    One row per (period_start, area_name) — most-recently-issued forecast kept.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / "nea_forecasts_2h.parquet"
    if cache_path.exists():
        logger.info("  [nea2h] loading NEA 2h forecasts from cache")
        df = pd.read_parquet(cache_path)
        df["period_start"] = pd.to_datetime(df["period_start"]).dt.tz_localize("Asia/Singapore")
        return df

    logger.info("  [nea2h] parsing NEA 2h forecast CSVs...")
    dfs = []
    for year in years:
        path = DATA_DIR / f"Historical2hourWeatherForecast{year}.csv"
        if not path.exists():
            logger.warning(f"  [nea2h] missing: {path.name}")
            continue
        df = pd.read_csv(
            path,
            usecols=["valid_period_start", "update_timestamp",
                     "location_name", "location_longitude", "location_latitude",
                     "forecast_code"],
            parse_dates=["valid_period_start", "update_timestamp"],
        )
        df["valid_period_start"] = pd.to_datetime(df["valid_period_start"], utc=True).dt.tz_convert("Asia/Singapore")
        df["update_timestamp"]   = pd.to_datetime(df["update_timestamp"],   utc=True).dt.tz_convert("Asia/Singapore")
        dfs.append(df)
        logger.info(f"  [nea2h] {path.name}: {len(df):,} rows")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    # Keep latest forecast for each (period_start, area)
    combined = combined.sort_values("update_timestamp")
    combined = combined.drop_duplicates(subset=["valid_period_start", "location_name"], keep="last")

    # Map forecast codes
    combined["nea_class4"] = combined["forecast_code"].map(_NEA_CODE_4)
    combined["nea_class3"] = combined["forecast_code"].map(_NEA_CODE_3)
    combined = combined.dropna(subset=["nea_class4"])

    result = combined.rename(columns={
        "valid_period_start": "period_start",
        "location_name":      "area_name",
        "location_latitude":  "latitude",
        "location_longitude": "longitude",
    })[["period_start", "area_name", "latitude", "longitude", "nea_class4", "nea_class3"]]

    result["period_start"] = result["period_start"].dt.tz_localize(None)
    result.to_parquet(cache_path)
    logger.info(f"  [nea2h] {len(result)} area-period rows cached")
    result["period_start"] = pd.to_datetime(result["period_start"]).dt.tz_localize("Asia/Singapore")
    return result


def load_station_rainfall_2h(years: list) -> pd.DataFrame:
    """
    Load per-station rainfall aggregated to 2h buckets (aligned to even SGT hours).
    Returns DataFrame: period_start, station_id, station_name, latitude, longitude, rainfall_mm
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / "station_2h_rainfall.parquet"
    if cache_path.exists():
        logger.info("  [rain2h] loading station 2h rainfall from cache")
        return pd.read_parquet(cache_path)

    logger.info("  [rain2h] building station 2h rainfall from CSVs...")
    records = []
    for year in years:
        path = DATA_DIR / f"HistoricalRainfallacrossSingapore{year}.csv"
        if not path.exists():
            continue
        for chunk in pd.read_csv(
            path,
            usecols=["timestamp", "station_id", "station_name",
                     "location_latitude", "location_longitude", "reading_value"],
            chunksize=500_000,
            parse_dates=["timestamp"],
        ):
            lo, hi = BOUNDS["rainfall"]
            chunk = chunk[(chunk["reading_value"] >= lo) & (chunk["reading_value"] <= hi)]
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], utc=True).dt.tz_convert("Asia/Singapore")
            # 2h buckets aligned to even hours
            chunk["period_start"] = chunk["timestamp"].dt.floor("2h")
            records.append(chunk[["period_start", "station_id", "station_name",
                                  "location_latitude", "location_longitude", "reading_value"]])

    if not records:
        return pd.DataFrame()

    df = pd.concat(records, ignore_index=True)
    # Sum readings per station per 2h period (readings are 5-min mm totals)
    station_locs = (df.groupby("station_id")[["station_name", "location_latitude", "location_longitude"]]
                    .first().reset_index())
    agg = (df.groupby(["period_start", "station_id"])["reading_value"]
           .sum().reset_index().rename(columns={"reading_value": "rainfall_mm"}))
    agg = agg.merge(station_locs, on="station_id", how="left")
    agg["period_start"] = agg["period_start"].dt.tz_localize(None)
    agg.to_parquet(cache_path)
    logger.info(f"  [rain2h] {len(agg)} station-period rows cached")
    return agg


def compute_nea_2h_area_benchmark(
    nea_2h: pd.DataFrame,
    station_rain_2h: pd.DataFrame,
    feat_df: pd.DataFrame,
    cls_models: dict,
    cls3_models: dict,
    feature_cols: list,
    test_year: int,
) -> dict:
    """
    Compare NEA 2-hour per-area forecasts vs actual station rainfall (2024 holdout).

    Two sub-comparisons:
    1. per_area_nea:  NEA area forecast vs actual at nearest station — pure NEA accuracy.
    2. island_wide:   Both aggregated to island-wide majority vote — fair ML vs NEA comparison.
    """
    from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, fbeta_score

    def _rain_f2(y_true_arr, y_pred_arr, n):
        """F2 score on rain classes only (class > 0). β=2 → recall weighted 2x."""
        rain_labels = list(range(1, n))
        if len(rain_labels) == 0:
            return 0.0
        return float(fbeta_score(y_true_arr, y_pred_arr, beta=2,
                                  average="macro", labels=rain_labels, zero_division=0))

    def _rain_recall(report_dict, cats_dict, n):
        """Average recall across all rain classes (class > 0)."""
        recalls = [report_dict.get(cats_dict[i], {}).get("recall", 0) for i in range(1, n)]
        return float(np.mean(recalls)) if recalls else 0.0

    # Filter to test year
    nea_t = nea_2h[nea_2h["period_start"].dt.year == test_year].copy()
    rain_t = station_rain_2h[station_rain_2h["period_start"].dt.year == test_year].copy()

    # Normalise period_start to tz-naive for consistent merging
    if nea_t["period_start"].dt.tz is not None:
        nea_t["period_start"] = nea_t["period_start"].dt.tz_localize(None)
    if not rain_t.empty and rain_t["period_start"].dt.tz is not None:
        rain_t["period_start"] = rain_t["period_start"].dt.tz_localize(None)

    if nea_t.empty or rain_t.empty:
        return {"error": "no data for test year"}

    # ---- Build station lookup ----
    stations = (station_rain_2h[["station_id", "station_name",
                                  "location_latitude", "location_longitude"]]
                .drop_duplicates("station_id"))

    # ---- Map each NEA area to nearest station ----
    area_station_map = {}  # area_name -> station_id
    unique_areas = nea_t[["area_name", "latitude", "longitude"]].drop_duplicates("area_name")
    for _, row in unique_areas.iterrows():
        best_sid, best_dist = None, 999.0
        for _, st in stations.iterrows():
            d = _haversine_km(row["latitude"], row["longitude"],
                              st["location_latitude"], st["location_longitude"])
            if d < best_dist:
                best_dist = d
                best_sid = st["station_id"]
        if best_dist <= 10.0:  # accept if within 10 km
            area_station_map[row["area_name"]] = best_sid
        else:
            logger.debug(f"  [nea2h] {row['area_name']}: nearest station {best_dist:.1f} km — excluded")

    logger.info(f"  [nea2h] {len(area_station_map)}/{len(unique_areas)} areas mapped to stations")

    nea_t = nea_t[nea_t["area_name"].isin(area_station_map)].copy()
    nea_t["station_id"] = nea_t["area_name"].map(area_station_map)

    # ---- ML predictions (1h-ahead, island-wide) aggregated to 2h ----
    ml_hourly = feat_df[feat_df.index.year == test_year].copy()
    if ml_hourly.index.tz is None:
        ml_hourly.index = ml_hourly.index.tz_localize("Asia/Singapore")

    ml_preds = {}
    for n_class, models_dict in [(4, cls_models), (3, cls3_models)]:
        model = models_dict.get(1)
        if model is None:
            continue
        valid = ml_hourly[feature_cols].dropna()
        proba = model.predict(valid.values)
        pred_classes = np.argmax(proba, axis=1)
        period_starts = valid.index.floor("2h").tz_localize(None)
        tmp = pd.DataFrame({
            "period_start": period_starts,
            "ml_class":     pred_classes,
            **{f"ml_p{c}": proba[:, c] for c in range(n_class)},
        })
        ml_preds[n_class] = (tmp.groupby("period_start")
                             .agg(ml_class=("ml_class", lambda x: x.mode().iloc[0]),
                                  **{f"ml_p{c}": (f"ml_p{c}", "mean") for c in range(n_class)})
                             .reset_index())

    results = {}

    for n_class in [3, 4]:
        target_col = f"nea_class{n_class}"
        cats = RAIN_CATEGORIES_3 if n_class == 3 else RAIN_CATEGORIES
        fn_cls = rainfall_to_3class if n_class == 3 else rainfall_to_category

        nea_sub = nea_t[["period_start", "area_name", "station_id", target_col]].copy()
        nea_sub[target_col] = nea_sub[target_col].astype(float)

        # Merge actual rainfall from nearest station
        rain_sub = rain_t[["period_start", "station_id", "rainfall_mm"]].copy()
        rain_sub["period_start"] = pd.to_datetime(rain_sub["period_start"])
        nea_sub["period_start"]  = pd.to_datetime(nea_sub["period_start"])
        merged = nea_sub.merge(rain_sub, on=["period_start", "station_id"], how="inner")
        merged["actual_class"] = merged["rainfall_mm"].apply(fn_cls)

        if merged.empty:
            continue

        # ------ 1. Per-area NEA accuracy ------
        y_true = merged["actual_class"].values.astype(int)
        y_nea  = merged[target_col].values.astype(int)
        nea_acc = float(accuracy_score(y_true, y_nea))
        nea_cm  = confusion_matrix(y_true, y_nea, labels=list(range(n_class))).tolist()
        nea_cr  = classification_report(y_true, y_nea, labels=list(range(n_class)),
                                        target_names=list(cats.values()),
                                        output_dict=True, zero_division=0)
        nea_f2   = _rain_f2(y_true, y_nea, n_class)
        nea_rr   = _rain_recall(nea_cr, cats, n_class)

        # Per-area breakdown
        per_area = {}
        for area, grp in merged.groupby("area_name"):
            yt = grp["actual_class"].values.astype(int)
            yn = grp[target_col].values.astype(int)
            per_area[area] = {
                "n_samples": int(len(yt)),
                "nea_accuracy": round(float(accuracy_score(yt, yn)), 4),
            }

        # ------ 1b. Per-area ML accuracy (apply island-wide prediction to every area) ------
        # This is a fair per-area comparison: NEA uses area-specific knowledge;
        # ML uses one island-wide prediction replicated for all 47 areas.
        ml_df = ml_preds.get(n_class)
        ml_per_area_result = None
        per_area_ens_result = None
        if ml_df is not None:
            proba_cols = [f"ml_p{c}" for c in range(n_class)]
            merged_ml = merged.merge(
                ml_df[["period_start", "ml_class"] + proba_cols], on="period_start", how="left"
            )
            ml_valid = merged_ml.dropna(subset=["ml_class"])
            if len(ml_valid) > 0:
                ml_pa_y_true = ml_valid["actual_class"].values.astype(int)
                ml_pa_y_pred = ml_valid["ml_class"].values.astype(int)
                ml_pa_acc = float(accuracy_score(ml_pa_y_true, ml_pa_y_pred))
                ml_pa_cr  = classification_report(ml_pa_y_true, ml_pa_y_pred,
                                                   labels=list(range(n_class)),
                                                   target_names=list(cats.values()),
                                                   output_dict=True, zero_division=0)
                ml_f2  = _rain_f2(ml_pa_y_true, ml_pa_y_pred, n_class)
                ml_rr  = _rain_recall(ml_pa_cr, cats, n_class)

                # Per-area ensemble: blend ML island-wide proba with NEA area forecast
                ml_pa_proba = merged_ml.loc[ml_valid.index, [f"ml_p{c}" for c in range(n_class)]].values \
                    if all(f"ml_p{c}" in merged_ml.columns for c in range(n_class)) else None
                if ml_pa_proba is not None and len(ml_pa_proba) == len(ml_valid):
                    nea_pa_soft = np.zeros((len(ml_valid), n_class))
                    for ii, cls_v in enumerate(ml_valid[target_col].values):
                        if not pd.isna(cls_v):
                            nea_pa_soft[ii, int(cls_v)] = 0.7
                            for jj in range(n_class):
                                if jj != int(cls_v):
                                    nea_pa_soft[ii, jj] = 0.3 / (n_class - 1)
                    pa_ens_proba = 0.6 * ml_pa_proba + 0.4 * nea_pa_soft
                    pa_y_ens = np.argmax(pa_ens_proba, axis=1)
                    pa_ens_acc = float(accuracy_score(ml_pa_y_true, pa_y_ens))
                    pa_ens_f2  = _rain_f2(ml_pa_y_true, pa_y_ens, n_class)
                    pa_ens_cr  = classification_report(ml_pa_y_true, pa_y_ens, labels=list(range(n_class)),
                                                       target_names=list(cats.values()),
                                                       output_dict=True, zero_division=0)
                    per_area_ens_result = {
                        "accuracy": round(pa_ens_acc, 4),
                        "rain_f2":  round(pa_ens_f2, 4),
                        "report":   pa_ens_cr,
                        "note": "ensemble 60% ML + 40% NEA applied per area",
                    }
                else:
                    per_area_ens_result = None

                ml_per_area_result = {
                    "accuracy": round(ml_pa_acc, 4),
                    "rain_recall": round(ml_rr, 4),
                    "rain_f2": round(ml_f2, 4),
                    "n_samples": int(len(ml_valid)),
                    "report": ml_pa_cr,
                    "note": "island-wide ML prediction applied to each of 47 areas",
                }
                logger.info(f"  [2h {n_class}-class] NEA per-area acc={nea_acc:.3f} f2={nea_f2:.3f} | ML per-area acc={ml_pa_acc:.3f} f2={ml_f2:.3f}")

        # ------ 2. Island-wide (fair ML comparison) ------
        # Majority vote across all areas per 2h period
        iw_actual = (merged.groupby("period_start")["actual_class"]
                     .agg(lambda x: x.mode().iloc[0]).reset_index())
        iw_nea_df = (merged.groupby("period_start")[target_col]
                     .agg(lambda x: x.mode().iloc[0]).reset_index())
        iw_merged = iw_actual.merge(iw_nea_df, on="period_start", how="inner")

        if ml_df is not None:
            iw_merged = iw_merged.merge(
                ml_df[["period_start", "ml_class"] + [f"ml_p{c}" for c in range(n_class)]],
                on="period_start", how="left"
            )

        iw_results = {}
        if not iw_merged.empty:
            iw_y_true = iw_merged["actual_class"].values.astype(int)
            iw_y_nea  = iw_merged[target_col].values.astype(int)
            iw_nea_acc = float(accuracy_score(iw_y_true, iw_y_nea))
            iw_nea_cm  = confusion_matrix(iw_y_true, iw_y_nea, labels=list(range(n_class))).tolist()
            iw_nea_cr  = classification_report(iw_y_true, iw_y_nea, labels=list(range(n_class)),
                                               target_names=list(cats.values()),
                                               output_dict=True, zero_division=0)
            iw_nea_f2 = _rain_f2(iw_y_true, iw_y_nea, n_class)
            iw_results["nea"] = {"accuracy": round(iw_nea_acc, 4), "rain_f2": round(iw_nea_f2, 4),
                                  "confusion_matrix": iw_nea_cm, "report": iw_nea_cr}

            if ml_df is not None and "ml_class" in iw_merged.columns:
                iw_y_ml = iw_merged["ml_class"].values
                iw_valid = ~pd.isna(iw_y_ml)
                iw_y_ml_v  = iw_y_ml[iw_valid].astype(int)
                iw_y_true_v = iw_y_true[iw_valid]
                if len(iw_y_ml_v):
                    iw_ml_acc = float(accuracy_score(iw_y_true_v, iw_y_ml_v))
                    iw_ml_cm  = confusion_matrix(iw_y_true_v, iw_y_ml_v,
                                                  labels=list(range(n_class))).tolist()
                    iw_ml_cr  = classification_report(iw_y_true_v, iw_y_ml_v,
                                                       labels=list(range(n_class)),
                                                       target_names=list(cats.values()),
                                                       output_dict=True, zero_division=0)
                    iw_ml_f2  = _rain_f2(iw_y_true_v, iw_y_ml_v, n_class)
                    iw_results["ml_island_wide"] = {
                        "accuracy": round(iw_ml_acc, 4), "rain_f2": round(iw_ml_f2, 4),
                        "confusion_matrix": iw_ml_cm, "report": iw_ml_cr,
                    }
                    iw_results["n_samples"] = int(iw_valid.sum())

                    # Ensemble 60/40
                    ens_rows = iw_merged[iw_valid].copy()
                    iw_ml_proba = ens_rows[[f"ml_p{c}" for c in range(n_class)]].values
                    iw_nea_soft = np.zeros((len(ens_rows), n_class))
                    for ii, cls in enumerate(ens_rows[target_col].values):
                        if not pd.isna(cls):
                            iw_nea_soft[ii, int(cls)] = 0.7
                            for jj in range(n_class):
                                if jj != int(cls):
                                    iw_nea_soft[ii, jj] = 0.3 / (n_class - 1)
                    iw_ens_proba = 0.6 * iw_ml_proba + 0.4 * iw_nea_soft
                    iw_y_ens = np.argmax(iw_ens_proba, axis=1)
                    iw_ens_acc = float(accuracy_score(iw_y_true_v, iw_y_ens))
                    iw_ens_cm  = confusion_matrix(iw_y_true_v, iw_y_ens,
                                                   labels=list(range(n_class))).tolist()
                    iw_ens_cr  = classification_report(iw_y_true_v, iw_y_ens,
                                                        labels=list(range(n_class)),
                                                        target_names=list(cats.values()),
                                                        output_dict=True, zero_division=0)
                    iw_results["ensemble_60ml_40nea"] = {
                        "accuracy": round(iw_ens_acc, 4),
                        "confusion_matrix": iw_ens_cm, "report": iw_ens_cr,
                    }
                    logger.info(f"  [2h IW {n_class}-class] NEA={iw_nea_acc:.3f} ML={iw_ml_acc:.3f} Ens={iw_ens_acc:.3f}")

        results[f"class{n_class}"] = {
            "n_area_period_samples": int(len(merged)),
            "n_areas": int(len(per_area)),
            "per_area_nea": {
                "accuracy": round(nea_acc, 4),
                "rain_recall": round(nea_rr, 4),
                "rain_f2": round(nea_f2, 4),
                "confusion_matrix": nea_cm,
                "report": nea_cr,
                "note": "NEA 2h per-area forecast accuracy vs nearest station actual (47 areas).",
                "per_area": per_area,
            },
            "per_area_ml": ml_per_area_result,
            "per_area_ensemble": per_area_ens_result if ml_df is not None else None,
            "island_wide": {
                **iw_results,
                "note": "Both NEA and actual aggregated to island-wide via majority vote across all 47 areas. Fair apples-to-apples comparison with ML island-wide prediction.",
            },
        }

    return {
        "description": (
            "NEA 2h per-area forecast vs actual station rainfall (nearest station, ≤10 km). "
            "per_area_nea: NEA area-level accuracy (NEA's natural granularity — ML not compared here). "
            "island_wide: both aggregated to island-wide majority vote for fair ML vs NEA comparison. "
            f"Test year: {test_year}."
        ),
        "test_year": test_year,
        "overall": results,
    }


def compute_nea_regional_benchmark(
    regional_rain: pd.DataFrame,
    nea_forecasts: pd.DataFrame,
    feat_df: pd.DataFrame,
    cls_models: dict,       # {horizon_h: lgb_model}
    cls3_models: dict,      # {horizon_h: lgb_model}
    feature_cols: list,
    test_year: int,
) -> dict:
    """
    Apples-to-apples benchmark: NEA 6h regional forecasts vs actual 6h regional rainfall.
    Also evaluates ML island-wide model on same 6h blocks, and blends them.

    Returns dict with per-region and overall metrics.
    """
    from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, fbeta_score

    def _rain_f2_6h(y_true_arr, y_pred_arr, n):
        rain_labels = list(range(1, n))
        return float(fbeta_score(y_true_arr, y_pred_arr, beta=2,
                                  average="macro", labels=rain_labels, zero_division=0))

    regions = ["north", "south", "east", "west", "central"]

    # Filter to test year
    actual = regional_rain[regional_rain["period_start"].dt.year == test_year].copy()
    nea    = nea_forecasts[nea_forecasts["period_start"].dt.year == test_year].copy()

    # ML: get island-wide hourly predictions for test year, aggregate to 6h
    # Use the 1h-ahead classifier (closest to nowcast) for each block's start
    ml_hourly = feat_df[feat_df.index.year == test_year].copy()
    # Ensure tz-aware index in SGT
    if ml_hourly.index.tz is None:
        ml_hourly.index = ml_hourly.index.tz_localize("Asia/Singapore")

    # Precompute ML 3-class and 4-class predictions hour-by-hour
    ml_preds = {}
    for n_class, models_dict in [(4, cls_models), (3, cls3_models)]:
        model = models_dict.get(1)  # use 1h model
        if model is None:
            continue
        valid = ml_hourly[feature_cols].dropna()
        proba = model.predict(valid.values)  # shape (N, n_class)
        pred_classes = np.argmax(proba, axis=1)
        # Map each hour → 6h period
        period_starts = valid.index.floor("6h")
        ml_preds[n_class] = pd.DataFrame({
            "period_start": period_starts,
            "ml_class": pred_classes,
            **{f"ml_p{c}": proba[:, c] for c in range(n_class)},
        })
        # Per-period: take the max predicted class (worst case is most useful)
        # or majority vote. We'll do majority vote (mode).
        ml_preds[n_class] = (
            ml_preds[n_class]
            .groupby("period_start")
            .agg(ml_class=("ml_class", lambda x: x.mode().iloc[0]),
                 **{f"ml_p{c}": (f"ml_p{c}", "mean") for c in range(n_class)})
            .reset_index()
        )

    overall_results = {}
    per_region_results = {}

    for n_class in [3, 4]:
        target_col = f"nea_class{n_class}"
        cats = RAIN_CATEGORIES_3 if n_class == 3 else RAIN_CATEGORIES
        fn_cls = rainfall_to_3class if n_class == 3 else rainfall_to_category

        actual_cls = actual.copy()
        actual_cls["actual_class"] = actual_cls["rainfall_mm"].apply(fn_cls)

        ml_df = ml_preds.get(n_class)

        merged = actual_cls.merge(nea[["period_start", "region", target_col]], on=["period_start", "region"], how="inner")
        if ml_df is not None:
            merged = merged.merge(ml_df[["period_start", "ml_class"] + [f"ml_p{c}" for c in range(n_class)]], on="period_start", how="left")

        if merged.empty:
            logger.warning(f"  NEA benchmark: no matched rows for {n_class}-class")
            continue

        # ---- Island-wide aggregate (FAIR apples-to-apples comparison) ----
        # Problem with per-region: ML is island-wide (same prediction for all 5 regions)
        # while NEA is region-specific. This inflates ML sample count 5x with identical
        # predictions but different actuals. Fix: aggregate both to island-wide first.
        #
        # Aggregation rule: majority vote (mode) across all regions per period.
        # This answers: "What was the dominant rain condition island-wide this 6h window?"
        iw_actual = (actual_cls.groupby("period_start")["actual_class"]
                     .agg(lambda x: x.mode().iloc[0]).reset_index())
        iw_nea_df = (nea[["period_start", "region", target_col]]
                     .dropna(subset=[target_col])
                     .groupby("period_start")[target_col]
                     .agg(lambda x: x.mode().iloc[0]).reset_index())
        iw_merged = iw_actual.merge(iw_nea_df, on="period_start", how="inner")
        if ml_df is not None:
            iw_merged = iw_merged.merge(
                ml_df[["period_start", "ml_class"] + [f"ml_p{c}" for c in range(n_class)]],
                on="period_start", how="left"
            )

        iw_results = {}
        if not iw_merged.empty:
            iw_y_true = iw_merged["actual_class"].values.astype(int)
            iw_y_nea  = iw_merged[target_col].values.astype(int)
            iw_nea_acc = float(accuracy_score(iw_y_true, iw_y_nea))
            iw_nea_cm  = confusion_matrix(iw_y_true, iw_y_nea, labels=list(range(n_class))).tolist()
            iw_nea_cr  = classification_report(iw_y_true, iw_y_nea, labels=list(range(n_class)),
                                               target_names=list(cats.values()),
                                               output_dict=True, zero_division=0)
            iw_nea_f2 = _rain_f2_6h(iw_y_true, iw_y_nea, n_class)
            iw_results["nea"] = {"accuracy": round(iw_nea_acc, 4), "rain_f2": round(iw_nea_f2, 4), "confusion_matrix": iw_nea_cm, "report": iw_nea_cr}

            if ml_df is not None and "ml_class" in iw_merged.columns:
                iw_y_ml = iw_merged["ml_class"].values
                iw_valid = ~pd.isna(iw_y_ml)
                iw_y_ml_v = iw_y_ml[iw_valid].astype(int)
                iw_y_true_v = iw_y_true[iw_valid]
                if len(iw_y_ml_v):
                    iw_ml_acc = float(accuracy_score(iw_y_true_v, iw_y_ml_v))
                    iw_ml_f2  = _rain_f2_6h(iw_y_true_v, iw_y_ml_v, n_class)
                    iw_ml_cm  = confusion_matrix(iw_y_true_v, iw_y_ml_v, labels=list(range(n_class))).tolist()
                    iw_ml_cr  = classification_report(iw_y_true_v, iw_y_ml_v, labels=list(range(n_class)),
                                                      target_names=list(cats.values()),
                                                      output_dict=True, zero_division=0)
                    iw_results["ml_island_wide"] = {"accuracy": round(iw_ml_acc, 4), "rain_f2": round(iw_ml_f2, 4), "confusion_matrix": iw_ml_cm, "report": iw_ml_cr}
                    iw_results["n_samples"] = int(iw_valid.sum())

                    # Ensemble
                    iw_ens_rows = iw_merged[iw_valid].copy()
                    iw_ml_proba = iw_ens_rows[[f"ml_p{c}" for c in range(n_class)]].values
                    iw_nea_soft = np.zeros((len(iw_ens_rows), n_class))
                    for ii, cls in enumerate(iw_ens_rows[target_col].values):
                        if not pd.isna(cls):
                            iw_nea_soft[ii, int(cls)] = 0.7
                            for jj in range(n_class):
                                if jj != int(cls):
                                    iw_nea_soft[ii, jj] = 0.3 / (n_class - 1)
                    iw_ens_proba = 0.6 * iw_ml_proba + 0.4 * iw_nea_soft
                    iw_y_ens = np.argmax(iw_ens_proba, axis=1)
                    iw_ens_acc = float(accuracy_score(iw_y_true_v, iw_y_ens))
                    iw_ens_cm  = confusion_matrix(iw_y_true_v, iw_y_ens, labels=list(range(n_class))).tolist()
                    iw_ens_cr  = classification_report(iw_y_true_v, iw_y_ens, labels=list(range(n_class)),
                                                       target_names=list(cats.values()),
                                                       output_dict=True, zero_division=0)
                    iw_results["ensemble_60ml_40nea"] = {"accuracy": round(iw_ens_acc, 4), "confusion_matrix": iw_ens_cm, "report": iw_ens_cr}
                    logger.info(f"  [IW {n_class}-class] NEA acc={iw_nea_acc:.3f} | ML acc={iw_ml_acc:.3f} | Ens acc={iw_ens_acc:.3f}")

        # ---- Per-region metrics (legacy — NEA has advantage here since it's regional) ----
        y_true = merged["actual_class"].values
        y_nea  = merged[target_col].values
        valid_mask = ~(pd.isna(y_nea))
        y_true = y_true[valid_mask].astype(int)
        y_nea  = y_nea[valid_mask].astype(int)

        nea_acc = float(accuracy_score(y_true, y_nea))
        nea_cm  = confusion_matrix(y_true, y_nea, labels=list(range(n_class))).tolist()
        nea_cr  = classification_report(y_true, y_nea, labels=list(range(n_class)),
                                        target_names=list(cats.values()),
                                        output_dict=True, zero_division=0)

        ml_acc = None; ml_cm = None; ml_cr = None
        ens_acc = None; ens_cm = None; ens_cr = None

        if ml_df is not None and "ml_class" in merged.columns:
            y_ml = merged["ml_class"].values[valid_mask]
            y_ml_valid = y_ml[~pd.isna(y_ml)].astype(int)
            y_true_ml  = y_true[~pd.isna(y_ml)]
            if len(y_ml_valid):
                ml_acc = float(accuracy_score(y_true_ml, y_ml_valid))
                ml_cm  = confusion_matrix(y_true_ml, y_ml_valid, labels=list(range(n_class))).tolist()
                ml_cr  = classification_report(y_true_ml, y_ml_valid, labels=list(range(n_class)),
                                               target_names=list(cats.values()),
                                               output_dict=True, zero_division=0)

                # Ensemble: 60% ML + 40% NEA (one-hot softened)
                ens_rows = merged[valid_mask][~pd.isna(merged["ml_class"].values[valid_mask])].copy()
                ml_proba = ens_rows[[f"ml_p{c}" for c in range(n_class)]].values
                nea_soft = np.zeros((len(ens_rows), n_class))
                for i, cls in enumerate(ens_rows[target_col].values):
                    if not pd.isna(cls):
                        nea_soft[i, int(cls)] = 0.7
                        for j in range(n_class):
                            if j != int(cls):
                                nea_soft[i, j] = 0.3 / (n_class - 1)
                ens_proba = 0.6 * ml_proba + 0.4 * nea_soft
                y_ens = np.argmax(ens_proba, axis=1)
                y_true_ens = ens_rows["actual_class"].values.astype(int)
                ens_acc = float(accuracy_score(y_true_ens, y_ens))
                ens_cm  = confusion_matrix(y_true_ens, y_ens, labels=list(range(n_class))).tolist()
                ens_cr  = classification_report(y_true_ens, y_ens, labels=list(range(n_class)),
                                                target_names=list(cats.values()),
                                                output_dict=True, zero_division=0)

                logger.info(f"  [regional {n_class}-class] NEA acc={nea_acc:.3f} | ML acc={ml_acc:.3f} | Ensemble acc={ens_acc:.3f}")

        nea_f2_reg = _rain_f2_6h(y_true, y_nea, n_class)
        overall_results[f"class{n_class}"] = {
            "n_samples": int(len(y_true)),
            "note": "Per-region stacked: NEA regional forecasts vs regional actuals (NEA advantage — region-specific). ML applies same island-wide prediction to each of 5 regions.",
            "nea": {"accuracy": round(nea_acc, 4), "rain_f2": round(nea_f2_reg, 4), "confusion_matrix": nea_cm, "report": nea_cr},
            "ml_island_wide": {"accuracy": round(ml_acc, 4), "rain_f2": round(_rain_f2_6h(y_true[~pd.isna(merged["ml_class"].values[valid_mask])], y_ml_valid, n_class), 4), "confusion_matrix": ml_cm, "report": ml_cr} if ml_acc else None,
            "ensemble_60ml_40nea": {"accuracy": round(ens_acc, 4), "rain_f2": round(_rain_f2_6h(y_true_ens, y_ens, n_class), 4), "confusion_matrix": ens_cm, "report": ens_cr} if ens_acc else None,
            "island_wide": iw_results,  # Fair comparison: both aggregated to island-wide majority vote
        }

        # ---- Per-region metrics ----
        per_region_results[f"class{n_class}"] = {}
        for region in regions:
            r_merged = merged[merged["region"] == region]
            if r_merged.empty:
                continue
            y_t = r_merged["actual_class"].values.astype(int)
            y_n = r_merged[target_col].values
            v = ~pd.isna(y_n)
            y_t, y_n = y_t[v].astype(int), y_n[v].astype(int)
            if len(y_t) == 0:
                continue
            per_region_results[f"class{n_class}"][region] = {
                "n_samples": int(len(y_t)),
                "nea_accuracy": round(float(accuracy_score(y_t, y_n)), 4),
                "nea_confusion_matrix": confusion_matrix(y_t, y_n, labels=list(range(n_class))).tolist(),
            }
            if ml_df is not None and "ml_class" in r_merged.columns:
                y_ml_r = r_merged["ml_class"].values[v]
                v2 = ~pd.isna(y_ml_r)
                if v2.sum():
                    per_region_results[f"class{n_class}"][region]["ml_accuracy"] = round(
                        float(accuracy_score(y_t[v2], y_ml_r[v2].astype(int))), 4
                    )

    return {
        "description": (
            "NEA 6h regional forecast vs actual 6h station observations (2024 holdout). "
            "overall.classN = per-region stacked (NEA has advantage: region-specific predictions). "
            "overall.classN.island_wide = FAIR comparison: both aggregated to island-wide majority vote per period."
        ),
        "test_year": test_year,
        "overall": overall_results,
        "per_region": per_region_results,
    }


# ===========================================================================
# 11. Main
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

    logger.info("\n[2/8] Loading external features (CAPE, MJO)…")
    try:
        sys.path.insert(0, str(BASE_DIR))
        from fetch_external_features import load_all_external_features
        ext_df = load_all_external_features()
        logger.info(f"  External features: {len(ext_df)} rows, {len(ext_df.columns)} cols")
    except Exception as e:
        logger.warning(f"  External features unavailable ({e}) — training without them")
        ext_df = None

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
    feat_df = make_features(rain_h, temp_h, hum_h, wind_h, HORIZONS, ext_df=ext_df)
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

    # --- 3-class model training ---
    logger.info("\n[8b] Training 3-class models (No Rain / Light Rain / Heavy+Thundery)...")
    cls3_models = {}
    three_class_results = []

    for horizon in HORIZONS:
        cls3_target = f"target_class3_{horizon}h"
        cols_needed = feature_cols + [cls3_target]
        sub = feat_df[cols_needed].dropna()

        train_sub = sub[sub.index.year.isin(TRAIN_YEARS)]
        val_sub   = sub[sub.index.year == VAL_YEAR]
        test_sub  = sub[sub.index.year == TEST_YEAR]

        if len(train_sub) < 500:
            continue

        X_train = train_sub[feature_cols].values
        X_val   = val_sub[feature_cols].values
        X_test  = test_sub[feature_cols].values
        y_train = train_sub[cls3_target].values.astype(int)
        y_val   = val_sub[cls3_target].values.astype(int)
        y_test  = test_sub[cls3_target].values.astype(int)

        # Cost weights: No Rain=1, Light Rain=2, Heavy+Thundery=5
        COST3 = np.array([1.0, 2.0, 5.0])
        weights = COST3[y_train]

        import lightgbm as lgb
        train_set = lgb.Dataset(X_train, label=y_train, weight=weights)
        val_set   = lgb.Dataset(X_val,   label=y_val, reference=train_set)
        params = {
            "objective": "multiclass", "num_class": 3,
            "metric": ["multi_logloss"], "learning_rate": 0.05,
            "num_leaves": 63, "min_child_samples": 50,
            "feature_fraction": 0.8, "bagging_fraction": 0.8,
            "bagging_freq": 5, "verbose": -1,
        }
        evals_result = {}
        model3 = lgb.train(
            params, train_set, num_boost_round=1000,
            valid_sets=[train_set, val_set], valid_names=["train", "val"],
            callbacks=[lgb.early_stopping(50, verbose=False),
                       lgb.log_evaluation(200),
                       lgb.record_evaluation(evals_result)],
        )
        cls3_models[horizon] = model3

        y_pred = np.argmax(model3.predict(X_test), axis=1)
        cr3 = classification_report(y_test, y_pred, target_names=list(RAIN_CATEGORIES_3.values()),
                                    output_dict=True, zero_division=0)
        cm3 = confusion_matrix(y_test, y_pred).tolist()
        acc3 = float(cr3.get("accuracy", 0))

        logger.info(f"  3-class h={horizon}h | Acc={acc3:.3f}")

        joblib.dump({"model": model3, "feature_cols": feature_cols, "horizon_h": horizon,
                     "trained_at": datetime.utcnow().isoformat(), "categories": RAIN_CATEGORIES_3,
                     "test_accuracy": acc3},
                    MODEL_DIR / f"rainfall_cls3_{horizon}h.joblib")

        three_class_results.append({
            "horizon_h": horizon,
            "n_train": int(len(X_train)), "n_val": int(len(X_val)), "n_test": int(len(X_test)),
            "accuracy": round(acc3, 4),
            "confusion_matrix": cm3,
            "report": cr3,
            "categories": RAIN_CATEGORIES_3,
        })

    # --- NEA benchmark ---
    logger.info("\n[8c] Computing NEA regional benchmark...")
    nea_benchmark = {}
    try:
        # Also need 4-class cls_models dict — collect from the existing training loop
        cls4_models = {}
        for horizon in HORIZONS:
            p = MODEL_DIR / f"rainfall_cls_{horizon}h.joblib"
            if p.exists():
                obj = joblib.load(p)
                cls4_models[horizon] = obj["model"]

        regional_rain = load_regional_rainfall_6h(all_years)
        nea_fcst = load_nea_forecasts_6h(all_years)

        if not regional_rain.empty and not nea_fcst.empty:
            nea_benchmark = compute_nea_regional_benchmark(
                regional_rain, nea_fcst, feat_df,
                cls4_models, cls3_models, feature_cols, TEST_YEAR
            )
            logger.info("  NEA 6h regional benchmark complete")
        else:
            logger.warning("  NEA 6h benchmark skipped: insufficient data")
    except Exception as e:
        logger.warning(f"  NEA 6h benchmark failed: {e}")
        nea_benchmark = {"error": str(e)}

    # --- NEA 2-hour per-area benchmark ---
    logger.info("\n[8d] Computing NEA 2-hour per-area benchmark...")
    nea_2h_benchmark = {}
    try:
        cls4_models_2h = {}
        for horizon in HORIZONS:
            p = MODEL_DIR / f"rainfall_cls_{horizon}h.joblib"
            if p.exists():
                obj = joblib.load(p)
                cls4_models_2h[horizon] = obj["model"]

        nea_2h = load_nea_forecasts_2h(all_years)
        station_rain_2h = load_station_rainfall_2h(all_years)

        if not nea_2h.empty and not station_rain_2h.empty:
            nea_2h_benchmark = compute_nea_2h_area_benchmark(
                nea_2h, station_rain_2h, feat_df,
                cls4_models_2h, cls3_models, feature_cols, TEST_YEAR
            )
            logger.info("  NEA 2h area benchmark complete")
        else:
            logger.warning("  NEA 2h area benchmark skipped: insufficient data")
    except Exception as e:
        logger.warning(f"  NEA 2h area benchmark failed: {e}")
        import traceback; traceback.print_exc()
        nea_2h_benchmark = {"error": str(e)}

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
        "three_class_results": three_class_results,
        "nea_benchmark": nea_benchmark,
        "nea_2h_benchmark": nea_2h_benchmark,
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
