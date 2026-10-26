import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response

from app.services import haze_scene as hs
from app.services.rain_gauges import get_rain_gauge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rain", tags=["rain"])


def latest_wind() -> dict | None:
    """The NEA station wind for the latest hour with readings, for leaning the drawn rain."""
    grid = hs.hour_grid(datetime.now(timezone.utc), 3)
    try:
        rows = hs.load_wind_rows(grid[0])
    except Exception as exc:
        logger.warning(f"Rain wind query failed: {exc.__class__.__name__}")
        return None
    mean = hs.aggregate_wind(rows, grid)["mean"]
    for t, m in zip(reversed(grid), reversed(mean)):
        if m:
            return {**m, "at": t.astimezone(hs.SGT).isoformat()}
    return None


@router.get("/gauges")
async def rain_gauges(response: Response):
    """The last two hours of 5-minute rain totals from NEA's rain gauges, plus the latest station wind."""
    data = await get_rain_gauge_service().gauges()
    if data is None:
        raise HTTPException(status_code=503, detail="rain gauges unavailable")
    response.headers["Cache-Control"] = "public, max-age=120"
    return {**data, "wind": await asyncio.to_thread(latest_wind)}
