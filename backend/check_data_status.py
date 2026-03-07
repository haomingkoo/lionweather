#!/usr/bin/env python3
"""
Check current data collection status for LionWeather ML training.

This script provides a comprehensive overview of:
1. Total records collected
2. Records by country and location
3. Time range of collected data
4. Data completeness and quality
5. Readiness for ML training
"""

import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Database path
DB_PATH = os.getenv("DATABASE_PATH", "weather.db")


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def check_data_status():
    """Check comprehensive data collection status."""
    con = get_connection()
    cursor = con.cursor()
    
    print("=" * 80)
    print("LIONWEATHER DATA COLLECTION STATUS")
    print("=" * 80)
    print()
    
    # 1. Check if weather_records table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='weather_records'
    """)
    
    if not cursor.fetchone():
        print("❌ ERROR: weather_records table does not exist!")
        print("   The database schema may not be initialized.")
        con.close()
        return
    
    # 2. Total records
    cursor.execute("SELECT COUNT(*) FROM weather_records")
    total_records = cursor.fetchone()[0]
    
    print(f"📊 TOTAL RECORDS: {total_records:,}")
    print()
    
    if total_records == 0:
        print("⚠️  WARNING: No data collected yet!")
        print("   - Data collection runs every 10 minutes")
        print("   - Check backend logs for collection errors")
        print("   - Verify API endpoints are accessible")
        con.close()
        return
    
    # 3. Records by country
    cursor.execute("""
        SELECT country, COUNT(*) as count
        FROM weather_records
        GROUP BY country
        ORDER BY count DESC
    """)
    
    print("📍 RECORDS BY COUNTRY:")
    country_counts = {}
    for row in cursor.fetchall():
        country, count = row
        country_counts[country] = count
        print(f"   {country.capitalize():15} {count:6,} records")
    print()
    
    # 4. Records by location (top 10)
    cursor.execute("""
        SELECT country, location, COUNT(*) as count
        FROM weather_records
        GROUP BY country, location
        ORDER BY count DESC
        LIMIT 10
    """)
    
    print("🌍 TOP 10 LOCATIONS:")
    for row in cursor.fetchall():
        country, location, count = row
        print(f"   {country.capitalize():12} / {location:30} {count:5,} records")
    print()
    
    # 5. Time range
    cursor.execute("""
        SELECT 
            MIN(timestamp) as first_record,
            MAX(timestamp) as last_record
        FROM weather_records
    """)
    
    first_record, last_record = cursor.fetchone()
    
    if first_record and last_record:
        first_dt = datetime.fromisoformat(first_record)
        last_dt = datetime.fromisoformat(last_record)
        duration = last_dt - first_dt
        
        print("⏰ TIME RANGE:")
        print(f"   First record: {first_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Last record:  {last_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration:     {duration.days} days, {duration.seconds // 3600} hours")
        print()
        
        # 6. Recent activity (last 24 hours)
        cutoff_24h = datetime.now() - timedelta(hours=24)
        cursor.execute("""
            SELECT COUNT(*) FROM weather_records
            WHERE timestamp >= ?
        """, (cutoff_24h.isoformat(),))
        
        recent_count = cursor.fetchone()[0]
        print(f"📈 RECENT ACTIVITY (Last 24 hours): {recent_count:,} records")
        print()
        
        # 7. Data completeness check
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN temperature IS NOT NULL AND temperature != 0 THEN 1 ELSE 0 END) as has_temp,
                SUM(CASE WHEN humidity IS NOT NULL AND humidity != 0 THEN 1 ELSE 0 END) as has_humidity,
                SUM(CASE WHEN rainfall IS NOT NULL THEN 1 ELSE 0 END) as has_rainfall,
                SUM(CASE WHEN wind_speed IS NOT NULL AND wind_speed != 0 THEN 1 ELSE 0 END) as has_wind
            FROM weather_records
        """)
        
        total, has_temp, has_humidity, has_rainfall, has_wind = cursor.fetchone()
        
        print("✅ DATA COMPLETENESS:")
        print(f"   Temperature: {has_temp:6,} / {total:6,} ({has_temp/total*100:5.1f}%)")
        print(f"   Humidity:    {has_humidity:6,} / {total:6,} ({has_humidity/total*100:5.1f}%)")
        print(f"   Rainfall:    {has_rainfall:6,} / {total:6,} ({has_rainfall/total*100:5.1f}%)")
        print(f"   Wind Speed:  {has_wind:6,} / {total:6,} ({has_wind/total*100:5.1f}%)")
        print()
        
        # 8. ML Training Readiness Assessment
        print("🤖 ML TRAINING READINESS:")
        print()
        
        # Minimum requirements for training
        min_records_needed = 168  # 1 week of hourly data
        min_duration_hours = 24   # At least 24 hours of data
        
        duration_hours = duration.total_seconds() / 3600
        
        ready_for_training = True
        
        if total_records < min_records_needed:
            print(f"   ⚠️  Need more data: {total_records}/{min_records_needed} records")
            print(f"      ({min_records_needed - total_records} more needed)")
            ready_for_training = False
        else:
            print(f"   ✅ Sufficient records: {total_records:,} (minimum: {min_records_needed})")
        
        if duration_hours < min_duration_hours:
            print(f"   ⚠️  Need longer duration: {duration_hours:.1f}/{min_duration_hours} hours")
            print(f"      ({min_duration_hours - duration_hours:.1f} more hours needed)")
            ready_for_training = False
        else:
            print(f"   ✅ Sufficient duration: {duration_hours:.1f} hours (minimum: {min_duration_hours})")
        
        if has_temp / total < 0.8:
            print(f"   ⚠️  Temperature data incomplete: {has_temp/total*100:.1f}% (need 80%+)")
            ready_for_training = False
        else:
            print(f"   ✅ Temperature data complete: {has_temp/total*100:.1f}%")
        
        print()
        
        if ready_for_training:
            print("🎉 READY FOR ML TRAINING!")
            print("   You can start training models now.")
            print()
            print("   Next steps:")
            print("   1. Run: python -m app.ml.training_pipeline")
            print("   2. Or wait for scheduled training (Sundays at 2 AM)")
        else:
            print("⏳ NOT READY YET - Keep collecting data")
            print()
            print("   Estimated time to readiness:")
            if duration_hours < min_duration_hours:
                hours_needed = min_duration_hours - duration_hours
                print(f"   - {hours_needed:.1f} more hours of data collection")
            if total_records < min_records_needed:
                # Assuming 10-minute collection intervals
                collections_needed = (min_records_needed - total_records) / len(country_counts)
                minutes_needed = collections_needed * 10
                print(f"   - Approximately {minutes_needed/60:.1f} more hours")
        
        print()
        
        # 9. Data quality issues
        cursor.execute("""
            SELECT COUNT(*) FROM weather_records
            WHERE temperature < -50 OR temperature > 60
               OR humidity < 0 OR humidity > 100
               OR rainfall < 0
               OR wind_speed < 0
        """)
        
        invalid_count = cursor.fetchone()[0]
        
        if invalid_count > 0:
            print(f"⚠️  DATA QUALITY ISSUES: {invalid_count} records with invalid values")
            print("   (These will be filtered during training)")
        else:
            print("✅ DATA QUALITY: All records have valid values")
        
        print()
    
    con.close()
    
    print("=" * 80)
    print()


if __name__ == "__main__":
    try:
        check_data_status()
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
