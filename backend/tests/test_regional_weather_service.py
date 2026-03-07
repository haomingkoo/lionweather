"""
Unit tests for RegionalWeatherService.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.regional_weather_service import (
    RegionalWeatherService,
    CityWeather,
    RegionalAPIError
)


@pytest.fixture
def service():
    """Create a RegionalWeatherService instance for testing"""
    return RegionalWeatherService(
        cache_ttl_seconds=1800,
        timeout_seconds=10.0,
        weatherapi_key="test_api_key"
    )


@pytest.fixture
def sample_malaysian_response():
    """Sample response from Malaysian Weather API"""
    return [
        {
            "location": {
                "location_name": "Kuala Lumpur"
            },
            "forecasts": [
                {
                    "temperature": {
                        "max": 32.5,
                        "min": 24.0
                    },
                    "summary": {
                        "text": "Partly Cloudy"
                    }
                }
            ]
        },
        {
            "location": {
                "location_name": "George Town"
            },
            "forecasts": [
                {
                    "temperature": {
                        "max": 31.0,
                        "min": 25.0
                    },
                    "summary": {
                        "text": "Thunderstorms"
                    }
                }
            ]
        }
    ]


@pytest.fixture
def sample_weatherapi_response():
    """Sample response from WeatherAPI"""
    return {
        "location": {
            "name": "Jakarta"
        },
        "current": {
            "temp_c": 29.5,
            "condition": {
                "text": "Sunny"
            },
            "humidity": 70,
            "wind_kph": 10.5,
            "last_updated": "2024-01-15 10:00"
        }
    }


class TestCityWeather:
    """Tests for CityWeather data model"""
    
    def test_to_dict(self):
        """Test CityWeather to_dict conversion"""
        city = CityWeather(
            id="kuala-lumpur",
            name="Kuala Lumpur",
            country="Malaysia",
            temperature=32.5,
            condition="Partly Cloudy",
            humidity=75.0,
            wind_speed=12.0,
            last_updated=datetime(2024, 1, 15, 10, 0, 0)
        )
        
        result = city.to_dict()
        
        assert result["id"] == "kuala-lumpur"
        assert result["name"] == "Kuala Lumpur"
        assert result["country"] == "Malaysia"
        assert result["temperature"] == 32.5
        assert result["condition"] == "Partly Cloudy"
        assert result["humidity"] == 75.0
        assert result["windSpeed"] == 12.0
        assert result["lastUpdated"] == "2024-01-15T10:00:00"
    
    def test_to_dict_with_none_values(self):
        """Test CityWeather to_dict with None values"""
        city = CityWeather(
            id="test-city",
            name="Test City",
            country="Test Country",
            temperature=25.0,
            condition="Clear"
        )
        
        result = city.to_dict()
        
        assert result["humidity"] is None
        assert result["windSpeed"] is None
        assert result["lastUpdated"] is None


class TestRegionalWeatherService:
    """Tests for RegionalWeatherService"""
    
    def test_initialization(self, service):
        """Test service initialization"""
        assert service.cache_ttl == timedelta(seconds=1800)
        assert service.timeout == 10.0
        assert service.weatherapi_key == "test_api_key"
        assert len(service.malaysian_cities) >= 10
        assert len(service.malaysian_cities) <= 12
        assert len(service.indonesian_cities) >= 15
        assert len(service.indonesian_cities) <= 18
        assert service.city_cache == []
        assert service.cache_timestamp is None
    
    def test_is_cache_valid_empty_cache(self, service):
        """Test cache validation with empty cache"""
        assert service.is_cache_valid() is False
    
    def test_is_cache_valid_fresh_cache(self, service):
        """Test cache validation with fresh cache"""
        service.city_cache = [
            CityWeather(
                id="test",
                name="Test",
                country="Test",
                temperature=25.0,
                condition="Clear"
            )
        ]
        service.cache_timestamp = datetime.now()
        
        assert service.is_cache_valid() is True
    
    def test_is_cache_valid_expired_cache(self, service):
        """Test cache validation with expired cache"""
        service.city_cache = [
            CityWeather(
                id="test",
                name="Test",
                country="Test",
                temperature=25.0,
                condition="Clear"
            )
        ]
        service.cache_timestamp = datetime.now() - timedelta(seconds=1900)
        
        assert service.is_cache_valid() is False
    
    @pytest.mark.asyncio
    async def test_get_regional_cities_returns_cached_data(self, service):
        """Test that get_regional_cities returns cached data when cache is valid"""
        # Set up valid cache
        cached_cities = [
            CityWeather(
                id="test",
                name="Test",
                country="Test",
                temperature=25.0,
                condition="Clear"
            )
        ]
        service.city_cache = cached_cities
        service.cache_timestamp = datetime.now()
        
        result = await service.get_regional_cities()
        
        assert result == cached_cities
    
    def test_transform_malaysian_response(self, service, sample_malaysian_response):
        """Test transformation of Malaysian API response"""
        result = service.transform_malaysian_response(sample_malaysian_response)
        
        assert len(result) == 2
        
        # Check first city
        assert result[0].id == "kuala-lumpur"
        assert result[0].name == "Kuala Lumpur"
        assert result[0].country == "Malaysia"
        assert result[0].temperature == 32.5
        assert result[0].condition == "Partly Cloudy"
        assert result[0].humidity is None
        assert result[0].wind_speed is None
        
        # Check second city
        assert result[1].id == "george-town"
        assert result[1].name == "George Town"
        assert result[1].temperature == 31.0
        assert result[1].condition == "Thunderstorms"
    
    def test_transform_malaysian_response_filters_non_curated_cities(self, service):
        """Test that Malaysian response transformation filters out non-curated cities"""
        response = [
            {
                "location": {
                    "location_name": "Unknown City"
                },
                "forecasts": [
                    {
                        "temperature": {
                            "max": 30.0
                        },
                        "summary": {
                            "text": "Clear"
                        }
                    }
                ]
            }
        ]
        
        result = service.transform_malaysian_response(response)
        
        assert len(result) == 0
    
    def test_transform_weatherapi_response(self, service, sample_weatherapi_response):
        """Test transformation of WeatherAPI response"""
        result = service.transform_weatherapi_response("Jakarta", sample_weatherapi_response)
        
        assert result.id == "jakarta"
        assert result.name == "Jakarta"
        assert result.country == "Indonesia"
        assert result.temperature == 29.5
        assert result.condition == "Sunny"
        assert result.humidity == 70.0
        assert result.wind_speed == 10.5
        assert result.last_updated is not None
    
    def test_transform_weatherapi_response_handles_missing_data(self, service):
        """Test WeatherAPI transformation handles missing data gracefully"""
        response = {
            "location": {},
            "current": {
                "condition": {
                    "text": "Unknown"
                }
            }
        }
        
        result = service.transform_weatherapi_response("Test City", response)
        
        assert result.name == "Test City"
        assert result.temperature == 0.0
        assert result.condition == "Unknown"
        assert result.humidity is None
        assert result.wind_speed is None
    
    @pytest.mark.asyncio
    async def test_fetch_indonesian_data_without_api_key(self):
        """Test that fetch_indonesian_data returns empty list without API key"""
        service = RegionalWeatherService(weatherapi_key=None)
        
        result = await service.fetch_indonesian_data()
        
        assert result == []
    
    def test_city_lists_have_correct_counts(self, service):
        """Test that city lists have the correct number of cities"""
        # Malaysian cities: ~10-12
        assert 10 <= len(service.malaysian_cities) <= 12
        
        # Indonesian cities: ~15-18
        assert 15 <= len(service.indonesian_cities) <= 18
        
        # Total: 25-30
        total = len(service.malaysian_cities) + len(service.indonesian_cities)
        assert 25 <= total <= 30
    
    def test_malaysian_cities_list(self, service):
        """Test that Malaysian cities list contains expected cities"""
        expected_cities = [
            "Kuala Lumpur",
            "George Town",
            "Johor Bahru",
            "Ipoh",
            "Kuching",
            "Kota Kinabalu"
        ]
        
        for city in expected_cities:
            assert city in service.malaysian_cities
    
    def test_indonesian_cities_list(self, service):
        """Test that Indonesian cities list contains expected cities"""
        expected_cities = [
            "Jakarta",
            "Surabaya",
            "Bandung",
            "Medan",
            "Semarang",
            "Makassar"
        ]
        
        for city in expected_cities:
            assert city in service.indonesian_cities


class TestBatchFetchingWithRetry:
    """Tests for batch fetching with retry logic and exponential backoff"""
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_success_first_attempt(self, service):
        """Test successful fetch on first attempt"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        
        result = await service._fetch_with_retry(
            mock_client,
            "https://test.com",
            params={"key": "value"}
        )
        
        assert result == mock_response
        assert mock_client.get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_success_after_failures(self, service):
        """Test successful fetch after 2 failures with exponential backoff"""
        mock_client = AsyncMock()
        
        # Create mock responses
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                # First two attempts fail
                mock_response.raise_for_status.side_effect = Exception("Network error")
            else:
                # Third attempt succeeds
                mock_response.raise_for_status = MagicMock()
            return mock_response
        
        mock_client.get = mock_get
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await service._fetch_with_retry(
                mock_client,
                "https://test.com"
            )
            
            assert call_count == 3
            # Verify exponential backoff delays: 1s, 2s
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1)
            mock_sleep.assert_any_call(2)
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_all_attempts_fail(self, service):
        """Test that exception is raised after all retry attempts fail"""
        mock_client = AsyncMock()
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("Network error")
            return mock_response
        
        mock_client.get = mock_get
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(Exception, match="Network error"):
                await service._fetch_with_retry(
                    mock_client,
                    "https://test.com",
                    max_retries=3
                )
            
            assert call_count == 3
            # Verify exponential backoff delays: 1s, 2s
            assert mock_sleep.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_malaysian_data_with_retry(self, service, sample_malaysian_response):
        """Test Malaysian data fetch uses retry logic"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.json.return_value = sample_malaysian_response
            mock_response.raise_for_status = MagicMock()
            
            with patch.object(service, '_fetch_with_retry', return_value=mock_response) as mock_retry:
                result = await service.fetch_malaysian_data()
                
                # Verify retry method was called
                mock_retry.assert_called_once()
                assert len(result) == 2
                assert result[0].name == "Kuala Lumpur"
    
    @pytest.mark.asyncio
    async def test_fetch_indonesian_city_with_retry_success(self, service, sample_weatherapi_response):
        """Test Indonesian city fetch with retry succeeds"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sample_weatherapi_response
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        
        result = await service.fetch_indonesian_city_with_retry(
            mock_client,
            "Jakarta"
        )
        
        assert result.name == "Jakarta"
        assert result.country == "Indonesia"
        assert result.temperature == 29.5
        assert mock_client.get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fetch_indonesian_city_with_retry_after_failures(self, service, sample_weatherapi_response):
        """Test Indonesian city fetch succeeds after failures with exponential backoff"""
        mock_client = AsyncMock()
        
        # First attempt fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = Exception("API error")
        
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = sample_weatherapi_response
        mock_response_success.raise_for_status = MagicMock()
        
        mock_client.get.side_effect = [mock_response_fail, mock_response_success]
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await service.fetch_indonesian_city_with_retry(
                mock_client,
                "Jakarta"
            )
            
            assert result.name == "Jakarta"
            assert mock_client.get.call_count == 2
            # Verify 1s delay after first failure
            mock_sleep.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_fetch_indonesian_city_with_retry_all_fail(self, service):
        """Test Indonesian city fetch raises exception after all retries fail"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API error")
        mock_client.get.return_value = mock_response
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(Exception, match="API error"):
                await service.fetch_indonesian_city_with_retry(
                    mock_client,
                    "Jakarta",
                    max_retries=3
                )
            
            assert mock_client.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_batch_indonesian_fetch_handles_individual_failures(self, service, sample_weatherapi_response):
        """Test batch Indonesian fetch continues when individual cities fail"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Track which city is being fetched
            call_count = 0
            
            async def mock_get(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                # Check if this is Jakarta (first city)
                params = kwargs.get('params', {})
                city = params.get('q', '')
                
                mock_response = MagicMock()
                if city == "Jakarta":
                    # Jakarta succeeds
                    mock_response.json.return_value = sample_weatherapi_response
                    mock_response.raise_for_status = MagicMock()
                else:
                    # All other cities fail
                    mock_response.raise_for_status.side_effect = Exception("API error")
                
                return mock_response
            
            mock_client.get = mock_get
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await service.fetch_indonesian_data()
                
                # Should have 1 successful city (Jakarta)
                assert len(result) == 1
                assert result[0].name == "Jakarta"
    
    @pytest.mark.asyncio
    async def test_batch_indonesian_fetch_all_succeed(self, service):
        """Test batch Indonesian fetch when all cities succeed"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Create mock responses for each city
            def create_response(city_name):
                response_data = {
                    "location": {"name": city_name},
                    "current": {
                        "temp_c": 28.0,
                        "condition": {"text": "Clear"},
                        "humidity": 70,
                        "wind_kph": 10,
                        "last_updated": "2024-01-15 10:00"
                    }
                }
                mock_response = MagicMock()
                mock_response.json.return_value = response_data
                mock_response.raise_for_status = MagicMock()
                return mock_response
            
            # Mock successful responses for all cities
            mock_client.get.side_effect = [
                create_response(city) for city in service.indonesian_cities
            ]
            
            result = await service.fetch_indonesian_data()
            
            # Should have all cities
            assert len(result) == len(service.indonesian_cities)
            assert all(city.country == "Indonesia" for city in result)
    
    @pytest.mark.asyncio
    async def test_get_regional_cities_combines_both_apis(self, service, sample_malaysian_response):
        """Test that get_regional_cities combines Malaysian and Indonesian data"""
        # Mock Malaysian API
        with patch.object(service, 'fetch_malaysian_data') as mock_malaysian:
            mock_malaysian.return_value = [
                CityWeather(
                    id="kuala-lumpur",
                    name="Kuala Lumpur",
                    country="Malaysia",
                    temperature=32.0,
                    condition="Cloudy"
                )
            ]
            
            # Mock Indonesian API
            with patch.object(service, 'fetch_indonesian_data') as mock_indonesian:
                mock_indonesian.return_value = [
                    CityWeather(
                        id="jakarta",
                        name="Jakarta",
                        country="Indonesia",
                        temperature=29.0,
                        condition="Sunny"
                    )
                ]
                
                result = await service.get_regional_cities()
                
                # Should have cities from both APIs
                assert len(result) == 2
                assert result[0].country == "Malaysia"
                assert result[1].country == "Indonesia"
                
                # Verify cache was updated
                assert len(service.city_cache) == 2
                assert service.cache_timestamp is not None
    
    @pytest.mark.asyncio
    async def test_get_regional_cities_returns_stale_cache_on_failure(self, service):
        """Test that get_regional_cities returns stale cache when both APIs fail"""
        # Set up stale cache
        stale_cities = [
            CityWeather(
                id="test",
                name="Test City",
                country="Test",
                temperature=25.0,
                condition="Clear"
            )
        ]
        service.city_cache = stale_cities
        service.cache_timestamp = datetime.now() - timedelta(seconds=2000)  # Expired
        
        # Mock both APIs to fail
        with patch.object(service, 'fetch_malaysian_data') as mock_malaysian:
            mock_malaysian.side_effect = Exception("API error")
            
            with patch.object(service, 'fetch_indonesian_data') as mock_indonesian:
                mock_indonesian.return_value = []
                
                result = await service.get_regional_cities()
                
                # Should return stale cache
                assert result == stale_cities
