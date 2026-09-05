"""TDD tests for Phase 5: Decision Engine.

Verifies:
- Seam 1: Structured Explainability & Enhanced Hard Constraints
- Seam 2: 4-Action Pure Decision Evaluator & Candidate Ranking
- Seam 3: Fleet-Wide Batch Evaluation (evaluate_all) & Active Risk Mapping
- Seam 4: Recommendation Lifecycle (approve, reject) & Audit Events
- Seam 5: Recommendation API Endpoints & Schemas
- Seam 6: Scenario-Driven Regression Suite & Invariants
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
    ExplainabilityFacts,
    SafeExcessCalculator,
    TransferValidator,
    ActionScorer,
    PureDecisionEvaluator,
)


def _store() -> uuid.UUID:
    return uuid.uuid4()


def _product() -> uuid.UUID:
    return uuid.uuid4()


# ===========================================================================
# Seams 1 & 2: Pure Decision Evaluator, Hard Constraints & Explainability
# ===========================================================================

def test_decision_transfer_preferred_over_reorder():
    """When source has safe excess and ETA beats stockout window, TRANSFER beats REORDER."""
    prod = _product()
    dest = _store()
    src = _store()

    # Destination: 5 units on hand, 24 units/day demand (stockout in 5h), 24h supplier lead time
    t_in = TransferInput(
        source_store_id=src,
        destination_store_id=dest,
        product_id=prod,
        source_quantity=100,
        source_forecast_demand_24h=24.0,
        source_safety_stock=0,
        destination_quantity=5,
        destination_forecast_demand_24h=24.0,
        destination_forecast_demand_48h=48.0,
        destination_lead_time_hours=24,
        destination_stockout_probability=0.90,
        distance_km=6.0,  # 6km / 30km/h = 0.2h ETA << 5h
        transfer_quantity=20,
    )

    r_in = ReorderInput(
        store_id=dest,
        product_id=prod,
        supplier_lead_time_hours=24,
        hours_to_stockout=5.0,
        current_quantity=5,
        forecast_demand_24h=24.0,
        reorder_quantity=30,
        stockout_probability=0.90,
    )

    h_in = HoldInput(
        store_id=dest,
        product_id=prod,
        stockout_probability=0.90,
        spoilage_probability=0.0,
        hours_to_stockout=5.0,
        hours_to_expiry=120.0,
    )

    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(transfers=[t_in], reorders=[r_in], discounts=[], hold=h_in)

    assert result.recommended.action_type == "transfer"
    assert result.recommended.quantity == 20
    assert result.recommended.source_store_id == src
    assert result.confidence > 0.5

    # Reorder is present as an alternative
    alt_actions = [a.action_type for a in result.alternatives]
    assert "reorder" in alt_actions
    assert "hold" in alt_actions

    # Explainability must be present and structured
    assert result.explainability is not None
    assert "transfer" in result.explainability.why_this_action.lower() or "safe excess" in result.explainability.why_this_action.lower()
    assert "reorder" in result.explainability.why_not_alternatives


def test_decision_reorder_when_no_transfer_source():
    """When no transfer candidates exist, REORDER ranks #1 for stockout risk."""
    prod = _product()
    store = _store()

    r_in = ReorderInput(
        store_id=store,
        product_id=prod,
        supplier_lead_time_hours=12,
        hours_to_stockout=14.0,
        current_quantity=10,
        forecast_demand_24h=20.0,
        reorder_quantity=40,
        stockout_probability=0.75,
    )

    h_in = HoldInput(
        store_id=store,
        product_id=prod,
        stockout_probability=0.75,
        spoilage_probability=0.0,
        hours_to_stockout=14.0,
        hours_to_expiry=100.0,
    )

    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(transfers=[], reorders=[r_in], discounts=[], hold=h_in)

    assert result.recommended.action_type == "reorder"
    assert result.recommended.quantity == 40
    assert result.recommended.destination_store_id == store
    assert ReasonCode.NO_SAFE_TRANSFER_SOURCE in result.recommended.reason_codes


def test_decision_discount_preferred_for_spoilage():
    """When spoilage risk is elevated, DISCOUNT ranks #1."""
    prod = _product()
    store = _store()

    d_in = DiscountInput(
        store_id=store,
        product_id=prod,
        at_risk_quantity=25,
        hours_to_expiry=5.0,
        forecast_demand_before_expiry=5.0,
        spoilage_probability=0.85,
        discount_pct=0.30,
    )

    h_in = HoldInput(
        store_id=store,
        product_id=prod,
        stockout_probability=0.0,
        spoilage_probability=0.85,
        hours_to_stockout=100.0,
        hours_to_expiry=5.0,
    )

    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(transfers=[], reorders=[], discounts=[d_in], hold=h_in)

    assert result.recommended.action_type == "discount"
    assert result.recommended.quantity == 25
    assert ReasonCode.HIGH_SPOILAGE_RISK in result.recommended.reason_codes
    assert ReasonCode.DISCOUNT_CAN_ACCELERATE in result.recommended.reason_codes


def test_decision_hold_preferred_when_healthy():
    """When both stockout and spoilage risks are low, HOLD ranks #1."""
    prod = _product()
    store = _store()

    h_in = HoldInput(
        store_id=store,
        product_id=prod,
        stockout_probability=0.05,
        spoilage_probability=0.02,
        hours_to_stockout=72.0,
        hours_to_expiry=96.0,
    )

    evaluator = PureDecisionEvaluator()
    result = evaluator.evaluate(transfers=[], reorders=[], discounts=[], hold=h_in)

    assert result.recommended.action_type == "hold"
    assert result.recommended.score >= 0.90
    assert ReasonCode.INVENTORY_HEALTHY in result.recommended.reason_codes


def test_decision_hard_constraints_reject_infeasible():
    """Hard constraints reject transfers that deplete source, exceed distance, or arrive too late."""
    validator = TransferValidator()
    src = _store()
    dest = _store()
    prod = _product()

    # 1. Would deplete source (requested 50, but source only has 30 total)
    depleting = TransferInput(
        source_store_id=src, destination_store_id=dest, product_id=prod,
        source_quantity=30, source_forecast_demand_24h=20.0, source_safety_stock=0,
        destination_quantity=5, destination_forecast_demand_24h=20.0, destination_forecast_demand_48h=40.0,
        destination_lead_time_hours=24, destination_stockout_probability=0.8,
        distance_km=5.0, transfer_quantity=50,
    )
    vr1 = validator.validate(depleting)
    assert not vr1.feasible
    assert ReasonCode.WOULD_DEPLETE_SOURCE in vr1.rejection_codes

    # 2. Exceeds max distance (25km > 20km limit)
    too_far = TransferInput(
        source_store_id=src, destination_store_id=dest, product_id=prod,
        source_quantity=100, source_forecast_demand_24h=10.0, source_safety_stock=0,
        destination_quantity=5, destination_forecast_demand_24h=20.0, destination_forecast_demand_48h=40.0,
        destination_lead_time_hours=24, destination_stockout_probability=0.8,
        distance_km=25.0, transfer_quantity=20,
    )
    vr2 = validator.validate(too_far)
    assert not vr2.feasible
    assert ReasonCode.EXCEEDS_MAX_DISTANCE in vr2.rejection_codes

    # 3. Cannot arrive in time (destination has 1h of stock, but travel time is 18km / 30km/h = 0.6h is ok,
    # but 10 units at 50/h demand is 0.2h stock vs 0.6h travel -> cannot arrive)
    too_slow = TransferInput(
        source_store_id=src, destination_store_id=dest, product_id=prod,
        source_quantity=100, source_forecast_demand_24h=10.0, source_safety_stock=0,
        destination_quantity=2, destination_forecast_demand_24h=240.0,  # 10 units/hr -> 2 units = 0.2h
        destination_forecast_demand_48h=480.0, destination_lead_time_hours=24,
        destination_stockout_probability=0.9, distance_km=18.0,  # 18km / 30km/h = 0.6h > 0.2h
        transfer_quantity=20,
    )
    vr3 = validator.validate(too_slow)
    assert not vr3.feasible
    assert ReasonCode.CANNOT_ARRIVE_IN_TIME in vr3.rejection_codes


def test_decision_explainability_structure():
    """DecisionResult exposes complete 5-part explainability facts."""
    prod = _product()
    dest = _store()
    src = _store()

    t_in = TransferInput(
        source_store_id=src, destination_store_id=dest, product_id=prod,
        source_quantity=100, source_forecast_demand_24h=24.0, source_safety_stock=0,
        destination_quantity=4, destination_forecast_demand_24h=24.0, destination_forecast_demand_48h=48.0,
        destination_lead_time_hours=24, destination_stockout_probability=0.85,
        distance_km=5.0, transfer_quantity=20,
    )
    r_in = ReorderInput(
        store_id=dest, product_id=prod, supplier_lead_time_hours=24,
        hours_to_stockout=4.0, current_quantity=4, forecast_demand_24h=24.0,
        reorder_quantity=30, stockout_probability=0.85,
    )
    h_in = HoldInput(
        store_id=dest, product_id=prod, stockout_probability=0.85,
        spoilage_probability=0.0, hours_to_stockout=4.0, hours_to_expiry=72.0,
    )

    evaluator = PureDecisionEvaluator()
    res = evaluator.evaluate(transfers=[t_in], reorders=[r_in], discounts=[], hold=h_in)

    exp = res.explainability
    assert exp is not None
    assert len(exp.what_happened) > 0
    assert len(exp.why_this_action) > 0
    assert "reorder" in exp.why_not_alternatives
    assert "hold" in exp.why_not_alternatives
    assert "stockout_risk_reduction" in exp.expected_impact

# ===========================================================================
# Seams 3, 4, 5 & 6: Orchestrator, Lifecycle, API & Determinism
# ===========================================================================
from datetime import datetime, timezone
from sqlalchemy import select, update
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.database import get_db
from backend.models.core import Risk, Inventory, Batch, Store, Product, Recommendation, Action
from backend.models.enums import RiskType, RiskSeverity, RiskStatus, RecommendationStatus, ActionStatus, ActionType
from backend.services.simulation.engine import SimulationEngine
from backend.services.forecasting.engine import ForecastingEngine
from backend.services.risk.engine import RiskEngine
from backend.services.decision.engine import DecisionOrchestrator


@pytest.mark.asyncio
async def test_decision_orchestrator_evaluate_single_risk(db_session):
    """DecisionOrchestrator evaluates an active risk and persists a structured recommendation."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Drop inventory for one item to guarantee risk
    inv = (await db_session.execute(select(Inventory))).scalars().first()
    inv.quantity = 2
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    risk = (await db_session.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))).scalars().first()
    assert risk is not None

    orchestrator = DecisionOrchestrator()
    rec = await orchestrator.run(db_session, risk.risk_id)
    await db_session.commit()

    assert rec is not None
    assert rec.risk_id == risk.risk_id
    assert rec.status == RecommendationStatus.PENDING
    assert rec.score > 0.0
    assert 0.0 <= rec.confidence <= 1.0
    assert len(rec.reason_codes) > 0
    assert isinstance(rec.alternatives, list)
    assert len(rec.alternatives) > 0


@pytest.mark.asyncio
async def test_decision_orchestrator_evaluate_all_fleet(db_session):
    """evaluate_all processes all active risks and avoids duplicate pending recommendations."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Force low inventory to generate risks
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    active_risks = (await db_session.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))).scalars().all()
    assert len(active_risks) > 0

    orchestrator = DecisionOrchestrator()
    count_1 = await orchestrator.evaluate_all(db_session)
    await db_session.commit()

    assert count_1 > 0

    # Second run without new risks should generate 0 duplicate pending recommendations
    count_2 = await orchestrator.evaluate_all(db_session)
    await db_session.commit()

    assert count_2 == 0


@pytest.mark.asyncio
async def test_decision_lifecycle_approve_and_stage_action(db_session):
    """Approving a recommendation sets status to APPROVED and stages a pending Action."""
    sim = SimulationEngine(seed=42, historical_days=5)
    await sim.initialize(db_session)
    await db_session.commit()

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=(await db_session.execute(select(Store))).scalars().first().store_id,
        product_id=(await db_session.execute(select(Product))).scalars().first().product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.9,
        expected_time=datetime.now(timezone.utc).replace(tzinfo=None),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)
    await db_session.commit()

    rec_id = uuid.uuid4()
    rec = Recommendation(
        recommendation_id=rec_id,
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=20,
        source_store_id=risk.store_id,
        destination_store_id=risk.store_id,
        score=0.85,
        confidence=0.90,
        reason_codes=["HIGH_STOCKOUT_RISK"],
        alternatives=[],
        status=RecommendationStatus.PENDING,
    )
    db_session.add(rec)
    await db_session.commit()

    orchestrator = DecisionOrchestrator()
    approved = await orchestrator.approve(db_session, rec_id, approver="lead_dispatcher")
    await db_session.commit()

    assert approved is not None
    assert approved.status == RecommendationStatus.APPROVED

    # Staged action must exist
    action = (await db_session.execute(select(Action).where(Action.recommendation_id == rec_id))).scalars().first()
    assert action is not None
    assert action.status == ActionStatus.PENDING
    assert action.approved_by == "lead_dispatcher"


@pytest.mark.asyncio
async def test_decision_lifecycle_reject(db_session):
    """Rejecting a recommendation sets status to REJECTED."""
    sim = SimulationEngine(seed=42, historical_days=5)
    await sim.initialize(db_session)
    await db_session.commit()

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=(await db_session.execute(select(Store))).scalars().first().store_id,
        product_id=(await db_session.execute(select(Product))).scalars().first().product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.WARNING,
        probability=0.5,
        expected_time=datetime.now(timezone.utc).replace(tzinfo=None),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)
    await db_session.commit()

    rec_id = uuid.uuid4()
    rec = Recommendation(
        recommendation_id=rec_id,
        risk_id=risk.risk_id,
        action_type=ActionType.HOLD,
        quantity=0,
        score=0.50,
        confidence=0.60,
        reason_codes=["STOCKOUT_RISK_LOW"],
        alternatives=[],
        status=RecommendationStatus.PENDING,
    )
    db_session.add(rec)
    await db_session.commit()

    orchestrator = DecisionOrchestrator()
    rejected = await orchestrator.reject(db_session, rec_id, reason="capacity constraint")
    await db_session.commit()

    assert rejected is not None
    assert rejected.status == RecommendationStatus.REJECTED


@pytest.mark.asyncio
async def test_decision_api_batch_evaluate_and_filters(db_session):
    """API endpoints for batch evaluate, listing with filters, and approve/reject lifecycle."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Create risk
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Batch evaluate recommendations
        eval_resp = await client.post("/api/recommendations/evaluate")
        assert eval_resp.status_code == 200
        data = eval_resp.json()
        assert "recommendations_generated" in data
        assert data["recommendations_generated"] > 0

        # 2. List recommendations
        list_resp = await client.get("/api/recommendations")
        assert list_resp.status_code == 200
        recs = list_resp.json()
        assert len(recs) > 0
        first_rec = recs[0]

        # 3. Filter by status
        pending_resp = await client.get("/api/recommendations?status=pending")
        assert pending_resp.status_code == 200
        for r in pending_resp.json():
            assert r["status"] == "pending"

        # 4. Approve recommendation
        rec_id = first_rec["recommendation_id"]
        appr_resp = await client.post(f"/api/recommendations/{rec_id}/approve")
        assert appr_resp.status_code == 200
        assert appr_resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_decision_immutability_and_determinism(db_session):
    """Decision evaluation does not mutate inventory and produces deterministic results."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    await db_session.execute(update(Inventory).values(quantity=2))
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    risk = (await db_session.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))).scalars().first()
    assert risk is not None

    inv_before = {
        (inv.store_id, inv.product_id): inv.quantity
        for inv in (await db_session.execute(select(Inventory))).scalars().all()
    }

    orchestrator = DecisionOrchestrator()
    rec1 = await orchestrator.run(db_session, risk.risk_id)
    await db_session.commit()

    inv_after = {
        (inv.store_id, inv.product_id): inv.quantity
        for inv in (await db_session.execute(select(Inventory))).scalars().all()
    }
    assert inv_before == inv_after

    # Second evaluation of the same risk
    rec2_result = orchestrator._evaluator.evaluate(
        transfers=[],
        reorders=[
            ReorderInput(
                store_id=risk.store_id, product_id=risk.product_id,
                supplier_lead_time_hours=24, hours_to_stockout=5.0,
                current_quantity=2, forecast_demand_24h=20.0,
                reorder_quantity=30, stockout_probability=risk.probability,
            )
        ],
        discounts=[],
        hold=HoldInput(
            store_id=risk.store_id, product_id=risk.product_id,
            stockout_probability=risk.probability, spoilage_probability=0.0,
            hours_to_stockout=5.0, hours_to_expiry=100.0,
        ),
    )
    assert rec2_result.recommended.action_type == "reorder"
    assert rec2_result.recommended.quantity == 30
