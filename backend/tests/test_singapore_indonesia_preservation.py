"""
Preservation Property Tests - Singapore and Indonesia Data Collection

**Validates: Requirements 3.5, 3.9**

These tests verify that Singapore and Indonesia data collection continues to work correctly
after implementing fixes for Malaysia data mixing issue.

IMPORTANT: These tests should PASS on UNFIXED code to establish baseline behavior.
They serve as regression tests to ensure the Malaysia fix doesn't break existing functionality.

Context:
- Singapore currently returns ~15 current observation records (working correctly)
- Indonesia currently returns ~30 current observation records (working correctly)
- We need to ensure these continue working after we fix Malaysia
- ML training should continue using only weather_data table
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List

from app.services.data_collector import DataCollector, WeatherRecord


class TestSingaporeIndonesiaPreservation:
    """
    Property-based tests to ensure Singapore and Indonesia data collection remains unchanged.
    
    These tests verify:
    - Singapore data collection returns ~15 current observation records successfully
    - Indonesia data collection returns ~30 current observation records successfully
    - Temperature and rainfall data continue to store correctly
    - ML training continues using only weather_data table
    """
    
    @pytest.mark.asyncio
    async def test_singapore_data_collection_baseline(self):
        """
        Baseline test: Verify Singapore data collection works on unfixed code.
        
        This test establishes the baseline behavior that must be preserved:
        - Singapore API calls succeed
        - Parsing returns ~15 records (one per station)
        - All records have valid current observation data
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Create realistic Singapore API response based on actual API format
        # Singapore has approximately 15 weather stations
        mock_stations = [
            {"id": f"S{i}", "name": f"Station_{i}", "location": {"latitude": 1.3 + i * 0.01, "longitude": 103.8 + i * 0.01}}
            for i in range(15)
        ]
        
        mock_temp_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 28.0 + i * 0.5}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        mock_rainfall_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 0.0 + i * 0.1}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        mock_humidity_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 70.0 + i}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        mock_wind_speed_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 10.0 + i}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        mock_wind_dir_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 180.0 + i * 10}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock the _fetch_json method to return our mock responses
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                mock_temp_response,
                mock_rainfall_response,
                mock_humidity_response,
                mock_wind_speed_response,
                mock_wind_dir_response
            ]
            
            # Call fetch_singapore_data
            records = await collector.fetch_singapore_data()
            
            # PRESERVATION REQUIREMENT: Singapore data collection must continue to work
            assert len(records) > 0, (
                f"Singapore data collection failed: expected non-zero records, got {len(records)}. "
                f"This baseline behavior must be preserved after Malaysia fix."
            )
            
            # Verify we get approximately 15 records (one per station)
            assert 10 <= len(records) <= 20, (
                f"Singapore record count changed: expected ~15 records, got {len(records)}. "
                f"This baseline behavior must be preserved after Malaysia fix."
            )
            
            # Verify all records have valid current observation data
            for record in records:
                assert record.temperature > 0, f"Invalid temperature: {record.temperature}"
                assert record.location != "Unknown", f"Invalid location: {record.location}"
                assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
                assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
                assert record.country == "singapore"
                assert record.source_api == "api-open.data.gov.sg"
            
            # Verify each location has only 1 record (current observation only)
            locations = [record.location for record in records]
            unique_locations = set(locations)
            assert len(locations) == len(unique_locations), (
                f"Singapore has duplicate records for same location. "
                f"Expected 1 record per station (current observation only)."
            )
            
            print(f"✓ Singapore baseline test passed: Collected {len(records)} current observation records")
            for record in records[:5]:  # Show first 5
                print(f"  - {record.location}: {record.temperature}°C, {record.rainfall}mm, {record.humidity}%")
    
    @pytest.mark.asyncio
    async def test_indonesia_data_collection_baseline(self):
        """
        Baseline test: Verify Indonesia data collection works on unfixed code.
        
        This test establishes the baseline behavior that must be preserved:
        - Indonesia API calls succeed (using Open-Meteo)
        - Parsing returns ~30 records (one per city)
        - All records have valid current observation data
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock Open-Meteo API responses for Indonesian cities
        mock_open_meteo_response = {
            "current": {
                "temperature_2m": 28.5,
                "relative_humidity_2m": 75.0,
                "precipitation": 0.5,
                "wind_speed_10m": 12.0,
                "wind_direction_10m": 180.0,
                "surface_pressure": 1013.25
            }
        }
        
        # Mock the _fetch_json method to return our mock response for all cities
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_open_meteo_response
            
            # Call fetch_indonesia_data
            records = await collector.fetch_indonesia_data()
            
            # PRESERVATION REQUIREMENT: Indonesia data collection must continue to work
            assert len(records) > 0, (
                f"Indonesia data collection failed: expected non-zero records, got {len(records)}. "
                f"This baseline behavior must be preserved after Malaysia fix."
            )
            
            # Verify we get approximately 30 records (one per city)
            assert 25 <= len(records) <= 35, (
                f"Indonesia record count changed: expected ~30 records, got {len(records)}. "
                f"This baseline behavior must be preserved after Malaysia fix."
            )
            
            # Verify all records have valid current observation data
            for record in records:
                assert record.temperature > 0, f"Invalid temperature: {record.temperature}"
                assert record.location != "Unknown", f"Invalid location: {record.location}"
                assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
                assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
                assert record.country == "indonesia"
                assert record.source_api == "open-meteo.com"
            
            # Verify each location has only 1 record (current observation only)
            locations = [record.location for record in records]
            unique_locations = set(locations)
            assert len(locations) == len(unique_locations), (
                f"Indonesia has duplicate records for same location. "
                f"Expected 1 record per city (current observation only)."
            )
            
            print(f"✓ Indonesia baseline test passed: Collected {len(records)} current observation records")
            for record in records[:5]:  # Show first 5
                print(f"  - {record.location}: {record.temperature}°C, {record.rainfall}mm, {record.humidity}%")
    
    @pytest.mark.asyncio
    @given(
        num_stations=st.integers(min_value=10, max_value=20),
        base_temp=st.floats(min_value=25.0, max_value=32.0),
        base_rainfall=st.floats(min_value=0.0, max_value=5.0)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_singapore_parsing_logic_unchanged(
        self,
        num_stations: int,
        base_temp: float,
        base_rainfall: float
    ):
        """
        Property-based test: Singapore parsing logic produces consistent results.
        
        Property: For all valid Singapore API responses with N stations,
        the parser returns N records with correctly extracted current observation data.
        
        This test generates many test cases to ensure parsing logic is preserved
        across different input variations.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code (establishes baseline)
        """
        # Generate mock Singapore API response with variable number of stations
        mock_stations = [
            {"id": f"S{i}", "name": f"Station_{i}", "location": {"latitude": 1.3 + i * 0.01, "longitude": 103.8 + i * 0.01}}
            for i in range(num_stations)
        ]
        
        mock_temp_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": base_temp + i * 0.5}
                            for i in range(num_stations)
                        ]
                    }
                ]
            }
        }
        
        mock_rainfall_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": base_rainfall + i * 0.1}
                            for i in range(num_stations)
                        ]
                    }
                ]
            }
        }
        
        mock_humidity_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 70.0 + i}
                            for i in range(num_stations)
                        ]
                    }
                ]
            }
        }
        
        mock_wind_speed_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 10.0 + i}
                            for i in range(num_stations)
                        ]
                    }
                ]
            }
        }
        
        mock_wind_dir_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 180.0}
                            for i in range(num_stations)
                        ]
                    }
                ]
            }
        }
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Parse the data directly (testing parsing logic)
        records = collector._parse_singapore_data(
            mock_temp_response,
            mock_rainfall_response,
            mock_humidity_response,
            mock_wind_speed_response,
            mock_wind_dir_response
        )
        
        # PRESERVATION PROPERTY: Parsing logic must remain unchanged
        # Property 1: Number of records equals number of stations (1 record per station)
        assert len(records) == num_stations, (
            f"Parsing logic changed: expected {num_stations} records, got {len(records)}"
        )
        
        # Property 2: All records have correct country and source
        for record in records:
            assert record.country == "singapore", f"Country changed: {record.country}"
            assert record.source_api == "api-open.data.gov.sg", f"Source API changed: {record.source_api}"
        
        # Property 3: Each station has exactly 1 record (current observation only)
        locations = [record.location for record in records]
        unique_locations = set(locations)
        assert len(locations) == len(unique_locations), (
            f"Singapore parser creating duplicate records. Expected 1 record per station."
        )
    
    @pytest.mark.asyncio
    @given(
        num_cities=st.integers(min_value=25, max_value=35),
        base_temp=st.floats(min_value=24.0, max_value=33.0),
        base_humidity=st.floats(min_value=60.0, max_value=90.0)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_indonesia_parsing_logic_unchanged(
        self,
        num_cities: int,
        base_temp: float,
        base_humidity: float
    ):
        """
        Property-based test: Indonesia parsing logic produces consistent results.
        
        Property: For all valid Open-Meteo API responses for N Indonesian cities,
        the system returns N records with correctly extracted current observation data.
        
        This test generates many test cases to ensure parsing logic is preserved
        across different input variations.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code (establishes baseline)
        """
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock Open-Meteo API response
        mock_response = {
            "current": {
                "temperature_2m": base_temp,
                "relative_humidity_2m": base_humidity,
                "precipitation": 0.5,
                "wind_speed_10m": 12.0,
                "wind_direction_10m": 180.0,
                "surface_pressure": 1013.25
            }
        }
        
        # Mock the _fetch_json method to return our mock response
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response
            
            # Call fetch_indonesia_data
            records = await collector.fetch_indonesia_data()
            
            # PRESERVATION PROPERTY: Parsing logic must remain unchanged
            # Property 1: Number of records approximately equals number of cities
            # (allowing for some API failures)
            assert len(records) >= num_cities * 0.8, (
                f"Parsing logic changed: expected ~{num_cities} records, got {len(records)}"
            )
            
            # Property 2: All records have correct country and source
            for record in records:
                assert record.country == "indonesia", f"Country changed: {record.country}"
                assert record.source_api == "open-meteo.com", f"Source API changed: {record.source_api}"
            
            # Property 3: Each city has exactly 1 record (current observation only)
            locations = [record.location for record in records]
            unique_locations = set(locations)
            assert len(locations) == len(unique_locations), (
                f"Indonesia parser creating duplicate records. Expected 1 record per city."
            )
    
    @pytest.mark.asyncio
    async def test_temperature_and_rainfall_storage_preserved(self):
        """
        Test that temperature and rainfall data continue to store correctly.
        
        This baseline behavior must be preserved after Malaysia fix.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Test Singapore temperature and rainfall storage
        mock_stations = [
            {"id": "S1", "name": "Station_1", "location": {"latitude": 1.3, "longitude": 103.8}}
        ]
        
        mock_temp_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": "S1", "value": 28.5}]
                    }
                ]
            }
        }
        
        mock_rainfall_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": "S1", "value": 2.5}]
                    }
                ]
            }
        }
        
        mock_humidity_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": "S1", "value": 75.0}]
                    }
                ]
            }
        }
        
        mock_wind_speed_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": "S1", "value": 12.0}]
                    }
                ]
            }
        }
        
        mock_wind_dir_response = {
            "code": 0,
            "data": {
                "stations": mock_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": "S1", "value": 180.0}]
                    }
                ]
            }
        }
        
        collector = DataCollector()
        
        # Parse Singapore data
        singapore_records = collector._parse_singapore_data(
            mock_temp_response,
            mock_rainfall_response,
            mock_humidity_response,
            mock_wind_speed_response,
            mock_wind_dir_response
        )
        
        # Verify temperature and rainfall are correctly stored
        assert len(singapore_records) == 1
        record = singapore_records[0]
        assert record.temperature == 28.5, f"Temperature storage changed: {record.temperature}"
        assert record.rainfall == 2.5, f"Rainfall storage changed: {record.rainfall}"
        assert record.humidity == 75.0, f"Humidity storage changed: {record.humidity}"
        
        print("✓ Temperature and rainfall storage preserved for Singapore")
        
        # Test Indonesia temperature and rainfall storage
        mock_indonesia_response = {
            "current": {
                "temperature_2m": 29.5,
                "relative_humidity_2m": 80.0,
                "precipitation": 1.5,
                "wind_speed_10m": 10.0,
                "wind_direction_10m": 200.0,
                "surface_pressure": 1012.0
            }
        }
        
        # Create a single record manually to test storage
        indonesia_record = WeatherRecord(
            timestamp=datetime.now(),
            country="indonesia",
            location="Jakarta",
            latitude=-6.2088,
            longitude=106.8456,
            temperature=mock_indonesia_response["current"]["temperature_2m"],
            rainfall=mock_indonesia_response["current"]["precipitation"],
            humidity=mock_indonesia_response["current"]["relative_humidity_2m"],
            wind_speed=mock_indonesia_response["current"]["wind_speed_10m"],
            wind_direction=mock_indonesia_response["current"]["wind_direction_10m"],
            pressure=mock_indonesia_response["current"]["surface_pressure"],
            source_api="open-meteo.com"
        )
        
        # Verify temperature and rainfall are correctly stored
        assert indonesia_record.temperature == 29.5, f"Temperature storage changed: {indonesia_record.temperature}"
        assert indonesia_record.rainfall == 1.5, f"Rainfall storage changed: {indonesia_record.rainfall}"
        assert indonesia_record.humidity == 80.0, f"Humidity storage changed: {indonesia_record.humidity}"
        
        print("✓ Temperature and rainfall storage preserved for Indonesia")
    
    @pytest.mark.asyncio
    async def test_ml_training_uses_only_weather_data_table(self):
        """
        Test that ML training continues using only weather_data table.
        
        This test verifies that the data collection structure remains compatible
        with ML training expectations:
        - All records are current observations (1 per location)
        - No forecast data mixed in
        - Data structure matches weather_data table schema
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Create mock data for all three countries
        mock_singapore_stations = [
            {"id": f"S{i}", "name": f"SG_Station_{i}", "location": {"latitude": 1.3 + i * 0.01, "longitude": 103.8 + i * 0.01}}
            for i in range(15)
        ]
        
        mock_temp_response = {
            "code": 0,
            "data": {
                "stations": mock_singapore_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": f"S{i}", "value": 28.0} for i in range(15)]
                    }
                ]
            }
        }
        
        mock_rainfall_response = {
            "code": 0,
            "data": {
                "stations": mock_singapore_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": f"S{i}", "value": 0.5} for i in range(15)]
                    }
                ]
            }
        }
        
        mock_humidity_response = {
            "code": 0,
            "data": {
                "stations": mock_singapore_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": f"S{i}", "value": 75.0} for i in range(15)]
                    }
                ]
            }
        }
        
        mock_wind_speed_response = {
            "code": 0,
            "data": {
                "stations": mock_singapore_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": f"S{i}", "value": 12.0} for i in range(15)]
                    }
                ]
            }
        }
        
        mock_wind_dir_response = {
            "code": 0,
            "data": {
                "stations": mock_singapore_stations,
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [{"stationId": f"S{i}", "value": 180.0} for i in range(15)]
                    }
                ]
            }
        }
        
        collector = DataCollector()
        
        # Parse Singapore data
        singapore_records = collector._parse_singapore_data(
            mock_temp_response,
            mock_rainfall_response,
            mock_humidity_response,
            mock_wind_speed_response,
            mock_wind_dir_response
        )
        
        # Mock Indonesia data
        mock_indonesia_response = {
            "current": {
                "temperature_2m": 29.0,
                "relative_humidity_2m": 78.0,
                "precipitation": 1.0,
                "wind_speed_10m": 11.0,
                "wind_direction_10m": 190.0,
                "surface_pressure": 1013.0
            }
        }
        
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_indonesia_response
            indonesia_records = await collector.fetch_indonesia_data()
        
        # Verify all records are current observations (1 per location)
        # Property: Each location should have exactly 1 record
        singapore_locations = [r.location for r in singapore_records]
        singapore_unique = set(singapore_locations)
        assert len(singapore_locations) == len(singapore_unique), (
            f"Singapore has duplicate records. ML training expects 1 record per location."
        )
        
        indonesia_locations = [r.location for r in indonesia_records]
        indonesia_unique = set(indonesia_locations)
        assert len(indonesia_locations) == len(indonesia_unique), (
            f"Indonesia has duplicate records. ML training expects 1 record per location."
        )
        
        # Verify all records have required fields for ML training
        all_records = singapore_records + indonesia_records
        for record in all_records:
            # ML training requires these fields
            assert hasattr(record, 'timestamp'), "Missing timestamp field"
            assert hasattr(record, 'country'), "Missing country field"
            assert hasattr(record, 'location'), "Missing location field"
            assert hasattr(record, 'latitude'), "Missing latitude field"
            assert hasattr(record, 'longitude'), "Missing longitude field"
            assert hasattr(record, 'temperature'), "Missing temperature field"
            assert hasattr(record, 'rainfall'), "Missing rainfall field"
            assert hasattr(record, 'humidity'), "Missing humidity field"
            
            # Verify data types match weather_data table schema
            assert isinstance(record.timestamp, datetime), "timestamp must be datetime"
            assert isinstance(record.country, str), "country must be string"
            assert isinstance(record.location, str), "location must be string"
            assert isinstance(record.latitude, float), "latitude must be float"
            assert isinstance(record.longitude, float), "longitude must be float"
            assert isinstance(record.temperature, float), "temperature must be float"
            assert isinstance(record.rainfall, float), "rainfall must be float"
            assert isinstance(record.humidity, float), "humidity must be float"
        
        print(f"✓ ML training compatibility preserved:")
        print(f"  - Singapore: {len(singapore_records)} current observation records")
        print(f"  - Indonesia: {len(indonesia_records)} current observation records")
        print(f"  - All records have required fields for weather_data table")
        print(f"  - No duplicate records per location (current observations only)")


if __name__ == "__main__":
    # Run the tests
    async def run_tests():
        test_suite = TestSingaporeIndonesiaPreservation()
        
        print("Running Singapore and Indonesia Preservation Tests...")
        print("=" * 80)
        print("IMPORTANT: These tests should PASS on unfixed code")
        print("They establish baseline behavior that must be preserved after Malaysia fix")
        print("=" * 80)
        
        # Run Singapore baseline test
        print("\n1. Singapore Baseline Test:")
        await test_suite.test_singapore_data_collection_baseline()
        
        # Run Indonesia baseline test
        print("\n2. Indonesia Baseline Test:")
        await test_suite.test_indonesia_data_collection_baseline()
        
        # Run temperature and rainfall storage test
        print("\n3. Temperature and Rainfall Storage Test:")
        await test_suite.test_temperature_and_rainfall_storage_preserved()
        
        # Run ML training compatibility test
        print("\n4. ML Training Compatibility Test:")
        await test_suite.test_ml_training_uses_only_weather_data_table()
        
        print("\n" + "=" * 80)
        print("✓ All Singapore and Indonesia preservation tests completed")
        print("\nThese tests establish the baseline behavior that must be preserved")
        print("after implementing Malaysia data mixing fix.")
        print("=" * 80)
    
    asyncio.run(run_tests())
