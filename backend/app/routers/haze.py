import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response

from app.services import wind_grid as wg
from app.services.haze_scene import ALLOWED_HOURS, get_haze_scene_service, hour_grid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/haze", tags=["haze"])

# Smoke drift starts from fires seen up to a day before the window and runs a day past it.
FIELD_MARGIN = timedelta(hours=24)


def _check(hours: int) -> None:
    if hours not in ALLOWED_HOURS:
        raise HTTPException(status_code=400, detail=f"hours must be one of {list(ALLOWED_HOURS)}")


@router.get("/scene")
async def haze_scene(response: Response, hours: int = Query(72)):
    """Hourly PSI, PM2.5, wind, air paths and fire hotspots for the haze page. Cached for 10 minutes."""
    _check(hours)
    try:
        scene = await get_haze_scene_service().scene(hours)
    except Exception as exc:
        logger.error(f"Haze scene failed: {exc}")
        raise HTTPException(status_code=503, detail="haze data unavailable") from exc
    response.headers["Cache-Control"] = "public, max-age=300"
    return scene


@router.get("/wind-field")
async def haze_wind_field(response: Response, hours: int = Query(72)):
    """850 hPa wind over the region for the window, plus a day either side, for the smoke drift."""
    _check(hours)
    grid = await wg.get_wind_grid_service().grid()
    if grid is None:
        return {"status": "unavailable", "message": "Wind for the smoke drift is not available right now."}
    hours_grid = hour_grid(datetime.now(timezone.utc), hours)
    payload = wg.field_payload(grid, hours_grid[0] - FIELD_MARGIN, hours_grid[-1] + FIELD_MARGIN)
    response.headers["Cache-Control"] = "public, max-age=900"
    return payload
