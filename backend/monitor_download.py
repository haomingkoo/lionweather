"""
Monitor NEA data download progress and report failures
"""

import os
from pathlib import Path
import pandas as pd
from datetime import datetime

def monitor_download():
    """Monitor download progress and report any issues"""
    
    data_dir = Path("nea_historical_data")
    
    if not data_dir.exists():
        print("❌ Download directory doesn't exist yet")
        return
    
    print("=" * 80)
    print("NEA DATA DOWNLOAD MONITOR")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Expected collections
    expected_collections = {
        "historical_air_temperature": "Historical Air Temperature",
        "historical_relative_humidity": "Historical Relative Humidity",
        "historical_rainfall": "Historical Rainfall",
        "historical_wind_speed": "Historical Wind Speed",
        "historical_wind_direction": "Historical Wind Direction",
        "historical_4day_weather_forecast": "Historical 4-day Weather Forecast",
        "historical_24hour_weather_forecast": "Historical 24-hour Weather Forecast",
        "air_pollutant__pm25": "Air Pollutant - PM2.5",
        "historical_1hr_pm25": "Historical 1-hr PM2.5",
        "air_pollutant__carbon_monoxide": "Air Pollutant - Carbon Monoxide",
    }
    
    total_files = 0
    total_rows = 0
    total_size_mb = 0
    failed_files = []
    empty_files = []
    small_files = []
    
    # Scan all collections
    for collection_dir in sorted(data_dir.iterdir()):
        if not collection_dir.is_dir():
            continue
        
        collection_name = collection_dir.name
        csv_files = list(collection_dir.glob("*.csv"))
        
        if not csv_files:
            print(f"⚠️  {collection_name}: NO FILES YET")
            continue
        
        print(f"📁 {collection_name}:")
        
        for csv_file in sorted(csv_files):
            try:
                # Check file size
                file_size = csv_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                
                # Read CSV to check rows
                df = pd.read_csv(csv_file)
                row_count = len(df)
                
                total_files += 1
                total_rows += row_count
                total_size_mb += file_size_mb
                
                # Flag potential issues
                status = "✓"
                if row_count == 0:
                    status = "❌ EMPTY"
                    empty_files.append(str(csv_file))
                elif row_count < 100:
                    status = "⚠️  SMALL"
                    small_files.append((str(csv_file), row_count))
                
                print(f"  {status} {csv_file.name}: {row_count:,} rows, {file_size_mb:.2f} MB")
                
            except Exception as e:
                print(f"  ❌ {csv_file.name}: FAILED TO READ - {str(e)}")
                failed_files.append((str(csv_file), str(e)))
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files downloaded: {total_files}")
    print(f"Total rows: {total_rows:,}")
    print(f"Total size: {total_size_mb:.2f} MB")
    print()
    
    # Report issues
    if failed_files:
        print("❌ FAILED FILES:")
        for file_path, error in failed_files:
            print(f"  - {file_path}")
            print(f"    Error: {error}")
        print()
    
    if empty_files:
        print("❌ EMPTY FILES (0 rows):")
        for file_path in empty_files:
            print(f"  - {file_path}")
        print()
    
    if small_files:
        print("⚠️  SUSPICIOUSLY SMALL FILES (<100 rows):")
        for file_path, row_count in small_files:
            print(f"  - {file_path}: {row_count} rows")
        print()
    
    if not failed_files and not empty_files:
        print("✅ All downloaded files look good!")
        print()
    
    # Check for missing collections
    found_collections = {d.name for d in data_dir.iterdir() if d.is_dir()}
    missing_collections = set(expected_collections.keys()) - found_collections
    
    if missing_collections:
        print("⏳ COLLECTIONS NOT YET DOWNLOADED:")
        for coll in sorted(missing_collections):
            print(f"  - {expected_collections[coll]}")
        print()
    
    print("=" * 80)
    print()
    print("To check again, run: ./venv/bin/python3 monitor_download.py")
    print("=" * 80)


if __name__ == "__main__":
    monitor_download()
