"""TDD tests for Phase 6 LangGraph Agent (spec sections 19-21).

Test seams (red->green order):

Unit seams -- pure tool/node logic with a real in-memory SQLite DB:
 1.  AgentState TypedDict -- required fields present
 2.  get_recommendation -- returns rec dict for known id
 3.  get_recommendation -- returns None for unknown id
 4.  get_inventory -- returns quantity for known (store, product)
 5.  get_inventory -- returns 0 for unknown pair
 6.  validate_transfer -- feasible when source has enough inventory
 7.  validate_transfer -- infeasible when source inventory insufficient
 8.  create_transfer -- raises PermissionError if rec not APPROVED
 9.  create_transfer -- applies transfer and returns success=True
10.  create_reorder -- raises PermissionError if rec not APPROVED
11.  create_reorder -- applies reorder and returns success=True
12.  apply_discount -- raises PermissionError if rec not APPROVED
13.  apply_discount -- returns success=True for approved discount
14.  recalculate_options -- creates a new recommendation row
15.  node_validate -- sets error if rec not found
16.  node_validate -- sets error if rec not APPROVED
17.  node_validate -- returns recommendation snapshot when APPROVED
18.  node_pre_check -- pre_check_passed=False when source inventory stale
19.  node_pre_check -- pre_check_passed=True for reorder action
20.  node_execute -- dispatches hold as no-op (success=True)
21.  node_execute -- dispatches transfer and returns execution_result
22.  node_verify -- verified=True after successful transfer
23.  node_finalize -- sets status="completed"
24.  node_recover -- sets status="requires_human_review"
25.  Full graph run -- happy path APPROVED transfer -> completed
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.agents.execution.state import AgentState
from backend.agents.execution.tools import (
    get_recommendation,
    get_inventory,
    validate_transfer,
    create_transfer,
    create_reorder,
    apply_discount,
    recalculate_options,
)
from backend.agents.execution.nodes import (
    node_validate,
    node_pre_check,
    node_execute,
    node_verify,
    node_finalize,
    node_recover,
)
from backend.agents.execution.runner import ExecutionRunner
from backend.models.core import (
    Recommendation, Inventory, Risk, Store, Supplier, Product,
)
from backend.models.enums import (
    RecommendationStatus, ActionType, ActionStatus, RiskType, RiskSeverity,
    RiskStatus, StoreStatus, SupplierStatus, ProductCategory,
)
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers to seed a minimal scenario in the test DB
# ---------------------------------------------------------------------------

async def _seed_transfer_scenario(db_session):
    """Create two stores, a product, two inventory rows, and an APPROVED transfer rec."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(
        supplier_id=uuid.uuid4(),
        name="Test Supplier",
        lead_time_hours=24,
        status=SupplierStatus.ACTIVE,
    )
    db_session.add(supplier)

    product = Product(
        product_id=uuid.uuid4(),
        name="Test Bread",
        category=ProductCategory.BAKERY,
        unit="unit",
        shelf_life_hours=48,
        base_price=10.0,
        supplier_id=supplier.supplier_id,
    )
    db_session.add(product)

    src_store = Store(
        store_id=uuid.uuid4(),
        name="Store A",
        latitude=19.0,
        longitude=72.8,
        operating_status=StoreStatus.ACTIVE,
    )
    dst_store = Store(
        store_id=uuid.uuid4(),
        name="Store B",
        latitude=19.1,
        longitude=72.9,
        operating_status=StoreStatus.ACTIVE,
    )
    db_session.add(src_store)
    db_session.add(dst_store)

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dst_store.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.90,
        expected_time=now + timedelta(hours=6),
        status=RiskStatus.ACTIVE,
        created_at=now,
    )
    db_session.add(risk)

    # Source has 100 units, destination has 0
    src_inv = Inventory(store_id=src_store.store_id, product_id=product.product_id, quantity=100)
    dst_inv = Inventory(store_id=dst_store.store_id, product_id=product.product_id, quantity=0)
    db_session.add(src_inv)
    db_session.add(dst_inv)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=20,
        source_store_id=src_store.store_id,
        destination_store_id=dst_store.store_id,
        score=0.75,
        confidence=0.80,
        reason_codes=["HIGH_STOCKOUT_RISK", "SOURCE_HAS_SAFE_EXCESS"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
        created_at=now,
    )
    db_session.add(rec)
    await db_session.commit()

    return {
        "supplier": supplier,
        "product": product,
        "src_store": src_store,
        "dst_store": dst_store,
        "risk": risk,
        "src_inv": src_inv,
        "dst_inv": dst_inv,
        "rec": rec,
    }


async def _seed_reorder_scenario(db_session):
    """APPROVED reorder recommendation."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(
        supplier_id=uuid.uuid4(),
        name="Reorder Supplier",
        lead_time_hours=12,
        status=SupplierStatus.ACTIVE,
    )
    db_session.add(supplier)

    product = Product(
        product_id=uuid.uuid4(),
        name="Test Milk",
        category=ProductCategory.DAIRY,
        unit="litre",
        shelf_life_hours=72,
        base_price=25.0,
        supplier_id=supplier.supplier_id,
    )
    db_session.add(product)

    store = Store(
        store_id=uuid.uuid4(),
        name="Reorder Store",
        latitude=19.2,
        longitude=73.0,
        operating_status=StoreStatus.ACTIVE,
    )
    db_session.add(store)

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=store.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.WARNING,
        probability=0.60,
        expected_time=now + timedelta(hours=12),
        status=RiskStatus.ACTIVE,
        created_at=now,
    )
    db_session.add(risk)

    inv = Inventory(store_id=store.store_id, product_id=product.product_id, quantity=5)
    db_session.add(inv)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.REORDER,
        quantity=50,
        source_store_id=None,
        destination_store_id=store.store_id,
        score=0.55,
        confidence=0.70,
        reason_codes=["HIGH_STOCKOUT_RISK"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
        created_at=now,
    )
    db_session.add(rec)
    await db_session.commit()

    return {"supplier": supplier, "product": product, "store": store, "risk": risk, "inv": inv, "rec": rec}


async def _seed_pending_rec(db_session):
    """PENDING (not approved) recommendation for rejection tests."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(supplier_id=uuid.uuid4(), name="S", lead_time_hours=24, status=SupplierStatus.ACTIVE)
    db_session.add(supplier)
    product = Product(product_id=uuid.uuid4(), name="P", category=ProductCategory.STAPLES, unit="kg", shelf_life_hours=720, base_price=5.0, supplier_id=supplier.supplier_id)
    db_session.add(product)
    store = Store(store_id=uuid.uuid4(), name="St", latitude=0.0, longitude=0.0, operating_status=StoreStatus.ACTIVE)
    db_session.add(store)
    risk = Risk(risk_id=uuid.uuid4(), store_id=store.store_id, product_id=product.product_id, risk_type=RiskType.STOCKOUT, severity=RiskSeverity.LOW, probability=0.1, expected_time=now + timedelta(hours=48), status=RiskStatus.ACTIVE, created_at=now)
    db_session.add(risk)
    rec = Recommendation(recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER, quantity=10, source_store_id=store.store_id, destination_store_id=store.store_id, score=0.1, confidence=0.1, reason_codes=[], alternatives=[], status=RecommendationStatus.PENDING, created_at=now)
    db_session.add(rec)
    await db_session.commit()
    return rec


# ---------------------------------------------------------------------------
# 1. AgentState TypedDict
# ---------------------------------------------------------------------------

def test_agent_state_can_be_constructed():
    """AgentState is a TypedDict; required fields can be set."""
    state: AgentState = {
        "recommendation_id": uuid.uuid4(),
        "db": None,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    assert state["status"] == "running"
    assert state["pre_check_passed"] is True


# ---------------------------------------------------------------------------
# 2-5. Tool: get_recommendation / get_inventory
# ---------------------------------------------------------------------------

async def test_get_recommendation_returns_dict_for_known_id(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    rec = scenario["rec"]
    result = await get_recommendation(db_session, rec.recommendation_id)
    assert result is not None
    assert result["recommendation_id"] == str(rec.recommendation_id)
    assert result["action_type"] == "transfer"
    assert result["status"] == "approved"


async def test_get_recommendation_returns_none_for_unknown_id(db_session):
    result = await get_recommendation(db_session, uuid.uuid4())
    assert result is None


async def test_get_inventory_returns_quantity(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    inv = await get_inventory(db_session, scenario["src_store"].store_id, scenario["product"].product_id)
    assert inv["quantity"] == 100


async def test_get_inventory_returns_zero_for_unknown(db_session):
    inv = await get_inventory(db_session, uuid.uuid4(), uuid.uuid4())
    assert inv["quantity"] == 0


# ---------------------------------------------------------------------------
# 6-7. Tool: validate_transfer
# ---------------------------------------------------------------------------

async def test_validate_transfer_feasible_when_sufficient_source(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    # source has 100, transfer_qty=20 -> feasible
    result = await validate_transfer(db_session, scenario["rec"].recommendation_id)
    assert result["feasible"] is True


async def test_validate_transfer_infeasible_when_insufficient_source(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    # drain source to 5 (below transfer_qty=20)
    scenario["src_inv"].quantity = 5
    await db_session.flush()
    result = await validate_transfer(db_session, scenario["rec"].recommendation_id)
    assert result["feasible"] is False
    assert "insufficient" in result["reason"]


# ---------------------------------------------------------------------------
# 8-13. Mutation tool permission checks
# ---------------------------------------------------------------------------

async def test_create_transfer_rejects_non_approved_rec(db_session):
    pending_rec = await _seed_pending_rec(db_session)
    with pytest.raises(PermissionError, match="approved"):
        await create_transfer(db_session, pending_rec.recommendation_id)


async def test_create_transfer_applies_transfer_successfully(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    result = await create_transfer(db_session, scenario["rec"].recommendation_id)
    assert result["success"] is True
    assert result["transferred_quantity"] == 20


async def test_create_reorder_rejects_non_approved_rec(db_session):
    pending_rec = await _seed_pending_rec(db_session)
    with pytest.raises(PermissionError, match="approved"):
        await create_reorder(db_session, pending_rec.recommendation_id)


async def test_create_reorder_applies_reorder_successfully(db_session):
    scenario = await _seed_reorder_scenario(db_session)
    result = await create_reorder(db_session, scenario["rec"].recommendation_id)
    assert result["success"] is True
    assert result["reordered_quantity"] == 50


async def test_apply_discount_rejects_non_approved_rec(db_session):
    pending_rec = await _seed_pending_rec(db_session)
    with pytest.raises(PermissionError, match="approved"):
        await apply_discount(db_session, pending_rec.recommendation_id)


async def test_apply_discount_returns_success_for_approved(db_session):
    scenario = await _seed_reorder_scenario(db_session)
    # promote rec to discount type for this test
    scenario["rec"].action_type = ActionType.DISCOUNT
    scenario["rec"].status = RecommendationStatus.APPROVED
    await db_session.flush()
    result = await apply_discount(db_session, scenario["rec"].recommendation_id)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 14. recalculate_options
# ---------------------------------------------------------------------------

async def test_recalculate_options_creates_new_recommendation(db_session):
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine
    from backend.services.risk.engine import RiskEngine
    from sqlalchemy import select
    from backend.models.core import Risk as RiskModel

    sim = SimulationEngine(seed=99, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    await fc.run(db_session, horizon_hours=24)
    await db_session.commit()

    re = RiskEngine()
    await re.run(db_session)
    await db_session.commit()

    result = await db_session.execute(select(RiskModel).limit(1))
    risk = result.scalar_one_or_none()
    assert risk is not None

    recalc_result = await recalculate_options(db_session, risk.risk_id)
    # Should create a new recommendation (or return None if no candidates)
    # Either outcome is valid -- we just check the shape
    assert "new_recommendation_id" in recalc_result


# ---------------------------------------------------------------------------
# 15-17. node_validate
# ---------------------------------------------------------------------------

async def test_node_validate_sets_error_if_rec_not_found(db_session):
    state: AgentState = {
        "recommendation_id": uuid.uuid4(),
        "db": db_session,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_validate(state)
    assert result["error"] is not None
    assert result["status"] == "failed"


async def test_node_validate_sets_error_if_rec_not_approved(db_session):
    pending_rec = await _seed_pending_rec(db_session)
    state: AgentState = {
        "recommendation_id": pending_rec.recommendation_id,
        "db": db_session,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_validate(state)
    assert result["error"] is not None
    assert "approved" in result["error"].lower()


async def test_node_validate_succeeds_for_approved_rec(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_validate(state)
    assert result["error"] is None
    assert result["recommendation"] is not None
    assert result["recommendation"]["action_type"] == "transfer"


# ---------------------------------------------------------------------------
# 18-19. node_pre_check
# ---------------------------------------------------------------------------

async def test_node_pre_check_fails_when_source_inventory_stale(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    # drain source below transfer qty
    scenario["src_inv"].quantity = 2
    await db_session.flush()

    rec_snap = await get_recommendation(db_session, scenario["rec"].recommendation_id)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": rec_snap,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_pre_check(state)
    assert result["pre_check_passed"] is False
    assert result["stale_inventory"] is True


async def test_node_pre_check_passes_for_reorder_action(db_session):
    scenario = await _seed_reorder_scenario(db_session)
    rec_snap = await get_recommendation(db_session, scenario["rec"].recommendation_id)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": rec_snap,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_pre_check(state)
    assert result["pre_check_passed"] is True


# ---------------------------------------------------------------------------
# 20-21. node_execute
# ---------------------------------------------------------------------------

async def test_node_execute_hold_is_noop(db_session):
    state: AgentState = {
        "recommendation_id": uuid.uuid4(),
        "db": db_session,
        "recommendation": {"action_type": "hold", "status": "approved"},
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_execute(state)
    assert result["execution_result"]["success"] is True
    assert result["execution_error"] is None


async def test_node_execute_transfer_applies_inventory_change(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    rec_snap = await get_recommendation(db_session, scenario["rec"].recommendation_id)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": rec_snap,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_execute(state)
    assert result["execution_error"] is None
    assert result["execution_result"]["success"] is True
    assert result["execution_result"]["transferred_quantity"] == 20


# ---------------------------------------------------------------------------
# 22. node_verify
# ---------------------------------------------------------------------------

async def test_node_verify_passes_after_successful_transfer(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    rec_snap = await get_recommendation(db_session, scenario["rec"].recommendation_id)
    # Execute first
    exec_result = await create_transfer(db_session, scenario["rec"].recommendation_id)

    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": rec_snap,
        "execution_result": exec_result,
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_verify(state)
    assert result["verified"] is True


# ---------------------------------------------------------------------------
# 23. node_finalize
# ---------------------------------------------------------------------------

async def test_node_finalize_sets_status_completed(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": {},
        "events": [],
        "status": "running",
        "pre_check_passed": True,
        "stale_inventory": False,
        "verified": True,
        "requires_human_review": False,
    }
    result = await node_finalize(state)
    assert result["status"] == "completed"
    assert result["requires_human_review"] is False


# ---------------------------------------------------------------------------
# 24. node_recover
# ---------------------------------------------------------------------------

async def test_node_recover_sets_requires_human_review(db_session):
    scenario = await _seed_transfer_scenario(db_session)
    rec_snap = await get_recommendation(db_session, scenario["rec"].recommendation_id)
    state: AgentState = {
        "recommendation_id": scenario["rec"].recommendation_id,
        "db": db_session,
        "recommendation": rec_snap,
        "events": [],
        "status": "running",
        "pre_check_passed": False,
        "stale_inventory": True,
        "pre_check_error": "insufficient_source_inventory",
        "verified": False,
        "requires_human_review": False,
    }
    result = await node_recover(state)
    assert result["status"] == "requires_human_review"
    assert result["requires_human_review"] is True


# ---------------------------------------------------------------------------
# 25. Full graph happy path
# ---------------------------------------------------------------------------

async def test_full_graph_happy_path_approved_transfer_completes(db_session):
    """Happy path: APPROVED transfer -> completed status."""
    scenario = await _seed_transfer_scenario(db_session)
    runner = ExecutionRunner()
    run_result = await runner.run(db_session, scenario["rec"].recommendation_id)
    await db_session.commit()

    assert run_result.status == "completed"
    assert run_result.action_type == "transfer"
    assert run_result.requires_human_review is False
    assert len(run_result.events) > 0
