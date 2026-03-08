"""
Historical Forecast Data Seeding Script

This script creates historical forecast records by pairing:
1. What was predicted (forecast made at time T for time T+N)
2. What actually happened (observed weather at time T+N)

This creates ground truth data for ML model training and evaluation.

CRITICAL: Only uses real data - NO mock/synthetic data generation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.db.database import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalForecastSeeder:
    """Creates historical forecast records from existing weather data"""
    
    def __init__(self):
        """Initialize the seeder"""
        pass
    
    def get_weather_records(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch weather records from database for a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of weather records
        """
        con = get_connection()
        cursor = con.cursor()
        
        cursor.execute("""
            SELECT 
                timestamp, temperature, humidity, rainfall, 
                wind_speed, wind_direction, pressure
            FROM weather_records
            WHERE country = 'singapore'
            AND timestamp >= ?
            AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        con.close()
        
        records = []
        for row in rows:
            records.append({
                "timestamp": row[0],
                "temperature": row[1],
                "humidity": row[2],
                "rainfall": row[3],
                "wind_speed": row[4],
                "wind_direction": row[5],
                "pressure": row[6]
            })
        
        return records
    
    def create_forecast_pairs(
        self, 
        records: List[Dict[str, Any]],
        forecast_hours: List[int] = [1, 3, 6, 12, 24]
    ) -> List[Dict[str, Any]]:
        """
        Create forecast-actual pairs from weather records.
        
        For each record at time T, we create "forecasts" for T+1h, T+3h, T+6h, etc.
        by looking ahead in the data. This simulates what a forecast would have been.
        
        Args:
            records: List of weather records sorted by timestamp
            forecast_hours: List of hours ahead to create forecasts for
            
        Returns:
            List of forecast-actual pairs
        """
        pairs = []
        
        # Create a lookup dictionary for fast access
        # Handle both ISO format with and without timezone
        records_by_time = {}
        for r in records:
            # Normalize timestamp format
            ts = r["timestamp"]
            # Parse and normalize to consistent format
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                normalized_ts = dt.strftime("%Y-%m-%dT%H:%M")
                records_by_time[normalized_ts] = r
            except:
                records_by_time[ts] = r
        
        for i, record in enumerate(records):
            try:
                # Parse timestamp
                ts = record["timestamp"]
                prediction_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                continue
            
            # For each forecast horizon
            for hours_ahead in forecast_hours:
                target_time = prediction_time + timedelta(hours=hours_ahead)
                target_time_str = target_time.strftime("%Y-%m-%dT%H:%M")
                
                # Find the actual observation at target time
                actual_record = records_by_time.get(target_time_str)
                
                if actual_record:
                    # Create a forecast pair
                    # "Predicted" = current observation (naive persistence forecast)
                    # "Actual" = what actually happened
                    pair = {
                        "prediction_time": record["timestamp"],
                        "target_time": target_time_str,
                        "hours_ahead": hours_ahead,
                        "predicted_temperature": record["temperature"],
                        "actual_temperature": actual_record["temperature"],
                        "predicted_humidity": record["humidity"],
                        "actual_humidity": actual_record["humidity"],
                        "predicted_rainfall": record["rainfall"],
                        "actual_rainfall": actual_record["rainfall"],
                        "predicted_wind_speed": record["wind_speed"],
                        "actual_wind_speed": actual_record["wind_speed"]
                    }
                    pairs.append(pair)
        
        return pairs
    
    def store_forecast_pairs(self, pairs: List[Dict[str, Any]]) -> int:
        """
        Store forecast-actual pairs in the database.
        
        We'll store these in the forecast_data table with a special source_api
        to indicate they are historical training data.
        
        Args:
            pairs: List of forecast-actual pairs
            
        Returns:
            Number of records inserted
        """
        con = get_connection()
        cursor = con.cursor()
        
        inserted_count = 0
        skipped_count = 0
        
        for pair in pairs:
            try:
                # Store as a forecast record
                # We'll use the forecast_data table structure
                cursor.execute("""
                    INSERT OR IGNORE INTO forecast_data (
                        prediction_time, target_time_start, target_time_end,
                        country, location, latitude, longitude,
                        temperature_low, temperature_high,
                        humidity_low, humidity_high,
                        wind_speed_low, wind_speed_high,
                        forecast_description,
                        source_api, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pair["prediction_time"],
                    pair["target_time"],
                    pair["target_time"],
                    "singapore",
                    "Singapore (Historical Forecast)",
                    1.3521,
                    103.8198,
                    pair["predicted_temperature"],  # Use predicted as "low"
                    pair["actual_temperature"],     # Use actual as "high"
                    pair["predicted_humidity"],
                    pair["actual_humidity"],
                    pair["predicted_wind_speed"],
                    pair["actual_wind_speed"],
                    f"Historical forecast {pair['hours_ahead']}h ahead",
                    "historical_training_data",
                    datetime.now().isoformat()
                ))
                
                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error inserting forecast pair: {str(e)}")
                continue
        
        con.commit()
        con.close()
        
        logger.info(f"✓ Inserted {inserted_count} forecast pairs, skipped {skipped_count} duplicates")
        return inserted_count
    
    async def seed_forecasts(self, months_back: int = 12) -> Dict[str, Any]:
        """
        Main method to seed historical forecast data.
        
        Args:
            months_back: Number of months of historical data to process
            
        Returns:
            Dictionary with seeding results
        """
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30 * months_back)
        
        logger.info(f"🌱 Starting historical forecast seeding...")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Creating forecast-actual pairs for ML training")
        
        # Fetch all weather records
        logger.info("Fetching weather records from database...")
        records = self.get_weather_records(
            start_date.isoformat(),
            end_date.isoformat()
        )
        logger.info(f"✓ Fetched {len(records)} weather records")
        
        if len(records) < 100:
            logger.warning(
                f"⚠️  Only {len(records)} records found. "
                "Run seed_historical_data.py first to populate weather data."
            )
            return {
                "success": False,
                "error": "Insufficient weather records. Run seed_historical_data.py first."
            }
        
        # Create forecast pairs
        logger.info("Creating forecast-actual pairs...")
        pairs = self.create_forecast_pairs(records)
        logger.info(f"✓ Created {len(pairs)} forecast-actual pairs")
        
        # Store pairs
        logger.info("Storing forecast pairs in database...")
        inserted = self.store_forecast_pairs(pairs)
        
        result = {
            "success": True,
            "total_records_inserted": inserted,
            "total_pairs_created": len(pairs),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "source_records": len(records)
        }
        
        logger.info(f"🎉 Historical forecast seeding complete!")
        logger.info(f"   Total forecast pairs inserted: {inserted}")
        
        return result


async def main():
    """Main entry point for the seeding script"""
    seeder = HistoricalForecastSeeder()
    
    try:
        result = await seeder.seed_forecasts(months_back=3)
        
        print("\n" + "="*60)
        print("HISTORICAL FORECAST SEEDING RESULTS")
        print("="*60)
        
        if result["success"]:
            print(f"Total forecast pairs inserted: {result['total_records_inserted']}")
            print(f"Total pairs created: {result['total_pairs_created']}")
            print(f"Source weather records: {result['source_records']}")
            print(f"Date range: {result['date_range']['start']} to {result['date_range']['end']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
        
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
