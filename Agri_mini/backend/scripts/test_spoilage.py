"""
Manual Verification Script for Phase 8: Weather-Aware Spoilage Risk Estimation

Tests transit spoilage risk and physical loss percentage between:
Commodity: Tomato
Origin: Thrissur, Kerala (10.5276 N, 76.2144 E)
Destination: Kochi, Kerala (9.9312 N, 76.2673 E)
Transport Date: 2026-08-28
"""

import sys
from pathlib import Path
from datetime import date

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.database import SessionLocal
from app.schemas.spoilage import SpoilageEstimateRequest
from app.services.spoilage_service import SpoilageService, DEFAULT_PERISHABILITY_PROFILES
from app.services.routing_service import RoutingError, NoRouteFoundError, RoutingAPIError


def run_spoilage_verification():
    print("=" * 80)
    print("AGRI_MINI — PHASE 8: WEATHER-AWARE SPOILAGE RISK ESTIMATION VERIFICATION")
    print("=" * 80)

    # 1. Display Configured Perishability Profiles
    print("\n[1] Configured Commodity Perishability Profiles:")
    print("-" * 80)
    for code, profile in DEFAULT_PERISHABILITY_PROFILES.items():
        print(
            f"  - {profile.display_name:<14} | Base Score: {profile.base_perishability_score:>4.1f}/100 | "
            f"Opt Temp: {profile.preferred_temp_min_c:>4.1f}°C to {profile.preferred_temp_max_c:>4.1f}°C | "
            f"Heat Sens: {profile.heat_sensitivity:>3.1f}x | Hum Sens: {profile.humidity_sensitivity:>3.1f}x | "
            f"Transit Sens: {profile.transit_time_sensitivity:>3.1f}x | Max Loss: {profile.max_loss_potential_pct:>4.1f}%"
        )

    # 2. Setup Test Request: Tomato, Thrissur -> Kochi
    commodity = "Tomato"
    origin_name = "Thrissur, Kerala"
    origin_lat, origin_lon = 10.5276, 76.2144

    destination_name = "Kochi, Kerala"
    dest_lat, dest_lon = 9.9312, 76.2673
    transport_date = date(2026, 8, 28)

    print(f"\n[2] Executing Spoilage Risk Estimation:")
    print(f"  Commodity     : {commodity}")
    print(f"  Origin        : {origin_name} ({origin_lat}, {origin_lon})")
    print(f"  Destination   : {destination_name} ({dest_lat}, {dest_lon})")
    print(f"  Transit Date  : {transport_date.isoformat()}")
    print("-" * 80)

    service = SpoilageService()
    request = SpoilageEstimateRequest(
        commodity=commodity,
        origin_name=origin_name,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_name=destination_name,
        destination_lat=dest_lat,
        destination_lon=dest_lon,
        transport_date=transport_date,
    )

    db = None
    try:
        db = SessionLocal()
    except Exception:
        db = None

    try:
        response = service.estimate_spoilage_from_coordinates(request, db=db)
        print("\n[SPOILAGE ESTIMATION SUCCESS]")
        print("=" * 80)
        print(f"  Commodity Evaluated          : {response.commodity}")
        print(f"  Origin                       : {response.origin}")
        print(f"  Destination                  : {response.destination}")
        print(f"  Methodology                  : {response.estimation_type}")
        print(f"  Routing Provider             : {response.routing_provider}")
        print("-" * 80)
        print("  Route & Transit Metrics:")
        print(f"    - Road Distance            : {response.distance_km:.2f} km")
        print(f"    - Transit Travel Duration  : {response.transit_duration_minutes:.2f} minutes ({response.transit_duration_minutes / 60.0:.2f} hours)")
        print("-" * 80)
        print("  Agro-Weather Conditions:")
        print(f"    - Temperature (Mean)       : {response.weather.temperature_mean_c:.2f} °C")
        print(f"    - Temperature (Peak Max)   : {response.weather.temperature_max_c:.2f} °C")
        print(f"    - Relative Humidity        : {response.weather.humidity_pct:.2f} %")
        print(f"    - Expected Precipitation   : {response.weather.precipitation_mm:.2f} mm")
        print(f"    - Weather Source           : {response.weather_source} (Matched: {response.weather_matched})")
        print("-" * 80)
        print("  Contributing Risk Factors (Stress Breakdown [0-100]):")
        print(f"    - Base Perishability       : {response.risk_factors.base_perishability:.1f} / 100")
        print(f"    - Temperature Stress       : {response.risk_factors.temperature_stress:.1f} / 100")
        print(f"    - Humidity Stress          : {response.risk_factors.humidity_stress:.1f} / 100")
        print(f"    - Transit Duration Stress  : {response.risk_factors.transit_time_stress:.1f} / 100")
        print(f"    - Rain / Moisture Stress   : {response.risk_factors.rain_stress:.1f} / 100")
        print("-" * 80)
        print(f"  FINAL SPOILAGE RISK SCORE    : {response.risk_score:.1f} / 100.0")
        print(f"  RISK LEVEL CATEGORY          : {response.risk_level}")
        print(f"  ESTIMATED TRANSIT LOSS       : {response.estimated_spoilage_pct:.2f} % of cargo volume")
        print("=" * 80)

        # 3. Comparative High-Stress Scenario (Banana under severe heat)
        print("\n[3] Comparative Verification: High-Stress Banana Scenario (38°C, 6h Transit):")
        print("-" * 80)
        req_banana = SpoilageEstimateRequest(
            commodity="Banana",
            origin_name=origin_name,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_name=destination_name,
            destination_lat=dest_lat,
            destination_lon=dest_lon,
            transport_date=transport_date,
            temperature_override_c=38.0,
            humidity_override_pct=90.0,
        )
        res_banana = service.estimate_spoilage_from_coordinates(req_banana, db=db)
        print(f"  Commodity: {res_banana.commodity} | Temp: {res_banana.weather.temperature_mean_c}°C | Hum: {res_banana.weather.humidity_pct}%")
        print(f"  Risk Score                   : {res_banana.risk_score:.1f} / 100.0")
        print(f"  Risk Level                   : {res_banana.risk_level}")
        print(f"  Estimated Transit Loss       : {res_banana.estimated_spoilage_pct:.2f} %")
        print(f"  Comparison Check             : {'PASSED' if res_banana.risk_score > response.risk_score else 'FAILED'}")
        print("=" * 80)

    except RoutingAPIError as rae:
        print(f"\n[CONTROLLED ROUTING API ERROR]: {rae}")
    except NoRouteFoundError as nrfe:
        print(f"\n[CONTROLLED NO ROUTE FOUND]: {nrfe}")
    except Exception as exc:
        print(f"\n[ERROR]: Unexpected spoilage estimation failure: {exc}")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    run_spoilage_verification()
