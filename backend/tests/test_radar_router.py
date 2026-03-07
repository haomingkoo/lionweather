"""
Tests for radar API router endpoints
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.radar_service import NEAAPIError, RadarFrame

client = TestClient(app)


@pytest.fixture
def mock_radar_frames():
    """Create mock radar frames for testing"""
    frames = []
    for i in range(6):
        timestamp = datetime(2024, 1, 15, 10, i * 5, 0)
        frame = RadarFrame(
            timestamp=timestamp,
            image_data=f"image_data_{i}".encode(),
            bounds=((1.1, 103.6), (1.5, 104.1))
        )
        frames.append(frame)
    return frames


class TestGetRadarFrames:
    """Tests for GET /api/radar/frames endpoint"""
    
    def test_get_radar_frames_success(self, mock_radar_frames):
        """Test successful retrieval of radar frames"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(return_value=mock_radar_frames)
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames")
            
            assert response.status_code == 200
            data = response.json()
            assert "frames" in data
            assert "interval" in data
            assert "count" in data
            assert data["count"] == 6
            assert data["interval"] == 300
            assert len(data["frames"]) == 6
            
            # Verify frame structure
            first_frame = data["frames"][0]
            assert "timestamp" in first_frame
            assert "imageUrl" in first_frame
            assert "bounds" in first_frame
            assert first_frame["imageUrl"].startswith("/api/radar/image/")
    
    def test_get_radar_frames_with_count_parameter(self, mock_radar_frames):
        """Test retrieval with custom count parameter"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(return_value=mock_radar_frames[:3])
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames?count=3")
            
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
            assert len(data["frames"]) == 3
    
    def test_get_radar_frames_empty_response(self):
        """Test handling of empty frame list"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames")
            
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["frames"] == []
    
    def test_get_radar_frames_nea_api_error_with_cache(self, mock_radar_frames):
        """Test handling NEA API error when cache is available"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(side_effect=NEAAPIError("API unavailable"))
            mock_service.frame_cache = mock_radar_frames
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames")
            
            assert response.status_code == 200
            data = response.json()
            assert data["cached"] is True
            assert len(data["frames"]) == 6
    
    def test_get_radar_frames_nea_api_error_no_cache(self):
        """Test handling NEA API error when no cache is available"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(side_effect=NEAAPIError("API unavailable"))
            mock_service.frame_cache = []
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames")
            
            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()
    
    def test_get_radar_frames_invalid_count_parameter(self):
        """Test validation of count parameter"""
        response = client.get("/api/radar/frames?count=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/radar/frames?count=20")
        assert response.status_code == 422  # Validation error
    
    def test_get_radar_frames_unexpected_error(self):
        """Test handling of unexpected errors"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(side_effect=Exception("Unexpected error"))
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/radar/frames")
            
            assert response.status_code == 500


class TestGetRadarImage:
    """Tests for GET /api/radar/image/{timestamp} endpoint"""
    
    def test_get_radar_image_success(self):
        """Test successful retrieval of radar image"""
        timestamp = int(datetime(2024, 1, 15, 10, 0, 0).timestamp())
        image_data = b"fake_png_data"
        
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_frame_image = AsyncMock(return_value=image_data)
            mock_get_service.return_value = mock_service
            
            response = client.get(f"/api/radar/image/{timestamp}")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/png"
            assert response.content == image_data
            assert "Cache-Control" in response.headers
            assert "max-age=300" in response.headers["Cache-Control"]
    
    def test_get_radar_image_not_found(self):
        """Test handling of non-existent timestamp"""
        timestamp = 1234567890
        
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_frame_image = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service
            
            response = client.get(f"/api/radar/image/{timestamp}")
            
            assert response.status_code == 404
            detail = response.json()["detail"].lower()
            assert "radar image" in detail and "found" in detail
    
    def test_get_radar_image_nea_api_error(self):
        """Test handling of NEA API errors"""
        timestamp = int(datetime(2024, 1, 15, 10, 0, 0).timestamp())
        
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_frame_image = AsyncMock(side_effect=NEAAPIError("API unavailable"))
            mock_get_service.return_value = mock_service
            
            response = client.get(f"/api/radar/image/{timestamp}")
            
            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()
    
    def test_get_radar_image_unexpected_error(self):
        """Test handling of unexpected errors"""
        timestamp = int(datetime(2024, 1, 15, 10, 0, 0).timestamp())
        
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_frame_image = AsyncMock(side_effect=Exception("Unexpected error"))
            mock_get_service.return_value = mock_service
            
            response = client.get(f"/api/radar/image/{timestamp}")
            
            assert response.status_code == 500
    
    def test_get_radar_image_content_disposition(self):
        """Test that Content-Disposition header is set correctly"""
        timestamp = int(datetime(2024, 1, 15, 10, 0, 0).timestamp())
        image_data = b"fake_png_data"
        
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_frame_image = AsyncMock(return_value=image_data)
            mock_get_service.return_value = mock_service
            
            response = client.get(f"/api/radar/image/{timestamp}")
            
            assert response.status_code == 200
            assert "Content-Disposition" in response.headers
            assert f"radar_{timestamp}.png" in response.headers["Content-Disposition"]
            assert "inline" in response.headers["Content-Disposition"]


class TestRadarEndpointsIntegration:
    """Integration tests for radar endpoints"""
    
    def test_frames_and_image_workflow(self, mock_radar_frames):
        """Test the complete workflow of fetching frames then images"""
        with patch('app.routers.radar.get_radar_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_radar_frames = AsyncMock(return_value=mock_radar_frames)
            mock_service.get_frame_image = AsyncMock(return_value=b"image_data")
            mock_get_service.return_value = mock_service
            
            # First, get the frames
            frames_response = client.get("/api/radar/frames")
            assert frames_response.status_code == 200
            frames_data = frames_response.json()
            
            # Extract timestamp from first frame's imageUrl
            first_frame = frames_data["frames"][0]
            image_url = first_frame["imageUrl"]
            timestamp = image_url.split("/")[-1]
            
            # Then, fetch the image
            image_response = client.get(f"/api/radar/image/{timestamp}")
            assert image_response.status_code == 200
            assert image_response.headers["content-type"] == "image/png"
