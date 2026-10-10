"""
ceda_prediction.py
Pydantic schemas for the CEDA 26-feature Random Forest price prediction endpoint.
POST /api/predict/price
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CedaPricePredictionRequest(BaseModel):
    """
    Minimal user-facing input.  The 26 engineered ML features are derived
    server-side from historical CEDA data — the caller never supplies them.
    """
    commodity_id:    int  = Field(..., description="Active commodity ID (e.g. 78 = Tomato)",   examples=[78])
    district_id:     int  = Field(..., description="Kerala census district ID (e.g. 591)",      examples=[591])
    market_id:       int  = Field(..., description="AGMARKNET market ID (e.g. 2157)",           examples=[2157])
    prediction_date: date = Field(..., description="Date for which to predict modal_price",     examples=["2025-10-15"])

    @field_validator("commodity_id", "district_id", "market_id")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ID must be a positive integer")
        return v

    @model_validator(mode="after")
    def prediction_date_reasonable(self) -> "CedaPricePredictionRequest":
        from datetime import date as _date
        if self.prediction_date < _date(2024, 1, 1):
            raise ValueError("prediction_date must not be before 2024-01-01")
        return self


class CedaPricePredictionResponse(BaseModel):
    """Structured inference output from the CEDA Random Forest pipeline."""
    status:                  str           = Field(default="success")
    commodity_id:            int
    commodity_name:          str
    district_id:             int
    market_id:               int
    prediction_date:         date
    predicted_modal_price:   float         = Field(..., description="Predicted modal price (INR/quintal)")
    unit:                    str           = Field(default="INR/quintal")
    model:                   str           = Field(default="Random Forest")
    prior_observations_used: int           = Field(..., description="# of historical records used for lag/rolling features")
    latest_known_price:      Optional[float] = Field(None, description="Most recent actual modal_price before prediction_date")
    weather_note:            str           = Field(..., description="Weather data provenance note")
    prediction_timestamp:    str


class CedaPredictionError(BaseModel):
    status:  str = "error"
    detail:  str
