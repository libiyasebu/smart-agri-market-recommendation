from fastapi import APIRouter, HTTPException, status
from app.schemas.transport import TransportEstimateRequest, TransportEstimateResponse
from app.services.transport_service import TransportService
from app.services.routing_service import InvalidCoordinatesError, NoRouteFoundError, RoutingAPIError, RoutingError

router = APIRouter(prefix="/api/v1/transport", tags=["Transportation & Logistics"])


@router.post(
    "/estimate",
    response_model=TransportEstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Agricultural Transportation Cost",
    description=(
        "Calculates the estimated road transportation cost for moving agricultural produce "
        "from origin to destination using live OSRM road distance, duration, and vehicle profile specifications."
    ),
)
def estimate_transport_cost_endpoint(
    request: TransportEstimateRequest,
):
    """
    Endpoint for agricultural transportation cost estimation.
    Uses OSRM driving route to calculate fuel, maintenance, driver, and multi-trip expenses.
    """
    service = TransportService()
    try:
        response = service.estimate_cost_from_coordinates(request)
        return response
    except InvalidCoordinatesError as ce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ce),
        )
    except NoRouteFoundError as nre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(nre),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except RoutingAPIError as re:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Routing service unavailable: {re}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transportation cost calculation failed: {str(e)}",
        )
