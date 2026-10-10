from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.spoilage import SpoilageEstimateRequest, SpoilageEstimateResponse
from app.services.spoilage_service import SpoilageService
from app.services.routing_service import InvalidCoordinatesError, NoRouteFoundError, RoutingAPIError, RoutingError


router = APIRouter(prefix="/api/v1/spoilage", tags=["Spoilage Risk"])


@router.post(
    "/estimate",
    response_model=SpoilageEstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Agricultural Transit Spoilage Risk",
    description=(
        "Estimates the expected quality deterioration risk score (0-100), risk level (LOW/MODERATE/HIGH/VERY HIGH), "
        "and physical loss percentage for agricultural produce during road transit based on commodity perishability, "
        "live OSRM driving duration, and agro-meteorological weather stress (Open-Meteo)."
    ),
)
def estimate_spoilage_risk_endpoint(
    request: SpoilageEstimateRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint for weather-and-transit agricultural spoilage risk estimation.
    Integrates OSRM driving duration and regional temperature/humidity conditions.
    """
    service = SpoilageService()
    try:
        response = service.estimate_spoilage_from_coordinates(request, db=db)
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
            detail=f"Spoilage risk estimation failed: {str(e)}",
        )
