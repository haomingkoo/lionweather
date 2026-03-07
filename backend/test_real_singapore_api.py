#!/usr/bin/env python3
"""
Test script to call the real Singapore API and see what it returns.
This will help us understand why Singapore data collection returns 0 records.
"""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_real_singapore_api():
    """Test the real Singapore API endpoints to see actual response format."""
    
    base_url = "https://api-open.data.gov.sg"
    endpoints = [
        "air-temperature",
        "rainfall",
        "relative-humidity",
        "wind-speed",
        "wind-direction"
    ]
    
    print("=" * 80)
    print("TESTING REAL SINGAPORE API")
    print("=" * 80)
    print()
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0)) as session:
        for endpoint in endpoints:
            url = f"{base_url}/v2/real-time/api/{endpoint}"
            print(f"📡 Testing endpoint: {endpoint}")
            print(f"   URL: {url}")
            
            try:
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "weather-ml-forecasting/1.0 (educational project)",
                }
                
                async with session.get(url, headers=headers) as response:
                    print(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Print response structure
                        print(f"   Response type: {type(data).__name__}")
                        
                        if isinstance(data, dict):
                            print(f"   Top-level keys: {list(data.keys())}")
                            
                            # Check for 'data' key
                            if 'data' in data:
                                data_obj = data['data']
                                print(f"   data type: {type(data_obj).__name__}")
                                print(f"   data keys: {list(data_obj.keys()) if isinstance(data_obj, dict) else 'N/A'}")
                                
                                # Check for 'records' key
                                if isinstance(data_obj, dict) and 'records' in data_obj:
                                    records = data_obj['records']
                                    print(f"   records type: {type(records).__name__}")
                                    print(f"   records count: {len(records) if isinstance(records, list) else 'N/A'}")
                                    
                                    if isinstance(records, list) and len(records) > 0:
                                        first_record = records[0]
                                        print(f"   first record keys: {list(first_record.keys()) if isinstance(first_record, dict) else 'N/A'}")
                                        
                                        # Check for 'item' key
                                        if isinstance(first_record, dict) and 'item' in first_record:
                                            item = first_record['item']
                                            print(f"   item keys: {list(item.keys()) if isinstance(item, dict) else 'N/A'}")
                                            
                                            # Check for 'readings' key
                                            if isinstance(item, dict) and 'readings' in item:
                                                readings = item['readings']
                                                print(f"   readings count: {len(readings) if isinstance(readings, list) else 'N/A'}")
                                                
                                                if isinstance(readings, list) and len(readings) > 0:
                                                    print(f"   ✅ Found {len(readings)} readings!")
                                                    # Print first reading
                                                    first_reading = readings[0]
                                                    print(f"   First reading: {json.dumps(first_reading, indent=6)}")
                                                else:
                                                    print(f"   ❌ readings is empty or not a list!")
                                            else:
                                                print(f"   ❌ No 'readings' key in item!")
                                        else:
                                            print(f"   ❌ No 'item' key in first record!")
                                    else:
                                        print(f"   ❌ records is empty or not a list!")
                                else:
                                    print(f"   ❌ No 'records' key in data!")
                            else:
                                print(f"   ❌ No 'data' key in response!")
                            
                            # Print full response for debugging (first 500 chars)
                            print(f"   Full response (first 500 chars):")
                            print(f"   {json.dumps(data, indent=2)[:500]}")
                        
                        print()
                    else:
                        error_text = await response.text()
                        print(f"   ❌ Error: {error_text[:200]}")
                        print()
                        
            except Exception as e:
                print(f"   ❌ Exception: {str(e)}")
                print()
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_real_singapore_api())
