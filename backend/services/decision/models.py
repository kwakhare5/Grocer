"""GROCER v2 Decision Engine -- Pure deterministic models.

Implements spec section 14 (decision pipeline), section 15 (transfer logic /
safe excess / hard constraints), section 16 (configurable weighted scoring),
section 17 (recommendation object + reason codes).

All logic is pure Python -- no async, no DB.  Easily unit-tested.
The DecisionOrchestrator (engine.py) owns DB I/O and event emission.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Reason codes (spec section 17)
# ---------------------------------------------------------------------------

class ReasonCode(str, enum.Enum):
    HIGH_STOCKOUT_RISK          = "HIGH_STOCKOUT_RISK"
    SOURCE_HAS_SAFE_EXCESS      = "SOURCE_HAS_SAFE_EXCESS"
    SUPPLIER_TOO_SLOW           = "SUPPLIER_TOO_SLOW"
    LOW_TRANSFER_DISTANCE       = "LOW_TRANSFER_DISTANCE"
    HIGH_SPOILAGE_RISK          = "HIGH_SPOILAGE_RISK"
    DISCOUNT_CAN_ACCELERATE     = "DISCOUNT_CAN_ACCELERATE"
    NO_SAFE_TRANSFER_SOURCE     = "NO_SAFE_TRANSFER_SOURCE"
    INVENTORY_HEALTHY           = "INVENTORY_HEALTHY"
    EXPIRY_DISTANT              = "EXPIRY_DISTANT"
    SUPPLIER_RELIABLE           = "SUPPLIER_RELIABLE"
    STOCKOUT_RISK_LOW           = "STOCKOUT_RISK_LOW"
    MULTIPLE_STORES_NEED_REPLEN = "MULTIPLE_STORES_NEED_REPLEN"
    TRANSFER_NOT_FEASIBLE       = "TRANSFER_NOT_FEASIBLE"
    WOULD_DEPLETE_SOURCE        = "WOULD_DEPLETE_SOURCE"
    EXCEEDS_MAX_DISTANCE        = "EXCEEDS_MAX_DISTANCE"
    CANNOT_ARRIVE_IN_TIME       = "CANNOT_ARRIVE_IN_TIME"


# ---------------------------------------------------------------------------
# Configurable scoring weights (spec section 16)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoringWeights:
    """All scoring weights in one place -- no magic numbers scattered."""
    stockout_risk_reduction: float  = 0.35
    spoilage_reduction: float       = 0.25
    availability_improvement: float = 0.20
    transfer_cost_penalty: float    = 0.10
    supplier_delay_penalty: float   = 0.05
    distance_penalty: float         = 0.05
    source_risk_penalty: float      = 0.00

    # Operational policy constants
    safety_window_hours: float      = 24.0
    safety_buffer_fraction: float   = 0.15
    max_transfer_distance_km: float = 20.0
    transfer_speed_kmh: float       = 30.0


DEFAULT_WEIGHTS = ScoringWeights()


# ---------------------------------------------------------------------------
# Input containers for each action type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransferInput:
    """All information needed to evaluate a transfer candidate."""
    source_store_id: uuid.UUID
    destination_store_id: uuid.UUID
    product_id: uuid.UUID
    source_quantity: int
    source_forecast_demand_24h: float
    source_safety_stock: int
    destination_quantity: int
    destination_forecast_demand_24h: float
    destination_forecast_demand_48h: float
    destination_lead_time_hours: int
    destination_stockout_probability: float
    distance_km: float
    transfer_quantity: int
    destination_spoilage_probability: float = 0.0


@dataclass(frozen=True)
class ReorderInput:
    """All information needed to evaluate a reorder candidate."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    supplier_lead_time_hours: int
    hours_to_stockout: float
    current_quantity: int
    forecast_demand_24h: float
    reorder_quantity: int
    stockout_probability: float


@dataclass(frozen=True)
class DiscountInput:
    """All information needed to evaluate a discount candidate."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    at_risk_quantity: int
    hours_to_expiry: float
    forecast_demand_before_expiry: float
    spoilage_probability: float
    discount_pct: float


@dataclass(frozen=True)
class HoldInput:
    """Context for a hold decision."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    stockout_probability: float
    spoilage_probability: float
    hours_to_stockout: float
    hours_to_expiry: float


# ---------------------------------------------------------------------------
# Output containers
# ---------------------------------------------------------------------------

@dataclass
class ExplainabilityFacts:
    """Structured 5-part explainability container per spec §15, §17."""
    what_happened: str
    why_this_action: str
    why_not_alternatives: dict[str, str]
    expected_impact: dict[str, Any]
    reason_codes: list[str]


@dataclass
class CandidateAction:
    """A feasible action with its score and reason codes."""
    action_type: str
    score: float
    quantity: int
    source_store_id: Optional[uuid.UUID]
    destination_store_id: Optional[uuid.UUID]
    reason_codes: list[ReasonCode]
    metadata: dict


@dataclass
class DecisionResult:
    """Top recommendation and ranked alternatives (spec section 17)."""
    recommended: CandidateAction
    alternatives: list[CandidateAction]
    confidence: float
    explainability: Optional[ExplainabilityFacts] = None



# ---------------------------------------------------------------------------
# Safe Excess Calculator (spec section 15.1)
# ---------------------------------------------------------------------------

class SafeExcessCalculator:
    """Compute how many units a source store can safely transfer away."""

    def __init__(self, weights: ScoringWeights = DEFAULT_WEIGHTS) -> None:
        self._w = weights

    def compute(
        self,
        current_quantity: int,
        forecast_demand_24h: float,
        safety_stock: int = 0,
    ) -> int:
        """Return number of units safely transferable (>=0)."""
        hourly_demand = forecast_demand_24h / 24.0
        demand_during_window = hourly_demand * self._w.safety_window_hours
        buffer = demand_during_window * self._w.safety_buffer_fraction
        required = demand_during_window + buffer + safety_stock
        excess = current_quantity - required
        return max(0, int(excess))


# ---------------------------------------------------------------------------
# Transfer Validator -- hard constraints (spec section 15.3)
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    feasible: bool
    rejection_codes: list[ReasonCode]


class TransferValidator:
    """Applies hard reject rules before scoring any transfer."""

    def __init__(self, weights: ScoringWeights = DEFAULT_WEIGHTS) -> None:
        self._w = weights
        self._excess_calc = SafeExcessCalculator(weights)

    def validate(self, inp: TransferInput) -> ValidationResult:
        codes: list[ReasonCode] = []

        if inp.source_quantity < inp.transfer_quantity:
            codes.append(ReasonCode.WOULD_DEPLETE_SOURCE)

        available = self._excess_calc.compute(
            inp.source_quantity,
            inp.source_forecast_demand_24h,
            inp.source_safety_stock,
        )
        if inp.transfer_quantity > available:
            if ReasonCode.WOULD_DEPLETE_SOURCE not in codes:
                codes.append(ReasonCode.WOULD_DEPLETE_SOURCE)

        if inp.distance_km > self._w.max_transfer_distance_km:
            codes.append(ReasonCode.EXCEEDS_MAX_DISTANCE)

        travel_time_hours = inp.distance_km / self._w.transfer_speed_kmh
        if inp.destination_quantity > 0:
            # Only reject if stock still remains but transfer can't arrive before it runs out
            hourly_demand_dest = max(inp.destination_forecast_demand_24h / 24.0, 1e-9)
            destination_hours_of_stock = inp.destination_quantity / hourly_demand_dest
            if travel_time_hours > destination_hours_of_stock:
                codes.append(ReasonCode.CANNOT_ARRIVE_IN_TIME)
        # When dest_qty == 0, destination is already stocked out -- any transfer helps

        return ValidationResult(feasible=len(codes) == 0, rejection_codes=codes)


# ---------------------------------------------------------------------------
# Action Scorer (spec section 16)
# ---------------------------------------------------------------------------

class ActionScorer:
    """Scores each candidate action using spec section 16 weighted formula."""

    def __init__(self, weights: ScoringWeights = DEFAULT_WEIGHTS) -> None:
        self._w = weights

    def score_transfer(self, inp: TransferInput) -> float:
        w = self._w
        stockout_reduction = inp.destination_stockout_probability * w.stockout_risk_reduction
        spoilage_reduction = inp.destination_spoilage_probability * w.spoilage_reduction
        availability_gain  = inp.destination_stockout_probability * w.availability_improvement

        excess_calc = SafeExcessCalculator(w)
        available = excess_calc.compute(
            inp.source_quantity,
            inp.source_forecast_demand_24h,
            inp.source_safety_stock,
        )
        source_stress  = max(0.0, 1.0 - (available / max(inp.source_quantity, 1)))
        distance_cost  = (inp.distance_km / w.max_transfer_distance_km) * w.distance_penalty
        source_penalty = source_stress * w.source_risk_penalty

        return round(
            stockout_reduction + spoilage_reduction + availability_gain
            - distance_cost - source_penalty,
            6,
        )

    def score_reorder(self, inp: ReorderInput) -> float:
        w = self._w
        stockout_reduction = inp.stockout_probability * w.stockout_risk_reduction
        availability_gain  = inp.stockout_probability * w.availability_improvement
        delay_ratio   = max(0.0, min(1.0, inp.supplier_lead_time_hours / max(inp.hours_to_stockout, 1.0)))
        delay_penalty = delay_ratio * w.supplier_delay_penalty
        return round(stockout_reduction + availability_gain - delay_penalty, 6)

    def score_discount(self, inp: DiscountInput) -> float:
        w = self._w
        spoilage_reduction = inp.spoilage_probability * w.spoilage_reduction
        transfer_cost      = inp.discount_pct * w.transfer_cost_penalty
        return round(spoilage_reduction - transfer_cost, 6)

    def score_hold(self, inp: HoldInput) -> float:
        combined_risk = max(inp.stockout_probability, inp.spoilage_probability)
        return round(1.0 - combined_risk, 6)


# ---------------------------------------------------------------------------
# Pure Decision Evaluator (spec section 14)
# ---------------------------------------------------------------------------

class PureDecisionEvaluator:
    """Evaluates all candidate actions and returns the ranked recommendation."""

    def __init__(self, weights: ScoringWeights = DEFAULT_WEIGHTS) -> None:
        self._w      = weights
        self._scorer    = ActionScorer(weights)
        self._validator = TransferValidator(weights)
        self._excess    = SafeExcessCalculator(weights)

    def evaluate(
        self,
        transfers: list[TransferInput],
        reorders: list[ReorderInput],
        discounts: list[DiscountInput],
        hold: HoldInput,
    ) -> DecisionResult:
        candidates: list[CandidateAction] = []

        # Transfers
        for t in transfers:
            vr = self._validator.validate(t)
            if not vr.feasible:
                continue
            score     = self._scorer.score_transfer(t)
            available = self._excess.compute(
                t.source_quantity, t.source_forecast_demand_24h, t.source_safety_stock
            )
            codes: list[ReasonCode] = [
                ReasonCode.HIGH_STOCKOUT_RISK,
                ReasonCode.SOURCE_HAS_SAFE_EXCESS,
            ]
            if t.distance_km < (self._w.max_transfer_distance_km * 0.4):
                codes.append(ReasonCode.LOW_TRANSFER_DISTANCE)
            candidates.append(CandidateAction(
                action_type="transfer",
                score=score,
                quantity=t.transfer_quantity,
                source_store_id=t.source_store_id,
                destination_store_id=t.destination_store_id,
                reason_codes=codes,
                metadata={
                    "distance_km": t.distance_km,
                    "source_excess": available,
                    "destination_stockout_probability": t.destination_stockout_probability,
                },
            ))

        # Reorders
        for r in reorders:
            score = self._scorer.score_reorder(r)
            codes = [ReasonCode.HIGH_STOCKOUT_RISK]
            if r.supplier_lead_time_hours > r.hours_to_stockout:
                codes.append(ReasonCode.SUPPLIER_TOO_SLOW)
            if not transfers:
                codes.append(ReasonCode.NO_SAFE_TRANSFER_SOURCE)
            candidates.append(CandidateAction(
                action_type="reorder",
                score=score,
                quantity=r.reorder_quantity,
                source_store_id=None,
                destination_store_id=r.store_id,
                reason_codes=codes,
                metadata={
                    "supplier_lead_time_hours": r.supplier_lead_time_hours,
                    "hours_to_stockout": r.hours_to_stockout,
                    "stockout_probability": r.stockout_probability,
                },
            ))

        # Discounts
        for d in discounts:
            score = self._scorer.score_discount(d)
            codes = [ReasonCode.HIGH_SPOILAGE_RISK, ReasonCode.DISCOUNT_CAN_ACCELERATE]
            candidates.append(CandidateAction(
                action_type="discount",
                score=score,
                quantity=d.at_risk_quantity,
                source_store_id=d.store_id,
                destination_store_id=None,
                reason_codes=codes,
                metadata={
                    "hours_to_expiry": d.hours_to_expiry,
                    "at_risk_quantity": d.at_risk_quantity,
                    "discount_pct": d.discount_pct,
                    "spoilage_probability": d.spoilage_probability,
                },
            ))

        # Hold (always generated)
        hold_score = self._scorer.score_hold(hold)
        hold_codes = [ReasonCode.INVENTORY_HEALTHY, ReasonCode.STOCKOUT_RISK_LOW]
        if hold.hours_to_expiry > 24.0:
            hold_codes.append(ReasonCode.EXPIRY_DISTANT)
        candidates.append(CandidateAction(
            action_type="hold",
            score=hold_score,
            quantity=0,
            source_store_id=None,
            destination_store_id=None,
            reason_codes=hold_codes,
            metadata={
                "stockout_probability": hold.stockout_probability,
                "spoilage_probability": hold.spoilage_probability,
            },
        ))

        candidates.sort(key=lambda c: c.score, reverse=True)
        recommended  = candidates[0]
        alternatives = candidates[1:]

        if alternatives:
            gap        = recommended.score - alternatives[0].score
            confidence = round(min(1.0, 0.5 + gap), 4)
        else:
            confidence = 1.0

        # Build 5-part structured explainability per spec §15, §17
        if hold.stockout_probability >= 0.3:
            what_happened = (
                f"Projected demand depletes inventory in {hold.hours_to_stockout:.1f}h "
                f"(stockout probability {hold.stockout_probability:.0%})"
            )
        elif hold.spoilage_probability >= 0.25:
            what_happened = (
                f"Perishable inventory has batches expiring in {hold.hours_to_expiry:.1f}h "
                f"(spoilage probability {hold.spoilage_probability:.0%})"
            )
        else:
            what_happened = "Inventory levels and batch lifecycles are healthy within safety thresholds"

        if recommended.action_type == "transfer":
            dist = recommended.metadata.get("distance_km", 0.0)
            excess = recommended.metadata.get("source_excess", 0)
            why_this_action = (
                f"Transfer of {recommended.quantity} units from source store ({dist:.1f}km away). "
                f"Source has {excess} units safe excess and transfer arrives before projected stockout."
            )
        elif recommended.action_type == "reorder":
            lt = recommended.metadata.get("supplier_lead_time_hours", 24)
            why_this_action = (
                f"Wholesale reorder of {recommended.quantity} units initiates replenishment. "
                f"Supplier lead time is {lt}h with reliable fulfillment."
            )
        elif recommended.action_type == "discount":
            pct = recommended.metadata.get("discount_pct", 0.2)
            why_this_action = (
                f"Dynamic markdown of {pct:.0%} on {recommended.quantity} units accelerates sell-through "
                f"before expiry in {recommended.metadata.get('hours_to_expiry', 0):.1f}h."
            )
        else:
            why_this_action = "Holding status quo avoids unnecessary transport friction and procurement cost."

        why_not_alternatives: dict[str, str] = {}
        for alt in alternatives:
            if alt.action_type == "reorder":
                lt = alt.metadata.get("supplier_lead_time_hours", 24)
                hts = alt.metadata.get("hours_to_stockout", 0)
                if lt > hts:
                    why_not_alternatives["reorder"] = (
                        f"Supplier lead time ({lt}h) exceeds remaining stock window ({hts:.1f}h); "
                        "reorder would arrive too late to prevent stockout."
                    )
                else:
                    why_not_alternatives["reorder"] = (
                        f"Wholesale reorder lead time ({lt}h) is slower than intranet transfer."
                    )
            elif alt.action_type == "transfer":
                why_not_alternatives["transfer"] = (
                    "No alternative source store has sufficient safe excess or acceptable distance."
                )
            elif alt.action_type == "discount":
                why_not_alternatives["discount"] = (
                    "Stockout is the dominant risk; discounting would accelerate depletion."
                )
            elif alt.action_type == "hold":
                if hold.stockout_probability > 0.3:
                    why_not_alternatives["hold"] = (
                        f"Unaddressed stockout risk is {hold.stockout_probability:.0%}; inaction guarantees stockout."
                    )
                elif hold.spoilage_probability > 0.25:
                    why_not_alternatives["hold"] = (
                        f"Unaddressed spoilage risk is {hold.spoilage_probability:.0%}; inaction causes physical waste."
                    )
                else:
                    why_not_alternatives["hold"] = "Action yields a higher availability score than holding."

        expected_impact = {
            "stockout_risk_reduction": round(hold.stockout_probability if recommended.action_type in ("transfer", "reorder") else 0.0, 4),
            "spoilage_reduction": round(hold.spoilage_probability if recommended.action_type == "discount" else 0.0, 4),
            "availability_improvement": round(0.95 if recommended.action_type in ("transfer", "reorder") else 0.80, 4),
            "estimated_action_cost": round(
                recommended.metadata.get("distance_km", 5.0) * 15.0 if recommended.action_type == "transfer"
                else (recommended.quantity * 25.0 if recommended.action_type == "reorder" else 0.0),
                2,
            ),
        }

        explainability = ExplainabilityFacts(
            what_happened=what_happened,
            why_this_action=why_this_action,
            why_not_alternatives=why_not_alternatives,
            expected_impact=expected_impact,
            reason_codes=[r.value if hasattr(r, "value") else str(r) for r in recommended.reason_codes],
        )

        return DecisionResult(
            recommended=recommended,
            alternatives=alternatives,
            confidence=confidence,
            explainability=explainability,
        )

