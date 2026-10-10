"""
test_ceda_recommendation.py
Focused end-to-end integration test for POST /api/recommend/ceda
- Mocks OSRM routing so no external API is needed
- Uses genuine CEDA/weather data for price + spoilage
- Tests Banana (commodity_id=19) with 2 high-data markets
"""
import sys, json, math
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
ENDPOINT = "/api/recommend/ceda"

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: print(f"  [PASS] {name}"); PASS += 1
    else: print(f"  [FAIL] {name}  |  {detail}"); FAIL += 1

# Fake OSRM response for 2 different distances (mock varies by call count)
ROUTE_SHORT = {"status":"success","provider":"OSRM","distance_km":45.0,"duration_minutes":55.0,"geometry":{"type":"LineString","coordinates":[],"total_points":0}}
ROUTE_LONG  = {"status":"success","provider":"OSRM","distance_km":120.0,"duration_minutes":135.0,"geometry":{"type":"LineString","coordinates":[],"total_points":0}}
route_calls = []

def fake_get_route(self, origin_lat, origin_lon, dest_lat, dest_lon, **kw):
    route_calls.append((dest_lat, dest_lon))
    return ROUTE_SHORT if len(route_calls) % 2 == 1 else ROUTE_LONG

# Kozhikode: cid=19, mid=2157, did=591 (830 records)
# Kannur:    cid=19, mid=138,  did=589 (718 records)
PAYLOAD = {
    "commodity_id":   19,
    "quantity_kg":    500,
    "source_latitude":  11.25,
    "source_longitude": 75.78,
    "prediction_date": "2025-10-15",
    "candidate_markets": [
        {"market_id":2157,"district_id":591,"market_name":"Kozhikode Market",
         "destination_lat":11.2588,"destination_lon":75.7804},
        {"market_id":138, "district_id":589,"market_name":"Kannur Market",
         "destination_lat":11.8745,"destination_lon":75.3704},
    ]
}

print("\n[TEST 1] Valid 2-market recommendation (mocked OSRM)")
with patch("app.services.routing_service.RoutingDataService.get_route", fake_get_route):
    r = client.post(ENDPOINT, json=PAYLOAD)
check("HTTP 200",           r.status_code == 200, r.text[:300])
if r.status_code == 200:
    b = r.json()
    check("status==success",           b.get("status") == "success")
    check("commodity_name present",    bool(b.get("commodity_name")))
    check("recommended_market present",  "recommended_market" in b)
    check("markets list len == 2",     len(b.get("markets", [])) == 2)
    top = b["recommended_market"]
    check("top has market_name",       bool(top.get("market_name")))
    check("top has topsis_score",      top.get("topsis_score") is not None)
    check("topsis_score in [0,1]",     0.0 <= top["topsis_score"] <= 1.0)
    check("top has predicted_price",   top.get("predicted_price_per_quintal", 0) > 0)
    check("top has transport_cost",    top.get("transport_cost_inr", 0) >= 0)
    check("top has spoilage_risk",     top.get("spoilage_risk_score") is not None)
    check("top has net_return",        top.get("expected_net_return_inr") is not None)
    check("reason_summary present",    bool(top.get("reason_summary")))
    check("ranking_method == TOPSIS",  b.get("ranking_method") == "TOPSIS")
    for mkt in b["markets"]:
        pred = mkt.get("predicted_price_per_quintal", 0)
        check(f"market {mkt['market_name']} price > 0", pred > 0, f"pred={pred}")
        rev = mkt.get("expected_revenue_inr", 0)
        check(f"market {mkt['market_name']} revenue >= 0", rev >= 0, f"rev={rev}")
        tc = mkt.get("transport_cost_inr", -1)
        check(f"market {mkt['market_name']} transport_cost >= 0", tc >= 0, f"tc={tc}")
    print("\n  [RECOMMENDATION RESULT]")
    print(f"  Recommended: {top['market_name']}")
    print(f"  TOPSIS score: {top['topsis_score']:.4f}")
    print(f"  Predicted price: Rs {top['predicted_price_per_quintal']:.2f}/qtl")
    print(f"  Transport cost: Rs {top['transport_cost_inr']:.2f}")
    print(f"  Expected net return: Rs {top['expected_net_return_inr']:.2f}")
    print(f"  Reason: {top['reason_summary']}")

print("\n[TEST 2] Invalid commodity_id")
with patch("app.services.routing_service.RoutingDataService.get_route", fake_get_route):
    r2 = client.post(ENDPOINT, json={**PAYLOAD, "commodity_id": 9999})
check("HTTP 400 for bad commodity", r2.status_code == 400, r2.text[:200])

print("\n[TEST 3] Only 1 candidate market (Pydantic validation)")
bad = dict(PAYLOAD); bad["candidate_markets"] = [PAYLOAD["candidate_markets"][0]]
r3 = client.post(ENDPOINT, json=bad)
check("HTTP 422 for <2 markets", r3.status_code == 422, r3.text[:200])

print("\n[TEST 4] Old /api/v1/recommend/markets still registered")
r4 = client.post("/api/v1/recommend/markets", json={})
check("Old route not 404", r4.status_code != 404, r4.text[:100])

print()
print("=" * 55)
print(f"  RESULTS:  {PASS} passed  |  {FAIL} failed")
print("=" * 55)
sys.exit(0 if FAIL == 0 else 1)
