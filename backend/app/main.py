import os
import sqlite3
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
from app.routers.forecasts import router as forecasts_router
from app.routers.environmental import router as environmental_router
from app.routers.ml_forecast import router as ml_router
from app.routers.weather_data import router as weather_data_router
from app.routers.performance import router as performance_router
from app.routers.ml import router as ml_api_router
from app.routers.radar import router as radar_router
from app.routers.regional import router as regional_router
from app.routers.alerts import router as alerts_router
from app.db.migrations import migrate_ml_tables
from app.services.radar_service import get_radar_service

DB_PATH = os.getenv("DATABASE_PATH", "weather.db")


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS forecast_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            prediction_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            
            -- Our ML predictions
            ml_temperature REAL,
            ml_condition TEXT,
            ml_rain_probability REAL,
            ml_confidence REAL,
            
            -- Official predictions
            official_temperature REAL,
            official_condition TEXT,
            official_source TEXT,
            
            -- Actual weather (recorded later)
            actual_temperature REAL,
            actual_condition TEXT,
            actual_rainfall REAL,
            actual_recorded_at TEXT,
            
            -- Performance metrics
            ml_temp_error REAL,
            official_temp_error REAL,
            ml_condition_correct INTEGER,
            official_condition_correct INTEGER,
            ml_wins INTEGER DEFAULT 0,
            
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)
    
    # Model training data table
    con.execute("""
        CREATE TABLE IF NOT EXISTS sensor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS model_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    con.commit()
    con.close()


init_db()

# Run ML table migrations
migrate_ml_tables()

app = FastAPI(
    title="LionWeather API",
    description="AI-powered weather forecasting for Singapore, Malaysia, and Indonesia",
    version="1.0.0",
)

app.include_router(locations_router, prefix="/api")
app.include_router(rainfall_router, prefix="/api")
app.include_router(weather_router, prefix="/api")
app.include_router(forecasts_router, prefix="/api")
app.include_router(environmental_router, prefix="/api")
app.include_router(ml_router, prefix="/api")
app.include_router(weather_data_router, prefix="/api")
app.include_router(performance_router, prefix="/api")
app.include_router(ml_api_router)
app.include_router(radar_router, prefix="/api")
app.include_router(regional_router, prefix="/api")
app.include_router(alerts_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Start background services on application startup"""
    from app.ml.scheduler import TrainingScheduler
    from app.services.data_collector import DataCollector
    from app.services.data_store import DataStore
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
    
    logger.info("=" * 60)
    logger.info("ALL BACKGROUND SERVICES STARTED")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services on application shutdown"""
    radar_service = get_radar_service()
    await radar_service.stop_background_polling()
    logger.info("Application shutdown complete")
