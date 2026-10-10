from datetime import date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class CommodityPerishabilityProfile(BaseModel):
    """
    Agricultural commodity perishability and post-harvest sensitivity profile.
    """
    commodity: str = Field(..., description="Unique machine-readable commodity key (e.g., tomato)")
    display_name: str = Field(..., description="Human-readable commodity display name")
    base_perishability_score: float = Field(..., ge=0.0, le=100.0, description="Inherent physiological decay tendency [0-100]")
    preferred_temp_min_c: float = Field(..., description="Minimum optimal transit temperature in Celsius")
    preferred_temp_max_c: float = Field(..., description="Maximum optimal transit temperature in Celsius")
    heat_sensitivity: float = Field(default=1.0, gt=0.0, description="Sensitivity multiplier to ambient temperatures above optimal range")
    humidity_sensitivity: float = Field(default=1.0, gt=0.0, description="Sensitivity multiplier to ambient humidity extremes")
    transit_time_sensitivity: float = Field(default=1.0, gt=0.0, description="Sensitivity multiplier to prolonged transit duration")
    max_loss_potential_pct: float = Field(default=25.0, ge=1.0, le=100.0, description="Theoretical maximum physical loss percentage under extreme transit stress")


class WeatherMetrics(BaseModel):
    """
    Agro-meteorological metrics along transit corridor.
    """
    temperature_mean_c: float = Field(..., description="Mean ambient temperature in Celsius")
    temperature_max_c: float = Field(..., description="Maximum daytime ambient temperature in Celsius")
    humidity_pct: float = Field(..., ge=0.0, le=100.0, description="Mean relative humidity percentage")
    precipitation_mm: float = Field(default=0.0, ge=0.0, description="Expected precipitation / rain in mm")
    source: str = Field(default="Open-Meteo", description="Weather data origin (database, live_api, configured_fallback)")


class RiskFactorsBreakdown(BaseModel):
    """
    Transparent breakdown of contributing environmental and logistics stress factors.
    """
    base_perishability: float = Field(..., ge=0.0, le=100.0, description="Commodity inherent decay factor [0-100]")
    temperature_stress: float = Field(..., ge=0.0, le=100.0, description="Thermal stress index due to heat or chilling [0-100]")
    humidity_stress: float = Field(..., ge=0.0, le=100.0, description="Moisture / relative humidity stress index [0-100]")
    transit_time_stress: float = Field(..., ge=0.0, le=100.0, description="Transit duration exposure stress index [0-100]")
    rain_stress: float = Field(default=0.0, ge=0.0, le=100.0, description="Adverse precipitation impact factor [0-100]")


class SpoilageEstimateRequest(BaseModel):
    """
    Request schema for agricultural transit spoilage risk and loss estimation.
    """
    commodity: str = Field(..., description="Agricultural commodity name (e.g., Tomato, Onion, Potato, Banana, Cabbage, Green Chilli)", json_schema_extra={"example": "Tomato"})
    
    origin_name: str = Field(default="Origin Location", description="Origin name/mandi (e.g. Thrissur, Kerala)", json_schema_extra={"example": "Thrissur, Kerala"})
    origin_lat: float = Field(..., ge=-90.0, le=90.0, description="Origin latitude", json_schema_extra={"example": 10.5276})
    origin_lon: float = Field(..., ge=-180.0, le=180.0, description="Origin longitude", json_schema_extra={"example": 76.2144})

    destination_name: str = Field(default="Destination Market", description="Destination mandi/market name (e.g. Kochi, Kerala)", json_schema_extra={"example": "Kochi, Kerala"})
    destination_lat: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude", json_schema_extra={"example": 9.9312})
    destination_lon: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude", json_schema_extra={"example": 76.2673})

    transport_date: date = Field(..., description="Date of transit (YYYY-MM-DD)", json_schema_extra={"example": "2026-08-28"})

    # Optional manual weather override for simulation / testing
    temperature_override_c: Optional[float] = Field(default=None, description="Optional explicit ambient temperature override in Celsius")
    humidity_override_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Optional explicit relative humidity override percentage")

    @field_validator("commodity")
    @classmethod
    def validate_commodity(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("commodity cannot be empty")
        return cleaned


class SpoilageEstimateResponse(BaseModel):
    """
    Detailed transparent calculation response for agricultural spoilage risk and expected loss percentage.
    """
    status: str = Field(default="success", description="Status code")
    commodity: str = Field(..., description="Commodity evaluated")
    
    origin: str = Field(..., description="Origin location label")
    destination: str = Field(..., description="Destination location label")

    distance_km: float = Field(..., description="Road transit distance in kilometers")
    transit_duration_minutes: float = Field(..., description="Estimated transit travel duration in minutes")

    weather: WeatherMetrics = Field(..., description="Agro-meteorological conditions evaluated")

    risk_score: float = Field(..., ge=0.0, le=100.0, description="Overall normalized spoilage risk score [0.0 to 100.0]")
    risk_level: str = Field(..., description="Categorical risk classification: LOW, MODERATE, HIGH, VERY HIGH")

    estimated_spoilage_pct: float = Field(..., ge=0.0, le=100.0, description="Estimated transit crop loss percentage [0.0 to 100.0%]")

    risk_factors: RiskFactorsBreakdown = Field(..., description="Detailed breakdown of individual contributing stress factors")

    weather_matched: bool = Field(..., description="True if weather was resolved from database or live API; False if default fallback was applied")
    weather_source: str = Field(..., description="Weather source identifier: database, live_api, or configured_fallback")
    routing_provider: str = Field(default="OSRM (OpenStreetMap)", description="Routing provider used for transit metrics")

    estimation_type: str = Field(
        default="weather-and-transit heuristic",
        description="Methodology designation (transparent rule-based estimator; not a trained ML model)"
    )
