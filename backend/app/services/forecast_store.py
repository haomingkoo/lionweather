"""
Forecast Store Service

Stores official weather forecasts in the forecast_data table.
Handles background polling for forecast collection (separate from current observations).

Phase 2 of the two-system architecture:
- System 1: Current observations (weather_data table) - 10-minute polling
- System 2: Official forecasts (forecast_data table) - hourly polling
"""

import logging
from datetime import datetime
from typing import Dict, List
from app.db.database import get_connection, get_database_url

logger = logging.getLogger(__name__)


class ForecastStore:
    """Stores official weather forecasts in the database."""
    
    def __init__(self):
        """Initialize ForecastStore."""
        pass
    
    def store_forecast(self, forecast: Dict) -> int:
        """
        Store a single forecast in the forecast_data table.
        
        Uses UPSERT logic (INSERT OR REPLACE) to handle duplicates.
        Duplicates are identified by: prediction_time, target_time_start, 
        target_time_end, country, location.
        
        Args:
            forecast: Forecast dictionary with required fields
            
        Returns:
            Forecast ID (row ID)
        """
        con = get_connection()
        cursor = con.cursor()
        
        try:
            # Get current timestamp
            created_at = datetime.now().isoformat()

            is_postgres = get_database_url().startswith("postgresql")
            values = (
                forecast.get("prediction_time"),
                forecast.get("target_time_start"),
                forecast.get("target_time_end"),
                forecast.get("country"),
                forecast.get("location"),
                forecast.get("latitude"),
                forecast.get("longitude"),
                forecast.get("temperature_low"),
                forecast.get("temperature_high"),
                forecast.get("humidity_low"),
                forecast.get("humidity_high"),
                forecast.get("wind_speed_low"),
                forecast.get("wind_speed_high"),
                forecast.get("wind_direction"),
                forecast.get("forecast_description"),
                forecast.get("source_api"),
                created_at,
            )

            if is_postgres:
                ph = "%s"
                upsert_sql = f"""
                    INSERT INTO forecast_data (
                        prediction_time, target_time_start, target_time_end,
                        country, location, latitude, longitude,
                        temperature_low, temperature_high,
                        humidity_low, humidity_high,
                        wind_speed_low, wind_speed_high,
                        wind_direction, forecast_description, source_api, created_at
                    ) VALUES ({", ".join([ph] * 17)})
                    ON CONFLICT (prediction_time, target_time_start, target_time_end, country, location)
                    DO UPDATE SET
                        temperature_low      = EXCLUDED.temperature_low,
                        temperature_high     = EXCLUDED.temperature_high,
                        humidity_low         = EXCLUDED.humidity_low,
                        humidity_high        = EXCLUDED.humidity_high,
                        wind_speed_low       = EXCLUDED.wind_speed_low,
                        wind_speed_high      = EXCLUDED.wind_speed_high,
                        wind_direction       = EXCLUDED.wind_direction,
                        forecast_description = EXCLUDED.forecast_description,
                        source_api           = EXCLUDED.source_api,
                        created_at           = EXCLUDED.created_at
                """
            else:
                ph = "?"
                upsert_sql = f"""
                    INSERT OR REPLACE INTO forecast_data (
                        prediction_time, target_time_start, target_time_end,
                        country, location, latitude, longitude,
                        temperature_low, temperature_high,
                        humidity_low, humidity_high,
                        wind_speed_low, wind_speed_high,
                        wind_direction, forecast_description, source_api, created_at
                    ) VALUES ({", ".join([ph] * 17)})
                """

            cursor.execute(upsert_sql, values)
            
            forecast_id = cursor.lastrowid
            con.commit()
            
            return forecast_id
            
        except Exception as e:
            logger.error(f"Failed to store forecast: {e}")
            con.rollback()
            raise
        finally:
            con.close()
    
    def store_forecasts(self, forecasts: List[Dict]) -> Dict[str, int]:
        """
        Store multiple forecasts in the forecast_data table.
        
        Args:
            forecasts: List of forecast dictionaries
            
        Returns:
            Dictionary with storage statistics
        """
        stored_count = 0
        error_count = 0
        errors = []
        
        for forecast in forecasts:
            try:
                self.store_forecast(forecast)
                stored_count += 1
            except Exception as e:
                error_count += 1
                errors.append(str(e))
                logger.error(f"Failed to store forecast: {e}")
        
        result = {
            "total": len(forecasts),
            "stored": stored_count,
            "errors": error_count,
            "error_messages": errors[:10]  # First 10 errors only
        }
        
        logger.info(f"Stored {stored_count}/{len(forecasts)} forecasts")
        
        return result
    
    def get_latest_forecasts(self, country: str = None, location: str = None) -> List[Dict]:
        """
        Get latest forecasts from the database.
        
        Args:
            country: Filter by country (optional)
            location: Filter by location (optional)
            
        Returns:
            List of forecast dictionaries
        """
        con = get_connection()
        cursor = con.cursor()
        
        try:
            query = """
                SELECT 
                    id,
                    prediction_time,
                    target_time_start,
                    target_time_end,
                    country,
                    location,
                    latitude,
                    longitude,
                    temperature_low,
                    temperature_high,
                    humidity_low,
                    humidity_high,
                    wind_speed_low,
                    wind_speed_high,
                    wind_direction,
                    forecast_description,
                    source_api,
                    created_at
                FROM forecast_data
                WHERE 1=1
            """
            
            params = []
            
            if country:
                query += " AND country = ?"
                params.append(country)
            
            if location:
                query += " AND location = ?"
                params.append(location)
            
            query += " ORDER BY prediction_time DESC, target_time_start ASC LIMIT 100"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            forecasts = []
            for row in rows:
                forecast = {
                    "id": row[0],
                    "prediction_time": row[1],
                    "target_time_start": row[2],
                    "target_time_end": row[3],
                    "country": row[4],
                    "location": row[5],
                    "latitude": row[6],
                    "longitude": row[7],
                    "temperature_low": row[8],
                    "temperature_high": row[9],
                    "humidity_low": row[10],
                    "humidity_high": row[11],
                    "wind_speed_low": row[12],
                    "wind_speed_high": row[13],
                    "wind_direction": row[14],
                    "forecast_description": row[15],
                    "source_api": row[16],
                    "created_at": row[17]
                }
                forecasts.append(forecast)
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Failed to get forecasts: {e}")
            return []
        finally:
            con.close()
    
    def get_forecast_count(self, country: str = None) -> int:
        """
        Get count of forecasts in the database.
        
        Args:
            country: Filter by country (optional)
            
        Returns:
            Number of forecasts
        """
        con = get_connection()
        cursor = con.cursor()
        
        try:
            if country:
                cursor.execute(
                    "SELECT COUNT(*) FROM forecast_data WHERE country = ?",
                    (country,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM forecast_data")
            
            result = cursor.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Failed to get forecast count: {e}")
            return 0
        finally:
            con.close()
