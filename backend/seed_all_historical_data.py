"""
Master script to run all historical data seeding steps

This script runs:
1. seed_historical_data.py - Fetch historical weather data
2. seed_historical_forecasts.py - Create forecast-actual pairs
3. verify_historical_data.py - Verify data quality

Usage:
    python seed_all_historical_data.py [--months MONTHS]

Arguments:
    --months: Number of months of historical data to fetch (default: 12)
"""

import asyncio
import sys
import argparse
from seed_historical_data import HistoricalDataSeeder
from seed_historical_forecasts import HistoricalForecastSeeder
from verify_historical_data import HistoricalDataVerifier


async def main():
    """Run all seeding steps"""
    parser = argparse.ArgumentParser(description='Seed historical weather data')
    parser.add_argument('--months', type=int, default=12, 
                       help='Number of months of historical data to fetch')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("HISTORICAL DATA SEEDING - FULL PIPELINE")
    print("="*60)
    print(f"Fetching {args.months} months of historical data")
    print("="*60 + "\n")
    
    # Step 1: Seed historical weather data
    print("\n📥 STEP 1: Fetching historical weather data...")
    print("-" * 60)
    seeder = HistoricalDataSeeder(months_back=args.months)
    try:
        result1 = await seeder.seed_data()
        print(f"✓ Step 1 complete: {result1['total_records_inserted']} records inserted")
    except Exception as e:
        print(f"❌ Step 1 failed: {str(e)}")
        sys.exit(1)
    
    # Step 2: Seed historical forecast data
    print("\n🔮 STEP 2: Creating forecast-actual pairs...")
    print("-" * 60)
    forecast_seeder = HistoricalForecastSeeder()
    try:
        result2 = await forecast_seeder.seed_forecasts(months_back=args.months)
        if result2["success"]:
            print(f"✓ Step 2 complete: {result2['total_records_inserted']} forecast pairs inserted")
        else:
            print(f"❌ Step 2 failed: {result2.get('error', 'Unknown error')}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Step 2 failed: {str(e)}")
        sys.exit(1)
    
    # Step 3: Verify data quality
    print("\n✅ STEP 3: Verifying data quality...")
    print("-" * 60)
    verifier = HistoricalDataVerifier()
    try:
        result3 = verifier.verify_all()
        if result3["valid"]:
            print("✓ Step 3 complete: Data quality is GOOD")
        else:
            print("⚠️  Step 3 complete: Data quality issues detected (see details above)")
    except Exception as e:
        print(f"❌ Step 3 failed: {str(e)}")
        sys.exit(1)
    
    # Final summary
    print("\n" + "="*60)
    print("🎉 ALL STEPS COMPLETE!")
    print("="*60)
    print(f"Weather records: {result1['total_records_inserted']}")
    print(f"Forecast pairs: {result2['total_records_inserted']}")
    print(f"Data quality: {'GOOD' if result3['valid'] else 'ISSUES DETECTED'}")
    print(f"Date range: {result1['date_range']['start']} to {result1['date_range']['end']}")
    print("="*60)
    print("\n✓ Historical data is ready for ML model training!")
    print("\nNext steps:")
    print("  1. Review ML_TRAINING_PLAN.md for training guidelines")
    print("  2. Run train_initial_models.py to train ML models")
    print("  3. Evaluate model performance")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
