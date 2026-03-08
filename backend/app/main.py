import os
import logging
import asyncio
import sys

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env file
load_dotenv()

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

from app.routers.locations import router as locations_router
from app.routers.rainfall import router as rainfall_router
from app.routers.comprehensive_weather import router as weather_router
from app.routers.weather import router as simple_weather_router
from app.routers.forecasts import router as forecasts_router
from app.routers.environmental import router as environmental_router
from app.routers.ml_forecast import router as ml_router
from app.routers.weather_data import router as weather_data_router
from app.routers.performance import router as performance_router
from app.routers.ml import router as ml_api_router
from app.routers.radar import router as radar_router
from app.routers.regional import router as regional_router
from app.routers.data_health import router as data_health_router
from app.routers.historical_data import router as historical_data_router
from app.routers.ml_predictions import router as ml_predictions_router
from app.routers.ml_models import router as ml_models_router
from app.db.migrations import migrate_ml_tables, migrate_forecast_tables
from app.db.database import execute_sql, get_database_url
from app.services.radar_service import get_radar_service


def init_db():
    """Initialize database tables (works with both SQLite and PostgreSQL)"""
    logger.info(f"Initializing database: {get_database_url()}")
    
    # Use SERIAL for PostgreSQL, INTEGER PRIMARY KEY AUTOINCREMENT for SQLite
    # SQLAlchemy handles this automatically
    database_url = get_database_url()
    is_postgres = database_url.startswith("postgresql")
    
    # Auto-increment syntax differs between SQLite and PostgreSQL
    if is_postgres:
        id_column = "id SERIAL PRIMARY KEY"
    else:
        id_column = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    execute_sql(f"""
        CREATE TABLE IF NOT EXISTS locations (
            {id_column},
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at TEXT NOT NULL,
            weather_condition TEXT,
            weather_observed_at TEXT,
            weather_source TEXT,
            weather_area TEXT,
            weather_valid_period_text TEXT,
            weather_refreshed_at TEXT,
            UNIQUE(latitude, longitude)
        )
    """)
    
    # Performance tracking table
    execute_sql(f"""
        CREATE TABLE IF NOT EXISTS forecast_performance (
            {id_column},
            location_id INTEGER NOT NULL,
            prediction_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            
            ml_temperature REAL,
            ml_condition TEXT,
            ml_rain_probability REAL,
            ml_confidence REAL,
            
            official_temperature REAL,
            official_condition TEXT,
            official_source TEXT,
            
            actual_temperature REAL,
            actual_condition TEXT,
            actual_rainfall REAL,
            actual_recorded_at TEXT,
            
            ml_temp_error REAL,
            official_temp_error REAL,
            ml_condition_correct INTEGER,
            official_condition_correct INTEGER,
            ml_wins INTEGER DEFAULT 0
        )
    """)
    
    # Model training data table
    execute_sql(f"""
        CREATE TABLE IF NOT EXISTS sensor_history (
            {id_column},
            timestamp TEXT NOT NULL,
            temperature_mean REAL,
            temperature_std REAL,
            humidity_mean REAL,
            humidity_std REAL,
            rainfall_total REAL,
            wind_speed_mean REAL,
            wind_direction_mean REAL,
            pm25_mean REAL,
            psi_mean REAL,
            uv_index REAL,
            hour INTEGER,
            day_of_week INTEGER,
            month INTEGER,
            UNIQUE(timestamp)
        )
    """)
    
    # Benchmark summary table
    execute_sql(f"""
        CREATE TABLE IF NOT EXISTS model_benchmarks (
            {id_column},
            date TEXT NOT NULL,
            model_version TEXT NOT NULL,
            total_predictions INTEGER,
            ml_avg_mae REAL,
            official_avg_mae REAL,
            ml_win_rate REAL,
            ml_condition_accuracy REAL,
            official_condition_accuracy REAL,
            improvement_pct REAL,
            UNIQUE(date, model_version)
        )
    """)
    
    logger.info("Database tables initialized successfully")


init_db()

# Run ML table migrations
migrate_ml_tables()

# Run forecast table migrations
migrate_forecast_tables()

app = FastAPI(
    title="LionWeather API",
    description="AI-powered weather forecasting for Singapore, Malaysia, and Indonesia",
    version="1.0.0",
)

app.include_router(locations_router, prefix="/api")
app.include_router(rainfall_router, prefix="/api")
app.include_router(weather_router, prefix="/api")
app.include_router(simple_weather_router)
app.include_router(forecasts_router, prefix="/api")
app.include_router(environmental_router, prefix="/api")
app.include_router(ml_router, prefix="/api")
app.include_router(weather_data_router, prefix="/api")
app.include_router(performance_router, prefix="/api")
app.include_router(ml_api_router)
app.include_router(radar_router, prefix="/api")
app.include_router(regional_router, prefix="/api")
app.include_router(data_health_router)
app.include_router(historical_data_router)
app.include_router(ml_predictions_router)
app.include_router(ml_models_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/status")
def status_check():
    """Detailed status check including background tasks and database"""
    import os
    from datetime import datetime, timedelta
    db_path = os.getenv("DATABASE_PATH", "weather.db")
    db_exists = os.path.exists(db_path)
    
    # Get database stats if it exists
    db_stats = {}
    if db_exists:
        try:
            from app.db.database import execute_sql
            
            # Check weather_records table
            try:
                from app.db.database import fetch_one, fetch_all
                
                result = fetch_one("SELECT COUNT(*) as count FROM weather_records")
                db_stats["weather_records_total"] = result[0] if result else 0
                
                # Get counts by country
                country_results = fetch_all("SELECT country, COUNT(*) as count FROM weather_records GROUP BY country")
                db_stats["by_country"] = {row[0]: row[1] for row in country_results} if country_results else {}
                
                # Get recent activity (last hour)
                cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
                result = fetch_one(
                    "SELECT COUNT(*) as count FROM weather_records WHERE timestamp >= :cutoff",
                    {"cutoff": cutoff}
                )
                db_stats["weather_records_last_hour"] = result[0] if result else 0
                
                # Get latest timestamp
                result = fetch_one("SELECT MAX(timestamp) as latest FROM weather_records")
                db_stats["latest_weather_record"] = result[0] if result and result[0] else "None"
            except Exception as e:
                db_stats["weather_records_error"] = str(e)
            
            # Check forecast_data table
            try:
                from app.db.database import fetch_one
                
                result = fetch_one("SELECT COUNT(*) as count FROM forecast_data")
                db_stats["forecast_data_total"] = result[0] if result else 0
                
                # Get latest forecast timestamp - try different column names
                try:
                    result = fetch_one("SELECT MAX(collected_at) as latest FROM forecast_data")
                    db_stats["latest_forecast"] = result[0] if result and result[0] else "None"
                except:
                    # Try alternative column name
                    result = fetch_one("SELECT MAX(timestamp) as latest FROM forecast_data")
                    db_stats["latest_forecast"] = result[0] if result and result[0] else "None"
            except Exception as e:
                db_stats["forecast_data_error"] = str(e)
                
        except Exception as e:
            db_stats["error"] = str(e)
    
    return {
        "status": "healthy",
        "background_tasks": {
            "data_collector": "configured (runs every 10 minutes)",
            "radar_service": "configured (runs every 5 minutes)",
            "ml_scheduler": "configured (runs Sundays at 2 AM)"
        },
        "database": {
            "path": db_path,
            "exists": db_exists,
            "stats": db_stats
        }
    }


@app.post("/admin/collect-forecasts")
async def trigger_forecast_collection():
    """
    Manually trigger forecast collection (for testing/debugging).
    
    Collects official forecasts from Singapore, Malaysia, and Indonesia APIs
    and stores them in the forecast_data table.
    """
    from app.services.forecast_collector import ForecastCollector
    from app.services.forecast_store import ForecastStore
    
    logger.info("Manual forecast collection triggered via /admin/collect-forecasts")
    
    collector = ForecastCollector()
    store = ForecastStore()
    
    try:
        # Collect forecasts from all sources
        forecasts = await collector.collect_all_forecasts()
        logger.info(f"Manual forecast collection: Collected {len(forecasts)} forecasts")
        
        if not forecasts:
            return {
                "success": True,
                "collected": 0,
                "stored": 0,
                "message": "No forecasts collected - all sources may have failed"
            }
        
        # Store forecasts
        result = store.store_forecasts(forecasts)
        
        # Count by country
        by_country = {
            "singapore": len([f for f in forecasts if f["country"] == "singapore"]),
            "malaysia": len([f for f in forecasts if f["country"] == "malaysia"]),
            "indonesia": len([f for f in forecasts if f["country"] == "indonesia"])
        }
        
        response = {
            "success": True,
            "collected": len(forecasts),
            "stored": result["stored"],
            "by_country": by_country,
            "errors": result.get("error_messages", [])
        }
        
        logger.info(f"Manual forecast collection complete: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Manual forecast collection failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/admin/collect-now")
async def trigger_collection():
    """
    Manually trigger data collection (for testing/debugging).
    
    Note: The database uses ON CONFLICT handling to automatically prevent duplicates.
    Records with the same (timestamp, country, location) will be updated instead of duplicated.
    """
    from app.services.data_collector import DataCollector
    from app.services.data_store import DataStore
    import asyncio
    
    logger.info("Manual data collection triggered via /admin/collect-now")
    
    collector = DataCollector()
    store = DataStore()
    
    try:
        # Collect data from all sources
        records = await collector.collect_all_sources()
        logger.info(f"Manual collection: Collected {len(records)} records")
        
        # Store records (duplicates are automatically handled by ON CONFLICT clause)
        stored = 0
        updated = 0
        errors = []
        
        for record in records:
            try:
                # save_weather_record uses INSERT OR REPLACE for upsert logic
                # This automatically handles duplicates by updating existing records
                record_id = await asyncio.to_thread(store.store_record, record)
                stored += 1
            except Exception as e:
                errors.append(f"{record.location}: {str(e)}")
                logger.error(f"Failed to store record: {e}")
        
        # Count by country
        by_country = {
            "singapore": len([r for r in records if r.country == "singapore"]),
            "malaysia": len([r for r in records if r.country == "malaysia"]),
            "indonesia": len([r for r in records if r.country == "indonesia"])
        }
        
        result = {
            "success": True,
            "collected": len(records),
            "stored": stored,
            "by_country": by_country,
            "note": "Duplicates are automatically handled - existing records are updated",
            "errors": errors[:10] if errors else []  # First 10 errors only
        }
        
        logger.info(f"Manual collection complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Manual collection failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/admin/remove-duplicates")
async def remove_duplicates(dry_run: bool = True):
    """
    Remove duplicate weather records from the database.
    
    Duplicates are defined as records with the same (timestamp, country, location).
    When duplicates are found, keeps the most recent record and removes older ones.
    
    Args:
        dry_run: If True (default), only reports what would be deleted without actually deleting
        
    Returns:
        Summary of duplicates found and removed
    """
    from app.db.database import execute_sql
    
    logger.info(f"Duplicate removal triggered (dry_run={dry_run})")
    
    try:
        # Find duplicates
        duplicates = execute_sql("""
            SELECT timestamp, country, location, COUNT(*) as count
            FROM weather_records
            GROUP BY timestamp, country, location
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        if not duplicates:
            return {
                "success": True,
                "duplicates_found": 0,
                "records_removed": 0,
                "message": "No duplicates found - database is clean!"
            }
        
        duplicate_groups = len(duplicates)
        total_to_remove = sum(row[3] - 1 for row in duplicates)  # count - 1 for each group
        
        if dry_run:
            # Just report what would be deleted
            sample_duplicates = [
                {
                    "timestamp": row[0],
                    "country": row[1],
                    "location": row[2],
                    "count": row[3]
                }
                for row in duplicates[:10]  # Show first 10
            ]
            
            return {
                "success": True,
                "dry_run": True,
                "duplicates_found": duplicate_groups,
                "records_to_remove": total_to_remove,
                "sample": sample_duplicates,
                "message": f"Found {duplicate_groups} groups of duplicates. Set dry_run=false to remove them."
            }
        
        # Actually remove duplicates
        removed_count = 0
        
        for timestamp, country, location, count in duplicates:
            # Get all records in this duplicate group, ordered by created_at DESC
            records = execute_sql("""
                SELECT id FROM weather_records
                WHERE timestamp = ? AND country = ? AND location = ?
                ORDER BY created_at DESC
            """, (timestamp, country, location))
            
            # Keep the first one (most recent), delete the rest
            if len(records) > 1:
                delete_ids = [r[0] for r in records[1:]]
                
                # Delete duplicates
                placeholders = ','.join('?' * len(delete_ids))
                execute_sql(
                    f"DELETE FROM weather_records WHERE id IN ({placeholders})",
                    delete_ids
                )
                
                removed_count += len(delete_ids)
                logger.info(f"Removed {len(delete_ids)} duplicates for {country}/{location} at {timestamp}")
        
        return {
            "success": True,
            "dry_run": False,
            "duplicates_found": duplicate_groups,
            "records_removed": removed_count,
            "message": f"Successfully removed {removed_count} duplicate records from {duplicate_groups} groups"
        }
        
    except Exception as e:
        logger.error(f"Duplicate removal failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """Start background services on application startup"""
    from app.ml.scheduler import TrainingScheduler
    from app.services.data_collector import DataCollector
    from app.services.data_store import DataStore
    from app.services.forecast_collector import ForecastCollector
    from app.services.forecast_store import ForecastStore
    import asyncio
    
    logger.info("=" * 60)
    logger.info("STARTING WEATHER APP - BACKGROUND SERVICES")
    logger.info("=" * 60)
    
    # Start radar service (scraping weather.gov.sg images)
    try:
        logger.info("Starting radar service...")
        radar_service = get_radar_service()
        await radar_service.start_background_polling()
        logger.info("✓ Radar service started successfully")
    except Exception as e:
        logger.error(f"✗ Radar service failed to start: {e}", exc_info=True)
    
    # Start ML training scheduler (weekly training on Sunday 2 AM)
    try:
        logger.info("Starting ML training scheduler...")
        training_scheduler = TrainingScheduler()
        training_scheduler.start()
        logger.info("✓ ML training scheduler started (runs Sundays at 2 AM)")
    except Exception as e:
        logger.error(f"✗ ML scheduler failed to start: {e}", exc_info=True)
    
    # Start data collector (fetch weather data every 10 minutes)
    logger.info("Starting background data collector...")
    data_collector = DataCollector()
    data_store = DataStore()
    
    async def collect_and_store_data():
        """Background task to collect and store weather data"""
        collection_count = 0
        while True:
            try:
                collection_count += 1
                logger.info(f"[Collection #{collection_count}] Starting data collection from all sources...")
                
                # Collect data
                records = await data_collector.collect_all_sources()
                logger.info(f"[Collection #{collection_count}] Collected {len(records)} weather records")
                
                if not records:
                    logger.warning(f"[Collection #{collection_count}] No records collected - all sources may have failed")
                else:
                    # Store records in database
                    stored_count = 0
                    for record in records:
                        try:
                            await asyncio.to_thread(data_store.store_record, record)
                            stored_count += 1
                        except Exception as e:
                            logger.error(f"Failed to store record for {record.location}: {e}")
                    
                    logger.info(f"[Collection #{collection_count}] ✓ Stored {stored_count}/{len(records)} records in database")
                
                # Log next collection time
                logger.info(f"[Collection #{collection_count}] Next collection in 10 minutes...")
                
            except Exception as e:
                logger.error(f"[Collection #{collection_count}] Data collection failed: {e}", exc_info=True)
            
            # Wait 10 minutes before next collection
            await asyncio.sleep(600)
    
    # Start data collection task in background
    asyncio.create_task(collect_and_store_data())
    logger.info("✓ Data collector started (collects every 10 minutes)")
    
    # Start forecast collector (fetch forecasts every hour)
    logger.info("Starting background forecast collector...")
    forecast_collector = ForecastCollector()
    forecast_store = ForecastStore()
    
    async def collect_and_store_forecasts():
        """Background task to collect and store official forecasts"""
        forecast_collection_count = 0
        while True:
            try:
                forecast_collection_count += 1
                logger.info(f"[Forecast Collection #{forecast_collection_count}] Starting forecast collection from all sources...")
                
                # Collect forecasts
                forecasts = await forecast_collector.collect_all_forecasts()
                logger.info(f"[Forecast Collection #{forecast_collection_count}] Collected {len(forecasts)} forecasts")
                
                if not forecasts:
                    logger.warning(f"[Forecast Collection #{forecast_collection_count}] No forecasts collected - all sources may have failed")
                else:
                    # Store forecasts in database
                    result = forecast_store.store_forecasts(forecasts)
                    logger.info(f"[Forecast Collection #{forecast_collection_count}] ✓ Stored {result['stored']}/{len(forecasts)} forecasts in database")
                
                # Log next collection time
                logger.info(f"[Forecast Collection #{forecast_collection_count}] Next forecast collection in 1 hour...")
                
            except Exception as e:
                logger.error(f"[Forecast Collection #{forecast_collection_count}] Forecast collection failed: {e}", exc_info=True)
            
            # Wait 1 hour before next collection
            await asyncio.sleep(3600)
    
    # Start forecast collection task in background
    asyncio.create_task(collect_and_store_forecasts())
    logger.info("✓ Forecast collector started (collects every hour)")
    
    logger.info("=" * 60)
    logger.info("ALL BACKGROUND SERVICES STARTED")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services on application shutdown"""
    radar_service = get_radar_service()
    await radar_service.stop_background_polling()
    logger.info("Application shutdown complete")
