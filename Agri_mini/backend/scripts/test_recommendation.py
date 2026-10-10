"""
Manual Verification Script for Phase 10: Multi-Market Comparison & TOPSIS Market Recommendation

Orchestrates:
  - ML Price Prediction (PredictionService)
  - Road Transportation Cost (TransportService)
  - Weather-Aware Transit Spoilage Loss (SpoilageService)
  - Expected Profit & Financial Evaluation (ProfitService)
  - Multi-Criteria TOPSIS Decision Analysis (RecommendationService)

Evaluates and ranks candidate APMC markets for:
Farmer Origin: Thrissur, Kerala (10.5276 N, 76.2144 E)
Commodity: Tomato (Hybrid)
Quantity: 1000 kg (10 quintals)
Vehicle: mini_truck
Prediction Date: 2026-08-28
Cultivation Cost: Rs 12,000
"""

import sys
from pathlib import Path
from datetime import date

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.database import SessionLocal
from app.schemas.recommendation import CandidateMarket, MarketRecommendationRequest
from app.services.recommendation_service import RecommendationService


def run_recommendation_verification():
    print("=" * 85)
    print("AGRI_MINI — PHASE 10: TOPSIS MULTI-MARKET RECOMMENDATION VERIFICATION")
    print("=" * 85)

    # 1. Setup Candidate Mandi Alternatives in Kerala
    candidate_markets = [
        CandidateMarket(
            market="Kochi (Ernakulam) Market",
            district="Ernakulam",
            state="Kerala",
            destination_name="Kochi, Kerala",
            destination_lat=9.9312,
            destination_lon=76.2673,
        ),
        CandidateMarket(
            market="Palakkad Wholesale Mandi",
            district="Palakkad",
            state="Kerala",
            destination_name="Palakkad, Kerala",
            destination_lat=10.7867,
            destination_lon=76.6548,
        ),
        CandidateMarket(
            market="Kozhikode Central Mandi",
            district="Kozhikode",
            state="Kerala",
            destination_name="Kozhikode, Kerala",
            destination_lat=11.2588,
            destination_lon=75.7804,
        ),
        CandidateMarket(
            market="Trivandrum APMC",
            district="Thiruvananthapuram",
            state="Kerala",
            destination_name="Thiruvananthapuram, Kerala",
            destination_lat=8.5241,
            destination_lon=76.9366,
        ),
    ]

    commodity = "Tomato"
    variety = "Hybrid"
    origin_name = "Thrissur, Kerala"
    origin_lat, origin_lon = 10.5276, 76.2144
    quantity_kg = 1000.0
    vehicle_type = "mini_truck"
    prediction_date = date(2026, 8, 28)
    production_cost = 12000.0

    print(f"\n[1] Farmer Shipment Parameters:")
    print(f"  Commodity        : {commodity} ({variety})")
    print(f"  Farm Origin      : {origin_name} ({origin_lat}, {origin_lon})")
    print(f"  Quantity Loaded  : {quantity_kg:.1f} kg ({quantity_kg / 100.0:.1f} quintals)")
    print(f"  Logistics Vehicle: {vehicle_type}")
    print(f"  Target Date      : {prediction_date.isoformat()}")
    print(f"  Production Cost  : Rs {production_cost:.2f}")
    print(f"  Candidate Mandis : {len(candidate_markets)} regional markets")
    print("-" * 85)

    db = None
    try:
        db = SessionLocal()
        service = RecommendationService()

        req = MarketRecommendationRequest(
            commodity=commodity,
            variety=variety,
            prediction_date=prediction_date,
            origin_name=origin_name,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            quantity_kg=quantity_kg,
            vehicle_type=vehicle_type,
            fuel_price_per_litre=95.0,
            production_cost=production_cost,
            candidate_markets=candidate_markets,
        )

        resp = service.recommend_markets(req, db=db)

        # 2. Display Configured Criteria & Weights
        print("\n[2] Configured Multi-Criteria Decision Model (TOPSIS):")
        print("-" * 85)
        print(f"  {'Criterion Name':<30} | {'Optimization':<12} | {'Weight':<8} | {'Explanation'}")
        print("-" * 85)
        for crit in resp.criteria_used:
            opt_label = "Maximize (Benefit)" if crit.criterion_type == "benefit" else "Minimize (Cost)"
            expl = "Net farmer profit" if crit.name == "expected_profit" else ("Selling rate" if crit.name == "predicted_price" else ("Freight charge" if crit.name == "transportation_cost" else ("Transit time" if crit.name == "transit_duration" else "Quality loss risk")))
            print(f"  {crit.display_name:<30} | {opt_label:<20} | {crit.weight:>5.2f}  | {expl}")
        print("-" * 85)

        # 3. Display Detailed Market Ranking Table
        print("\n[3] TOPSIS Multi-Market Evaluation & Ranking Table:")
        print("=" * 85)
        print(f" {'Rank':<4} | {'Candidate Market':<24} | {'Price/Qtl':<11} | {'Dist':<7} | {'Freight':<10} | {'Spoil%':<7} | {'Net Profit':<11} | {'TOPSIS Score'}")
        print("-" * 85)
        for item in resp.rankings:
            profit_str = f"Rs {item.expected_profit:.2f}" if item.expected_profit is not None else f"Rs {item.expected_net_return:.2f}"
            print(
                f" #{item.rank:<3} | {item.market:<24} | Rs {item.predicted_price_per_quintal:>7.2f} | {item.distance_km:>5.1f}km | "
                f"Rs {item.transportation_cost:>7.2f} | {item.estimated_spoilage_pct:>5.1f}% | {profit_str:>11} | {item.topsis_score:>8.4f} (D+: {item.distance_to_ideal_best:.3f}, D-: {item.distance_to_ideal_worst:.3f})"
            )
        print("=" * 85)

        # 4. Display Recommendation Summary
        rec = resp.recommended_market
        profit_rec_str = f"Rs {rec.expected_profit:.2f}" if rec.expected_profit is not None else f"Rs {rec.expected_net_return:.2f}"

        print(f"\n[RECOMMENDED MARKET]: {rec.market} ({rec.district}, {rec.state})")
        print(f"  TOPSIS Closeness Score : {rec.topsis_score:.4f} (Rank #{rec.rank})")
        print(f"  Expected Net Profit    : {profit_rec_str}")
        print(f"  Predicted Modal Price  : Rs {rec.predicted_price_per_quintal:.2f} / quintal")
        print(f"  Transportation Freight : Rs {rec.transportation_cost:.2f}")
        print(f"  Decision Rationale     : {rec.reason_summary}")
        print("=" * 85)
        print("\n[MARKET RECOMMENDATION SUCCESS]")
        print("=" * 85)

    except Exception as exc:
        print(f"\n[ERROR]: Recommendation execution failed: {exc}")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    run_recommendation_verification()
