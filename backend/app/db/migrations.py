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
    
    # Create model_metadata table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS model_metadata (
            {id_column},
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
            created_at TEXT NOT NULL
        )
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


if __name__ == "__main__":
    migrate_ml_tables()
