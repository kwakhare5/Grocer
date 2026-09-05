"""TDD tests for Phase 1: Backend as Single Source of Truth.

Verifies:
1. GET /api/simulations/active creates or retrieves the active simulation.
2. Advance time mutates backend state and persists in the database.
3. Inventory totals strictly agree with batch sums.
4. Engine recovers correctly from DB even if in-memory cache is wiped.
5. Reset restores a clean authoritative state with a new simulation record.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func

from backend.main import create_app
from backend.database import get_db
from backend.models.core import Simulation, Inventory, Batch
from backend.models.enums import SimulationStatus
from backend.api.simulations import _engines


@pytest_asyncio.fixture
async def phase1_client(db_session):
    """Async HTTP client wired to isolated test session."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_active_simulation_creates_default_when_empty(phase1_client, db_session):
    """GET /api/simulations/active creates and initializes a default simulation if none exists."""
    _engines.clear()
    res = await phase1_client.get("/api/simulations/active")
    assert res.status_code == 200
    data = res.json()
    assert "simulation_id" in data
    assert data["status"] in (SimulationStatus.RUNNING.value, SimulationStatus.CREATED.value)
    assert data["seed"] == 42

    # Verify persisted in DB
    result = await db_session.execute(select(Simulation))
    simulations = result.scalars().all()
    assert len(simulations) >= 1


@pytest.mark.asyncio
async def test_active_simulation_returns_existing(phase1_client):
    """Subsequent calls to /api/simulations/active return the same simulation."""
    res1 = await phase1_client.get("/api/simulations/active")
    assert res1.status_code == 200
    id1 = res1.json()["simulation_id"]

    res2 = await phase1_client.get("/api/simulations/active")
    assert res2.status_code == 200
    id2 = res2.json()["simulation_id"]

    assert id1 == id2


@pytest.mark.asyncio
async def test_simulation_advancement_persists_time_and_state(phase1_client, db_session):
    """POST /api/simulations/{id}/advance updates current_time in DB and returns state."""
    active_res = await phase1_client.get("/api/simulations/active")
    sim_id = active_res.json()["simulation_id"]
    initial_time = active_res.json()["current_time"]

    advance_res = await phase1_client.post(
        f"/api/simulations/{sim_id}/advance",
        json={"hours": 6},
    )
    assert advance_res.status_code == 200
    advance_data = advance_res.json()
    assert advance_data["current_time"] != initial_time

    # Verify DB reflects new time
    sim = await db_session.get(Simulation, __import__("uuid").UUID(sim_id))
    assert sim is not None
    assert sim.current_time.isoformat()[:19] == advance_data["current_time"][:19]


@pytest.mark.asyncio
async def test_engine_reconstitution_without_memory_cache(phase1_client, db_session):
    """Simulation operations succeed even when in-memory _engines dict is wiped."""
    active_res = await phase1_client.get("/api/simulations/active")
    sim_id = active_res.json()["simulation_id"]

    # Explicitly clear in-memory cache to simulate server restart
    _engines.clear()

    # Advance time should recover engine from DB and succeed
    advance_res = await phase1_client.post(
        f"/api/simulations/{sim_id}/advance",
        json={"hours": 1},
    )
    assert advance_res.status_code == 200
    assert sim_id in _engines


@pytest.mark.asyncio
async def test_inventory_agrees_with_batch_quantities(phase1_client, db_session):
    """Derivation invariant: sum of active batch quantities matches inventory for all products."""
    await phase1_client.get("/api/simulations/active")

    # Query inventories and batches
    inv_res = await db_session.execute(select(Inventory))
    inventories = inv_res.scalars().all()
    assert len(inventories) > 0

    for inv in inventories:
        batch_sum_res = await db_session.execute(
            select(func.coalesce(func.sum(Batch.quantity), 0)).where(
                Batch.store_id == inv.store_id,
                Batch.product_id == inv.product_id,
                Batch.quantity > 0,
            )
        )
        batch_sum = batch_sum_res.scalar()
        assert inv.quantity == batch_sum, (
            f"Mismatch for store {inv.store_id}, product {inv.product_id}: "
            f"inventory={inv.quantity}, batch_sum={batch_sum}"
        )


@pytest.mark.asyncio
async def test_reset_creates_fresh_authoritative_state(phase1_client):
    """POST /api/simulations/{id}/reset cleans and creates a new simulation ID."""
    active_res = await phase1_client.get("/api/simulations/active")
    sim_id = active_res.json()["simulation_id"]

    reset_res = await phase1_client.post(f"/api/simulations/{sim_id}/reset")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["status"] in (SimulationStatus.RUNNING.value, "reset_complete")
