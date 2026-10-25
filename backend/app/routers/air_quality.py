import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.air_quality import (
    LINKS,
    MAX_HISTORY_HOURS,
    REGIONS,
    SOURCE,
    get_air_quality_service,
    load_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/air-quality", tags=["air-quality"])


@router.get("/latest")
async def air_quality_latest():
    """Latest NEA 24-hr PSI and 1-hr PM2.5 by region, with NEA health bands."""
    service = get_air_quality_service()
    await service.refresh()
    return service.latest()


@router.get("/history")
async def air_quality_history(
    hours: int = Query(24, ge=1, le=MAX_HISTORY_HOURS),
    region: str | None = Query(None),
):
    """Hourly stored readings for the last `hours`, oldest first."""
    if region is not None and region not in REGIONS:
        raise HTTPException(status_code=400, detail=f"region must be one of {list(REGIONS)}")
    try:
        points = await asyncio.to_thread(load_history, hours)
    except Exception as exc:
        logger.error(f"Air quality history query failed: {exc}")
        raise HTTPException(status_code=503, detail="air quality history unavailable") from exc
    if region:
        points = [
            {"timestamp": p["timestamp"], "regions": {region: p["regions"][region]}}
            for p in points
            if region in p["regions"]
        ]
    return {"hours": hours, "region": region, "points": points, "source": SOURCE, "links": LINKS}
