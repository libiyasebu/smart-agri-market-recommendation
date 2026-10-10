"""
ceda_recommendation.py  (router)
POST /api/recommend/ceda
Full CEDA-based market evaluation and TOPSIS ranking.
Existing /api/v1/recommend/markets is untouched.
"""
from fastapi import APIRouter, HTTPException, status

from app.schemas.ceda_recommendation import (
    CedaRecommendationRequest,
    CedaRecommendationResponse,
    CedaRankedMarket,
    CedaRecommendedMarket,
    CedaFailedMarket,
)
from app.services.market_evaluation_service import (
    MarketEvaluationService,
    CedaCandidateMarket,
)

router = APIRouter(prefix="/api/recommend", tags=["CEDA Market Recommendation"])


@router.post(
    "/ceda",
    response_model=CedaRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate and Rank Markets (CEDA RF Model + TOPSIS)",
    description=(
        "Full end-to-end market evaluation pipeline: "
        "CEDA Random Forest price prediction → OSRM routing → "
        "transport cost → spoilage risk → profit → TOPSIS ranking. "
        "Returns a ranked recommendation of candidate markets."
    ),
)
def recommend_ceda(request: CedaRecommendationRequest) -> CedaRecommendationResponse:
    try:
        svc = MarketEvaluationService.get_instance()

        candidates = [
            CedaCandidateMarket(
                market_id       = m.market_id,
                district_id     = m.district_id,
                market_name     = m.market_name,
                destination_lat = m.destination_lat,
                destination_lon = m.destination_lon,
            )
            for m in request.candidate_markets
        ]

        result = svc.evaluate(
            commodity_id      = request.commodity_id,
            quantity_kg       = request.quantity_kg,
            source_lat        = request.source_latitude,
            source_lon        = request.source_longitude,
            prediction_date   = request.prediction_date,
            candidate_markets = candidates,
            vehicle_type      = request.vehicle_type,
            fuel_price        = request.fuel_price_per_litre,
            toll_charges      = request.toll_charges,
            other_charges     = request.other_charges,
            production_cost   = request.production_cost,
        )

        top = result["recommended_market"]
        recommended = CedaRecommendedMarket(
            rank                        = 1,
            market_id                   = top["market_id"],
            district_id                 = top["district_id"],
            market_name                 = top["market_name"],
            topsis_score                = top["topsis_score"],
            predicted_price_per_quintal = top["predicted_price_per_quintal"],
            transport_cost_inr          = top["transport_cost_inr"],
            spoilage_risk_score         = top["spoilage_risk_score"],
            expected_net_return_inr     = top["expected_net_return_inr"],
            expected_profit_inr         = top.get("expected_profit_inr"),
            reason_summary              = top["reason_summary"],
        )

        markets = [CedaRankedMarket(**m) for m in result["markets"]]
        failed  = [CedaFailedMarket(**f) for f in result["failed_markets"]]

        return CedaRecommendationResponse(
            status               = "success",
            commodity_id         = result["commodity_id"],
            commodity_name       = result["commodity_name"],
            quantity_kg          = result["quantity_kg"],
            prediction_date      = request.prediction_date,
            recommended_market   = recommended,
            markets              = markets,
            failed_markets       = failed,
            ranking_method       = "TOPSIS",
            criteria_used        = result["criteria_used"],
            evaluation_timestamp = result["evaluation_timestamp"],
        )

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Model artifact error: {fe}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Market evaluation failed: {e}")
