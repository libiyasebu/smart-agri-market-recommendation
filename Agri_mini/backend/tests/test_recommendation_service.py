import pytest
import math
from datetime import date
from unittest.mock import MagicMock
from app.services.recommendation_service import RecommendationService
from app.schemas.recommendation import (
    CriterionInfo,
    CandidateMarket,
    MarketRecommendationRequest,
)
from app.schemas.profit import (
    ProfitEvaluationResponse,
    QuantityBreakdown,
    PriceInfo,
    SpoilageSummary,
    TransportSummary,
    FinancialBreakdown,
)


def test_topsis_criteria_resolution_and_weight_normalization():
    """Verify criteria selection based on production cost and weight normalization."""
    service = RecommendationService()

    # Case 1: Without production cost
    crit_no_prod = service.resolve_criteria_and_weights(has_production_cost=False)
    assert len(crit_no_prod) == 5
    assert crit_no_prod[0].name == "expected_net_return"
    assert crit_no_prod[0].criterion_type == "benefit"
    assert round(sum(c.weight for c in crit_no_prod), 4) == 1.0

    # Case 2: With production cost
    crit_prod = service.resolve_criteria_and_weights(has_production_cost=True)
    assert len(crit_prod) == 5
    assert crit_prod[0].name == "expected_profit"
    assert crit_prod[0].criterion_type == "benefit"
    assert round(sum(c.weight for c in crit_prod), 4) == 1.0

    # Case 3: Custom weights normalized safely
    custom = {
        "expected_net_return": 2.0,
        "predicted_price": 1.0,
        "transportation_cost": 1.0,
        "transit_duration": 0.5,
        "spoilage_risk_score": 0.5,
    }
    crit_custom = service.resolve_criteria_and_weights(has_production_cost=False, custom_weights=custom)
    assert round(sum(c.weight for c in crit_custom), 4) == 1.0
    assert crit_custom[0].weight == 0.4  # 2.0 / 5.0


def test_topsis_invalid_custom_weights_rejected():
    """Verify unsupported criteria keys or negative weights raise explicit ValueError."""
    service = RecommendationService()

    with pytest.raises(ValueError) as exc:
        service.resolve_criteria_and_weights(
            has_production_cost=False,
            custom_weights={"non_existent_metric": 0.5},
        )
    assert "Unsupported criterion key" in str(exc.value)

    with pytest.raises(ValueError) as exc2:
        service.resolve_criteria_and_weights(
            has_production_cost=False,
            custom_weights={"expected_net_return": -0.2},
        )
    assert "must be strictly positive" in str(exc2.value)


def test_pure_topsis_math_and_ranking_deterministic():
    """Verify pure TOPSIS calculation, score bounds [0, 1], and deterministic ranking."""
    service = RecommendationService()
    criteria = [
        CriterionInfo(name="expected_net_return", display_name="Net Return", criterion_type="benefit", weight=0.40),
        CriterionInfo(name="predicted_price", display_name="Price", criterion_type="benefit", weight=0.20),
        CriterionInfo(name="transportation_cost", display_name="Transport Cost", criterion_type="cost", weight=0.15),
        CriterionInfo(name="transit_duration", display_name="Duration", criterion_type="cost", weight=0.10),
        CriterionInfo(name="spoilage_risk_score", display_name="Spoilage Risk", criterion_type="cost", weight=0.15),
    ]

    # Alternative A: High return, low cost, close proximity (Clearly superior)
    # Alternative B: Low return, high cost, far distance (Inferior)
    candidates = [
        {
            "market": "Market A (Kochi)",
            "expected_net_return": 22000.0,
            "predicted_price": 2400.0,
            "transportation_cost": 1500.0,
            "transit_duration": 80.0,
            "spoilage_risk_score": 35.0,
            "distance_km": 80.0,
        },
        {
            "market": "Market B (Distant Mandi)",
            "expected_net_return": 16000.0,
            "predicted_price": 2100.0,
            "transportation_cost": 4200.0,
            "transit_duration": 280.0,
            "spoilage_risk_score": 65.0,
            "distance_km": 280.0,
        },
    ]

    ranked = service.calculate_topsis_rankings(candidates, criteria)

    assert len(ranked) == 2
    # Market A must be Rank #1 with higher TOPSIS score
    assert ranked[0]["market"] == "Market A (Kochi)"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["market"] == "Market B (Distant Mandi)"
    assert ranked[1]["rank"] == 2

    assert 0.0 <= ranked[0]["topsis_score"] <= 1.0
    assert 0.0 <= ranked[1]["topsis_score"] <= 1.0
    assert ranked[0]["topsis_score"] > ranked[1]["topsis_score"]

    # Re-running produces identical deterministic results
    ranked2 = service.calculate_topsis_rankings(candidates, criteria)
    assert ranked[0]["topsis_score"] == ranked2[0]["topsis_score"]


def test_topsis_identical_candidates_tie_handling():
    """Verify TOPSIS handles identical candidates without division-by-zero crashes."""
    service = RecommendationService()
    criteria = [
        CriterionInfo(name="expected_net_return", display_name="Net Return", criterion_type="benefit", weight=0.50),
        CriterionInfo(name="transportation_cost", display_name="Transport Cost", criterion_type="cost", weight=0.50),
    ]

    candidates = [
        {"market": "Market 1", "expected_net_return": 20000.0, "transportation_cost": 1000.0, "distance_km": 50.0},
        {"market": "Market 2", "expected_net_return": 20000.0, "transportation_cost": 1000.0, "distance_km": 50.0},
    ]

    ranked = service.calculate_topsis_rankings(candidates, criteria)
    assert len(ranked) == 2
    assert ranked[0]["topsis_score"] == 0.50
    assert ranked[1]["topsis_score"] == 0.50
    assert ranked[0]["rank"] == 1
    assert ranked[1]["rank"] == 2


def test_topsis_fewer_than_two_candidates_raises_error():
    """Verify TOPSIS rejects evaluation if fewer than 2 candidates provided."""
    service = RecommendationService()
    criteria = [
        CriterionInfo(name="expected_net_return", display_name="Net Return", criterion_type="benefit", weight=1.0)
    ]
    with pytest.raises(ValueError) as exc:
        service.calculate_topsis_rankings([{"market": "Only One", "expected_net_return": 100.0}], criteria)
    assert "at least 2 alternatives" in str(exc.value)


def test_topsis_nan_or_inf_value_raises_error():
    """Verify NaN or Inf in decision matrix is rejected."""
    service = RecommendationService()
    criteria = [
        CriterionInfo(name="expected_net_return", display_name="Net Return", criterion_type="benefit", weight=1.0)
    ]
    with pytest.raises(ValueError) as exc:
        service.calculate_topsis_rankings(
            [
                {"market": "M1", "expected_net_return": float("nan")},
                {"market": "M2", "expected_net_return": 100.0},
            ],
            criteria,
        )
    assert "Invalid metric value" in str(exc.value)


def test_mocked_multi_market_orchestration():
    """Verify multi-market recommendation workflow with mocked ProfitService."""
    mock_profit_service = MagicMock()

    def mock_eval(req, db):
        if "Kochi" in req.market:
            return ProfitEvaluationResponse(
                status="success",
                commodity="Tomato",
                variety="Hybrid",
                market=req.market,
                district=req.district,
                state="Kerala",
                origin="Thrissur",
                destination="Kochi",
                prediction_date=req.prediction_date,
                quantity=QuantityBreakdown(original_kg=1000.0, original_quintals=10.0, spoilage_pct=6.5, spoiled_kg=65.0, sellable_kg=935.0, sellable_quintals=9.35),
                price=PriceInfo(predicted_modal_price_per_quintal=2500.0, unit="INR/quintal", model_used="Random Forest (Tuned)"),
                spoilage=SpoilageSummary(risk_score=36.0, risk_level="MODERATE", estimated_spoilage_pct=6.5),
                transport=TransportSummary(distance_km=85.0, transit_duration_minutes=80.0, vehicle_type="mini_truck", vehicle_display_name="Mini Truck", number_of_trips=1, total_transport_cost=1500.0),
                financials=FinancialBreakdown(
                    gross_revenue_before_spoilage=25000.0,
                    spoilage_value_loss=1625.0,
                    gross_revenue_after_spoilage=23375.0,
                    transportation_cost=1500.0,
                    expected_net_return=21875.0,
                    production_cost=10000.0,
                    expected_profit=11875.0,
                    net_return_per_kg=21.88,
                    net_return_per_quintal=2187.5,
                ),
                currency="INR",
                result_type="expected_profit_with_production_cost",
                evaluation_notes="Test note",
                evaluation_timestamp="2026-08-28T10:00:00",
            )
        else:
            return ProfitEvaluationResponse(
                status="success",
                commodity="Tomato",
                variety="Hybrid",
                market=req.market,
                district=req.district,
                state="Kerala",
                origin="Thrissur",
                destination="Trivandrum",
                prediction_date=req.prediction_date,
                quantity=QuantityBreakdown(original_kg=1000.0, original_quintals=10.0, spoilage_pct=12.0, spoiled_kg=120.0, sellable_kg=880.0, sellable_quintals=8.8),
                price=PriceInfo(predicted_modal_price_per_quintal=2300.0, unit="INR/quintal", model_used="Random Forest (Tuned)"),
                spoilage=SpoilageSummary(risk_score=60.0, risk_level="HIGH", estimated_spoilage_pct=12.0),
                transport=TransportSummary(distance_km=280.0, transit_duration_minutes=270.0, vehicle_type="mini_truck", vehicle_display_name="Mini Truck", number_of_trips=1, total_transport_cost=3800.0),
                financials=FinancialBreakdown(
                    gross_revenue_before_spoilage=23000.0,
                    spoilage_value_loss=2760.0,
                    gross_revenue_after_spoilage=20240.0,
                    transportation_cost=3800.0,
                    expected_net_return=16440.0,
                    production_cost=10000.0,
                    expected_profit=6440.0,
                    net_return_per_kg=16.44,
                    net_return_per_quintal=1644.0,
                ),
                currency="INR",
                result_type="expected_profit_with_production_cost",
                evaluation_notes="Test note",
                evaluation_timestamp="2026-08-28T10:00:00",
            )

    mock_profit_service.evaluate_profit.side_effect = mock_eval

    service = RecommendationService(profit_service=mock_profit_service)

    req = MarketRecommendationRequest(
        commodity="Tomato",
        variety="Hybrid",
        prediction_date=date(2026, 8, 28),
        origin_name="Thrissur",
        origin_lat=10.5276,
        origin_lon=76.2144,
        quantity_kg=1000.0,
        production_cost=10000.0,
        candidate_markets=[
            CandidateMarket(
                market="Kochi Market",
                district="Ernakulam",
                state="Kerala",
                destination_name="Kochi",
                destination_lat=9.9312,
                destination_lon=76.2673,
            ),
            CandidateMarket(
                market="Trivandrum APMC",
                district="Thiruvananthapuram",
                state="Kerala",
                destination_name="Trivandrum",
                destination_lat=8.5241,
                destination_lon=76.9366,
            ),
        ],
    )

    resp = service.recommend_markets(req, db=MagicMock())

    assert resp.status == "success"
    assert resp.recommended_market.market == "Kochi Market"
    assert resp.recommended_market.rank == 1
    assert len(resp.rankings) == 2
    assert resp.rankings[0].market == "Kochi Market"
    assert resp.rankings[0].expected_profit == 11875.0
    assert resp.rankings[1].market == "Trivandrum APMC"
    assert resp.rankings[1].expected_profit == 6440.0
    assert resp.recommended_market.topsis_score > resp.rankings[1].topsis_score
    assert len(resp.failed_candidates) == 0


def test_candidate_failure_handling_with_remaining_valid_candidates():
    """Verify that if 1 out of 3 candidates fails, it is reported in failed_candidates while remaining 2 are ranked."""
    mock_profit_service = MagicMock()

    def mock_eval(req, db):
        if "BadRoute" in req.market:
            raise ValueError("No drivable road route found to island market")
        return ProfitEvaluationResponse(
            status="success",
            commodity="Tomato",
            variety="Hybrid",
            market=req.market,
            district=req.district,
            state="Kerala",
            origin="Thrissur",
            destination="Dest",
            prediction_date=req.prediction_date,
            quantity=QuantityBreakdown(original_kg=1000.0, original_quintals=10.0, spoilage_pct=5.0, spoiled_kg=50.0, sellable_kg=950.0, sellable_quintals=9.5),
            price=PriceInfo(predicted_modal_price_per_quintal=2400.0, unit="INR/quintal", model_used="Random Forest (Tuned)"),
            spoilage=SpoilageSummary(risk_score=35.0, risk_level="MODERATE", estimated_spoilage_pct=5.0),
            transport=TransportSummary(distance_km=70.0, transit_duration_minutes=60.0, vehicle_type="mini_truck", vehicle_display_name="Mini Truck", number_of_trips=1, total_transport_cost=1200.0),
            financials=FinancialBreakdown(
                gross_revenue_before_spoilage=24000.0,
                spoilage_value_loss=1200.0,
                gross_revenue_after_spoilage=22800.0,
                transportation_cost=1200.0,
                expected_net_return=21600.0,
                production_cost=None,
                expected_profit=None,
                net_return_per_kg=21.6,
                net_return_per_quintal=2160.0,
            ),
            currency="INR",
            result_type="expected_net_return_without_production_cost",
            evaluation_notes="Test note",
            evaluation_timestamp="2026-08-28T10:00:00",
        )

    mock_profit_service.evaluate_profit.side_effect = mock_eval
    service = RecommendationService(profit_service=mock_profit_service)

    req = MarketRecommendationRequest(
        commodity="Tomato",
        variety="Hybrid",
        prediction_date=date(2026, 8, 28),
        origin_name="Thrissur",
        origin_lat=10.5276,
        origin_lon=76.2144,
        quantity_kg=1000.0,
        candidate_markets=[
            CandidateMarket(market="Market Valid 1", district="D1", destination_name="Dest1", destination_lat=10.0, destination_lon=76.0),
            CandidateMarket(market="Market BadRoute", district="D2", destination_name="Dest2", destination_lat=11.0, destination_lon=77.0),
            CandidateMarket(market="Market Valid 2", district="D3", destination_name="Dest3", destination_lat=12.0, destination_lon=78.0),
        ],
    )

    resp = service.recommend_markets(req, db=MagicMock())
    assert resp.status == "success"
    assert len(resp.rankings) == 2
    assert len(resp.failed_candidates) == 1
    assert resp.failed_candidates[0].market == "Market BadRoute"
    assert "No drivable road route" in resp.failed_candidates[0].failure_reason
