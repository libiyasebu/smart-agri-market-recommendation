import sys
import argparse
from pathlib import Path

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.weather_service import (
    WeatherDataService,
    WeatherError,
    WeatherAPIError,
    InvalidCoordinatesError,
)


def print_separator(char="=", length=105):
    print(char * length)


def format_table(forecasts):
    """Prints a clean tabular representation of normalized daily weather records."""
    if not forecasts:
        print("  No weather records returned.")
        return

    header = (
        f"{'#':<3} | {'Date':<12} | {'Mean Temp':<11} | {'Min Temp':<10} | {'Max Temp':<10} | "
        f"{'Humidity':<10} | {'Precip (mm)':<13} | {'Rain (mm)':<11} | {'Condition':<20}"
    )
    print_separator("-", len(header))
    print(header)
    print_separator("-", len(header))

    for idx, f in enumerate(forecasts, 1):
        mean_t = f"{f['temp_mean_celsius']} °C" if f['temp_mean_celsius'] is not None else "N/A"
        min_t = f"{f['temp_min_celsius']} °C" if f['temp_min_celsius'] is not None else "N/A"
        max_t = f"{f['temp_max_celsius']} °C" if f['temp_max_celsius'] is not None else "N/A"
        hum = f"{f['humidity_mean_pct']} %" if f['humidity_mean_pct'] is not None else "N/A"
        precip = f"{f['precipitation_mm']} mm" if f['precipitation_mm'] is not None else "N/A"
        rain = f"{f['rain_mm']} mm" if f['rain_mm'] is not None else "N/A"
        cond = f"{f['weather_condition']} ({f['weather_code']})" if f['weather_code'] is not None else "N/A"

        row = (
            f"{idx:<3} | {f['date']:<12} | {mean_t:<11} | {min_t:<10} | {max_t:<10} | "
            f"{hum:<10} | {precip:<13} | {rain:<11} | {cond:<20}"
        )
        print(row)
    print_separator("-", len(header))


def main():
    parser = argparse.ArgumentParser(description="Test Open-Meteo Weather Data Acquisition Service")
    # Default coordinates: Thrissur, Kerala (Lat: 10.5276, Lon: 76.2144)
    parser.add_argument("--lat", type=float, default=10.5276, help="Latitude (default: 10.5276 for Thrissur, Kerala)")
    parser.add_argument("--lon", type=float, default=76.2144, help="Longitude (default: 76.2144 for Thrissur, Kerala)")
    parser.add_argument("--location-name", type=str, default="Thrissur, Kerala", help="Descriptive name of test location")
    parser.add_argument("--days", type=int, default=7, help="Number of forecast days (default: 7)")
    parser.add_argument("--start-date", type=str, default=None, help="Start date YYYY-MM-DD (optional)")
    parser.add_argument("--end-date", type=str, default=None, help="End date YYYY-MM-DD (optional)")

    args = parser.parse_args()

    print_separator()
    print("  OPEN-METEO WEATHER DATA ACQUISITION TEST (Phase 2B)")
    print_separator()

    service = WeatherDataService()
    print(f"  Target Location   : {args.location_name}")
    print(f"  Coordinates       : Latitude {args.lat}, Longitude {args.lon}")
    print(f"  Open-Meteo URL    : {service.base_url}")
    if args.start_date and args.end_date:
        print(f"  Query Range       : {args.start_date} to {args.end_date}")
    else:
        print(f"  Forecast Window   : Next {args.days} Days")
    print_separator()

    try:
        result = service.fetch_weather(
            latitude=args.lat,
            longitude=args.lon,
            start_date=args.start_date,
            end_date=args.end_date,
            forecast_days=args.days,
        )

        loc = result["location"]
        print(f" [SUCCESS] Successfully retrieved weather from Open-Meteo!")
        print(f"  Resolved Location : Lat {loc['latitude']}, Lon {loc['longitude']}, Elev {loc['elevation']}m, Timezone {loc['timezone']}")
        print(f"  Total Days Fetched: {result['total_days']}")
        print()
        print("  Sample Normalized Weather Records (Agri & Transport Metrics):")
        format_table(result["daily_forecasts"])
        print()
        print("[STATUS] Phase 2B weather data-source test passed successfully!")

    except InvalidCoordinatesError as e:
        print(f"\n [COORDINATES ERROR]: {e}\n")
        sys.exit(2)

    except WeatherAPIError as e:
        print(f"\n [API ERROR] Failed to fetch weather: {e}\n")
        sys.exit(1)

    except WeatherError as e:
        print(f"\n [WEATHER ERROR]: {e}\n")
        sys.exit(1)

    except Exception as e:
        print(f"\n [UNEXPECTED ERROR]: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
