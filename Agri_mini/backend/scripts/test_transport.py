"""
Manual Verification Script for Phase 7: Transportation Cost & Logistics Module

Tests road routing and transportation cost calculations between:
Origin: Thrissur, Kerala (10.5276 N, 76.2144 E)
Destination: Kochi, Kerala (9.9312 N, 76.2673 E)
Quantity: 1000 kg
Vehicle: mini_truck
"""

import sys
import os
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.schemas.transport import TransportEstimateRequest
from app.services.transport_service import TransportService, DEFAULT_VEHICLE_PROFILES
from app.services.routing_service import RoutingDataService, RoutingError, NoRouteFoundError, RoutingAPIError


def run_transport_verification():
    print("=" * 80)
    print("AGRI_MINI — PHASE 7: TRANSPORTATION COST & LOGISTICS VERIFICATION")
    print("=" * 80)

    # 1. Display available vehicle profiles
    print("\n[1] Configured Agricultural Vehicle Profiles:")
    print("-" * 80)
    for code, profile in DEFAULT_VEHICLE_PROFILES.items():
        print(
            f"  - {profile.type_code:<12} | {profile.display_name:<48} | "
            f"Cap: {profile.capacity_kg:>5.0f} kg | Mileage: {profile.fuel_efficiency_km_per_litre:>4.1f} km/L | "
            f"Maint: Rs {profile.maintenance_cost_per_km:>4.1f}/km | Driver: Rs {profile.driver_base_cost:>6.1f}"
        )

    # 2. Setup Test Request: Thrissur -> Kochi
    origin_name = "Thrissur, Kerala"
    origin_lat, origin_lon = 10.5276, 76.2144

    destination_name = "Kochi, Kerala"
    dest_lat, dest_lon = 9.9312, 76.2673

    quantity_kg = 1000.0
    vehicle_type = "mini_truck"
    fuel_price = 95.0
    toll_charges = 0.0
    other_charges = 0.0

    print(f"\n[2] Executing Route & Logistics Calculation:")
    print(f"  Origin       : {origin_name} ({origin_lat}, {origin_lon})")
    print(f"  Destination  : {destination_name} ({dest_lat}, {dest_lon})")
    print(f"  Quantity     : {quantity_kg:.1f} kg ({quantity_kg / 100.0:.1f} quintals)")
    print(f"  Vehicle Type : {vehicle_type} (Fuel @ Rs {fuel_price:.2f}/L)")
    print("-" * 80)

    service = TransportService()
    request = TransportEstimateRequest(
        origin_name=origin_name,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_name=destination_name,
        destination_lat=dest_lat,
        destination_lon=dest_lon,
        quantity_kg=quantity_kg,
        vehicle_type=vehicle_type,
        fuel_price_per_litre=fuel_price,
        toll_charges=toll_charges,
        other_charges=other_charges,
    )

    try:
        response = service.estimate_cost_from_coordinates(request)
        print("\n[LIVE ROUTE SUCCESS]")
        print("=" * 80)
        print(f"  Provider                     : {response.routing_provider}")
        print(f"  Cost Estimation Designation : {response.cost_type.upper()}")
        print("-" * 80)
        print(f"  Road Distance                : {response.distance_km:.2f} km")
        print(f"  Estimated Transit Duration   : {response.estimated_duration_minutes:.2f} minutes ({response.estimated_duration_minutes / 60.0:.2f} hours)")
        print(f"  Transport Quantity           : {response.quantity_kg:.2f} kg ({response.quantity_quintals:.2f} quintals)")
        print(f"  Vehicle Selected             : {response.vehicle_display_name} ({response.vehicle_type})")
        print(f"  Vehicle Capacity             : {response.vehicle_capacity_kg:.2f} kg")
        print(f"  Trips Required               : {response.number_of_trips}")
        print("-" * 80)
        print("  Cost Breakdown (Per Trip):")
        print(f"    - Fuel Efficiency          : {response.fuel_efficiency_km_per_litre:.2f} km/L")
        print(f"    - Fuel Consumed            : {response.fuel_required_litres:.2f} Litres")
        print(f"    - Fuel Price               : Rs {response.fuel_price_per_litre:.2f} / L")
        print(f"    - Fuel Cost                : Rs {response.fuel_cost:.2f}")
        print(f"    - Maintenance & Wear Cost  : Rs {response.maintenance_cost:.2f}")
        print(f"    - Driver Base Wage         : Rs {response.driver_cost:.2f}")
        print(f"    - Toll Charges             : Rs {response.toll_charges:.2f}")
        print(f"    - Misc / Loading Charges   : Rs {response.other_charges:.2f}")
        print(f"    - Single Trip Subtotal     : Rs {response.single_trip_cost:.2f}")
        print("-" * 80)
        print(f"  TOTAL TRANSPORTATION COST    : Rs {response.total_transport_cost:.2f} {response.currency}")
        print(f"  Unit Cost Per Kilogram       : Rs {response.transport_cost_per_kg:.2f} / kg")
        print(f"  Unit Cost Per Quintal        : Rs {response.transport_cost_per_quintal:.2f} / quintal")
        print("=" * 80)

        # 3. Multi-Trip Critical Scenario (3000 kg with 1500 kg capacity)
        print("\n[3] Verification: Multi-Trip Scenario (3000 kg Payload):")
        print("-" * 80)
        req_multi = TransportEstimateRequest(
            origin_name=origin_name,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_name=destination_name,
            destination_lat=dest_lat,
            destination_lon=dest_lon,
            quantity_kg=3000.0,
            vehicle_type=vehicle_type,
            fuel_price_per_litre=fuel_price,
        )
        res_multi = service.estimate_cost_from_coordinates(req_multi)
        print(f"  Quantity: {res_multi.quantity_kg:.0f} kg | Capacity: {res_multi.vehicle_capacity_kg:.0f} kg")
        print(f"  Trips Computed               : {res_multi.number_of_trips} (Expected: 2)")
        print(f"  Single Trip Cost             : Rs {res_multi.single_trip_cost:.2f}")
        print(f"  Total Cost (2 Trips)         : Rs {res_multi.total_transport_cost:.2f}")
        print(f"  Cost Per Quintal (30 qtl)    : Rs {res_multi.transport_cost_per_quintal:.2f} / quintal")
        print(f"  Verification Check           : {'PASSED' if res_multi.number_of_trips == 2 and res_multi.total_transport_cost == round(res_multi.single_trip_cost * 2, 2) else 'FAILED'}")
        print("=" * 80)

    except RoutingAPIError as rae:
        print(f"\n[CONTROLLED ROUTING API ERROR]: {rae}")
    except NoRouteFoundError as nrfe:
        print(f"\n[CONTROLLED NO ROUTE FOUND]: {nrfe}")
    except Exception as exc:
        print(f"\n[ERROR]: Unexpected calculation failure: {exc}")


if __name__ == "__main__":
    run_transport_verification()
