"""
Test for Singapore Data Collection Bug

This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

This test encodes the expected behavior - it will validate the fix when it passes after implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.data_collector import DataCollector, WeatherRecord


class TestSingaporeDataCollection:
    """Test Singapore data collection returns 0 records despite successful API calls"""
    
    @pytest.mark.asyncio
    async def test_singapore_api_returns_zero_records(self):
        """
        GOAL: Surface counterexamples that demonstrate Singapore data collection 
        returns 0 records despite successful API calls
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug exists)
        """
        # Create mock API responses that match Singapore API v2 format
        mock_temp_response = {
            "code": 0,
            "data": {
                "stations": [
                    {
                        "id": "S50",
                        "deviceId": "S50",
                        "name": "Clementi Road",
                        "location": {
                            "latitude": 1.3337,
                            "longitude": 103.7768
                        }
                    },
                    {
                        "id": "S24",
                        "deviceId": "S24",
                        "name": "Upper Changi Road North",
                        "location": {
                            "latitude": 1.3644,
                            "longitude": 103.9915
                        }
                    }
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 28.5},
                            {"stationId": "S24", "value": 29.2}
                        ]
                    }
                ],
                "readingType": "DBT 1M F",
                "readingUnit": "deg C"
            },
            "errorMsg": ""
        }
        
        mock_rainfall_response = {
            "code": 0,
            "data": {
                "stations": [
                    {"id": "S50", "deviceId": "S50", "name": "Clementi Road", "location": {"latitude": 1.3337, "longitude": 103.7768}},
                    {"id": "S24", "deviceId": "S24", "name": "Upper Changi Road North", "location": {"latitude": 1.3644, "longitude": 103.9915}}
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 0.0},
                            {"stationId": "S24", "value": 0.5}
                        ]
                    }
                ],
                "readingType": "Rainfall",
                "readingUnit": "mm"
            },
            "errorMsg": ""
        }
        
        mock_humidity_response = {
            "code": 0,
            "data": {
                "stations": [
                    {"id": "S50", "deviceId": "S50", "name": "Clementi Road", "location": {"latitude": 1.3337, "longitude": 103.7768}},
                    {"id": "S24", "deviceId": "S24", "name": "Upper Changi Road North", "location": {"latitude": 1.3644, "longitude": 103.9915}}
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 75.0},
                            {"stationId": "S24", "value": 78.0}
                        ]
                    }
                ],
                "readingType": "Relative Humidity",
                "readingUnit": "%"
            },
            "errorMsg": ""
        }
        
        mock_wind_speed_response = {
            "code": 0,
            "data": {
                "stations": [
                    {"id": "S50", "deviceId": "S50", "name": "Clementi Road", "location": {"latitude": 1.3337, "longitude": 103.7768}},
                    {"id": "S24", "deviceId": "S24", "name": "Upper Changi Road North", "location": {"latitude": 1.3644, "longitude": 103.9915}}
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 12.5},
                            {"stationId": "S24", "value": 15.0}
                        ]
                    }
                ],
                "readingType": "Wind Speed",
                "readingUnit": "km/h"
            },
            "errorMsg": ""
        }
        
        mock_wind_dir_response = {
            "code": 0,
            "data": {
                "stations": [
                    {"id": "S50", "deviceId": "S50", "name": "Clementi Road", "location": {"latitude": 1.3337, "longitude": 103.7768}},
                    {"id": "S24", "deviceId": "S24", "name": "Upper Changi Road North", "location": {"latitude": 1.3644, "longitude": 103.9915}}
                ],
                "readings": [
                    {
                        "timestamp": "2024-01-15T10:00:00+08:00",
                        "data": [
                            {"stationId": "S50", "value": 180.0},
                            {"stationId": "S24", "value": 200.0}
                        ]
                    }
                ],
                "readingType": "Wind Direction",
                "readingUnit": "degrees"
            },
            "errorMsg": ""
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
            
            # EXPECTED BEHAVIOR (from design document):
            # records.length > 0 AND all records have valid temperature, location, coordinates
            
            # This assertion will FAIL on unfixed code (proving bug exists)
            assert len(records) > 0, (
                f"Expected non-zero records from Singapore API, got {len(records)}. "
                f"Bug confirmed: Singapore data collection returns 0 records despite successful API calls."
            )
            
            # Verify all records have valid data
            for record in records:
                assert record.temperature > 0, f"Invalid temperature: {record.temperature}"
                assert record.location != "Unknown", f"Invalid location: {record.location}"
                assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
                assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
                assert record.country == "singapore"
                assert record.source_api == "api-open.data.gov.sg"
            
            print(f"✓ Test passed: Collected {len(records)} Singapore weather records")
            for record in records:
                print(f"  - {record.location}: {record.temperature}°C, {record.rainfall}mm, {record.humidity}%")


if __name__ == "__main__":
    # Run the test
    asyncio.run(TestSingaporeDataCollection().test_singapore_api_returns_zero_records())
