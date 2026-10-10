import os
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

from app.services.agmarknet_service import (
    AgmarknetDataService,
    AgmarknetApiKeyMissingError,
    AgmarknetAPIError,
)


def print_separator(char="=", length=100):
    print(char * length)


def format_table(records):
    """Prints a clean tabular representation of normalized market records."""
    if not records:
        print("  No records returned.")
        return

    header = (
        f"{'#':<3} | {'State':<15} | {'District':<15} | {'Market':<15} | "
        f"{'Commodity':<12} | {'Variety':<10} | {'Arrival Date':<12} | "
        f"{'Min (INR)':<9} | {'Max (INR)':<9} | {'Modal (INR)':<11}"
    )
    print_separator("-", len(header))
    print(header)
    print_separator("-", len(header))

    for idx, r in enumerate(records, 1):
        min_p = f"{r['min_price']:.1f}" if r['min_price'] is not None else "N/A"
        max_p = f"{r['max_price']:.1f}" if r['max_price'] is not None else "N/A"
        modal_p = f"{r['modal_price']:.1f}" if r['modal_price'] is not None else "N/A"

        row = (
            f"{idx:<3} | {r['state'][:15]:<15} | {r['district'][:15]:<15} | {r['market'][:15]:<15} | "
            f"{r['commodity'][:12]:<12} | {r['variety'][:10]:<10} | {r['arrival_date'][:12]:<12} | "
            f"{min_p:<9} | {max_p:<9} | {modal_p:<11}"
        )
        print(row)
    print_separator("-", len(header))


def main():
    parser = argparse.ArgumentParser(description="Test Agmarknet / data.gov.in Market Data Acquisition Service")
    parser.add_argument("--commodity", type=str, default=None, help="Filter by commodity name (e.g. Tomato, Onion)")
    parser.add_argument("--state", type=str, default=None, help="Filter by state (e.g. Maharashtra)")
    parser.add_argument("--district", type=str, default=None, help="Filter by district (e.g. Pune)")
    parser.add_argument("--market", type=str, default=None, help="Filter by market name (e.g. Pune)")
    parser.add_argument("--limit", type=int, default=10, help="Number of records to fetch (default: 10)")
    parser.add_argument("--api-key", type=str, default=None, help="Explicit data.gov.in API key")

    args = parser.parse_args()

    print_separator()
    print("  AGMARKNET / DATA.GOV.IN MARKET DATA ACQUISITION TEST (Phase 2A)")
    print_separator()

    service = AgmarknetDataService(api_key=args.api_key)
    print(f"  Target Endpoint  : {service.endpoint_url}")
    print(f"  Resource ID      : {service.resource_id}")
    print(f"  Query Parameters : commodity='{args.commodity}', state='{args.state}', district='{args.district}', market='{args.market}', limit={args.limit}")
    print_separator()

    try:
        result = service.fetch_market_prices(
            commodity=args.commodity,
            state=args.state,
            district=args.district,
            market=args.market,
            limit=args.limit,
        )

        print(f" [SUCCESS] Successfully connected to data.gov.in API!")
        print(f"  Total Available Records in Dataset : {result['total_records']}")
        print(f"  Records Returned for this Query   : {result['returned_count']}")
        print()
        print("  Sample Normalized Records:")
        format_table(result["records"])
        print()
        print("[STATUS] Phase 2A data-source test passed successfully!")

    except AgmarknetApiKeyMissingError as e:
        print("\n [AUTHENTICATION REQUIRED] Missing API Key:")
        print(f"{e}\n")
        print(" Instructions to configure your API key:")
        print(" 1. Sign up on https://data.gov.in (free government portal).")
        print(" 2. Navigate to 'My Account' -> 'My API Key' to obtain your API key.")
        print(" 3. Open 'backend/.env' (or create it from 'backend/.env.example') and set:")
        print("    DATA_GOV_IN_API_KEY=your_actual_api_key_here")
        print(" 4. Re-run: python backend/scripts/test_agmarknet.py\n")
        sys.exit(2)

    except AgmarknetAPIError as e:
        print(f"\n [API ERROR] Failed to fetch data: {e}\n")
        sys.exit(1)

    except Exception as e:
        print(f"\n [UNEXPECTED ERROR]: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
