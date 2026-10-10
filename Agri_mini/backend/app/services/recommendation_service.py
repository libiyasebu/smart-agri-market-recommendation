import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.schemas.profit import ProfitEvaluationRequest, ProfitEvaluationResponse
from app.schemas.recommendation import (
    CandidateMarket,
    CriterionInfo,
    MarketRankItem,
    FailedCandidateMarket,
    RecommendedMarketSummary,
    MarketRecommendationRequest,
    MarketRecommendationResponse,
)
from app.services.profit_service import ProfitService


# -----------------------------------------------------------------------------
# Default Centralized TOPSIS Criteria and Weights
# -----------------------------------------------------------------------------
# Benefit criteria: higher is better
# Cost criteria: lower is better

DEFAULT_CRITERIA_WITHOUT_PRODUCTION_COST: List[Dict[str, Any]] = [
    {"name": "expected_net_return", "display_name": "Expected Net Return", "type": "benefit", "default_weight": 0.40},
    {"name": "predicted_price", "display_name": "Predicted Selling Price", "type": "benefit", "default_weight": 0.20},
    {"name": "transportation_cost", "display_name": "Transportation Cost", "type": "cost", "default_weight": 0.15},
    {"name": "transit_duration", "display_name": "Transit Duration", "type": "cost", "default_weight": 0.10},
    {"name": "spoilage_risk_score", "display_name": "Transit Spoilage Risk", "type": "cost", "default_weight": 0.15},
]

DEFAULT_CRITERIA_WITH_PRODUCTION_COST: List[Dict[str, Any]] = [
    {"name": "expected_profit", "display_name": "Expected Profit", "type": "benefit", "default_weight": 0.40},
    {"name": "predicted_price", "display_name": "Predicted Selling Price", "type": "benefit", "default_weight": 0.20},
    {"name": "transportation_cost", "display_name": "Transportation Cost", "type": "cost", "default_weight": 0.15},
    {"name": "transit_duration", "display_name": "Transit Duration", "type": "cost", "default_weight": 0.10},
    {"name": "spoilage_risk_score", "display_name": "Transit Spoilage Risk", "type": "cost", "default_weight": 0.15},
]


class RecommendationService:
    """
    Multi-Market Agricultural Decision-Support and Ranking Engine using TOPSIS
    (Technique for Order Preference by Similarity to Ideal Solution).
    """

    def __init__(self, profit_service: Optional[ProfitService] = None):
        self.profit_service = profit_service or ProfitService()

    # -------------------------------------------------------------------------
    # 1. Criteria & Weights Resolution
    # -------------------------------------------------------------------------

    def resolve_criteria_and_weights(
        self,
        has_production_cost: bool,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> List[CriterionInfo]:
        """
        Resolves criteria definitions and validates/normalizes weights to sum exactly to 1.0.
        """
        base_configs = (
            DEFAULT_CRITERIA_WITH_PRODUCTION_COST
            if has_production_cost
            else DEFAULT_CRITERIA_WITHOUT_PRODUCTION_COST
        )

        criteria_map = {c["name"]: dict(c) for c in base_configs}

        if custom_weights:
            # Validate custom weight keys
            for key, weight in custom_weights.items():
                if key not in criteria_map:
                    supported = ", ".join(criteria_map.keys())
                    raise ValueError(
                        f"Unsupported criterion key '{key}' in custom_weights. Supported criteria are: {supported}"
                    )
                if weight <= 0:
                    raise ValueError(f"Custom weight for '{key}' must be strictly positive (got {weight})")
                criteria_map[key]["default_weight"] = float(weight)

        # Normalize weights so sum is exactly 1.0
        total_weight = sum(c["default_weight"] for c in criteria_map.values())
        if total_weight <= 0:
            raise ValueError("Total criteria weight sum must be positive")

        result: List[CriterionInfo] = []
        for c in base_configs:
            norm_weight = round(criteria_map[c["name"]]["default_weight"] / total_weight, 4)
            result.append(
                CriterionInfo(
                    name=c["name"],
                    display_name=c["display_name"],
                    criterion_type=c["type"],
                    weight=norm_weight,
                )
            )

        # Minor rounding adjustment on the primary criterion so sum is exactly 1.0
        weight_sum = sum(c.weight for c in result)
        diff = round(1.0 - weight_sum, 4)
        if abs(diff) > 0.00001:
            result[0].weight = round(result[0].weight + diff, 4)

        return result

    # -------------------------------------------------------------------------
    # 2. Pure TOPSIS Calculation
    # -------------------------------------------------------------------------

    def calculate_topsis_rankings(
        self,
        candidate_data: List[Dict[str, Any]],
        criteria: List[CriterionInfo],
    ) -> List[Dict[str, Any]]:
        """
        Executes vector normalization, weighted distance to Ideal Best (A+) and Ideal Worst (A-),
        and computes relative closeness coefficient C_i for each candidate.
        """
        m = len(candidate_data)  # Number of alternatives
        n = len(criteria)        # Number of criteria

        if m < 2:
            raise ValueError(f"TOPSIS ranking requires at least 2 alternatives (got {m})")

        # 1. Build Decision Matrix X [m x n]
        matrix: List[List[float]] = []
        for cand in candidate_data:
            row: List[float] = []
            for crit in criteria:
                val = cand.get(crit.name)
                if val is None or math.isnan(val) or math.isinf(val):
                    raise ValueError(f"Invalid metric value for criterion '{crit.name}' in candidate '{cand.get('market')}': {val}")
                row.append(float(val))
            matrix.append(row)

        # 2. Column-wise Vector Normalization: r_ij = x_ij / sqrt(sum_k x_kj^2)
        norm_matrix: List[List[float]] = [[0.0] * n for _ in range(m)]
        for j in range(n):
            sum_sq = sum(matrix[i][j] ** 2 for i in range(m))
            col_norm = math.sqrt(sum_sq)
            for i in range(m):
                if col_norm == 0.0:
                    norm_matrix[i][j] = 0.0
                else:
                    norm_matrix[i][j] = matrix[i][j] / col_norm

        # 3. Apply Criteria Weights: v_ij = w_j * r_ij
        weighted_matrix: List[List[float]] = [[0.0] * n for _ in range(m)]
        for j in range(n):
            w = criteria[j].weight
            for i in range(m):
                weighted_matrix[i][j] = norm_matrix[i][j] * w

        # 4. Determine Ideal Best (A+) and Ideal Worst (A-)
        ideal_best: List[float] = [0.0] * n
        ideal_worst: List[float] = [0.0] * n

        for j in range(n):
            col_vals = [weighted_matrix[i][j] for i in range(m)]
            crit_type = criteria[j].criterion_type.lower()
            if crit_type == "benefit":
                ideal_best[j] = max(col_vals)
                ideal_worst[j] = min(col_vals)
            else:  # cost criterion
                ideal_best[j] = min(col_vals)
                ideal_worst[j] = max(col_vals)

        # 5. Calculate Euclidean Distances S_i+ and S_i-
        distances_best: List[float] = []
        distances_worst: List[float] = []
        closeness_scores: List[float] = []

        for i in range(m):
            d_best = math.sqrt(sum((weighted_matrix[i][j] - ideal_best[j]) ** 2 for j in range(n)))
            d_worst = math.sqrt(sum((weighted_matrix[i][j] - ideal_worst[j]) ** 2 for j in range(n)))
            distances_best.append(round(d_best, 6))
            distances_worst.append(round(d_worst, 6))

            # 6. Relative Closeness Coefficient: C_i = S_i- / (S_i+ + S_i-)
            total_dist = d_best + d_worst
            if total_dist == 0.0:
                # All candidates identical across all criteria
                score = 0.50
            else:
                score = d_worst / total_dist

            closeness_scores.append(round(max(0.0, min(1.0, score)), 4))

        # 7. Merge scores into candidate records and sort
        ranked_items: List[Dict[str, Any]] = []
        for i in range(m):
            item = dict(candidate_data[i])
            item["topsis_score"] = closeness_scores[i]
            item["distance_to_ideal_best"] = distances_best[i]
            item["distance_to_ideal_worst"] = distances_worst[i]
            ranked_items.append(item)

        # Sort descending by topsis_score; tie-break on expected_net_return / profit
        def get_tiebreaker_metric(x: Dict[str, Any]) -> float:
            val = x.get("expected_profit") if x.get("expected_profit") is not None else x.get("expected_net_return")
            return float(val) if val is not None else 0.0

        ranked_items.sort(
            key=lambda x: (
                x["topsis_score"],
                get_tiebreaker_metric(x),
                -x.get("distance_km", 0.0),
            ),
            reverse=True,
        )

        # Assign ranks
        for idx, item in enumerate(ranked_items, start=1):
            item["rank"] = idx

        return ranked_items

    # -------------------------------------------------------------------------
    # 3. Decision Rationale Formulator
    # -------------------------------------------------------------------------

    def generate_recommendation_verdict(
        self,
        top_item: Dict[str, Any],
        all_items: List[Dict[str, Any]],
        has_production_cost: bool,
    ) -> str:
        """
        Builds a transparent decision summary explaining why the top market scored highest.
        """
        market = top_item["market"]
        profit_val = top_item.get("expected_profit") if (has_production_cost and top_item.get("expected_profit") is not None) else top_item.get("expected_net_return")
        profit_label = "expected profit" if has_production_cost else "expected net return"
        price_val = top_item["predicted_price_per_quintal"]
        dist_val = top_item["distance_km"]
        cost_val = top_item["transportation_cost"]
        spoil_pct = top_item["estimated_spoilage_pct"]

        reasons: List[str] = []

        def get_cand_financial(x: Dict[str, Any]) -> float:
            val = x.get("expected_profit") if (has_production_cost and x.get("expected_profit") is not None) else x.get("expected_net_return")
            return float(val) if val is not None else 0.0

        # Check if top market has the highest financial return
        max_return = max(get_cand_financial(x) for x in all_items)
        if profit_val is not None and profit_val >= max_return:
            reasons.append(f"highest {profit_label} (Rs {profit_val:.2f})")

        # Check if top market has the shortest transit or lowest transport cost
        min_cost = min(x["transportation_cost"] for x in all_items)
        if cost_val <= min_cost:
            reasons.append(f"lowest freight cost (Rs {cost_val:.2f})")

        min_spoil = min(x["estimated_spoilage_pct"] for x in all_items)
        if spoil_pct <= min_spoil:
            reasons.append(f"minimal transit spoilage loss ({spoil_pct:.2f}%)")

        max_price = max(x["predicted_price_per_quintal"] for x in all_items)
        if price_val >= max_price:
            reasons.append(f"highest selling price (Rs {price_val:.2f}/qtl)")

        if not reasons:
            reasons.append(f"optimal weighted balance of selling price (Rs {price_val:.2f}/qtl) and freight logistics")

        joined_reasons = ", ".join(reasons)
        return (
            f"Recommended '{market}' as Rank #1 because it delivers the {joined_reasons} "
            f"over a {dist_val:.1f} km transit route with a TOPSIS closeness score of {top_item['topsis_score']:.4f}."
        )

    # -------------------------------------------------------------------------
    # 4. Multi-Market Evaluation Orchestration
    # -------------------------------------------------------------------------

    def recommend_markets(
        self,
        request: MarketRecommendationRequest,
        db: Session,
    ) -> MarketRecommendationResponse:
        """
        Orchestrates multi-market profit evaluations, builds the TOPSIS decision matrix,
        computes relative closeness rankings, and delivers decision-support recommendations.
        """
        has_production_cost = request.production_cost is not None
        criteria = self.resolve_criteria_and_weights(
            has_production_cost=has_production_cost,
            custom_weights=request.custom_weights,
        )

        evaluated_candidates: List[Dict[str, Any]] = []
        failed_candidates: List[FailedCandidateMarket] = []

        # 1. Evaluate each candidate destination market
        for cand in request.candidate_markets:
            profit_req = ProfitEvaluationRequest(
                commodity=request.commodity,
                variety=cand.variety or request.variety,
                market=cand.market,
                district=cand.district,
                state=cand.state,
                prediction_date=request.prediction_date,
                origin_name=request.origin_name,
                origin_lat=request.origin_lat,
                origin_lon=request.origin_lon,
                destination_name=cand.destination_name,
                destination_lat=cand.destination_lat,
                destination_lon=cand.destination_lon,
                quantity_kg=request.quantity_kg,
                vehicle_type=request.vehicle_type,
                fuel_price_per_litre=request.fuel_price_per_litre,
                toll_charges=request.toll_charges,
                other_charges=request.other_charges,
                production_cost=request.production_cost,
            )

            try:
                eval_resp: ProfitEvaluationResponse = self.profit_service.evaluate_profit(profit_req, db=db)
                cand_metrics = {
                    "market": cand.market,
                    "district": cand.district,
                    "state": cand.state,
                    "destination_name": cand.destination_name,
                    "destination_lat": cand.destination_lat,
                    "destination_lon": cand.destination_lon,
                    "distance_km": eval_resp.transport.distance_km,
                    "transit_duration_minutes": eval_resp.transport.transit_duration_minutes,
                    "transportation_cost": eval_resp.transport.total_transport_cost,
                    "predicted_price_per_quintal": eval_resp.price.predicted_modal_price_per_quintal,
                    "spoilage_risk_score": eval_resp.spoilage.risk_score,
                    "estimated_spoilage_pct": eval_resp.spoilage.estimated_spoilage_pct,
                    "sellable_quantity_kg": eval_resp.quantity.sellable_kg,
                    "gross_revenue_after_spoilage": eval_resp.financials.gross_revenue_after_spoilage,
                    "expected_net_return": eval_resp.financials.expected_net_return,
                    "production_cost": eval_resp.financials.production_cost,
                    "expected_profit": eval_resp.financials.expected_profit,
                    # Dimension mappings for TOPSIS
                    "expected_profit": eval_resp.financials.expected_profit if has_production_cost else None,
                    "predicted_price": eval_resp.price.predicted_modal_price_per_quintal,
                    "transit_duration": eval_resp.transport.transit_duration_minutes,
                }
                evaluated_candidates.append(cand_metrics)
            except Exception as e:
                failed_candidates.append(
                    FailedCandidateMarket(
                        market=cand.market,
                        district=cand.district,
                        failure_reason=str(e),
                    )
                )

        # 2. Check minimum candidate requirements
        if len(evaluated_candidates) < 2:
            failure_msgs = "; ".join([f"{f.market}: {f.failure_reason}" for f in failed_candidates])
            raise ValueError(
                f"Insufficient valid candidate markets to compute TOPSIS recommendation. "
                f"At least 2 successfully evaluated markets required, but only {len(evaluated_candidates)} succeeded. "
                f"Evaluation failures: {failure_msgs}"
            )

        # 3. Execute TOPSIS Ranking
        ranked_data = self.calculate_topsis_rankings(
            candidate_data=evaluated_candidates,
            criteria=criteria,
        )

        # 4. Construct Response Items
        rankings: List[MarketRankItem] = []
        for item in ranked_data:
            profit_val = item.get("expected_profit") if has_production_cost else item.get("expected_net_return")
            label = "Profit" if has_production_cost else "Net Return"
            verdict = (
                f"Rank #{item['rank']}: TOPSIS Score {item['topsis_score']:.4f} | "
                f"Expected {label}: Rs {profit_val:.2f} | "
                f"Price: Rs {item['predicted_price_per_quintal']:.2f}/qtl | "
                f"Distance: {item['distance_km']:.1f} km | "
                f"Freight: Rs {item['transportation_cost']:.2f} | "
                f"Spoilage: {item['estimated_spoilage_pct']:.2f}%"
            )
            rankings.append(
                MarketRankItem(
                    rank=item["rank"],
                    market=item["market"],
                    district=item["district"],
                    state=item["state"],
                    destination_name=item["destination_name"],
                    destination_lat=item["destination_lat"],
                    destination_lon=item["destination_lon"],
                    distance_km=item["distance_km"],
                    transit_duration_minutes=item["transit_duration_minutes"],
                    transportation_cost=item["transportation_cost"],
                    predicted_price_per_quintal=item["predicted_price_per_quintal"],
                    spoilage_risk_score=item["spoilage_risk_score"],
                    estimated_spoilage_pct=item["estimated_spoilage_pct"],
                    sellable_quantity_kg=item["sellable_quantity_kg"],
                    gross_revenue_after_spoilage=item["gross_revenue_after_spoilage"],
                    expected_net_return=item["expected_net_return"],
                    production_cost=item["production_cost"],
                    expected_profit=item["expected_profit"],
                    topsis_score=item["topsis_score"],
                    distance_to_ideal_best=item["distance_to_ideal_best"],
                    distance_to_ideal_worst=item["distance_to_ideal_worst"],
                    summary_verdict=verdict,
                )
            )

        # 5. Construct Recommended Market Summary
        top_cand = ranked_data[0]
        reason_summary = self.generate_recommendation_verdict(
            top_item=top_cand,
            all_items=ranked_data,
            has_production_cost=has_production_cost,
        )

        recommended_market = RecommendedMarketSummary(
            rank=1,
            market=top_cand["market"],
            district=top_cand["district"],
            state=top_cand["state"],
            topsis_score=top_cand["topsis_score"],
            expected_net_return=top_cand["expected_net_return"],
            expected_profit=top_cand.get("expected_profit"),
            predicted_price_per_quintal=top_cand["predicted_price_per_quintal"],
            transportation_cost=top_cand["transportation_cost"],
            spoilage_risk_score=top_cand["spoilage_risk_score"],
            reason_summary=reason_summary,
        )

        notes = (
            "Multi-market ranking computed using TOPSIS vector normalization and Euclidean distance to ideal best/worst solutions. "
            "Selling prices are forecasted by tuned Random Forest ML model; transit durations and logistics costs are calculated via OSRM; "
            "spoilage loss is derived from regional agro-meteorological conditions. Rankings reflect multi-criteria trade-offs under the specified weights."
        )

        return MarketRecommendationResponse(
            status="success",
            commodity=request.commodity,
            variety=request.variety,
            prediction_date=request.prediction_date,
            origin=request.origin_name,
            quantity_kg=request.quantity_kg,
            recommended_market=recommended_market,
            criteria_used=criteria,
            rankings=rankings,
            failed_candidates=failed_candidates,
            method="TOPSIS",
            currency="INR",
            recommendation_notes=notes,
            evaluation_timestamp=datetime.now().isoformat(),
        )
