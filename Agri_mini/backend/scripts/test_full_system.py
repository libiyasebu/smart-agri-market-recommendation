"""
Agri_mini - End-to-End API Smoke Test Script (Phase 12)
Sequentially validates all 5 core decision-support REST APIs + health endpoint
using the verified Tomato / Thrissur agro-logistics test scenario.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

def run_full_system_smoke_test():
    client = TestClient(app)
    all_passed = True

    print("=" * 85)
    print("AGRI_MINI -- PHASE 12: END-TO-END SYSTEM API SMOKE TEST")
    print("Scenario: Tomato (Hybrid) | Origin: Thrissur (10.5276, 76.2144) | Qty: 1000 kg")
    print("=" * 85)

    # -------------------------------------------------------------------------
    # 1. GET /health
    # -------------------------------------------------------------------------
    print("\n[1] GET /health")
    try:
        r = client.get("/health")
        if r.status_code == 200 and r.json().get("status") == "healthy":
            print(f"  HTTP {r.status_code} OK | Service: {r.json().get('service')} (v{r.json().get('version')})")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # 2. POST /api/v1/predict/price
    # -------------------------------------------------------------------------
    print("\n[2] POST /api/v1/predict/price")
    payload_pred = {
        "commodity": "Tomato",
        "variety": "Hybrid",
        "market": "Thrissur APMC",
        "district": "Thrissur",
        "state": "Kerala",
        "prediction_date": "2026-08-28"
    }
    try:
        r = client.post("/api/v1/predict/price", json=payload_pred)
        if r.status_code == 200:
            d = r.json()
            price = d.get("predicted_modal_price")
            model = d.get("model_used")
            feats = d.get("features_used_count")
            print(f"  HTTP {r.status_code} OK | Modal Price: Rs {price:.2f}/qtl | Model: {model} ({feats} features)")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # 3. POST /api/v1/transport/estimate
    # -------------------------------------------------------------------------
    print("\n[3] POST /api/v1/transport/estimate")
    payload_trans = {
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Palakkad, Kerala",
        "destination_lat": 10.7867,
        "destination_lon": 76.6548,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0
    }
    try:
        r = client.post("/api/v1/transport/estimate", json=payload_trans)
        if r.status_code == 200:
            d = r.json()
            dist = d.get("distance_km")
            time_m = d.get("estimated_duration_minutes")
            cost = d.get("total_transport_cost")
            print(f"  HTTP {r.status_code} OK | Distance: {dist:.1f} km | Duration: {time_m:.1f} min | Freight: Rs {cost:.2f}")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # 4. POST /api/v1/spoilage/estimate
    # -------------------------------------------------------------------------
    print("\n[4] POST /api/v1/spoilage/estimate")
    payload_spoil = {
        "commodity": "Tomato",
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Palakkad, Kerala",
        "destination_lat": 10.7867,
        "destination_lon": 76.6548,
        "transport_date": "2026-08-28"
    }
    try:
        r = client.post("/api/v1/spoilage/estimate", json=payload_spoil)
        if r.status_code == 200:
            d = r.json()
            score = d.get("risk_score")
            loss_pct = d.get("estimated_spoilage_pct")
            level = d.get("risk_level")
            print(f"  HTTP {r.status_code} OK | Risk Score: {score:.1f}/100 | Spoilage: {loss_pct:.2f}% | Level: {level}")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # 5. POST /api/v1/profit/evaluate
    # -------------------------------------------------------------------------
    print("\n[5] POST /api/v1/profit/evaluate")
    payload_profit = {
        "commodity": "Tomato",
        "variety": "Hybrid",
        "market": "Palakkad Wholesale Mandi",
        "district": "Palakkad",
        "state": "Kerala",
        "prediction_date": "2026-08-28",
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "destination_name": "Palakkad, Kerala",
        "destination_lat": 10.7867,
        "destination_lon": 76.6548,
        "quantity_kg": 1000.0,
        "vehicle_type": "mini_truck",
        "fuel_price_per_litre": 95.0,
        "production_cost": 12000.0
    }
    try:
        r = client.post("/api/v1/profit/evaluate", json=payload_profit)
        if r.status_code == 200:
            d = r.json()
            fin = d.get("financials", {})
            net_ret = fin.get("expected_net_return")
            profit = fin.get("expected_profit")
            print(f"  HTTP {r.status_code} OK | Net Return: Rs {net_ret:.2f} | Net Profit: Rs {profit:.2f}")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # 6. POST /api/v1/recommend/markets
    # -------------------------------------------------------------------------
    print("\n[6] POST /api/v1/recommend/markets")
    payload_rec = {
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
            {"market": "Palakkad Wholesale Mandi", "district": "Palakkad", "state": "Kerala", "destination_name": "Palakkad, Kerala", "destination_lat": 10.7867, "destination_lon": 76.6548},
            {"market": "Kochi (Ernakulam) Market", "district": "Ernakulam", "state": "Kerala", "destination_name": "Kochi, Kerala", "destination_lat": 9.9312, "destination_lon": 76.2673},
            {"market": "Kozhikode Central Mandi", "district": "Kozhikode", "state": "Kerala", "destination_name": "Kozhikode, Kerala", "destination_lat": 11.2588, "destination_lon": 75.7804},
            {"market": "Trivandrum APMC", "district": "Thiruvananthapuram", "state": "Kerala", "destination_name": "Thiruvananthapuram, Kerala", "destination_lat": 8.5241, "destination_lon": 76.9366},
        ]
    }
    try:
        r = client.post("/api/v1/recommend/markets", json=payload_rec)
        if r.status_code == 200:
            d = r.json()
            rec = d.get("recommended_market", {})
            ranks = d.get("rankings", [])
            print(f"  HTTP {r.status_code} OK | Evaluated: {len(ranks)} mandis")
            print(f"  Recommended Mandi : {rec.get('market')} (Rank #{rec.get('rank')})")
            print(f"  TOPSIS Closeness  : {rec.get('topsis_score'):.4f}")
            print(f"  Expected Profit   : Rs {rec.get('expected_profit'):.2f}")
            print("  --> [PASS]")
        else:
            print(f"  HTTP {r.status_code} ERROR: {r.text}")
            print("  --> [FAIL]")
            all_passed = False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  --> [FAIL]")
        all_passed = False

    # -------------------------------------------------------------------------
    # Final Result
    # -------------------------------------------------------------------------
    print("\n" + "=" * 85)
    if all_passed:
        print("[FULL SYSTEM TEST SUCCESS]")
        print("All 6 API endpoints executed and passed verification.")
        print("=" * 85)
        sys.exit(0)
    else:
        print("[FULL SYSTEM TEST FAILED]")
        print("One or more endpoint tests failed.")
        print("=" * 85)
        sys.exit(1)

if __name__ == "__main__":
    run_full_system_smoke_test()
