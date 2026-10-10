import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_dashboard_endpoint_returns_200_html(client):
    """Verify GET /dashboard/ returns HTTP 200 with complete decision-support markup."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")

    html = response.text
    # 1. Page Title & Brand
    assert "AI Agricultural Price Prediction & Decision-Support System" in html
    assert "AgriDecision AI" in html

    # 2. Workflow Navigation Tabs
    assert "workflow-tabs" in html
    assert "Price Forecast" in html
    assert "Smart Market Recommendation" in html

    # 3. Form Sections for Workflow 1 (Price Prediction)
    assert 'id="prediction-form"' in html
    assert 'id="commodity-input"' in html
    assert 'id="market-input"' in html
    assert 'id="results-card"' in html

    # 4. Form Sections for Workflow 2 (Smart Market Recommendation)
    assert 'id="recommendation-form"' in html
    assert 'id="rec-commodity-select"' in html
    assert 'id="candidate-markets-list"' in html
    assert 'id="rec-results-container"' in html
    assert 'class="card rec-hero-card"' in html
    assert 'class="ranking-table"' in html
    assert 'class="criteria-table"' in html
    assert 'id="rec-failed-candidates-box"' in html


def test_frontend_static_assets_load(client):
    """Verify static CSS stylesheet and JavaScript client load via /dashboard mount."""
    # CSS
    r_css = client.get("/dashboard/css/style.css")
    assert r_css.status_code == 200
    css = r_css.text
    assert "--primary-700" in css
    assert ".workflow-tabs" in css
    assert ".rec-hero-card" in css
    assert ".ranking-table" in css

    # JS
    r_js = client.get("/dashboard/js/app.js")
    assert r_js.status_code == 200
    js = r_js.text
    assert "/api/v1/predict/price" in js
    assert "/api/recommend/ceda" in js
    assert "handleRecommendationSubmit" in js
    assert "renderRecommendationResult" in js


def test_dashboard_displays_per_kg_price(client):
    """Verify Change 3: predicted price per kg conversion is displayed in HTML, CSS, and JS."""
    # HTML markup check
    r_html = client.get("/dashboard/")
    assert r_html.status_code == 200
    html = r_html.text
    # Workflow 1 hero price per kg
    assert 'id="res-hero-price-kg"' in html
    assert 'id="res-price-per-kg"' in html
    # Workflow 2 recommendation hero price per kg
    assert 'id="rec-hero-price-kg-val"' in html
    # Ranking table header
    assert "Price (Qtl &bull; kg)" in html or "Price / Qtl" in html

    # CSS styles check
    r_css = client.get("/dashboard/css/style.css")
    assert r_css.status_code == 200
    css = r_css.text
    assert ".hero-price-kg-row" in css
    assert ".fin-value-subrow" in css

    # JS logic check
    r_js = client.get("/dashboard/js/app.js")
    assert r_js.status_code == 200
    js = r_js.text
    assert "resHeroPriceKg" in js
    assert "recHeroPriceKgVal" in js
    assert "/ 100.0" in js or "/ 100" in js


def test_dashboard_contains_decision_support_transparency_notice(client):
    """Verify TOPSIS methodology and decision-support disclaimer appear in the HTML."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.text
    assert "Decision-Support Disclaimer" in html
    assert "TOPSIS" in html
    assert "Decision Priorities" in html


def test_recommendation_api_contract_for_frontend(client):
    """Verify real POST /api/v1/recommend/markets payload matches frontend expectations."""
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
        "toll_charges": 0.0,
        "other_charges": 0.0,
        "production_cost": 12000.0,
        "candidate_markets": [
            {
                "market": "Palakkad Wholesale Mandi",
                "district": "Palakkad",
                "state": "Kerala",
                "destination_name": "Palakkad, Kerala",
                "destination_lat": 10.7867,
                "destination_lon": 76.6548,
            },
            {
                "market": "Kochi (Ernakulam) Market",
                "district": "Ernakulam",
                "state": "Kerala",
                "destination_name": "Kochi, Kerala",
                "destination_lat": 9.9312,
                "destination_lon": 76.2673,
            },
        ],
    }

    response = client.post("/api/v1/recommend/markets", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["method"] == "TOPSIS"
    assert "recommended_market" in data
    assert "rankings" in data
    assert len(data["rankings"]) == 2
    assert "criteria_used" in data
    assert len(data["criteria_used"]) == 5

    rec = data["recommended_market"]
    assert "market" in rec
    assert "topsis_score" in rec
    assert "expected_profit" in rec
    assert "reason_summary" in rec


def test_system_endpoints_regression_with_frontend_mount(client):
    """Verify all backend APIs and monitoring endpoints remain functional."""
    # Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    endpoints = r_root.json()["endpoints"]
    assert "market_recommendation" in endpoints
    assert "profit_evaluation" in endpoints
    assert "price_prediction" in endpoints
    assert "transport_estimation" in endpoints
    assert "spoilage_estimation" in endpoints

    # Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"


def test_system_info_endpoint(client):
    """Verify GET /api/v1/system/info returns accurate metadata and model specs."""
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()
    assert "project_name" in data
    assert data["production_model"] == "Random Forest (Tuned)"
    assert data["feature_count"] == 54
    assert len(data["modules"]) == 5
    assert data["status"] == "operational"

