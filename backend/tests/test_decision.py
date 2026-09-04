"""TDD tests for the Decision Engine pure models (spec sections 14-17, Phase 5).

Test seams in red->green order:

Unit seams (pure math, no DB):
1.  ReasonCode enum -- all spec section 17 codes present
2.  ScoringWeights -- defaults are configurable dataclass
3.  SafeExcessCalculator.compute() -- spec section 15.1 safe excess formula
4.  TransferValidator.validate() -- feasible when constraints pass
5.  TransferValidator.validate() -- WOULD_DEPLETE_SOURCE when excess insufficient
6.  TransferValidator.validate() -- EXCEEDS_MAX_DISTANCE when too far
7.  TransferValidator.validate() -- CANNOT_ARRIVE_IN_TIME when travel > stock hours
8.  ActionScorer.score_transfer() -- higher for closer source, high dest risk
9.  ActionScorer.score_reorder() -- penalised when supplier slower than stockout
10. ActionScorer.score_discount() -- scales with spoilage probability
11. ActionScorer.score_hold() -- 1.0 - combined_risk
12. PureDecisionEvaluator.evaluate() -- transfer wins when feasible + high dest risk
13. PureDecisionEvaluator.evaluate() -- hold wins when all risks low
14. PureDecisionEvaluator.evaluate() -- infeasible transfer excluded; reorder wins
15. PureDecisionEvaluator.evaluate() -- discount ranks for spoilage scenario
16. PureDecisionEvaluator.evaluate() -- alternatives exclude recommended action
17. PureDecisionEvaluator.evaluate() -- confidence >= 0 and <= 1
"""
from __future__ import annotations

import uuid
import pytest

from backend.services.decision.models import (
    ReasonCode,
    ScoringWeights,
    DEFAULT_WEIGHTS,
    TransferInput,
    ReorderInput,
    DiscountInput,
    HoldInput,
    CandidateAction,
    DecisionResult,
    SafeExcessCalculator,
    ValidationResult,
    TransferValidator,
    ActionScorer,
    PureDecisionEvaluator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store() -> uuid.UUID:
    return uuid.uuid4()

def _product() -> uuid.UUID:
    return uuid.uuid4()

def _transfer(
    src_qty: int = 100,
    src_demand: float = 20.0,
    dest_qty: int = 5,
    dest_demand: float = 30.0,
    dest_risk: float = 0.85,
    distance_km: float = 3.0,
    transfer_qty: int = 20,
) -> TransferInput:
    return TransferInput(
        source_store_id=_store(),
        destination_store_id=_store(),
        product_id=_product(),
        source_quantity=src_qty,
        source_forecast_demand_24h=src_demand,
        source_safety_stock=0,
        destination_quantity=dest_qty,
        destination_forecast_demand_24h=dest_demand,
        destination_forecast_demand_48h=dest_demand * 2,
        destination_lead_time_hours=24,
        destination_stockout_probability=dest_risk,
        distance_km=distance_km,
        transfer_quantity=transfer_qty,
    )

def _reorder(
    stockout_prob: float = 0.8,
    lead_time: int = 24,
    hours_to_stockout: float = 12.0,
) -> ReorderInput:
    return ReorderInput(
        store_id=_store(),
        product_id=_product(),
        supplier_lead_time_hours=lead_time,
        hours_to_stockout=hours_to_stockout,
        current_quantity=10,
        forecast_demand_24h=20.0,
        reorder_quantity=40,
        stockout_probability=stockout_prob,
    )

def _discount(spoilage_prob: float = 0.7, discount_pct: float = 0.20) -> DiscountInput:
    return DiscountInput(
        store_id=_store(),
        product_id=_product(),
        at_risk_quantity=50,
        hours_to_expiry=8.0,
        forecast_demand_before_expiry=20.0,
        spoilage_probability=spoilage_prob,
        discount_pct=discount_pct,
    )

def _hold(stockout_prob: float = 0.05, spoilage_prob: float = 0.05) -> HoldInput:
    return HoldInput(
        store_id=_store(),
        product_id=_product(),
        stockout_probability=stockout_prob,
        spoilage_probability=spoilage_prob,
        hours_to_stockout=72.0,
        hours_to_expiry=48.0,
    )


# ---------------------------------------------------------------------------
# 1. ReasonCode enum
# ---------------------------------------------------------------------------

def test_reason_codes_have_all_spec_values():
    """All reason codes from spec section 17 must be present."""
    expected = {
        "HIGH_STOCKOUT_RISK",
        "SOURCE_HAS_SAFE_EXCESS",
        "SUPPLIER_TOO_SLOW",
        "LOW_TRANSFER_DISTANCE",
        "HIGH_SPOILAGE_RISK",
        "DISCOUNT_CAN_ACCELERATE",
        "NO_SAFE_TRANSFER_SOURCE",
        "INVENTORY_HEALTHY",
        "EXPIRY_DISTANT",
        "STOCKOUT_RISK_LOW",
        "WOULD_DEPLETE_SOURCE",
        "EXCEEDS_MAX_DISTANCE",
        "CANNOT_ARRIVE_IN_TIME",
    }
    actual = {c.value for c in ReasonCode}
    assert expected.issubset(actual)


# ---------------------------------------------------------------------------
# 2. ScoringWeights
# ---------------------------------------------------------------------------

def test_scoring_weights_defaults_are_sane():
    w = DEFAULT_WEIGHTS
    assert 0 < w.stockout_risk_reduction <= 1
    assert 0 < w.spoilage_reduction <= 1
    assert w.max_transfer_distance_km > 0
    assert w.safety_window_hours > 0

def test_scoring_weights_are_overridable():
    custom = ScoringWeights(stockout_risk_reduction=0.50, spoilage_reduction=0.10)
    assert custom.stockout_risk_reduction == 0.50
    # immutable -- should not accept assignment
    with pytest.raises(Exception):
        custom.stockout_risk_reduction = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. SafeExcessCalculator
# ---------------------------------------------------------------------------

def test_safe_excess_returns_zero_when_inventory_is_tight():
    calc = SafeExcessCalculator()
    # 24h demand = 24 units. Safety window 24h + 15% buffer = 27.6 => excess = 0
    result = calc.compute(current_quantity=25, forecast_demand_24h=24.0)
    assert result == 0

def test_safe_excess_returns_positive_when_inventory_plentiful():
    calc = SafeExcessCalculator()
    # 24h demand = 10, window = 24h, buffer = 15% => required ~11.5 => excess from 100 = ~88
    result = calc.compute(current_quantity=100, forecast_demand_24h=10.0)
    assert result > 50

def test_safe_excess_respects_safety_stock():
    calc = SafeExcessCalculator()
    baseline = calc.compute(current_quantity=100, forecast_demand_24h=10.0)
    with_safety = calc.compute(current_quantity=100, forecast_demand_24h=10.0, safety_stock=20)
    assert with_safety < baseline

def test_safe_excess_never_negative():
    calc = SafeExcessCalculator()
    result = calc.compute(current_quantity=0, forecast_demand_24h=50.0)
    assert result == 0


# ---------------------------------------------------------------------------
# 4-7. TransferValidator
# ---------------------------------------------------------------------------

def test_transfer_validator_feasible_when_all_constraints_pass():
    """Good transfer: source has excess, short distance, dest needs it now."""
    validator = TransferValidator()
    t = _transfer(src_qty=200, src_demand=10.0, dest_qty=0, dest_demand=20.0, distance_km=2.0, transfer_qty=30)
    vr = validator.validate(t)
    assert vr.feasible is True
    assert vr.rejection_codes == []

def test_transfer_validator_rejects_when_depletes_source():
    """Transfer qty exceeds safe excess."""
    validator = TransferValidator()
    # source has 10 units, demand=20/day => excess = 0; trying to transfer 5
    t = _transfer(src_qty=10, src_demand=20.0, transfer_qty=5)
    vr = validator.validate(t)
    assert vr.feasible is False
    assert ReasonCode.WOULD_DEPLETE_SOURCE in vr.rejection_codes

def test_transfer_validator_rejects_excessive_distance():
    validator = TransferValidator()
    t = _transfer(distance_km=25.0)  # default max is 20km
    vr = validator.validate(t)
    assert vr.feasible is False
    assert ReasonCode.EXCEEDS_MAX_DISTANCE in vr.rejection_codes

def test_transfer_validator_rejects_when_cannot_arrive_in_time():
    """Travel time > destination hours of stock."""
    validator = TransferValidator()
    # dest has 1 unit, demand 24/day = 1/h => 1 hour of stock
    # distance 15km at 30kmh => 0.5h travel -- should pass
    # make it worse: dest has 1 unit, demand 60/day = 2.5/h => 0.4h of stock, travel 15km=0.5h
    t = _transfer(
        src_qty=200,
        src_demand=5.0,
        dest_qty=1,
        dest_demand=60.0,
        distance_km=15.0,
        transfer_qty=10,
    )
    vr = validator.validate(t)
    assert vr.feasible is False
    assert ReasonCode.CANNOT_ARRIVE_IN_TIME in vr.rejection_codes


# ---------------------------------------------------------------------------
# 8-11. ActionScorer
# ---------------------------------------------------------------------------

def test_scorer_transfer_higher_for_higher_dest_risk():
    scorer = ActionScorer()
    low_risk  = _transfer(dest_risk=0.10)
    high_risk = _transfer(dest_risk=0.90)
    assert scorer.score_transfer(high_risk) > scorer.score_transfer(low_risk)

def test_scorer_transfer_penalises_distance():
    scorer = ActionScorer()
    close  = _transfer(distance_km=1.0)
    far    = _transfer(distance_km=19.0)
    assert scorer.score_transfer(close) > scorer.score_transfer(far)

def test_scorer_reorder_penalised_when_supplier_slower_than_stockout():
    scorer = ActionScorer()
    fast_stockout = _reorder(lead_time=48, hours_to_stockout=6.0)
    slow_stockout = _reorder(lead_time=6,  hours_to_stockout=48.0)
    # fast_stockout: delay_ratio = 48/6 = capped at 1 => max penalty
    # slow_stockout: delay_ratio = 6/48 = 0.125 => small penalty
    assert scorer.score_reorder(slow_stockout) > scorer.score_reorder(fast_stockout)

def test_scorer_discount_scales_with_spoilage_probability():
    scorer = ActionScorer()
    low_risk  = _discount(spoilage_prob=0.10)
    high_risk = _discount(spoilage_prob=0.90)
    assert scorer.score_discount(high_risk) > scorer.score_discount(low_risk)

def test_scorer_hold_is_one_minus_combined_risk():
    scorer = ActionScorer()
    h = _hold(stockout_prob=0.2, spoilage_prob=0.3)
    expected = round(1.0 - 0.3, 6)
    assert scorer.score_hold(h) == pytest.approx(expected, abs=1e-5)


# ---------------------------------------------------------------------------
# 12-17. PureDecisionEvaluator
# ---------------------------------------------------------------------------

def test_evaluator_transfer_wins_when_feasible_and_dest_high_risk():
    evaluator = PureDecisionEvaluator()
    t = _transfer(src_qty=200, src_demand=10.0, dest_qty=0, dest_demand=20.0, dest_risk=0.95, distance_km=2.0, transfer_qty=30)
    result = evaluator.evaluate(
        transfers=[t],
        reorders=[_reorder(stockout_prob=0.95, lead_time=48, hours_to_stockout=2.0)],
        discounts=[],
        hold=_hold(stockout_prob=0.95, spoilage_prob=0.0),
    )
    assert result.recommended.action_type == "transfer"

def test_evaluator_hold_wins_when_risks_are_low():
    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(
        transfers=[],
        reorders=[_reorder(stockout_prob=0.05, lead_time=12, hours_to_stockout=72.0)],
        discounts=[],
        hold=_hold(stockout_prob=0.05, spoilage_prob=0.02),
    )
    # Low risk = hold score ~0.95, reorder score low
    assert result.recommended.action_type == "hold"

def test_evaluator_excludes_infeasible_transfer():
    """Infeasible transfer must not appear in recommended or alternatives."""
    evaluator = PureDecisionEvaluator()
    # infeasible: src_qty too low
    bad_transfer = _transfer(src_qty=5, src_demand=20.0, transfer_qty=10)
    result = evaluator.evaluate(
        transfers=[bad_transfer],
        reorders=[_reorder(stockout_prob=0.8)],
        discounts=[],
        hold=_hold(stockout_prob=0.8),
    )
    all_types = [result.recommended.action_type] + [a.action_type for a in result.alternatives]
    assert "transfer" not in all_types

def test_evaluator_discount_in_alternatives_for_spoilage_scenario():
    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(
        transfers=[],
        reorders=[_reorder(stockout_prob=0.1)],
        discounts=[_discount(spoilage_prob=0.85, discount_pct=0.20)],
        hold=_hold(stockout_prob=0.1, spoilage_prob=0.85),
    )
    all_types = [result.recommended.action_type] + [a.action_type for a in result.alternatives]
    assert "discount" in all_types

def test_evaluator_alternatives_do_not_include_recommended():
    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(
        transfers=[_transfer(src_qty=200, src_demand=10.0, dest_qty=0, dest_demand=20.0, dest_risk=0.9, distance_km=2.0, transfer_qty=30)],
        reorders=[_reorder()],
        discounts=[_discount()],
        hold=_hold(),
    )
    rec_type = result.recommended.action_type
    for alt in result.alternatives:
        # action_type alone is not unique (there could be multiple transfers)
        # but the recommended object must not be literally the same object
        assert alt is not result.recommended

def test_evaluator_confidence_is_bounded():
    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(
        transfers=[_transfer()],
        reorders=[_reorder()],
        discounts=[_discount()],
        hold=_hold(),
    )
    assert 0.0 <= result.confidence <= 1.0
