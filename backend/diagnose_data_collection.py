"""
Comprehensive diagnostic script for data collection issues
"""
import asyncio
import logging
from datetime import datetime, timedelta
from app.services.data_collector import DataCollector
from app.db.database import get_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_data_collection():
    """Test data collection from all sources"""
    print("\n" + "=" * 80)
    print("DIAGNOSING DATA COLLECTION ISSUES")
    print("=" * 80)
    
    collector = DataCollector()
    
    # Test Singapore
    print("\n1. TESTING SINGAPORE DATA COLLECTION")
    print("-" * 80)
    try:
        singapore_records = await collector.fetch_singapore_data()
        print(f"✓ Singapore: {len(singapore_records)} records")
        if singapore_records:
            sample = singapore_records[0]
            print(f"  Sample: {sample.location} - Temp: {sample.temperature}°C, "
                  f"Humidity: {sample.humidity}%, Wind: {sample.wind_speed} km/h, "
                  f"Pressure: {sample.pressure}")
        else:
            print("  ✗ NO RECORDS - Check logs above for API errors")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        logger.error("Singapore collection failed", exc_info=True)
    
    # Test Malaysia
    print("\n2. TESTING MALAYSIA DATA COLLECTION")
    print("-" * 80)
    try:
        malaysia_records = await collector.fetch_malaysia_data()
        print(f"✓ Malaysia: {len(malaysia_records)} records")
        if malaysia_records:
            sample = malaysia_records[0]
            print(f"  Sample: {sample.location} - Temp: {sample.temperature}°C, "
                  f"Humidity: {sample.humidity}%, Wind: {sample.wind_speed} km/h")
        else:
            print("  ✗ NO RECORDS - Check logs above for API errors")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        logger.error("Malaysia collection failed", exc_info=True)
    
    # Test Indonesia
    print("\n3. TESTING INDONESIA DATA COLLECTION")
    print("-" * 80)
    try:
        indonesia_records = await collector.fetch_indonesia_data()
        print(f"✓ Indonesia: {len(indonesia_records)} records")
        if indonesia_records:
            sample = indonesia_records[0]
            print(f"  Sample: {sample.location} - Temp: {sample.temperature}°C, "
                  f"Humidity: {sample.humidity}%, Wind: {sample.wind_speed} km/h, "
                  f"Pressure: {sample.pressure}")
        else:
            print("  ✗ NO RECORDS - Check logs above for API errors")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        logger.error("Indonesia collection failed", exc_info=True)
    
    # Test all sources combined
    print("\n4. TESTING COMBINED COLLECTION")
    print("-" * 80)
    try:
        all_records = await collector.collect_all_sources()
        print(f"✓ Total records from all sources: {len(all_records)}")
        
        # Count by country
        by_country = {}
        for record in all_records:
            by_country[record.country] = by_country.get(record.country, 0) + 1
        
        for country, count in by_country.items():
            print(f"  {country}: {count} records")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        logger.error("Combined collection failed", exc_info=True)

def check_database_status():
    """Check current database status"""
    print("\n" + "=" * 80)
    print("CHECKING DATABASE STATUS")
    print("=" * 80)
    
    engine = get_engine()
    with engine.connect() as db:
        try:
            from sqlalchemy import text
            # Check total records
            result = db.execute(text("SELECT COUNT(*) FROM weather_data"))
            total = result.scalar()
            print(f"\n1. Total records in database: {total}")
            
            # Check by country
            print("\n2. Records by country:")
            result = db.execute(text("""
                SELECT country, COUNT(*) as count 
                FROM weather_data 
                GROUP BY country 
                ORDER BY count DESC
            """))
            for row in result:
                print(f"   {row[0]}: {row[1]} records")
            
            # Check recent data (last 24 hours)
            print("\n3. Recent data (last 24 hours):")
            result = db.execute(text("""
                SELECT country, COUNT(*) as count 
                FROM weather_data 
                WHERE timestamp > datetime('now', '-24 hours')
                GROUP BY country 
                ORDER BY count DESC
            """))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"   {row[0]}: {row[1]} records")
            else:
                print("   ✗ NO RECENT DATA - Background polling may not be running")
            
            # Check latest timestamp by country
            print("\n4. Latest data timestamp by country:")
            result = db.execute(text("""
                SELECT country, MAX(timestamp) as latest 
                FROM weather_data 
                GROUP BY country 
                ORDER BY latest DESC
            """))
            for row in result:
                print(f"   {row[0]}: {row[1]}")
            
            # Check for missing variables
            print("\n5. Records with missing variables:")
            result = db.execute(text("""
                SELECT 
                    SUM(CASE WHEN humidity = 0 THEN 1 ELSE 0 END) as zero_humidity,
                    SUM(CASE WHEN wind_speed = 0 THEN 1 ELSE 0 END) as zero_wind,
                    SUM(CASE WHEN pressure IS NULL THEN 1 ELSE 0 END) as null_pressure
                FROM weather_data
            """))
            row = result.fetchone()
            print(f"   Zero humidity: {row[0]}")
            print(f"   Zero wind_speed: {row[1]}")
            print(f"   NULL pressure: {row[2]}")
            
        except Exception as e:
            print(f"✗ Database check failed: {e}")
            logger.error("Database check failed", exc_info=True)

async def main():
    """Run all diagnostics"""
    await test_data_collection()
    check_database_status()
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
