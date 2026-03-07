"""
Bug Condition Exploration Test - Malaysia Data Mixing Current and Forecasts

**Validates: Requirements 1.9**

This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

GOAL: Surface counterexamples showing Malaysia stores 2,520+ records (mixing current + forecasts)

The bug is that Malaysia API returns forecast data with 7 time periods per location,
resulting in 2,520 records (284 locations × 7 forecast periods + current) being stored
in the weather_data table. This mixes current observations with forecast data, creating
data leakage risks for ML training.

Expected behavior after fix:
- Malaysia should store only ~284 records (1 current observation per location)
- Forecast data should be stored in a separate forecast_data table

EXPECTED OUTCOME: Test FAILS on unfixed code (this is correct - it proves the bug exists)
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck

from app.services.data_collector import DataCollector, WeatherRecord


class TestMalaysiaDataMixingExploration:
    """
    Bug condition exploration test for Malaysia data mixing issue.
    
    This test verifies that Malaysia currently returns 2,520+ records because
    it includes 7 forecast periods per location, mixing current observations
    with forecast data in the same table.
    """
    
    @pytest.mark.asyncio
    async def test_malaysia_returns_excessive_records_with_forecasts(self):
        """
        GOAL: Surface counterexamples showing Malaysia stores 2,520+ records
        
        Bug Condition: Malaysia API returns forecast data with multiple time periods
        per location, resulting in 2,520+ records (284 locations × 7 forecast periods)
        being stored in the weather_data table.
        
        This test creates a realistic Malaysia API response with multiple forecast
        periods per location to demonstrate the bug.
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug exists)
        After fix: Test PASSES (Malaysia returns only ~284 current observation records)
        """
        # Create mock Malaysia API response with multiple forecast periods per location
        # Simulating 284 locations with 7 forecast periods each
        num_locations = 284
        num_forecast_periods = 7
        
        mock_malaysia_response = []
        
        # Generate forecast data for each location with 7 time periods
        for location_idx in range(num_locations):
            location_name = f"Location_{location_idx}"
            latitude = 1.0 + (location_idx * 0.1)
            longitude = 100.0 + (location_idx * 0.1)
            
            # Create 7 forecast periods for this location (current + 6 future periods)
            for period_idx in range(num_forecast_periods):
                forecast_time = datetime.now() + timedelta(hours=period_idx * 3)
                
                mock_malaysia_response.append({
                    "location": {
                        "location_name": location_name,
                        "latitude": latitude,
                        "longitude": longitude
                    },
                    "date": forecast_time.isoformat(),
                    "min_temp": 24.0 + period_idx,
                    "max_temp": 32.0 + period_idx,
                    "forecast_period": period_idx  # 0 = current, 1-6 = future forecasts
                })
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Mock the _fetch_json method to return our mock response
        with patch.object(collector, '_fetch_json', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_malaysia_response
            
            # Call fetch_malaysia_data
            records = await collector.fetch_malaysia_data()
            
            # BUG CONDITION: Malaysia returns 2,520+ records (mixing current + forecasts)
            # EXPECTED BEHAVIOR AFTER FIX: Malaysia should return only ~284 records (current only)
            
            print(f"\n{'='*80}")
            print(f"COUNTEREXAMPLE FOUND - Malaysia Data Mixing Bug")
            print(f"{'='*80}")
            print(f"Total records returned: {len(records)}")
            print(f"Expected after fix: ~{num_locations} records (current observations only)")
            print(f"Current behavior: {len(records)} records (mixing current + forecasts)")
            print(f"{'='*80}\n")
            
            # Count unique locations
            unique_locations = set(record.location for record in records)
            print(f"Unique locations: {len(unique_locations)}")
            print(f"Records per location: {len(records) / len(unique_locations):.1f}")
            print(f"Expected records per location after fix: 1 (current observation only)")
            print(f"{'='*80}\n")
            
            # Show sample records for one location to demonstrate multiple time periods
            if records:
                sample_location = records[0].location
                sample_records = [r for r in records if r.location == sample_location]
                print(f"Sample location '{sample_location}' has {len(sample_records)} records:")
                for idx, record in enumerate(sample_records[:7]):  # Show first 7
                    print(f"  Period {idx}: {record.timestamp} - Temp: {record.temperature}°C")
                print(f"{'='*80}\n")
            
            # This assertion will FAIL on unfixed code (proving bug exists)
            # After fix, this will PASS (Malaysia returns only current observations)
            assert len(records) <= num_locations * 1.2, (
                f"Bug confirmed: Malaysia returns {len(records)} records, "
                f"expected ~{num_locations} records (current observations only). "
                f"The system is mixing current observations with forecast data "
                f"({len(records) / num_locations:.1f} records per location). "
                f"This creates data leakage risk where ML training could see future forecast data."
            )
            
            # Additional verification: Check that we only have 1 record per location
            records_per_location = {}
            for record in records:
                if record.location not in records_per_location:
                    records_per_location[record.location] = 0
                records_per_location[record.location] += 1
            
            # After fix, each location should have exactly 1 record (current observation)
            locations_with_multiple_records = [
                loc for loc, count in records_per_location.items() if count > 1
            ]
            
            assert len(locations_with_multiple_records) == 0, (
                f"Bug confirmed: {len(locations_with_multiple_records)} locations have "
                f"multiple records (forecast data mixed with current observations). "
                f"Expected: 1 record per location (current observation only). "
                f"Sample locations with multiple records: {locations_with_multiple_records[:5]}"
            )
    
    @pytest.mark.asyncio
    @given(
        num_locations=st.integers(min_value=50, max_value=300),
        num_forecast_periods=st.integers(min_value=5, max_value=10)
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_malaysia_forecast_mixing_property(
        self,
        num_locations: int,
        num_forecast_periods: int
    ):
        """
        Property-based test: Malaysia data mixing occurs for any number of locations
        and forecast periods.
        
        Property: For all Malaysia API responses with N locations and F forecast periods,
        the system should store only N records (current observations), not N × F records.
        
        This test generates many test cases to demonstrate the bug occurs consistently
        across different input variations.
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug is systematic)
        After fix: Test PASSES (only current observations are stored)
        """
        # Generate mock Malaysia API response with multiple forecast periods
        mock_response = []
        
        for location_idx in range(num_locations):
            location_name = f"Location_{location_idx}"
            latitude = 1.0 + (location_idx * 0.1)
            longitude = 100.0 + (location_idx * 0.1)
            
            # Create multiple forecast periods for this location
            for period_idx in range(num_forecast_periods):
                forecast_time = datetime.now() + timedelta(hours=period_idx * 3)
                
                mock_response.append({
                    "location": {
                        "location_name": location_name,
                        "latitude": latitude,
                        "longitude": longitude
                    },
                    "date": forecast_time.isoformat(),
                    "min_temp": 24.0 + period_idx,
                    "max_temp": 32.0 + period_idx
                })
        
        # Create DataCollector instance
        collector = DataCollector()
        
        # Parse the data directly (testing parsing logic)
        records = collector._parse_malaysia_data(mock_response)
        
        # BUG CONDITION PROPERTY: System stores N × F records instead of N records
        # EXPECTED BEHAVIOR AFTER FIX: System stores only N records (current observations)
        
        # This assertion will FAIL on unfixed code (proving bug exists)
        assert len(records) <= num_locations * 1.2, (
            f"Bug confirmed: Malaysia parser returns {len(records)} records for "
            f"{num_locations} locations with {num_forecast_periods} forecast periods. "
            f"Expected: ~{num_locations} records (current observations only). "
            f"Actual: {len(records)} records ({len(records) / num_locations:.1f} per location). "
            f"The parser is not filtering forecast data, creating data leakage risk."
        )
    
    @pytest.mark.asyncio
    async def test_malaysia_forecast_data_in_weather_data_table(self):
        """
        Test that Malaysia forecast data is being stored in weather_data table.
        
        Bug Condition: The weather_data table contains forecast data (multiple time
        periods per location) instead of only current observations.
        
        This creates two problems:
        1. Data leakage: ML training could see future forecast data
        2. No benchmark: Can't compare ML predictions against official forecasts
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug exists)
        After fix: Test PASSES (only current observations in weather_data)
        """
        # Create mock Malaysia API response with clear forecast periods
        mock_response = [
            # Location 1 - Current observation (period 0)
            {
                "location": {
                    "location_name": "Kuala Lumpur",
                    "latitude": 3.1390,
                    "longitude": 101.6869
                },
                "date": datetime.now().isoformat(),
                "min_temp": 24.0,
                "max_temp": 32.0,
                "forecast_period": 0  # Current
            },
            # Location 1 - Forecast period 1 (+3 hours)
            {
                "location": {
                    "location_name": "Kuala Lumpur",
                    "latitude": 3.1390,
                    "longitude": 101.6869
                },
                "date": (datetime.now() + timedelta(hours=3)).isoformat(),
                "min_temp": 25.0,
                "max_temp": 33.0,
                "forecast_period": 1  # Forecast
            },
            # Location 1 - Forecast period 2 (+6 hours)
            {
                "location": {
                    "location_name": "Kuala Lumpur",
                    "latitude": 3.1390,
                    "longitude": 101.6869
                },
                "date": (datetime.now() + timedelta(hours=6)).isoformat(),
                "min_temp": 26.0,
                "max_temp": 34.0,
                "forecast_period": 2  # Forecast
            }
        ]
        
        collector = DataCollector()
        records = collector._parse_malaysia_data(mock_response)
        
        # BUG CONDITION: All 3 records (current + 2 forecasts) are stored in weather_data
        # EXPECTED BEHAVIOR AFTER FIX: Only 1 record (current observation) is stored
        
        print(f"\n{'='*80}")
        print(f"COUNTEREXAMPLE - Forecast Data in weather_data Table")
        print(f"{'='*80}")
        print(f"Location: Kuala Lumpur")
        print(f"Records stored: {len(records)}")
        print(f"Expected after fix: 1 (current observation only)")
        print(f"\nRecords breakdown:")
        for idx, record in enumerate(records):
            print(f"  Record {idx + 1}: {record.timestamp} - Temp: {record.temperature}°C")
        print(f"{'='*80}\n")
        
        # This assertion will FAIL on unfixed code (proving bug exists)
        assert len(records) == 1, (
            f"Bug confirmed: weather_data table contains {len(records)} records for "
            f"Kuala Lumpur (mixing current observation with {len(records) - 1} forecast periods). "
            f"Expected: 1 record (current observation only). "
            f"This creates data leakage risk where ML training could see future forecast data."
        )
    
    @pytest.mark.asyncio
    async def test_compare_malaysia_vs_singapore_indonesia_record_counts(self):
        """
        Test that demonstrates the discrepancy between Malaysia and other countries.
        
        Bug Condition: Malaysia returns 2,520+ records while Singapore returns ~15
        and Indonesia returns ~30, despite all being current observation systems.
        
        This discrepancy reveals that Malaysia is mixing forecast data with current
        observations.
        
        EXPECTED OUTCOME: Test FAILS on unfixed code (proves bug exists)
        After fix: Test PASSES (all countries return similar record counts per location)
        """
        # Mock responses for all three countries
        
        # Singapore: 15 current observation records (1 per station)
        mock_singapore_response = {
            "code": 0,
            "data": {
                "stations": [
                    {
                        "id": f"S{i}",
                        "name": f"Station_{i}",
                        "location": {"latitude": 1.3 + i * 0.01, "longitude": 103.8 + i * 0.01}
                    }
                    for i in range(15)
                ],
                "readings": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": [
                            {"stationId": f"S{i}", "value": 28.0 + i}
                            for i in range(15)
                        ]
                    }
                ]
            }
        }
        
        # Malaysia: 284 locations × 7 forecast periods = 1,988 records
        num_malaysia_locations = 284
        num_forecast_periods = 7
        mock_malaysia_response = []
        
        for loc_idx in range(num_malaysia_locations):
            for period_idx in range(num_forecast_periods):
                mock_malaysia_response.append({
                    "location": {
                        "location_name": f"MY_Location_{loc_idx}",
                        "latitude": 3.0 + loc_idx * 0.01,
                        "longitude": 101.0 + loc_idx * 0.01
                    },
                    "date": (datetime.now() + timedelta(hours=period_idx * 3)).isoformat(),
                    "min_temp": 24.0,
                    "max_temp": 32.0
                })
        
        collector = DataCollector()
        
        # Parse Singapore data
        singapore_records = collector._parse_singapore_data(
            mock_singapore_response,
            mock_singapore_response,
            mock_singapore_response,
            mock_singapore_response,
            mock_singapore_response
        )
        
        # Parse Malaysia data
        malaysia_records = collector._parse_malaysia_data(mock_malaysia_response)
        
        # Calculate records per location
        singapore_locations = len(set(r.location for r in singapore_records))
        malaysia_locations = len(set(r.location for r in malaysia_records))
        
        singapore_records_per_location = len(singapore_records) / singapore_locations if singapore_locations > 0 else 0
        malaysia_records_per_location = len(malaysia_records) / malaysia_locations if malaysia_locations > 0 else 0
        
        print(f"\n{'='*80}")
        print(f"COUNTEREXAMPLE - Record Count Discrepancy")
        print(f"{'='*80}")
        print(f"Singapore:")
        print(f"  Total records: {len(singapore_records)}")
        print(f"  Unique locations: {singapore_locations}")
        print(f"  Records per location: {singapore_records_per_location:.1f}")
        print(f"\nMalaysia:")
        print(f"  Total records: {len(malaysia_records)}")
        print(f"  Unique locations: {malaysia_locations}")
        print(f"  Records per location: {malaysia_records_per_location:.1f}")
        print(f"\nExpected after fix:")
        print(f"  All countries should have ~1 record per location (current observation only)")
        print(f"{'='*80}\n")
        
        # This assertion will FAIL on unfixed code (proving bug exists)
        assert malaysia_records_per_location <= 1.5, (
            f"Bug confirmed: Malaysia has {malaysia_records_per_location:.1f} records per location, "
            f"while Singapore has {singapore_records_per_location:.1f} records per location. "
            f"Expected: ~1 record per location for all countries (current observations only). "
            f"Malaysia is mixing current observations with forecast data."
        )


if __name__ == "__main__":
    # Run the tests
    async def run_tests():
        test_suite = TestMalaysiaDataMixingExploration()
        
        print("Running Malaysia Data Mixing Bug Condition Exploration Tests...")
        print("=" * 80)
        print("IMPORTANT: These tests are EXPECTED TO FAIL on unfixed code")
        print("Failure confirms the bug exists (Malaysia mixing current + forecast data)")
        print("=" * 80)
        
        # Run main exploration test
        print("\n1. Main Exploration Test:")
        try:
            await test_suite.test_malaysia_returns_excessive_records_with_forecasts()
            print("❌ UNEXPECTED: Test passed (bug may not exist or already fixed)")
        except AssertionError as e:
            print(f"✓ EXPECTED: Test failed (bug confirmed)")
            print(f"   Error: {str(e)[:200]}...")
        
        # Run forecast data in weather_data table test
        print("\n2. Forecast Data in weather_data Table Test:")
        try:
            await test_suite.test_malaysia_forecast_data_in_weather_data_table()
            print("❌ UNEXPECTED: Test passed (bug may not exist or already fixed)")
        except AssertionError as e:
            print(f"✓ EXPECTED: Test failed (bug confirmed)")
            print(f"   Error: {str(e)[:200]}...")
        
        # Run comparison test
        print("\n3. Record Count Comparison Test:")
        try:
            await test_suite.test_compare_malaysia_vs_singapore_indonesia_record_counts()
            print("❌ UNEXPECTED: Test passed (bug may not exist or already fixed)")
        except AssertionError as e:
            print(f"✓ EXPECTED: Test failed (bug confirmed)")
            print(f"   Error: {str(e)[:200]}...")
        
        print("\n" + "=" * 80)
        print("Bug condition exploration complete")
        print("These tests will PASS after implementing the fix (filtering to current observations only)")
        print("=" * 80)
    
    asyncio.run(run_tests())
