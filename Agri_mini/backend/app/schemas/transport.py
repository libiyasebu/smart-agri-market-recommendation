from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class VehicleProfile(BaseModel):
    """
    Agricultural transport vehicle specification profile.
    """
    type_code: str = Field(..., description="Unique machine-readable vehicle code (e.g. mini_truck)")
    display_name: str = Field(..., description="Human-readable vehicle name")
    capacity_kg: float = Field(..., gt=0, description="Payload weight capacity in kilograms")
    fuel_efficiency_km_per_litre: float = Field(..., gt=0, description="Average fuel economy in km/litre")
    maintenance_cost_per_km: float = Field(..., ge=0, description="Depreciation and maintenance cost per km in INR")
    driver_base_cost: float = Field(..., ge=0, description="Driver wage and trip overhead in INR")


class TransportEstimateRequest(BaseModel):
    """
    Input schema for agricultural transportation cost estimation.
    """
    origin_name: str = Field(default="Origin Location", description="Origin name/mandi (e.g. Thrissur, Kerala)", json_schema_extra={"example": "Thrissur, Kerala"})
    origin_lat: float = Field(..., ge=-90.0, le=90.0, description="Origin latitude", json_schema_extra={"example": 10.5276})
    origin_lon: float = Field(..., ge=-180.0, le=180.0, description="Origin longitude", json_schema_extra={"example": 76.2144})

    destination_name: str = Field(default="Destination Market", description="Destination mandi/market name (e.g. Kochi, Kerala)", json_schema_extra={"example": "Kochi, Kerala"})
    destination_lat: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude", json_schema_extra={"example": 9.9312})
    destination_lon: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude", json_schema_extra={"example": 76.2673})

    quantity_kg: float = Field(..., gt=0, description="Produce quantity in kilograms", json_schema_extra={"example": 1000.0})

    vehicle_type: str = Field(default="mini_truck", description="Vehicle type: three_wheeler, mini_truck, pickup, medium_truck, large_truck", json_schema_extra={"example": "mini_truck"})

    fuel_price_per_litre: float = Field(default=95.0, gt=0, description="Fuel price per litre in INR (configured estimate)", json_schema_extra={"example": 95.0})

    toll_charges: float = Field(default=0.0, ge=0, description="Toll gate charges per trip in INR", json_schema_extra={"example": 0.0})
    other_charges: float = Field(default=0.0, ge=0, description="Loading/unloading or misc charges per trip in INR", json_schema_extra={"example": 0.0})

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle_type(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("vehicle_type cannot be empty")
        return cleaned


class TransportEstimateResponse(BaseModel):
    """
    Detailed transparent calculation breakdown of transportation cost.
    """
    status: str = Field(default="success", description="Status code")
    origin: str = Field(..., description="Origin location label")
    destination: str = Field(..., description="Destination location label")

    # Routing metrics
    distance_km: float = Field(..., description="Road driving distance in kilometers")
    estimated_duration_minutes: float = Field(..., description="Estimated transit duration in minutes")

    # Load metrics
    quantity_kg: float = Field(..., description="Quantity transported in kg")
    quantity_quintals: float = Field(..., description="Quantity transported in quintals (kg / 100)")

    # Vehicle specifications
    vehicle_type: str = Field(..., description="Vehicle type code")
    vehicle_display_name: str = Field(..., description="Vehicle display name")
    vehicle_capacity_kg: float = Field(..., description="Vehicle payload capacity in kg")
    number_of_trips: int = Field(..., description="Total round-trip runs required = ceil(quantity / capacity)")

    # Cost breakdown components (Per Trip)
    fuel_efficiency_km_per_litre: float = Field(..., description="Vehicle fuel efficiency (km/L)")
    fuel_required_litres: float = Field(..., description="Fuel required for single trip (distance / efficiency)")
    fuel_price_per_litre: float = Field(..., description="Fuel price per litre in INR")
    fuel_cost: float = Field(..., description="Fuel expense per trip in INR")

    maintenance_cost: float = Field(..., description="Vehicle wear and operating expense per trip in INR")
    driver_cost: float = Field(..., description="Driver wage and base charge per trip in INR")
    toll_charges: float = Field(..., description="Toll fees per trip in INR")
    other_charges: float = Field(..., description="Miscellaneous charges per trip in INR")

    # Aggregated totals
    single_trip_cost: float = Field(..., description="Total cost for one single vehicle trip in INR")
    total_transport_cost: float = Field(..., description="Grand total transport cost across all required trips in INR")

    # Normalized unit costs
    transport_cost_per_kg: float = Field(..., description="Transportation cost per kilogram in INR/kg")
    transport_cost_per_quintal: float = Field(..., description="Transportation cost per quintal in INR/quintal")

    currency: str = Field(default="INR", description="Currency code")
    routing_provider: str = Field(default="OSRM (OpenStreetMap)", description="Routing calculation source")
    cost_type: str = Field(default="estimated", description="Cost estimate designation")
