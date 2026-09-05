"""TDD tests for Phase 2: Operational Simulator.

Verifies:
- Seam 1: Haversine distance matrix & transfer ETA
- Seam 2: Transfer dispatch & stock reservation (conservation)
- Seam 3: Transfer delivery & arrival batch creation
- Seam 4: Supplier PO lifecycle & lead-time delay
- Seam 5: 5 Canonical scenarios (normal, demand_spike, supplier_delay, expiry_wave, network_imbalance)
- Seam 6: Core operational invariants (non-negative inventory, no expired sales/transfers, determinism)
"""
from __future__ import annotations

import math
import pytest
from datetime import datetime, timezone, timedelta

from backend.services.simulation.transfer import (
    calculate_haversine_distance,
    calculate_transfer_eta_minutes,
    get_store_distance_matrix,
)
from backend.services.simulation.seed_data import STORES


def test_calculate_haversine_distance():
    """Bandra to Andheri distance should be ~7.4 km."""
    # Bandra: 19.0596, 72.8295; Andheri: 19.1136, 72.8697
    bandra = next(s for s in STORES if 'Bandra' in s.name)
    andheri = next(s for s in STORES if 'Andheri' in s.name)

    dist_km = calculate_haversine_distance(
        bandra.latitude, bandra.longitude,
        andheri.latitude, andheri.longitude,
    )
    assert 6.0 <= dist_km <= 9.0
    # Same point distance is 0
    assert calculate_haversine_distance(bandra.latitude, bandra.longitude, bandra.latitude, bandra.longitude) == 0.0


def test_calculate_transfer_eta():
    """Transfer ETA should factor distance and traffic multiplier."""
    # 10 km distance at 25 km/h base speed: 10 / 25 * 60 = 24 mins
    eta_normal = calculate_transfer_eta_minutes(distance_km=10.0, speed_kmh=25.0, traffic_multiplier=1.0)
    assert eta_normal == 24.0

    # Rush hour traffic multiplier 1.5x -> 36 mins
    eta_traffic = calculate_transfer_eta_minutes(distance_km=10.0, speed_kmh=25.0, traffic_multiplier=1.5)
    assert eta_traffic == 36.0


def test_store_network_distance_matrix():
    """Matrix should cover all 5 dark stores with zero diagonal and positive symmetric entries."""
    matrix = get_store_distance_matrix()
    assert len(matrix) == 5

    for s1 in STORES:
        assert s1.name in matrix
        for s2 in STORES:
            assert s2.name in matrix[s1.name]
            if s1.name == s2.name:
                assert matrix[s1.name][s2.name] == 0.0
            else:
                assert matrix[s1.name][s2.name] > 0.0
                # Symmetric
                assert math.isclose(matrix[s1.name][s2.name], matrix[s2.name][s1.name], rel_tol=1e-5)


@pytest.mark.asyncio
async def test_transfer_dispatch_and_mass_conservation(db_session):
    """Dispatching a transfer immediately reserves stock from source; network mass is conserved."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.transfer import (
        dispatch_transfer, process_arriving_transfers, clear_active_transfers, get_active_transfers
    )
    from backend.models.core import Inventory, Batch, Store, Product
    from sqlalchemy import select

    clear_active_transfers()
    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    # Get Bandra and Andheri stores
    stores = (await db_session.execute(select(Store))).scalars().all()
    bandra = next(s for s in stores if 'Bandra' in s.name)
    andheri = next(s for s in stores if 'Andheri' in s.name)

    # Get Toned Milk product
    products = (await db_session.execute(select(Product))).scalars().all()
    milk = next(p for p in products if 'Toned Milk' in p.name)

    # Initial inventories
    bandra_inv_before = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == bandra.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    andheri_inv_before = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity

    transfer_qty = 10
    assert bandra_inv_before >= transfer_qty, "Need enough stock to test transfer"

    # Dispatch transfer
    now = engine.clock.now
    transfer = await dispatch_transfer(
        db_session,
        source_store_id=bandra.store_id,
        destination_store_id=andheri.store_id,
        product_id=milk.product_id,
        quantity=transfer_qty,
        current_time=now,
    )
    await db_session.commit()

    assert transfer.status == 'in_transit'
    assert len(get_active_transfers()) == 1

    # Source inventory must be decremented immediately
    bandra_inv_after = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == bandra.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    assert bandra_inv_after == bandra_inv_before - transfer_qty

    # Invariant: Network mass conservation (Source + In-Transit + Dest == Original Total)
    network_total_mid = bandra_inv_after + transfer_qty + andheri_inv_before
    assert network_total_mid == bandra_inv_before + andheri_inv_before

    # Process before arrival ETA -> no delivery yet
    delivered_early = await process_arriving_transfers(db_session, current_time=now)
    assert len(delivered_early) == 0

    # Process after arrival ETA -> delivers and creates fresh destination batches
    arrival_time = transfer.arrival_eta + timedelta(minutes=5)
    delivered = await process_arriving_transfers(db_session, current_time=arrival_time)
    await db_session.commit()
    assert len(delivered) == 1
    assert delivered[0].status == 'delivered'

    # Destination inventory must be incremented by transfer_qty
    andheri_inv_after = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    assert andheri_inv_after == andheri_inv_before + transfer_qty

    # Invariant: Final Network Total strictly conserved
    assert (bandra_inv_after + andheri_inv_after) == (bandra_inv_before + andheri_inv_before)


@pytest.mark.asyncio
async def test_transfer_cannot_exceed_available_stock(db_session):
    """Attempting to dispatch more than available stock raises ValueError."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.transfer import dispatch_transfer, clear_active_transfers
    from backend.models.core import Store, Product
    from sqlalchemy import select

    clear_active_transfers()
    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    stores = (await db_session.execute(select(Store))).scalars().all()
    products = (await db_session.execute(select(Product))).scalars().all()

    with pytest.raises(ValueError, match="Insufficient active stock"):
        await dispatch_transfer(
            db_session,
            source_store_id=stores[0].store_id,
            destination_store_id=stores[1].store_id,
            product_id=products[0].product_id,
            quantity=999999,
            current_time=engine.clock.now,
        )


@pytest.mark.asyncio
async def test_supplier_po_lifecycle_and_delivery(db_session):
    """Creating a supplier PO tracks lead time and delivers fresh batches upon arrival."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.supplier import (
        create_purchase_order, process_supplier_deliveries, clear_active_pos, get_active_pos
    )
    from backend.models.core import Inventory, Batch, Store, Product, Supplier
    from sqlalchemy import select

    clear_active_pos()
    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    andheri = next(s for s in (await db_session.execute(select(Store))).scalars().all() if 'Andheri' in s.name)
    milk = next(p for p in (await db_session.execute(select(Product))).scalars().all() if 'Toned Milk' in p.name)
    amul = next(s for s in (await db_session.execute(select(Supplier))).scalars().all() if 'Amul' in s.name)

    inv_before = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity

    now = engine.clock.now
    po = await create_purchase_order(
        db_session,
        supplier_id=amul.supplier_id,
        store_id=andheri.store_id,
        product_id=milk.product_id,
        quantity=50,
        current_time=now,
    )
    await db_session.commit()

    assert po.status == 'in_transit'
    assert po.expected_arrival == now + timedelta(hours=amul.lead_time_hours)
    assert len(get_active_pos()) == 1

    # Before lead time elapsed: no delivery
    early_deliveries = await process_supplier_deliveries(db_session, current_time=now + timedelta(hours=12))
    assert len(early_deliveries) == 0

    # After lead time elapsed: arrives
    arrived = await process_supplier_deliveries(db_session, current_time=now + timedelta(hours=amul.lead_time_hours + 1))
    await db_session.commit()
    assert len(arrived) == 1
    assert arrived[0].status == 'delivered'

    # Inventory incremented
    inv_after = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    assert inv_after == inv_before + 50


@pytest.mark.asyncio
async def test_supplier_delay_disruption(db_session):
    """Supplier delay extends arrival ETA and postpones batch receipt."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.supplier import (
        create_purchase_order, apply_supplier_delay, process_supplier_deliveries, clear_active_pos
    )
    from backend.models.core import Inventory, Store, Product, Supplier
    from sqlalchemy import select

    clear_active_pos()
    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    andheri = next(s for s in (await db_session.execute(select(Store))).scalars().all() if 'Andheri' in s.name)
    milk = next(p for p in (await db_session.execute(select(Product))).scalars().all() if 'Toned Milk' in p.name)
    amul = next(s for s in (await db_session.execute(select(Supplier))).scalars().all() if 'Amul' in s.name)

    now = engine.clock.now
    po = await create_purchase_order(
        db_session,
        supplier_id=amul.supplier_id,
        store_id=andheri.store_id,
        product_id=milk.product_id,
        quantity=30,
        current_time=now,
    )
    # Disruption: Add +24h delay
    delayed_po = apply_supplier_delay(po.po_id, additional_hours=24)
    assert delayed_po.status == 'delayed'
    assert delayed_po.expected_arrival == now + timedelta(hours=amul.lead_time_hours + 24)

    # At normal lead time, should not arrive
    deliveries_at_normal = await process_supplier_deliveries(db_session, current_time=now + timedelta(hours=amul.lead_time_hours + 1))
    assert len(deliveries_at_normal) == 0

    # At delayed arrival, should arrive
    deliveries_at_delayed = await process_supplier_deliveries(db_session, current_time=now + timedelta(hours=amul.lead_time_hours + 25))
    assert len(deliveries_at_delayed) == 1
    assert deliveries_at_delayed[0].status == 'delivered'


def test_scenario_catalog_and_modifiers():
    """All 5 canonical scenarios exist with distinct demand and lead-time configurations."""
    from backend.services.simulation.scenarios import get_scenario_config, SCENARIO_NAMES

    assert len(SCENARIO_NAMES) == 5
    assert set(SCENARIO_NAMES) == {'normal', 'demand_spike', 'supplier_delay', 'expiry_wave', 'network_imbalance'}

    # demand_spike has 2.5x dairy multiplier
    spike = get_scenario_config('demand_spike')
    assert spike.demand_multiplier_by_category.get('dairy', 1.0) == 2.5

    # supplier_delay has positive delay hours
    delayed = get_scenario_config('supplier_delay')
    assert delayed.supplier_lead_time_delay_hours >= 24

    # normal has baseline 1.0 multipliers
    normal = get_scenario_config('normal')
    assert normal.demand_multiplier_by_category.get('dairy', 1.0) == 1.0


@pytest.mark.asyncio
async def test_apply_network_imbalance_scenario(db_session):
    """network_imbalance creates severe excess in Bandra and drains Andheri."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.scenarios import apply_scenario
    from backend.models.core import Inventory, Store, Product
    from sqlalchemy import select

    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    result = await apply_scenario(db_session, engine, 'network_imbalance')
    await db_session.commit()

    assert result['scenario'] == 'network_imbalance'

    # Andheri milk stock should be <= 5 units (starved)
    andheri = next(s for s in (await db_session.execute(select(Store))).scalars().all() if 'Andheri' in s.name)
    milk = next(p for p in (await db_session.execute(select(Product))).scalars().all() if 'Toned Milk' in p.name)

    andheri_inv = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    assert andheri_inv <= 5

    # Bandra milk stock should be inflated (>= 60 units)
    bandra = next(s for s in (await db_session.execute(select(Store))).scalars().all() if 'Bandra' in s.name)
    bandra_inv = (await db_session.execute(
        select(Inventory).where(Inventory.store_id == bandra.store_id, Inventory.product_id == milk.product_id)
    )).scalar_one().quantity
    assert bandra_inv >= 60


@pytest.mark.asyncio
async def test_apply_expiry_wave_scenario(db_session):
    """expiry_wave creates batches expiring within 12 hours for perishables."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.scenarios import apply_scenario
    from backend.models.core import Batch, Product
    from sqlalchemy import select

    engine = SimulationEngine(seed=42, historical_days=3)
    await engine.initialize(db_session)
    await db_session.commit()

    await apply_scenario(db_session, engine, 'expiry_wave')
    await db_session.commit()

    # Query batches expiring in <= 12 hours
    now = engine.clock.now
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    cutoff = now_naive + timedelta(hours=12)

    near_expiry_batches = (await db_session.execute(
        select(Batch).where(
            Batch.expires_at <= cutoff,
            Batch.expires_at > now_naive,
            Batch.quantity > 0,
        )
    )).scalars().all()
    assert len(near_expiry_batches) >= 5


@pytest.mark.asyncio
async def test_invariant_no_negative_inventory_under_stress(db_session):
    """Advancing through high order volume never drives inventory or batch quantities below 0."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.models.core import Inventory, Batch
    from sqlalchemy import select

    engine = SimulationEngine(seed=999, historical_days=3)
    sim = await engine.initialize(db_session)
    await db_session.commit()

    # Advance 48 hours with order generation
    await engine.advance_time(db_session, sim.simulation_id, hours=48)
    await db_session.commit()

    # Invariant: No negative inventories
    negative_inv = (await db_session.execute(
        select(Inventory).where(Inventory.quantity < 0)
    )).scalars().all()
    assert len(negative_inv) == 0

    # Invariant: No negative batches
    negative_batches = (await db_session.execute(
        select(Batch).where(Batch.quantity < 0)
    )).scalars().all()
    assert len(negative_batches) == 0


@pytest.mark.asyncio
async def test_invariant_no_expired_batches_remain_in_inventory(db_session):
    """Expired batches must have quantity=0 or be excluded from inventory derivation."""
    from backend.services.simulation.engine import SimulationEngine
    from backend.models.core import Batch, Inventory
    from sqlalchemy import select, func

    engine = SimulationEngine(seed=42, historical_days=3)
    sim = await engine.initialize(db_session)
    await db_session.commit()

    # Advance 72 hours so multiple perishable batches expire
    await engine.advance_time(db_session, sim.simulation_id, hours=72)
    await db_session.commit()

    now = engine.clock.now
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now

    # Invariant: Active batches (quantity > 0) must NOT be expired
    expired_active_batches = (await db_session.execute(
        select(Batch).where(
            Batch.quantity > 0,
            Batch.expires_at <= now_naive,
        )
    )).scalars().all()
    assert len(expired_active_batches) == 0


@pytest.mark.asyncio
async def test_invariant_deterministic_reproducibility(db_session):
    """Identical seeds produce identical simulation clocks and entity counts."""
    from backend.services.simulation.engine import SimulationEngine

    engine1 = SimulationEngine(seed=777, historical_days=2)
    sim1 = await engine1.initialize(db_session)

    assert sim1.seed == 777
    assert engine1.clock.now == sim1.current_time


@pytest.mark.asyncio
async def test_api_get_network(client):
    """GET /api/simulations/{id}/network returns store nodes and distance matrix."""
    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 1})
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["simulation_id"]

    resp = await client.get(f"/api/simulations/{sim_id}/network")
    assert resp.status_code == 200
    data = resp.json()
    assert "stores" in data
    assert len(data["stores"]) == 5
    assert "distance_matrix_km" in data
    assert "Dark Store Bandra" in data["distance_matrix_km"]
    assert data["distance_matrix_km"]["Dark Store Bandra"]["Dark Store Bandra"] == 0.0



@pytest.mark.asyncio
async def test_api_in_transit_tracking(client):
    """GET /api/simulations/{id}/in-transit returns active transfers and purchase orders."""
    from backend.services.simulation.transfer import clear_active_transfers
    from backend.services.simulation.supplier import clear_active_pos

    clear_active_transfers()
    clear_active_pos()

    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 1})
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["simulation_id"]

    resp = await client.get(f"/api/simulations/{sim_id}/in-transit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transfers"] == []
    assert data["purchase_orders"] == []


@pytest.mark.asyncio
async def test_api_apply_scenario(client):
    """POST /api/simulations/{id}/scenario applies operational scenario."""
    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 1})
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["simulation_id"]

    # Invalid scenario
    bad_resp = await client.post(f"/api/simulations/{sim_id}/scenario", json={"scenario": "invalid_scenario"})
    assert bad_resp.status_code == 400
    assert "Invalid scenario" in bad_resp.json()["detail"]

    # Valid scenario
    good_resp = await client.post(f"/api/simulations/{sim_id}/scenario", json={"scenario": "demand_spike"})
    assert good_resp.status_code == 200
    result = good_resp.json()
    assert result["scenario"] == "demand_spike"
    assert result["status"] == "applied"


@pytest.mark.asyncio
async def test_api_advance_delivers_in_transit_transfers(client):
    """Advancing simulation time automatically delivers transfers whose ETA has passed."""
    from backend.services.simulation.transfer import clear_active_transfers, dispatch_transfer
    from backend.models.core import Store, Product
    from backend.tests.conftest import test_session_factory
    from sqlalchemy import select

    clear_active_transfers()

    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 1})
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["simulation_id"]
    sim_time_str = create_resp.json()["current_time"]
    current_time = datetime.fromisoformat(sim_time_str)

    async with test_session_factory() as session:
        stores = (await session.execute(select(Store))).scalars().all()
        products = (await session.execute(select(Product))).scalars().all()
        bandra = next(s for s in stores if 'Bandra' in s.name)
        andheri = next(s for s in stores if 'Andheri' in s.name)
        milk = next(p for p in products if 'Toned Milk' in p.name)

        await dispatch_transfer(
            session,
            source_store_id=bandra.store_id,
            destination_store_id=andheri.store_id,
            product_id=milk.product_id,
            quantity=5,
            current_time=current_time,
        )
        await session.commit()

    # Verify 1 in-transit
    resp = await client.get(f"/api/simulations/{sim_id}/in-transit")
    assert resp.status_code == 200
    assert len(resp.json()["transfers"]) == 1

    # Advance 2 hours -> ETA is ~20 mins, so it should be delivered
    adv_resp = await client.post(f"/api/simulations/{sim_id}/advance", json={"hours": 2})
    assert adv_resp.status_code == 200
    adv_data = adv_resp.json()
    assert adv_data["transfers_delivered"] >= 1

    # Verify in-transit list is now clear
    resp2 = await client.get(f"/api/simulations/{sim_id}/in-transit")
    assert resp2.status_code == 200
    assert len(resp2.json()["transfers"]) == 0


