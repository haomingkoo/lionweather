"""
Database connection utility that supports both SQLite and PostgreSQL.

Uses a singleton engine to prevent connection pool exhaustion.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
import logging

logger = logging.getLogger(__name__)

# Singleton engine - created once, reused for all calls
_engine = None


def get_database_url() -> str:
    """Get database URL from environment, defaulting to SQLite."""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        logger.info("Using PostgreSQL database from DATABASE_URL")
        # Railway uses postgres:// but SQLAlchemy needs postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    db_path = os.getenv("DATABASE_PATH", "weather.db")
    logger.info(f"Using SQLite database at {db_path}")
    return f"sqlite:///{db_path}"


def is_postgres() -> bool:
    """Return True if the configured database is PostgreSQL."""
    return get_engine().url.drivername.startswith("postgresql")


def get_engine():
    """Return the singleton SQLAlchemy engine (created on first call)."""
    global _engine
    if _engine is not None:
        return _engine

    database_url = get_database_url()

    if database_url.startswith("sqlite"):
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

    return _engine


def get_connection():
    """Get a raw database connection (compatible with sqlite3 API)."""
    return get_engine().raw_connection()


def execute_sql(sql: str, params=None):
    """Execute SQL statement (works with both SQLite and PostgreSQL)."""
    with get_engine().connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        conn.commit()
        return result


def fetch_all(sql: str, params=None):
    """Fetch all rows from SQL query."""
    with get_engine().connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        return result.fetchall()


def fetch_one(sql: str, params=None):
    """Fetch one row from SQL query."""
    with get_engine().connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))
        return result.fetchone()
