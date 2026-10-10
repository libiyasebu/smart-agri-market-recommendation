import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

import urllib.request
import urllib.error
from fastapi.testclient import TestClient
from app.main import app


def print_separator(char="=", length=95):
    print(char * length)


def test_via_http_url(url: str, payload: dict):
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/v1/predict/price",
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        status_code = resp.getcode()
        body = resp.read().decode("utf-8")
        return status_code, json.loads(body)


def main():
    parser = argparse.ArgumentParser(description="Test FastAPI Price Prediction Endpoint (Phase 6A)")
    parser.add_argument("--url", type=str, default=None, help="Live FastAPI base URL (e.g., http://127.0.0.1:8000)")
    parser.add_argument("--commodity", type=str, default="Tomato", help="Commodity name (default: Tomato)")
    parser.add_argument("--market", type=str, default="Thrissur APMC", help="Market name (default: Thrissur APMC)")
    parser.add_argument("--district", type=str, default="Thrissur", help="District name (default: Thrissur)")
    parser.add_argument("--state", type=str, default="Kerala", help="State name (default: Kerala)")
    parser.add_argument("--variety", type=str, default="Hybrid", help="Variety name (default: Hybrid)")
    parser.add_argument("--date", type=str, default="2026-08-28", help="Prediction date YYYY-MM-DD (default: 2026-08-28)")
    args = parser.parse_args()

    print_separator()
    print("  FASTAPI AGRICULTURAL PRICE PREDICTION API TEST (Phase 6A)")
    print_separator()

    payload = {
        "commodity": args.commodity,
        "market": args.market,
        "district": args.district,
        "state": args.state,
        "variety": args.variety,
        "prediction_date": args.date,
    }

    print(f"  [Request Payload]:")
    print(json.dumps(payload, indent=4))
    print_separator("-")

    status_code = None
    response_json = {}

    if args.url:
        print(f"  Mode: Live HTTP request to {args.url}...")
        try:
            status_code, response_json = test_via_http_url(args.url, payload)
        except urllib.error.HTTPError as e:
            status_code = e.code
            response_json = json.loads(e.read().decode("utf-8"))
        except Exception as e:
            print(f"  [ERROR] Connection failed to {args.url}: {e}")
            print("  Falling back to in-process FastAPI TestClient...")
            client = TestClient(app)
            resp = client.post("/api/v1/predict/price", json=payload)
            status_code = resp.status_code
            response_json = resp.json()
    else:
        print("  Mode: Direct FastAPI TestClient invocation...")
        client = TestClient(app)
        resp = client.post("/api/v1/predict/price", json=payload)
        status_code = resp.status_code
        response_json = resp.json()

    print(f"  [HTTP Status Code]: {status_code}")
    print("\n  [API Response JSON]:")
    print(json.dumps(response_json, indent=4))
    print_separator("-")

    if status_code == 200 and response_json.get("status") == "success":
        pred = response_json.get("predicted_modal_price")
        unit = response_json.get("unit")
        model = response_json.get("model_used")
        pts = response_json.get("historical_data_points_used")
        latest = response_json.get("latest_known_price")

        print(f"  -> Predicted Modal Price : Rs. {pred:.2f} ({unit})")
        print(f"  -> Latest Known Price    : Rs. {latest:.2f} (from {pts} prior observations)")
        print(f"  -> Model Used            : {model}")
        print(f"  -> Context Matches       : Weather={response_json.get('weather_matched')}, FAOSTAT={response_json.get('faostat_matched')}, Route={response_json.get('route_matched')}")
        print(f"  -> Total Model Features  : {response_json.get('features_used_count')} features")
        print_separator()
        print(" [API SUCCESS] FastAPI price prediction endpoint returned valid prediction successfully!")
    else:
        print_separator()
        print(" [API FAILURE] Prediction endpoint returned error response.")
        sys.exit(1)


if __name__ == "__main__":
    main()
