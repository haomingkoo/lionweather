import os
import logging
import asyncio
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# ---------------------------------------------------------------------------
# Rate limiter — keyed by client IP
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="LionWeather API",
    description="AI-powered weather forecasting for Singapore, Malaysia, and Indonesia",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _require_admin(secret: str | None) -> None:
    """Raise 403 if the provided secret does not match ADMIN_SECRET env var."""
    expected = os.getenv("ADMIN_SECRET")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")


# CORS — allow frontend domain and Railway preview URLs
allowed_origins = [
    "https://weather.kooexperience.com",
    "https://lionweather.kooexperience.com",
    "https://kooexperience.com",
    "https://lionweather-frontend-production.up.railway.app",
    "http://localhost:5173",
    "http://localhost:3000",
]
# Also allow any Railway preview URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
@limiter.limit("20/minute")
def status_check(request: Request):
    """Detailed status: shows exactly what's in the DB, per source API, per country."""
    import os
    from datetime import datetime, timedelta
    from app.db.database import fetch_one, fetch_all

    db_path = os.getenv("DATABASE_PATH", "weather.db")
    db_exists = os.path.exists(db_path)
    now = datetime.utcnow()
    cutoff_1h = (now - timedelta(hours=1)).isoformat()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()

    sources = []
    total_records = 0
    records_last_hour = 0
    records_last_24h = 0
    forecast_total = 0
    forecast_sources = []

    if db_exists:
        # ── Observations (weather_records) ────────────────────────────────
        try:
            rows = fetch_all("""
                SELECT
                    source_api,
                    country,
                    COUNT(*)          AS total,
                    MAX(timestamp)    AS latest,
                    MIN(timestamp)    AS oldest,
                    SUM(CASE WHEN timestamp >= :c1h  THEN 1 ELSE 0 END) AS last_1h,
                    SUM(CASE WHEN timestamp >= :c24h THEN 1 ELSE 0 END) AS last_24h
                FROM weather_records
                GROUP BY source_api, country
                ORDER BY country, total DESC
            """, {"c1h": cutoff_1h, "c24h": cutoff_24h})

            for row in rows:
                entry = {
                    "source_api": row["source_api"],
                    "country": row["country"],
                    "total_records": row["total"],
                    "latest_record": row["latest"],
                    "oldest_record": row["oldest"],
                    "records_last_1h": row["last_1h"],
                    "records_last_24h": row["last_24h"],
                    "status": "ok" if row["last_1h"] and row["last_1h"] > 0 else (
                        "stale" if row["last_24h"] and row["last_24h"] > 0 else "no_recent_data"
                    ),
                }
                sources.append(entry)
                total_records += row["total"] or 0
                records_last_hour += row["last_1h"] or 0
                records_last_24h += row["last_24h"] or 0
        except Exception as e:
            sources = [{"error": str(e)}]

        # ── Forecasts (forecast_data) ──────────────────────────────────────
        try:
            frows = fetch_all("""
                SELECT
                    source_api,
                    country,
                    COUNT(*) AS total,
                    MAX(created_at) AS latest
                FROM forecast_data
                GROUP BY source_api, country
                ORDER BY country, total DESC
            """)
            for row in frows:
                forecast_sources.append({
                    "source_api": row["source_api"],
                    "country": row["country"],
                    "total_records": row["total"],
                    "latest_collected": row["latest"],
                })
                forecast_total += row["total"] or 0
        except Exception as e:
            forecast_sources = [{"error": str(e)}]

    return {
        "status": "healthy",
        "timestamp_utc": now.isoformat(),
        "background_services": {
            "observations": "every 10 min — Singapore (NEA), Malaysia (Open-Meteo), Indonesia (Open-Meteo)",
            "forecasts": "every hour — Singapore (NEA), Malaysia (data.gov.my), Indonesia (Open-Meteo)",
            "radar": "every 5 min — Singapore weather.gov.sg",
            "ml_training": "weekly — Sundays 2 AM",
        },
        "database": {
            "path": db_path,
            "exists": db_exists,
        },
        "observations": {
            "total_records": total_records,
            "records_last_1h": records_last_hour,
            "records_last_24h": records_last_24h,
            "by_source": sources,
        },
        "forecasts": {
            "total_records": forecast_total,
            "by_source": forecast_sources,
        },
    }


@app.get("/admin/export")
async def export_data(
    table: str = "weather_records",
    fmt: str = "csv",
    limit: int = 10000,
    country: str = None,
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    _require_admin(x_admin_secret)
    """
    Export raw database records as CSV or JSON for inspection.

    Query params:
      table   = weather_records | forecast_data | sensor_history  (default: weather_records)
      fmt     = csv | json  (default: csv)
      limit   = max rows returned  (default: 10000)
      country = filter by country  (optional)

    Example: GET /admin/export?table=weather_records&fmt=csv&country=singapore
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse, JSONResponse
    from app.db.database import fetch_all

    allowed_tables = {"weather_records", "forecast_data", "sensor_history", "locations"}
    if table not in allowed_tables:
        return JSONResponse({"error": f"table must be one of {sorted(allowed_tables)}"}, status_code=400)

    if country:
        sql = f"SELECT * FROM {table} WHERE country = :country ORDER BY timestamp DESC LIMIT :limit"
        rows = fetch_all(sql, {"country": country, "limit": limit})
    else:
        sql = f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT :limit"
        rows = fetch_all(sql, {"limit": limit})

    if not rows:
        return JSONResponse({"rows": 0, "message": "No data found"})

    keys = list(rows[0]._mapping.keys())

    if fmt == "json":
        data = [dict(zip(keys, row)) for row in rows]
        return JSONResponse({"rows": len(data), "columns": keys, "data": data})

    # CSV streaming response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(keys)
    for row in rows:
        writer.writerow(list(row))

    output.seek(0)
    filename = f"{table}_{country or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/admin/collect-forecasts")
async def trigger_forecast_collection(
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    _require_admin(x_admin_secret)
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
async def trigger_collection(
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    _require_admin(x_admin_secret)
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
async def remove_duplicates(
    dry_run: bool = True,
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    _require_admin(x_admin_secret)
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


# ---------------------------------------------------------------------------
# Retrain state (in-memory, single process)
# ---------------------------------------------------------------------------
_retrain_state: dict = {
    "status": "idle",       # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "log_tail": [],         # last N lines of stdout+stderr
    "pid": None,
}


@app.post("/admin/retrain")
async def trigger_retrain(
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    """
    Trigger ML model retraining in the background.

    Protected by the ADMIN_SECRET environment variable.
    Pass it as the X-Admin-Secret request header.

    Training reads historical NEA CSV files from nea_historical_data/.
    On Railway, ensure those CSVs are present in the mounted volume.

    Returns immediately with {"status": "started"} if training begins,
    or {"status": "running", ...} if a run is already in progress.

    Poll GET /admin/retrain-status to check progress.
    """
    expected = os.getenv("ADMIN_SECRET")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")

    if _retrain_state["status"] == "running":
        return {
            "status": "already_running",
            "started_at": _retrain_state["started_at"],
            "pid": _retrain_state["pid"],
        }

    # Launch training subprocess
    async def _run_training():
        _retrain_state["status"] = "running"
        _retrain_state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _retrain_state["finished_at"] = None
        _retrain_state["log_tail"] = []
        _retrain_state["pid"] = None

        backend_dir = str(Path(__file__).parent.parent)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ml.train_full_analysis",
            cwd=backend_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _retrain_state["pid"] = proc.pid
        log_lines = []

        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            log_lines.append(line)
            if len(log_lines) > 200:
                log_lines.pop(0)
            _retrain_state["log_tail"] = log_lines[-50:]

        await proc.wait()
        _retrain_state["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if proc.returncode == 0:
            _retrain_state["status"] = "done"
            logger.info("Retrain job completed successfully")
        else:
            _retrain_state["status"] = "error"
            logger.error(f"Retrain job failed (exit {proc.returncode})")

    asyncio.create_task(_run_training())

    return {
        "status": "started",
        "message": "Training running in background. Poll /admin/retrain-status for progress.",
    }


@app.get("/admin/retrain-status")
async def retrain_status(
    x_admin_secret: str = Header(default=None, alias="X-Admin-Secret"),
):
    """Check the status of the most recent retrain job."""
    expected = os.getenv("ADMIN_SECRET")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")

    return {
        "status": _retrain_state["status"],
        "started_at": _retrain_state["started_at"],
        "finished_at": _retrain_state["finished_at"],
        "pid": _retrain_state["pid"],
        "log_tail": _retrain_state["log_tail"],
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
