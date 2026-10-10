from datetime import date
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class QuantityBreakdown(BaseModel):
    """
    Physical produce weight and spoilage volume breakdown.
    """
    original_kg: float = Field(..., gt=0, description="Total harvest volume loaded at origin in kilograms")
    original_quintals: float = Field(..., gt=0, description="Total harvest volume loaded at origin in quintals (kg / 100)")
    spoilage_pct: float = Field(..., ge=0.0, le=100.0, description="Estimated transit quality deterioration / loss percentage")
    spoiled_kg: float = Field(..., ge=0.0, description="Estimated lost / unsellable produce quantity in kilograms")
    sellable_kg: float = Field(..., ge=0.0, description="Expected sellable produce quantity arriving at market in kilograms")
    sellable_quintals: float = Field(..., ge=0.0, description="Expected sellable produce quantity arriving at market in quintals")


class PriceInfo(BaseModel):
    """
    Predicted crop market price information.
    """
    predicted_modal_price_per_quintal: float = Field(..., gt=0, description="Predicted modal crop price in INR per quintal")
    unit: str = Field(default="INR/quintal", description="Currency per quintal")
    model_used: str = Field(..., description="ML production model used for price forecasting")
    latest_known_price: Optional[float] = Field(None, description="Most recent historical modal price in database")


class SpoilageSummary(BaseModel):
    """
    Agro-weather and transit spoilage risk assessment summary.
    """
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Normalized transit spoilage risk score [0-100]")
    risk_level: str = Field(..., description="Categorical risk tier: LOW, MODERATE, HIGH, VERY HIGH")
    estimated_spoilage_pct: float = Field(..., ge=0.0, le=100.0, description="Estimated transit volume loss percentage")
    estimation_type: str = Field(default="weather-and-transit heuristic", description="Methodology designation")


class TransportSummary(BaseModel):
    """
    Road routing and logistics cost summary.
    """
    distance_km: float = Field(..., ge=0.0, description="Road driving distance in kilometers")
    transit_duration_minutes: float = Field(..., ge=0.0, description="Estimated driving duration in minutes")
    vehicle_type: str = Field(..., description="Vehicle type code (e.g. mini_truck)")
    vehicle_display_name: str = Field(..., description="Vehicle display name")
    number_of_trips: int = Field(..., ge=1, description="Total required vehicle round-trips")
    total_transport_cost: float = Field(..., ge=0.0, description="Total logistics transportation expense in INR")
    routing_provider: str = Field(default="OSRM (OpenStreetMap)", description="Route data provider")


class FinancialBreakdown(BaseModel):
    """
    Transparent financial revenue, expense, and net return breakdown.
    """
    gross_revenue_before_spoilage: float = Field(..., description="Hypothetical revenue assuming 0% transit loss (original_quintals * price)")
    spoilage_value_loss: float = Field(..., ge=0.0, description="Monetary value lost due to transit deterioration (spoiled_quintals * price)")
    gross_revenue_after_spoilage: float = Field(..., description="Realized gross revenue from sellable produce (sellable_quintals * price)")
    transportation_cost: float = Field(..., ge=0.0, description="Total road freight and logistics expense")
    expected_net_return: float = Field(..., description="Expected net revenue after subtracting transportation from post-spoilage gross revenue")
    production_cost: Optional[float] = Field(None, ge=0.0, description="Optional user-provided cultivation/production cost")
    expected_profit: Optional[float] = Field(None, description="Expected accounting profit (expected_net_return - production_cost) if production_cost provided")
    net_return_per_kg: float = Field(..., description="Expected net return per kilogram loaded (INR/kg)")
    net_return_per_quintal: float = Field(..., description="Expected net return per quintal loaded (INR/quintal)")


class ProfitEvaluationRequest(BaseModel):
    """
    Request schema for comprehensive expected profit and net return evaluation.
    """
    commodity: str = Field(..., description="Crop/commodity name (e.g. Tomato, Onion, Potato)", json_schema_extra={"example": "Tomato"})
    market: str = Field(..., description="Destination APMC market / mandi name", json_schema_extra={"example": "Kochi (Ernakulam) Market"})
    district: str = Field(..., description="Destination market district", json_schema_extra={"example": "Ernakulam"})
    state: str = Field(default="Kerala", description="State of the market", json_schema_extra={"example": "Kerala"})
    variety: str = Field(default="Hybrid", description="Crop cultivar / variety", json_schema_extra={"example": "Hybrid"})

    prediction_date: date = Field(..., description="Target market arrival and selling date (YYYY-MM-DD)", json_schema_extra={"example": "2026-08-28"})

    origin_name: str = Field(default="Origin Location", description="Farmer farm / origin location", json_schema_extra={"example": "Thrissur, Kerala"})
    origin_lat: float = Field(..., ge=-90.0, le=90.0, description="Origin latitude", json_schema_extra={"example": 10.5276})
    origin_lon: float = Field(..., ge=-180.0, le=180.0, description="Origin longitude", json_schema_extra={"example": 76.2144})

    destination_name: str = Field(default="Destination Market", description="Destination mandi location name", json_schema_extra={"example": "Kochi, Kerala"})
    destination_lat: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude", json_schema_extra={"example": 9.9312})
    destination_lon: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude", json_schema_extra={"example": 76.2673})

    quantity_kg: float = Field(..., gt=0.0, description="Total harvest quantity in kilograms", json_schema_extra={"example": 1000.0})

    vehicle_type: str = Field(default="mini_truck", description="Vehicle profile code: three_wheeler, mini_truck, pickup, medium_truck, large_truck", json_schema_extra={"example": "mini_truck"})
    fuel_price_per_litre: float = Field(default=95.0, gt=0.0, description="Fuel rate in INR per litre (configured estimate)", json_schema_extra={"example": 95.0})
    toll_charges: float = Field(default=0.0, ge=0.0, description="Total toll gate charges per trip in INR", json_schema_extra={"example": 0.0})
    other_charges: float = Field(default=0.0, ge=0.0, description="Loading/unloading/misc charges per trip in INR", json_schema_extra={"example": 0.0})

    production_cost: Optional[float] = Field(default=None, ge=0.0, description="Optional total cultivation / production cost in INR", json_schema_extra={"example": 10000.0})

    # Optional simulation overrides
    temperature_override_c: Optional[float] = Field(default=None, description="Optional explicit transit temperature in Celsius")
    humidity_override_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Optional explicit relative humidity percentage")

    @field_validator("commodity", "market", "district", "state", "variety")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned


class ProfitEvaluationResponse(BaseModel):
    """
    Comprehensive financial evaluation response for selling produce at a destination market.
    """
    status: str = Field(default="success", description="Response status")
    commodity: str = Field(..., description="Crop commodity evaluated")
    variety: str = Field(..., description="Crop variety")
    market: str = Field(..., description="Destination market name")
    district: str = Field(..., description="Destination market district")
    state: str = Field(..., description="Destination market state")
    origin: str = Field(..., description="Origin farm / location")
    destination: str = Field(..., description="Destination mandi location")
    prediction_date: date = Field(..., description="Market arrival date evaluated")

    quantity: QuantityBreakdown = Field(..., description="Produce volume and transit spoilage breakdown")
    price: PriceInfo = Field(..., description="Predicted price details")
    spoilage: SpoilageSummary = Field(..., description="Transit spoilage risk summary")
    transport: TransportSummary = Field(..., description="Logistics transport summary")
    financials: FinancialBreakdown = Field(..., description="Financial revenue, expense, and net return breakdown")

    currency: str = Field(default="INR", description="Currency unit")
    result_type: str = Field(..., description="Evaluation designation: expected_net_return_without_production_cost or expected_profit_with_production_cost")
    evaluation_notes: str = Field(..., description="Transparent explanatory notes on cost factors and revenue calculations")
    evaluation_timestamp: str = Field(..., description="ISO execution timestamp")
