"""
ceda_prediction.py  (router)
POST /api/predict/price
Uses the CEDA-trained 26-feature Random Forest pipeline.
The existing /api/v1/predict/price endpoint is untouched.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.schemas.ceda_prediction import (
    CedaPricePredictionRequest,
    CedaPricePredictionResponse,
)
from app.services.price_prediction_service import (
    PricePredictionService,
    ACTIVE_COMMODITIES,
)

router = APIRouter(prefix="/api/predict", tags=["CEDA Price Prediction"])


@router.post(
    "/price",
    response_model=CedaPricePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict Agricultural Modal Price (CEDA RF Model)",
    description=(
        "Predicts modal price (INR/quintal) using the CEDA-trained Random Forest "
        "pipeline with 26 leakage-free features. Historical lag/rolling price "
        "features are derived server-side from genuine CEDA records strictly "
        "prior to the requested prediction_date."
    ),
)
def predict_price(request: CedaPricePredictionRequest) -> CedaPricePredictionResponse:
    try:
        svc = PricePredictionService.get_instance()
        predicted, n_pts, latest, wx_note = svc.predict(
            commodity_id    = request.commodity_id,
            district_id     = request.district_id,
            market_id       = request.market_id,
            prediction_date = request.prediction_date,
        )
        return CedaPricePredictionResponse(
            status                  = "success",
            commodity_id            = request.commodity_id,
            commodity_name          = ACTIVE_COMMODITIES[request.commodity_id],
            district_id             = request.district_id,
            market_id               = request.market_id,
            prediction_date         = request.prediction_date,
            predicted_modal_price   = predicted,
            unit                    = "INR/quintal",
            model                   = "Random Forest",
            prior_observations_used = n_pts,
            latest_known_price      = latest,
            weather_note            = wx_note,
            prediction_timestamp    = datetime.now().isoformat(),
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Model artifact error: {fe}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Prediction failed: {e}")
