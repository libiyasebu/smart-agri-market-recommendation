import sys
import argparse
from pathlib import Path

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.routing_service import (
    RoutingDataService,
    RoutingError,
    InvalidCoordinatesError,
    NoRouteFoundError,
    RoutingAPIError,
)


def print_separator(char="=", length=100):
    print(char * length)


def main():
    parser = argparse.ArgumentParser(description="Test OSRM / OpenStreetMap Routing and Distance Acquisition Service")
    # Default: Thrissur, Kerala to Kochi, Kerala
    parser.add_argument("--origin-lat", type=float, default=10.5276, help="Origin Latitude (default: 10.5276 for Thrissur)")
    parser.add_argument("--origin-lon", type=float, default=76.2144, help="Origin Longitude (default: 76.2144 for Thrissur)")
    parser.add_argument("--origin-name", type=str, default="Thrissur, Kerala", help="Origin descriptive name")
    parser.add_argument("--dest-lat", type=float, default=9.9312, help="Destination Latitude (default: 9.9312 for Kochi)")
    parser.add_argument("--dest-lon", type=float, default=76.2673, help="Destination Longitude (default: 76.2673 for Kochi)")
    parser.add_argument("--dest-name", type=str, default="Kochi, Kerala", help="Destination descriptive name")

    args = parser.parse_args()

    print_separator()
    print("  OSRM / OPENSTREETMAP ROUTING & DISTANCE ACQUISITION TEST (Phase 2D)")
    print_separator()

    service = RoutingDataService()
    print(f"  Routing Service URL : {service.base_url}")
    print(f"  Driving Profile     : {service.profile}")
    print(f"  Origin Location     : {args.origin_name} (Lat: {args.origin_lat}, Lon: {args.origin_lon})")
    print(f"  Destination Location: {args.dest_name} (Lat: {args.dest_lat}, Lon: {args.dest_lon})")
    print_separator()

    try:
        result = service.get_route(
            origin_lat=args.origin_lat,
            origin_lon=args.origin_lon,
            dest_lat=args.dest_lat,
            dest_lon=args.dest_lon,
        )

        geom = result["geometry"]
        sample_pts = geom["coordinates"]
        start_pt = sample_pts[0] if sample_pts else "N/A"
        end_pt = sample_pts[-1] if sample_pts else "N/A"

        print(" [LIVE API SUCCESS] Route successfully retrieved from OSRM / OpenStreetMap!")
        print_separator("-")
        print(f"  Origin              : {args.origin_name} ({result['origin']['latitude']}, {result['origin']['longitude']})")
        print(f"  Destination         : {args.dest_name} ({result['destination']['latitude']}, {result['destination']['longitude']})")
        print(f"  Road Distance       : {result['distance_km']} km")
        print(f"  Estimated Duration  : {result['duration_minutes']} minutes (~{result['duration_hours']} hours)")
        print(f"  Routing Provider    : {result['provider']}")
        print(f"  Route Geometry      : {geom['type']} with {geom['total_points']} waypoints")
        print(f"  Start Waypoint (Lon, Lat) : {start_pt}")
        print(f"  End Waypoint   (Lon, Lat) : {end_pt}")
        print_separator("-")
        print()
        print("[STATUS] Phase 2D routing data-source test passed successfully!")

    except InvalidCoordinatesError as e:
        print(f"\n [INVALID COORDINATES ERROR]: {e}\n")
        sys.exit(2)

    except NoRouteFoundError as e:
        print(f"\n [NO ROUTE FOUND ERROR]: {e}\n")
        sys.exit(1)

    except RoutingAPIError as e:
        print(f"\n [LIVE API FAILURE] Failed to compute route from OSRM:")
        print(f"{e}\n")
        sys.exit(1)

    except RoutingError as e:
        print(f"\n [ROUTING ERROR]: {e}\n")
        sys.exit(1)

    except Exception as e:
        print(f"\n [UNEXPECTED ERROR]: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
