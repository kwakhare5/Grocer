"""Tests for Phase 9 Customer / WhatsApp replenishment endpoints (Spec §22 & §32.8)."""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.main import create_app
from backend.database import get_db
from backend.models.core import Customer, Store, Product, Inventory, Order, OrderItem
from backend.services.simulation.engine import SimulationEngine


@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Seed database with simulation base data."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_customers(seeded_db, db_session):
    """GET /api/customers should list all seeded customers."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 20
        first_cust = data[0]
        assert "customer_id" in first_cust
        assert "name" in first_cust
        assert "home_store_name" in first_cust
        assert "fill_pct" in first_cust


@pytest.mark.asyncio
async def test_get_customer_detail(seeded_db, db_session):
    """GET /api/customers/{id} should return customer profile and pantry staples."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/customers/{cust.customer_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] == str(cust.customer_id)
        assert data["name"] == cust.name
        assert len(data["staples"]) > 0


@pytest.mark.asyncio
async def test_get_customer_detail_not_found(db_session):
    """GET /api/customers/{id} should return 404 for unknown customer."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/customers/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_customer_messages(seeded_db, db_session):
    """GET /api/customers/{id}/messages should return proactive alert."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/customers/{cust.customer_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) > 0
        assert data["messages"][0]["sender"] == "bot"


@pytest.mark.asyncio
async def test_send_customer_message(seeded_db, db_session):
    """POST /api/customers/{id}/messages should process user conversational reply."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/customers/{cust.customer_id}/messages",
            json={"message": "Add bread"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Bread" in data["reply"]
        assert data["stage"] == "breakdown"


@pytest.mark.asyncio
async def test_reorder_customer(seeded_db, db_session):
    """POST /api/customers/{id}/reorder should deduct inventory and create order."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    # Check store inventory before reorder
    inv_stmt = select(Inventory).where(Inventory.store_id == cust.home_store_id).limit(1)
    inv_before = (await db_session.execute(inv_stmt)).scalar_one()
    initial_qty = inv_before.quantity

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/customers/{cust.customer_id}/reorder",
            json={
                "items": [
                    {"product_id": str(inv_before.product_id), "quantity": 2}
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["pantry_restored"] is True
        assert data["total_amount"] > 0

    # Verify inventory was deducted in DB
    await db_session.refresh(inv_before)
    assert inv_before.quantity == max(0, initial_qty - 2)


@pytest.mark.asyncio
async def test_remind_customer(seeded_db, db_session):
    """POST /api/customers/{id}/remind should schedule reminder."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/customers/{cust.customer_id}/remind",
            json={"delay_hours": 24},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["delay_hours"] == 24


@pytest.mark.asyncio
async def test_skip_customer(seeded_db, db_session):
    """POST /api/customers/{id}/skip should record skip."""
    cust_stmt = select(Customer).limit(1)
    cust = (await db_session.execute(cust_stmt)).scalar_one()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/customers/{cust.customer_id}/skip",
            json={"reason": "stocked_up"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
