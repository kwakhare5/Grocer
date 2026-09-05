"""TDD tests for Phase 6: Human Approval + LangGraph Execution Engine.

Verifies:
- Seam 1: Batch-Aware Mutation Tools (FIFO deduction, batch creation, inventory sync) & Idempotency Guard
- Seam 2: Action Entity Synchronization (PENDING -> EXECUTING -> COMPLETED/FAILED)
- Seam 3: Strict Programmatic Verification Node (node_verify) & Database Assertions
- Seam 4: Failure Recovery & Fresh Alternative Re-calculation (node_recover)
- Seam 5: API Hardening & Run Trace Persistence
- Seam 6: Comprehensive Regression Suite & Invariant Verification
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, func

from backend.models.core import (
    Store, Product, Supplier, Inventory, Batch, Risk, Recommendation, Action, Event
)
from backend.models.enums import (
    StoreStatus, ProductCategory, SupplierStatus, RiskType, RiskSeverity,
    RiskStatus, ActionType, ActionStatus, RecommendationStatus
)
from backend.agents.execution.tools import (
    create_transfer,
    create_reorder,
    apply_discount,
    get_inventory,
)


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _setup_stores_and_product(db_session):
    """Seed supplier, product, and 2 stores."""
    now = _naive_now()
    supplier = Supplier(
        supplier_id=uuid.uuid4(),
        name="Phase 6 Supplier",
        lead_time_hours=24,
        status=SupplierStatus.ACTIVE,
    )
    db_session.add(supplier)

    product = Product(
        product_id=uuid.uuid4(),
        name="Fresh Milk 1L",
        category=ProductCategory.DAIRY,
        unit="bottle",
        shelf_life_hours=48,
        base_price=3.5,
        supplier_id=supplier.supplier_id,
    )
    db_session.add(product)

    src_store = Store(
        store_id=uuid.uuid4(),
        name="Tiong Bahru Dark Store",
        latitude=1.2868,
        longitude=103.8272,
        operating_status=StoreStatus.ACTIVE,
    )
    dest_store = Store(
        store_id=uuid.uuid4(),
        name="Orchard Dark Store",
        latitude=1.3048,
        longitude=103.8318,
        operating_status=StoreStatus.ACTIVE,
    )
    db_session.add(src_store)
    db_session.add(dest_store)
    await db_session.flush()

    return supplier, product, src_store, dest_store


# ===========================================================================
# Seam 1: Batch-Aware Mutation Tools & Idempotency Guard
# ===========================================================================

@pytest.mark.asyncio
async def test_transfer_fifo_batch_deduction_and_destination_batch_creation(db_session):
    """create_transfer deducts FIFO from earliest expiring batches and creates matching destination batches."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    # Source has 2 batches:
    # Batch 1: 15 units expiring in 10h (earlier)
    # Batch 2: 25 units expiring in 30h (later)
    b1 = Batch(
        batch_id=uuid.uuid4(),
        store_id=src.store_id,
        product_id=product.product_id,
        quantity=15,
        received_at=now - timedelta(hours=20),
        expires_at=now + timedelta(hours=10),
    )
    b2 = Batch(
        batch_id=uuid.uuid4(),
        store_id=src.store_id,
        product_id=product.product_id,
        quantity=25,
        received_at=now - timedelta(hours=10),
        expires_at=now + timedelta(hours=30),
    )
    db_session.add_all([b1, b2])

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=40)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=5)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.88,
        expected_time=now + timedelta(hours=5),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=20,  # Takes 15 from b1, 5 from b2
        source_store_id=src.store_id,
        destination_store_id=dest.store_id,
        score=0.92,
        confidence=0.85,
        reason_codes=["SAFE_EXCESS_AVAILABLE"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    # Execute transfer tool
    res = await create_transfer(db_session, rec.recommendation_id)
    await db_session.commit()

    assert res["success"] is True
    assert res["transferred_quantity"] == 20

    # Verify source batches: b1 depleted to 0, b2 reduced to 20
    b1_refreshed = await db_session.get(Batch, b1.batch_id)
    b2_refreshed = await db_session.get(Batch, b2.batch_id)
    assert b1_refreshed.quantity == 0
    assert b2_refreshed.quantity == 20

    # Verify destination batches created with matching expiry dates
    dest_batches_res = await db_session.execute(
        select(Batch).where(Batch.store_id == dest.store_id).order_by(Batch.expires_at.asc())
    )
    dest_batches = dest_batches_res.scalars().all()
    assert len(dest_batches) == 2
    assert dest_batches[0].quantity == 15
    assert dest_batches[0].expires_at == b1.expires_at
    assert dest_batches[1].quantity == 5
    assert dest_batches[1].expires_at == b2.expires_at

    # Verify inventory aggregates synchronized with sum of batches
    src_inv_refreshed = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == src.store_id, Inventory.product_id == product.product_id)
    )).scalar_one()
    dest_inv_refreshed = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == dest.store_id, Inventory.product_id == product.product_id)
    )).scalar_one()

    assert src_inv_refreshed.quantity == 20
    assert dest_inv_refreshed.quantity == 25  # 5 initial + 20 transferred


@pytest.mark.asyncio
async def test_transfer_rejects_expired_batches(db_session):
    """create_transfer fails if source stock consists only of expired batches."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    # Expired batch at source
    expired_batch = Batch(
        batch_id=uuid.uuid4(),
        store_id=src.store_id,
        product_id=product.product_id,
        quantity=30,
        received_at=now - timedelta(hours=60),
        expires_at=now - timedelta(hours=1),  # Already expired!
    )
    db_session.add(expired_batch)

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=30)
    db_session.add(src_inv)

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.9,
        expected_time=now + timedelta(hours=4),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=15,
        source_store_id=src.store_id,
        destination_store_id=dest.store_id,
        score=0.88,
        confidence=0.80,
        reason_codes=["SAFE_EXCESS_AVAILABLE"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    res = await create_transfer(db_session, rec.recommendation_id)
    assert res["success"] is False
    assert "expired" in res["error"].lower() or "insufficient" in res["error"].lower()

    # Source inventory must not be mutated
    inv_check = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == src.store_id, Inventory.product_id == product.product_id)
    )).scalar_one()
    assert inv_check.quantity == 30


@pytest.mark.asyncio
async def test_reorder_creates_fresh_batch_with_shelf_life(db_session):
    """create_reorder creates a fresh Batch at destination store matching product shelf life."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=2)
    db_session.add(dest_inv)

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.85,
        expected_time=now + timedelta(hours=3),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.REORDER,
        quantity=50,
        source_store_id=None,
        destination_store_id=dest.store_id,
        score=0.90,
        confidence=0.90,
        reason_codes=["SUPPLIER_LEAD_TIME_FEASIBLE"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    res = await create_reorder(db_session, rec.recommendation_id)
    await db_session.commit()

    assert res["success"] is True
    assert res["reordered_quantity"] == 50

    # Destination batch created
    new_batches = (await db_session.execute(
        select(Batch).where(Batch.store_id == dest.store_id, Batch.product_id == product.product_id)
    )).scalars().all()
    assert len(new_batches) == 1
    assert new_batches[0].quantity == 50
    # Expiry is roughly now + 48 hours
    exp_delta = (new_batches[0].expires_at - now).total_seconds() / 3600.0
    assert 47.0 <= exp_delta <= 49.0

    # Aggregate inventory updated
    dest_inv_refreshed = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == dest.store_id, Inventory.product_id == product.product_id)
    )).scalar_one()
    assert dest_inv_refreshed.quantity == 52  # 2 initial + 50


@pytest.mark.asyncio
async def test_idempotency_rejects_already_executed_recommendation(db_session):
    """Mutation tools reject recommendations that have already been executed."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.9,
        expected_time=now + timedelta(hours=4),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=10,
        source_store_id=src.store_id,
        destination_store_id=dest.store_id,
        score=0.85,
        confidence=0.85,
        reason_codes=["SAFE_EXCESS_AVAILABLE"],
        alternatives=[],
        status=RecommendationStatus.EXECUTED,  # Already executed!
    )
    db_session.add(rec)
    await db_session.commit()

    res = await create_transfer(db_session, rec.recommendation_id)
    assert res["success"] is False
    assert "already executed" in res["error"].lower() or "executed" in res["error"].lower()


# ===========================================================================
# Seam 2: Action Entity Synchronization (PENDING -> EXECUTING -> COMPLETED/FAILED)
# ===========================================================================

from backend.agents.execution.nodes import (
    node_validate,
    node_pre_check,
    node_execute,
    node_verify,
    node_finalize,
    node_recover,
)
from backend.agents.execution.state import AgentState


@pytest.mark.asyncio
async def test_action_lifecycle_transitions_to_completed_on_success(db_session):
    """Action row transitions to EXECUTING during execution and COMPLETED upon finalization."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=50)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=10)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.9,
        expected_time=now + timedelta(hours=4),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=15,
        source_store_id=src.store_id,
        destination_store_id=dest.store_id,
        score=0.9,
        confidence=0.85,
        reason_codes=["SAFE_EXCESS_AVAILABLE"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)

    # Staged action created upon operator approval
    action = Action(
        action_id=uuid.uuid4(),
        recommendation_id=rec.recommendation_id,
        action_type=ActionType.TRANSFER,
        approved_by="lead_dispatcher",
        approved_at=now,
        status=ActionStatus.PENDING,
    )
    db_session.add(action)
    await db_session.commit()

    # Step 1: node_validate
    state: AgentState = {
        "recommendation_id": rec.recommendation_id,
        "db": db_session,
        "events": [],
    }
    val_update = await node_validate(state)
    state.update(val_update)
    assert state.get("action_id") == action.action_id

    # Step 2: node_pre_check
    pc_update = await node_pre_check(state)
    state.update(pc_update)
    assert state["pre_check_passed"] is True

    # Step 3: node_execute
    exec_update = await node_execute(state)
    state.update(exec_update)
    assert state["execution_result"]["success"] is True

    # Check intermediate state: action is EXECUTING
    action_refreshed = await db_session.get(Action, action.action_id)
    assert action_refreshed.status == ActionStatus.EXECUTING

    # Step 4: node_verify
    ver_update = await node_verify(state)
    state.update(ver_update)
    assert state["verified"] is True

    # Step 5: node_finalize
    fin_update = await node_finalize(state)
    state.update(fin_update)
    assert state["status"] == "completed"

    # Action row must now be COMPLETED with executed_at recorded
    action_final = await db_session.get(Action, action.action_id)
    assert action_final.status == ActionStatus.COMPLETED
    assert action_final.executed_at is not None


@pytest.mark.asyncio
async def test_action_lifecycle_transitions_to_failed_on_recovery(db_session):
    """Action row transitions to FAILED with failure_reason recorded when recovery triggers."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    risk = Risk(
        risk_id=uuid.uuid4(),
        store_id=dest.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.9,
        expected_time=now + timedelta(hours=4),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(),
        risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER,
        quantity=30,
        source_store_id=src.store_id,
        destination_store_id=dest.store_id,
        score=0.9,
        confidence=0.85,
        reason_codes=["SAFE_EXCESS_AVAILABLE"],
        alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)

    action = Action(
        action_id=uuid.uuid4(),
        recommendation_id=rec.recommendation_id,
        action_type=ActionType.TRANSFER,
        approved_by="lead_dispatcher",
        approved_at=now,
        status=ActionStatus.PENDING,
    )
    db_session.add(action)
    await db_session.commit()

    # Trigger recovery directly with failure context
    state: AgentState = {
        "recommendation_id": rec.recommendation_id,
        "action_id": action.action_id,
        "db": db_session,
        "recommendation": {
            "recommendation_id": str(rec.recommendation_id),
            "risk_id": str(risk.risk_id),
            "action_type": "transfer",
        },
        "pre_check_passed": False,
        "pre_check_error": "insufficient_source_inventory: have 0, need 30",
        "stale_inventory": True,
        "events": [],
    }
    rec_update = await node_recover(state)
    state.update(rec_update)

    assert state["status"] == "requires_human_review"
    action_refreshed = await db_session.get(Action, action.action_id)
    assert action_refreshed.status == ActionStatus.FAILED
    assert "insufficient_source_inventory" in action_refreshed.failure_reason


# ===========================================================================
# Seam 3: Strict Programmatic Verification Node & Invariants
# ===========================================================================

@pytest.mark.asyncio
async def test_node_verify_passes_and_records_details_for_valid_transfer(db_session):
    """node_verify checks non-negative inventory and audit event persistence."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=30)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=10)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.CRITICAL, probability=0.9,
        expected_time=now + timedelta(hours=4), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=10, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.9, confidence=0.85, reason_codes=["SAFE_EXCESS_AVAILABLE"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    # Run execute
    exec_res = await create_transfer(db_session, rec.recommendation_id)
    await db_session.commit()

    state: AgentState = {
        "recommendation_id": rec.recommendation_id,
        "db": db_session,
        "recommendation": {
            "recommendation_id": str(rec.recommendation_id),
            "action_type": "transfer",
            "source_store_id": str(src.store_id),
            "destination_store_id": str(dest.store_id),
            "quantity": 10,
        },
        "execution_result": exec_res,
        "events": [],
    }

    ver_res = await node_verify(state)
    assert ver_res["verified"] is True
    assert ver_res.get("verification_details") is not None
    assert ver_res["verification_details"]["source_non_negative"] is True
    assert ver_res["verification_details"]["dest_non_negative"] is True
    assert ver_res["verification_details"]["audit_event_logged"] is True


@pytest.mark.asyncio
async def test_node_verify_fails_on_negative_inventory_invariant(db_session):
    """node_verify fails and diverts when negative inventory is detected."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    # Corrupt source inventory to negative
    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=-5)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=10)
    db_session.add_all([src_inv, dest_inv])
    await db_session.commit()

    state: AgentState = {
        "recommendation_id": uuid.uuid4(),
        "db": db_session,
        "recommendation": {
            "action_type": "transfer",
            "source_store_id": str(src.store_id),
            "destination_store_id": str(dest.store_id),
            "quantity": 10,
        },
        "execution_result": {
            "success": True,
            "source_store_id": str(src.store_id),
            "destination_store_id": str(dest.store_id),
            "product_id": str(product.product_id),
            "transferred_quantity": 10,
        },
        "events": [],
    }

    ver_res = await node_verify(state)
    assert ver_res["verified"] is False
    assert "negative inventory" in ver_res["verify_error"].lower()


# ===========================================================================
# Seam 4: Failure Recovery & Fresh Alternative Re-calculation
# ===========================================================================

from backend.agents.execution.runner import ExecutionRunner


@pytest.mark.asyncio
async def test_full_graph_stale_inventory_triggers_recovery_and_recalculates(db_session):
    """When source inventory changes between approval and execution, graph diverts to recover and generates new option."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    # Source initially had stock, but depleted to 0 (drift)
    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=0)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=2)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.CRITICAL, probability=0.9,
        expected_time=now + timedelta(hours=3), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=20, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.9, confidence=0.85, reason_codes=["SAFE_EXCESS_AVAILABLE"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)

    action = Action(
        action_id=uuid.uuid4(), recommendation_id=rec.recommendation_id, action_type=ActionType.TRANSFER,
        approved_by="dispatcher", approved_at=now, status=ActionStatus.PENDING,
    )
    db_session.add(action)
    await db_session.commit()

    runner = ExecutionRunner()
    run_result = await runner.run(db_session, rec.recommendation_id)
    await db_session.commit()

    assert run_result.status == "requires_human_review"
    assert run_result.requires_human_review is True
    assert run_result.error is not None
    assert "insufficient_source_inventory" in run_result.error

    # Linked action should be marked FAILED
    action_refreshed = await db_session.get(Action, action.action_id)
    assert action_refreshed.status == ActionStatus.FAILED
    assert "insufficient_source_inventory" in action_refreshed.failure_reason

    # Decision Engine proposed a new alternative recommendation
    assert run_result.new_recommendation_id is not None
    new_rec = await db_session.get(Recommendation, run_result.new_recommendation_id)
    assert new_rec is not None
    assert new_rec.status == RecommendationStatus.PENDING


# ===========================================================================
# Seam 5: API Hardening & Run Trace Persistence
# ===========================================================================

from httpx import ASGITransport, AsyncClient
from backend.main import create_app
from backend.database import get_db


@pytest.mark.asyncio
async def test_api_execute_approved_transfer_and_query_runs(db_session):
    """POST /api/agent/execute executes approved recommendation, records run, and exposes GET /runs."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=40)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=5)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.CRITICAL, probability=0.9,
        expected_time=now + timedelta(hours=3), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=15, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.92, confidence=0.88, reason_codes=["SAFE_EXCESS_AVAILABLE"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Execute recommendation
        resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["action_type"] == "transfer"
        assert "run_id" in data
        run_id = data["run_id"]

        # 2. Query run status by ID
        status_resp = await client.get(f"/api/agent/runs/{run_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

        # 3. List recent runs
        list_resp = await client.get("/api/agent/runs")
        assert list_resp.status_code == 200
        runs = list_resp.json()
        assert any(r["run_id"] == run_id for r in runs)


@pytest.mark.asyncio
async def test_api_execute_rejects_pending_or_already_executed(db_session):
    """POST /api/agent/execute returns 409 for non-approved or already executed recommendations."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.WARNING, probability=0.6,
        expected_time=now + timedelta(hours=8), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec_pending = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=10, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.8, confidence=0.8, reason_codes=["SAFE_EXCESS_AVAILABLE"], alternatives=[],
        status=RecommendationStatus.PENDING,
    )
    rec_executed = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.HOLD,
        quantity=0, source_store_id=None, destination_store_id=None,
        score=0.5, confidence=0.7, reason_codes=["HOLD"], alternatives=[],
        status=RecommendationStatus.EXECUTED,
    )
    db_session.add_all([rec_pending, rec_executed])
    await db_session.commit()

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pending -> 409
        r1 = await client.post(f"/api/agent/execute/{rec_pending.recommendation_id}")
        assert r1.status_code == 409

        # Executed -> 409
        r2 = await client.post(f"/api/agent/execute/{rec_executed.recommendation_id}")
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_api_execute_rejected_recommendation_returns_409(db_session):
    """POST /api/agent/execute returns 409 when attempting to execute a REJECTED recommendation."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.WARNING, probability=0.5,
        expected_time=now + timedelta(hours=8), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec_rejected = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=10, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.4, confidence=0.6, reason_codes=["LOW_CONFIDENCE"], alternatives=[],
        status=RecommendationStatus.REJECTED,
    )
    db_session.add(rec_rejected)
    await db_session.commit()

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/agent/execute/{rec_rejected.recommendation_id}")
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_batch_conservation_invariant_across_transfers(db_session):
    """Total batch quantity across stores is strictly conserved before and after transfers."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    b1 = Batch(
        batch_id=uuid.uuid4(), store_id=src.store_id, product_id=product.product_id,
        quantity=30, received_at=now - timedelta(hours=10), expires_at=now + timedelta(hours=20),
    )
    b2 = Batch(
        batch_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        quantity=15, received_at=now - timedelta(hours=5), expires_at=now + timedelta(hours=25),
    )
    db_session.add_all([b1, b2])

    src_inv = Inventory(store_id=src.store_id, product_id=product.product_id, quantity=30)
    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=15)
    db_session.add_all([src_inv, dest_inv])

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.CRITICAL, probability=0.9,
        expected_time=now + timedelta(hours=3), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER,
        quantity=12, source_store_id=src.store_id, destination_store_id=dest.store_id,
        score=0.9, confidence=0.9, reason_codes=["SAFE_EXCESS_AVAILABLE"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec)
    await db_session.commit()

    # Sum of all batches before
    batches_before = (await db_session.execute(
        select(func.sum(Batch.quantity)).where(Batch.product_id == product.product_id)
    )).scalar()
    assert batches_before == 45

    runner = ExecutionRunner()
    run_res = await runner.run(db_session, rec.recommendation_id)
    await db_session.commit()

    assert run_res.status == "completed"

    # Sum of all batches after
    batches_after = (await db_session.execute(
        select(func.sum(Batch.quantity)).where(Batch.product_id == product.product_id)
    )).scalar()
    assert batches_after == batches_before == 45


@pytest.mark.asyncio
async def test_full_graph_discount_and_hold_execution(db_session):
    """DISCOUNT and HOLD recommendations execute cleanly through the full LangGraph runner."""
    supplier, product, src, dest = await _setup_stores_and_product(db_session)
    now = _naive_now()

    dest_inv = Inventory(store_id=dest.store_id, product_id=product.product_id, quantity=20)
    db_session.add(dest_inv)

    risk_spoilage = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.SPOILAGE, severity=RiskSeverity.CRITICAL, probability=0.85,
        expected_time=now + timedelta(hours=6), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk_spoilage)

    rec_discount = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk_spoilage.risk_id, action_type=ActionType.DISCOUNT,
        quantity=20, source_store_id=None, destination_store_id=dest.store_id,
        score=0.88, confidence=0.85, reason_codes=["HIGH_SPOILAGE_RISK"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec_discount)

    act_discount = Action(
        action_id=uuid.uuid4(), recommendation_id=rec_discount.recommendation_id,
        action_type=ActionType.DISCOUNT, approved_by="pricing_manager",
        approved_at=now, status=ActionStatus.PENDING,
    )
    db_session.add(act_discount)
    await db_session.commit()

    runner = ExecutionRunner()
    res_disc = await runner.run(db_session, rec_discount.recommendation_id)
    await db_session.commit()

    assert res_disc.status == "completed"
    assert res_disc.action_type == "discount"
    act_disc_refreshed = await db_session.get(Action, act_discount.action_id)
    assert act_disc_refreshed.status == ActionStatus.COMPLETED

    # HOLD execution test
    risk_healthy = Risk(
        risk_id=uuid.uuid4(), store_id=dest.store_id, product_id=product.product_id,
        risk_type=RiskType.STOCKOUT, severity=RiskSeverity.LOW, probability=0.05,
        expected_time=now + timedelta(hours=96), status=RiskStatus.ACTIVE,
    )
    db_session.add(risk_healthy)

    rec_hold = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk_healthy.risk_id, action_type=ActionType.HOLD,
        quantity=0, source_store_id=None, destination_store_id=dest.store_id,
        score=0.95, confidence=0.95, reason_codes=["INVENTORY_HEALTHY"], alternatives=[],
        status=RecommendationStatus.APPROVED,
    )
    db_session.add(rec_hold)

    act_hold = Action(
        action_id=uuid.uuid4(), recommendation_id=rec_hold.recommendation_id,
        action_type=ActionType.HOLD, approved_by="auto_system",
        approved_at=now, status=ActionStatus.PENDING,
    )
    db_session.add(act_hold)
    await db_session.commit()

    res_hold = await runner.run(db_session, rec_hold.recommendation_id)
    await db_session.commit()

    assert res_hold.status == "completed"
    assert res_hold.action_type == "hold"
    act_hold_refreshed = await db_session.get(Action, act_hold.action_id)
    assert act_hold_refreshed.status == ActionStatus.COMPLETED





