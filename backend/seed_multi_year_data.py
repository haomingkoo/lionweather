"""
Seed 2-3 years of historical weather data (2022-2025) for comprehensive analysis.

This script fetches historical data from Open-Meteo for the years 2022, 2023, 2024,
and partial 2025 to enable robust time series analysis and ML model training.
"""

import sqlite3
import logging
from datetime import datetime
import urllib.request
import urllib.parse
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SINGAPORE_LAT = 1.3521
SINGAPORE_LON = 103.8198
HISTORICAL_API_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_year_data(year):
    """Fetch one year of historical data"""
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31" if year < 2025 else "2025-03-08"
    
    params = {
        "latitude": str(SINGAPORE_LAT),
        "longitude": str(SINGAPORE_LON),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_direction_10m",
            "surface_pressure",
            "weather_code"
        ]),
        "timezone": "Asia/Singapore"
    }
    
    logger.info(f"Fetching {year} data...")
    
    try:
        url = HISTORICAL_API_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=60) as response:
            data = json.loads(response.read().decode())
            logger.info(f"✓ Fetched {year}: {len(data.get('hourly', {}).get('time', []))} hours")
            return year, data
    except Exception as e:
        logger.error(f"✗ Failed to fetch {year}: {e}")
        return year, None


def store_data(year, data):
    """Store data in database"""
    if not data:
        return 0
    
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    
    if not times:
        return 0
    
    conn = sqlite3.connect("app/db/weather.db")
    cursor = conn.cursor()
    
    inserted = 0
    for i in range(len(times)):
        try:
            timestamp = times[i]
            temperature = hourly.get("temperature_2m", [])[i]
            humidity = hourly.get("relative_humidity_2m", [])[i]
            precipitation = hourly.get("precipitation", [])[i]
            wind_speed = hourly.get("wind_speed_10m", [])[i]
            wind_direction = hourly.get("wind_direction_10m", [])[i]
            pressure = hourly.get("surface_pressure", [])[i]
            
            if temperature is None or humidity is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO weather_records (
                    timestamp, country, location, latitude, longitude,
                    temperature, rainfall, humidity, wind_speed, wind_direction,
                    pressure, source_api, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                "singapore",
                "Singapore (Historical)",
                SINGAPORE_LAT,
                SINGAPORE_LON,
                temperature,
                precipitation or 0.0,
                humidity,
                wind_speed or 0.0,
                wind_direction,
                pressure,
                "open-meteo.com/historical",
                datetime.now().isoformat()
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
                
        except Exception as e:
            logger.error(f"Error inserting record: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"✓ Stored {inserted} records for {year}")
    return inserted


def main():
    """Seed 2022-2025 historical data"""
    logger.info("="*60)
    logger.info("SEEDING MULTI-YEAR HISTORICAL DATA (2022-2025)")
    logger.info("="*60)
    
    years = [2022, 2023, 2024, 2025]
    total_inserted = 0
    
    # Fetch and store each year
    for year in years:
        year_num, data = fetch_year_data(year)
        if data:
            inserted = store_data(year_num, data)
            total_inserted += inserted
            time.sleep(2)  # Be respectful to API
    
    logger.info("="*60)
    logger.info(f"COMPLETE: {total_inserted} total records inserted")
    logger.info("="*60)


if __name__ == "__main__":
    main()
