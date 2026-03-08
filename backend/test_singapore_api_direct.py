"""
Direct test of Singapore API to see response structure
"""
import asyncio
import aiohttp
import json

async def test_singapore_api():
    print("=" * 60)
    print("TESTING SINGAPORE API DIRECTLY")
    print("=" * 60)
    
    base_url = "https://api-open.data.gov.sg"
    endpoint = "air-temperature"
    
    url = f"{base_url}/v2/real-time/api/{endpoint}"
    print(f"\nFetching: {url}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                print(f"Status: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                
                data = await response.json()
                
                print(f"\nResponse structure:")
                print(json.dumps(data, indent=2, default=str)[:2000])  # First 2000 chars
                
                # Check if data exists
                if "data" in data:
                    data_obj = data["data"]
                    print(f"\nData keys: {list(data_obj.keys())}")
                    
                    if "stations" in data_obj:
                        print(f"Number of stations: {len(data_obj['stations'])}")
                        if data_obj['stations']:
                            print(f"Sample station: {data_obj['stations'][0]}")
                    
                    if "readings" in data_obj:
                        print(f"Number of reading sets: {len(data_obj['readings'])}")
                        if data_obj['readings']:
                            readings = data_obj['readings'][0]
                            print(f"Reading timestamp: {readings.get('timestamp')}")
                            print(f"Number of data points: {len(readings.get('data', []))}")
                            if readings.get('data'):
                                print(f"Sample data point: {readings['data'][0]}")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_singapore_api())
