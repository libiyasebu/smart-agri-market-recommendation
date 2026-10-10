from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class CandidateMarket(BaseModel):
    """
    Candidate mandi / destination market input specification.
    """
    market: str = Field(..., description="Mandi / APMC market name (e.g. Kochi (Ernakulam) Market)", json_schema_extra={"example": "Kochi (Ernakulam) Market"})
    district: str = Field(..., description="Market district name (e.g. Ernakulam)", json_schema_extra={"example": "Ernakulam"})
    state: str = Field(default="Kerala", description="Market state name", json_schema_extra={"example": "Kerala"})
    destination_name: str = Field(..., description="Geographic destination name for route calculation", json_schema_extra={"example": "Kochi, Kerala"})
    destination_lat: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude", json_schema_extra={"example": 9.9312})
    destination_lon: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude", json_schema_extra={"example": 76.2673})
    variety: Optional[str] = Field(None, description="Optional market-specific crop variety override")

    @field_validator("market", "district", "state", "destination_name")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned


class CriterionInfo(BaseModel):
    """
    Metadata for a multi-criteria decision dimension used in TOPSIS.
    """
    name: str = Field(..., description="Technical criterion code (e.g. expected_net_return)")
    display_name: str = Field(..., description="Human-readable criterion label")
    criterion_type: str = Field(..., description="Optimization direction: 'benefit' (higher is better) or 'cost' (lower is better)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Normalized weight assigned in TOPSIS evaluation")


class MarketRankItem(BaseModel):
    """
    Detailed evaluation metrics and TOPSIS ranking for a candidate market alternative.
    """
    rank: int = Field(..., ge=1, description="Rank position (1 is best recommendation)")
    market: str = Field(..., description="Mandi / market name")
    district: str = Field(..., description="District")
    state: str = Field(..., description="State")
    destination_name: str = Field(..., description="Geographic destination name")
    destination_lat: float = Field(..., description="Latitude")
    destination_lon: float = Field(..., description="Longitude")

    # Routing & Logistics
    distance_km: float = Field(..., ge=0.0, description="Road transit distance in km")
    transit_duration_minutes: float = Field(..., ge=0.0, description="Road transit duration in minutes")
    transportation_cost: float = Field(..., ge=0.0, description="Total logistics transportation expense in INR")

    # Market Price & Produce Integrity
    predicted_price_per_quintal: float = Field(..., gt=0.0, description="ML-predicted modal price in INR/quintal")
    spoilage_risk_score: float = Field(..., ge=0.0, le=100.0, description="Spoilage risk index [0-100]")
    estimated_spoilage_pct: float = Field(..., ge=0.0, le=100.0, description="Estimated transit volume loss percentage")
    sellable_quantity_kg: float = Field(..., ge=0.0, description="Volume arriving sellable at destination in kg")

    # Financial Performance
    gross_revenue_after_spoilage: float = Field(..., description="Realized gross revenue from sellable produce in INR")
    expected_net_return: float = Field(..., description="Expected net revenue after deducting freight from gross revenue in INR")
    production_cost: Optional[float] = Field(None, ge=0.0, description="Optional cultivation cost in INR")
    expected_profit: Optional[float] = Field(None, description="Expected accounting profit in INR if production cost provided")

    # TOPSIS Evaluation Scores
    topsis_score: float = Field(..., ge=0.0, le=1.0, description="TOPSIS relative closeness coefficient C_i in range [0, 1]")
    distance_to_ideal_best: float = Field(..., ge=0.0, description="Euclidean distance to ideal best solution S_i+")
    distance_to_ideal_worst: float = Field(..., ge=0.0, description="Euclidean distance to ideal worst solution S_i-")
    summary_verdict: str = Field(..., description="Qualitative comparative verdict for this market")


class FailedCandidateMarket(BaseModel):
    """
    Details for a candidate market that encountered a downstream service failure during evaluation.
    """
    market: str = Field(..., description="Candidate market name")
    district: str = Field(..., description="District")
    failure_reason: str = Field(..., description="Controlled error description")


class RecommendedMarketSummary(BaseModel):
    """
    Executive summary for the top-ranked recommended market.
    """
    rank: int = Field(default=1, description="Rank (always 1 for top recommendation)")
    market: str = Field(..., description="Recommended market name")
    district: str = Field(..., description="District")
    state: str = Field(..., description="State")
    topsis_score: float = Field(..., ge=0.0, le=1.0, description="TOPSIS score")
    expected_net_return: float = Field(..., description="Expected net return in INR")
    expected_profit: Optional[float] = Field(None, description="Expected profit in INR")
    predicted_price_per_quintal: float = Field(..., description="Predicted price in INR/quintal")
    transportation_cost: float = Field(..., description="Transportation cost in INR")
    spoilage_risk_score: float = Field(..., description="Spoilage risk score [0-100]")
    reason_summary: str = Field(..., description="Transparent rationale explaining why this market ranked highest")


class MarketRecommendationRequest(BaseModel):
    """
    Request schema for TOPSIS multi-market comparison and recommendation.
    """
    commodity: str = Field(..., description="Crop commodity name", json_schema_extra={"example": "Tomato"})
    variety: str = Field(default="Hybrid", description="Crop variety name", json_schema_extra={"example": "Hybrid"})
    prediction_date: date = Field(..., description="Target market selling date", json_schema_extra={"example": "2026-08-28"})

    origin_name: str = Field(default="Origin Location", description="Farm origin location", json_schema_extra={"example": "Thrissur, Kerala"})
    origin_lat: float = Field(..., ge=-90.0, le=90.0, description="Origin latitude", json_schema_extra={"example": 10.5276})
    origin_lon: float = Field(..., ge=-180.0, le=180.0, description="Origin longitude", json_schema_extra={"example": 76.2144})

    quantity_kg: float = Field(..., gt=0.0, description="Total harvest volume in kg", json_schema_extra={"example": 1000.0})
    vehicle_type: str = Field(default="mini_truck", description="Vehicle profile code", json_schema_extra={"example": "mini_truck"})
    fuel_price_per_litre: float = Field(default=95.0, gt=0.0, description="Fuel rate in INR/Litre", json_schema_extra={"example": 95.0})
    toll_charges: float = Field(default=0.0, ge=0.0, description="Toll charges per trip in INR", json_schema_extra={"example": 0.0})
    other_charges: float = Field(default=0.0, ge=0.0, description="Loading/other charges per trip in INR", json_schema_extra={"example": 0.0})

    production_cost: Optional[float] = Field(default=None, ge=0.0, description="Optional cultivation cost in INR", json_schema_extra={"example": 12000.0})

    candidate_markets: List[CandidateMarket] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of 2 to 10 candidate destination markets to compare and rank",
    )

    custom_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional custom criteria weights mapping criterion name to weight (e.g. {'expected_profit': 0.4, 'predicted_price': 0.2, ...})",
    )

    @field_validator("commodity", "variety", "origin_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned

    @model_validator(mode="after")
    def validate_candidate_markets_uniqueness(self):
        seen = set()
        for cand in self.candidate_markets:
            key = f"{cand.market.strip().lower()}:{cand.district.strip().lower()}"
            if key in seen:
                raise ValueError(f"Duplicate candidate market in request: '{cand.market}' ({cand.district})")
            seen.add(key)
        return self


class MarketRecommendationResponse(BaseModel):
    """
    Response schema containing TOPSIS market recommendation, full ranking, and decision breakdown.
    """
    status: str = Field(default="success", description="Status code")
    commodity: str = Field(..., description="Crop commodity evaluated")
    variety: str = Field(..., description="Crop variety")
    prediction_date: date = Field(..., description="Selling date evaluated")
    origin: str = Field(..., description="Farm origin location")
    quantity_kg: float = Field(..., description="Produce harvest quantity in kg")

    recommended_market: RecommendedMarketSummary = Field(..., description="Top recommended destination mandi")
    criteria_used: List[CriterionInfo] = Field(..., description="TOPSIS criteria, optimization direction, and normalized weights")
    rankings: List[MarketRankItem] = Field(..., description="Full list of candidate markets sorted by descending TOPSIS score")
    failed_candidates: List[FailedCandidateMarket] = Field(default_factory=list, description="Candidate markets that could not be evaluated")

    method: str = Field(default="TOPSIS", description="Multi-criteria decision methodology")
    currency: str = Field(default="INR", description="Currency unit")
    recommendation_notes: str = Field(..., description="Transparent decision-support and interpretability notes")
    evaluation_timestamp: str = Field(..., description="ISO timestamp")
