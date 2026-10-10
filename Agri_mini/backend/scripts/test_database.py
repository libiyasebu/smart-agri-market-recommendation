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

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from app.config import settings
from app.database import check_db_connection


def print_separator(char="=", length=90):
    print(char * length)


def mask_db_url(url_str: str) -> str:
    """Masks password from connection string for secure logging/display."""
    try:
        u = make_url(url_str)
        return u.render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def main():
    parser = argparse.ArgumentParser(description="Test PostgreSQL + SQLAlchemy Database Connection (Phase 3A)")
    parser.add_argument("--database-url", type=str, default=None, help="Explicit database URL override (optional)")

    args = parser.parse_args()

    raw_db_url = args.database_url or settings.DATABASE_URL
    if raw_db_url.startswith("postgresql://"):
        target_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        target_url = raw_db_url

    masked_url = mask_db_url(target_url)

    print_separator()
    print("  POSTGRESQL + SQLALCHEMY DATABASE CONNECTION TEST (Phase 3A)")
    print_separator()
    print(f"  Target Driver URL : {masked_url}")

    try:
        u = make_url(target_url)
        print(f"  Host              : {u.host or 'localhost'}")
        print(f"  Port              : {u.port or 5432}")
        print(f"  Database Target   : {u.database or 'agri_mini_db'}")
        print(f"  Username          : {u.username or 'postgres'}")
    except Exception:
        pass
    print_separator()

    try:
        # Create a dedicated testing engine
        test_engine = create_engine(target_url, pool_pre_ping=True)

        # Connect and execute SELECT 1
        info = check_db_connection(custom_engine=test_engine)
        test_engine.dispose()

        print(" [DATABASE CONNECTION SUCCESS] Successfully connected to PostgreSQL via SQLAlchemy!")
        print_separator("-")
        print(f"  Database Name     : {info['database_name']}")
        print(f"  Connected User    : {info['current_user']}")
        print(f"  PostgreSQL Server : {info['server_version']}")
        print(f"  Query Executed    : SELECT 1 (Alive: {info['alive']})")
        print(f"  Connection Status : Active & Healthy")
        print_separator("-")
        print()
        print("[STATUS] Phase 3A database connection verification passed successfully!")

    except Exception as e:
        print("\n [DATABASE CONNECTION FAILURE] Failed to connect to PostgreSQL:")
        print(f"{e}\n")
        print(" Troubleshooting Steps:")
        print(" 1. Ensure PostgreSQL service is running on your machine.")
        print(" 2. Verify that the database exists: psql -U postgres -c 'CREATE DATABASE agri_mini_db;'")
        print(" 3. Verify your PostgreSQL password in backend/.env:")
        print("    DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/agri_mini_db")
        print(" 4. Re-run: python backend/scripts/test_database.py\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
