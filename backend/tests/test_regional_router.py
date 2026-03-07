"""
Tests for Regional Weather API router.

Tests the /api/regional/cities endpoint with search functionality,
caching, and error handling.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.services.regional_weather_service import CityWeather, RegionalAPIError


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_cities():
    """Sample city data for testing"""
    return [
        CityWeather(
            id="singapore",
            name="Singapore",
            country="Singapore",
            temperature=28.5,
            condition="Partly Cloudy",
            humidity=75.0,
            wind_speed=12.0,
            last_updated=datetime(2024, 1, 15, 10, 0, 0)
        ),
        CityWeather(
            id="kuala-lumpur",
            name="Kuala Lumpur",
            country="Malaysia",
            temperature=27.0,
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
        ),
        CityWeather(
            id="george-town",
            name="George Town",
            country="Malaysia",
            temperature=26.5,
            condition="Cloudy",
            humidity=78.0,
            wind_speed=9.0,
            last_updated=datetime(2024, 1, 15, 10, 0, 0)
        )
    ]


class TestGetRegionalCities:
    """Tests for GET /api/regional/cities endpoint"""
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_success(self, mock_get_service, client, sample_cities):
        """Test successful retrieval of regional cities"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "cities" in data
        assert "cachedAt" in data
        assert "count" in data
        
        assert len(data["cities"]) == 4
        assert data["count"] == 4
        assert data["cachedAt"] == "2024-01-15T09:45:00"
        
        # Verify first city structure
        city = data["cities"][0]
        assert city["id"] == "singapore"
        assert city["name"] == "Singapore"
        assert city["country"] == "Singapore"
        assert city["temperature"] == 28.5
        assert city["condition"] == "Partly Cloudy"
        assert city["humidity"] == 75.0
        assert city["windSpeed"] == 12.0
        assert city["lastUpdated"] == "2024-01-15T10:00:00"
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_with_search_by_name(self, mock_get_service, client, sample_cities):
        """Test filtering cities by name search"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with search parameter
        response = client.get("/api/regional/cities?search=jakarta")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 1
        assert data["count"] == 1
        assert data["cities"][0]["name"] == "Jakarta"
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_with_search_by_country(self, mock_get_service, client, sample_cities):
        """Test filtering cities by country search"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with search parameter
        response = client.get("/api/regional/cities?search=malaysia")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 2
        assert data["count"] == 2
        assert all(city["country"] == "Malaysia" for city in data["cities"])
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_with_search_case_insensitive(self, mock_get_service, client, sample_cities):
        """Test search is case-insensitive"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with uppercase search
        response = client.get("/api/regional/cities?search=SINGAPORE")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 1
        assert data["cities"][0]["name"] == "Singapore"
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_with_search_no_matches(self, mock_get_service, client, sample_cities):
        """Test search with no matching cities"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with non-matching search
        response = client.get("/api/regional/cities?search=nonexistent")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 0
        assert data["count"] == 0
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_with_search_partial_match(self, mock_get_service, client, sample_cities):
        """Test search with partial name match"""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with partial search
        response = client.get("/api/regional/cities?search=george")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 1
        assert data["cities"][0]["name"] == "George Town"
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_api_error_with_cache(self, mock_get_service, client, sample_cities):
        """Test API error returns cached data with stale flag"""
        # Setup mock service that raises error but has cache
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(
            side_effect=RegionalAPIError("API unavailable")
        )
        mock_service.city_cache = sample_cities
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 0, 0)
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify response returns cached data
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 4
        assert data["count"] == 4
        assert data["stale"] is True
        assert data["cachedAt"] == "2024-01-15T09:00:00"
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_api_error_with_cache_and_search(self, mock_get_service, client, sample_cities):
        """Test API error with search still filters cached data"""
        # Setup mock service that raises error but has cache
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(
            side_effect=RegionalAPIError("API unavailable")
        )
        mock_service.city_cache = sample_cities
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 0, 0)
        mock_get_service.return_value = mock_service
        
        # Make request with search
        response = client.get("/api/regional/cities?search=indonesia")
        
        # Verify response returns filtered cached data
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 1
        assert data["count"] == 1
        assert data["cities"][0]["country"] == "Indonesia"
        assert data["stale"] is True
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_api_error_no_cache(self, mock_get_service, client):
        """Test API error without cache returns 503"""
        # Setup mock service that raises error with no cache
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(
            side_effect=RegionalAPIError("API unavailable")
        )
        mock_service.city_cache = []
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify error response
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_unexpected_error(self, mock_get_service, client):
        """Test unexpected error returns 500"""
        # Setup mock service that raises unexpected error
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify error response
        assert response.status_code == 500
        assert "internal server error" in response.json()["detail"].lower()
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_empty_result(self, mock_get_service, client):
        """Test endpoint with empty city list"""
        # Setup mock service with empty list
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=[])
        mock_service.cache_timestamp = datetime(2024, 1, 15, 9, 45, 0)
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["cities"] == []
        assert data["count"] == 0
    
    @patch('app.routers.regional.get_regional_weather_service')
    def test_get_cities_no_cache_timestamp(self, mock_get_service, client, sample_cities):
        """Test endpoint when cache timestamp is None"""
        # Setup mock service with no cache timestamp
        mock_service = MagicMock()
        mock_service.get_regional_cities = AsyncMock(return_value=sample_cities)
        mock_service.cache_timestamp = None
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.get("/api/regional/cities")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["cities"]) == 4
        assert data["cachedAt"] is None
