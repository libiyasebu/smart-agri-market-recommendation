from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.profit import ProfitEvaluationRequest, ProfitEvaluationResponse
from app.services.profit_service import ProfitService
from app.services.routing_service import InvalidCoordinatesError, NoRouteFoundError, RoutingAPIError, RoutingError


router = APIRouter(prefix="/api/v1/profit", tags=["Profit Evaluation"])


@router.post(
    "/evaluate",
    response_model=ProfitEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Expected Agricultural Profit and Market Returns",
    description=(
        "Evaluates the expected financial net return and potential profit for selling produce at a candidate destination market "
        "by combining machine learning modal price prediction, OSRM road transport logistics costing, and "
        "agro-weather transit spoilage loss estimation."
    ),
)
def evaluate_profit_endpoint(
    request: ProfitEvaluationRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint for agricultural profit and net return evaluation.
    Orchestrates Price Prediction, Transportation Logistics, and Spoilage Risk models.
    """
    service = ProfitService()
    try:
        response = service.evaluate_profit(request, db=db)
        return response
    except InvalidCoordinatesError as ce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ce),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except NoRouteFoundError as nre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(nre),
        )
    except RoutingAPIError as re:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Routing service unavailable: {re}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profit evaluation failed: {str(e)}",
        )
