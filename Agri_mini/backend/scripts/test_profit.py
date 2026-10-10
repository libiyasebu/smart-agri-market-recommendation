"""
Manual Verification Script for Phase 9: Expected Profit Evaluation

Orchestrates:
  - ML Price Prediction (PredictionService)
  - OSRM Road Transportation Cost (TransportService)
  - Weather-Aware Transit Spoilage Loss (SpoilageService)

Evaluates expected net financial return and accounting profit for:
Commodity: Tomato (Hybrid)
Origin: Thrissur, Kerala (10.5276 N, 76.2144 E)
Destination: Kochi (Ernakulam) Market (9.9312 N, 76.2673 E)
Quantity: 1000 kg
Vehicle: mini_truck
Date: 2026-08-28
"""

import sys
from pathlib import Path
from datetime import date

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.database import SessionLocal
from app.schemas.profit import ProfitEvaluationRequest
from app.services.profit_service import ProfitService
from app.services.routing_service import RoutingError, NoRouteFoundError, RoutingAPIError


def run_profit_verification():
    print("=" * 80)
    print("AGRI_MINI — PHASE 9: EXPECTED PROFIT EVALUATION VERIFICATION")
    print("=" * 80)

    # 1. Primary Scenario: Thrissur -> Kochi (Ernakulam) Market
    commodity = "Tomato"
    variety = "Hybrid"
    market = "Kochi (Ernakulam) Market"
    district = "Ernakulam"
    state = "Kerala"

    origin_name = "Thrissur, Kerala"
    origin_lat, origin_lon = 10.5276, 76.2144

    destination_name = "Kochi, Kerala"
    dest_lat, dest_lon = 9.9312, 76.2673

    quantity_kg = 1000.0
    vehicle_type = "mini_truck"
    prediction_date = date(2026, 8, 28)
    production_cost = 12000.0  # Optional cultivation/harvest cost (Rs 12,000)

    print(f"\n[1] Evaluating Primary Market Destination:")
    print(f"  Commodity        : {commodity} ({variety})")
    print(f"  Origin Farm      : {origin_name} ({origin_lat}, {origin_lon})")
    print(f"  Destination Mandi: {market}, {district}, {state}")
    print(f"  Quantity Loaded  : {quantity_kg:.1f} kg ({quantity_kg / 100.0:.1f} quintals)")
    print(f"  Vehicle Selected : {vehicle_type}")
    print(f"  Target Date      : {prediction_date.isoformat()}")
    print(f"  Production Cost  : Rs {production_cost:.2f}")
    print("-" * 80)

    db = None
    try:
        db = SessionLocal()
        service = ProfitService()

        req_primary = ProfitEvaluationRequest(
            commodity=commodity,
            market=market,
            district=district,
            state=state,
            variety=variety,
            prediction_date=prediction_date,
            origin_name=origin_name,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_name=destination_name,
            destination_lat=dest_lat,
            destination_lon=dest_lon,
            quantity_kg=quantity_kg,
            vehicle_type=vehicle_type,
            fuel_price_per_litre=95.0,
            production_cost=production_cost,
        )

        res = service.evaluate_profit(req_primary, db=db)

        print("\n[PROFIT EVALUATION SUCCESS]")
        print("=" * 80)
        print(f"  Result Designation : {res.result_type}")
        print("-" * 80)
        print("  1. MARKET PRICE FORECAST (PredictionService):")
        print(f"     - Predicted Modal Price    : Rs {res.price.predicted_modal_price_per_quintal:.2f} / quintal")
        print(f"     - Model Architecture       : {res.price.model_used}")
        print(f"     - Latest Recorded Price    : Rs {res.price.latest_known_price:.2f}" if res.price.latest_known_price else "     - Latest Recorded Price: N/A")
        print("-" * 80)
        print("  2. PHYSICAL QUANTITY & TRANSIT SPOILAGE (SpoilageService):")
        print(f"     - Original Harvest Volume  : {res.quantity.original_kg:.2f} kg ({res.quantity.original_quintals:.2f} quintals)")
        print(f"     - Spoilage Risk Score      : {res.spoilage.risk_score:.1f} / 100 ({res.spoilage.risk_level})")
        print(f"     - Estimated Spoilage Loss  : {res.quantity.spoilage_pct:.2f} %")
        print(f"     - Lost / Spoiled Produce   : {res.quantity.spoiled_kg:.2f} kg")
        print(f"     - Expected Sellable Volume : {res.quantity.sellable_kg:.2f} kg ({res.quantity.sellable_quintals:.3f} quintals)")
        print("-" * 80)
        print("  3. TRANSPORTATION & LOGISTICS (TransportService):")
        print(f"     - Road Distance            : {res.transport.distance_km:.2f} km")
        print(f"     - Transit Travel Duration  : {res.transport.transit_duration_minutes:.2f} minutes")
        print(f"     - Vehicle Used             : {res.transport.vehicle_display_name}")
        print(f"     - Total Transportation Cost: Rs {res.transport.total_transport_cost:.2f}")
        print("-" * 80)
        print("  4. COMPREHENSIVE FINANCIAL BREAKDOWN:")
        print(f"     - Gross Revenue (0% loss)  : Rs {res.financials.gross_revenue_before_spoilage:.2f}")
        print(f"     - Spoilage Value Loss      : - Rs {res.financials.spoilage_value_loss:.2f}")
        print(f"     - Realized Gross Revenue   : Rs {res.financials.gross_revenue_after_spoilage:.2f}")
        print(f"     - Transportation Freight   : - Rs {res.financials.transportation_cost:.2f}")
        print("     " + "-" * 40)
        print(f"     = EXPECTED NET RETURN      : Rs {res.financials.expected_net_return:.2f} {res.currency}")
        print(f"     - Production/Crop Cost     : - Rs {res.financials.production_cost:.2f}")
        print(f"     = EXPECTED PROFIT          : Rs {res.financials.expected_profit:.2f} {res.currency}")
        print("     " + "-" * 40)
        print(f"     - Net Return Per Kilogram  : Rs {res.financials.net_return_per_kg:.2f} / kg")
        print(f"     - Net Return Per Quintal   : Rs {res.financials.net_return_per_quintal:.2f} / quintal")
        print("=" * 80)

        # 2. Comparative Scenario: Distant Mandi with High Transport & Spoilage
        print("\n[2] Comparative Evaluation: Distant Market with Higher Freight & Spoilage Exposure:")
        print("    Destination: Trivandrum APMC (~280 km road distance)")
        print("-" * 80)
        req_distant = ProfitEvaluationRequest(
            commodity=commodity,
            market="Trivandrum APMC",
            district="Thiruvananthapuram",
            state="Kerala",
            variety=variety,
            prediction_date=prediction_date,
            origin_name=origin_name,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_name="Thiruvananthapuram, Kerala",
            destination_lat=8.5241,
            destination_lon=76.9366,
            quantity_kg=quantity_kg,
            vehicle_type=vehicle_type,
            fuel_price_per_litre=95.0,
            production_cost=production_cost,
        )

        res_distant = service.evaluate_profit(req_distant, db=db)

        print(f"  {'Metric':<30} | {'Primary (Kochi)':<20} | {'Distant (Trivandrum)':<20}")
        print("-" * 80)
        print(f"  {'Road Distance':<30} | {res.transport.distance_km:>17.2f} km | {res_distant.transport.distance_km:>17.2f} km")
        print(f"  {'Transit Duration':<30} | {res.transport.transit_duration_minutes:>15.1f} min | {res_distant.transport.transit_duration_minutes:>15.1f} min")
        print(f"  {'Estimated Spoilage Loss':<30} | {res.quantity.spoilage_pct:>18.2f} % | {res_distant.quantity.spoilage_pct:>18.2f} %")
        print(f"  {'Transportation Cost':<30} | Rs {res.transport.total_transport_cost:>15.2f} | Rs {res_distant.transport.total_transport_cost:>15.2f}")
        print(f"  {'Gross Revenue (Post-Loss)':<30} | Rs {res.financials.gross_revenue_after_spoilage:>15.2f} | Rs {res_distant.financials.gross_revenue_after_spoilage:>15.2f}")
        print(f"  {'EXPECTED NET RETURN':<30} | Rs {res.financials.expected_net_return:>15.2f} | Rs {res_distant.financials.expected_net_return:>15.2f}")
        print(f"  {'EXPECTED PROFIT':<30} | Rs {res.financials.expected_profit:>15.2f} | Rs {res_distant.financials.expected_profit:>15.2f}")
        print("=" * 80)
        print("  Comparison Summary: Greater transit distance increases freight costs and transit spoilage,")
        print("  demonstrating how spatial decision support guides optimal market destination selection.")
        print("=" * 80)

    except RoutingAPIError as rae:
        print(f"\n[CONTROLLED ROUTING ERROR]: {rae}")
    except NoRouteFoundError as nrfe:
        print(f"\n[CONTROLLED NO ROUTE]: {nrfe}")
    except Exception as exc:
        print(f"\n[ERROR]: Profit evaluation failed: {exc}")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    run_profit_verification()
