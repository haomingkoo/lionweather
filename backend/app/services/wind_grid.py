"""Gridded wind over Sumatra, the Strait and Borneo from Open-Meteo, and air paths through it.

One request fetches hourly wind at 850 hPa, 925 hPa and 10 m for a 1 degree grid,
7 days back and 2 days ahead. Back-trajectories walk upwind from Singapore through
that grid; the page also gets the 850 hPa field to drift smoke forward.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LEVELS = ("850hPa", "925hPa", "10m")
LONS = np.arange(95.0, 121.0, 1.0)
LATS = np.arange(-6.0, 8.0, 1.0)
PAST_DAYS = 7
FORECAST_DAYS = 2
GRID_TTL = timedelta(hours=3)
# Keep serving the last good grid through an Open-Meteo outage for this long.
GRID_STALE_LIMIT = timedelta(hours=12)
M_PER_DEG = 111_320.0
SINGAPORE = (1.3521, 103.8198)
SUBSTEPS = 4  # per hour


@dataclass
class WindGrid:
    times: np.ndarray  # unix seconds, hourly, ascending
    lats: np.ndarray  # ascending
    lons: np.ndarray  # ascending
    u: dict[str, np.ndarray] = field(default_factory=dict)  # (time, lat, lon), m/s towards east
    v: dict[str, np.ndarray] = field(default_factory=dict)  # m/s towards north
    fetched_at: datetime | None = None

    def velocity(self, level: str, t: float, lat: float, lon: float) -> tuple[float, float] | None:
        """Bilinear in space, linear in time. None outside the grid or its hours."""
        lats, lons, times = self.lats, self.lons, self.times
        if not (lats[0] <= lat <= lats[-1] and lons[0] <= lon <= lons[-1] and times[0] <= t <= times[-1]):
            return None
        fy = (lat - lats[0]) / (lats[1] - lats[0])
        fx = (lon - lons[0]) / (lons[1] - lons[0])
        ft = (t - times[0]) / (times[1] - times[0]) if len(times) > 1 else 0.0
        y0, x0, t0 = min(int(fy), len(lats) - 2), min(int(fx), len(lons) - 2), min(int(ft), max(len(times) - 2, 0))
        wy, wx, wt = fy - y0, fx - x0, ft - t0
        out = []
        for arr in (self.u[level], self.v[level]):
            def at(ti):
                c = arr[ti, y0:y0 + 2, x0:x0 + 2]
                return (c[0, 0] * (1 - wx) + c[0, 1] * wx) * (1 - wy) + (c[1, 0] * (1 - wx) + c[1, 1] * wx) * wy
            t1 = min(t0 + 1, len(times) - 1)
            val = at(t0) * (1 - wt) + at(t1) * wt
            if not np.isfinite(val):
                return None
            out.append(float(val))
        return out[0], out[1]


def to_uv(speed: float, direction: float) -> tuple[float, float]:
    """Meteorological 'from' direction to eastward/northward components."""
    rad = math.radians(direction)
    return -speed * math.sin(rad), -speed * math.cos(rad)


def from_uv(u: float, v: float) -> tuple[float, float]:
    return math.hypot(u, v), (math.degrees(math.atan2(-u, -v)) + 360) % 360


def displace(lat: float, lon: float, u: float, v: float, seconds: float) -> tuple[float, float]:
    """Move a point by a wind (m/s) for a time; negative seconds goes back in time."""
    lat2 = lat + v * seconds / M_PER_DEG
    lon2 = lon + u * seconds / (M_PER_DEG * math.cos(math.radians((lat + lat2) / 2)))
    return lat2, lon2


def back_trajectory(grid: WindGrid, level: str, end_t: float, hours: int, start=SINGAPORE) -> dict:
    """Integrate upwind from `start`, hour by hour, with midpoint (RK2) sub-steps.

    Returns [lat, lon, hours_before] points and whether the full length was traced;
    the path stops where it leaves the grid or the hours the grid covers.
    """
    lat, lon = start
    t = float(end_t)
    points = [[round(lat, 3), round(lon, 3), 0]]
    dt = -3600.0 / SUBSTEPS
    for hour in range(1, hours + 1):
        for _ in range(SUBSTEPS):
            k1 = grid.velocity(level, t, lat, lon)
            if k1 is None:
                return {"points": points, "complete": False}
            mid_lat, mid_lon = displace(lat, lon, k1[0], k1[1], dt / 2)
            k2 = grid.velocity(level, t + dt / 2, mid_lat, mid_lon)
            if k2 is None:
                return {"points": points, "complete": False}
            lat, lon = displace(lat, lon, k2[0], k2[1], dt)
            t += dt
        points.append([round(lat, 3), round(lon, 3), hour])
    return {"points": points, "complete": True}


def parse_open_meteo(payload: list[dict] | dict, lats=LATS, lons=LONS) -> WindGrid:
    """Open-Meteo returns one object per location, in request order (lat-major)."""
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(lats) * len(lons):
        raise ValueError(f"expected {len(lats) * len(lons)} locations, got {len(items)}")
    times = np.asarray(items[0]["hourly"]["time"], dtype=np.int64)
    grid = WindGrid(times=times, lats=np.asarray(lats, float), lons=np.asarray(lons, float))
    shape = (len(times), len(lats), len(lons))
    for level in LEVELS:
        u = np.full(shape, np.nan)
        v = np.full(shape, np.nan)
        for k, item in enumerate(items):
            y, x = divmod(k, len(lons))
            hourly = item["hourly"]
            speed = np.asarray([np.nan if s is None else s for s in hourly[f"wind_speed_{level}"]], float)
            direction = np.radians([np.nan if d is None else d for d in hourly[f"wind_direction_{level}"]])
            u[:, y, x] = -speed * np.sin(direction)
            v[:, y, x] = -speed * np.cos(direction)
        grid.u[level] = u
        grid.v[level] = v
    return grid


async def fetch_wind_grid(client: httpx.AsyncClient) -> WindGrid:
    lat_list = [f"{la:g}" for la in LATS for _ in LONS]
    lon_list = [f"{lo:g}" for _ in LATS for lo in LONS]
    hourly = ",".join(f"wind_{q}_{level}" for level in LEVELS for q in ("speed", "direction"))
    params = {
        "latitude": ",".join(lat_list),
        "longitude": ",".join(lon_list),
        "hourly": hourly,
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "wind_speed_unit": "ms",
        "timezone": "GMT",
        "timeformat": "unixtime",
    }
    response = await client.get(OPEN_METEO_URL, params=params)
    response.raise_for_status()
    grid = await asyncio.to_thread(parse_open_meteo, response.json())
    grid.fetched_at = datetime.now(timezone.utc)
    return grid


def field_payload(grid: WindGrid, start: datetime, end: datetime, level: str = "850hPa") -> dict:
    """The wind field between two times, as tenths of m/s, for drifting smoke in the browser."""
    t0, t1 = start.timestamp(), end.timestamp()
    idx = np.nonzero((grid.times >= t0) & (grid.times <= t1))[0]
    if not len(idx):
        return {"status": "unavailable", "message": "No wind for this window."}

    def pack(arr):
        block = np.round(arr[idx] * 10)
        return [None if not np.isfinite(x) else int(x) for x in block.ravel()]

    now = datetime.now(timezone.utc).timestamp()
    future = grid.times[idx][grid.times[idx] > now]
    return {
        "status": "ok",
        "level": level,
        "unit": "0.1 m/s",
        "t0": int(grid.times[idx[0]]),
        "step_s": 3600,
        "hours": int(len(idx)),
        "lats": grid.lats.tolist(),
        "lons": grid.lons.tolist(),
        "u": pack(grid.u[level]),
        "v": pack(grid.v[level]),
        "forecast_from": int(future[0]) if len(future) else None,
    }


class WindGridService:
    def __init__(self) -> None:
        self._grid: WindGrid | None = None
        self._checked: datetime | None = None
        self._lock = asyncio.Lock()

    async def grid(self) -> WindGrid | None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._grid and self._checked and now - self._checked < GRID_TTL:
                return self._grid
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    self._grid = await fetch_wind_grid(client)
                self._checked = now
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.warning(f"Open-Meteo wind grid failed: {exc.__class__.__name__}")
                # Retry in 10 minutes; serve the last good grid while it is recent enough.
                self._checked = now - GRID_TTL + timedelta(minutes=10)
                if self._grid and self._grid.fetched_at and now - self._grid.fetched_at > GRID_STALE_LIMIT:
                    self._grid = None
            return self._grid


_service: WindGridService | None = None


def get_wind_grid_service() -> WindGridService:
    global _service
    if _service is None:
        _service = WindGridService()
    return _service
