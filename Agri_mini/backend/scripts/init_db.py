import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env file from backend or project root
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.url import make_url
from app.config import settings
from app.database import Base, check_db_connection
# Explicitly import all models so Base.metadata is fully populated
import app.models


def print_separator(char="=", length=90):
    print(char * length)


def mask_db_url(url_str: str) -> str:
    """Masks password from connection string for secure display."""
    try:
        u = make_url(url_str)
        return u.render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def init_database(target_url: str):
    masked_url = mask_db_url(target_url)

    print_separator()
    print("  POSTGRESQL DATABASE INITIALIZATION & TABLE CREATION (Phase 3B)")
    print_separator()
    print(f"  Target Driver URL : {masked_url}")

    # Check connection first
    test_engine = create_engine(target_url, pool_pre_ping=True)
    db_info = check_db_connection(custom_engine=test_engine)
    print(f"  Connected to      : {db_info['database_name']} (User: {db_info['current_user']}, Server: {db_info['server_version']})")
    print_separator("-")

    # Create all tables defined in Base.metadata
    print("  Creating tables defined in SQLAlchemy ORM models...")
    Base.metadata.create_all(bind=test_engine)

    # Inspect created tables
    inspector = inspect(test_engine)
    existing_tables = inspector.get_table_names()

    expected_tables = ["market_prices", "weather_records", "faostat_indicators", "route_records"]
    created_count = 0

    print()
    print("  Database Tables Verified:")
    for table_name in expected_tables:
        if table_name in existing_tables:
            columns = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            pk_cols = ", ".join(pk_constraint.get("constrained_columns", []))
            indexes = inspector.get_indexes(table_name)
            uqs = inspector.get_unique_constraints(table_name)
            print(f"  [OK] Table '{table_name:<20}' -> {len(columns):2d} columns, PK: ({pk_cols}), {len(indexes)} indexes, {len(uqs)} unique constraints")
            created_count += 1
        else:
            print(f"  [MISSING] Table '{table_name}' was NOT found in database!")

    test_engine.dispose()
    print_separator("-")

    if created_count == len(expected_tables):
        print(" [SUCCESS] All 4 required ORM database tables are created and verified in PostgreSQL!")
        print("[STATUS] Phase 3B database schema initialization completed successfully!")
    else:
        print(f" [WARNING] Only {created_count}/{len(expected_tables)} expected tables were found.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL Database Tables via SQLAlchemy ORM (Phase 3B)")
    parser.add_argument("--database-url", type=str, default=None, help="Explicit database URL override (optional)")

    args = parser.parse_args()

    raw_db_url = args.database_url or settings.DATABASE_URL
    if raw_db_url.startswith("postgresql://"):
        target_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        target_url = raw_db_url

    try:
        init_database(target_url)
    except Exception as e:
        print(f"\n [INITIALIZATION ERROR] Failed to initialize database tables:")
        print(f"{e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
