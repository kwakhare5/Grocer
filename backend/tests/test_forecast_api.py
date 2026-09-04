"""TDD API tests for Phase 3 endpoints.

Seams under test:
1. GET  /api/stores                       — returns 5 seeded stores
2. GET  /api/stores/{id}                  — returns single store or 404
3. GET  /api/stores/{id}/inventory        — returns inventory + batches structure
4. GET  /api/stores/{id}/forecasts        — returns forecast list for store
5. GET  /api/products                     — returns 25 seeded products
6. GET  /api/products/{id}                — returns single product or 404
7. POST /api/forecasts/generate           — generates forecasts, returns count
8. GET  /api/forecasts                    — lists stored forecasts
9. GET  /api/forecasts?store_id=<id>      — filters by store
10. GET /api/forecasts?model_name=...     — filters by model
11. GET /api/forecasts/evaluate           — returns evaluation per model
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.database import get_db
from backend.services.simulation.engine import SimulationEngine


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Seed simulator data and return the db session."""
    engine = SimulationEngine(seed=42, historical_days=7)
    await engine.initialize(db_session)
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


# ── Store endpoints ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_stores_returns_five_stores(client):
    """GET /api/stores returns all 5 seeded dark stores."""
    resp = await client.get("/api/stores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    names = [s["name"] for s in data]
    assert any("Andheri" in n for n in names)


@pytest.mark.asyncio
async def test_list_stores_has_required_fields(client):
    """Each store object has the required schema fields."""
    resp = await client.get("/api/stores")
    assert resp.status_code == 200
    for store in resp.json():
        assert "store_id" in store
        assert "name" in store
        assert "latitude" in store
        assert "longitude" in store
        assert "operating_status" in store


@pytest.mark.asyncio
async def test_get_store_by_id(client, seeded_db):
    """GET /api/stores/{id} returns the correct store."""
    # Use the first seeded store
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    resp = await client.get(f"/api/stores/{store.store_id}")
    assert resp.status_code == 200
    assert resp.json()["store_id"] == str(store.store_id)


@pytest.mark.asyncio
async def test_get_store_not_found(client):
    """GET /api/stores/{random_uuid} returns 404."""
    resp = await client.get(f"/api/stores/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_store_inventory_structure(client, seeded_db):
    """GET /api/stores/{id}/inventory returns correct structure."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    resp = await client.get(f"/api/stores/{store.store_id}/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert "store_id" in data
    assert "inventory" in data
    assert "batches" in data
    assert isinstance(data["inventory"], list)
    assert isinstance(data["batches"], list)


@pytest.mark.asyncio
async def test_get_store_inventory_has_products(client, seeded_db):
    """Inventory response has product entries with correct fields."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    resp = await client.get(f"/api/stores/{store.store_id}/inventory")
    assert resp.status_code == 200
    inv = resp.json()["inventory"]
    assert len(inv) > 0
    item = inv[0]
    assert "product_id" in item
    assert "product_name" in item
    assert "quantity" in item
    assert item["quantity"] >= 0


@pytest.mark.asyncio
async def test_get_store_forecasts_empty_before_generation(client, seeded_db):
    """GET /api/stores/{id}/forecasts returns empty list before any forecasts generated."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    resp = await client.get(f"/api/stores/{store.store_id}/forecasts")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Product endpoints ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_products_returns_25(client):
    """GET /api/products returns all 25 seeded products."""
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    assert len(resp.json()) == 25


@pytest.mark.asyncio
async def test_list_products_has_required_fields(client):
    """Each product has the required schema fields."""
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    for p in resp.json():
        assert "product_id" in p
        assert "name" in p
        assert "category" in p
        assert "shelf_life_hours" in p
        assert "base_price" in p


@pytest.mark.asyncio
async def test_get_product_by_id(client, seeded_db):
    """GET /api/products/{id} returns the correct product."""
    from sqlalchemy import select
    from backend.models.core import Product
    result = await seeded_db.execute(select(Product).limit(1))
    product = result.scalars().first()

    resp = await client.get(f"/api/products/{product.product_id}")
    assert resp.status_code == 200
    assert resp.json()["product_id"] == str(product.product_id)
    assert "supplier_id" in resp.json()


@pytest.mark.asyncio
async def test_get_product_not_found(client):
    """GET /api/products/{random_uuid} returns 404."""
    resp = await client.get(f"/api/products/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Forecast endpoints ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_forecasts_returns_count(client):
    """POST /api/forecasts/generate returns forecasts_generated count > 0."""
    resp = await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "forecasts_generated" in data
    assert data["forecasts_generated"] > 0
    assert data["horizon_hours"] == 24


@pytest.mark.asyncio
async def test_list_forecasts_returns_generated_rows(client):
    """GET /api/forecasts returns forecasts after generation."""
    # Generate first
    gen_resp = await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    assert gen_resp.status_code == 200
    count = gen_resp.json()["forecasts_generated"]

    # Then list
    list_resp = await client.get("/api/forecasts")
    assert list_resp.status_code == 200
    forecasts = list_resp.json()
    assert len(forecasts) == count


@pytest.mark.asyncio
async def test_forecast_schema_fields(client):
    """Generated forecast rows have all required schema fields."""
    await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    resp = await client.get("/api/forecasts")
    assert resp.status_code == 200
    for fc in resp.json():
        assert "forecast_id" in fc
        assert "store_id" in fc
        assert "product_id" in fc
        assert "predicted_demand" in fc
        assert "confidence" in fc
        assert "model_name" in fc
        assert 0.0 <= fc["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_filter_forecasts_by_store(client, seeded_db):
    """GET /api/forecasts?store_id=X returns only forecasts for that store."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    await client.post("/api/forecasts/generate", json={"horizon_hours": 24})

    resp = await client.get(f"/api/forecasts?store_id={store.store_id}")
    assert resp.status_code == 200
    for fc in resp.json():
        assert fc["store_id"] == str(store.store_id)


@pytest.mark.asyncio
async def test_filter_forecasts_by_model(client):
    """GET /api/forecasts?model_name=baseline returns only baseline forecasts."""
    await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    resp = await client.get("/api/forecasts?model_name=baseline")
    assert resp.status_code == 200
    for fc in resp.json():
        assert fc["model_name"] == "baseline"


@pytest.mark.asyncio
async def test_evaluate_forecasts_returns_models(client):
    """GET /api/forecasts/evaluate returns evaluation rows for each model."""
    await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    resp = await client.get("/api/forecasts/evaluate")
    assert resp.status_code == 200
    evals = resp.json()
    assert len(evals) > 0
    for e in evals:
        assert "model_name" in e
        assert "mae" in e
        assert "rmse" in e
        assert "mape" in e
        assert "n_samples" in e
        assert e["mae"] >= 0


@pytest.mark.asyncio
async def test_store_forecasts_populated_after_generation(client, seeded_db):
    """GET /api/stores/{id}/forecasts returns items after generation."""
    from sqlalchemy import select
    from backend.models.core import Store
    result = await seeded_db.execute(select(Store).limit(1))
    store = result.scalars().first()

    await client.post("/api/forecasts/generate", json={"horizon_hours": 24})
    resp = await client.get(f"/api/stores/{store.store_id}/forecasts")
    assert resp.status_code == 200
    assert len(resp.json()) > 0
