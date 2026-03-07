#!/usr/bin/env python3
"""
Test script to verify the Singapore API fix works with real API calls.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.data_collector import DataCollector


async def test_singapore_fix():
    """Test that Singapore data collection now works with real API."""
    
    print("=" * 80)
    print("TESTING SINGAPORE API FIX WITH REAL API")
    print("=" * 80)
    print()
    
    collector = DataCollector()
    
    print("🇸🇬 Fetching Singapore weather data...")
    records = await collector.fetch_singapore_data()
    
    print()
    print("=" * 80)
    print(f"RESULTS: Collected {len(records)} Singapore weather records")
    print("=" * 80)
    print()
    
    if len(records) == 0:
        print("❌ FAILED: No records collected!")
        return False
    
    print(f"✅ SUCCESS: Collected {len(records)} records")
    print()
    print("Sample records:")
    for i, record in enumerate(records[:5]):
        print(f"{i+1}. {record.location}")
        print(f"   Temperature: {record.temperature}°C")
        print(f"   Rainfall: {record.rainfall}mm")
        print(f"   Humidity: {record.humidity}%")
        print(f"   Wind Speed: {record.wind_speed} km/h")
        print(f"   Wind Direction: {record.wind_direction}°")
        print(f"   Coordinates: ({record.latitude}, {record.longitude})")
        print()
    
    # Verify all records have valid data
    for record in records:
        assert record.temperature > 0 or record.temperature < 0, f"Invalid temperature: {record.temperature}"
        assert record.location != "Unknown", f"Invalid location: {record.location}"
        assert record.latitude != 0.0, f"Invalid latitude: {record.latitude}"
        assert record.longitude != 0.0, f"Invalid longitude: {record.longitude}"
        assert record.country == "singapore"
        assert record.source_api == "api-open.data.gov.sg"
    
    print("✅ All records validated successfully!")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_singapore_fix())
    sys.exit(0 if result else 1)
