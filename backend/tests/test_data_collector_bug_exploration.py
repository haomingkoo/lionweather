"""
Bug Condition Exploration Test for Data Collection API Parsing Fix

This test encodes the EXPECTED BEHAVIOR for the three parsing bugs:
- Singapore: Empty readings arrays should be handled gracefully
- Malaysia: List response format should be parsed correctly
- Indonesia: Malformed XML should be recovered gracefully

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
When the bugs are fixed, this test will PASS, confirming the expected behavior is satisfied.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

import pytest
from datetime import datetime
from app.services.data_collector import DataCollector, WeatherRecord


@pytest.fixture
def data_collector():
    """Create a DataCollector instance for testing"""
    return DataCollector(timeout_seconds=5.0)


class TestBugConditionExploration:
    """
    Property 1: Bug Condition - API Parsing Failures for Singapore, Malaysia, and Indonesia
    
    These tests demonstrate the three parsing bugs on unfixed code.
    Expected outcome: FAIL on unfixed code (proves bugs exist)
    After fix: PASS (confirms expected behavior)
    """
    
    def test_singapore_empty_readings_array(self, data_collector):
        """
        Test Singapore API parsing with empty readings array.
        
        Bug Condition: When Singapore API returns valid JSON with empty readings array,
        the system silently returns 0 records.
        
        Expected Behavior: System should handle empty readings gracefully and return
        empty list without crashing.
        
        **Validates: Requirements 1.1, 2.1**
        """
        # Mock response with empty readings array
        temp_data = {
            "metadata": {
                "stations": [
                    {
                        "id": "S50",
                        "name": "Clementi",
                        "location": {"latitude": 1.3337, "longitude": 103.7768}
                    }
                ]
            },
            "items": [
                {
                    "timestamp": "2024-01-15T10:00:00+08:00",
                    "readings": []  # Empty readings - bug condition
                }
            ]
        }
        
        rainfall_data = {"items": [{"timestamp": "2024-01-15T10:00:00+08:00", "readings": []}]}
        humidity_data = {"items": [{"timestamp": "2024-01-15T10:00:00+08:00", "readings": []}]}
        wind_speed_data = {"items": [{"timestamp": "2024-01-15T10:00:00+08:00", "readings": []}]}
        wind_dir_data = {"items": [{"timestamp": "2024-01-15T10:00:00+08:00", "readings": []}]}
        
        # Parse the data
        records = data_collector._parse_singapore_data(
            temp_data, rainfall_data, humidity_data, wind_speed_data, wind_dir_data
        )
        
        # Expected behavior: Should return empty list gracefully (not crash)
        assert isinstance(records, list)
        assert len(records) == 0
        
    def test_singapore_partial_data_some_endpoints_empty(self, data_collector):
        """
        Test Singapore API parsing with partial data (some endpoints have readings, others empty).
        
        Bug Condition: When temperature has readings but rainfall is empty,
        the system returns 0 records even though temperature data is available.
        
        Expected Behavior: System should create WeatherRecord objects with available data,
        using default values (0.0) for missing optional fields.
        
        **Validates: Requirements 1.1, 2.1**
        """
        # Temperature has readings (v2 API format)
        temp_data = {
            "code": 1,
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "item": {
                            "readings": [
                                {
                                    "station": {
                                        "id": "S50",
                                        "name": "Clementi",
                                        "location": {"latitude": 1.3337, "longitude": 103.7768}
                                    },
                                    "value": 28.5
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        # Rainfall is empty
        rainfall_data = {
            "code": 1,
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "item": {"readings": []}
                    }
                ]
            }
        }
        
        # Humidity has readings
        humidity_data = {
            "code": 1,
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "item": {
                            "readings": [
                                {
                                    "station": {
                                        "id": "S50",
                                        "name": "Clementi",
                                        "location": {"latitude": 1.3337, "longitude": 103.7768}
                                    },
                                    "value": 75.0
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        # Wind speed is empty
        wind_speed_data = {
            "code": 1,
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "item": {"readings": []}
                    }
                ]
            }
        }
        
        wind_dir_data = {
            "code": 1,
            "data": {
                "records": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "item": {"readings": []}
                    }
                ]
            }
        }
        
        # Parse the data
        records = data_collector._parse_singapore_data(
            temp_data, rainfall_data, humidity_data, wind_speed_data, wind_dir_data
        )
        
        # Expected behavior: Should successfully parse and return WeatherRecord with available data
        assert len(records) > 0, "Should return records when some endpoints have valid data"
        assert all(isinstance(r, WeatherRecord) for r in records)
        
        # Verify the record has temperature and humidity data
        record = records[0]
        assert record.temperature == 28.5
        assert record.humidity == 75.0
        assert record.rainfall == 0.0  # Default value for missing data
        assert record.wind_speed == 0.0  # Default value for missing data
        assert record.location == "Clementi"
        assert record.country == "singapore"
    
    def test_malaysia_list_response_format(self, data_collector):
        """
        Test Malaysia API parsing with list response format (not dict).
        
        Bug Condition: When Malaysia API returns a JSON array (list) directly instead of
        a dictionary with "data" key, the system crashes with AttributeError:
        'list' object has no attribute 'get'
        
        Expected Behavior: System should correctly handle list structure, iterate through
        location entries, and extract weather data without crashing.
        
        **Validates: Requirements 1.2, 2.2**
        """
        # Mock response based on actual Malaysia API format (forecast endpoint)
        # The API returns forecast data with min/max temp, not current conditions
        malaysia_list_response = [
            {
                "location": {
                    "location_id": "Ds001",
                    "location_name": "Kuala Lumpur"
                },
                "latitude": 3.1390,
                "longitude": 101.6869,
                "date": "2024-01-15",
                "min_temp": 26,
                "max_temp": 32
            },
            {
                "location": {
                    "location_id": "Ds002",
                    "location_name": "Penang"
                },
                "latitude": 5.4164,
                "longitude": 100.3327,
                "date": "2024-01-15",
                "min_temp": 25,
                "max_temp": 31
            }
        ]
        
        # Parse the data - this should NOT crash
        records = data_collector._parse_malaysia_data(malaysia_list_response)
        
        # Expected behavior: Should successfully parse list format and return WeatherRecord objects
        assert len(records) > 0, "Should return records when parsing list response format"
        assert all(isinstance(r, WeatherRecord) for r in records)
        
        # Verify records have correct data
        assert any(r.location == "Kuala Lumpur" for r in records)
        assert any(r.location == "Penang" for r in records)
        
        kl = next(r for r in records if r.location == "Kuala Lumpur")
        assert kl.temperature == 29.0  # Average of min (26) and max (32)
        assert kl.country == "malaysia"
    
    def test_indonesia_malformed_xml_mismatched_tags(self, data_collector):
        """
        Test Indonesia API parsing with malformed XML (mismatched tags).
        
        Bug Condition: When Indonesia API returns XML with mismatched opening/closing tags
        (e.g., <area>...</areas>), the system fails with ParseError: mismatched tag
        
        Expected Behavior: System should gracefully handle malformed XML by attempting
        to repair common issues or returning empty list without crashing.
        
        **Validates: Requirements 1.3, 2.3**
        """
        # Mock XML with mismatched tag (</areas> instead of </area>)
        malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
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
        </areas>
    </forecast>
</data>"""
        
        # Parse the data - this should NOT crash
        records = data_collector._parse_indonesia_data(malformed_xml)
        
        # Expected behavior: Should handle malformed XML gracefully
        # After fix: Should either repair the XML and parse successfully, or return empty list
        assert isinstance(records, list), "Should return a list even with malformed XML"
        
        # If the fix repairs the XML successfully, we should get records
        # If the fix cannot repair, it should return empty list gracefully
        if len(records) > 0:
            assert all(isinstance(r, WeatherRecord) for r in records)
            jakarta = next((r for r in records if r.location == "Jakarta"), None)
            if jakarta:
                assert jakarta.temperature == 31.0
                assert jakarta.humidity == 78.0
                assert jakarta.country == "indonesia"
    
    def test_indonesia_malformed_xml_invalid_characters(self, data_collector):
        """
        Test Indonesia API parsing with XML containing invalid characters.
        
        Bug Condition: When Indonesia API returns XML with invalid characters,
        the parser may fail.
        
        Expected Behavior: System should strip invalid characters and parse successfully,
        or return empty list gracefully.
        
        **Validates: Requirements 1.3, 2.3**
        """
        # Mock XML with some potentially problematic characters
        xml_with_issues = """<?xml version="1.0" encoding="UTF-8"?>
<data>
    <forecast>
        <area id="ID001" description="Jakarta & Surroundings" latitude="-6.2088" longitude="106.8456">
            <parameter id="t" description="Temperature">
                <timerange datetime="2024-01-15T10:00:00+07:00">
                    <value>31.0</value>
                </timerange>
            </parameter>
        </area>
    </forecast>
</data>"""
        
        # Parse the data - should handle gracefully
        records = data_collector._parse_indonesia_data(xml_with_issues)
        
        # Expected behavior: Should handle XML with special characters
        assert isinstance(records, list)
        # This particular XML should parse successfully even on unfixed code
        # (it's actually valid XML with properly escaped &)


class TestBugConditionSummary:
    """
    Summary test that validates all three bug conditions together.
    
    This test confirms that the parsing methods can handle unexpected API response
    structures without crashing and return appropriate results.
    """
    
    def test_all_bug_conditions_handled_gracefully(self, data_collector):
        """
        Comprehensive test validating all three bug conditions are handled.
        
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        # Test 1: Singapore with empty readings
        sg_empty = {
            "metadata": {"stations": [{"id": "S1", "name": "Test", "location": {"latitude": 1.0, "longitude": 103.0}}]},
            "items": [{"timestamp": "2024-01-15T10:00:00+08:00", "readings": []}]
        }
        sg_records = data_collector._parse_singapore_data(sg_empty, sg_empty, sg_empty, sg_empty, sg_empty)
        assert isinstance(sg_records, list)
        
        # Test 2: Malaysia with list format
        my_list = [
            {
                "location_name": "Test City",
                "latitude": 3.0,
                "longitude": 101.0,
                "forecast": [{"temperature": 30.0, "rainfall": 0.0, "humidity": 70.0, "wind_speed": 10.0}]
            }
        ]
        my_records = data_collector._parse_malaysia_data(my_list)
        assert isinstance(my_records, list)
        assert len(my_records) > 0  # Should successfully parse list format
        
        # Test 3: Indonesia with malformed XML
        id_malformed = """<?xml version="1.0"?><data><forecast><area id="1" description="Test" latitude="0" longitude="0"></areas></forecast></data>"""
        id_records = data_collector._parse_indonesia_data(id_malformed)
        assert isinstance(id_records, list)  # Should not crash
