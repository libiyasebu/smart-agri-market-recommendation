import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.prediction_service import PredictionService


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_prediction_service_singleton_artifact_loading():
    service = PredictionService.get_instance()
    assert service.model is not None
    assert service.encoder is not None
    assert service.scaler is not None
    assert len(service.feature_names) == 54
    assert service.metadata.get("target_variable") == "modal_price"


def test_successful_price_prediction_endpoint(client):
    payload = {
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
    }

    response = client.post("/api/v1/predict/price", json=payload)
    assert response.status_code == 200, f"Error: {response.text}"

    data = response.json()
    assert data["status"] == "success"
    assert data["commodity"] == "Tomato"
    assert data["market"] == "Thrissur APMC"
    assert data["unit"] == "INR/quintal"
    assert isinstance(data["predicted_modal_price"], (int, float))
    assert data["predicted_modal_price"] > 0
    assert data["features_used_count"] == 54
    assert data["historical_data_points_used"] > 0
    assert "prediction_timestamp" in data


def test_prediction_for_another_commodity(client):
    payload = {
        "commodity": "Onion",
        "market": "Kochi (Ernakulam) Market",
        "district": "Ernakulam",
        "state": "Kerala",
        "variety": "Red / Nasik",
        "prediction_date": "2026-08-28",
    }

    response = client.post("/api/v1/predict/price", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["commodity"] == "Onion"
    assert data["predicted_modal_price"] > 1000.0


def test_unsupported_commodity_or_no_history_returns_400(client):
    payload = {
        "commodity": "DragonFruitNonExistent",
        "market": "UnknownMandi",
        "district": "UnknownDistrict",
        "state": "Kerala",
        "variety": "Exotic",
        "prediction_date": "2026-08-28",
    }

    response = client.post("/api/v1/predict/price", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient historical price records" in data["detail"]


def test_malformed_request_returns_422(client):
    # Missing prediction_date
    payload = {
        "commodity": "Tomato",
        "market": "Thrissur APMC",
        "district": "Thrissur",
    }

    response = client.post("/api/v1/predict/price", json=payload)
    assert response.status_code == 422


def test_empty_string_validation_error(client):
    payload = {
        "commodity": "   ",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "variety": "Hybrid",
        "prediction_date": "2026-08-28",
    }

    response = client.post("/api/v1/predict/price", json=payload)
    assert response.status_code == 422


def test_root_and_health_endpoints_still_functioning(client):
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert r_root.json()["status"] == "online"
    assert "price_prediction" in r_root.json()["endpoints"]

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"
