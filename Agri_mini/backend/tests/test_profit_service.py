import pytest
from datetime import date
from unittest.mock import MagicMock
from app.services.profit_service import ProfitService
from app.schemas.profit import ProfitEvaluationRequest
from app.schemas.prediction import PricePredictionResponse
from app.schemas.transport import TransportEstimateResponse
from app.schemas.spoilage import SpoilageEstimateResponse, WeatherMetrics, RiskFactorsBreakdown


def test_pure_financial_calculation_deterministic():
    """Verify basic financial formulas, revenue, spoilage value loss, and net returns."""
    service = ProfitService()
    # 1000 kg (10 quintals), price = 2500 Rs/qtl, spoilage = 5%, transport = 1500 Rs
    qty_breakdown, fin_breakdown, res_type, notes = service.calculate_financials(
        quantity_kg=1000.0,
        predicted_modal_price_per_quintal=2500.0,
        estimated_spoilage_pct=5.0,
        total_transport_cost=1500.0,
        production_cost=None,
    )

    # Quantity checks
    assert qty_breakdown.original_kg == 1000.0
    assert qty_breakdown.original_quintals == 10.0
    assert qty_breakdown.spoilage_pct == 5.0
    assert qty_breakdown.spoiled_kg == 50.0
    assert qty_breakdown.sellable_kg == 950.0
    assert qty_breakdown.sellable_quintals == 9.5

    # Revenue before spoilage: 10 * 2500 = 25000.0 Rs
    assert fin_breakdown.gross_revenue_before_spoilage == 25000.0

    # Revenue after spoilage: 9.5 * 2500 = 23750.0 Rs
    assert fin_breakdown.gross_revenue_after_spoilage == 23750.0

    # Spoilage value loss: 25000 - 23750 = 1250.0 Rs
    assert fin_breakdown.spoilage_value_loss == 1250.0

    # Transport cost: 1500.0 Rs
    assert fin_breakdown.transportation_cost == 1500.0

    # Expected net return: 23750 - 1500 = 22250.0 Rs
    assert fin_breakdown.expected_net_return == 22250.0
    assert fin_breakdown.expected_profit is None
    assert fin_breakdown.production_cost is None
    assert res_type == "expected_net_return_without_production_cost"

    # Unit returns
    assert fin_breakdown.net_return_per_kg == 22.25
    assert fin_breakdown.net_return_per_quintal == 2225.0


def test_financial_calculation_with_production_cost():
    """Verify that optional production cost yields correct expected_profit."""
    service = ProfitService()
    qty_breakdown, fin_breakdown, res_type, notes = service.calculate_financials(
        quantity_kg=1000.0,
        predicted_modal_price_per_quintal=2500.0,
        estimated_spoilage_pct=5.0,
        total_transport_cost=1500.0,
        production_cost=12000.0,  # Cultivation expense
    )

    assert fin_breakdown.production_cost == 12000.0
    # Expected profit: net return (22250) - production_cost (12000) = 10250.0 Rs
    assert fin_breakdown.expected_profit == 10250.0
    assert res_type == "expected_profit_with_production_cost"
    assert "cultivation/production cost" in notes.lower()


def test_zero_spoilage_boundary():
    """Verify zero spoilage keeps sellable quantity equal to original and zero spoilage loss."""
    service = ProfitService()
    qty_breakdown, fin_breakdown, _, _ = service.calculate_financials(
        quantity_kg=500.0,
        predicted_modal_price_per_quintal=3000.0,
        estimated_spoilage_pct=0.0,
        total_transport_cost=800.0,
    )
    assert qty_breakdown.spoiled_kg == 0.0
    assert qty_breakdown.sellable_kg == 500.0
    assert qty_breakdown.sellable_quintals == 5.0
    assert fin_breakdown.spoilage_value_loss == 0.0
    assert fin_breakdown.gross_revenue_before_spoilage == 15000.0
    assert fin_breakdown.gross_revenue_after_spoilage == 15000.0
    assert fin_breakdown.expected_net_return == 14200.0


def test_high_spoilage_scenario():
    """Verify heavy transit spoilage (e.g. 25% loss) correctly reduces volume and revenues."""
    service = ProfitService()
    qty_breakdown, fin_breakdown, _, _ = service.calculate_financials(
        quantity_kg=2000.0,  # 20 quintals
        predicted_modal_price_per_quintal=2000.0,
        estimated_spoilage_pct=25.0,
        total_transport_cost=2000.0,
    )
    assert qty_breakdown.spoiled_kg == 500.0
    assert qty_breakdown.sellable_kg == 1500.0
    assert qty_breakdown.sellable_quintals == 15.0
    assert fin_breakdown.gross_revenue_before_spoilage == 40000.0
    assert fin_breakdown.gross_revenue_after_spoilage == 30000.0
    assert fin_breakdown.spoilage_value_loss == 10000.0
    assert fin_breakdown.expected_net_return == 28000.0


def test_spoilage_and_transport_applied_exactly_once():
    """Explicitly verify that spoilage and transport costs are not double-deducted."""
    service = ProfitService()
    # 10 qtl @ 1000 Rs/qtl = 10000 gross. 10% spoilage = 1000 loss -> 9000 post-spoilage. Transport = 2000.
    _, fin, _, _ = service.calculate_financials(
        quantity_kg=1000.0,
        predicted_modal_price_per_quintal=1000.0,
        estimated_spoilage_pct=10.0,
        total_transport_cost=2000.0,
    )
    # Expected net return must be strictly 9000 - 2000 = 7000.0
    assert fin.expected_net_return == 7000.0
    assert fin.gross_revenue_after_spoilage == 9000.0
    assert fin.gross_revenue_before_spoilage == 10000.0


def test_invalid_financial_inputs_raise_errors():
    """Verify validation for negative or zero quantities, negative prices, and negative costs."""
    service = ProfitService()

    with pytest.raises(ValueError) as exc:
        service.calculate_financials(quantity_kg=0.0, predicted_modal_price_per_quintal=2000.0, estimated_spoilage_pct=5.0, total_transport_cost=100.0)
    assert "quantity_kg" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_financials(quantity_kg=100.0, predicted_modal_price_per_quintal=-500.0, estimated_spoilage_pct=5.0, total_transport_cost=100.0)
    assert "predicted_modal_price_per_quintal" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_financials(quantity_kg=100.0, predicted_modal_price_per_quintal=2000.0, estimated_spoilage_pct=5.0, total_transport_cost=-10.0)
    assert "total_transport_cost" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_financials(quantity_kg=100.0, predicted_modal_price_per_quintal=2000.0, estimated_spoilage_pct=5.0, total_transport_cost=100.0, production_cost=-50.0)
    assert "production_cost" in str(exc.value)


def test_mocked_multi_service_orchestration():
    """Test full orchestration with mocked Prediction, Transport, and Spoilage services."""
    mock_prediction = MagicMock()
    mock_prediction.predict_price.return_value = PricePredictionResponse(
        status="success",
        commodity="Tomato",
        market="Kochi Market",
        district="Ernakulam",
        state="Kerala",
        variety="Hybrid",
        prediction_date=date(2026, 8, 28),
        predicted_modal_price=2400.0,
        unit="INR/quintal",
        model_used="Random Forest (Tuned)",
        historical_data_points_used=14,
        latest_known_price=2450.0,
        weather_matched=True,
        faostat_matched=True,
        route_matched=True,
        features_used_count=54,
        prediction_timestamp="2026-08-28T10:00:00",
    )

    mock_transport = MagicMock()
    mock_transport.estimate_cost_from_coordinates.return_value = TransportEstimateResponse(
        status="success",
        origin="Thrissur",
        destination="Kochi",
        distance_km=84.89,
        estimated_duration_minutes=82.95,
        quantity_kg=1000.0,
        quantity_quintals=10.0,
        vehicle_type="mini_truck",
        vehicle_display_name="Mini Truck",
        vehicle_capacity_kg=1500.0,
        number_of_trips=1,
        fuel_efficiency_km_per_litre=12.0,
        fuel_required_litres=7.07,
        fuel_price_per_litre=95.0,
        fuel_cost=672.05,
        maintenance_cost=339.56,
        driver_cost=500.0,
        toll_charges=0.0,
        other_charges=0.0,
        single_trip_cost=1511.61,
        total_transport_cost=1511.61,
        transport_cost_per_kg=1.51,
        transport_cost_per_quintal=151.16,
        currency="INR",
        routing_provider="OSRM (OpenStreetMap)",
        cost_type="estimated",
    )

    mock_spoilage = MagicMock()
    mock_spoilage.estimate_spoilage_from_coordinates.return_value = SpoilageEstimateResponse(
        status="success",
        commodity="Tomato",
        origin="Thrissur",
        destination="Kochi",
        distance_km=84.89,
        transit_duration_minutes=82.95,
        weather=WeatherMetrics(temperature_mean_c=26.2, temperature_max_c=29.6, humidity_pct=89.0, precipitation_mm=2.3, source="database"),
        risk_score=39.0,
        risk_level="MODERATE",
        estimated_spoilage_pct=7.01,
        risk_factors=RiskFactorsBreakdown(base_perishability=55.0, temperature_stress=44.8, humidity_stress=54.0, transit_time_stress=23.2, rain_stress=0.0),
        weather_matched=True,
        weather_source="database",
        routing_provider="OSRM (OpenStreetMap)",
        estimation_type="weather-and-transit heuristic",
    )

    service = ProfitService(
        prediction_service=mock_prediction,
        transport_service=mock_transport,
        spoilage_service=mock_spoilage,
    )

    req = ProfitEvaluationRequest(
        commodity="Tomato",
        market="Kochi Market",
        district="Ernakulam",
        state="Kerala",
        variety="Hybrid",
        prediction_date=date(2026, 8, 28),
        origin_name="Thrissur",
        origin_lat=10.5276,
        origin_lon=76.2144,
        destination_name="Kochi",
        destination_lat=9.9312,
        destination_lon=76.2673,
        quantity_kg=1000.0,
        production_cost=8000.0,
    )

    res = service.evaluate_profit(req, db=MagicMock())

    assert res.status == "success"
    assert res.commodity == "Tomato"
    assert res.quantity.original_kg == 1000.0
    assert res.quantity.spoiled_kg == 70.1
    assert res.quantity.sellable_kg == 929.9
    assert res.price.predicted_modal_price_per_quintal == 2400.0
    assert res.spoilage.estimated_spoilage_pct == 7.01
    assert res.transport.total_transport_cost == 1511.61

    # Revenue: 9.299 * 2400 = 22317.60
    assert res.financials.gross_revenue_after_spoilage == 22317.60
    # Net return: 22317.60 - 1511.61 = 20805.99
    assert res.financials.expected_net_return == 20805.99
    # Profit: 20805.99 - 8000.0 = 12805.99
    assert res.financials.expected_profit == 12805.99
    assert res.result_type == "expected_profit_with_production_cost"
