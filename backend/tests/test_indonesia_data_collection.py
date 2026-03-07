"""
Test for Indonesia Data Collection Bug

This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

This test encodes the expected behavior - it will validate the fix when it passes after implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.data_collector import DataCollector, WeatherRecord


class TestIndonesiaDataCollection:
    """Test Indonesia data collection returns 0 records despite successful API calls"""
    
    @pytest.mark.asyncio
    async def test_indonesia_api_returns_zero_records(self):
        """
        GOAL: Surface counterexamples that demonstrate Indonesia data collection 
        returns 0 records despite successful API calls
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug exists)
        
        **Validates: Requirements 2.2, 2.3**
        """
        # Create mock XML response that matches BMKG XML format
        mock_xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<data>
    <forecast>
        <issue timestamp="202401151000" year="2024" month="01" day="15" hour="10" minute="00"/>
        <area id="501" description="Jakarta" latitude="-6.2088" longitude="106.8456" coordinate="106.8456 -6.2088" type="land">
            <parameter id="t" description="Temperature" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="C">28.5</value>
                </timerange>
            </parameter>
            <parameter id="hu" description="Humidity" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="%">75.0</value>
                </timerange>
            </parameter>
            <parameter id="ws" description="Wind Speed" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="m/s">3.5</value>
                </timerange>
            </parameter>
            <parameter id="wd" description="Wind Direction" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="deg">180</value>
                </timerange>
            </parameter>
            <parameter id="tp" description="Rainfall" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="mm">0.0</value>
                </timerange>
            </parameter>
        </area>
        <area id="502" description="Surabaya" latitude="-7.2575" longitude="112.7521" coordinate="112.7521 -7.2575" type="land">
            <parameter id="t" description="Temperature" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="C">30.2</value>
                </timerange>
            </parameter>
            <parameter id="hu" description="Humidity" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="%">80.0</value>
                </timerange>
            </parameter>
            <parameter id="ws" description="Wind Speed" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="m/s">4.2</value>
                </timerange>
            </parameter>
        </area>
        <area id="503" description="Bandung" latitude="-6.9175" longitude="107.6191" coordinate="107.6191 -6.9175" type="land">
            <parameter id="t" description="Temperature" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="C">26.8</value>
                </timerange>
            </parameter>
            <parameter id="hu" description="Humidity" type="hourly">
                <timerange type="hourly" datetime="202401151000">
                    <value unit="%">70.0</value>
                </timerange>
            </parameter>
        </area>
    </forecast>
</data>"""
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock the _fetch_xml method to return our mock XML response
        with patch.object(collector, '_fetch_xml', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_xml_response
            
            # Call fetch_indonesia_data
            records = await collector.fetch_indonesia_data()
            
            # EXPECTED BEHAVIOR (from design document):
            # records.length > 0 AND all records have valid weather parameters
            
            # This assertion will FAIL on unfixed code (proving bug exists)
            assert len(records) > 0, (
                f"Expected non-zero records from Indonesia API, got {len(records)}. "
                f"Bug confirmed: Indonesia data collection returns 0 records despite successful API calls."
            )
            
            # Verify all records have valid data
            for record in records:
                assert record.temperature > 0, f"Invalid temperature: {record.temperature}"
                assert record.location != "Unknown", f"Invalid location: {record.location}"
                assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
                assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
                assert record.country == "indonesia"
                assert record.source_api == "data.bmkg.go.id"
            
            print(f"✓ Test passed: Collected {len(records)} Indonesia weather records")
            for record in records:
                print(f"  - {record.location}: {record.temperature}°C, {record.rainfall}mm, {record.humidity}%")


if __name__ == "__main__":
    # Run the test
    asyncio.run(TestIndonesiaDataCollection().test_indonesia_api_returns_zero_records())
