"""
test_ceda_thrissur_recommendation.py
====================================
End-to-end tests for CEDA Thrissur market candidate integration:
- Tomato (commodity_id=78): 4 Thrissur candidates (147, 2152, 2366, 2364)
- Banana (commodity_id=19): 3 supported Thrissur candidates (147, 2366, 2364)
- Graceful partial failure handling for unsupported market combinations
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)

def test_thrissur_tomato_recommendation(client):
    """Controlled Tomato test with 4 Thrissur candidates from Thrissur farm."""
    payload = {
        "commodity_id": 78,
        "quantity_kg": 1000.0,
        "source_latitude": 10.5276,
        "source_longitude": 76.2144,
        "prediction_date": "2025-10-15",
        "candidate_markets": [
            {"market_id": 147, "district_id": 594, "market_name": "Thrissur Market 147", "destination_lat": 10.5276, "destination_lon": 76.2144},
            {"market_id": 2152, "district_id": 594, "market_name": "Thrissur Market 2152", "destination_lat": 10.3070, "destination_lon": 76.3335},
            {"market_id": 2366, "district_id": 594, "market_name": "Thrissur Market 2366", "destination_lat": 10.6508, "destination_lon": 76.0711},
            {"market_id": 2364, "district_id": 594, "market_name": "Thrissur Market 2364", "destination_lat": 10.2216, "destination_lon": 76.1953},
        ],
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "toll_charges": 0.0,
        "other_charges": 0.0,
        "production_cost": None,
    }

    response = client.post("/api/recommend/ceda", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["status"] == "success"
    assert data["commodity_id"] == 78
    assert data["commodity_name"] == "Tomato"
    assert data["quantity_kg"] == 1000.0
    assert data["ranking_method"] == "TOPSIS"

    # Verify recommended market structure
    rec = data["recommended_market"]
    assert rec["market_name"] in [
        "Thrissur APMC (Sakthan Market)",
        "Chalakudy Wholesale Market",
        "Kunnamkulam Market",
        "Kodungallur Market",
        "Thrissur Market 147",
        "Thrissur Market 2152",
        "Thrissur Market 2366",
        "Thrissur Market 2364",
    ]
    assert 0.0 <= rec["topsis_score"] <= 1.0
    assert rec["predicted_price_per_quintal"] > 0
    assert rec["transport_cost_inr"] >= 0
    assert rec["spoilage_risk_score"] >= 0
    assert rec["expected_net_return_inr"] > 0
    assert len(rec["reason_summary"]) > 0

    # Verify candidate evaluation: at least 2 ranked, total candidates accounted for
    markets = data["markets"]
    failed = data.get("failed_markets", [])
    assert len(markets) >= 2
    assert len(markets) + len(failed) == 4
    for idx, m in enumerate(markets, 1):
        assert m["rank"] == idx
        assert m["predicted_price_per_quintal"] > 0
        assert m["distance_km"] >= 0
        assert m["transit_duration_minutes"] >= 0
        assert m["transport_cost_inr"] >= 0
        assert m["estimated_spoilage_pct"] >= 0
        assert m["expected_net_return_inr"] > 0
        assert 0.0 <= m["topsis_score"] <= 1.0


def test_thrissur_banana_recommendation(client):
    """Controlled Banana test with 3 supported Thrissur candidates (147, 2366, 2364)."""
    payload = {
        "commodity_id": 19,
        "quantity_kg": 1000.0,
        "source_latitude": 10.5276,
        "source_longitude": 76.2144,
        "prediction_date": "2025-10-15",
        "candidate_markets": [
            {"market_id": 147, "district_id": 594, "market_name": "Thrissur Market 147", "destination_lat": 10.5276, "destination_lon": 76.2144},
            {"market_id": 2366, "district_id": 594, "market_name": "Thrissur Market 2366", "destination_lat": 10.6508, "destination_lon": 76.0711},
            {"market_id": 2364, "district_id": 594, "market_name": "Thrissur Market 2364", "destination_lat": 10.2216, "destination_lon": 76.1953},
        ],
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "toll_charges": 0.0,
        "other_charges": 0.0,
        "production_cost": None,
    }

    response = client.post("/api/recommend/ceda", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["status"] == "success"
    assert data["commodity_id"] == 19
    assert data["commodity_name"] == "Banana"
    markets = data["markets"]
    failed = data.get("failed_markets", [])
    assert len(markets) >= 2
    assert len(markets) + len(failed) == 3

    rec = data["recommended_market"]
    assert rec["predicted_price_per_quintal"] > 0
    assert rec["expected_net_return_inr"] > 0
    assert 0.0 <= rec["topsis_score"] <= 1.0


def test_thrissur_banana_graceful_failure_handling(client):
    """Verify that including an unsupported market (e.g. 2152 for Banana) reports it in failed_markets without crashing."""
    payload = {
        "commodity_id": 19,
        "quantity_kg": 1000.0,
        "source_latitude": 10.5276,
        "source_longitude": 76.2144,
        "prediction_date": "2025-10-15",
        "candidate_markets": [
            {"market_id": 147, "district_id": 594, "market_name": "Thrissur Market 147", "destination_lat": 10.5276, "destination_lon": 76.2144},
            {"market_id": 2152, "district_id": 594, "market_name": "Thrissur Market 2152", "destination_lat": 10.3070, "destination_lon": 76.3335},
            {"market_id": 2366, "district_id": 594, "market_name": "Thrissur Market 2366", "destination_lat": 10.6508, "destination_lon": 76.0711},
            {"market_id": 2364, "district_id": 594, "market_name": "Thrissur Market 2364", "destination_lat": 10.2216, "destination_lon": 76.1953},
        ],
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "toll_charges": 0.0,
        "other_charges": 0.0,
        "production_cost": None,
    }

    response = client.post("/api/recommend/ceda", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    # 3 markets evaluated and ranked
    assert len(data["markets"]) == 3
    # Market 2152 captured in failed_markets
    assert len(data["failed_markets"]) == 1
    failed = data["failed_markets"][0]
    assert failed["market_id"] == 2152
    assert "no historical records" in failed["failure_reason"]


def test_thrissur_banana_small_farmer_three_wheeler(client):
    """Verify small load (50 kg) recommendation pipeline with three_wheeler."""
    payload = {
        "commodity_id": 19,
        "quantity_kg": 50.0,
        "source_latitude": 10.5276,
        "source_longitude": 76.2144,
        "prediction_date": "2025-10-15",
        "candidate_markets": [
            {"market_id": 147, "district_id": 594, "market_name": "Thrissur Market 147", "destination_lat": 10.5276, "destination_lon": 76.2144},
            {"market_id": 2366, "district_id": 594, "market_name": "Thrissur Market 2366", "destination_lat": 10.6508, "destination_lon": 76.0711},
            {"market_id": 2364, "district_id": 594, "market_name": "Thrissur Market 2364", "destination_lat": 10.2216, "destination_lon": 76.1953},
        ],
        "vehicle_type": "three_wheeler",
        "fuel_price_per_litre": 95.0,
        "toll_charges": 0.0,
        "other_charges": 0.0,
        "production_cost": None,
    }

    response = client.post("/api/recommend/ceda", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert data["quantity_kg"] == 50.0

    # Compare against mini_truck to confirm three_wheeler is cheaper
    payload_mini = dict(payload)
    payload_mini["vehicle_type"] = "mini_truck"
    resp_mini = client.post("/api/recommend/ceda", json=payload_mini)
    assert resp_mini.status_code == 200
    data_mini = resp_mini.json()

    for m_tw, m_mt in zip(data["markets"], data_mini["markets"]):
        assert m_tw["transport_cost_inr"] < m_mt["transport_cost_inr"]

