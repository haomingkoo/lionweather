#!/usr/bin/env python3
"""
Test script to see the full structure of Singapore API response.
"""

import asyncio
import aiohttp
import json


async def test_singapore_api_structure():
    """Test to see the full structure of Singapore API response."""
    
    base_url = "https://api-open.data.gov.sg"
    endpoint = "air-temperature"
    url = f"{base_url}/v2/real-time/api/{endpoint}"
    
    print("=" * 80)
    print(f"TESTING: {url}")
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
                
                # Print full response with nice formatting
                print(json.dumps(data, indent=2))
            else:
                print(f"Error: {response.status}")
                print(await response.text())


if __name__ == "__main__":
    asyncio.run(test_singapore_api_structure())
