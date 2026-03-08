"""Database migration scripts for ML weather forecasting system."""

from app.db.database import get_connection, get_database_url


def migrate_ml_tables():
    """Create new tables for ML weather forecasting system."""
    database_url = get_database_url()
    is_postgres = database_url.startswith("postgresql")
    
    # Auto-increment syntax differs between SQLite and PostgreSQL
    if is_postgres:
        id_column = "id SERIAL PRIMARY KEY"
    else:
        id_column = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    con = get_connection()
    cursor = con.cursor()
    
    # Create weather_records table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS weather_records (
            {id_column},
            timestamp TEXT NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            temperature REAL NOT NULL,
            rainfall REAL NOT NULL,
            humidity REAL NOT NULL,
            wind_speed REAL NOT NULL,
            wind_direction REAL,
            pressure REAL,
            source_api TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(timestamp, country, location)
        )
    """)
    
    # Create indexes for weather_records
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weather_timestamp 
        ON weather_records(timestamp)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weather_location 
        ON weather_records(country, location)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weather_composite 
        ON weather_records(country, location, timestamp)
    """)
    
    # Create model_metadata table with versioning support
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS model_metadata (
            {id_column},
            semantic_version TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            weather_parameter TEXT NOT NULL,
            country TEXT NOT NULL,
            version TEXT NOT NULL,
            hyperparameters TEXT NOT NULL,
            training_date TEXT NOT NULL,
            training_samples INTEGER NOT NULL,
            validation_mae REAL NOT NULL,
            validation_rmse REAL NOT NULL,
            validation_mape REAL NOT NULL,
            file_path TEXT NOT NULL,
            is_production INTEGER DEFAULT 0,
            status TEXT DEFAULT 'testing',
            training_data_hash TEXT,
            feature_list TEXT,
            config_json TEXT,
            metrics_json TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(semantic_version, model_name)
        )
    """)
    
    # Create model_performance_log table for time-series tracking
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS model_performance_log (
            {id_column},
            model_version TEXT NOT NULL,
            model_name TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            horizon_hours INTEGER NOT NULL,
            mae REAL,
            rmse REAL,
            f1_score REAL,
            accuracy REAL,
            precision REAL,
            recall REAL,
            n_samples INTEGER,
            rain_events INTEGER
        )
    """)
    
    # Create index for performance log
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_log_version 
        ON model_performance_log(model_version, model_name)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_log_date 
        ON model_performance_log(evaluation_date)
    """)
    
    # Create predictions table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS predictions (
            {id_column},
            model_id INTEGER NOT NULL,
            prediction_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            weather_parameter TEXT NOT NULL,
            predicted_value REAL NOT NULL,
            confidence_lower REAL NOT NULL,
            confidence_upper REAL NOT NULL
        )
    """)
    
    # Create index for predictions
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_target 
        ON predictions(target_timestamp, country, location)
    """)
    
    # Create evaluation_metrics table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS evaluation_metrics (
            {id_column},
            model_id INTEGER NOT NULL,
            evaluation_timestamp TEXT NOT NULL,
            target_timestamp TEXT NOT NULL,
            hours_ahead INTEGER NOT NULL,
            country TEXT NOT NULL,
            location TEXT NOT NULL,
            weather_parameter TEXT NOT NULL,
            predicted_value REAL NOT NULL,
            actual_value REAL NOT NULL,
            absolute_error REAL NOT NULL,
            squared_error REAL NOT NULL,
            percentage_error REAL NOT NULL
        )
    """)
    
    # Create index for evaluation_metrics
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_eval_model 
        ON evaluation_metrics(model_id, evaluation_timestamp)
    """)
    
    con.commit()
    con.close()
    
    print("ML weather forecasting tables created successfully")


def migrate_forecast_tables():
    """Create forecast_data table for official weather forecasts."""
    database_url = get_database_url()
    is_postgres = database_url.startswith("postgresql")
    
    # Auto-increment syntax differs between SQLite and PostgreSQL
    if is_postgres:
        id_column = "id SERIAL PRIMARY KEY"
    else:
        id_column = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    con = get_connection()
    cursor = con.cursor()
    
    # Create forecast_data table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS forecast_data (
            {id_column},
            
            prediction_time TEXT NOT NULL,
            target_time_start TEXT NOT NULL,
            target_time_end TEXT NOT NULL,
            
            country TEXT NOT NULL,
            location TEXT,
            latitude REAL,
            longitude REAL,
            
            temperature_low REAL,
            temperature_high REAL,
            humidity_low REAL,
            humidity_high REAL,
            wind_speed_low REAL,
            wind_speed_high REAL,
            wind_direction TEXT,
            forecast_description TEXT,
            
            source_api TEXT NOT NULL,
            created_at TEXT NOT NULL,
            
            UNIQUE(prediction_time, target_time_start, target_time_end, country, location)
        )
    """)
    
    # Create indexes for forecast_data
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forecast_country 
        ON forecast_data(country)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forecast_location 
        ON forecast_data(country, location)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forecast_target_time 
        ON forecast_data(target_time_start)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forecast_prediction_time 
        ON forecast_data(prediction_time)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forecast_composite 
        ON forecast_data(country, location, target_time_start)
    """)
    
    con.commit()
    con.close()
    
    print("Forecast data table created successfully")


def migrate_add_weather_code():
    """Add weather_code column to weather_records table for NEA classification."""
    con = get_connection()
    cursor = con.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("SELECT weather_code FROM weather_records LIMIT 1")
        print("weather_code column already exists")
    except Exception:
        # Column doesn't exist, add it
        cursor.execute("""
            ALTER TABLE weather_records ADD COLUMN weather_code INTEGER
        """)
        
        # Create index for weather_code queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_weather_code
            ON weather_records(weather_code)
        """)
        
        con.commit()
        print("weather_code column added successfully")
    
    con.close()


if __name__ == "__main__":
    migrate_ml_tables()
    migrate_forecast_tables()
    migrate_add_weather_code()
