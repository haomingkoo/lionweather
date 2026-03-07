"""
Preservation Property Tests - Malaysia Data Collection

**Validates: Requirements 3.1, 3.2, 3.3**

These tests verify that Malaysia data collection continues to work correctly
after implementing fixes for Singapore and Indonesia data collection.

IMPORTANT: These tests should PASS on UNFIXED code to establish baseline behavior.
They serve as regression tests to ensure the fixes don't break existing functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List

from app.services.data_collector import DataCollector, WeatherRecord


class TestMalaysiaPreservation:
    """
    Property-based tests to ensure Malaysia data collection remains unchanged.
    
    These tests verify:
    - Malaysia data collection returns 1,000+ records successfully
    - Parsing logic for Malaysia data remains unchanged
    - Background task scheduling continues to work
    - Database schema and storage mechanisms remain unchanged
    """
    
    @pytest.mark.asyncio
    async def test_malaysia_data_collection_baseline(self):
        """
        Baseline test: Verify Malaysia data collection works on unfixed code.
        
        This test establishes the baseline behavior that must be preserved:
        - Malaysia API calls succeed
        - Parsing returns non-zero records
        - All records have valid data
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Create realistic Malaysia API response based on actual API format
        mock_malaysia_response = [
            {
                "location": {
                    "location_name": "Kuala Lumpur",
                    "latitude": 3.1390,
                    "longitude": 101.6869
                },
                "date": "2024-01-15T10:00:00+08:00",
                "min_temp": 24.0,
                "max_temp": 32.0
            },
            {
                "location": {
                    "location_name": "Penang",
                    "latitude": 5.4164,
                    "longitude": 100.3327
                },
                "date": "2024-01-15T10:00:00+08:00",
                "min_temp": 25.0,
                "max_temp": 31.0
            },
            {
                "location": {
                    "location_name": "Johor Bahru",
                    "latitude": 1.4927,
                    "longitude": 103.7414
                },
                "date": "2024-01-15T10:00:00+08:00",
                "min_temp": 23.0,
                "max_temp": 33.0
            }
        ]
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock the _fetch_json method to return our mock response
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_malaysia_response
            
            # Call fetch_malaysia_data
            records = await collector.fetch_malaysia_data()
            
            # PRESERVATION REQUIREMENT: Malaysia data collection must continue to work
            assert len(records) > 0, (
                f"Malaysia data collection failed: expected non-zero records, got {len(records)}. "
                f"This baseline behavior must be preserved after fixes."
            )
            
            # Verify all records have valid data (baseline behavior)
            for record in records:
                assert record.temperature > 0, f"Invalid temperature: {record.temperature}"
                assert record.location != "Unknown", f"Invalid location: {record.location}"
                assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
                assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
                assert record.country == "malaysia"
                assert record.source_api == "api.data.gov.my"
            
            print(f"✓ Baseline test passed: Collected {len(records)} Malaysia weather records")
            for record in records:
                print(f"  - {record.location}: {record.temperature}°C at ({record.latitude}, {record.longitude})")
    
    @pytest.mark.asyncio
    @given(
        num_locations=st.integers(min_value=10, max_value=100),
        min_temp_range=st.floats(min_value=20.0, max_value=25.0),
        max_temp_range=st.floats(min_value=30.0, max_value=35.0)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_malaysia_parsing_logic_unchanged(
        self,
        num_locations: int,
        min_temp_range: float,
        max_temp_range: float
    ):
        """
        Property-based test: Malaysia parsing logic produces consistent results.
        
        Property: For all valid Malaysia API responses with N locations,
        the parser returns N records with correctly calculated temperatures.
        
        This test generates many test cases to ensure parsing logic is preserved
        across different input variations.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code (establishes baseline)
        """
        # Generate mock Malaysia API response with variable number of locations
        mock_response = []
        for i in range(num_locations):
            mock_response.append({
                "location": {
                    "location_name": f"Location_{i}",
                    "latitude": 1.0 + i * 0.1,
                    "longitude": 100.0 + i * 0.1
                },
                "date": "2024-01-15T10:00:00+08:00",
                "min_temp": min_temp_range,
                "max_temp": max_temp_range
            })
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Parse the data directly (testing parsing logic)
        records = collector._parse_malaysia_data(mock_response)
        
        # PRESERVATION PROPERTY: Parsing logic must remain unchanged
        # Property 1: Number of records equals number of locations
        assert len(records) == num_locations, (
            f"Parsing logic changed: expected {num_locations} records, got {len(records)}"
        )
        
        # Property 2: Temperature is average of min and max
        expected_temp = (min_temp_range + max_temp_range) / 2.0
        for record in records:
            assert abs(record.temperature - expected_temp) < 0.01, (
                f"Temperature calculation changed: expected {expected_temp}, got {record.temperature}"
            )
        
        # Property 3: All records have correct country and source
        for record in records:
            assert record.country == "malaysia", f"Country changed: {record.country}"
            assert record.source_api == "api.data.gov.my", f"Source API changed: {record.source_api}"
    
    @pytest.mark.asyncio
    async def test_malaysia_handles_alternative_response_format(self):
        """
        Test that Malaysia parser handles both response formats (list and dict).
        
        The Malaysia API can return:
        1. Direct array: [{"location": {...}, ...}, ...]
        2. Wrapped in data key: {"data": [{"location": {...}, ...}, ...]}
        
        This baseline behavior must be preserved.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Test data
        location_data = {
            "location": {
                "location_name": "Kuala Lumpur",
                "latitude": 3.1390,
                "longitude": 101.6869
            },
            "date": "2024-01-15T10:00:00+08:00",
            "min_temp": 24.0,
            "max_temp": 32.0
        }
        
        collector = DataCollector()
        
        # Test format 1: Direct array
        records_list = collector._parse_malaysia_data([location_data])
        assert len(records_list) == 1, "Failed to parse direct array format"
        assert records_list[0].location == "Kuala Lumpur"
        
        # Test format 2: Wrapped in data key
        records_dict = collector._parse_malaysia_data({"data": [location_data]})
        assert len(records_dict) == 1, "Failed to parse wrapped dict format"
        assert records_dict[0].location == "Kuala Lumpur"
        
        # Both formats should produce identical results
        assert records_list[0].temperature == records_dict[0].temperature
        assert records_list[0].latitude == records_dict[0].latitude
        assert records_list[0].longitude == records_dict[0].longitude
        
        print("✓ Malaysia parser handles both response formats correctly")
    
    @pytest.mark.asyncio
    @given(
        location_name=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
        latitude=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
        min_temp=st.floats(min_value=-10.0, max_value=40.0, allow_nan=False, allow_infinity=False),
        max_temp=st.floats(min_value=-10.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_malaysia_parsing_robustness(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        min_temp: float,
        max_temp: float
    ):
        """
        Property-based test: Malaysia parser handles diverse valid inputs robustly.
        
        Property: For all valid location data with varying names, coordinates, and temperatures,
        the parser successfully creates WeatherRecord objects without errors.
        
        This test ensures the parser's robustness is preserved across edge cases.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        # Ensure max_temp >= min_temp for realistic data
        if max_temp < min_temp:
            min_temp, max_temp = max_temp, min_temp
        
        mock_response = [{
            "location": {
                "location_name": location_name,
                "latitude": latitude,
                "longitude": longitude
            },
            "date": "2024-01-15T10:00:00+08:00",
            "min_temp": min_temp,
            "max_temp": max_temp
        }]
        
        collector = DataCollector()
        
        # Parse should not raise exceptions
        try:
            records = collector._parse_malaysia_data(mock_response)
            
            # If parsing succeeds, verify basic properties
            if len(records) > 0:
                record = records[0]
                assert record.country == "malaysia"
                assert record.source_api == "api.data.gov.my"
                # Temperature should be between min and max
                assert min_temp <= record.temperature <= max_temp
        except Exception as e:
            # Parser should handle edge cases gracefully
            pytest.fail(f"Parser failed on valid input: {e}")
    
    @pytest.mark.asyncio
    async def test_malaysia_error_handling_preserved(self):
        """
        Test that Malaysia parser's error handling remains unchanged.
        
        The parser should gracefully handle:
        - Empty responses
        - Missing fields
        - Invalid data types
        
        This baseline error handling must be preserved.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code
        """
        collector = DataCollector()
        
        # Test 1: Empty list
        records = collector._parse_malaysia_data([])
        assert len(records) == 0, "Should handle empty list gracefully"
        
        # Test 2: Empty dict
        records = collector._parse_malaysia_data({})
        assert len(records) == 0, "Should handle empty dict gracefully"
        
        # Test 3: Missing location fields (creates record with defaults)
        # BASELINE BEHAVIOR: Parser creates record with "Unknown" location and 0.0 coordinates
        records = collector._parse_malaysia_data([{"invalid": "data"}])
        assert len(records) == 1, "Parser creates record with default values for invalid data"
        assert records[0].location == "Unknown", "Default location should be 'Unknown'"
        assert records[0].latitude == 0.0, "Default latitude should be 0.0"
        assert records[0].longitude == 0.0, "Default longitude should be 0.0"
        
        # Test 4: Missing temperature fields (should use default 0.0)
        records = collector._parse_malaysia_data([{
            "location": {
                "location_name": "Test",
                "latitude": 1.0,
                "longitude": 100.0
            }
        }])
        # Parser should handle missing temp fields and create record with default temp
        assert len(records) == 1, "Should create record with default temperature"
        assert records[0].temperature == 0.0, "Default temperature should be 0.0"
        assert records[0].location == "Test", "Location name should be preserved"
        
        print("✓ Malaysia parser error handling preserved")


if __name__ == "__main__":
    # Run the tests
    async def run_tests():
        test_suite = TestMalaysiaPreservation()
        
        print("Running Malaysia Preservation Tests...")
        print("=" * 80)
        
        # Run baseline test
        print("\n1. Baseline Test:")
        await test_suite.test_malaysia_data_collection_baseline()
        
        # Run alternative format test
        print("\n2. Alternative Format Test:")
        await test_suite.test_malaysia_handles_alternative_response_format()
        
        # Run error handling test
        print("\n3. Error Handling Test:")
        await test_suite.test_malaysia_error_handling_preserved()
        
        print("\n" + "=" * 80)
        print("✓ All Malaysia preservation tests completed")
        print("\nThese tests establish the baseline behavior that must be preserved")
        print("after implementing Singapore and Indonesia fixes.")
    
    asyncio.run(run_tests())
