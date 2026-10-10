import sys
import argparse
from pathlib import Path

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.faostat_service import (
    FAOSTATDataService,
    FAOSTATError,
    FAOSTATItemNotFoundError,
    FAOSTATAPIError,
)


def print_separator(char="=", length=110):
    print(char * length)


def format_table(records):
    """Prints a clean tabular representation of normalized FAOSTAT records."""
    if not records:
        print("  No FAOSTAT records returned.")
        return

    header = (
        f"{'#':<3} | {'Area':<10} | {'Item / Crop':<15} | {'Indicator':<16} | "
        f"{'Year':<6} | {'Value':<16} | {'Unit':<8} | {'Flag':<16}"
    )
    print_separator("-", len(header))
    print(header)
    print_separator("-", len(header))

    for idx, r in enumerate(records, 1):
        val_str = f"{r['value']:,.1f}" if r['value'] is not None else "N/A"
        flag_info = f"{r['flag']} ({r['flag_description']})" if r['flag_description'] else (r['flag'] or "Official")

        row = (
            f"{idx:<3} | {r['area'][:10]:<10} | {r['item'][:15]:<15} | {r['indicator'][:16]:<16} | "
            f"{r['year']:<6} | {val_str:<16} | {r['unit']:<8} | {flag_info[:16]:<16}"
        )
        print(row)
    print_separator("-", len(header))


def main():
    parser = argparse.ArgumentParser(description="Test FAOSTAT Macro Agricultural Indicators Data Acquisition Service")
    parser.add_argument("--commodity", type=str, default="Tomato", help="Commodity to test (e.g. Tomato, Onion, Potato, Wheat, Rice)")
    parser.add_argument("--year", type=int, default=None, help="Year filter (e.g. 2022)")
    parser.add_argument("--indicator", type=str, default=None, help="Indicator filter (e.g. Production, Yield, Area harvested)")
    parser.add_argument("--limit", type=int, default=10, help="Number of records to fetch (default: 10)")
    parser.add_argument("--live-only", action="store_true", help="Disable fallback snapshot; fail immediately if live API is unreachable")
    parser.add_argument("--token", type=str, default=None, help="Optional FAOSTAT API JWT Bearer token")

    args = parser.parse_args()

    print_separator()
    print("  FAOSTAT MACRO AGRICULTURAL INDICATORS DATA ACQUISITION TEST (Phase 2C)")
    print_separator()

    service = FAOSTATDataService(token=args.token)
    print(f"  Official Endpoint : {service.endpoint_url}")
    print(f"  Target Domain     : Crops and Livestock Products ({service.default_domain})")
    print(f"  Target Country    : India (FAO Area Code: {service.default_area_code})")
    print(f"  Commodity Query   : {args.commodity}")
    print(f"  Indicator Filter  : {args.indicator or 'All Indicators'}")
    print(f"  Year Filter       : {args.year or 'Recent Years'}")
    print(f"  Mode              : {'LIVE API ONLY (Fallback Disabled)' if args.live_only else 'LIVE API with Snapshot Fallback'}")
    print_separator()

    try:
        result = service.fetch_indicators(
            commodity=args.commodity,
            year=args.year,
            element=args.indicator,
            limit=args.limit,
            live_only=args.live_only,
        )

        if result["is_fallback"]:
            print(" [FALLBACK SNAPSHOT USED] Live API request failed; benchmark snapshot used for resilience:")
            print(f"  -> Live API Failure Reason : {result['live_error']}")
            print(f"  -> Data Source             : {result['source']}")
            print(f"  -> Geographic Level        : {result['geographic_level']}")
            print(f"  -> Records Retrieved       : {result['total_records']}")
        else:
            print(" [LIVE API SUCCESS] Successfully received and normalized live data from FAOSTAT:")
            print(f"  -> Endpoint Tested         : {result['endpoint_tested']}")
            print(f"  -> Data Source             : {result['source']}")
            print(f"  -> Geographic Level        : {result['geographic_level']}")
            print(f"  -> Records Retrieved       : {result['total_records']}")

        print()
        print("  Sample Normalized Macro Indicators:")
        format_table(result["records"])
        print()

        if result["is_fallback"]:
            print("[NOTE] Fallback data was used. If testing live connectivity only, run with --live-only.")
        else:
            print("[STATUS] Live FAOSTAT API verification succeeded!")

    except FAOSTATItemNotFoundError as e:
        print(f"\n [UNSUPPORTED COMMODITY]: {e}\n")
        sys.exit(2)

    except FAOSTATAPIError as e:
        print(f"\n [LIVE API FAILURE] Failed to query live FAOSTAT API:")
        print(f"{e}\n")
        print(" Root Cause Analysis:")
        print(" 1. The official FAOSTAT endpoint (https://fenixservices.fao.org/faostat/api/v1/en/data/QCL)")
        print("    in Rome is currently timing out or restricting unauthenticated requests.")
        print(" 2. To use live authenticated access, obtain a JWT Bearer token from the FAOSTAT")
        print("    Developer Portal (https://www.fao.org/faostat/en/#data) and pass --token <token>.")
        print(" 3. When running in normal mode (without --live-only), the application uses the official")
        print("    FAOSTAT Indian agricultural benchmark snapshot to ensure continuous functionality.\n")
        sys.exit(1)

    except FAOSTATError as e:
        print(f"\n [FAOSTAT ERROR]: {e}\n")
        sys.exit(1)

    except Exception as e:
        print(f"\n [UNEXPECTED ERROR]: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
