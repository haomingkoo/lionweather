"""
Tests for RadarService
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.radar_service import NEAAPIError, RadarFrame, RadarService


@pytest.fixture
def radar_service():
    """Create a RadarService instance for testing"""
    return RadarService(
        cache_ttl_seconds=300,
        poll_interval_seconds=300,
        timeout_seconds=10.0
    )


@pytest.fixture
def mock_radar_response():
    """Mock NEA API response"""
    return {
        "data": {
            "items": [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "image": "https://example.com/radar1.png"
                },
                {
                    "timestamp": "2024-01-15T09:55:00Z",
                    "image": "https://example.com/radar2.png"
                },
                {
                    "timestamp": "2024-01-15T09:50:00Z",
                    "image": "https://example.com/radar3.png"
                }
            ]
        }
    }


class TestRadarFrame:
    """Tests for RadarFrame data model"""
    
    def test_radar_frame_to_dict(self):
        """Test RadarFrame to_dict conversion"""
        timestamp = datetime(2024, 1, 15, 10, 0, 0)
        frame = RadarFrame(
            timestamp=timestamp,
            image_data=b"fake_image_data",
            bounds=((1.1, 103.6), (1.5, 104.1))
        )
        
        result = frame.to_dict()
        
        assert result["timestamp"] == timestamp.isoformat()
        assert result["imageUrl"] == f"/api/radar/image/{int(timestamp.timestamp())}"
        assert result["bounds"] == [[1.1, 103.6], [1.5, 104.1]]


class TestRadarService:
    """Tests for RadarService"""
    
    def test_is_cache_valid_empty_cache(self, radar_service):
        """Test cache validation with empty cache"""
        assert not radar_service.is_cache_valid()
    
    def test_is_cache_valid_fresh_cache(self, radar_service):
        """Test cache validation with fresh cache"""
        radar_service.frame_cache = [MagicMock()]
        radar_service.cache_timestamp = datetime.now()
        
        assert radar_service.is_cache_valid()
    
    def test_is_cache_valid_stale_cache(self, radar_service):
        """Test cache validation with stale cache"""
        radar_service.frame_cache = [MagicMock()]
        radar_service.cache_timestamp = datetime.now() - timedelta(minutes=10)
        
        assert not radar_service.is_cache_valid()
    
    @pytest.mark.asyncio
    async def test_get_radar_frames_returns_cached(self, radar_service):
        """Test that get_radar_frames returns cached data when valid"""
        # Setup cache
        mock_frame = MagicMock()
        radar_service.frame_cache = [mock_frame]
        radar_service.cache_timestamp = datetime.now()
        
        result = await radar_service.get_radar_frames(count=1)
        
        assert len(result) == 1
        assert result[0] == mock_frame
    
    @pytest.mark.asyncio
    async def test_get_radar_frames_empty_cache_fetches(self, radar_service, mock_radar_response):
        """Test that get_radar_frames fetches when cache is empty"""
        with patch.object(radar_service, '_fetch_frames_from_nea', new_callable=AsyncMock) as mock_fetch:
            mock_frame = RadarFrame(
                timestamp=datetime.now(),
                image_data=b"test",
                bounds=((1.1, 103.6), (1.5, 104.1))
            )
            mock_fetch.return_value = [mock_frame]
            
            result = await radar_service.get_radar_frames(count=1)
            
            mock_fetch.assert_called_once()
            assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_get_frame_image_found(self, radar_service):
        """Test getting image data for a specific timestamp"""
        timestamp = datetime(2024, 1, 15, 10, 0, 0)
        image_data = b"test_image_data"
        
        frame = RadarFrame(
            timestamp=timestamp,
            image_data=image_data,
            bounds=((1.1, 103.6), (1.5, 104.1))
        )
        radar_service.frame_cache = [frame]
        
        result = await radar_service.get_frame_image(int(timestamp.timestamp()))
        
        assert result == image_data
    
    @pytest.mark.asyncio
    async def test_get_frame_image_not_found(self, radar_service):
        """Test getting image data for non-existent timestamp"""
        result = await radar_service.get_frame_image(1234567890)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_radar_response_success(self, radar_service, mock_radar_response):
        """Test parsing successful radar API response"""
        mock_client = AsyncMock()
        mock_image_response = MagicMock()
        mock_image_response.content = b"fake_image_data"
        mock_client.get.return_value = mock_image_response
        
        frames = await radar_service._parse_radar_response(
            mock_radar_response,
            mock_client,
            count=3
        )
        
        assert len(frames) == 3
        assert all(isinstance(frame, RadarFrame) for frame in frames)
        assert all(frame.bounds == radar_service.SINGAPORE_BOUNDS for frame in frames)
    
    @pytest.mark.asyncio
    async def test_parse_radar_response_empty_items(self, radar_service):
        """Test parsing radar response with no items"""
        mock_client = AsyncMock()
        empty_response = {"data": {"items": []}}
        
        frames = await radar_service._parse_radar_response(
            empty_response,
            mock_client,
            count=3
        )
        
        assert len(frames) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_frames_from_nea_http_error(self, radar_service):
        """Test handling HTTP errors from NEA API"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=500)
            )
            mock_client.get.return_value = mock_response
            
            with pytest.raises(NEAAPIError):
                await radar_service._fetch_frames_from_nea(count=3)
    
    @pytest.mark.asyncio
    async def test_fetch_frames_from_nea_rate_limit(self, radar_service):
        """Test handling rate limit errors from NEA API"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Rate limit",
                request=MagicMock(),
                response=MagicMock(status_code=429)
            )
            mock_client.get.return_value = mock_response
            
            with pytest.raises(NEAAPIError, match="rate limit"):
                await radar_service._fetch_frames_from_nea(count=3)
    
    @pytest.mark.asyncio
    async def test_background_polling_starts(self, radar_service):
        """Test that background polling can be started"""
        with patch.object(radar_service, '_polling_loop', new_callable=AsyncMock):
            await radar_service.start_background_polling()
            
            assert radar_service._is_running
            assert radar_service._polling_task is not None
    
    @pytest.mark.asyncio
    async def test_background_polling_stops(self, radar_service):
        """Test that background polling can be stopped"""
        # Start polling first
        with patch.object(radar_service, '_polling_loop', new_callable=AsyncMock):
            await radar_service.start_background_polling()
            
            # Now stop it
            await radar_service.stop_background_polling()
            
            assert not radar_service._is_running
    
    @pytest.mark.asyncio
    async def test_background_polling_already_running(self, radar_service):
        """Test that starting polling twice doesn't create duplicate tasks"""
        with patch.object(radar_service, '_polling_loop', new_callable=AsyncMock):
            await radar_service.start_background_polling()
            first_task = radar_service._polling_task
            
            await radar_service.start_background_polling()
            second_task = radar_service._polling_task
            
            assert first_task == second_task
            
            await radar_service.stop_background_polling()


class TestRadarServiceSingleton:
    """Tests for RadarService singleton"""
    
    def test_get_radar_service_returns_instance(self):
        """Test that get_radar_service returns a RadarService instance"""
        from app.services.radar_service import get_radar_service
        
        service = get_radar_service()
        
        assert isinstance(service, RadarService)
    
    def test_get_radar_service_returns_same_instance(self):
        """Test that get_radar_service returns the same instance"""
        from app.services.radar_service import get_radar_service
        
        service1 = get_radar_service()
        service2 = get_radar_service()
        
        assert service1 is service2
