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


def test_spoilage_estimate_api_success(client):
    """Verify HTTP 200 and schema response on valid agricultural spoilage estimation request."""
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
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi, Kerala",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "transport_date": "2026-08-28",
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/spoilage/estimate", json=payload)
        assert response.status_code == 200, f"API Error: {response.text}"

        data = response.json()
        assert data["status"] == "success"
        assert data["commodity"] == "Tomato"
        assert data["origin"] == "Thrissur, Kerala"
        assert data["destination"] == "Kochi, Kerala"
        assert data["distance_km"] == 84.89
        assert data["transit_duration_minutes"] == 82.95

        # Weather structure
        assert "temperature_mean_c" in data["weather"]
        assert "humidity_pct" in data["weather"]

        # Risk and Loss
        assert 0.0 <= data["risk_score"] <= 100.0
        assert data["risk_level"] in ["LOW", "MODERATE", "HIGH", "VERY HIGH"]
        assert 0.0 <= data["estimated_spoilage_pct"] <= 100.0

        # Risk Factors
        assert "temperature_stress" in data["risk_factors"]
        assert "humidity_stress" in data["risk_factors"]
        assert "transit_time_stress" in data["risk_factors"]
        assert "base_perishability" in data["risk_factors"]

        assert data["routing_provider"] == "OSRM (OpenStreetMap)"
        assert data["estimation_type"] == "weather-and-transit heuristic"


def test_spoilage_estimate_with_overrides(client):
    """Verify manual temperature and humidity overrides are applied."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 100.0,
        "duration_minutes": 90.0,
        "duration_hours": 1.5,
    }

    payload = {
        "commodity": "Banana",
        "origin_name": "Thrissur",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "transport_date": "2026-08-28",
        "temperature_override_c": 38.0,
        "humidity_override_pct": 92.0,
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/spoilage/estimate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["weather"]["temperature_mean_c"] == 38.0
        assert data["weather"]["humidity_pct"] == 92.0
        assert data["weather_source"] == "user_override"
        assert data["risk_level"] in ["HIGH", "VERY HIGH"]


def test_spoilage_estimate_unsupported_commodity_returns_400(client):
    """Verify unsupported commodity raises HTTP 400 Bad Request."""
    mock_route = {
        "status": "success",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
    }

    payload = {
        "commodity": "DragonFruitExotic",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "transport_date": "2026-08-28",
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/spoilage/estimate", json=payload)
        assert response.status_code == 400
        assert "Unsupported commodity" in response.json()["detail"]


def test_spoilage_estimate_no_route_found_returns_404(client):
    """Verify NoRouteFoundError returns HTTP 404."""
    payload = {
        "commodity": "Tomato",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "transport_date": "2026-08-28",
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=NoRouteFoundError("No drivable route found"),
    ):
        response = client.post("/api/v1/spoilage/estimate", json=payload)
        assert response.status_code == 404
        assert "No drivable route" in response.json()["detail"]


def test_spoilage_estimate_routing_api_error_returns_502(client):
    """Verify RoutingAPIError returns HTTP 502 Bad Gateway."""
    payload = {
        "commodity": "Tomato",
        "origin_lat": 10.0,
        "origin_lon": 76.0,
        "destination_lat": 11.0,
        "destination_lon": 77.0,
        "transport_date": "2026-08-28",
    }

    with patch(
        "app.services.routing_service.RoutingDataService.get_route",
        side_effect=RoutingAPIError("OSRM timed out"),
    ):
        response = client.post("/api/v1/spoilage/estimate", json=payload)
        assert response.status_code == 502
        assert "Routing service unavailable" in response.json()["detail"]


def test_spoilage_estimate_malformed_request_returns_422(client):
    """Verify malformed inputs return HTTP 422 Unprocessable Entity."""
    # Missing required transport_date
    response = client.post(
        "/api/v1/spoilage/estimate",
        json={"commodity": "Tomato", "origin_lat": 10.0, "origin_lon": 76.0, "destination_lat": 11.0, "destination_lon": 77.0},
    )
    assert response.status_code == 422

    # Latitude out of bounds
    response = client.post(
        "/api/v1/spoilage/estimate",
        json={"commodity": "Tomato", "origin_lat": 120.0, "origin_lon": 76.0, "destination_lat": 11.0, "destination_lon": 77.0, "transport_date": "2026-08-28"},
    )
    assert response.status_code == 422


def test_system_endpoints_regression_with_spoilage(client):
    """Verify all prior system endpoints remain fully functional."""
    # Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "spoilage_estimation" in r_root.json()["endpoints"]
    assert "price_prediction" in r_root.json()["endpoints"]
    assert "transport_estimation" in r_root.json()["endpoints"]

    # Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    # Dashboard HTML
    r_dash = client.get("/dashboard/")
    assert r_dash.status_code == 200

    # Price Prediction Endpoint
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

    # Transport Estimation Endpoint
    transport_payload = {
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Kochi, Kerala",
        "destination_lat": 9.9312,
        "destination_lon": 76.2673,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
    }
    r_trans = client.post("/api/v1/transport/estimate", json=transport_payload)
    assert r_trans.status_code == 200
    assert r_trans.json()["status"] == "success"
