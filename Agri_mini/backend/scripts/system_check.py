"""
Agri_mini - Comprehensive System Health & Readiness Verification Script (Phase 12)
Validates Python runtime, environment config, PostgreSQL database, ORM tables,
production ML model artifacts, and all 5 backend decision-support services.
"""

import os
import sys
import json
from datetime import date
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def run_system_check():
    print("=" * 80)
    print("AGRI_MINI -- PHASE 12: SYSTEM HEALTH & READINESS VERIFICATION")
    print("=" * 80)

    failures = []
    warnings = []

    # 1. Python Environment Check
    print("\n[1] Python Runtime Environment:")
    py_ver = sys.version.split()[0]
    print(f"  Python Version: {py_ver} ({sys.executable})")
    if sys.version_info < (3, 10):
        failures.append(f"Python version >= 3.10 required, got {py_ver}")
    else:
        print("  [PASS] Python version compatible")

    # 2. Configuration & Settings Check
    print("\n[2] Environment Configuration:")
    try:
        from app.config import settings
        print(f"  Project Name: {settings.PROJECT_NAME}")
        print(f"  API Version : {settings.VERSION}")
        print(f"  Host / Port : {settings.HOST}:{settings.PORT}")
        print(f"  Database URL: {settings.sync_database_url.split('@')[-1] if '@' in settings.sync_database_url else 'configured'}")
        print("  [PASS] App Settings loaded successfully")
    except Exception as e:
        failures.append(f"Settings loading error: {e}")
        print(f"  [FAIL] Settings error: {e}")

    # 3. PostgreSQL Database Connection & Tables
    print("\n[3] PostgreSQL Database Connection & Tables:")
    try:
        from app.database import engine, SessionLocal
        from sqlalchemy import text, inspect

        with engine.connect() as conn:
            res = conn.execute(text("SELECT current_database(), version();")).fetchone()
            db_name, db_ver = res[0], res[1].split()[0]
            print(f"  Database Connected: {db_name} (PostgreSQL {db_ver})")

            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            print(f"  Tables Found: {existing_tables}")

            required_tables = ["market_prices", "weather_records", "faostat_indicators", "route_records"]
            for tbl in required_tables:
                if tbl in existing_tables:
                    cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl};")).scalar()
                    print(f"    - Table '{tbl}': {cnt:,} rows")
                    if cnt == 0:
                        warnings.append(f"Table '{tbl}' has 0 rows.")
                else:
                    failures.append(f"Missing required database table: {tbl}")
                    print(f"    [FAIL] Table '{tbl}' not found in database!")

            print("  [PASS] Database connectivity & table inspection complete")
    except Exception as e:
        failures.append(f"Database error: {e}")
        print(f"  [FAIL] Database connection failed: {e}")

    # 4. Production ML Model Artifacts
    print("\n[4] Production ML Model Artifacts:")
    artifacts_dir = backend_dir / "artifacts"
    model_file = artifacts_dir / "best_price_model.joblib"
    prep_file = artifacts_dir / "preprocessor.joblib"
    meta_file = artifacts_dir / "model_metadata.json"

    for f_path, label in [(model_file, "Tuned Price Model"), (prep_file, "Preprocessor Pipeline"), (meta_file, "Model Metadata JSON")]:
        if f_path.exists() and f_path.stat().st_size > 0:
            print(f"  - {label}: {f_path.name} ({f_path.stat().st_size:,} bytes) [FOUND]")
        else:
            failures.append(f"Missing artifact: {f_path.name}")
            print(f"  - {label}: {f_path.name} [MISSING]")

    # 5. Model Loading & In-Memory Verification
    print("\n[5] Model Loading & Deserialization:")
    try:
        import joblib
        model = joblib.load(model_file)
        preprocessor = joblib.load(prep_file)
        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        print(f"  Loaded Model Type    : {type(model).__name__}")
        print(f"  Selected Model Name  : {metadata.get('best_model_name')}")
        print(f"  Target Metric Target : {metadata.get('target_variable')} ({metadata.get('target_unit')})")
        print(f"  Validation MAE / R2  : {metadata.get('final_test_metrics', {}).get('mae')} / {metadata.get('final_test_metrics', {}).get('r2')}")
        print("  [PASS] Model and preprocessor loaded without errors")
    except Exception as e:
        failures.append(f"Model artifact loading error: {e}")
        print(f"  [FAIL] Could not load model artifacts: {e}")

    # 6. Backend Services Verification
    print("\n[6] Backend Services Verification:")
    db = SessionLocal()
    try:
        # 6a. Prediction Service
        try:
            from app.services.prediction_service import PredictionService
            from app.schemas.prediction import PricePredictionRequest
            pred_req = PricePredictionRequest(
                commodity="Tomato",
                market="Thrissur APMC",
                district="Thrissur",
                state="Kerala",
                variety="Hybrid",
                prediction_date=date(2026, 8, 28)
            )
            pred_svc = PredictionService.get_instance()
            pred_res = pred_svc.predict_price(pred_req, db)
            price_val = float(pred_res.predicted_modal_price)
            print(f"  [PASS] PredictionService: Rs {price_val:.2f}/qtl ({pred_res.model_used})")
        except Exception as e:
            failures.append(f"PredictionService failure: {e}")
            print(f"  [FAIL] PredictionService: {e}")

        # 6b. Transport Service
        try:
            from app.services.transport_service import TransportService
            from app.schemas.transport import TransportEstimateRequest
            trans_req = TransportEstimateRequest(
                origin_lat=10.5276, origin_lon=76.2144,
                destination_lat=10.7867, destination_lon=76.6548,
                quantity_kg=1000.0, vehicle_type="mini_truck"
            )
            trans_svc = TransportService()
            trans_res = trans_svc.estimate_cost_from_coordinates(trans_req)
            print(f"  [PASS] TransportService: {trans_res.distance_km:.1f} km, Rs {trans_res.total_transport_cost:.2f}")
        except Exception as e:
            failures.append(f"TransportService failure: {e}")
            print(f"  [FAIL] TransportService: {e}")

        # 6c. Spoilage Service
        try:
            from app.services.spoilage_service import SpoilageService
            from app.schemas.spoilage import SpoilageEstimateRequest
            spoil_req = SpoilageEstimateRequest(
                commodity="Tomato",
                origin_lat=10.5276, origin_lon=76.2144,
                destination_lat=10.7867, destination_lon=76.6548,
                transport_date=date(2026, 8, 28)
            )
            spoil_svc = SpoilageService()
            spoil_res = spoil_svc.estimate_spoilage_from_coordinates(spoil_req, db=db)
            print(f"  [PASS] SpoilageService: Risk Score {spoil_res.risk_score}, Spoilage {spoil_res.estimated_spoilage_pct:.2f}% ({spoil_res.risk_level})")
        except Exception as e:
            failures.append(f"SpoilageService failure: {e}")
            print(f"  [FAIL] SpoilageService: {e}")

        # 6d. Profit Service
        try:
            from app.services.profit_service import ProfitService
            from app.schemas.profit import ProfitEvaluationRequest
            profit_req = ProfitEvaluationRequest(
                commodity="Tomato",
                market="Palakkad Wholesale Mandi",
                district="Palakkad",
                state="Kerala",
                variety="Hybrid",
                prediction_date=date(2026, 8, 28),
                origin_lat=10.5276, origin_lon=76.2144,
                destination_lat=10.7867, destination_lon=76.6548,
                quantity_kg=1000.0,
                vehicle_type="mini_truck",
                production_cost=12000.0
            )
            profit_svc = ProfitService()
            profit_res = profit_svc.evaluate_profit(profit_req, db=db)
            print(f"  [PASS] ProfitService: Net Profit Rs {profit_res.financials.expected_profit:.2f} (Net Return Rs {profit_res.financials.expected_net_return:.2f})")
        except Exception as e:
            failures.append(f"ProfitService failure: {e}")
            print(f"  [FAIL] ProfitService: {e}")

        # 6e. Recommendation Service
        try:
            from app.services.recommendation_service import RecommendationService
            from app.schemas.recommendation import MarketRecommendationRequest, CandidateMarket
            rec_req = MarketRecommendationRequest(
                commodity="Tomato",
                variety="Hybrid",
                prediction_date=date(2026, 8, 28),
                origin_lat=10.5276, origin_lon=76.2144,
                origin_name="Thrissur, Kerala",
                quantity_kg=1000.0,
                vehicle_type="mini_truck",
                candidate_markets=[
                    CandidateMarket(market="Palakkad Wholesale Mandi", district="Palakkad", state="Kerala", destination_name="Palakkad, Kerala", destination_lat=10.7867, destination_lon=76.6548),
                    CandidateMarket(market="Kochi (Ernakulam) Market", district="Ernakulam", state="Kerala", destination_name="Kochi, Kerala", destination_lat=9.9312, destination_lon=76.2673),
                ],
                production_cost=12000.0
            )
            rec_svc = RecommendationService()
            rec_res = rec_svc.recommend_markets(rec_req, db=db)
            top_mandi = rec_res.recommended_market.market
            topsis_s = rec_res.recommended_market.topsis_score
            print(f"  [PASS] RecommendationService: Top Pick '{top_mandi}' (TOPSIS Score: {topsis_s:.4f})")
        except Exception as e:
            failures.append(f"RecommendationService failure: {e}")
            print(f"  [FAIL] RecommendationService: {e}")

    finally:
        db.close()

    # 7. Final Summary
    print("\n" + "=" * 80)
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print("-" * 80)

    if failures:
        print("SYSTEM CHECK FAILED")
        print("Issues found:")
        for f in failures:
            print(f"  [x] {f}")
        print("=" * 80)
        sys.exit(1)
    else:
        print("SYSTEM CHECK PASSED")
        print("All subsystems, database tables, ML artifacts, and decision engines are healthy.")
        print("=" * 80)
        sys.exit(0)

if __name__ == "__main__":
    run_system_check()
