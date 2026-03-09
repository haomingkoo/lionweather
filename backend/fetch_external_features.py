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


# ── 1. Open-Meteo archive variables (ERA5-backed, available for Singapore 2016-2024) ──
# Note: pressure-level vars (cape, 850hPa) return None for Singapore in the archive API.
# Use available surface/radiation proxies instead:
#   cloud_cover        → convective cloud fraction (direct instability signal)
#   shortwave_radiation→ daytime solar heating drives Sumatra-style convection
#   wind_direction_10m → surface wind direction identifies Sumatra squall westerly flow
#   surface_pressure   → mesoscale pressure falls precede squall lines

OM_HOURLY_VARS = [
    "cloud_cover",           # Total cloud cover (%)
    "shortwave_radiation",   # Solar radiation W/m² — daytime heating proxy
    "wind_direction_10m",    # Surface wind direction (°) — Sumatra squall indicator
    "surface_pressure",      # Sea-level pressure (hPa)
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


# ── 2. ERA5 convective variables via Copernicus CDS ──────────────────────────
# Requires ~/.cdsapirc with url + key from https://cds.climate.copernicus.eu/api-how-to
# The user must accept Terms of Use for each ERA5 dataset on the CDS website.

ERA5_SINGLE_VARS = [
    "convective_available_potential_energy",  # CAPE (J/kg)
    "convective_inhibition",                  # CIN (J/kg)
    "k_index",                                # K-index (°C) — thunderstorm potential
    "total_column_water_vapour",              # Precipitable water (kg/m²)
    "surface_pressure",                       # Surface pressure (Pa → hPa)
]

ERA5_PRESSURE_VARS = [
    "u_component_of_wind",    # Zonal wind at 850hPa and 200hPa (m/s)
    "v_component_of_wind",    # Meridional wind
    "temperature",            # Temperature at 850hPa (K)
    "relative_humidity",      # RH at 850hPa (%)
]


def fetch_era5_year(year: int, out_dir: Path) -> bool:
    """Download one year of ERA5 hourly data for Singapore. Returns True if successful."""
    try:
        import cdsapi
        import xarray as xr
    except ImportError:
        log.warning("cdsapi or xarray not installed — skipping ERA5 fetch")
        return False

    sl_path = out_dir / f"era5_sl_{year}.nc"
    pl_path = out_dir / f"era5_pl_{year}.nc"

    months = [f"{m:02d}" for m in range(1, 13)]
    days   = [f"{d:02d}" for d in range(1, 32)]
    times  = [f"{h:02d}:00" for h in range(24)]

    c = cdsapi.Client(quiet=True)

    # Single-level (CAPE, CIN, K-index, TPW, surface pressure)
    if not sl_path.exists():
        log.info(f"  ERA5 single-level {year}: requesting from CDS (may take a few minutes)…")
        try:
            c.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": "reanalysis",
                    "variable": ERA5_SINGLE_VARS,
                    "year": str(year),
                    "month": months,
                    "day": days,
                    "time": times,
                    "area": [2.0, 103.5, 1.0, 104.5],  # Singapore bounding box (N, W, S, E)
                    "format": "netcdf",
                },
                str(sl_path),
            )
            log.info(f"  ERA5 SL {year}: downloaded → {sl_path}")
        except Exception as e:
            log.error(f"  ERA5 SL {year} failed: {e}")
            return False
    else:
        log.info(f"  ERA5 SL {year}: cache exists")

    # Pressure-levels (850hPa + 200hPa winds/temp/humidity)
    if not pl_path.exists():
        log.info(f"  ERA5 pressure-levels {year}: requesting from CDS…")
        try:
            c.retrieve(
                "reanalysis-era5-pressure-levels",
                {
                    "product_type": "reanalysis",
                    "variable": ERA5_PRESSURE_VARS,
                    "pressure_level": ["200", "850"],
                    "year": str(year),
                    "month": months,
                    "day": days,
                    "time": times,
                    "area": [2.0, 103.5, 1.0, 104.5],
                    "format": "netcdf",
                },
                str(pl_path),
            )
            log.info(f"  ERA5 PL {year}: downloaded → {pl_path}")
        except Exception as e:
            log.error(f"  ERA5 PL {year} failed: {e}")
            return False
    else:
        log.info(f"  ERA5 PL {year}: cache exists")

    return True


def _process_era5_year(year: int, out_dir: Path) -> pd.DataFrame | None:
    """Load downloaded ERA5 NetCDF files for one year into a DataFrame."""
    try:
        import xarray as xr
    except ImportError:
        return None

    sl_path = out_dir / f"era5_sl_{year}.nc"
    pl_path = out_dir / f"era5_pl_{year}.nc"

    if not sl_path.exists() or not pl_path.exists():
        return None

    SGT = "Asia/Singapore"

    # Single-level: average over the bounding box (small area, values are nearly identical)
    ds_sl = xr.open_dataset(sl_path)
    sl_mean = ds_sl.mean(dim=["latitude", "longitude"])
    df_sl = sl_mean.to_dataframe().reset_index()

    # Rename and convert
    rename_sl = {
        "cape": "cape",
        "cin":  "cin",
        "kx":   "k_index",
        "tcwv": "total_column_water_vapour",
        "sp":   "surface_pressure_pa",
    }
    # ERA5 variable short names vary — find what we actually got
    actual_rename = {}
    for col in df_sl.columns:
        if col in rename_sl:
            actual_rename[col] = rename_sl[col]
    df_sl = df_sl.rename(columns=actual_rename)
    if "surface_pressure_pa" in df_sl.columns:
        df_sl["surface_pressure"] = df_sl["surface_pressure_pa"] / 100.0  # Pa → hPa

    df_sl["time"] = pd.to_datetime(df_sl["valid_time"] if "valid_time" in df_sl.columns else df_sl["time"])
    df_sl = df_sl.set_index("time")
    if df_sl.index.tz is None:
        df_sl.index = df_sl.index.tz_localize("UTC").tz_convert(SGT)

    # Pressure-level: separate 850hPa and 200hPa
    ds_pl = xr.open_dataset(pl_path)
    pl_mean = ds_pl.mean(dim=["latitude", "longitude"])

    rows = []
    for t in pl_mean.time.values:
        row = {"time": t}
        for lev in [850, 200]:
            sel = pl_mean.sel(pressure_level=lev) if "pressure_level" in pl_mean.dims else pl_mean.sel(level=lev)
            for var in pl_mean.data_vars:
                try:
                    row[f"{var}_{lev}"] = float(sel[var].sel(time=t, method="nearest"))
                except Exception:
                    pass
        rows.append(row)
    df_pl = pd.DataFrame(rows).set_index("time")
    df_pl.index = pd.to_datetime(df_pl.index)
    if df_pl.index.tz is None:
        df_pl.index = df_pl.index.tz_localize("UTC").tz_convert(SGT)

    # Compute derived: wind speed and shear
    for lev in [850, 200]:
        u_col = f"u_{lev}" if f"u_{lev}" in df_pl.columns else None
        v_col = f"v_{lev}" if f"v_{lev}" in df_pl.columns else None
        # Try alternate naming (ERA5 short names)
        for candidate_u in [f"u_{lev}", f"u_component_of_wind_{lev}", f"u{lev}"]:
            if candidate_u in df_pl.columns:
                u_col = candidate_u
                break
        for candidate_v in [f"v_{lev}", f"v_component_of_wind_{lev}", f"v{lev}"]:
            if candidate_v in df_pl.columns:
                v_col = candidate_v
                break
        if u_col and v_col:
            df_pl[f"wind_speed_{lev}hPa"] = np.sqrt(df_pl[u_col]**2 + df_pl[v_col]**2) * 3.6  # m/s → km/h

    if "wind_speed_850hPa" in df_pl.columns and "wind_speed_200hPa" in df_pl.columns:
        df_pl["wind_shear_850_200"] = df_pl["wind_speed_850hPa"] - df_pl["wind_speed_200hPa"]

    # Merge
    df = df_sl.join(df_pl, how="outer")

    # Clean up
    keep = ["cape", "cin", "k_index", "total_column_water_vapour",
            "wind_speed_850hPa", "wind_speed_200hPa", "wind_shear_850_200"]
    # Add temperature_850hPa if present
    for col in list(df_pl.columns):
        if "temperature_850" in col.lower() or "t_850" in col.lower():
            df[f"temperature_850hPa"] = df_pl[col] - 273.15  # K → °C
            keep.append("temperature_850hPa")
            break

    df = df[[c for c in keep if c in df.columns]]
    ds_sl.close()
    ds_pl.close()
    return df


def fetch_era5_convective() -> pd.DataFrame:
    """Download and process ERA5 CAPE/wind data for 2016-2024. Returns hourly DataFrame."""
    out_path = CACHE_DIR / "era5_convective.parquet"
    nc_dir   = CACHE_DIR / "era5_nc"
    nc_dir.mkdir(exist_ok=True)

    if out_path.exists():
        log.info(f"ERA5 convective cache exists: {out_path}")
        df = pd.read_parquet(out_path)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("Asia/Singapore")
        else:
            df.index = df.index.tz_convert("Asia/Singapore")
        log.info(f"  Loaded ERA5: {len(df)} rows  {df.index.min()} → {df.index.max()}")
        return df

    log.info("Fetching ERA5 convective features (2016-2024) via CDS API …")
    frames = []
    for year in YEARS:
        log.info(f"  Year {year}…")
        ok = fetch_era5_year(year, nc_dir)
        if ok:
            df_yr = _process_era5_year(year, nc_dir)
            if df_yr is not None and not df_yr.empty:
                frames.append(df_yr)
                log.info(f"  {year}: {len(df_yr)} rows, cols={list(df_yr.columns)}")
        time.sleep(1.0)

    if not frames:
        log.warning("No ERA5 data fetched — proceeding without pressure-level features")
        return pd.DataFrame()

    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.to_parquet(out_path)
    log.info(f"Saved ERA5 convective → {out_path}  ({len(df)} rows)")
    return df


# ── 3. BOM MJO RMM indices ───────────────────────────────────────────────────

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
      cloud_cover, shortwave_radiation, wind_direction_10m, surface_pressure,
      mjo_amplitude, mjo_sin_phase, mjo_cos_phase, mjo_rmm1, mjo_rmm2
    """
    om = fetch_openmeteo_convective()
    mjo = fetch_mjo()

    frames = []

    if not om.empty:
        # Add cyclical encoding of wind direction (0-360°)
        if "wind_direction_10m" in om.columns:
            om["wind_dir_sin"] = np.sin(np.deg2rad(om["wind_direction_10m"]))
            om["wind_dir_cos"] = np.cos(np.deg2rad(om["wind_direction_10m"]))
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
