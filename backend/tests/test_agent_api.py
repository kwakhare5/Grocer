"""TDD API tests for Phase 6 Agent execution endpoints (spec sections 19-21).

Test seams:
 1.  POST /api/agent/execute/{unknown_id}         -- 404
 2.  POST /api/agent/execute/{pending_rec_id}     -- 409 (not approved)
 3.  POST /api/agent/execute/{approved_hold_id}   -- 200, status=completed (hold no-op)
 4.  POST /api/agent/execute/{approved_transfer}  -- 200, status=completed
 5.  Run result has "status" field
 6.  Run result has "action_type" field
 7.  Run result has "events" list (non-empty)
 8.  Stale world: pre_check fails -> status=requires_human_review
 9.  After execution: recommendation status becomes "executed"
10.  GET /api/agent/runs/{unknown_run_id}         -- 404
11.  GET /api/agent/runs/{valid_run_id}           -- 200 with status
12.  POST execute reorder rec -> status=completed
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from backend.main import create_app
from backend.database import get_db
from backend.models.core import (
    Recommendation, Inventory, Risk, Store, Supplier, Product,
)
from backend.models.enums import (
    RecommendationStatus, ActionType, RiskType, RiskSeverity,
    RiskStatus, StoreStatus, SupplierStatus, ProductCategory,
)
from backend.services.simulation.engine import SimulationEngine
from backend.services.forecasting.engine import ForecastingEngine
from backend.services.risk.engine import RiskEngine
from backend.services.decision.engine import DecisionOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Full seeded DB: sim + forecast + risks evaluated."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    await fc.run(db_session, horizon_hours=24)
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    return db_session


@pytest_asyncio.fixture
async def approved_transfer_rec(seeded_db):
    """APPROVED TRANSFER recommendation ready for agent execution."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(
        supplier_id=uuid.uuid4(), name="API Test Supplier",
        lead_time_hours=24, status=SupplierStatus.ACTIVE,
    )
    seeded_db.add(supplier)

    product = Product(
        product_id=uuid.uuid4(), name="API Test Bread",
        category=ProductCategory.BAKERY, unit="unit",
        shelf_life_hours=48, base_price=10.0,
        supplier_id=supplier.supplier_id,
    )
    seeded_db.add(product)

    src_store = Store(store_id=uuid.uuid4(), name="API Src", latitude=19.0, longitude=72.8, operating_status=StoreStatus.ACTIVE)
    dst_store = Store(store_id=uuid.uuid4(), name="API Dst", latitude=19.1, longitude=72.9, operating_status=StoreStatus.ACTIVE)
    seeded_db.add(src_store)
    seeded_db.add(dst_store)

    risk = Risk(
        risk_id=uuid.uuid4(), store_id=dst_store.store_id,
        product_id=product.product_id, risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL, probability=0.9,
        expected_time=now + timedelta(hours=6),
        status=RiskStatus.ACTIVE, created_at=now,
    )
    seeded_db.add(risk)

    src_inv = Inventory(store_id=src_store.store_id, product_id=product.product_id, quantity=100)
    dst_inv = Inventory(store_id=dst_store.store_id, product_id=product.product_id, quantity=0)
    seeded_db.add(src_inv)
    seeded_db.add(dst_inv)

    rec = Recommendation(
        recommendation_id=uuid.uuid4(), risk_id=risk.risk_id,
        action_type=ActionType.TRANSFER, quantity=20,
        source_store_id=src_store.store_id,
        destination_store_id=dst_store.store_id,
        score=0.75, confidence=0.80,
        reason_codes=["HIGH_STOCKOUT_RISK", "SOURCE_HAS_SAFE_EXCESS"],
        alternatives=[], status=RecommendationStatus.APPROVED, created_at=now,
    )
    seeded_db.add(rec)
    await seeded_db.commit()
    return {"rec": rec, "src_inv": src_inv, "product": product, "risk": risk}


@pytest_asyncio.fixture
async def approved_hold_rec(seeded_db):
    """APPROVED HOLD recommendation (no-op execution)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(supplier_id=uuid.uuid4(), name="Hold Sup", lead_time_hours=24, status=SupplierStatus.ACTIVE)
    seeded_db.add(supplier)
    product = Product(product_id=uuid.uuid4(), name="Hold Prod", category=ProductCategory.STAPLES, unit="kg", shelf_life_hours=720, base_price=5.0, supplier_id=supplier.supplier_id)
    seeded_db.add(product)
    store = Store(store_id=uuid.uuid4(), name="Hold Store", latitude=19.2, longitude=73.0, operating_status=StoreStatus.ACTIVE)
    seeded_db.add(store)
    risk = Risk(risk_id=uuid.uuid4(), store_id=store.store_id, product_id=product.product_id, risk_type=RiskType.STOCKOUT, severity=RiskSeverity.LOW, probability=0.05, expected_time=now + timedelta(hours=72), status=RiskStatus.ACTIVE, created_at=now)
    seeded_db.add(risk)
    rec = Recommendation(recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.HOLD, quantity=0, source_store_id=None, destination_store_id=store.store_id, score=0.95, confidence=0.99, reason_codes=["INVENTORY_HEALTHY"], alternatives=[], status=RecommendationStatus.APPROVED, created_at=now)
    seeded_db.add(rec)
    await seeded_db.commit()
    return rec


@pytest_asyncio.fixture
async def pending_rec(seeded_db):
    """PENDING (unapproved) recommendation."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    supplier = Supplier(supplier_id=uuid.uuid4(), name="P Sup", lead_time_hours=24, status=SupplierStatus.ACTIVE)
    seeded_db.add(supplier)
    product = Product(product_id=uuid.uuid4(), name="P Prod", category=ProductCategory.STAPLES, unit="kg", shelf_life_hours=720, base_price=5.0, supplier_id=supplier.supplier_id)
    seeded_db.add(product)
    store = Store(store_id=uuid.uuid4(), name="P Store", latitude=19.3, longitude=73.1, operating_status=StoreStatus.ACTIVE)
    seeded_db.add(store)
    risk = Risk(risk_id=uuid.uuid4(), store_id=store.store_id, product_id=product.product_id, risk_type=RiskType.STOCKOUT, severity=RiskSeverity.LOW, probability=0.1, expected_time=now + timedelta(hours=48), status=RiskStatus.ACTIVE, created_at=now)
    seeded_db.add(risk)
    rec = Recommendation(recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.TRANSFER, quantity=10, source_store_id=store.store_id, destination_store_id=store.store_id, score=0.1, confidence=0.1, reason_codes=[], alternatives=[], status=RecommendationStatus.PENDING, created_at=now)
    seeded_db.add(rec)
    await seeded_db.commit()
    return rec


@pytest_asyncio.fixture
async def client(seeded_db):
    """HTTP client wired to seeded DB."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_with_transfer(approved_transfer_rec, seeded_db):
    """HTTP client wired to DB that has an approved transfer rec."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, approved_transfer_rec


@pytest_asyncio.fixture
async def client_with_hold(approved_hold_rec, seeded_db):
    """HTTP client wired to DB that has an approved hold rec."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, approved_hold_rec


@pytest_asyncio.fixture
async def client_with_pending(pending_rec, seeded_db):
    """HTTP client wired to DB that has a pending rec."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, pending_rec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_execute_unknown_recommendation_returns_404(client):
    """1. Unknown recommendation_id -> 404."""
    resp = await client.post(f"/api/agent/execute/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_execute_pending_recommendation_returns_409(client_with_pending):
    """2. PENDING recommendation -> 409 conflict (spec section 18 LOCKED)."""
    client, rec = client_with_pending
    resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    assert resp.status_code == 409
    assert "approved" in resp.json()["detail"].lower()


async def test_execute_approved_hold_returns_completed(client_with_hold):
    """3. HOLD recommendation -> 200, status=completed (no-op)."""
    client, rec = client_with_hold
    resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_execute_approved_transfer_returns_completed(client_with_transfer):
    """4. APPROVED TRANSFER -> 200, status=completed."""
    client, scenario = client_with_transfer
    resp = await client.post(f"/api/agent/execute/{scenario['rec'].recommendation_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_execute_response_has_status_field(client_with_hold):
    """5. Response has 'status' field."""
    client, rec = client_with_hold
    resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    assert "status" in resp.json()


async def test_execute_response_has_action_type_field(client_with_hold):
    """6. Response has 'action_type' field."""
    client, rec = client_with_hold
    resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    assert "action_type" in resp.json()
    assert resp.json()["action_type"] == "hold"


async def test_execute_response_has_events_list(client_with_hold):
    """7. Response has non-empty 'events' list."""
    client, rec = client_with_hold
    resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    data = resp.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0


async def test_execute_stale_inventory_returns_requires_human_review(client_with_transfer, seeded_db):
    """8. When source inventory changes before execution -> requires_human_review."""
    client, scenario = client_with_transfer
    # Drain source inventory to make transfer infeasible
    scenario["src_inv"].quantity = 0
    await seeded_db.flush()
    await seeded_db.commit()

    resp = await client.post(f"/api/agent/execute/{scenario['rec'].recommendation_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "requires_human_review"
    assert data["requires_human_review"] is True


async def test_execute_marks_recommendation_executed(client_with_transfer, seeded_db):
    """9. After successful execution, recommendation status becomes 'executed'."""
    client, scenario = client_with_transfer
    resp = await client.post(f"/api/agent/execute/{scenario['rec'].recommendation_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Check DB state
    from sqlalchemy import select
    result = await seeded_db.execute(
        select(Recommendation).where(Recommendation.recommendation_id == scenario["rec"].recommendation_id)
    )
    rec_row = result.scalar_one()
    rec_status = rec_row.status.value if hasattr(rec_row.status, "value") else str(rec_row.status)
    assert rec_status == "executed"


async def test_get_run_status_unknown_returns_404(client):
    """10. Unknown run_id -> 404."""
    resp = await client.get(f"/api/agent/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_run_status_after_execution(client_with_hold):
    """11. GET /api/agent/runs/{run_id} returns 200 after execute."""
    client, rec = client_with_hold
    exec_resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    run_id = exec_resp.json()["run_id"]
    resp = await client.get(f"/api/agent/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id
    assert "status" in resp.json()


async def test_execute_approved_reorder_returns_completed(seeded_db):
    """12. APPROVED REORDER -> status=completed."""
    from datetime import datetime, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(supplier_id=uuid.uuid4(), name="R Sup", lead_time_hours=12, status=SupplierStatus.ACTIVE)
    seeded_db.add(supplier)
    product = Product(product_id=uuid.uuid4(), name="R Prod", category=ProductCategory.DAIRY, unit="l", shelf_life_hours=72, base_price=25.0, supplier_id=supplier.supplier_id)
    seeded_db.add(product)
    store = Store(store_id=uuid.uuid4(), name="R Store", latitude=19.4, longitude=73.2, operating_status=StoreStatus.ACTIVE)
    seeded_db.add(store)
    risk = Risk(risk_id=uuid.uuid4(), store_id=store.store_id, product_id=product.product_id, risk_type=RiskType.STOCKOUT, severity=RiskSeverity.WARNING, probability=0.6, expected_time=now + timedelta(hours=12), status=RiskStatus.ACTIVE, created_at=now)
    seeded_db.add(risk)
    inv = Inventory(store_id=store.store_id, product_id=product.product_id, quantity=5)
    seeded_db.add(inv)
    rec = Recommendation(recommendation_id=uuid.uuid4(), risk_id=risk.risk_id, action_type=ActionType.REORDER, quantity=50, source_store_id=None, destination_store_id=store.store_id, score=0.55, confidence=0.70, reason_codes=["HIGH_STOCKOUT_RISK"], alternatives=[], status=RecommendationStatus.APPROVED, created_at=now)
    seeded_db.add(rec)
    await seeded_db.commit()

    app = create_app()
    async def override_get_db():
        yield seeded_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/agent/execute/{rec.recommendation_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
