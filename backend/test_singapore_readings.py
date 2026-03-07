#!/usr/bin/env python3
"""
Test script to examine the readings structure from Singapore API.
"""

import asyncio
import aiohttp
import json


async def test_readings_structure():
    """Examine the actual readings structure."""
    
    base_url = "https://api-open.data.gov.sg"
    url = f"{base_url}/v2/real-time/api/air-temperature"
    
    print("=" * 80)
    print("EXAMINING SINGAPORE API READINGS STRUCTURE")
    print("=" * 80)
    print()
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0)) as session:
        headers = {
            "Accept": "application/json",
            "User-Agent": "weather-ml-forecasting/1.0 (educational project)",
        }
        
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                
                print("Full API Response Structure:")
                print(json.dumps(data, indent=2))
                print()
                
                # Analyze structure
                print("=" * 80)
                print("STRUCTURE ANALYSIS:")
                print("=" * 80)
                print()
                
                if 'data' in data:
                    data_obj = data['data']
                    
                    # Stations
                    if 'stations' in data_obj:
                        stations = data_obj['stations']
                        print(f"✅ Found {len(stations)} stations")
                        if stations:
                            print(f"   First station: {json.dumps(stations[0], indent=2)}")
                        print()
                    
                    # Readings
                    if 'readings' in data_obj:
                        readings = data_obj['readings']
                        print(f"✅ Found {len(readings)} readings")
                        if readings:
                            print(f"   First reading: {json.dumps(readings[0], indent=2)}")
                        print()
                    
                    # Reading type and unit
                    print(f"Reading Type: {data_obj.get('readingType')}")
                    print(f"Reading Unit: {data_obj.get('readingUnit')}")
                    print()


if __name__ == "__main__":
    asyncio.run(test_readings_structure())
