from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class PricePredictionRequest(BaseModel):
    """
    Input schema for agricultural modal price prediction request.
    Strictly excludes any same-day target or price spread variables.
    """
    commodity: str = Field(..., description="Name of the agricultural crop/commodity", json_schema_extra={"example": "Tomato"})
    market: str = Field(..., description="Target mandi/APMC market name", json_schema_extra={"example": "Thrissur APMC"})
    district: str = Field(..., description="District of the target market", json_schema_extra={"example": "Thrissur"})
    state: str = Field(default="Kerala", description="State of the market", json_schema_extra={"example": "Kerala"})
    variety: str = Field(default="Hybrid", description="Crop variety name", json_schema_extra={"example": "Hybrid"})
    prediction_date: date = Field(..., description="Target date for which to predict modal price", json_schema_extra={"example": "2026-08-28"})

    @field_validator("commodity", "market", "district", "state", "variety")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class PricePredictionResponse(BaseModel):
    """
    Structured output schema for price prediction inference.
    """
    status: str = Field(default="success", description="Response status (success/error)")
    commodity: str = Field(..., description="Requested crop/commodity")
    market: str = Field(..., description="Target mandi market")
    district: str = Field(..., description="Target district")
    state: str = Field(..., description="Target state")
    variety: str = Field(..., description="Crop variety")
    prediction_date: date = Field(..., description="Prediction target date")
    predicted_modal_price: float = Field(..., description="Predicted modal price in INR per quintal")
    unit: str = Field(default="INR/quintal", description="Price unit")
    model_used: str = Field(..., description="Name of the machine learning model used for inference")
    historical_data_points_used: int = Field(..., description="Number of prior market price observations used to derive lag/rolling features")
    latest_known_price: Optional[float] = Field(None, description="Most recent recorded modal price prior to prediction_date")
    weather_matched: bool = Field(..., description="Whether location weather records were matched")
    faostat_matched: bool = Field(..., description="Whether FAOSTAT macro indicators were matched")
    route_matched: bool = Field(..., description="Whether OSRM route logistics were matched")
    features_used_count: int = Field(default=54, description="Total number of encoded features provided to the model")
    prediction_timestamp: str = Field(..., description="ISO timestamp of inference execution")
