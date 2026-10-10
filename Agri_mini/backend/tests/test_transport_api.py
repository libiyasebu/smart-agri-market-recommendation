import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.routing_service import (
    InvalidCoordinatesError,
    NoRouteFoundError,
    RoutingAPIError,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_transport_estimate_api_success(client):
    """Verify HTTP 200 and schema response on valid transport estimation request."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 84.89,
        "duration_minutes": 82.95,
        "duration_hours": 1.38,
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
    }

    payload = {
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi, Kerala",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "toll_charges": 0.0,
        "other_charges": 0.0,
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 200, f"API Error: {response.text}"

        data = response.json()
        assert data["status"] == "success"
        assert data["origin"] == "Thrissur, Kerala"
        assert data["destination"] == "Kochi, Kerala"
        assert data["distance_km"] == 84.89
        assert data["estimated_duration_minutes"] == 82.95
        assert data["quantity_kg"] == 1000.0
        assert data["quantity_quintals"] == 10.0
        assert data["vehicle_type"] == "mini_truck"
        assert data["vehicle_capacity_kg"] == 1500.0
        assert data["number_of_trips"] == 1

        # Fuel breakdown
        # 84.89 / 12 = 7.074166... L * 95 = 672.05
        assert data["fuel_efficiency_km_per_litre"] == 12.0
        assert data["fuel_price_per_litre"] == 95.0
        assert data["fuel_required_litres"] == 7.07
        assert data["fuel_cost"] == 672.05

        # Maintenance: 84.89 * 4 = 339.56
        assert data["maintenance_cost"] == 339.56
        # Driver: 500.0
        assert data["driver_cost"] == 500.0

        # Single trip & total: 672.05 + 339.56 + 500.0 = 1511.61
        assert data["single_trip_cost"] == 1511.61
        assert data["total_transport_cost"] == 1511.61

        # Per kg & per quintal
        assert data["transport_cost_per_kg"] == 1.51
        assert data["transport_cost_per_quintal"] == 151.16

        assert data["currency"] == "INR"
        assert data["routing_provider"] == "OSRM (OpenStreetMap)"
        assert data["cost_type"] == "estimated"


def test_transport_estimate_api_multi_trip_3000kg(client):
    """Verify multi-trip 3000 kg cargo with mini_truck (1500 kg capacity) correctly produces 2 trips."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 100.0,
        "duration_minutes": 90.0,
        "duration_hours": 1.5,
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
    }

    payload = {
        "origin_name": "Thrissur",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 3000.0,
        "vehicle_type": "mini_truck",
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["number_of_trips"] == 2
        assert data["quantity_kg"] == 3000.0
        assert data["quantity_quintals"] == 30.0
        assert data["total_transport_cost"] == round(data["single_trip_cost"] * 2, 2)


def test_transport_estimate_api_boundary_1501kg(client):
    """Verify exact boundary+1 kg (1501 kg with 1500 kg capacity) produces 2 trips."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 100.0,
        "duration_minutes": 90.0,
        "duration_hours": 1.5,
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
    }

    payload = {
        "origin_name": "Thrissur",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 1501.0,
        "vehicle_type": "mini_truck",
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["number_of_trips"] == 2


def test_transport_estimate_with_toll_and_other_charges(client):
    """Verify toll and other handling charges are included in calculation."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
    }

    payload = {
        "origin_name": "Thrissur",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 1000.0,
        "vehicle_type": "pickup",
        "toll_charges": 120.0,
        "other_charges": 80.0,
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["toll_charges"] == 120.0
        assert data["other_charges"] == 80.0


def test_transport_estimate_unsupported_vehicle_returns_400(client):
    """Verify unsupported vehicle type returns HTTP 400 Bad Request."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
        "origin": {"latitude": 10.0, "longitude": 76.0},
        "destination": {"latitude": 11.0, "longitude": 77.0},
    }

    payload = {
        "origin_name": "A",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_name": "B",
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
        "vehicle_type": "hovercraft",
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 400
        assert "Unsupported vehicle_type" in response.json()["detail"]


def test_transport_estimate_no_route_found_returns_404(client):
    """Verify NoRouteFoundError from routing service returns HTTP 404."""
    payload = {
        "origin_name": "Island A",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_name": "Island B",
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=NoRouteFoundError("No drivable road route found between points"),
    ):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 404
        assert "No drivable road route found" in response.json()["detail"]


def test_transport_estimate_routing_api_error_returns_502(client):
    """Verify RoutingAPIError returns HTTP 502 Bad Gateway."""
    payload = {
        "origin_name": "A",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_name": "B",
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=RoutingAPIError("OSRM timed out"),
    ):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 502
        assert "Routing service unavailable" in response.json()["detail"]


def test_transport_estimate_invalid_coordinates_returns_400(client):
    """Verify InvalidCoordinatesError from routing service returns HTTP 400."""
    payload = {
        "origin_name": "A",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_name": "B",
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=InvalidCoordinatesError("Origin latitude out of bounds"),
    ):
        response = client.post("/api/v1/transport/estimate", json=payload)
        assert response.status_code == 400
        assert "Origin latitude out of bounds" in response.json()["detail"]


def test_transport_estimate_malformed_request_returns_422(client):
    """Verify Pydantic schema validation failures return HTTP 422."""
    # Case 1: missing required origin_lat
    response = client.post("/api/v1/transport/estimate", json={"quantity_kg": 500.0})
    assert response.status_code == 422

    # Case 2: quantity <= 0
    response = client.post(
        "/api/v1/transport/estimate",
        json={
            "origin_lat": 10.0,
            "origin_lon": 76.0,
            "destination_lat": 11.0,
            "destination_lon": 77.0,
            "quantity_kg": 0.0,
        },
    )
    assert response.status_code == 422

    # Case 3: negative fuel price
    response = client.post(
        "/api/v1/transport/estimate",
        json={
            "origin_lat": 10.0,
            "origin_lon": 76.0,
            "destination_lat": 11.0,
            "destination_lon": 77.0,
            "quantity_kg": 100.0,
            "fuel_price_per_litre": -5.0,
        },
    )
    assert response.status_code == 422

    # Case 4: latitude > 90
    response = client.post(
        "/api/v1/transport/estimate",
        json={
            "origin_lat": 100.0,
            "origin_lon": 76.0,
            "destination_lat": 11.0,
            "destination_lon": 77.0,
            "quantity_kg": 100.0,
        },
    )
    assert response.status_code == 422


def test_system_endpoints_and_price_prediction_regression(client):
    """Verify root, health, and price prediction endpoints remain fully functional."""
    # 1. Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "transport_estimation" in r_root.json()["endpoints"]

    # 2. Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    # 3. Price prediction
    price_payload = {
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
    }
    r_price = client.post("/api/v1/predict/price", json=price_payload)
    assert r_price.status_code == 200
    assert r_price.json()["status"] == "success"
    assert r_price.json()["predicted_modal_price"] > 0
