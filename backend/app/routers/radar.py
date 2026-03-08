"""
Radar API router for animated rainfall visualization.

Provides endpoints for fetching radar frame metadata and serving radar images.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.radar_service import get_radar_service, NEAAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/radar", tags=["radar"])


@router.get("/frames")
async def get_radar_frames(count: int = Query(default=6, ge=1, le=12)):
    """
    Get radar frame metadata for animated visualization.
    
    Returns metadata for the latest radar frames including timestamps,
    image URLs, and geographic bounds. The actual images are served
    via the /radar/image/{timestamp} endpoint.
    
    Args:
        count: Number of frames to return (1-12, default 6)
        
    Returns:
        JSON response with frame metadata and animation settings
        
    Example response:
        {
            "frames": [
                {
                    "timestamp": "2024-01-15T10:00:00+00:00",
                    "imageUrl": "/api/radar/image/1705316400",
                    "bounds": [[1.1, 103.6], [1.5, 104.1]]
                }
            ],
            "interval": 300,
            "count": 6
        }
    """
    try:
        radar_service = get_radar_service()
        frames = await radar_service.get_radar_frames(count=count)
        
        if not frames:
            logger.warning("No radar frames available, returning empty response")
            return {
                "frames": [],
                "interval": 300,
                "count": 0
            }
        
        # Convert frames to dict format for JSON response
        # Use absolute URLs for production deployment
        import os
        backend_url = os.getenv("BACKEND_URL", "")
        
        frame_dicts = []
        for frame in frames:
            frame_dict = frame.to_dict()
            # Make image URL absolute if backend URL is set
            if backend_url and not frame_dict["imageUrl"].startswith("http"):
                frame_dict["imageUrl"] = f"{backend_url}{frame_dict['imageUrl']}"
            frame_dicts.append(frame_dict)
        
        logger.info(f"Returning {len(frame_dicts)} radar frames")
        
        return {
            "frames": frame_dicts,
            "interval": 300,  # 5 minutes in seconds
            "count": len(frame_dicts)
        }
        
    except NEAAPIError as e:
        logger.error(f"NEA API error: {e}")
        # Return cached data if available, otherwise raise error
        radar_service = get_radar_service()
        if radar_service.frame_cache:
            logger.info("Returning cached frames after API error")
            
            import os
            backend_url = os.getenv("BACKEND_URL", "")
            
            frame_dicts = []
            for frame in radar_service.frame_cache[:count]:
                frame_dict = frame.to_dict()
                if backend_url and not frame_dict["imageUrl"].startswith("http"):
                    frame_dict["imageUrl"] = f"{backend_url}{frame_dict['imageUrl']}"
                frame_dicts.append(frame_dict)
            
            return {
                "frames": frame_dicts,
                "interval": 300,
                "count": len(frame_dicts),
                "cached": True
            }
        raise HTTPException(
            status_code=503,
            detail="Radar data temporarily unavailable"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error fetching radar frames: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        ) from e


@router.get("/image/{timestamp}")
async def get_radar_image(timestamp: int):
    """
    Serve a radar image for a specific timestamp.
    
    Returns the PNG image data for the radar frame at the given timestamp.
    The timestamp should be obtained from the /radar/frames endpoint.
    
    Args:
        timestamp: Unix timestamp of the radar frame
        
    Returns:
        PNG image data with Content-Type: image/png
        
    Raises:
        404: If no frame exists for the given timestamp
        503: If radar service is unavailable
    """
    try:
        radar_service = get_radar_service()
        image_data = await radar_service.get_frame_image(timestamp)
        
        if image_data is None:
            logger.warning(f"No radar image found for timestamp {timestamp}")
            raise HTTPException(
                status_code=404,
                detail=f"No radar image found for timestamp {timestamp}"
            )
        
        logger.debug(f"Serving radar image for timestamp {timestamp}")
        
        # Return image with proper content type
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                "Content-Disposition": f"inline; filename=radar_{timestamp}.png"
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except NEAAPIError as e:
        logger.error(f"NEA API error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Radar data temporarily unavailable"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error serving radar image: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        ) from e
