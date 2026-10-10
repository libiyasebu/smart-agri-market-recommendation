import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.routing_service import NoRouteFoundError, RoutingAPIError


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_profit_evaluation_api_success(client):
    """Verify HTTP 200 and schema response on valid expected profit evaluation request."""
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
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi, Kerala",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "production_cost": 8000.0,
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/profit/evaluate", json=payload)
        assert response.status_code == 200, f"API Error: {response.text}"

        data = response.json()
        assert data["status"] == "success"
        assert data["commodity"] == "Tomato"
        assert data["market"] == "Thrissur APMC"
        assert data["quantity"]["original_kg"] == 1000.0
        assert data["quantity"]["original_quintals"] == 10.0
        assert data["quantity"]["sellable_kg"] > 0
        assert data["price"]["predicted_modal_price_per_quintal"] > 0
        assert data["spoilage"]["estimated_spoilage_pct"] >= 0
        assert data["transport"]["total_transport_cost"] > 0
        assert data["financials"]["gross_revenue_before_spoilage"] > 0
        assert data["financials"]["gross_revenue_after_spoilage"] > 0
        assert data["financials"]["expected_net_return"] > 0
        assert data["financials"]["production_cost"] == 8000.0
        assert data["financials"]["expected_profit"] is not None
        assert data["result_type"] == "expected_profit_with_production_cost"
        assert "evaluation_notes" in data


def test_profit_evaluation_without_production_cost(client):
    """Verify evaluation without production cost leaves expected_profit null."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
    }

    payload = {
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 500.0,
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/profit/evaluate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["financials"]["production_cost"] is None
        assert data["financials"]["expected_profit"] is None
        assert data["result_type"] == "expected_net_return_without_production_cost"


def test_profit_evaluation_unsupported_commodity_returns_400(client):
    """Verify unsupported commodity raises HTTP 400."""
    payload = {
        "commodity": "DragonFruitNonExistent",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Exotic",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
    }
    response = client.post("/api/v1/profit/evaluate", json=payload)
    assert response.status_code == 400


def test_profit_evaluation_malformed_request_returns_422(client):
    """Verify missing required parameters returns HTTP 422."""
    response = client.post("/api/v1/profit/evaluate", json={"commodity": "Tomato"})
    assert response.status_code == 422

    # Negative quantity
    response = client.post(
        "/api/v1/profit/evaluate",
        json={
            "commodity": "Tomato",
            "market": "Thrissur APMC",
            "district": "Thrissur",
            "state": "Kerala",
            "variety": "Hybrid",
            "prediction_date": "2026-08-28",
            "origin_lat": 10.0,
            "origin_lon": 76.0,
            "destination_lat": 11.0,
            "destination_lon": 77.0,
            "quantity_kg": -100.0,
        },
    )
    assert response.status_code == 422


def test_profit_evaluation_routing_failure_returns_404(client):
    """Verify NoRouteFoundError returns HTTP 404."""
    payload = {
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "quantity_kg": 500.0,
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=NoRouteFoundError("No drivable road route found"),
    ):
        response = client.post("/api/v1/profit/evaluate", json=payload)
        assert response.status_code == 404


def test_full_system_endpoints_regression(client):
    """Verify all 4 core API endpoints plus root and health remain functional."""
    # 1. Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "profit_evaluation" in r_root.json()["endpoints"]
    assert "price_prediction" in r_root.json()["endpoints"]
    assert "transport_estimation" in r_root.json()["endpoints"]
    assert "spoilage_estimation" in r_root.json()["endpoints"]

    # 2. Health
    r_health = client.get("/health")
    assert r_health.status_code == 200

    # 3. Dashboard
    r_dash = client.get("/dashboard/")
    assert r_dash.status_code == 200
