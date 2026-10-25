import logging

from fastapi import APIRouter, HTTPException, Query, Response

from app.services.haze_scene import ALLOWED_HOURS, get_haze_scene_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/haze", tags=["haze"])


@router.get("/scene")
async def haze_scene(response: Response, hours: int = Query(72)):
    """Hourly PSI, PM2.5, wind and fire hotspots for the haze page. Cached for 10 minutes."""
    if hours not in ALLOWED_HOURS:
        raise HTTPException(status_code=400, detail=f"hours must be one of {list(ALLOWED_HOURS)}")
    try:
        scene = await get_haze_scene_service().scene(hours)
    except Exception as exc:
        logger.error(f"Haze scene failed: {exc}")
        raise HTTPException(status_code=503, detail="haze data unavailable") from exc
    response.headers["Cache-Control"] = "public, max-age=300"
    return scene
