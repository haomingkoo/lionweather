"""
Database connection utility that supports both SQLite and PostgreSQL
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
import logging

logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment, defaulting to SQLite"""
    # Railway provides DATABASE_URL for PostgreSQL
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # PostgreSQL from Railway
        logger.info("Using PostgreSQL database from DATABASE_URL")
        # Railway uses postgres:// but SQLAlchemy needs postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url
    else:
        # SQLite for local development
        db_path = os.getenv("DATABASE_PATH", "weather.db")
        logger.info(f"Using SQLite database at {db_path}")
        return f"sqlite:///{db_path}"


def get_engine():
    """Create SQLAlchemy engine"""
    database_url = get_database_url()
    
    if database_url.startswith("sqlite"):
        # SQLite-specific configuration
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL configuration
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    
    return engine


def get_connection():
    """Get a database connection (compatible with sqlite3 API)"""
    engine = get_engine()
    return engine.raw_connection()


def execute_sql(sql: str, params=None):
    """Execute SQL statement (works with both SQLite and PostgreSQL)"""
    engine = get_engine()
    with engine.connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        conn.commit()
        return result


def fetch_all(sql: str, params=None):
    """Fetch all rows from SQL query"""
    engine = get_engine()
    with engine.connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        return result.fetchall()


def fetch_one(sql: str, params=None):
    """Fetch one row from SQL query"""
    engine = get_engine()
    with engine.connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        return result.fetchone()
