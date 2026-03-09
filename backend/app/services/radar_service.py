"""
Radar Service for fetching and caching NEA radar imagery.

This service scrapes radar images directly from weather.gov.sg since there's
no official API. Images are fetched every 10 minutes and cached for all users.

Rate Limit Optimization:
- Polls every 10 minutes instead of 5 to reduce load
- Adds 500ms delays between image fetches to avoid bursts
- No API key needed (public images)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class NEAAPIError(Exception):
    """Exception raised when NEA API requests fail"""
    pass


@dataclass
class RadarFrame:
    """Data model for a single radar frame"""
    timestamp: datetime
    image_data: bytes
    bounds: tuple[tuple[float, float], tuple[float, float]]  # ((lat_sw, lon_sw), (lat_ne, lon_ne))

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "imageUrl": f"/api/radar/image/{int(self.timestamp.timestamp())}",
            "bounds": [list(self.bounds[0]), list(self.bounds[1])]
        }


class RadarService:
    """
    Service for fetching and caching NEA radar imagery with background polling.
    
    The service automatically fetches radar data every 10 minutes in the background.
    All users get served from the same cached data for instant responses.
    
    Rate Limit Considerations:
    - API calls: 1 per poll (metadata only)
    - CDN image fetches: 6 per poll (with 500ms delays)
    - Total API impact: ~6 calls/hour (well under 36/hour limit)
    """
    
    # Exact bounds from weather.gov.sg JS: map_latitude_bottom/top/longitude_left/right
    SINGAPORE_BOUNDS = ((1.1550, 103.565), (1.4750, 104.130))
    
    def __init__(
        self,
        base_url: str = "https://api-open.data.gov.sg",
        cache_ttl_seconds: int = 120,  # 2 minutes — near-realtime
        poll_interval_seconds: int = 120,  # 2 minutes
        timeout_seconds: float = 10.0,
        user_agent: str = "weather-starter/0.1 (educational project)",
        api_key: Optional[str] = None
    ):
        self.base_url = base_url
        self.radar_path = "/v2/real-time/api/rain-area"
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.poll_interval = poll_interval_seconds
        self.timeout = timeout_seconds
        self.user_agent = user_agent
        self.api_key = api_key
        
        # In-memory cache
        self.frame_cache: list[RadarFrame] = []
        self.cache_timestamp: Optional[datetime] = None
        
        # Background polling task
        self._polling_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    def is_cache_valid(self) -> bool:
        """Check if cached frames are still valid based on TTL"""
        if not self.cache_timestamp or not self.frame_cache:
            return False
        
        age = datetime.now() - self.cache_timestamp
        return age < self.cache_ttl
    
    async def get_radar_frames(self, count: int = 20) -> list[RadarFrame]:
        """
        Get radar frames from cache or fetch if cache is invalid.
        
        Args:
            count: Number of frames to return (default 6)
            
        Returns:
            List of RadarFrame objects
        """
        # If cache is valid, return cached frames
        if self.is_cache_valid():
            logger.info(f"Returning {len(self.frame_cache[:count])} cached radar frames")
            return self.frame_cache[:count]
        
        # If cache is empty or stale, fetch immediately
        if not self.frame_cache or not self.is_cache_valid():
            logger.info("Cache empty or stale, fetching radar frames immediately")
            try:
                await self._fetch_and_cache_frames(count)
                logger.info(f"Successfully fetched and cached {len(self.frame_cache)} frames")
            except Exception as e:
                logger.error(f"Failed to fetch radar frames: {e}")
                # Return empty list if fetch fails and cache is empty
                if not self.frame_cache:
                    logger.warning("No cached frames available, returning empty list")
                    return []
        
        # Return whatever we have in cache (may be stale but better than nothing)
        logger.info(f"Returning {len(self.frame_cache[:count])} radar frames from cache")
        return self.frame_cache[:count]
    
    async def _fetch_and_cache_frames(self, count: int = 20) -> None:
        """
        Fetch radar frames from weather.gov.sg and update cache.
        
        This method fetches the latest radar imagery by scraping.
        """
        try:
            frames = await self._fetch_frames_from_nea(count)
            if frames:
                self.frame_cache = frames
                self.cache_timestamp = datetime.now()
                logger.info(f"Successfully cached {len(frames)} radar frames")
            else:
                logger.warning("No frames returned from weather.gov.sg")
        except NEAAPIError as e:
            logger.error(f"Radar scraping error: {e}")
            # Keep existing cache if available
            if not self.frame_cache:
                raise
        except Exception as e:
            logger.error(f"Unexpected error fetching radar frames: {e}")
            if not self.frame_cache:
                raise
    
    async def _fetch_frames_from_nea(self, count: int = 20) -> list[RadarFrame]:
        """
        Fetch radar frames by scraping weather.gov.sg images.
        
        Args:
            count: Number of frames to fetch
            
        Returns:
            List of RadarFrame objects
        """
        frames = []
        # weather.gov.sg uses Singapore time (UTC+8) — use that timezone
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)

        # Round down to nearest 5 minutes — fetch from current slot first
        minutes = (now.minute // 5) * 5
        current_time = now.replace(minute=minutes, second=0, microsecond=0)
        
        headers = {
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            # Fetch frames going back in time (5 minute intervals)
            for i in range(count):
                try:
                    frame_time = current_time - timedelta(minutes=i * 5)
                    
                    # Format timestamp as yyyyMMddHHmm
                    timestamp_str = frame_time.strftime("%Y%m%d%H%M")
                    
                    # Construct image URL
                    image_url = f"https://www.weather.gov.sg/files/rainarea/50km/v2/dpsri_70km_{timestamp_str}0000dBR.dpsri.png"
                    
                    # Add delay between requests (except first one)
                    if i > 0:
                        await asyncio.sleep(0.5)
                    
                    # Fetch image
                    response = await client.get(image_url)
                    response.raise_for_status()
                    image_data = response.content
                    
                    # Create RadarFrame
                    frame = RadarFrame(
                        timestamp=frame_time,
                        image_data=image_data,
                        bounds=self.SINGAPORE_BOUNDS
                    )
                    frames.append(frame)
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch radar frame for {frame_time}: {e}")
                    continue
        
        if not frames:
            raise NEAAPIError("No radar frames could be fetched")

        # Reverse so frames are in chronological order (oldest → newest)
        frames.reverse()
        logger.info(f"Successfully fetched {len(frames)} radar frames via scraping")
        return frames
    
    async def _parse_radar_response(
        self,
        data: dict,
        client: httpx.AsyncClient,
        count: int
    ) -> list[RadarFrame]:
        """
        Parse NEA radar API response and fetch image data.
        
        Args:
            data: JSON response from NEA API
            client: HTTP client for fetching images
            count: Number of frames to fetch
            
        Returns:
            List of RadarFrame objects
        """
        frames = []
        
        # Extract items from response
        items = data.get("data", {}).get("items", [])
        if not items:
            logger.warning("No items in radar API response")
            return frames
        
        # Limit to requested count
        items = items[:count]
        
        # Create a separate client for image fetching (CDN, not API)
        # Don't include API key for CDN image requests
        image_headers = {
            "User-Agent": self.user_agent,
        }
        
        async with httpx.AsyncClient(timeout=self.timeout, headers=image_headers) as image_client:
            # Fetch each frame's image data with delays to avoid bursts
            for i, item in enumerate(items):
                try:
                    # Add delay between image fetches (except first one)
                    if i > 0:
                        await asyncio.sleep(0.5)  # 500ms delay between images
                    
                    timestamp_str = item.get("timestamp")
                    if not timestamp_str:
                        logger.warning("Item missing timestamp, skipping")
                        continue
                    
                    # Parse timestamp
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    
                    # Get image URL
                    image_url = item.get("image")
                    if not image_url:
                        logger.warning(f"Item {timestamp_str} missing image URL, skipping")
                        continue
                    
                    # Fetch image data from CDN
                    image_response = await image_client.get(image_url)
                    image_response.raise_for_status()
                    image_data = image_response.content
                    
                    # Create RadarFrame
                    frame = RadarFrame(
                        timestamp=timestamp,
                        image_data=image_data,
                        bounds=self.SINGAPORE_BOUNDS
                    )
                    frames.append(frame)
                    
                except Exception as e:
                    logger.error(f"Failed to process radar frame: {e}")
                    continue
        
        logger.info(f"Successfully fetched {len(frames)} radar frames")
        return frames
    
    async def get_frame_image(self, timestamp: int) -> Optional[bytes]:
        """
        Get image data for a specific frame by timestamp.

        Args:
            timestamp: Unix timestamp of the frame

        Returns:
            Image data as bytes, or None if not found
        """
        # Use UTC-aware datetime to safely compare with tz-aware frame timestamps
        target_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        for frame in self.frame_cache:
            frame_ts = frame.timestamp
            # Normalise to UTC if the frame has a different timezone
            if frame_ts.tzinfo is None:
                frame_ts = frame_ts.replace(tzinfo=timezone.utc)
            else:
                frame_ts = frame_ts.astimezone(timezone.utc)
            # Match within 60-second window (5-min frames — generous tolerance)
            if abs((frame_ts - target_dt).total_seconds()) < 60:
                return frame.image_data

        return None
    
    async def start_background_polling(self) -> None:
        """
        Start background polling task that fetches radar data every 10 minutes.
        
        This should be called when the application starts up.
        """
        if self._is_running:
            logger.warning("Background polling already running")
            return
        
        self._is_running = True
        self._polling_task = asyncio.create_task(self._polling_loop())
        logger.info("Started background radar polling")
    
    async def stop_background_polling(self) -> None:
        """
        Stop background polling task.
        
        This should be called when the application shuts down.
        """
        if not self._is_running:
            return
        
        self._is_running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background radar polling")
    
    async def _polling_loop(self) -> None:
        """
        Background polling loop that fetches radar data at regular intervals.
        """
        # Fetch immediately on startup
        try:
            await self._fetch_and_cache_frames()
        except Exception as e:
            logger.warning(f"Initial radar fetch failed (radar may not be available): {e}")
        
        # Then poll at regular intervals
        while self._is_running:
            try:
                await asyncio.sleep(self.poll_interval)
                if self._is_running:  # Check again after sleep
                    await self._fetch_and_cache_frames()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Radar polling failed (continuing): {e}")
                # Continue polling even if one fetch fails


# Global singleton instance
_radar_service_instance: Optional[RadarService] = None


def get_radar_service() -> RadarService:
    """
    Get the global RadarService instance.
    
    Returns:
        RadarService singleton instance
    """
    import os
    
    global _radar_service_instance
    if _radar_service_instance is None:
        api_key = os.getenv("WEATHERAPI_KEY")
        logger.info(f"Initializing radar service with API key: {'present' if api_key else 'missing'}")
        if api_key:
            logger.info(f"API key starts with: {api_key[:10]}...")
        _radar_service_instance = RadarService(api_key=api_key)
    return _radar_service_instance
