"""
ceda_recommendation.py
Pydantic schemas for POST /api/recommend/ceda
"""
from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class CedaMarketCandidate(BaseModel):
    """One candidate market for evaluation."""
    market_id:        int   = Field(..., gt=0, description="AGMARKNET market ID", examples=[2157])
    district_id:      int   = Field(..., gt=0, description="Kerala census district ID", examples=[591])
    market_name:      str   = Field(...,        description="Market display name",       examples=["Kozhikode Market"])
    destination_lat:  float = Field(..., ge=-90,  le=90,  description="Market latitude",  examples=[11.2588])
    destination_lon:  float = Field(..., ge=-180, le=180, description="Market longitude", examples=[75.7804])

    @field_validator("market_name")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("market_name cannot be empty")
        return v.strip()


class CedaRecommendationRequest(BaseModel):
    """Request schema for the CEDA-based end-to-end market recommendation."""
    commodity_id:      int            = Field(..., gt=0,   description="Active commodity ID (e.g. 19=Banana, 78=Tomato)", examples=[19])
    quantity_kg:       float          = Field(..., gt=0,   description="Total produce quantity in kg",                    examples=[500.0])
    source_latitude:   float          = Field(..., ge=-90,  le=90,  description="Farm/origin latitude",                  examples=[11.2588])
    source_longitude:  float          = Field(..., ge=-180, le=180, description="Farm/origin longitude",                 examples=[75.7804])
    prediction_date:   date           = Field(...,         description="Target selling date (YYYY-MM-DD)",                examples=["2025-10-15"])
    candidate_markets: List[CedaMarketCandidate] = Field(..., min_length=2, max_length=10,
                                                         description="2–10 candidate markets to rank")
    vehicle_type:      str            = Field(default="mini_truck", description="Vehicle profile code")
    fuel_price_per_litre: float       = Field(default=95.0, gt=0, description="Diesel price INR/litre")
    toll_charges:      float          = Field(default=0.0, ge=0,  description="Toll per trip INR")
    other_charges:     float          = Field(default=0.0, ge=0,  description="Loading/misc per trip INR")
    production_cost:   Optional[float]= Field(default=None, ge=0, description="Optional cultivation cost in INR")

    @model_validator(mode="after")
    def no_duplicate_markets(self) -> "CedaRecommendationRequest":
        seen = set()
        for m in self.candidate_markets:
            key = (m.market_id, m.district_id)
            if key in seen:
                raise ValueError(f"Duplicate candidate market_id={m.market_id}, district_id={m.district_id}")
            seen.add(key)
        return self


class CedaRankedMarket(BaseModel):
    rank:                        int
    market_id:                   int
    district_id:                 int
    market_name:                 str
    destination_lat:             float
    destination_lon:             float
    distance_km:                 float
    transit_duration_minutes:    float
    transport_cost_inr:          float
    predicted_price_per_quintal: float
    spoilage_risk_score:         float
    estimated_spoilage_pct:      float
    sellable_quantity_kg:        float
    expected_revenue_inr:        float
    expected_net_return_inr:     float
    production_cost_inr:         Optional[float] = None
    expected_profit_inr:         Optional[float] = None
    topsis_score:                float
    summary_verdict:             str


class CedaRecommendedMarket(BaseModel):
    rank:                        int = 1
    market_id:                   int
    district_id:                 int
    market_name:                 str
    topsis_score:                float
    predicted_price_per_quintal: float
    transport_cost_inr:          float
    spoilage_risk_score:         float
    expected_net_return_inr:     float
    expected_profit_inr:         Optional[float] = None
    reason_summary:              str


class CedaFailedMarket(BaseModel):
    market_id:      int
    district_id:    int
    market_name:    str
    failure_reason: str


class CedaRecommendationResponse(BaseModel):
    status:              str           = "success"
    commodity_id:        int
    commodity_name:      str
    quantity_kg:         float
    prediction_date:     date
    recommended_market:  CedaRecommendedMarket
    markets:             List[CedaRankedMarket]
    failed_markets:      List[CedaFailedMarket] = []
    ranking_method:      str           = "TOPSIS"
    criteria_used:       List[Dict[str, Any]] = []
    evaluation_timestamp: str
