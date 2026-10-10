from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommendation import (
    MarketRecommendationRequest,
    MarketRecommendationResponse,
)
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/v1/recommend", tags=["Market Recommendation"])


@router.post(
    "/markets",
    response_model=MarketRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rank Candidate Markets and Recommend Optimal Destination",
    description=(
        "Evaluates multiple candidate agricultural markets for a given crop shipment by orchestrating "
        "ML price prediction, OSRM road transport costs, and agro-weather spoilage loss estimation. "
        "Applies TOPSIS (Technique for Order Preference by Similarity to Ideal Solution) multi-criteria "
        "decision analysis to rank markets and identify the optimal selling destination."
    ),
)
def recommend_markets_endpoint(
    request: MarketRecommendationRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint for TOPSIS-based multi-market ranking and recommendation.
    """
    service = RecommendationService()
    try:
        response = service.recommend_markets(request, db=db)
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Market recommendation failed: {str(e)}",
        )
