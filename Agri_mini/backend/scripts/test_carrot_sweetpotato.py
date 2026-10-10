import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

markets = [
    {"market": "Thrissur APMC (Sakthan Market)", "district": "Thrissur", "state": "Kerala", "destination_name": "Thrissur, Kerala", "destination_lat": 10.5276, "destination_lon": 76.2144},
    {"market": "Chalakudy Wholesale Market", "district": "Thrissur", "state": "Kerala", "destination_name": "Chalakudy, Kerala", "destination_lat": 10.3070, "destination_lon": 76.3335},
    {"market": "Kunnamkulam Market", "district": "Thrissur", "state": "Kerala", "destination_name": "Kunnamkulam, Kerala", "destination_lat": 10.6508, "destination_lon": 76.0711},
    {"market": "Kodungallur Market", "district": "Thrissur", "state": "Kerala", "destination_name": "Kodungallur, Kerala", "destination_lat": 10.2216, "destination_lon": 76.1953}
]

def test_crop(commodity, variety, qty, vehicle):
    payload = {
        "commodity": commodity,
        "variety": variety,
        "prediction_date": "2026-08-28",
        "origin_name": "Thrissur, Kerala",
        "origin_lat": 10.5276,
        "origin_lon": 76.2144,
        "quantity_kg": qty,
        "vehicle_type": vehicle,
        "fuel_price_per_litre": 95.0,
        "production_cost": 12000.0,
        "candidate_markets": markets
    }
    
    try:
        r = client.post("/api/v1/recommend/markets", json=payload)
        print(f"[{commodity} + {qty} + {vehicle}] Status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            ranks = d.get("rankings", [])
            print(f"[{commodity}] Evaluated: {len(ranks)} mandis")
        else:
            print(f"[{commodity}] Error: {r.text}")
    except Exception as e:
        print(f"[{commodity}] Exception: {e}")

test_crop("Tomato", "Hybrid", 1000.0, "mini_truck")
test_crop("Banana", "Robusta", 50.0, "three_wheeler")
