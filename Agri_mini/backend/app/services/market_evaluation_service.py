"""
market_evaluation_service.py
=============================
Orchestrates the full CEDA-based market evaluation workflow:

  CedaPricePredictionService (CEDA 26-feature RF)
      ↓ predicted_modal_price
  RoutingDataService (OSRM)
      ↓ distance_km, duration_minutes
  TransportService.calculate_transport_cost()
      ↓ total_transport_cost
  SpoilageService (direct weather-based calculation)
      ↓ estimated_spoilage_pct, risk_score
  ProfitService.calculate_financials()
      ↓ expected_net_return, expected_profit
  RecommendationService.calculate_topsis_rankings()
      ↓ ranked markets

Design rules:
- Does NOT touch /api/v1/predict/price or /api/v1/recommend/markets
- Does NOT reload the RF model per market (singleton used)
- One bad market does NOT abort evaluation of valid others
- No synthetic data, no DB writes
"""

import math
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple

from app.services.price_prediction_service import (
    PricePredictionService,
    ACTIVE_COMMODITIES,
)
from app.services.routing_service import RoutingDataService, RoutingError
from app.services.transport_service import TransportService
from app.services.spoilage_service import SpoilageService
from app.services.profit_service import ProfitService
from app.services.recommendation_service import (
    RecommendationService,
    DEFAULT_CRITERIA_WITHOUT_PRODUCTION_COST,
    DEFAULT_CRITERIA_WITH_PRODUCTION_COST,
)
from app.schemas.recommendation import (
    CriterionInfo,
    MarketRankItem,
    FailedCandidateMarket,
    RecommendedMarketSummary,
)


# ── Schemas used internally (plain dataclasses, not Pydantic, for speed) ──────

# Canonical verified market display names (Thrissur district)
VERIFIED_MARKET_DISPLAY_NAMES: Dict[int, str] = {
    147:  "Thrissur APMC (Sakthan Market)",
    2152: "Chalakudy Wholesale Market",
    2366: "Kunnamkulam Market",
    2364: "Kodungallur Market",
}


class CedaCandidateMarket:
    __slots__ = [
        "market_id", "district_id", "market_name",
        "destination_lat", "destination_lon", "destination_name",
    ]
    def __init__(self, market_id, district_id, market_name,
                 destination_lat, destination_lon, destination_name=None):
        self.market_id       = market_id
        self.district_id     = district_id
        # Resolve generic fallback names to verified actual mandi names
        if market_id in VERIFIED_MARKET_DISPLAY_NAMES:
            if not market_name or market_name.startswith("Thrissur Market ") or market_name == "unknown":
                market_name = VERIFIED_MARKET_DISPLAY_NAMES[market_id]
        self.market_name     = market_name
        self.destination_lat = destination_lat
        self.destination_lon = destination_lon
        self.destination_name = destination_name or market_name


class MarketEvaluationService:
    """
    Singleton orchestrator for CEDA-based multi-market evaluation.
    All sub-services are reused and not re-instantiated per request.
    """

    _instance: Optional["MarketEvaluationService"] = None

    def __init__(self):
        self.price_svc     = PricePredictionService.get_instance()
        self.routing_svc   = RoutingDataService()
        self.transport_svc = TransportService(routing_service=self.routing_svc)
        self.spoilage_svc  = SpoilageService(routing_service=self.routing_svc)
        self.profit_svc    = ProfitService(
            transport_service=self.transport_svc,
            spoilage_service=self.spoilage_svc,
        )
        self.rec_svc = RecommendationService(profit_service=self.profit_svc)

    @classmethod
    def get_instance(cls) -> "MarketEvaluationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Main evaluation entry point
    # ------------------------------------------------------------------
    def evaluate(
        self,
        commodity_id:    int,
        quantity_kg:     float,
        source_lat:      float,
        source_lon:      float,
        prediction_date: date,
        candidate_markets: List[CedaCandidateMarket],
        vehicle_type:    str   = "mini_truck",
        fuel_price:      float = 95.0,
        toll_charges:    float = 0.0,
        other_charges:   float = 0.0,
        production_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates each candidate market through the full pipeline and returns
        a ranked recommendation dict ready for the FastAPI response schema.
        """
        if commodity_id not in ACTIVE_COMMODITIES:
            raise ValueError(
                f"commodity_id={commodity_id} is not an active commodity. "
                f"Valid IDs: {sorted(ACTIVE_COMMODITIES.keys())}"
            )
        if quantity_kg <= 0:
            raise ValueError("quantity_kg must be > 0")
        if len(candidate_markets) < 2:
            raise ValueError("At least 2 candidate markets required for TOPSIS ranking.")

        commodity_name = ACTIVE_COMMODITIES[commodity_id]
        has_prod_cost  = production_cost is not None
        evaluated: List[Dict[str, Any]] = []
        failed:    List[Dict[str, Any]] = []

        for cm in candidate_markets:
            try:
                result = self._evaluate_one_market(
                    commodity_id     = commodity_id,
                    commodity_name   = commodity_name,
                    quantity_kg      = quantity_kg,
                    source_lat       = source_lat,
                    source_lon       = source_lon,
                    prediction_date  = prediction_date,
                    cm               = cm,
                    vehicle_type     = vehicle_type,
                    fuel_price       = fuel_price,
                    toll_charges     = toll_charges,
                    other_charges    = other_charges,
                    production_cost  = production_cost,
                )
                evaluated.append(result)
            except Exception as exc:
                failed.append({
                    "market_name":    cm.market_name,
                    "district_id":    cm.district_id,
                    "market_id":      cm.market_id,
                    "failure_reason": str(exc),
                })

        if len(evaluated) < 2:
            fail_msgs = "; ".join(
                f"{f['market_name']} (mid={f['market_id']}): {f['failure_reason']}"
                for f in failed
            )
            raise ValueError(
                f"Fewer than 2 markets evaluated successfully — cannot rank. "
                f"Failures: {fail_msgs}"
            )

        # ── TOPSIS ranking using the existing RecommendationService ───────────
        criteria_cfg = (
            DEFAULT_CRITERIA_WITH_PRODUCTION_COST
            if has_prod_cost
            else DEFAULT_CRITERIA_WITHOUT_PRODUCTION_COST
        )
        # Build CriterionInfo list (mirrors resolve_criteria_and_weights default path)
        total_w = sum(c["default_weight"] for c in criteria_cfg)
        criteria = [
            CriterionInfo(
                name          = c["name"],
                display_name  = c["display_name"],
                criterion_type= c["type"],
                weight        = round(c["default_weight"] / total_w, 4),
            )
            for c in criteria_cfg
        ]
        # Minor rounding fix
        diff = round(1.0 - sum(c.weight for c in criteria), 4)
        if abs(diff) > 0.00001:
            criteria[0].weight = round(criteria[0].weight + diff, 4)

        ranked_data = self.rec_svc.calculate_topsis_rankings(evaluated, criteria)

        # ── Build ranked market items ─────────────────────────────────────────
        rankings = []
        for item in ranked_data:
            pf_val = item.get("expected_profit") if has_prod_cost else item.get("expected_net_return")
            label  = "Profit" if has_prod_cost else "Net Return"
            verdict = (
                f"Rank #{item['rank']}: TOPSIS={item['topsis_score']:.4f} | "
                f"{label}=Rs {pf_val:.2f} | "
                f"Price=Rs {item['predicted_price_per_quintal']:.2f}/qtl | "
                f"Distance={item['distance_km']:.1f}km | "
                f"Freight=Rs {item['transportation_cost']:.2f} | "
                f"Spoilage={item['estimated_spoilage_pct']:.2f}%"
            )
            rankings.append({
                "rank":                      item["rank"],
                "market_id":                 item["market_id"],
                "district_id":               item["district_id"],
                "market_name":               item["market_name"],
                "destination_lat":           item["destination_lat"],
                "destination_lon":           item["destination_lon"],
                "distance_km":               item["distance_km"],
                "transit_duration_minutes":  item["transit_duration_minutes"],
                "transport_cost_inr":        item["transportation_cost"],
                "predicted_price_per_quintal": item["predicted_price_per_quintal"],
                "spoilage_risk_score":        item["spoilage_risk_score"],
                "estimated_spoilage_pct":     item["estimated_spoilage_pct"],
                "sellable_quantity_kg":       item["sellable_quantity_kg"],
                "expected_revenue_inr":       item["gross_revenue_after_spoilage"],
                "expected_net_return_inr":    item["expected_net_return"],
                "production_cost_inr":        item.get("production_cost"),
                "expected_profit_inr":        item.get("expected_profit"),
                "topsis_score":               item["topsis_score"],
                "summary_verdict":            verdict,
            })

        top = ranked_data[0]
        reason = self.rec_svc.generate_recommendation_verdict(
            top_item         = top,
            all_items        = ranked_data,
            has_production_cost = has_prod_cost,
        )

        return {
            "commodity_id":       commodity_id,
            "commodity_name":     commodity_name,
            "quantity_kg":        quantity_kg,
            "prediction_date":    str(prediction_date),
            "source_lat":         source_lat,
            "source_lon":         source_lon,
            "recommended_market": {
                "rank":                        1,
                "market_id":                   top["market_id"],
                "district_id":                 top["district_id"],
                "market_name":                 top["market_name"],
                "topsis_score":                top["topsis_score"],
                "predicted_price_per_quintal": top["predicted_price_per_quintal"],
                "transport_cost_inr":          top["transportation_cost"],
                "spoilage_risk_score":         top["spoilage_risk_score"],
                "expected_net_return_inr":     top["expected_net_return"],
                "expected_profit_inr":         top.get("expected_profit"),
                "reason_summary":              reason,
            },
            "markets":            rankings,
            "failed_markets":     failed,
            "ranking_method":     "TOPSIS",
            "criteria_used":      [
                {"name": c.name, "type": c.criterion_type, "weight": c.weight}
                for c in criteria
            ],
            "evaluation_timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Per-market evaluation
    # ------------------------------------------------------------------
    def _evaluate_one_market(
        self,
        commodity_id:    int,
        commodity_name:  str,
        quantity_kg:     float,
        source_lat:      float,
        source_lon:      float,
        prediction_date: date,
        cm:              CedaCandidateMarket,
        vehicle_type:    str,
        fuel_price:      float,
        toll_charges:    float,
        other_charges:   float,
        production_cost: Optional[float],
    ) -> Dict[str, Any]:
        """Single market evaluation — raises on any failure."""

        # 1. CEDA ML price prediction
        pred_price, n_pts, latest_price, wx_note = self.price_svc.predict(
            commodity_id    = commodity_id,
            district_id     = cm.district_id,
            market_id       = cm.market_id,
            prediction_date = prediction_date,
        )

        # 2. OSRM routing
        route = self.routing_svc.get_route(
            origin_lat  = source_lat,
            origin_lon  = source_lon,
            dest_lat    = cm.destination_lat,
            dest_lon    = cm.destination_lon,
        )
        distance_km       = float(route["distance_km"])
        duration_minutes  = float(route["duration_minutes"])

        # 3. Transport cost (pure calculation — no second OSRM call)
        trans_resp = self.transport_svc.calculate_transport_cost(
            distance_km          = distance_km,
            duration_minutes     = duration_minutes,
            quantity_kg          = quantity_kg,
            vehicle_type         = vehicle_type,
            fuel_price_per_litre = fuel_price,
            toll_charges         = toll_charges,
            other_charges        = other_charges,
            origin_name          = "Farm",
            destination_name     = cm.destination_name,
        )
        total_transport_cost = float(trans_resp.total_transport_cost)

        # 4. Spoilage risk (pure calculation using duration + commodity profile)
        # Use cached weather from price_svc history for this district
        wx_rows = PricePredictionService._history
        wx = wx_rows[
            (wx_rows["district_id"] == cm.district_id) &
            (wx_rows["date"] <= str(prediction_date))
        ].sort_values("date")
        if len(wx) == 0:
            # Fallback: Kerala average
            temp_mean, temp_max, humidity = 27.5, 32.0, 82.0
        else:
            wx_last   = wx.iloc[-1]
            temp_mean = float(wx_last.get("temperature_mean_c", 27.5))
            temp_max  = float(wx_last.get("temperature_max_c", 32.0))
            humidity  = float(wx_last.get("humidity_mean_pct", 82.0))

        spoil_resp = self.spoilage_svc.calculate_spoilage_risk(
            commodity        = commodity_name,
            distance_km      = distance_km,
            duration_minutes = duration_minutes,
            temp_mean_c      = temp_mean,
            temp_max_c       = temp_max,
            humidity_pct     = humidity,
            origin_name      = "Farm",
            destination_name = cm.destination_name,
        )
        risk_score   = float(spoil_resp.risk_score)
        spoilage_pct = float(spoil_resp.estimated_spoilage_pct)

        # 5. Financial calculation (reuse ProfitService pure function)
        qty_bd, fin_bd, _, _ = self.profit_svc.calculate_financials(
            quantity_kg                      = quantity_kg,
            predicted_modal_price_per_quintal= pred_price,
            estimated_spoilage_pct           = spoilage_pct,
            total_transport_cost             = total_transport_cost,
            production_cost                  = production_cost,
        )

        # 6. Build TOPSIS-compatible metric dict
        return {
            # Identity
            "market_id":             cm.market_id,
            "district_id":           cm.district_id,
            "market_name":           cm.market_name,
            # Aliases expected by generate_recommendation_verdict
            "market":                cm.market_name,
            "district":              str(cm.district_id),
            "state":                 "Kerala",
            "destination_name":      cm.destination_name,
            "destination_lat":       cm.destination_lat,
            "destination_lon":       cm.destination_lon,
            # TOPSIS fields (names MUST match DEFAULT_CRITERIA keys)
            "expected_net_return":   float(fin_bd.expected_net_return),
            "expected_profit":       float(fin_bd.expected_profit) if fin_bd.expected_profit is not None else None,
            "predicted_price":       float(pred_price),
            "transportation_cost":   total_transport_cost,
            "transit_duration":      duration_minutes,
            "spoilage_risk_score":   risk_score,
            # Extra detail fields
            "predicted_price_per_quintal": float(pred_price),
            "distance_km":                 distance_km,
            "transit_duration_minutes":    duration_minutes,
            "estimated_spoilage_pct":      spoilage_pct,
            "sellable_quantity_kg":        float(qty_bd.sellable_kg),
            "gross_revenue_after_spoilage":float(fin_bd.gross_revenue_after_spoilage),
            "production_cost":             production_cost,
        }
