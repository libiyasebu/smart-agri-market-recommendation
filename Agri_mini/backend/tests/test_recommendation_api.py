import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_recommend_markets_api_success(client):
    """Verify HTTP 200, TOPSIS ranking, and complete schema on multi-market recommendation request."""
    mock_route = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 84.89,
        "duration_minutes": 82.95,
        "duration_hours": 1.38,
    }

    payload = {
        "commodity": "Tomato",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "production_cost": 12000.0,
        "candidate_markets": [
            {
                "market": "Kochi (Ernakulam) Market",
                "district": "Ernakulam",
                "state": "Kerala",
                "destination_name": "Kochi, Kerala",
                "destination_lat": 9.9312,
                "destination_lon": 76.2673,
            },
            {
                "market": "Palakkad Wholesale Mandi",
                "district": "Palakkad",
                "state": "Kerala",
                "destination_name": "Palakkad, Kerala",
                "destination_lat": 10.7867,
                "destination_lon": 76.6548,
            },
        ],
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/recommend/markets", json=payload)
        assert response.status_code == 200, f"API Error: {response.text}"

        data = response.json()
        assert data["status"] == "success"
        assert data["commodity"] == "Tomato"
        assert data["method"] == "TOPSIS"
        assert data["recommended_market"]["rank"] == 1
        assert "market" in data["recommended_market"]
        assert "topsis_score" in data["recommended_market"]
        assert "reason_summary" in data["recommended_market"]

        # Criteria
        assert len(data["criteria_used"]) == 5
        assert data["criteria_used"][0]["name"] == "expected_profit"

        # Rankings
        assert len(data["rankings"]) == 2
        assert data["rankings"][0]["rank"] == 1
        assert data["rankings"][1]["rank"] == 2
        assert data["rankings"][0]["topsis_score"] >= data["rankings"][1]["topsis_score"]


def test_recommend_markets_custom_weights(client):
    """Verify custom criteria weights are accepted, normalized, and used."""
    mock_route = {
        "status": "success",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
    }

    payload = {
        "commodity": "Tomato",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "quantity_kg": 1000.0,
        "custom_weights": {
            "expected_net_return": 0.60,
            "predicted_price": 0.10,
            "transportation_cost": 0.10,
            "transit_duration": 0.10,
            "spoilage_risk_score": 0.10,
        },
        "candidate_markets": [
            {"market": "Kochi (Ernakulam) Market", "district": "Ernakulam", "destination_name": "Kochi", "destination_lat": 9.9312, "destination_lon": 76.2673},
            {"market": "Palakkad Wholesale Mandi", "district": "Palakkad", "destination_name": "Palakkad", "destination_lat": 10.7867, "destination_lon": 76.6548},
        ],
    }

    with patch("app.services.routing_service.RoutingDataService.get_route", return_value=mock_route):
        response = client.post("/api/v1/recommend/markets", json=payload)
        assert response.status_code == 200

        data = response.json()
        net_ret_crit = next(c for c in data["criteria_used"] if c["name"] == "expected_net_return")
        assert net_ret_crit["weight"] == 0.60


def test_recommend_markets_duplicate_markets_rejected(client):
    """Verify duplicate candidate markets raise HTTP 422 validation error."""
    payload = {
        "commodity": "Tomato",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "quantity_kg": 1000.0,
        "candidate_markets": [
            {"market": "Kochi Market", "district": "Ernakulam", "destination_name": "Kochi", "destination_lat": 9.9312, "destination_lon": 76.2673},
            {"market": "Kochi Market", "district": "Ernakulam", "destination_name": "Kochi", "destination_lat": 9.9312, "destination_lon": 76.2673},
        ],
    }
    response = client.post("/api/v1/recommend/markets", json=payload)
    assert response.status_code == 422
    assert "Duplicate candidate market" in response.text


def test_recommend_markets_less_than_two_candidates_rejected(client):
    """Verify single candidate market is rejected with HTTP 422."""
    payload = {
        "commodity": "Tomato",
        "prediction_date": "2026-08-28",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "quantity_kg": 1000.0,
        "candidate_markets": [
            {"market": "Kochi Market", "district": "Ernakulam", "destination_name": "Kochi", "destination_lat": 9.9312, "destination_lon": 76.2673},
        ],
    }
    response = client.post("/api/v1/recommend/markets", json=payload)
    assert response.status_code == 422


def test_full_system_endpoints_and_recommendation_regression(client):
    """Verify all 5 core POST endpoints plus root and health remain functional."""
    # 1. Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    endpoints = r_root.json()["endpoints"]
    assert "market_recommendation" in endpoints
    assert "profit_evaluation" in endpoints
    assert "price_prediction" in endpoints
    assert "transport_estimation" in endpoints
    assert "spoilage_estimation" in endpoints

    # 2. Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    # 3. Dashboard
    r_dash = client.get("/dashboard/")
    assert r_dash.status_code == 200
