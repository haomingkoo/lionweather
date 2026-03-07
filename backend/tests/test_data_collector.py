"""
Unit tests for DataCollector service
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import asyncio

from app.services.data_collector import DataCollector, WeatherRecord, RateLimiter


@pytest.fixture
def data_collector():
    """Create a DataCollector instance for testing"""
    return DataCollector(timeout_seconds=5.0)


@pytest.fixture
def mock_singapore_temp_response():
    """Mock Singapore temperature API response"""
    return {
        "metadata": {
            "stations": [
                {
                    "id": "S50",
                    "name": "Clementi",
                    "location": {"latitude": 1.3337, "longitude": 103.7768}
                },
                {
                    "id": "S44",
                    "name": "Changi",
                    "location": {"latitude": 1.3667, "longitude": 103.9833}
                }
            ]
        },
        "items": [
            {
                "timestamp": "2024-01-15T10:00:00+08:00",
                "readings": [
                    {"station_id": "S50", "value": 28.5},
                    {"station_id": "S44", "value": 29.2}
                ]
            }
        ]
    }


@pytest.fixture
def mock_singapore_rainfall_response():
    """Mock Singapore rainfall API response"""
    return {
        "items": [
            {
                "timestamp": "2024-01-15T10:00:00+08:00",
                "readings": [
                    {"station_id": "S50", "value": 0.5},
                    {"station_id": "S44", "value": 0.0}
                ]
            }
        ]
    }


@pytest.fixture
def mock_singapore_humidity_response():
    """Mock Singapore humidity API response"""
    return {
        "items": [
            {
                "timestamp": "2024-01-15T10:00:00+08:00",
                "readings": [
                    {"station_id": "S50", "value": 75.0},
                    {"station_id": "S44", "value": 72.0}
                ]
            }
        ]
    }


@pytest.fixture
def mock_singapore_wind_speed_response():
    """Mock Singapore wind speed API response"""
    return {
        "items": [
            {
                "timestamp": "2024-01-15T10:00:00+08:00",
                "readings": [
                    {"station_id": "S50", "value": 12.5},
                    {"station_id": "S44", "value": 15.0}
                ]
            }
        ]
    }


@pytest.fixture
def mock_singapore_wind_dir_response():
    """Mock Singapore wind direction API response"""
    return {
        "items": [
            {
                "timestamp": "2024-01-15T10:00:00+08:00",
                "readings": [
                    {"station_id": "S50", "value": 180.0},
                    {"station_id": "S44", "value": 200.0}
                ]
            }
        ]
    }


@pytest.fixture
def mock_malaysia_response():
    """Mock Malaysia API response"""
    return {
        "data": [
            {
                "location_id": "MY001",
                "location_name": "Kuala Lumpur",
                "latitude": 3.1390,
                "longitude": 101.6869,
                "forecast": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "temperature": 32.0,
                        "rainfall": 2.5,
                        "humidity": 80.0,
                        "wind_speed": 15.0,
                        "wind_direction": 90.0,
                        "pressure": 1010.0
                    }
                ]
            },
            {
                "location_id": "MY002",
                "location_name": "Penang",
                "latitude": 5.4164,
                "longitude": 100.3327,
                "forecast": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "suhu": 30.5,
                        "hujan": 0.0,
                        "kelembapan": 75.0,
                        "kelajuan_angin": 12.0
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_indonesia_xml_response():
    """Mock Indonesia BMKG XML response"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<data>
    <forecast>
        <area id="ID001" description="Jakarta" latitude="-6.2088" longitude="106.8456">
            <parameter id="t" description="Temperature">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>31.0</value>
                </timerange>
            </parameter>
            <parameter id="hu" description="Humidity">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>78.0</value>
                </timerange>
            </parameter>
            <parameter id="ws" description="Wind Speed">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>4.2</value>
                </timerange>
            </parameter>
            <parameter id="tp" description="Rainfall">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>1.5</value>
                </timerange>
            </parameter>
        </area>
        <area id="ID002" description="Surabaya" latitude="-7.2575" longitude="112.7521">
            <parameter id="temp" description="Temperature">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>29.5</value>
                </timerange>
            </parameter>
            <parameter id="humidity" description="Humidity">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>82.0</value>
                </timerange>
            </parameter>
            <parameter id="wind_speed" description="Wind Speed">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>3.5</value>
                </timerange>
            </parameter>
        </area>
    </forecast>
</data>"""


class TestWeatherRecord:
    """Tests for WeatherRecord dataclass"""
    
    def test_weather_record_creation(self):
        """Test that WeatherRecord can be created with all fields"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Changi",
            latitude=1.3667,
            longitude=103.9833,
            temperature=29.2,
            rainfall=0.0,
            humidity=72.0,
            wind_speed=15.0,
            wind_direction=200.0,
            pressure=1013.25,
            source_api="api-open.data.gov.sg"
        )
        
        assert record.country == "singapore"
        assert record.location == "Changi"
        assert record.temperature == 29.2
        assert record.rainfall == 0.0
        assert record.humidity == 72.0
        assert record.wind_speed == 15.0
    
    def test_weather_record_optional_fields(self):
        """Test that WeatherRecord works with optional fields as None"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Changi",
            latitude=1.3667,
            longitude=103.9833,
            temperature=29.2,
            rainfall=0.0,
            humidity=72.0,
            wind_speed=15.0,
            wind_direction=None,
            pressure=None,
            source_api="api-open.data.gov.sg"
        )
        
        assert record.wind_direction is None
        assert record.pressure is None


class TestDataCollector:
    """Tests for DataCollector class"""
    
    def test_data_collector_initialization(self, data_collector):
        """Test that DataCollector initializes with correct defaults"""
        assert data_collector.timeout_seconds == 5.0
        assert data_collector.singapore_base_url == "https://api-open.data.gov.sg"
    
    @pytest.mark.asyncio
    async def test_fetch_singapore_data(
        self,
        data_collector,
        mock_singapore_temp_response,
        mock_singapore_rainfall_response,
        mock_singapore_humidity_response,
        mock_singapore_wind_speed_response,
        mock_singapore_wind_dir_response
    ):
        """Test fetching Singapore weather data"""
        # Mock the _fetch_json method to return our test data
        with patch.object(data_collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                mock_singapore_temp_response,
                mock_singapore_rainfall_response,
                mock_singapore_humidity_response,
                mock_singapore_wind_speed_response,
                mock_singapore_wind_dir_response
            ]
            
            records = await data_collector.fetch_singapore_data()
            
            # Verify we got records
            assert len(records) == 2
            
            # Verify first record (Clementi)
            clementi = next(r for r in records if r.location == "Clementi")
            assert clementi.country == "singapore"
            assert clementi.temperature == 28.5
            assert clementi.rainfall == 0.5
            assert clementi.humidity == 75.0
            assert clementi.wind_speed == 12.5
            assert clementi.wind_direction == 180.0
            assert clementi.source_api == "api-open.data.gov.sg"
            
            # Verify second record (Changi)
            changi = next(r for r in records if r.location == "Changi")
            assert changi.country == "singapore"
            assert changi.temperature == 29.2
            assert changi.rainfall == 0.0
            assert changi.humidity == 72.0
            assert changi.wind_speed == 15.0
            assert changi.wind_direction == 200.0
    
    @pytest.mark.asyncio
    async def test_fetch_malaysia_data_error_handling(self, data_collector):
        """Test that Malaysia data fetch handles errors gracefully"""
        with patch.object(data_collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API error")
            
            records = await data_collector.fetch_malaysia_data()
            
            # Should return empty list on error
            assert isinstance(records, list)
            assert len(records) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_indonesia_data_error_handling(self, data_collector):
        """Test that Indonesia data fetch handles errors gracefully"""
        with patch.object(data_collector, '_fetch_xml', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API error")
            
            records = await data_collector.fetch_indonesia_data()
            
            # Should return empty list on error
            assert isinstance(records, list)
            assert len(records) == 0
    
    @pytest.mark.asyncio
    async def test_collect_all_sources(self, data_collector):
        """Test collecting data from all sources in parallel"""
        # Mock all three fetch methods
        with patch.object(data_collector, 'fetch_singapore_data', new_callable=AsyncMock) as mock_sg, \
             patch.object(data_collector, 'fetch_malaysia_data', new_callable=AsyncMock) as mock_my, \
             patch.object(data_collector, 'fetch_indonesia_data', new_callable=AsyncMock) as mock_id:
            
            # Set up return values
            mock_sg.return_value = [
                WeatherRecord(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    country="singapore",
                    location="Changi",
                    latitude=1.3667,
                    longitude=103.9833,
                    temperature=29.2,
                    rainfall=0.0,
                    humidity=72.0,
                    wind_speed=15.0,
                    wind_direction=200.0,
                    pressure=None,
                    source_api="api-open.data.gov.sg"
                )
            ]
            mock_my.return_value = []
            mock_id.return_value = []
            
            records = await data_collector.collect_all_sources()
            
            # Should get Singapore records (Malaysia and Indonesia return empty lists)
            assert len(records) >= 1
            assert all(isinstance(r, WeatherRecord) for r in records)
            assert any(r.country == "singapore" for r in records)
    
    @pytest.mark.asyncio
    async def test_collect_all_sources_handles_exceptions(self, data_collector):
        """Test that collect_all_sources continues when one source fails"""
        with patch.object(data_collector, 'fetch_singapore_data', new_callable=AsyncMock) as mock_sg, \
             patch.object(data_collector, 'fetch_malaysia_data', new_callable=AsyncMock) as mock_my, \
             patch.object(data_collector, 'fetch_indonesia_data', new_callable=AsyncMock) as mock_id:
            
            # Singapore succeeds
            mock_sg.return_value = [
                WeatherRecord(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    country="singapore",
                    location="Test",
                    latitude=1.0,
                    longitude=103.0,
                    temperature=28.0,
                    rainfall=0.0,
                    humidity=70.0,
                    wind_speed=10.0,
                    wind_direction=None,
                    pressure=None,
                    source_api="test"
                )
            ]
            
            # Malaysia fails
            mock_my.side_effect = Exception("API error")
            
            # Indonesia succeeds but returns empty
            mock_id.return_value = []
            
            records = await data_collector.collect_all_sources()
            
            # Should still get Singapore records despite Malaysia failure
            assert len(records) == 1
            assert records[0].country == "singapore"
    
    def test_parse_singapore_data(
        self,
        data_collector,
        mock_singapore_temp_response,
        mock_singapore_rainfall_response,
        mock_singapore_humidity_response,
        mock_singapore_wind_speed_response,
        mock_singapore_wind_dir_response
    ):
        """Test parsing Singapore API responses"""
        records = data_collector._parse_singapore_data(
            mock_singapore_temp_response,
            mock_singapore_rainfall_response,
            mock_singapore_humidity_response,
            mock_singapore_wind_speed_response,
            mock_singapore_wind_dir_response
        )
        
        assert len(records) == 2
        
        # Check that all records have required fields
        for record in records:
            assert isinstance(record, WeatherRecord)
            assert record.country == "singapore"
            assert record.temperature > 0
            assert record.humidity > 0
            assert record.wind_speed >= 0
            assert record.rainfall >= 0
            assert record.source_api == "api-open.data.gov.sg"
    
    def test_parse_singapore_data_empty_items(self, data_collector):
        """Test parsing Singapore data with empty items"""
        empty_data = {"items": []}
        
        records = data_collector._parse_singapore_data(
            empty_data, empty_data, empty_data, empty_data, empty_data
        )
        
        assert records == []
    
    def test_parse_malaysia_data(self, data_collector, mock_malaysia_response):
        """Test parsing Malaysia API responses"""
        records = data_collector._parse_malaysia_data(mock_malaysia_response)
        
        assert len(records) == 2
        
        # Check first record (Kuala Lumpur with English field names)
        kl = next(r for r in records if r.location == "Kuala Lumpur")
        assert kl.country == "malaysia"
        assert kl.temperature == 32.0
        assert kl.rainfall == 2.5
        assert kl.humidity == 80.0
        assert kl.wind_speed == 15.0
        assert kl.wind_direction == 90.0
        assert kl.pressure == 1010.0
        assert kl.source_api == "api.data.gov.my"
        
        # Check second record (Penang with Bahasa Melayu field names)
        penang = next(r for r in records if r.location == "Penang")
        assert penang.country == "malaysia"
        assert penang.temperature == 30.5
        assert penang.rainfall == 0.0
        assert penang.humidity == 75.0
        assert penang.wind_speed == 12.0
    
    def test_parse_malaysia_data_empty(self, data_collector):
        """Test parsing Malaysia data with empty response"""
        empty_data = {"data": []}
        records = data_collector._parse_malaysia_data(empty_data)
        assert records == []
    
    def test_parse_indonesia_data(self, data_collector, mock_indonesia_xml_response):
        """Test parsing Indonesia BMKG XML responses"""
        records = data_collector._parse_indonesia_data(mock_indonesia_xml_response)
        
        assert len(records) == 2
        
        # Check first record (Jakarta)
        jakarta = next(r for r in records if r.location == "Jakarta")
        assert jakarta.country == "indonesia"
        assert jakarta.temperature == 31.0
        assert jakarta.humidity == 78.0
        assert abs(jakarta.wind_speed - 15.12) < 0.5  # 4.2 m/s * 3.6 = 15.12 km/h
        assert jakarta.rainfall == 1.5
        assert jakarta.source_api == "data.bmkg.go.id"
        
        # Check second record (Surabaya)
        surabaya = next(r for r in records if r.location == "Surabaya")
        assert surabaya.country == "indonesia"
        assert surabaya.temperature == 29.5
        assert surabaya.humidity == 82.0
        assert abs(surabaya.wind_speed - 12.6) < 0.5  # 3.5 m/s * 3.6 = 12.6 km/h
    
    def test_parse_indonesia_data_invalid_xml(self, data_collector):
        """Test parsing Indonesia data with invalid XML"""
        invalid_xml = "<invalid>xml"
        records = data_collector._parse_indonesia_data(invalid_xml)
        assert records == []
    
    @pytest.mark.asyncio
    async def test_fetch_malaysia_data_with_mock(self, data_collector, mock_malaysia_response):
        """Test fetching Malaysia weather data with mocked response"""
        with patch.object(data_collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_malaysia_response
            
            records = await data_collector.fetch_malaysia_data()
            
            # Verify we got records
            assert len(records) == 2
            assert all(r.country == "malaysia" for r in records)
            assert any(r.location == "Kuala Lumpur" for r in records)
            assert any(r.location == "Penang" for r in records)
    
    @pytest.mark.asyncio
    async def test_fetch_indonesia_data_with_mock(self, data_collector, mock_indonesia_xml_response):
        """Test fetching Indonesia weather data with mocked response"""
        with patch.object(data_collector, '_fetch_xml', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_indonesia_xml_response
            
            records = await data_collector.fetch_indonesia_data()
            
            # Verify we got records
            assert len(records) == 2
            assert all(r.country == "indonesia" for r in records)
            assert any(r.location == "Jakarta" for r in records)
            assert any(r.location == "Surabaya" for r in records)



class TestRateLimiter:
    """Tests for RateLimiter class"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test that RateLimiter initializes with correct defaults"""
        limiter = RateLimiter(max_requests=100, time_window_seconds=3600)
        assert limiter.max_requests == 100
        assert limiter.time_window_seconds == 3600
        assert limiter.tokens == 100
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_token(self):
        """Test that acquiring a token decreases the token count"""
        limiter = RateLimiter(max_requests=10, time_window_seconds=3600)
        initial_tokens = limiter.tokens
        
        await limiter.acquire()
        
        assert limiter.tokens == initial_tokens - 1
    
    @pytest.mark.asyncio
    async def test_rate_limiter_multiple_acquires(self):
        """Test multiple token acquisitions"""
        limiter = RateLimiter(max_requests=5, time_window_seconds=3600)
        
        for i in range(3):
            await limiter.acquire()
        
        # Use approximate comparison due to floating-point precision
        assert abs(limiter.tokens - 2) < 0.01  # Started with 5, used 3
    
    @pytest.mark.asyncio
    async def test_rate_limiter_refill_over_time(self):
        """Test that tokens refill over time"""
        limiter = RateLimiter(max_requests=10, time_window_seconds=1)  # 1 second window for faster test
        
        # Use all tokens
        for i in range(10):
            await limiter.acquire()
        
        assert limiter.tokens < 1
        
        # Wait for refill (0.2 seconds should add 2 tokens)
        await asyncio.sleep(0.2)
        
        # Should be able to acquire again
        await limiter.acquire()
        assert limiter.tokens >= 0


class TestRetryLogic:
    """Tests for retry logic with exponential backoff"""
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_first_try(self, data_collector):
        """Test that retry succeeds on first attempt"""
        async def successful_func():
            return "success"
        
        result = await data_collector.retry_with_backoff(successful_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_after_failures(self, data_collector):
        """Test that retry succeeds after initial failures"""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await data_collector.retry_with_backoff(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_all_failures(self, data_collector):
        """Test that retry raises exception after all attempts fail"""
        async def failing_func():
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await data_collector.retry_with_backoff(failing_func)
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_delays(self, data_collector):
        """Test that retry uses correct exponential backoff delays"""
        call_times = []
        
        async def failing_func():
            call_times.append(asyncio.get_event_loop().time())
            raise Exception("Failure")
        
        try:
            await data_collector.retry_with_backoff(failing_func)
        except Exception:
            pass
        
        # Should have 3 attempts
        assert len(call_times) == 3
        
        # Check delays are approximately 1s and 2s
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.9 < delay1 < 1.2  # ~1 second with tolerance
        
        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert 1.9 < delay2 < 2.2  # ~2 seconds with tolerance


class TestDataValidation:
    """Tests for data validation and normalization"""
    
    def test_validate_record_valid_data(self, data_collector):
        """Test that valid records pass validation"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Changi",
            latitude=1.3667,
            longitude=103.9833,
            temperature=28.5,
            rainfall=5.0,
            humidity=75.0,
            wind_speed=12.5,
            wind_direction=180.0,
            pressure=1013.25,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is True
    
    def test_validate_record_invalid_temperature_too_low(self, data_collector):
        """Test that temperature below -50°C is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=-60.0,  # Invalid: too cold
            rainfall=0.0,
            humidity=50.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_invalid_temperature_too_high(self, data_collector):
        """Test that temperature above 60°C is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=70.0,  # Invalid: too hot
            rainfall=0.0,
            humidity=50.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_invalid_negative_rainfall(self, data_collector):
        """Test that negative rainfall is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=28.0,
            rainfall=-5.0,  # Invalid: negative
            humidity=50.0,
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_invalid_humidity_too_low(self, data_collector):
        """Test that humidity below 0% is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=28.0,
            rainfall=0.0,
            humidity=-10.0,  # Invalid: below 0
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_invalid_humidity_too_high(self, data_collector):
        """Test that humidity above 100% is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=28.0,
            rainfall=0.0,
            humidity=110.0,  # Invalid: above 100
            wind_speed=10.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_invalid_negative_wind_speed(self, data_collector):
        """Test that negative wind speed is rejected"""
        record = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=28.0,
            rainfall=0.0,
            humidity=50.0,
            wind_speed=-5.0,  # Invalid: negative
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        
        assert data_collector.validate_record(record) is False
    
    def test_validate_record_boundary_values(self, data_collector):
        """Test that boundary values are accepted"""
        # Test minimum valid values
        record_min = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=-50.0,  # Minimum valid
            rainfall=0.0,  # Minimum valid
            humidity=0.0,  # Minimum valid
            wind_speed=0.0,  # Minimum valid
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        assert data_collector.validate_record(record_min) is True
        
        # Test maximum valid values
        record_max = WeatherRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            country="singapore",
            location="Test",
            latitude=1.0,
            longitude=103.0,
            temperature=60.0,  # Maximum valid
            rainfall=1000.0,
            humidity=100.0,  # Maximum valid
            wind_speed=200.0,
            wind_direction=None,
            pressure=None,
            source_api="test"
        )
        assert data_collector.validate_record(record_max) is True
    
    def test_normalize_record(self, data_collector):
        """Test that normalize_record creates a valid WeatherRecord"""
        raw_data = {
            'timestamp': datetime(2024, 1, 15, 10, 0, 0),
            'location': 'Test Location',
            'latitude': 1.5,
            'longitude': 103.5,
            'temperature': 28.0,
            'rainfall': 2.5,
            'humidity': 70.0,
            'wind_speed': 15.0,
            'wind_direction': 180.0,
            'pressure': 1013.0,
            'source_api': 'test_api'
        }
        
        record = data_collector.normalize_record(raw_data, 'singapore')
        
        assert record.country == 'singapore'
        assert record.location == 'Test Location'
        assert record.temperature == 28.0
        assert record.rainfall == 2.5
        assert record.humidity == 70.0
        assert record.wind_speed == 15.0


class TestIntegrationWithRetryAndValidation:
    """Integration tests for retry logic and validation"""
    
    @pytest.mark.asyncio
    async def test_fetch_singapore_data_with_validation(self, data_collector):
        """Test that fetch_singapore_data validates records"""
        # Mock the internal fetch to return data with one invalid record
        async def mock_fetch():
            return [
                WeatherRecord(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    country="singapore",
                    location="Valid",
                    latitude=1.0,
                    longitude=103.0,
                    temperature=28.0,
                    rainfall=0.0,
                    humidity=70.0,
                    wind_speed=10.0,
                    wind_direction=None,
                    pressure=None,
                    source_api="test"
                ),
                WeatherRecord(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    country="singapore",
                    location="Invalid",
                    latitude=1.0,
                    longitude=103.0,
                    temperature=150.0,  # Invalid temperature
                    rainfall=0.0,
                    humidity=70.0,
                    wind_speed=10.0,
                    wind_direction=None,
                    pressure=None,
                    source_api="test"
                )
            ]
        
        with patch.object(data_collector, '_parse_singapore_data', return_value=await mock_fetch()):
            with patch.object(data_collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch_json:
                mock_fetch_json.return_value = {"items": []}
                
                records = await data_collector.fetch_singapore_data()
                
                # Should only get the valid record
                assert len(records) == 1
                assert records[0].location == "Valid"
    
    @pytest.mark.asyncio
    async def test_collect_all_sources_continues_on_failure(self, data_collector):
        """Test that collect_all_sources continues when one API fails"""
        with patch.object(data_collector, 'fetch_singapore_data', new_callable=AsyncMock) as mock_sg, \
             patch.object(data_collector, 'fetch_malaysia_data', new_callable=AsyncMock) as mock_my, \
             patch.object(data_collector, 'fetch_indonesia_data', new_callable=AsyncMock) as mock_id:
            
            # Singapore succeeds
            mock_sg.return_value = [
                WeatherRecord(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    country="singapore",
                    location="Test",
                    latitude=1.0,
                    longitude=103.0,
                    temperature=28.0,
                    rainfall=0.0,
                    humidity=70.0,
                    wind_speed=10.0,
                    wind_direction=None,
                    pressure=None,
                    source_api="test"
                )
            ]
            
            # Malaysia fails (but returns empty list due to error handling)
            mock_my.return_value = []
            
            # Indonesia succeeds but returns empty
            mock_id.return_value = []
            
            records = await data_collector.collect_all_sources()
            
            # Should still get Singapore records
            assert len(records) >= 1
            assert any(r.country == "singapore" for r in records)
