import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from app.database import SessionLocal, check_db_connection
from app.services.preprocessing_service import DataPreprocessingService


def print_separator(char="=", length=100):
    print(char * length)


def main():
    parser = argparse.ArgumentParser(description="Test Data Extraction, Cleaning and Preprocessing Pipeline (Phase 4A)")
    parser.parse_args()

    print_separator()
    print("  AGRICULTURAL DATA PREPROCESSING & FEATURE ENGINEERING PIPELINE (Phase 4A)")
    print_separator()

    db_info = check_db_connection()
    print(f"  Source Database   : {db_info['database_name']} (User: {db_info['current_user']}, Server: {db_info['server_version']})")
    print_separator("-")

    db = SessionLocal()
    try:
        service = DataPreprocessingService(db=db)
        print("  Extracting and processing multi-source data from PostgreSQL tables...")
        results = service.run_pipeline(db)

        # 1. Market Price Pipeline Stats
        mp = results["market_prices"]
        stats = mp["stats"]
        print("\n  [1] Market Price Cleaning & Feature Engineering:")
        print(f"      - Raw Input Rows         : {stats['input_rows']}")
        print(f"      - Clean Output Rows       : {stats['output_rows']}")
        print(f"      - Invalid Rows Filtered   : {stats['invalid_rows_filtered']}")
        print(f"      - Missing Values Handled  : {stats['missing_values_handled']}")
        print(f"      - Duplicates Removed      : {stats['duplicates_removed']}")
        print(f"      - Total Features Generated: {len(mp['features'])}")

        print("\n      Engineered Feature Columns:")
        for i in range(0, len(mp["features"]), 4):
            chunk = mp["features"][i:i+4]
            print("        " + ", ".join(f"{col:<22}" for col in chunk))

        # Sample preview
        print("\n      Sample Cleaned & Featured Market Records (Top 3):")
        print("      " + "-" * 90)
        df_sample = mp["dataframe"]
        cols_to_show = [
            "market", "commodity", "arrival_date", "modal_price",
            "price_spread", "price_spread_pct", "price_rolling_mean_3d", "price_change_1d"
        ]
        if not df_sample.empty:
            for idx, row in df_sample.head(3)[cols_to_show].iterrows():
                dt_str = row['arrival_date'].strftime('%Y-%m-%d') if hasattr(row['arrival_date'], 'strftime') else str(row['arrival_date'])
                print(f"      #{idx+1}: {row['market']:<22} | {row['commodity']:<10} | {dt_str} | Modal: Rs.{row['modal_price']:7.2f} | Spread: Rs.{row['price_spread']:5.2f} ({row['price_spread_pct']:4.1f}%) | 3D-Mean: Rs.{row['price_rolling_mean_3d']:7.2f} | Mom: Rs.{row['price_change_1d']:+6.2f}")
        print("      " + "-" * 90)

        # 2. Weather Pipeline Stats
        w = results["weather_records"]
        print(f"\n  [2] Agro-Meteorological Weather Records:")
        print(f"      - Total Processed Rows    : {w['total_rows']}")
        print(f"      - Features Prepared       : {', '.join(w['features'][:8])} ...")

        # 3. FAOSTAT Macro Indicators
        f = results["faostat_indicators"]
        print(f"\n  [3] FAOSTAT National Production & Yield Benchmarks:")
        print(f"      - Total Processed Rows    : {f['total_rows']}")
        print(f"      - Crops Covered           : {', '.join(f['commodities'])}")

        # 4. Route Logistics
        r = results["route_records"]
        print(f"\n  [4] Road Network Logistics Corridors:")
        print(f"      - Total Active Routes     : {r['total_routes']}")
        for c in r["corridors"]:
            print(f"        * {c}")

        print_separator("-")
        print(" [PIPELINE SUCCESS] Phase 4A data extraction, cleaning and preprocessing pipeline completed successfully!")

    except Exception as e:
        print(f"\n [PIPELINE FAILURE] Preprocessing pipeline encountered an error: {e}\n")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
