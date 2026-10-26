"""Rain from NEA's rain gauges (data.gov.sg, Singapore Open Data Licence).

Each gauge reports the rain that fell in the last 5 minutes. One request for
today's readings returns the newest 25 (about two hours), which is the loop the
rain map plays. Cached for 4 minutes, so the gauges are asked at most once per
reading interval.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

SGT = timezone(timedelta(hours=8))
URL = "https://api-open.data.gov.sg/v2/real-time/api/rainfall"
CACHE_TTL = timedelta(minutes=4)
STALE_LIMIT = timedelta(minutes=30)
SOURCE = {
    "name": "NEA rain gauges via data.gov.sg",
    "url": "https://data.gov.sg/datasets/d_6580738cdd7db79374ed3152159fbd69/view",
    "licence": "Singapore Open Data Licence",
}


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "lionweather/1.0"}
    key = os.getenv("WEATHER_API_KEY")
    if key:
        headers["x-api-key"] = key
    return headers


def parse_readings(payloads: list[dict]) -> dict:
    """Merge data.gov.sg rainfall pages into one oldest-first series per gauge."""
    stations: dict[str, dict] = {}
    by_time: dict[str, dict[str, float]] = {}
    for payload in payloads:
        data = payload.get("data") or {}
        for s in data.get("stations", []):
            loc = s.get("location") or {}
            if s.get("id") and loc.get("latitude") is not None:
                stations[s["id"]] = {"id": s["id"], "name": s.get("name", s["id"]), "lat": loc["latitude"], "lng": loc["longitude"]}
        for reading in data.get("readings", []):
            ts = reading.get("timestamp")
            if not ts:
                continue
            values = by_time.setdefault(ts, {})
            for d in reading.get("data", []):
                v = d.get("value")
                if d.get("stationId") and isinstance(v, (int, float)) and v >= 0:
                    values[d["stationId"]] = float(v)
    times = sorted(by_time, key=lambda t: datetime.fromisoformat(t))
    ids = sorted(stations)
    return {
        "unit": "mm in 5 minutes",
        "times": [datetime.fromisoformat(t).astimezone(SGT).isoformat() for t in times],
        "stations": [stations[i] for i in ids],
        "values": {i: [by_time[t].get(i) for t in times] for i in ids},
    }


async def fetch_gauges(client: httpx.AsyncClient, now: datetime) -> dict:
    today = now.astimezone(SGT).date()
    pages = [(await client.get(URL, params={"date": today.isoformat()})).raise_for_status().json()]
    # Just after midnight today's page is short; the end of yesterday fills the loop.
    if len((pages[0].get("data") or {}).get("readings", [])) < 13:
        pages.append((await client.get(URL, params={"date": (today - timedelta(days=1)).isoformat()})).raise_for_status().json())
    result = parse_readings(pages)
    result["times"] = result["times"][-25:]
    result["values"] = {k: v[-25:] for k, v in result["values"].items()}
    return result


class RainGaugeService:
    def __init__(self) -> None:
        self._cached: tuple[datetime, dict] | None = None
        self._lock = asyncio.Lock()

    async def gauges(self) -> dict | None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._cached and now - self._cached[0] < CACHE_TTL:
                return self._cached[1]
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
                    data = await fetch_gauges(client, now)
                data["source"] = SOURCE
                data["fetched_at"] = now.astimezone(SGT).isoformat()
                self._cached = (now, data)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(f"Rain gauges failed: {exc.__class__.__name__}")
                if self._cached and now - self._cached[0] > STALE_LIMIT:
                    self._cached = None
            return self._cached[1] if self._cached else None


_service: RainGaugeService | None = None


def get_rain_gauge_service() -> RainGaugeService:
    global _service
    if _service is None:
        _service = RainGaugeService()
    return _service
