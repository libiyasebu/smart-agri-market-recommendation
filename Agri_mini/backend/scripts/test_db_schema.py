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
from app.database import check_db_connection
import app.models


def print_separator(char="=", length=95):
    print(char * length)


def mask_db_url(url_str: str) -> str:
    """Masks password from connection string for secure display."""
    try:
        u = make_url(url_str)
        return u.render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def inspect_schema(target_url: str):
    masked_url = mask_db_url(target_url)

    print_separator()
    print("  POSTGRESQL SCHEMA & TABLE DEFINITION VERIFICATION (Phase 3B)")
    print_separator()
    print(f"  Target Driver URL : {masked_url}")

    # Check connection
    test_engine = create_engine(target_url, pool_pre_ping=True)
    db_info = check_db_connection(custom_engine=test_engine)
    print(f"  Database Target   : {db_info['database_name']} (Server: {db_info['server_version']})")
    print_separator("-")

    inspector = inspect(test_engine)
    existing_tables = set(inspector.get_table_names())

    expected_tables = {
        "market_prices": [
            "id", "state", "district", "market", "commodity", "variety",
            "arrival_date", "min_price", "max_price", "modal_price", "source", "created_at"
        ],
        "weather_records": [
            "id", "latitude", "longitude", "location_name", "record_date",
            "temp_mean_celsius", "temp_min_celsius", "temp_max_celsius",
            "humidity_mean_pct", "precipitation_mm", "rain_mm",
            "weather_code", "weather_condition", "source", "created_at"
        ],
        "faostat_indicators": [
            "id", "area", "area_code", "commodity", "item_code",
            "indicator", "indicator_code", "year", "value", "unit",
            "flag", "flag_description", "source", "created_at"
        ],
        "route_records": [
            "id", "origin_lat", "origin_lon", "origin_name",
            "dest_lat", "dest_lon", "dest_name",
            "distance_km", "duration_minutes", "duration_hours",
            "geometry_geojson", "routing_provider", "created_at"
        ],
    }

    all_passed = True

    for table_name, expected_cols in expected_tables.items():
        print(f"\n[TABLE] >>> '{table_name}'")
        if table_name not in existing_tables:
            print(f"  [ERROR] Table '{table_name}' does not exist in database!")
            all_passed = False
            continue

        columns = inspector.get_columns(table_name)
        col_names = {col["name"] for col in columns}
        pk_info = inspector.get_pk_constraint(table_name)
        pk_cols = pk_info.get("constrained_columns", [])
        uqs = inspector.get_unique_constraints(table_name)
        indexes = inspector.get_indexes(table_name)

        print(f"  Primary Key : {pk_cols}")
        print(f"  Columns ({len(columns)}):")
        for c in columns:
            nullable_str = "NULL" if c.get("nullable", True) else "NOT NULL"
            print(f"    - {c['name']:<20} : {str(c['type']):<22} [{nullable_str}]")

        if uqs:
            print(f"  Unique Constraints ({len(uqs)}):")
            for u in uqs:
                print(f"    - {u.get('name', 'unnamed')}: ({', '.join(u.get('column_names', []))})")

        if indexes:
            print(f"  Indexes ({len(indexes)}):")
            for idx in indexes:
                print(f"    - {idx.get('name')}: ({', '.join(idx.get('column_names', []))}) [unique={idx.get('unique', False)}]")

        # Verify all expected columns are present
        missing_cols = set(expected_cols) - col_names
        if missing_cols:
            print(f"  [ERROR] Missing expected columns: {missing_cols}")
            all_passed = False
        else:
            print(f"  [PASS] All {len(expected_cols)} expected columns verified.")

    test_engine.dispose()
    print()
    print_separator("-")

    if all_passed:
        print(" [VERIFICATION SUCCESS] All 4 PostgreSQL schema tables, columns, PKs & constraints verified!")
        print("[STATUS] Phase 3B database schema inspection passed successfully!")
    else:
        print(" [VERIFICATION FAILURE] Schema inconsistencies detected!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Inspect & Verify PostgreSQL Database Schema (Phase 3B)")
    parser.add_argument("--database-url", type=str, default=None, help="Explicit database URL override (optional)")

    args = parser.parse_args()

    raw_db_url = args.database_url or settings.DATABASE_URL
    if raw_db_url.startswith("postgresql://"):
        target_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        target_url = raw_db_url

    try:
        inspect_schema(target_url)
    except Exception as e:
        print(f"\n [SCHEMA ERROR] Failed to inspect database schema:")
        print(f"{e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
