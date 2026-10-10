import os
from typing import Dict, Any, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Determine database URL from settings / environment
DATABASE_URL = settings.sync_database_url

# Create SQLAlchemy engine with connection health pre-ping
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory for database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative Base for future ORM models (Phase 3B)
Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency for yielding transactional database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection(custom_engine=None) -> Dict[str, Any]:
    """
    Executes 'SELECT 1' against PostgreSQL to verify connectivity and retrieves connection metadata.

    Returns:
        Dict with status, database_name, current_user, server_version.
    """
    target_engine = custom_engine or engine
    with target_engine.connect() as connection:
        # Execute test query
        result = connection.execute(text("SELECT 1 AS alive, current_database() AS db_name, current_user AS db_user, version() AS db_version;")).fetchone()
        if result is None or result[0] != 1:
            raise ConnectionError("Database query 'SELECT 1' did not return expected result.")

        return {
            "status": "connected",
            "alive": result[0] == 1,
            "database_name": result[1],
            "current_user": result[2],
            "server_version": result[3].split()[0] + " " + result[3].split()[1],
            "full_version": result[3],
        }
