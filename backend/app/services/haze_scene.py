"""Hourly haze scene for the /haze page: PSI, PM2.5, wind and fire hotspots.

PSI and PM2.5 come from the air quality store (NEA via data.gov.sg), backfilled by day.
Wind comes from the NEA station readings the data collector already stores every
10 minutes. Fire hotspots come from NASA FIRMS and need a free FIRMS_MAP_KEY.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import os
from datetime import datetime, timedelta, timezone

import httpx

from app.db.database import fetch_all
from app.services import air_quality as aq

logger = logging.getLogger(__name__)

SGT = aq.SGT
ALLOWED_HOURS = (24, 48, 72)
CACHE_TTL = timedelta(minutes=10)
HOTSPOT_TTL = timedelta(hours=1)
# Back-trajectory length; surface wind of ~3 knots covers ~270 km in 48 h.
TRAJECTORY_HOURS = 48
SINGAPORE = (1.3521, 103.8198)
KM_PER_DEG = 111.32
KNOT_KMH = 1.852

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"
FIRMS_SOURCE = "VIIRS_SNPP_NRT"
# West, south, east, north: Sumatra, Peninsular Malaysia and Borneo.
FIRMS_BBOX = (95.0, -6.0, 119.5, 7.5)
FIRMS_SIGNUP = "https://firms.modaps.eosdis.nasa.gov/api/map_key/"
MAX_HOTSPOTS = 4000

SOURCES = {
    "air": {"name": "NEA via data.gov.sg", "url": "https://data.gov.sg/datasets/d_fe37906a0182569d891506e815e819b7/view"},
    "wind": {"name": "NEA weather stations via data.gov.sg", "url": "https://data.gov.sg/datasets/d_7677738484067741bf3b56ab5d69c7e9/view"},
    "fires": {"name": "NASA FIRMS (VIIRS S-NPP, near real time)", "url": "https://firms.modaps.eosdis.nasa.gov/"},
}


def hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def parse_ts(value) -> datetime | None:
    """Stored timestamps are ISO text, with or without offset; naive means SGT."""
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.replace(tzinfo=SGT) if dt.tzinfo is None else dt


def hour_grid(end: datetime, hours: int) -> list[datetime]:
    end = hour_floor(end)
    return [end - timedelta(hours=hours - 1 - i) for i in range(hours)]


# --- air quality -----------------------------------------------------------

def align_air(points: list[dict], grid: list[datetime]) -> dict:
    """Stored history points -> {psi|pm25: {region: [value or None per grid hour]}}."""
    index = {t: i for i, t in enumerate(grid)}
    psi = {r: [None] * len(grid) for r in aq.REGIONS}
    pm25 = {r: [None] * len(grid) for r in aq.REGIONS}
    for p in points:
        ts = parse_ts(p["timestamp"])
        i = index.get(hour_floor(ts)) if ts else None
        if i is None:
            continue
        for region, values in p["regions"].items():
            if region in psi:
                psi[region][i] = values.get("psi_24h")
                pm25[region][i] = values.get("pm25_1h")
    return {"psi": psi, "pm25": pm25}


def missing_air_dates(air: dict, grid: list[datetime]) -> list[str]:
    """SGT dates with any grid hour lacking PSI, newest first."""
    dates = set()
    for i, t in enumerate(grid):
        if all(air["psi"][r][i] is None for r in aq.REGIONS):
            dates.add(t.astimezone(SGT).date().isoformat())
    return sorted(dates, reverse=True)


async def backfill_air(dates: list[str]) -> int:
    stored = 0
    async with httpx.AsyncClient(timeout=aq.TIMEOUT_SECONDS, headers=aq._headers()) as client:
        for date in dates:
            try:
                psi = aq.parse_series(await aq.fetch_payload(client, aq.PSI_PATH, date), "psi_twenty_four_hourly")
                pm25 = aq.parse_series(await aq.fetch_payload(client, aq.PM25_PATH, date), "pm25_one_hourly")
            except aq.AirQualityError as exc:
                logger.warning(f"Haze scene backfill {date} failed: {exc}")
                continue
            stored += await asyncio.to_thread(
                aq.store_readings, psi, pm25, datetime.now(timezone.utc).isoformat()
            )
    return stored


# --- wind ------------------------------------------------------------------

def load_wind_rows(since: datetime) -> list[dict]:
    # Text timestamps: compare on the SGT date prefix, then filter precisely in Python.
    day = (since.astimezone(SGT) - timedelta(days=1)).date().isoformat()
    rows = fetch_all(
        """
        SELECT timestamp, location, latitude, longitude, wind_speed, wind_direction
        FROM weather_records
        WHERE country = 'singapore' AND source_api = 'api-open.data.gov.sg'
          AND timestamp >= :day
        """,
        {"day": day},
    )
    return [dict(r._mapping) for r in rows]


def to_uv(speed: float, direction: float) -> tuple[float, float]:
    """Meteorological 'from' direction -> eastward/northward components (same units)."""
    rad = math.radians(direction)
    return -speed * math.sin(rad), -speed * math.cos(rad)


def from_uv(u: float, v: float) -> tuple[float, float]:
    speed = math.hypot(u, v)
    direction = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    return speed, direction


def aggregate_wind(rows: list[dict], grid: list[datetime]) -> dict:
    """Vector-average station readings into hourly per-station and national means (knots)."""
    index = {t: i for i, t in enumerate(grid)}
    stations: dict[str, dict] = {}
    sums: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        ts = parse_ts(row["timestamp"])
        speed, direction = row.get("wind_speed"), row.get("wind_direction")
        if ts is None or speed is None or direction is None or speed < 0:
            continue
        i = index.get(hour_floor(ts))
        if i is None:
            continue
        name = row["location"]
        stations.setdefault(name, {"name": name, "lat": row["latitude"], "lng": row["longitude"]})
        u, v = to_uv(float(speed), float(direction))
        acc = sums.setdefault((name, i), [0.0, 0.0, 0])
        acc[0] += u
        acc[1] += v
        acc[2] += 1

    names = sorted(stations)
    per_station = {n: [None] * len(grid) for n in names}
    mean: list[dict | None] = [None] * len(grid)
    hour_acc = [[0.0, 0.0, 0] for _ in grid]
    for (name, i), (u, v, n) in sums.items():
        su, sv = u / n, v / n
        speed, direction = from_uv(su, sv)
        per_station[name][i] = [round(speed, 2), round(direction)]
        hour_acc[i][0] += su
        hour_acc[i][1] += sv
        hour_acc[i][2] += 1
    for i, (u, v, n) in enumerate(hour_acc):
        if n:
            speed, direction = from_uv(u / n, v / n)
            mean[i] = {"speed_kn": round(speed, 2), "dir_deg": round(direction), "stations": n}
    return {
        "unit": "knots",
        "stations": [stations[n] for n in names],
        "station_hourly": per_station,
        "mean": mean,
    }


def back_trajectory(mean: list[dict | None], end_index: int, hours: int = TRAJECTORY_HOURS) -> list[list[float]]:
    """Walk upwind from Singapore using the hourly national mean wind.

    Returns [lat, lng, hours_before_end] points from Singapore backwards. Hours
    without wind are skipped, so the path is shorter rather than invented.
    """
    lat, lng = SINGAPORE
    path = [[round(lat, 4), round(lng, 4), 0]]
    for step in range(hours):
        i = end_index - step
        if i < 0:
            break
        w = mean[i]
        if not w:
            continue
        u, v = to_uv(w["speed_kn"] * KNOT_KMH, w["dir_deg"])  # km/h towards
        # Going back in time moves against the flow.
        lat -= v / KM_PER_DEG
        lng -= u / (KM_PER_DEG * math.cos(math.radians(lat)))
        path.append([round(lat, 4), round(lng, 4), step + 1])
    return path


# --- fire hotspots -----------------------------------------------------------

def parse_firms_csv(text: str) -> list[dict]:
    if not text.lstrip().lower().startswith("latitude"):
        raise ValueError(text.strip()[:80] or "empty FIRMS response")
    points = []
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("confidence", "").lower() in ("l", "low"):
            continue
        try:
            hhmm = row["acq_time"].zfill(4)
            when = datetime.fromisoformat(f"{row['acq_date']}T{hhmm[:2]}:{hhmm[2:]}:00+00:00")
            points.append({
                "lat": round(float(row["latitude"]), 4),
                "lng": round(float(row["longitude"]), 4),
                "frp": round(float(row.get("frp") or 0), 1),
                "at": when.astimezone(SGT).isoformat(),
            })
        except (KeyError, ValueError):
            continue
    points.sort(key=lambda p: p["frp"], reverse=True)
    return points[:MAX_HOTSPOTS]


def hotspots_unavailable() -> dict:
    return {
        "status": "unavailable",
        "reason": "not_configured",
        "message": "Fire hotspots need a free NASA FIRMS key on the server.",
        "signup": FIRMS_SIGNUP,
        "points": [],
    }


async def fetch_hotspots(key: str, days: int) -> dict:
    url = FIRMS_URL.format(
        key=key, source=FIRMS_SOURCE, bbox=",".join(str(v) for v in FIRMS_BBOX), days=days
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        points = parse_firms_csv(response.text)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(f"FIRMS fetch failed: {exc.__class__.__name__}")
        return {"status": "error", "message": "NASA FIRMS did not answer. Try again later.", "points": []}
    return {"status": "ok", "days": days, "bbox": FIRMS_BBOX, "points": points}


# --- scene -------------------------------------------------------------------

def coverage(series: dict[str, list]) -> int:
    length = len(next(iter(series.values()), []))
    return sum(1 for i in range(length) if any(s[i] is not None for s in series.values()))


def build_scene(grid, air, wind_full, lookback, hotspots, fetched_at) -> dict:
    """Assemble the response; wind_full covers lookback extra hours before the grid."""
    mean_full = wind_full["mean"]
    trajectories = [back_trajectory(mean_full, lookback + i) for i in range(len(grid))]
    station_hourly = {k: v[lookback:] for k, v in wind_full["station_hourly"].items()}
    psi_last = max((i for i in range(len(grid)) if any(air["psi"][r][i] is not None for r in aq.REGIONS)), default=None)
    wind_mean = mean_full[lookback:]
    wind_last = max((i for i, w in enumerate(wind_mean) if w), default=None)
    return {
        "hours": [t.astimezone(SGT).isoformat() for t in grid],
        "regions": aq.DEFAULT_REGION_LOCATIONS,
        "psi": air["psi"],
        "pm25": air["pm25"],
        "wind": {
            "unit": "knots",
            "stations": wind_full["stations"],
            "station_hourly": station_hourly,
            "mean": wind_mean,
        },
        "trajectories": trajectories,
        "trajectory_hours": TRAJECTORY_HOURS,
        "hotspots": hotspots,
        "bands": {
            "psi": [{"max": u, "key": k, "label": label, "advice": a} for u, k, label, a in aq.PSI_BANDS],
            "pm25": [{"max": u, "key": k, "label": label, "advice": a} for u, k, label, a in aq.PM25_BANDS],
        },
        "coverage": {
            "hours": len(grid),
            "air_hours": coverage(air["psi"]),
            "wind_hours": sum(1 for w in wind_mean if w),
        },
        "latest": {
            "air": grid[psi_last].astimezone(SGT).isoformat() if psi_last is not None else None,
            "wind": grid[wind_last].astimezone(SGT).isoformat() if wind_last is not None else None,
        },
        "fetched_at": fetched_at.astimezone(SGT).isoformat(),
        "sources": SOURCES,
        "links": aq.LINKS,
    }


class HazeSceneService:
    def __init__(self) -> None:
        self._cache: dict[int, tuple[datetime, dict]] = {}
        self._hotspots: tuple[datetime, dict] | None = None
        self._lock = asyncio.Lock()

    async def _get_hotspots(self, now: datetime) -> dict:
        key = os.getenv("FIRMS_MAP_KEY", "").strip()
        if not key:
            return hotspots_unavailable()
        if self._hotspots and now - self._hotspots[0] < HOTSPOT_TTL:
            return self._hotspots[1]
        result = await fetch_hotspots(key, days=3)
        # Keep errors briefly so a FIRMS outage is retried soon.
        stamp = now if result["status"] == "ok" else now - HOTSPOT_TTL + timedelta(minutes=5)
        self._hotspots = (stamp, result)
        return result

    async def scene(self, hours: int) -> dict:
        async with self._lock:
            now = datetime.now(timezone.utc)
            cached = self._cache.get(hours)
            if cached and now - cached[0] < CACHE_TTL:
                return cached[1]
            grid = hour_grid(now, hours)
            points = await asyncio.to_thread(aq.load_history, hours + 1)
            air = align_air(points, grid)
            missing = missing_air_dates(air, grid[:-1])  # the current hour may not be out yet
            if missing:
                await backfill_air(missing)
                air = align_air(await asyncio.to_thread(aq.load_history, hours + 1), grid)

            lookback = TRAJECTORY_HOURS
            full_grid = hour_grid(now, hours + lookback)
            try:
                rows = await asyncio.to_thread(load_wind_rows, full_grid[0])
            except Exception as exc:
                logger.error(f"Haze scene wind query failed: {exc}")
                rows = []
            wind_full = aggregate_wind(rows, full_grid)
            hotspots = await self._get_hotspots(now)
            scene = build_scene(grid, air, wind_full, lookback, hotspots, now)
            self._cache[hours] = (now, scene)
            return scene


_service: HazeSceneService | None = None


def get_haze_scene_service() -> HazeSceneService:
    global _service
    if _service is None:
        _service = HazeSceneService()
    return _service
