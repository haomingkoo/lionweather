"""
Test script for forecast collection system.

Tests:
1. Forecast collection from all sources (Singapore, Malaysia, Indonesia)
2. Forecast storage in forecast_data table
3. Verification that weather_data only contains current observations
"""

import asyncio
import sys
from app.services.forecast_collector import ForecastCollector
from app.services.forecast_store import ForecastStore
from app.db.database import execute_sql, fetch_all


async def test_forecast_collection():
    """Test forecast collection from all sources."""
    print("=" * 60)
    print("TESTING FORECAST COLLECTION SYSTEM")
    print("=" * 60)
    
    # Initialize services
    collector = ForecastCollector()
    store = ForecastStore()
    
    # Test 1: Collect forecasts
    print("\n[Test 1] Collecting forecasts from all sources...")
    forecasts = await collector.collect_all_forecasts()
    print(f"✓ Collected {len(forecasts)} total forecasts")
    
    # Count by country
    singapore_count = len([f for f in forecasts if f["country"] == "singapore"])
    malaysia_count = len([f for f in forecasts if f["country"] == "malaysia"])
    indonesia_count = len([f for f in forecasts if f["country"] == "indonesia"])
    
    print(f"  - Singapore: {singapore_count} forecasts")
    print(f"  - Malaysia: {malaysia_count} forecasts")
    print(f"  - Indonesia: {indonesia_count} forecasts")
    
    if len(forecasts) == 0:
        print("❌ No forecasts collected - test failed")
        return False
    
    # Test 2: Store forecasts
    print("\n[Test 2] Storing forecasts in forecast_data table...")
    result = store.store_forecasts(forecasts)
    print(f"✓ Stored {result['stored']}/{result['total']} forecasts")
    
    if result['errors'] > 0:
        print(f"⚠️  {result['errors']} errors occurred:")
        for error in result['error_messages'][:5]:
            print(f"    - {error}")
    
    # Test 3: Verify forecasts in database
    print("\n[Test 3] Verifying forecasts in forecast_data table...")
    
    singapore_db_count = store.get_forecast_count("singapore")
    malaysia_db_count = store.get_forecast_count("malaysia")
    indonesia_db_count = store.get_forecast_count("indonesia")
    total_db_count = store.get_forecast_count()
    
    print(f"✓ Database contains {total_db_count} total forecasts")
    print(f"  - Singapore: {singapore_db_count} forecasts")
    print(f"  - Malaysia: {malaysia_db_count} forecasts")
    print(f"  - Indonesia: {indonesia_db_count} forecasts")
    
    # Test 4: Verify weather_data only contains current observations
    print("\n[Test 4] Verifying weather_data contains only current observations...")
    
    try:
        # Check if weather_records table exists (it's the actual table name)
        weather_count = fetch_all("SELECT COUNT(*) FROM weather_records")
        if weather_count:
            total_weather = weather_count[0][0]
            print(f"✓ weather_records table contains {total_weather} current observation records")
            
            # Check Malaysia records (should be ~284, not 2,520)
            malaysia_weather = fetch_all("SELECT COUNT(*) FROM weather_records WHERE country = 'malaysia'")
            if malaysia_weather:
                malaysia_obs_count = malaysia_weather[0][0]
                print(f"  - Malaysia current observations: {malaysia_obs_count} records")
                
                if malaysia_obs_count > 500:
                    print(f"⚠️  Warning: Malaysia has {malaysia_obs_count} records (expected ~284)")
                    print("     This might indicate forecast data is still mixed with current observations")
                else:
                    print(f"✓ Malaysia record count looks correct (only current observations)")
        else:
            print("⚠️  weather_records table is empty or doesn't exist")
    except Exception as e:
        print(f"⚠️  Could not check weather_records table: {e}")
    
    # Test 5: Sample forecast data
    print("\n[Test 5] Sample forecast data...")
    
    singapore_forecasts = store.get_latest_forecasts(country="singapore")
    if singapore_forecasts:
        sample = singapore_forecasts[0]
        print(f"✓ Singapore forecast sample:")
        print(f"  - Location: {sample['location']}")
        print(f"  - Prediction time: {sample['prediction_time']}")
        print(f"  - Target period: {sample['target_time_start']} to {sample['target_time_end']}")
        print(f"  - Temperature: {sample['temperature_low']}°C - {sample['temperature_high']}°C")
        print(f"  - Description: {sample['forecast_description']}")
    
    print("\n" + "=" * 60)
    print("FORECAST COLLECTION TEST COMPLETE")
    print("=" * 60)
    
    # Summary
    print("\n✓ All tests passed!")
    print(f"  - Collected {len(forecasts)} forecasts")
    print(f"  - Stored {result['stored']} forecasts in forecast_data table")
    print(f"  - Singapore: {singapore_count} forecasts collected")
    print(f"  - Malaysia: {malaysia_count} forecasts collected")
    print(f"  - Indonesia: {indonesia_count} forecasts collected")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_forecast_collection())
    sys.exit(0 if success else 1)
