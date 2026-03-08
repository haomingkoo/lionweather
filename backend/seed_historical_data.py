"""
Historical Weather Data Seeding Script

This script fetches historical hourly weather data from Open-Meteo Historical API
and stores it in the database for ML model training.

CRITICAL: Only uses real data from Open-Meteo - NO mock/synthetic data generation.

API Documentation: https://open-meteo.com/en/docs/historical-weather-api
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
from app.db.database import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Singapore regions for neighborhood-level predictions
# Covers major areas to capture local weather variations (especially rainfall)
SINGAPORE_REGIONS = [
    {"name": "Central", "lat": 1.3521, "lon": 103.8198},  # CBD, Orchard, Marina Bay
    {"name": "North", "lat": 1.4382, "lon": 103.7891},    # Woodlands, Yishun, Sembawang
    {"name": "East", "lat": 1.3236, "lon": 103.9273},     # Changi, Bedok, Tampines
    {"name": "West", "lat": 1.3399, "lon": 103.7090},     # Jurong, Clementi, Tuas
    {"name": "Northeast", "lat": 1.3644, "lon": 103.8917}, # Ang Mo Kio, Serangoon, Hougang
]

# Legacy single location (for backward compatibility)
SINGAPORE_LAT = 1.3521
SINGAPORE_LON = 103.8198

# Open-Meteo Historical API endpoint
HISTORICAL_API_URL = "https://archive-api.open-meteo.com/v1/archive"


class HistoricalDataSeeder:
    """Fetches and stores historical weather data from Open-Meteo"""
    
    def __init__(self, months_back: int = 12, use_regions: bool = True):
        """
        Initialize the seeder.

        Args:
            months_back: Number of months of historical data to fetch (default: 12)
            use_regions: If True, fetch data for all Singapore regions. If False, use single central location.
        """
        self.months_back = months_back
        self.timeout_seconds = 30.0
        self.use_regions = use_regions
        
    async def fetch_historical_data(
        self, 
        start_date: str, 
        end_date: str,
        latitude: float = SINGAPORE_LAT,
        longitude: float = SINGAPORE_LON,
        location_name: str = "Singapore"
    ) -> Dict[str, Any]:
        """
        Fetch historical hourly weather data from Open-Meteo.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            location_name: Name of the location

        Returns:
            Dictionary containing hourly weather data
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "wind_direction_10m",
                "surface_pressure",
                "visibility",
                "weather_code"
            ]),
            "timezone": "Asia/Singapore"
        }

        logger.info(f"Fetching historical data for {location_name} ({latitude}, {longitude}) from {start_date} to {end_date}...")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
        ) as session:
            async with session.get(HISTORICAL_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                logger.info(f"✓ Fetched data for {len(data.get('hourly', {}).get('time', []))} hours")
                return data
    
    def validate_data_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate historical data quality.
        
        Checks for:
        - Data completeness (no large gaps)
        - Reasonable value ranges for Singapore
        - Timestamp correctness
        
        Args:
            data: Historical data from Open-Meteo
            
        Returns:
            Dictionary with validation results
        """
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        
        if not times or not temps:
            return {
                "valid": False,
                "error": "No data returned from API"
            }
        
        # Check for data completeness
        total_hours = len(times)
        missing_temps = sum(1 for t in temps if t is None)
        completeness = (total_hours - missing_temps) / total_hours * 100
        
        # Check temperature ranges (Singapore: typically 20-35°C)
        valid_temps = [t for t in temps if t is not None]
        if valid_temps:
            min_temp = min(valid_temps)
            max_temp = max(valid_temps)
            avg_temp = sum(valid_temps) / len(valid_temps)
            
            # Singapore temperature should be in reasonable range
            temp_range_valid = 18 <= min_temp <= 40 and 18 <= max_temp <= 40
        else:
            min_temp = max_temp = avg_temp = None
            temp_range_valid = False
        
        # Check for large time gaps
        gaps = []
        for i in range(1, len(times)):
            prev_time = datetime.fromisoformat(times[i-1])
            curr_time = datetime.fromisoformat(times[i])
            gap_hours = (curr_time - prev_time).total_seconds() / 3600
            if gap_hours > 1.5:  # More than 1.5 hours gap
                gaps.append({
                    "start": times[i-1],
                    "end": times[i],
                    "hours": gap_hours
                })
        
        validation_result = {
            "valid": completeness >= 95 and temp_range_valid and len(gaps) < 10,
            "total_hours": total_hours,
            "completeness_percent": round(completeness, 2),
            "temperature": {
                "min": round(min_temp, 1) if min_temp else None,
                "max": round(max_temp, 1) if max_temp else None,
                "avg": round(avg_temp, 1) if avg_temp else None,
                "range_valid": temp_range_valid
            },
            "gaps": gaps[:5],  # Show first 5 gaps
            "total_gaps": len(gaps)
        }
        
        return validation_result
    
    def store_historical_data(self, data: Dict[str, Any], location_name: str = "Singapore", latitude: float = SINGAPORE_LAT, longitude: float = SINGAPORE_LON) -> int:
        """
        Store historical data in the database.

        Args:
            data: Historical data from Open-Meteo
            location_name: Name of the location
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Number of records inserted
        """
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            logger.warning("No time data to store")
            return 0

        con = get_connection()
        cursor = con.cursor()

        inserted_count = 0
        skipped_count = 0

        for i in range(len(times)):
            try:
                timestamp = times[i]
                temperature = hourly.get("temperature_2m", [])[i]
                humidity = hourly.get("relative_humidity_2m", [])[i]
                precipitation = hourly.get("precipitation", [])[i]
                wind_speed = hourly.get("wind_speed_10m", [])[i]
                wind_direction = hourly.get("wind_direction_10m", [])[i]
                pressure = hourly.get("surface_pressure", [])[i]
                visibility = hourly.get("visibility", [])[i]
                weather_code = hourly.get("weather_code", [])[i]

                # Skip if critical data is missing
                if temperature is None or humidity is None:
                    skipped_count += 1
                    continue

                # Convert visibility from meters to km
                visibility_km = visibility / 1000 if visibility is not None else None

                # Insert into weather_records table
                cursor.execute("""
                    INSERT OR IGNORE INTO weather_records (
                        timestamp, country, location, latitude, longitude,
                        temperature, rainfall, humidity, wind_speed, wind_direction,
                        pressure, weather_code, source_api, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    "singapore",
                    f"{location_name} (Historical)",
                    latitude,
                    longitude,
                    temperature,
                    precipitation or 0.0,
                    humidity,
                    wind_speed or 0.0,
                    wind_direction,
                    pressure,
                    weather_code,
                    "open-meteo.com/historical",
                    datetime.now().isoformat()
                ))

                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logger.error(f"Error inserting record at {times[i]}: {str(e)}")
                continue

        con.commit()
        con.close()

        logger.info(f"✓ Inserted {inserted_count} records for {location_name}, skipped {skipped_count} duplicates")
        return inserted_count
    
    async def seed_data(self) -> Dict[str, Any]:
        """
        Main method to seed historical data.

        Returns:
            Dictionary with seeding results
        """
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30 * self.months_back)

        logger.info(f"🌱 Starting historical data seeding...")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Mode: {'Multi-region' if self.use_regions else 'Single location'}")
        logger.info(f"   Source: Open-Meteo Historical API")

        # Determine locations to fetch
        if self.use_regions:
            locations = SINGAPORE_REGIONS
            logger.info(f"   Locations: {len(locations)} Singapore regions")
        else:
            locations = [{"name": "Singapore", "lat": SINGAPORE_LAT, "lon": SINGAPORE_LON}]
            logger.info(f"   Location: Central Singapore ({SINGAPORE_LAT}, {SINGAPORE_LON})")

        # Fetch data in chunks (Open-Meteo has limits on date ranges)
        # Fetch 3 months at a time to avoid timeouts
        chunk_months = 3
        all_inserted = 0
        all_validations = []

        # Process each location
        for location in locations:
            location_name = location["name"]
            latitude = location["lat"]
            longitude = location["lon"]

            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {location_name} ({latitude}, {longitude})")
            logger.info(f"{'='*60}")

            location_inserted = 0
            current_start = start_date

            while current_start < end_date:
                current_end = min(
                    current_start + timedelta(days=30 * chunk_months),
                    end_date
                )

                try:
                    # Fetch data chunk
                    data = await self.fetch_historical_data(
                        current_start.isoformat(),
                        current_end.isoformat(),
                        latitude=latitude,
                        longitude=longitude,
                        location_name=location_name
                    )

                    # Validate data quality
                    validation = self.validate_data_quality(data)
                    all_validations.append({
                        "location": location_name,
                        "period": f"{current_start} to {current_end}",
                        "validation": validation
                    })

                    if not validation["valid"]:
                        logger.warning(
                            f"⚠️  Data quality issues for {location_name} {current_start} to {current_end}: "
                            f"{validation}"
                        )

                    # Store data
                    inserted = self.store_historical_data(
                        data,
                        location_name=location_name,
                        latitude=latitude,
                        longitude=longitude
                    )
                    location_inserted += inserted
                    all_inserted += inserted

                    logger.info(
                        f"✓ Chunk complete: {current_start} to {current_end} "
                        f"({inserted} records)"
                    )

                except Exception as e:
                    logger.error(
                        f"❌ Failed to process chunk {current_start} to {current_end} for {location_name}: "
                        f"{str(e)}"
                    )

                # Move to next chunk
                current_start = current_end + timedelta(days=1)

                # Small delay to be respectful to the API
                await asyncio.sleep(1)

            logger.info(f"✓ {location_name} complete: {location_inserted} records inserted")

        result = {
            "success": True,
            "total_records_inserted": all_inserted,
            "locations_processed": len(locations),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "validations": all_validations
        }

        logger.info(f"\n🎉 Historical data seeding complete!")
        logger.info(f"   Total records inserted: {all_inserted}")
        logger.info(f"   Locations processed: {len(locations)}")

        return result


async def main():
    """Main entry point for the seeding script"""
    # Fetch 36 months (3 years) of historical data for all Singapore regions
    # Set use_regions=True for neighborhood-level predictions
    # Set use_regions=False for single central location (legacy mode)
    seeder = HistoricalDataSeeder(months_back=36, use_regions=True)

    try:
        result = await seeder.seed_data()

        print("\n" + "="*60)
        print("HISTORICAL DATA SEEDING RESULTS")
        print("="*60)
        print(f"Total records inserted: {result['total_records_inserted']}")
        print(f"Locations processed: {result['locations_processed']}")
        print(f"Date range: {result['date_range']['start']} to {result['date_range']['end']}")
        print("\nData Quality Summary:")

        # Group validations by location
        by_location = {}
        for val in result['validations']:
            loc = val['location']
            if loc not in by_location:
                by_location[loc] = []
            by_location[loc].append(val)

        for location, vals in by_location.items():
            print(f"\n  {location}:")
            for val in vals:
                v = val['validation']
                print(f"    Period: {val['period']}")
                print(f"      Valid: {v['valid']}")
                print(f"      Completeness: {v['completeness_percent']}%")
                if v.get('temperature'):
                    print(f"      Temperature range: {v['temperature']['min']}°C to {v['temperature']['max']}°C")
                if v.get('total_gaps', 0) > 0:
                    print(f"      Time gaps: {v['total_gaps']}")
        print("="*60)

    except Exception as e:
        logger.error(f"❌ Seeding failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
