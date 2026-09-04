import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import (
    Store, Product, Customer, Supplier, Order, OrderItem,
    Inventory, Batch, Forecast, Risk, Recommendation, Action,
    Event, Simulation, Scenario,
)
from backend.models.enums import (
    StoreStatus, ProductCategory, OrderStatus, SupplierStatus,
    RiskType, RiskSeverity, ActionType, ActionStatus,
    RecommendationStatus, SimulationStatus, RiskStatus,
)


@pytest.mark.asyncio
async def test_create_store(db_session: AsyncSession) -> None:
    """Should persist a Store with all required fields."""
    store = Store(
        store_id=uuid.uuid4(),
        name='Dark Store Alpha',
        latitude=19.076,
        longitude=72.877,
        operating_status=StoreStatus.ACTIVE,
    )
    db_session.add(store)
    await db_session.commit()

    result = await db_session.execute(select(Store))
    stores = result.scalars().all()
    assert len(stores) == 1
    assert stores[0].name == 'Dark Store Alpha'
    assert stores[0].operating_status == StoreStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_supplier(db_session: AsyncSession) -> None:
    """Should persist a Supplier."""
    supplier = Supplier(
        supplier_id=uuid.uuid4(),
        name='FreshCo Dairy',
        lead_time_hours=24,
        status=SupplierStatus.ACTIVE,
    )
    db_session.add(supplier)
    await db_session.commit()

    result = await db_session.execute(select(Supplier))
    suppliers = result.scalars().all()
    assert len(suppliers) == 1
    assert suppliers[0].lead_time_hours == 24


@pytest.mark.asyncio
async def test_create_product_with_supplier_fk(db_session: AsyncSession) -> None:
    """Should persist a Product linked to a Supplier."""
    supplier_id = uuid.uuid4()
    supplier = Supplier(
        supplier_id=supplier_id,
        name='BakeMaster',
        lead_time_hours=12,
        status=SupplierStatus.ACTIVE,
    )
    db_session.add(supplier)
    await db_session.flush()

    product = Product(
        product_id=uuid.uuid4(),
        name='Whole Wheat Bread 400g',
        category=ProductCategory.BAKERY,
        unit='loaf',
        shelf_life_hours=72,
        base_price=50.00,
        supplier_id=supplier_id,
    )
    db_session.add(product)
    await db_session.commit()

    result = await db_session.execute(select(Product))
    products = result.scalars().all()
    assert len(products) == 1
    assert products[0].category == ProductCategory.BAKERY


@pytest.mark.asyncio
async def test_create_customer_with_store_fk(db_session: AsyncSession) -> None:
    """Should persist a Customer linked to a home Store."""
    store_id = uuid.uuid4()
    store = Store(
        store_id=store_id,
        name='Dark Store Beta',
        latitude=19.1,
        longitude=72.9,
        operating_status=StoreStatus.ACTIVE,
    )
    db_session.add(store)
    await db_session.flush()

    customer = Customer(
        customer_id=uuid.uuid4(),
        name='Household Alpha',
        home_store_id=store_id,
    )
    db_session.add(customer)
    await db_session.commit()

    result = await db_session.execute(select(Customer))
    customers = result.scalars().all()
    assert len(customers) == 1
    assert customers[0].name == 'Household Alpha'


@pytest.mark.asyncio
async def test_create_order_with_items(db_session: AsyncSession) -> None:
    """Should persist an Order with OrderItems."""
    store_id = uuid.uuid4()
    store = Store(store_id=store_id, name='Store C', latitude=19.0, longitude=72.8, operating_status=StoreStatus.ACTIVE)
    db_session.add(store)

    customer_id = uuid.uuid4()
    customer = Customer(customer_id=customer_id, name='Test Customer', home_store_id=store_id)
    db_session.add(customer)

    supplier_id = uuid.uuid4()
    supplier = Supplier(supplier_id=supplier_id, name='Supplier X', lead_time_hours=6, status=SupplierStatus.ACTIVE)
    db_session.add(supplier)

    product_id = uuid.uuid4()
    product = Product(product_id=product_id, name='Milk 1L', category=ProductCategory.DAIRY, unit='L', shelf_life_hours=48, base_price=66.00, supplier_id=supplier_id)
    db_session.add(product)
    await db_session.flush()

    order_id = uuid.uuid4()
    order = Order(order_id=order_id, customer_id=customer_id, store_id=store_id, created_at=datetime.now(timezone.utc), status=OrderStatus.CONFIRMED)
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(id=uuid.uuid4(), order_id=order_id, product_id=product_id, quantity=2, price=66.00)
    db_session.add(item)
    await db_session.commit()

    result = await db_session.execute(select(OrderItem))
    items = result.scalars().all()
    assert len(items) == 1
    assert items[0].quantity == 2


@pytest.mark.asyncio
async def test_create_batch(db_session: AsyncSession) -> None:
    """Should persist a Batch with expiry tracking."""
    store_id = uuid.uuid4()
    store = Store(store_id=store_id, name='Store D', latitude=19.0, longitude=72.8, operating_status=StoreStatus.ACTIVE)
    db_session.add(store)

    supplier_id = uuid.uuid4()
    supplier = Supplier(supplier_id=supplier_id, name='Sup', lead_time_hours=6, status=SupplierStatus.ACTIVE)
    db_session.add(supplier)

    product_id = uuid.uuid4()
    product = Product(product_id=product_id, name='Tomatoes 500g', category=ProductCategory.PRODUCE, unit='kg', shelf_life_hours=96, base_price=32.00, supplier_id=supplier_id)
    db_session.add(product)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    batch = Batch(
        batch_id=uuid.uuid4(),
        store_id=store_id,
        product_id=product_id,
        quantity=45,
        received_at=now,
        expires_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    db_session.add(batch)
    await db_session.commit()

    result = await db_session.execute(select(Batch))
    batches = result.scalars().all()
    assert len(batches) == 1
    assert batches[0].quantity == 45


@pytest.mark.asyncio
async def test_create_simulation_and_scenario(db_session: AsyncSession) -> None:
    """Should persist Simulation and Scenario."""
    scenario = Scenario(
        scenario_id=uuid.uuid4(),
        name='Hero Transfer',
        description='Demand spike at Store 04, transfer from Store 02',
        configuration={'trigger': 'demand_spike', 'target_store': 4},
    )
    db_session.add(scenario)
    await db_session.flush()

    sim = Simulation(
        simulation_id=uuid.uuid4(),
        scenario_id=scenario.scenario_id,
        seed=48291,
        current_time=datetime.now(timezone.utc),
        status=SimulationStatus.CREATED,
        configuration={'stores': 5, 'products': 25},
    )
    db_session.add(sim)
    await db_session.commit()

    result = await db_session.execute(select(Simulation))
    sims = result.scalars().all()
    assert len(sims) == 1
    assert sims[0].seed == 48291


@pytest.mark.asyncio
async def test_create_event(db_session: AsyncSession) -> None:
    """Should persist an Event with JSON payload."""
    event = Event(
        event_id=uuid.uuid4(),
        event_type='ORDER_CREATED',
        timestamp=datetime.now(timezone.utc),
        entity_type='order',
        entity_id=uuid.uuid4(),
        payload={'order_total': 116.00, 'items': 2},
    )
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(Event))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == 'ORDER_CREATED'
    assert events[0].payload['items'] == 2
