import math
from typing import Dict, Any, Optional, List
from app.services.routing_service import RoutingDataService, RoutingError, InvalidCoordinatesError, NoRouteFoundError, RoutingAPIError
from app.schemas.transport import VehicleProfile, TransportEstimateRequest, TransportEstimateResponse


# Standard Agricultural Transport Vehicle Profiles
DEFAULT_VEHICLE_PROFILES: Dict[str, VehicleProfile] = {
    "three_wheeler": VehicleProfile(
        type_code="three_wheeler",
        display_name="Three-Wheeler Cargo Auto",
        capacity_kg=500.0,
        fuel_efficiency_km_per_litre=25.0,
        maintenance_cost_per_km=2.0,
        driver_base_cost=250.0,
    ),
    "mini_truck": VehicleProfile(
        type_code="mini_truck",
        display_name="Mini Truck (e.g., Tata Ace / Mahindra Bolero Maxx)",
        capacity_kg=1500.0,
        fuel_efficiency_km_per_litre=12.0,
        maintenance_cost_per_km=4.0,
        driver_base_cost=500.0,
    ),
    "pickup": VehicleProfile(
        type_code="pickup",
        display_name="Pickup Truck (e.g., Mahindra Pik-Up / Ashok Leyland Dost)",
        capacity_kg=2500.0,
        fuel_efficiency_km_per_litre=10.0,
        maintenance_cost_per_km=5.5,
        driver_base_cost=700.0,
    ),
    "medium_truck": VehicleProfile(
        type_code="medium_truck",
        display_name="Medium Commercial Truck (e.g., Eicher Pro / Tata 407)",
        capacity_kg=5000.0,
        fuel_efficiency_km_per_litre=7.0,
        maintenance_cost_per_km=8.0,
        driver_base_cost=1200.0,
    ),
    "large_truck": VehicleProfile(
        type_code="large_truck",
        display_name="Heavy Cargo Truck (10-Wheeler / Multi-Axle)",
        capacity_kg=12000.0,
        fuel_efficiency_km_per_litre=4.0,
        maintenance_cost_per_km=14.0,
        driver_base_cost=2000.0,
    ),
}


class TransportService:
    """
    Transportation and logistics cost estimation service for agricultural produce.
    Integrates with OSRM road routing and applies vehicle mechanics formulas.
    """

    def __init__(
        self,
        routing_service: Optional[RoutingDataService] = None,
        vehicle_profiles: Optional[Dict[str, VehicleProfile]] = None,
    ):
        self.routing_service = routing_service or RoutingDataService()
        self.vehicle_profiles = vehicle_profiles or DEFAULT_VEHICLE_PROFILES

    def get_vehicle_profile(self, vehicle_type: str) -> VehicleProfile:
        """Retrieves vehicle specifications or raises ValueError for unsupported types."""
        v_key = vehicle_type.strip().lower()
        if v_key not in self.vehicle_profiles:
            supported = ", ".join(self.vehicle_profiles.keys())
            raise ValueError(
                f"Unsupported vehicle_type '{vehicle_type}'. Supported vehicle types are: {supported}"
            )
        return self.vehicle_profiles[v_key]

    def calculate_transport_cost(
        self,
        distance_km: float,
        duration_minutes: float,
        quantity_kg: float,
        vehicle_type: str = "mini_truck",
        fuel_price_per_litre: float = 95.0,
        toll_charges: float = 0.0,
        other_charges: float = 0.0,
        origin_name: str = "Origin",
        destination_name: str = "Destination",
        routing_provider: str = "OSRM (OpenStreetMap)",
    ) -> TransportEstimateResponse:
        """
        Pure calculation function based on road distance, payload, and vehicle specifications.
        """
        # Validate inputs
        if distance_km < 0:
            raise ValueError(f"distance_km cannot be negative ({distance_km})")
        if quantity_kg <= 0:
            raise ValueError(f"quantity_kg must be strictly greater than 0 ({quantity_kg})")
        if fuel_price_per_litre <= 0:
            raise ValueError(f"fuel_price_per_litre must be greater than 0 ({fuel_price_per_litre})")
        if toll_charges < 0:
            raise ValueError(f"toll_charges cannot be negative ({toll_charges})")
        if other_charges < 0:
            raise ValueError(f"other_charges cannot be negative ({other_charges})")

        profile = self.get_vehicle_profile(vehicle_type)

        # 1. Number of trips calculation: ceil(quantity_kg / capacity_kg)
        number_of_trips = math.ceil(quantity_kg / profile.capacity_kg)

        # 2. Fuel consumption and cost per trip
        fuel_required_litres = distance_km / profile.fuel_efficiency_km_per_litre
        fuel_cost = fuel_required_litres * fuel_price_per_litre

        # 3. Maintenance and operating cost per trip
        maintenance_cost = distance_km * profile.maintenance_cost_per_km

        # 4. Driver base cost per trip
        driver_cost = profile.driver_base_cost

        # 5. Single trip cost breakdown
        single_trip_cost = round(
            fuel_cost
            + maintenance_cost
            + driver_cost
            + toll_charges
            + other_charges,
            2,
        )

        # 6. Total transport cost for all required round-trips
        total_transport_cost = round(single_trip_cost * number_of_trips, 2)

        # 7. Unit costs per kg and per quintal
        transport_cost_per_kg = total_transport_cost / quantity_kg
        quantity_quintals = quantity_kg / 100.0
        transport_cost_per_quintal = total_transport_cost / quantity_quintals

        return TransportEstimateResponse(
            status="success",
            origin=origin_name,
            destination=destination_name,
            distance_km=round(distance_km, 2),
            estimated_duration_minutes=round(duration_minutes, 2),
            quantity_kg=round(quantity_kg, 2),
            quantity_quintals=round(quantity_quintals, 2),
            vehicle_type=profile.type_code,
            vehicle_display_name=profile.display_name,
            vehicle_capacity_kg=round(profile.capacity_kg, 2),
            number_of_trips=number_of_trips,
            fuel_efficiency_km_per_litre=round(profile.fuel_efficiency_km_per_litre, 2),
            fuel_required_litres=round(fuel_required_litres, 2),
            fuel_price_per_litre=round(fuel_price_per_litre, 2),
            fuel_cost=round(fuel_cost, 2),
            maintenance_cost=round(maintenance_cost, 2),
            driver_cost=round(driver_cost, 2),
            toll_charges=round(toll_charges, 2),
            other_charges=round(other_charges, 2),
            single_trip_cost=round(single_trip_cost, 2),
            total_transport_cost=round(total_transport_cost, 2),
            transport_cost_per_kg=round(transport_cost_per_kg, 2),
            transport_cost_per_quintal=round(transport_cost_per_quintal, 2),
            currency="INR",
            routing_provider=routing_provider,
            cost_type="estimated",
        )

    def estimate_cost_from_coordinates(
        self,
        request: TransportEstimateRequest,
    ) -> TransportEstimateResponse:
        """
        Retrieves actual road driving distance and duration from OSRM,
        then calculates detailed logistics transport expenses.
        """
        route_info = self.routing_service.get_route(
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            dest_lat=request.destination_lat,
            dest_lon=request.destination_lon,
        )

        distance_km = float(route_info["distance_km"])
        duration_minutes = float(route_info["duration_minutes"])
        provider = str(route_info.get("provider", "OSRM (OpenStreetMap)"))

        return self.calculate_transport_cost(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            quantity_kg=request.quantity_kg,
            vehicle_type=request.vehicle_type,
            fuel_price_per_litre=request.fuel_price_per_litre,
            toll_charges=request.toll_charges,
            other_charges=request.other_charges,
            origin_name=request.origin_name,
            destination_name=request.destination_name,
            routing_provider=provider,
        )
