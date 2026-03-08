"""
Test Singapore data collection to diagnose why it returns 0 records
"""
import asyncio
import logging
from app.services.data_collector import DataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    print("=" * 60)
    print("TESTING SINGAPORE DATA COLLECTION")
    print("=" * 60)
    
    collector = DataCollector()
    
    print("\n1. Testing Singapore data collection...")
    records = await collector.fetch_singapore_data()
    
    print(f"\n2. Results:")
    print(f"   Total records: {len(records)}")
    
    if records:
        print(f"\n3. Sample record:")
        sample = records[0]
        print(f"   Location: {sample.location}")
        print(f"   Temperature: {sample.temperature}°C")
        print(f"   Humidity: {sample.humidity}%")
        print(f"   Rainfall: {sample.rainfall}mm")
        print(f"   Wind Speed: {sample.wind_speed} km/h")
        print(f"   Pressure: {sample.pressure}")
        print(f"   Timestamp: {sample.timestamp}")
    else:
        print("\n3. No records returned - check logs above for errors")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
