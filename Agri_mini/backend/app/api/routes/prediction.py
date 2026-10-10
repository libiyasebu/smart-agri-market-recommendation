from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.prediction import PricePredictionRequest, PricePredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/v1/predict", tags=["Price Prediction"])


@router.post(
    "/price",
    response_model=PricePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict Agricultural Modal Price",
    description=(
        "Predicts the expected modal price (INR per quintal) for a specified crop, mandi market, "
        "and future date using the trained Random Forest production model and real-time historical features."
    ),
)
def predict_price_endpoint(
    request: PricePredictionRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint for agricultural price forecasting.
    Constructs leakage-free historical features from PostgreSQL database and runs inference.
    """
    try:
        service = PredictionService.get_instance()
        response = service.predict_price(request, db)
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except FileNotFoundError as fe:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model artifact error: {fe}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price prediction inference failed: {str(e)}",
        )
