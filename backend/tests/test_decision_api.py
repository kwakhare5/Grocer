"""TDD API tests for Phase 5 Recommendation endpoints (spec sections 17, 18).

Test seams:
1.  GET  /api/recommendations                     -- returns empty list initially
2.  POST /api/recommendations/evaluate/{risk_id}  -- returns 404 for unknown risk
3.  POST /api/recommendations/evaluate/{risk_id}  -- creates recommendation for known risk
4.  GET  /api/recommendations                     -- returns recommendation after evaluate
5.  GET  /api/recommendations/{id}                -- returns specific recommendation
6.  GET  /api/recommendations/{random_uuid}       -- returns 404
7.  GET  /api/recommendations?risk_id=<id>        -- filters by risk_id
8.  GET  /api/recommendations?status=pending      -- filters by status
9.  POST /api/recommendations/{id}/approve        -- sets status to approved
10. POST /api/recommendations/{id}/reject         -- sets status to rejected
11. POST /api/recommendations/{random_uuid}/approve -- returns 404
12. POST /api/recommendations/{random_uuid}/reject  -- returns 404
13. POST ...evaluate -- recommendation action_type is one of the four valid types
14. POST ...evaluate -- reason_codes is non-empty list
15. POST ...evaluate -- confidence is between 0 and 1
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
from backend.services.risk.engine import RiskEngine


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Seed simulator, run forecasting, run risk evaluation, return db."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    return db_session


@pytest_asyncio.fixture
async def client(seeded_db):
    """HTTP client wired to the seeded + risk-evaluated test DB."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def first_risk_id(seeded_db):
    """Return the ID of the first active risk from the seeded DB."""
    from sqlalchemy import select
    from backend.models.core import Risk
    result = await seeded_db.execute(select(Risk).limit(1))
    risk = result.scalar_one_or_none()
    assert risk is not None, "Need at least one risk to test decision engine"
    return risk.risk_id


# ── Tests ───────────────────────────────────────────────────────────────────

async def test_list_recommendations_initially_empty(client):
    """1. Empty list before any evaluate call."""
    resp = await client.get("/api/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_evaluate_returns_404_for_unknown_risk(client):
    """2. Unknown risk_id -> 404."""
    resp = await client.post(f"/api/recommendations/evaluate/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_evaluate_creates_recommendation_for_known_risk(client, first_risk_id):
    """3. Evaluate a known risk -> 200 with valid recommendation."""
    resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendation_id" in data
    assert data["status"] == "pending"


async def test_list_returns_recommendation_after_evaluate(client, first_risk_id):
    """4. After evaluate, list returns the new recommendation."""
    await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    resp = await client.get("/api/recommendations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_recommendation_by_id(client, first_risk_id):
    """5. GET /api/recommendations/{id} returns correct recommendation."""
    eval_resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    rec_id = eval_resp.json()["recommendation_id"]
    resp = await client.get(f"/api/recommendations/{rec_id}")
    assert resp.status_code == 200
    assert resp.json()["recommendation_id"] == rec_id


async def test_get_recommendation_returns_404_for_unknown(client):
    """6. Unknown recommendation_id -> 404."""
    resp = await client.get(f"/api/recommendations/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_filter_by_risk_id(client, first_risk_id):
    """7. ?risk_id=<id> filters correctly."""
    await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    resp = await client.get(f"/api/recommendations?risk_id={first_risk_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["risk_id"] == str(first_risk_id) for r in data)


async def test_filter_by_status_pending(client, first_risk_id):
    """8. ?status=pending returns pending recommendations."""
    await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    resp = await client.get("/api/recommendations?status=pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(r["status"] == "pending" for r in data)


async def test_approve_recommendation(client, first_risk_id):
    """9. Approve sets status to approved."""
    eval_resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    rec_id = eval_resp.json()["recommendation_id"]
    resp = await client.post(f"/api/recommendations/{rec_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_reject_recommendation(client, first_risk_id):
    """10. Reject sets status to rejected."""
    eval_resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    rec_id = eval_resp.json()["recommendation_id"]
    resp = await client.post(f"/api/recommendations/{rec_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


async def test_approve_unknown_recommendation_returns_404(client):
    """11. Approve on unknown id -> 404."""
    resp = await client.post(f"/api/recommendations/{uuid.uuid4()}/approve")
    assert resp.status_code == 404


async def test_reject_unknown_recommendation_returns_404(client):
    """12. Reject on unknown id -> 404."""
    resp = await client.post(f"/api/recommendations/{uuid.uuid4()}/reject")
    assert resp.status_code == 404


async def test_evaluate_action_type_is_valid(client, first_risk_id):
    """13. action_type must be one of the four canonical types."""
    resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] in {"transfer", "reorder", "discount", "hold"}


async def test_evaluate_reason_codes_non_empty(client, first_risk_id):
    """14. reason_codes must be a non-empty list."""
    resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    assert resp.status_code == 200
    codes = resp.json()["reason_codes"]
    assert isinstance(codes, list)
    assert len(codes) > 0


async def test_evaluate_confidence_bounded(client, first_risk_id):
    """15. confidence must be in [0, 1]."""
    eval_resp = await client.post(f"/api/recommendations/evaluate/{first_risk_id}")
    rec_id = eval_resp.json()["recommendation_id"]
    resp = await client.get(f"/api/recommendations/{rec_id}")
    confidence = resp.json()["confidence"]
    assert 0.0 <= confidence <= 1.0
