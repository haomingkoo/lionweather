"""Singapore air quality (haze): NEA 24-hr PSI and 1-hr PM2.5 by region.

Source: NEA real-time data on data.gov.sg
  https://api-open.data.gov.sg/v2/real-time/api/psi
  https://api-open.data.gov.sg/v2/real-time/api/pm25
Bands and advisories: https://www.haze.gov.sg/ and
  https://www.nea.gov.sg/our-services/pollution-control/air-pollution/faqs
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from app.db.database import execute_sql, fetch_all, fetch_one, get_database_url

logger = logging.getLogger(__name__)

SGT = timezone(timedelta(hours=8))
BASE_URL = "https://api-open.data.gov.sg/v2/real-time/api"
PSI_PATH = "/psi"
PM25_PATH = "/pm25"
REGIONS = ("north", "south", "east", "west", "central")
SOURCE = "NEA via data.gov.sg"
LINKS = {
    "haze": "https://www.haze.gov.sg/",
    "nea": "https://www.nea.gov.sg/our-services/pollution-control/air-pollution/faqs",
}
TIMEOUT_SECONDS = 10.0
RATE_LIMIT_WAIT_SECONDS = 10
# Longer than the 15-minute background loop, so page views rarely hit upstream.
CACHE_TTL = timedelta(minutes=20)
RETRY_AFTER_FAILURE = timedelta(minutes=1)
# NEA publishes hourly; a reading older than this is labelled stale.
STALE_AFTER = timedelta(hours=2)
MAX_HISTORY_HOURS = 168

# 24-hr PSI descriptors and healthy-person advisory (NEA air pollution FAQ).
PSI_BANDS = (
    (50, "good", "Good", "Normal activities"),
    (100, "moderate", "Moderate", "Normal activities"),
    (200, "unhealthy", "Unhealthy", "Reduce prolonged or strenuous outdoor physical exertion"),
    (300, "very_unhealthy", "Very unhealthy", "Avoid prolonged or strenuous outdoor physical exertion"),
    (None, "hazardous", "Hazardous", "Minimise outdoor activity"),
)

# 1-hr PM2.5 bands in µg/m³ and healthy-person guide (haze.gov.sg).
PM25_BANDS = (
    (55, "normal", "Normal", "Continue with normal activities"),
    (150, "elevated", "Elevated", "Reduce strenuous outdoor activities for the next hour"),
    (250, "high", "High", "Avoid strenuous outdoor activities for the next hour"),
    (None, "very_high", "Very high", "Minimise all outdoor activities for the next hour"),
)


def _band(value: float | None, bands: tuple) -> dict | None:
    if value is None:
        return None
    for upper, key, label, advice in bands:
        if upper is None or value <= upper:
            return {"key": key, "label": label, "advice": advice}
    return None


def psi_band(value: float | None) -> dict | None:
    return _band(value, PSI_BANDS)


def pm25_band(value: float | None) -> dict | None:
    return _band(value, PM25_BANDS)


class AirQualityError(Exception):
    """data.gov.sg returned an error or an unusable payload."""


def _to_utc_iso(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(timezone.utc).isoformat()


def _to_sgt_iso(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(SGT).isoformat()


def parse_series(payload: dict, reading_key: str) -> dict[str, dict[str, float]]:
    """Map timestamp (UTC ISO) -> {region: value} for one reading type."""
    if not isinstance(payload, dict) or payload.get("code") != 0:
        msg = payload.get("errorMsg") if isinstance(payload, dict) else None
        raise AirQualityError(f"data.gov.sg error: {msg or 'unexpected payload'}")
    items = (payload.get("data") or {}).get("items") or []
    series: dict[str, dict[str, float]] = {}
    for item in items:
        values = (item.get("readings") or {}).get(reading_key) or {}
        regional = {r: values[r] for r in REGIONS if isinstance(values.get(r), (int, float))}
        if item.get("timestamp") and regional:
            series[_to_utc_iso(item["timestamp"])] = regional
    if not series:
        raise AirQualityError(f"no {reading_key} readings in payload")
    return series


def parse_region_locations(payload: dict) -> dict[str, dict[str, float]]:
    meta = (payload.get("data") or {}).get("regionMetadata") or []
    return {
        m["name"]: {"lat": m["labelLocation"]["latitude"], "lng": m["labelLocation"]["longitude"]}
        for m in meta
        if m.get("name") in REGIONS and m.get("labelLocation")
    }


# Fallback label points (same values data.gov.sg publishes in regionMetadata).
DEFAULT_REGION_LOCATIONS = {
    "north": {"lat": 1.41803, "lng": 103.82},
    "south": {"lat": 1.29587, "lng": 103.82},
    "east": {"lat": 1.35735, "lng": 103.94},
    "west": {"lat": 1.35735, "lng": 103.7},
    "central": {"lat": 1.35735, "lng": 103.82},
}


# --- storage ---------------------------------------------------------------

def init_air_quality_table() -> None:
    id_column = (
        "id SERIAL PRIMARY KEY"
        if get_database_url().startswith("postgresql")
        else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    execute_sql(f"""
        CREATE TABLE IF NOT EXISTS air_quality_readings (
            {id_column},
            timestamp TEXT NOT NULL,
            region TEXT NOT NULL,
            psi_24h REAL,
            pm25_1h REAL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            UNIQUE(timestamp, region)
        )
    """)
    execute_sql(
        "CREATE INDEX IF NOT EXISTS idx_air_quality_timestamp ON air_quality_readings(timestamp)"
    )


def store_readings(psi: dict, pm25: dict, fetched_at: str) -> int:
    rows = [
        {
            "ts": ts,
            "region": region,
            "psi": psi.get(ts, {}).get(region),
            "pm25": pm25.get(ts, {}).get(region),
            "source": SOURCE,
            "fetched_at": fetched_at,
        }
        for ts in set(psi) | set(pm25)
        for region in REGIONS
    ]
    rows = [r for r in rows if r["psi"] is not None or r["pm25"] is not None]
    if not rows:
        return 0
    # ON CONFLICT ... DO UPDATE works on both Postgres and SQLite >= 3.24.
    execute_sql(
        """
        INSERT INTO air_quality_readings (timestamp, region, psi_24h, pm25_1h, source, fetched_at)
        VALUES (:ts, :region, :psi, :pm25, :source, :fetched_at)
        ON CONFLICT (timestamp, region) DO UPDATE SET
            psi_24h = COALESCE(EXCLUDED.psi_24h, air_quality_readings.psi_24h),
            pm25_1h = COALESCE(EXCLUDED.pm25_1h, air_quality_readings.pm25_1h),
            fetched_at = EXCLUDED.fetched_at
        """,
        rows,
    )
    return len(rows)


def last_stored_timestamp() -> str | None:
    row = fetch_one(
        "SELECT MAX(timestamp) AS ts FROM air_quality_readings WHERE psi_24h IS NOT NULL"
    )
    return row._mapping["ts"] if row and row._mapping["ts"] else None


def load_history(hours: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = fetch_all(
        """
        SELECT timestamp, region, psi_24h, pm25_1h FROM air_quality_readings
        WHERE timestamp >= :cutoff ORDER BY timestamp
        """,
        {"cutoff": cutoff},
    )
    by_ts: dict[str, dict] = {}
    for row in rows:
        m = row._mapping
        point = by_ts.setdefault(m["timestamp"], {"timestamp": _to_sgt_iso(m["timestamp"]), "regions": {}})
        point["regions"][m["region"]] = {"psi_24h": m["psi_24h"], "pm25_1h": m["pm25_1h"]}
    return list(by_ts.values())


# --- fetch + cache ---------------------------------------------------------

def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "lionweather/1.0"}
    api_key = os.getenv("WEATHER_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


async def fetch_payload(client: httpx.AsyncClient, path: str, date: str | None = None) -> dict:
    params = {"date": date} if date else None
    try:
        response = await client.get(f"{BASE_URL}{path}", params=params)
        if response.status_code == 429:
            # data.gov.sg asks unauthenticated callers to retry after ~10 s.
            await asyncio.sleep(RATE_LIMIT_WAIT_SECONDS)
            response = await client.get(f"{BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise AirQualityError(f"{path} returned HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise AirQualityError(f"{path} request failed: {exc.__class__.__name__}") from exc


@dataclass
class Snapshot:
    psi: dict = field(default_factory=dict)
    pm25: dict = field(default_factory=dict)
    regions: dict = field(default_factory=lambda: dict(DEFAULT_REGION_LOCATIONS))
    fetched_at: datetime | None = None


class AirQualityService:
    def __init__(self) -> None:
        self.snapshot: Snapshot | None = None
        self.last_attempt_at: datetime | None = None
        self.last_error: str | None = None
        self._lock = asyncio.Lock()

    def _cache_fresh(self, now: datetime) -> bool:
        if self.last_attempt_at is None:
            return False
        ttl = CACHE_TTL if self.snapshot is not None else RETRY_AFTER_FAILURE
        return now - self.last_attempt_at < ttl

    async def refresh(self, force: bool = False) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if not force and self._cache_fresh(now):
                return
            self.last_attempt_at = now
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=_headers()) as client:
                    psi_raw = await fetch_payload(client, PSI_PATH)
                    pm25_raw = await fetch_payload(client, PM25_PATH)
                psi = parse_series(psi_raw, "psi_twenty_four_hourly")
                pm25 = parse_series(pm25_raw, "pm25_one_hourly")
            except AirQualityError as exc:
                self.last_error = str(exc)
                self.snapshot = None
                logger.warning(f"Air quality refresh failed: {exc}")
                return
            self.snapshot = Snapshot(
                psi=psi,
                pm25=pm25,
                regions=parse_region_locations(psi_raw) or dict(DEFAULT_REGION_LOCATIONS),
                fetched_at=now,
            )
            self.last_error = None
            try:
                await asyncio.to_thread(store_readings, psi, pm25, now.isoformat())
            except Exception as exc:  # storage must not hide fresh readings
                logger.error(f"Air quality store failed: {exc}")

    async def backfill(self, days: int = 2) -> int:
        """Store full days of hourly readings so the sparkline has history at boot."""
        today = datetime.now(SGT).date()
        stored = 0
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=_headers()) as client:
            for offset in range(days):
                date = (today - timedelta(days=offset)).isoformat()
                try:
                    psi = parse_series(await fetch_payload(client, PSI_PATH, date), "psi_twenty_four_hourly")
                    pm25 = parse_series(await fetch_payload(client, PM25_PATH, date), "pm25_one_hourly")
                except AirQualityError as exc:
                    logger.warning(f"Air quality backfill {date} failed: {exc}")
                    continue
                stored += await asyncio.to_thread(
                    store_readings, psi, pm25, datetime.now(timezone.utc).isoformat()
                )
        return stored

    def latest(self) -> dict:
        base = {"source": SOURCE, "links": LINKS}
        snap = self.snapshot
        if snap is None:
            try:
                last_good = last_stored_timestamp()
            except Exception as exc:
                logger.error(f"Air quality last-good lookup failed: {exc}")
                last_good = None
            return {
                **base,
                "status": "unavailable",
                "error": self.last_error or "No reading fetched yet",
                "last_good_observed_at": _to_sgt_iso(last_good) if last_good else None,
                "observed_at": None,
                "regions": [],
                "national": None,
            }
        return {**base, **build_latest(snap, datetime.now(timezone.utc))}


def build_latest(snap: Snapshot, now: datetime) -> dict:
    psi_ts = max(snap.psi)
    pm25_ts = max(snap.pm25)
    psi_now, pm25_now = snap.psi[psi_ts], snap.pm25[pm25_ts]
    observed = min(datetime.fromisoformat(psi_ts), datetime.fromisoformat(pm25_ts))
    regions = [
        {
            "region": r,
            **snap.regions.get(r, DEFAULT_REGION_LOCATIONS[r]),
            "psi_24h": psi_now.get(r),
            "psi_band": psi_band(psi_now.get(r)),
            "pm25_1h": pm25_now.get(r),
            "pm25_band": pm25_band(pm25_now.get(r)),
        }
        for r in REGIONS
    ]
    psi_values = list(psi_now.values())
    pm25_values = list(pm25_now.values())
    psi_max, pm25_max = max(psi_values), max(pm25_values)
    return {
        "status": "stale" if now - observed > STALE_AFTER else "ok",
        "error": None,
        "observed_at": observed.astimezone(SGT).isoformat(),
        "psi_observed_at": _to_sgt_iso(psi_ts),
        "pm25_observed_at": _to_sgt_iso(pm25_ts),
        "fetched_at": snap.fetched_at.astimezone(SGT).isoformat() if snap.fetched_at else None,
        "last_good_observed_at": observed.astimezone(SGT).isoformat(),
        "regions": regions,
        # NEA reports a national 24-hr PSI as the range across regions.
        "national": {
            "psi_24h_min": min(psi_values),
            "psi_24h_max": psi_max,
            "psi_band": psi_band(psi_max),
            "pm25_1h_max": pm25_max,
            "pm25_band": pm25_band(pm25_max),
        },
    }


_service: AirQualityService | None = None


def get_air_quality_service() -> AirQualityService:
    global _service
    if _service is None:
        _service = AirQualityService()
    return _service
