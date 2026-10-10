from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.schemas.prediction import PricePredictionRequest
from app.schemas.transport import TransportEstimateRequest
from app.schemas.spoilage import SpoilageEstimateRequest
from app.schemas.profit import (
    QuantityBreakdown,
    PriceInfo,
    SpoilageSummary,
    TransportSummary,
    FinancialBreakdown,
    ProfitEvaluationRequest,
    ProfitEvaluationResponse,
)
from app.services.prediction_service import PredictionService
from app.services.transport_service import TransportService
from app.services.spoilage_service import SpoilageService


class ProfitService:
    """
    Agricultural Expected Profit and Financial Evaluation Service.
    Orchestrates:
      1. Machine Learning Price Prediction (PredictionService)
      2. Road Routing and Transportation Logistics Cost (TransportService)
      3. Weather-Aware Produce Spoilage & Transit Loss (SpoilageService)
    To calculate transparent sellable volumes, revenues, losses, and expected net returns.
    """

    def __init__(
        self,
        prediction_service: Optional[PredictionService] = None,
        transport_service: Optional[TransportService] = None,
        spoilage_service: Optional[SpoilageService] = None,
    ):
        self.prediction_service = prediction_service or PredictionService.get_instance()
        self.transport_service = transport_service or TransportService()
        self.spoilage_service = spoilage_service or SpoilageService()

    # -------------------------------------------------------------------------
    # 1. Pure Deterministic Financial Calculation
    # -------------------------------------------------------------------------

    def calculate_financials(
        self,
        quantity_kg: float,
        predicted_modal_price_per_quintal: float,
        estimated_spoilage_pct: float,
        total_transport_cost: float,
        production_cost: Optional[float] = None,
    ) -> Tuple[QuantityBreakdown, FinancialBreakdown, str, str]:
        """
        Pure calculation function for revenue, spoilage value loss, transport deduction,
        and expected net return.
        """
        if quantity_kg <= 0:
            raise ValueError(f"quantity_kg must be strictly greater than 0 ({quantity_kg})")
        if predicted_modal_price_per_quintal <= 0:
            raise ValueError(f"predicted_modal_price_per_quintal must be strictly greater than 0 ({predicted_modal_price_per_quintal})")
        if total_transport_cost < 0:
            raise ValueError(f"total_transport_cost cannot be negative ({total_transport_cost})")
        if production_cost is not None and production_cost < 0:
            raise ValueError(f"production_cost cannot be negative ({production_cost})")

        # 1. Weight and volume breakdown (1 quintal = 100 kg)
        original_quintals = quantity_kg / 100.0
        spoilage_pct = max(0.0, min(100.0, float(estimated_spoilage_pct)))

        # Physical produce loss applied exactly once
        spoiled_kg = round(quantity_kg * (spoilage_pct / 100.0), 3)
        sellable_kg = round(max(0.0, quantity_kg - spoiled_kg), 3)
        sellable_quintals = round(sellable_kg / 100.0, 5)

        # 2. Revenue calculations
        gross_revenue_before_spoilage = round(original_quintals * predicted_modal_price_per_quintal, 2)
        gross_revenue_after_spoilage = round(sellable_quintals * predicted_modal_price_per_quintal, 2)
        spoilage_value_loss = round(gross_revenue_before_spoilage - gross_revenue_after_spoilage, 2)

        # 3. Expected Net Return (Transportation deducted exactly once)
        expected_net_return = round(gross_revenue_after_spoilage - total_transport_cost, 2)

        # 4. Optional Production Cost & Profit
        if production_cost is not None:
            expected_profit = round(expected_net_return - float(production_cost), 2)
            result_type = "expected_profit_with_production_cost"
            notes = (
                f"Evaluation includes cultivation/production cost deduction of Rs {production_cost:.2f}. "
                f"Gross revenue reflects {spoilage_pct:.2f}% transit spoilage loss deduction, "
                f"and freight cost of Rs {total_transport_cost:.2f} is deducted."
            )
        else:
            expected_profit = None
            result_type = "expected_net_return_without_production_cost"
            notes = (
                "Expected Net Return represents gross market revenue minus transit spoilage loss and road transportation freight. "
                "Cultivation/production cost was not provided and is therefore not deducted. "
                "This value represents net cash return delivered to the farm gate."
            )

        # 5. Unit net returns
        net_return_per_kg = round(expected_net_return / quantity_kg, 2)
        net_return_per_quintal = round(expected_net_return / original_quintals, 2)

        quantity_breakdown = QuantityBreakdown(
            original_kg=round(quantity_kg, 2),
            original_quintals=round(original_quintals, 2),
            spoilage_pct=round(spoilage_pct, 2),
            spoiled_kg=round(spoiled_kg, 2),
            sellable_kg=round(sellable_kg, 2),
            sellable_quintals=round(sellable_quintals, 3),
        )

        financial_breakdown = FinancialBreakdown(
            gross_revenue_before_spoilage=gross_revenue_before_spoilage,
            spoilage_value_loss=spoilage_value_loss,
            gross_revenue_after_spoilage=gross_revenue_after_spoilage,
            transportation_cost=round(total_transport_cost, 2),
            expected_net_return=expected_net_return,
            production_cost=round(production_cost, 2) if production_cost is not None else None,
            expected_profit=expected_profit,
            net_return_per_kg=net_return_per_kg,
            net_return_per_quintal=net_return_per_quintal,
        )

        return quantity_breakdown, financial_breakdown, result_type, notes

    # -------------------------------------------------------------------------
    # 2. Multi-Module Orchestration
    # -------------------------------------------------------------------------

    def evaluate_profit(
        self,
        request: ProfitEvaluationRequest,
        db: Session,
    ) -> ProfitEvaluationResponse:
        """
        Orchestrates Price Prediction, Transportation Logistics, and Spoilage Risk
        to compute full expected market profit and returns.
        """
        # 1. Execute ML Price Prediction
        price_req = PricePredictionRequest(
            commodity=request.commodity,
            market=request.market,
            district=request.district,
            state=request.state,
            variety=request.variety,
            prediction_date=request.prediction_date,
        )
        price_resp = self.prediction_service.predict_price(price_req, db)
        predicted_price = float(price_resp.predicted_modal_price)

        # 2. Execute Transportation Cost Estimation
        trans_req = TransportEstimateRequest(
            origin_name=request.origin_name,
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            destination_name=request.destination_name,
            destination_lat=request.destination_lat,
            destination_lon=request.destination_lon,
            quantity_kg=request.quantity_kg,
            vehicle_type=request.vehicle_type,
            fuel_price_per_litre=request.fuel_price_per_litre,
            toll_charges=request.toll_charges,
            other_charges=request.other_charges,
        )
        trans_resp = self.transport_service.estimate_cost_from_coordinates(trans_req)
        total_transport_cost = float(trans_resp.total_transport_cost)

        # 3. Execute Spoilage Risk Estimation
        spoil_req = SpoilageEstimateRequest(
            commodity=request.commodity,
            origin_name=request.origin_name,
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            destination_name=request.destination_name,
            destination_lat=request.destination_lat,
            destination_lon=request.destination_lon,
            transport_date=request.prediction_date,
            temperature_override_c=request.temperature_override_c,
            humidity_override_pct=request.humidity_override_pct,
        )
        spoil_resp = self.spoilage_service.estimate_spoilage_from_coordinates(spoil_req, db=db)
        estimated_spoilage_pct = float(spoil_resp.estimated_spoilage_pct)

        # 4. Calculate Financials
        qty_breakdown, fin_breakdown, res_type, notes = self.calculate_financials(
            quantity_kg=request.quantity_kg,
            predicted_modal_price_per_quintal=predicted_price,
            estimated_spoilage_pct=estimated_spoilage_pct,
            total_transport_cost=total_transport_cost,
            production_cost=request.production_cost,
        )

        return ProfitEvaluationResponse(
            status="success",
            commodity=request.commodity,
            variety=request.variety,
            market=request.market,
            district=request.district,
            state=request.state,
            origin=request.origin_name,
            destination=request.destination_name,
            prediction_date=request.prediction_date,
            quantity=qty_breakdown,
            price=PriceInfo(
                predicted_modal_price_per_quintal=predicted_price,
                unit=price_resp.unit,
                model_used=price_resp.model_used,
                latest_known_price=price_resp.latest_known_price,
            ),
            spoilage=SpoilageSummary(
                risk_score=float(spoil_resp.risk_score),
                risk_level=spoil_resp.risk_level,
                estimated_spoilage_pct=estimated_spoilage_pct,
                estimation_type=spoil_resp.estimation_type,
            ),
            transport=TransportSummary(
                distance_km=float(trans_resp.distance_km),
                transit_duration_minutes=float(trans_resp.estimated_duration_minutes),
                vehicle_type=trans_resp.vehicle_type,
                vehicle_display_name=trans_resp.vehicle_display_name,
                number_of_trips=int(trans_resp.number_of_trips),
                total_transport_cost=total_transport_cost,
                routing_provider=trans_resp.routing_provider,
            ),
            financials=fin_breakdown,
            currency="INR",
            result_type=res_type,
            evaluation_notes=notes,
            evaluation_timestamp=datetime.now().isoformat(),
        )
