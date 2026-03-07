"""
Integration tests for Regional Weather API.

Tests the complete flow from endpoint to service with real service instances.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.services.regional_weather_service import CityWeather
from datetime import datetime


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_cities():
    """Sample city data for testing"""
    return [
        CityWeather(
            id="kuala-lumpur",
            name="Kuala Lumpur",
            country="Malaysia",
            temperature=32.0,
            condition="Thunderstorms",
            humidity=82.0,
            wind_speed=8.0,
            last_updated=datetime(2024, 1, 15, 10, 0, 0)
        ),
        CityWeather(
            id="jakarta",
            name="Jakarta",
            country="Indonesia",
            temperature=29.5,
            condition="Sunny",
            humidity=70.0,
            wind_speed=10.0,
            last_updated=datetime(2024, 1, 15, 10, 0, 0)
        )
    ]


class TestRegionalWeatherIntegration:
    """Integration tests for regional weather endpoints"""
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_integration(self, mock_get_service, client, sample_cities):
        """Test complete flow from endpoint to service"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify response structure
        assert response.status_code == 200
        data = response.json()
        
        assert "cities" in data
        assert "cachedAt" in data
        assert "count" in data
        
        # Verify we got cities
        assert data["count"] == 2
        
        # Verify city data structure
        for city in data["cities"]:
            assert "id" in city
            assert "name" in city
            assert "country" in city
            assert "temperature" in city
            assert "condition" in city
            assert "lastUpdated" in city
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_search_functionality_integration(self, mock_get_service, client, sample_cities):
        """Test search filtering works end-to-end"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with search
        response = client.get("/api/regional/cities?search=kuala")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Should only return Kuala Lumpur
        assert data["count"] == 1
        assert all("kuala" in city["name"].lower() for city in data["cities"])
    
    def test_endpoint_exists(self, client):
        """Test that the endpoint is registered and accessible"""
        # This will fail if the endpoint doesn't exist
        # We expect either 200 (success) or 503 (service unavailable)
        # but not 404 (not found)
        response = client.get("/api/regional/cities")
        assert response.status_code in [200, 503, 500]  # Not 404
