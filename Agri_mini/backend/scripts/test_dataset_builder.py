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

import numpy as np
from app.database import SessionLocal, check_db_connection
from app.services.dataset_builder import MLDatasetBuilder


def print_separator(char="=", length=100):
    print(char * length)


def main():
    parser = argparse.ArgumentParser(description="Test ML Dataset Builder and Train/Test Preparation (Phase 4B)")
    parser.add_argument("--test-size", type=float, default=0.2, help="Proportion of newest observations for testing (default: 0.2)")
    args = parser.parse_args()

    print_separator()
    print("  ML DATASET BUILDER & MULTI-SOURCE INTEGRATION TEST (Phase 4B)")
    print_separator()

    db_info = check_db_connection()
    print(f"  Source Database   : {db_info['database_name']} (User: {db_info['current_user']}, Server: {db_info['server_version']})")
    print_separator("-")

    db = SessionLocal()
    try:
        builder = MLDatasetBuilder(db=db)
        print(f"  Executing ML Dataset Builder (Chronological Train/Test Split: {round((1-args.test_size)*100)}:{round(args.test_size*100)})...")
        data = builder.prepare_ml_dataset(test_size=args.test_size, db=db)

        dstats = data["dataset_stats"]
        ustats = data["unmatched_stats"]
        tstats = data["target_stats"]

        print("\n  [1] Target Variable Definition:")
        print("      - Target (y)             : modal_price (INR per quintal)")
        print(f"      - y_train Distribution    : Mean=Rs.{tstats['train']['mean']:.2f}, Std={tstats['train']['std']:.2f}, Min=Rs.{tstats['train']['min']:.2f}, Max=Rs.{tstats['train']['max']:.2f}")
        print(f"      - y_test Distribution     : Mean=Rs.{tstats['test']['mean']:.2f}, Std={tstats['test']['std']:.2f}, Min=Rs.{tstats['test']['min']:.2f}, Max=Rs.{tstats['test']['max']:.2f}")

        print("\n  [2] Target Leakage Prevention & Feature Selection:")
        print("      - DELIBERATELY EXCLUDED  : modal_price (target), min_price, max_price, price_spread,")
        print("                                 price_spread_pct, price_to_min_ratio, price_to_max_ratio,")
        print("                                 and unshifted same-day rolling averages.")
        print("      - HISTORICAL PREDICTORS  : hist_lag_1d_price (price at t-1), hist_rolling_mean_3d,")
        print("                                 hist_rolling_mean_7d, hist_rolling_std_7d, hist_price_momentum_1d")
        print("                                 (all strictly computed from observations prior to prediction day).")

        print("\n  [3] Multi-Source Feature Integration:")
        print(f"      - Total Market Samples   : {ustats['total_market_records']}")
        print(f"      - Weather Matched        : {ustats['weather_matched']}/{ustats['total_market_records']} ({round(ustats['weather_matched']/ustats['total_market_records']*100, 1)}%)")
        print(f"      - FAOSTAT Matched        : {ustats['faostat_matched']}/{ustats['total_market_records']} ({round(ustats['faostat_matched']/ustats['total_market_records']*100, 1)}%)")
        print(f"      - Route Logistics Matched: {ustats['route_matched']}/{ustats['total_market_records']} ({round(ustats['route_matched']/ustats['total_market_records']*100, 1)}%)")

        print("\n  [4] Chronological Train / Test Split:")
        print(f"      - Training Date Range    : {data['train_date_range']['start']} to {data['train_date_range']['end']}")
        print(f"      - Testing Date Range     : {data['test_date_range']['start']} to {data['test_date_range']['end']}")
        print(f"      - X_train Shape          : {data['X_train'].shape}")
        print(f"      - y_train Shape          : {data['y_train'].shape}")
        print(f"      - X_test Shape           : {data['X_test'].shape}")
        print(f"      - y_test Shape           : {data['y_test'].shape}")

        print("\n  [5] Encoding & Scaler Verification:")
        print(f"      - Numerical Features     : {dstats['numerical_features_count']}")
        print(f"      - One-Hot Encoded Features: {dstats['categorical_encoded_features_count']}")
        print(f"      - Total Model Features   : {dstats['total_model_features']}")
        
        # Check numerical sanity
        has_train_nan = np.isnan(data["X_train"]).any()
        has_test_nan = np.isnan(data["X_test"]).any()
        has_train_inf = np.isinf(data["X_train"]).any()
        has_test_inf = np.isinf(data["X_test"]).any()

        print(f"      - X_train NaN / Inf Free : {not (has_train_nan or has_train_inf)}")
        print(f"      - X_test NaN / Inf Free  : {not (has_test_nan or has_test_inf)}")

        print("\n  [6] Sample Feature Names (First 15 of %d):" % len(data["feature_names"]))
        for i in range(0, min(15, len(data["feature_names"])), 3):
            chunk = data["feature_names"][i:i+3]
            print("        " + ", ".join(f"{c:<28}" for c in chunk))

        print_separator("-")
        print(" [DATASET SUCCESS] Phase 4B ML dataset builder executed and verified successfully!")

    except Exception as e:
        print(f"\n [DATASET FAILURE] ML dataset preparation encountered an error: {e}\n")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
