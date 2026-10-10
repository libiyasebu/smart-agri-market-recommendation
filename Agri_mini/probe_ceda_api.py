"""
Try different CEDA API market endpoints.
"""
import urllib.request
import json

CEDA_API_KEY = "7cc6f5aca769c93ff3caa553a39ba673a828e1cca75d7df4bea59576183cff56"
BASE_URL = "https://api.ceda.ashoka.edu.in/v1"

# Try GET /agmarknet/geographies to see what markets appear
endpoints_to_try = [
    ("GET", f"{BASE_URL}/agmarknet/geographies", None),
    ("GET", f"{BASE_URL}/agmarknet/markets?state_id=32&district_id=594", None),
    ("POST", f"{BASE_URL}/agmarknet/markets", json.dumps({"state_id": 32, "district_id": 594, "format": "json"}).encode()),
    ("POST", f"{BASE_URL}/agmarknet/markets", json.dumps({"census_state_id": 32, "census_district_id": 594}).encode()),
]

for method, url, data in endpoints_to_try:
    print(f"\n--- {method} {url} ---")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {CEDA_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "AgriMini/1.0",
        },
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"SUCCESS: {json.dumps(result, indent=2)[:2000]}")
    except urllib.error.HTTPError as e:
        body = e.read()[:300]
        print(f"HTTP {e.code}: {body}")
    except Exception as e:
        print(f"Error: {e}")
