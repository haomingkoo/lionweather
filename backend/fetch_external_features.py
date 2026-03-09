"""
Fetch external weather features for ML training enhancement.

Downloads and caches:
  1. Open-Meteo historical archive — CAPE, lifted index, CIN, precipitable water,
     850hPa / 200hPa wind speeds (ERA5-backed, hourly, 2016-2024)
  2. BOM MJO RMM indices — daily phase + amplitude (1974-present) → interpolated hourly

Outputs (saved to models/cache/):
  openmeteo_convective.parquet   (hourly, Asia/Singapore timezone)
  mjo_hourly.parquet             (hourly, Asia/Singapore timezone)

Usage:
  cd backend
  python fetch_external_features.py
"""

import time
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CACHE_DIR = Path("models/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Singapore coordinates
SG_LAT = 1.3521
SG_LON = 103.8198

YEARS = list(range(2016, 2025))


# ── 1. Open-Meteo convective variables ───────────────────────────────────────

OM_HOURLY_VARS = [
    "cape",                      # Convective Available Potential Energy (J/kg)
    "lifted_index",              # Lifted Index (negative = unstable)
    "convective_inhibition",     # CIN (J/kg)
    "wind_speed_850hPa",         # Low-level wind speed (km/h)
    "wind_speed_200hPa",         # Upper-level jet stream (km/h)
    "wind_direction_850hPa",     # Low-level wind direction (degrees)
    "temperature_850hPa",        # Low-level temperature (°C)
    "relative_humidity_850hPa",  # Low-level humidity (%) — proxy for column moisture
]


def fetch_openmeteo_year(year: int) -> pd.DataFrame | None:
    """Fetch one year of hourly convective data from Open-Meteo archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": SG_LAT,
        "longitude": SG_LON,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(OM_HOURLY_VARS),
        "timezone": "Asia/Singapore",
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error(f"  Open-Meteo fetch failed for {year}: {e}")
        return None

    hourly = data.get("hourly", {})
    if not hourly or "time" not in hourly:
        log.error(f"  No hourly data returned for {year}")
        return None

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df.index = df.index.tz_localize("Asia/Singapore")
    log.info(f"  {year}: {len(df)} rows, vars={list(df.columns)}")
    return df


def fetch_openmeteo_convective() -> pd.DataFrame:
    """Fetch all years and combine into one DataFrame."""
    out_path = CACHE_DIR / "openmeteo_convective.parquet"
    if out_path.exists():
        log.info(f"Open-Meteo convective cache exists: {out_path}")
        df = pd.read_parquet(out_path)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("Asia/Singapore")
        else:
            df.index = df.index.tz_convert("Asia/Singapore")
        log.info(f"  Loaded: {len(df)} rows  {df.index.min()} → {df.index.max()}")
        return df

    log.info("Fetching Open-Meteo convective features (2016-2024)…")
    frames = []
    for year in YEARS:
        log.info(f"  Fetching {year}…")
        df_year = fetch_openmeteo_year(year)
        if df_year is not None:
            frames.append(df_year)
        time.sleep(1.0)  # be polite to the API

    if not frames:
        log.error("No Open-Meteo data fetched")
        return pd.DataFrame()

    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.to_parquet(out_path)
    log.info(f"Saved Open-Meteo convective → {out_path}  ({len(df)} rows)")
    return df


# ── 2. BOM MJO RMM indices ───────────────────────────────────────────────────

BOM_MJO_URL = "http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt"


def fetch_mjo() -> pd.DataFrame:
    """
    Download BOM MJO RMM indices, parse, interpolate daily → hourly.
    Saves mjo_hourly.parquet.

    MJO phase 1-8 (cyclically encoded):
      - Phases 3-5: suppressed convection over Maritime Continent/Singapore
      - Phases 6-8: enhanced convection over Singapore
    """
    out_path = CACHE_DIR / "mjo_hourly.parquet"
    if out_path.exists():
        log.info(f"MJO cache exists: {out_path}")
        df = pd.read_parquet(out_path)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("Asia/Singapore")
        else:
            df.index = df.index.tz_convert("Asia/Singapore")
        log.info(f"  Loaded: {len(df)} rows  {df.index.min()} → {df.index.max()}")
        return df

    log.info(f"Fetching MJO RMM data from BOM…")
    try:
        resp = requests.get(BOM_MJO_URL, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0 LionWeather/1.0"})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        log.error(f"BOM MJO fetch failed: {e}")
        return pd.DataFrame()

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("year") or line.startswith("Day") or line.startswith("Missing"):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            rmm1, rmm2 = float(parts[3]), float(parts[4])
            phase, amplitude = int(parts[5]), float(parts[6])
            rows.append({
                "date": pd.Timestamp(year=year, month=month, day=day),
                "mjo_rmm1": rmm1,
                "mjo_rmm2": rmm2,
                "mjo_phase": phase,
                "mjo_amplitude": amplitude,
            })
        except (ValueError, IndexError):
            continue

    if not rows:
        log.error("Failed to parse MJO data")
        return pd.DataFrame()

    daily = pd.DataFrame(rows).set_index("date")
    # Mark missing/unreliable days (amplitude = 999 or phase = 0)
    bad = (daily["mjo_amplitude"] > 100) | (daily["mjo_phase"] == 0)
    daily.loc[bad, ["mjo_rmm1", "mjo_rmm2", "mjo_amplitude"]] = np.nan
    daily.loc[bad, "mjo_phase"] = np.nan

    log.info(f"  MJO daily: {len(daily)} rows  {daily.index.min()} → {daily.index.max()}")

    # Cyclical encoding of phase (1-8)
    daily["mjo_sin_phase"] = np.sin(2 * np.pi * (daily["mjo_phase"] - 1) / 8)
    daily["mjo_cos_phase"] = np.cos(2 * np.pi * (daily["mjo_phase"] - 1) / 8)

    # Interpolate daily → hourly (linear for continuous vars, forward-fill for phase)
    hourly_idx = pd.date_range(
        start=daily.index.min(),
        end=daily.index.max() + pd.Timedelta(hours=23),
        freq="1h",
    )
    daily_h = daily.reindex(hourly_idx).interpolate(method="linear").ffill().bfill()
    daily_h.index = daily_h.index.tz_localize("Asia/Singapore")

    daily_h.to_parquet(out_path)
    log.info(f"Saved MJO hourly → {out_path}  ({len(daily_h)} rows)")
    return daily_h


# ── 3. Load and merge everything ─────────────────────────────────────────────

def load_all_external_features(start: str = "2016-01-01",
                                end: str = "2024-12-31") -> pd.DataFrame:
    """
    Load (and fetch if missing) all external features, merged on hourly timestamps.

    Returns DataFrame with columns:
      cape, lifted_index, convective_inhibition, precipitable_water,
      wind_speed_850hPa, wind_speed_200hPa, wind_direction_850hPa,
      temperature_850hPa, relative_humidity_850hPa,
      wind_shear_850_200,
      mjo_amplitude, mjo_sin_phase, mjo_cos_phase, mjo_rmm1, mjo_rmm2
    """
    om = fetch_openmeteo_convective()
    mjo = fetch_mjo()

    frames = []

    if not om.empty:
        # Compute wind shear (850hPa - 200hPa): proxy for convective organisation
        if "wind_speed_850hPa" in om.columns and "wind_speed_200hPa" in om.columns:
            om["wind_shear_850_200"] = om["wind_speed_850hPa"] - om["wind_speed_200hPa"]
        frames.append(om)

    if not mjo.empty:
        mjo_cols = ["mjo_amplitude", "mjo_sin_phase", "mjo_cos_phase", "mjo_rmm1", "mjo_rmm2"]
        frames.append(mjo[[c for c in mjo_cols if c in mjo.columns]])

    if not frames:
        return pd.DataFrame()

    # Align to common hourly index
    merged = frames[0]
    for f in frames[1:]:
        merged = merged.join(f, how="outer")

    # Filter to requested range
    start_ts = pd.Timestamp(start, tz="Asia/Singapore")
    end_ts   = pd.Timestamp(end,   tz="Asia/Singapore") + pd.Timedelta(hours=23)
    merged = merged[(merged.index >= start_ts) & (merged.index <= end_ts)]
    merged = merged.resample("1h").mean().ffill().bfill()

    log.info(f"External features: {len(merged)} hourly rows, {len(merged.columns)} columns")
    log.info(f"  Columns: {list(merged.columns)}")
    return merged


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=== Fetching external ML features ===")
    df = load_all_external_features()
    if df.empty:
        log.error("No data fetched — check network / API availability")
        sys.exit(1)

    log.info("\nSample (first 3 rows):")
    log.info(df.head(3).to_string())
    log.info(f"\nNull counts:\n{df.isnull().sum()}")
    log.info("\nDone.")
