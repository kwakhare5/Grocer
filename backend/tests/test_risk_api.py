"""TDD API tests for Phase 4 Risk endpoints.

Seams under test:
1.  GET  /api/risks                       — returns list (initially empty)
2.  POST /api/risks/evaluate              — triggers risk engine, returns count
3.  GET  /api/risks                       — returns detected risks after evaluation
4.  GET  /api/risks/{id}                  — returns specific risk details
5.  GET  /api/risks/{random_uuid}         — returns 404
6.  GET  /api/risks?store_id=<id>         — filters by store
7.  GET  /api/risks?risk_type=stockout    — filters by risk_type
8.  GET  /api/risks?severity=critical     — filters by severity
9.  GET  /api/risks?status=active         — filters by status
10. POST /api/risks/{id}/resolve          — marks risk as resolved
11. POST /api/risks/{random_uuid}/resolve — returns 404
12. GET  /api/stores/{id}/risks           — returns store-scoped risks
13. GET  /api/stores/{random_uuid}/risks  — returns 404
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.database import get_db
from backend.services.simulation.engine import SimulationEngine
from backend.services.forecasting.engine import ForecastingEngine
from backend.models.core import Inventory
from sqlalchemy import update


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Seed simulator data, generate forecasts, and return db session."""
    engine = SimulationEngine(seed=42, historical_days=7)
    await engine.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()
    return db_session


@pytest_asyncio.fixture
async def client(seeded_db):
    """HTTP client wired to the seeded test DB via dependency override."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Risk Endpoints ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_risks_initially_empty(client):
    """GET /api/risks returns empty list before evaluation."""
    resp = await client.get("/api/risks")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_evaluate_risks_endpoint(client, seeded_db):
    """POST /api/risks/evaluate triggers risk evaluation."""
    # Force low inventory to guarantee risk generation
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    resp = await client.post("/api/risks/evaluate")
    assert resp.status_code == 200
    data = resp.json()
    assert "risks_detected" in data
    assert data["risks_detected"] > 0


@pytest.mark.asyncio
async def test_list_risks_after_evaluation(client, seeded_db):
    """GET /api/risks returns risks after evaluation."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    eval_resp = await client.post("/api/risks/evaluate")
    count = eval_resp.json()["risks_detected"]

    resp = await client.get("/api/risks")
    assert resp.status_code == 200
    risks = resp.json()
    assert len(risks) == count
    assert len(risks) > 0

    first = risks[0]
    assert "risk_id" in first
    assert "store_id" in first
    assert "product_id" in first
    assert "risk_type" in first
    assert "severity" in first
    assert "probability" in first
    assert "expected_time" in first
    assert "status" in first


@pytest.mark.asyncio
async def test_get_risk_by_id(client, seeded_db):
    """GET /api/risks/{risk_id} returns risk details."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")
    list_resp = await client.get("/api/risks")
    first_risk = list_resp.json()[0]
    risk_id = first_risk["risk_id"]

    resp = await client.get(f"/api/risks/{risk_id}")
    assert resp.status_code == 200
    assert resp.json()["risk_id"] == risk_id
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_get_risk_not_found(client):
    """GET /api/risks/{random_uuid} returns 404."""
    resp = await client.get(f"/api/risks/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_risks_by_store(client, seeded_db):
    """GET /api/risks?store_id=X returns only risks for that store."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")
    list_resp = await client.get("/api/risks")
    target_store = list_resp.json()[0]["store_id"]

    resp = await client.get(f"/api/risks?store_id={target_store}")
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) > 0
    for r in filtered:
        assert r["store_id"] == target_store


@pytest.mark.asyncio
async def test_filter_risks_by_risk_type(client, seeded_db):
    """GET /api/risks?risk_type=stockout returns only stockout risks."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")
    resp = await client.get("/api/risks?risk_type=stockout")
    assert resp.status_code == 200
    for r in resp.json():
        assert r["risk_type"] == "stockout"


@pytest.mark.asyncio
async def test_filter_risks_by_status(client, seeded_db):
    """GET /api/risks?status=active returns only active risks."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")
    resp = await client.get("/api/risks?status=active")
    assert resp.status_code == 200
    for r in resp.json():
        assert r["status"] == "active"


@pytest.mark.asyncio
async def test_resolve_risk_endpoint(client, seeded_db):
    """POST /api/risks/{risk_id}/resolve transitions risk status to resolved."""
    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")
    list_resp = await client.get("/api/risks")
    risk_id = list_resp.json()[0]["risk_id"]

    resp = await client.post(f"/api/risks/{risk_id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    # Verify risk status is resolved in GET
    detail_resp = await client.get(f"/api/risks/{risk_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_resolve_risk_not_found(client):
    """POST /api/risks/{random_uuid}/resolve returns 404."""
    resp = await client.post(f"/api/risks/{uuid.uuid4()}/resolve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_store_risks_endpoint(client, seeded_db):
    """GET /api/stores/{store_id}/risks returns risks for the store."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    await seeded_db.execute(update(Inventory).values(quantity=1))
    await seeded_db.commit()

    await client.post("/api/risks/evaluate")

    resp = await client.get(f"/api/stores/{store.store_id}/risks")
    assert resp.status_code == 200
    risks = resp.json()
    assert len(risks) > 0
    for r in risks:
        assert r["store_id"] == str(store.store_id)


@pytest.mark.asyncio
async def test_store_risks_not_found(client):
    """GET /api/stores/{random_uuid}/risks returns 404."""
    resp = await client.get(f"/api/stores/{uuid.uuid4()}/risks")
    assert resp.status_code == 404
