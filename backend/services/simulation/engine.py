"""GROCER v2 Simulation Engine.

Handles deterministic simulation: time control, seeding,
order generation, inventory/batch lifecycle.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import (
    Store, Product, Customer, Supplier, Order, OrderItem,
    Inventory, Batch, Simulation, Scenario, Event,
)
from backend.models.enums import (
    StoreStatus, ProductCategory, OrderStatus, SupplierStatus,
    SimulationStatus,
)
from backend.services.simulation.seed_data import (
    STORES, SUPPLIERS, PRODUCTS, CUSTOMERS,
    SeedProduct, SeedCustomer,
)
from backend.services.simulation.transfer import process_arriving_transfers, clear_active_transfers
from backend.services.simulation.supplier import process_supplier_deliveries, clear_active_pos



class SimulationClock:
    """Manages simulated time for a simulation instance."""

    def __init__(self, start_time: datetime, seed: int = 42):
        self._current_time = start_time
        self._start_time = start_time
        self._seed = seed

    @property
    def now(self) -> datetime:
        return self._current_time

    @property
    def start_time(self) -> datetime:
        return self._start_time

    def advance(self, hours: int) -> datetime:
        """Advance simulation time by N hours. Returns new current time."""
        self._current_time += timedelta(hours=hours)
        return self._current_time

    def reset(self) -> datetime:
        """Reset clock to start time."""
        self._current_time = self._start_time
        return self._current_time


class SimulationEngine:
    """Core simulation engine for GROCER v2.

    Handles:
    - Database seeding (stores, suppliers, products, customers)
    - Initial inventory and batch creation
    - Deterministic order generation over historical days
    - Time advancement with inventory depletion and batch expiry
    - Reset capability
    """

    def __init__(self, seed: int = 42, historical_days: int = 60):
        self.seed = seed
        self.historical_days = historical_days
        self.rng = random.Random(seed)
        self.clock: SimulationClock | None = None
        self._supplier_map: dict[str, uuid.UUID] = {}
        self._store_map: dict[str, uuid.UUID] = {}
        self._product_list: list[SeedProduct] = []

    async def initialize(self, db: AsyncSession) -> Simulation:
        """Seed all base data and generate historical orders.
        
        Returns the created Simulation ORM object.
        """
        # 1. Calculate timeline
        sim_start = datetime.now(timezone.utc) - timedelta(days=self.historical_days)
        self.clock = SimulationClock(sim_start, self.seed)

        # 2. Seed stores, suppliers, products, customers
        await self._seed_base_data(db)

        # 3. Create initial inventory and batches
        await self._create_initial_inventory(db)

        # 4. Generate historical orders day by day
        await self._generate_historical_orders(db)

        # 5. Advance clock to "now" (end of historical period)
        self.clock.advance(self.historical_days * 24)

        # 6. Ensure active batches exist at simulation present time
        await self._expire_batches(db, self.clock.now)
        await self._restock_inventory(db, self.clock.now)

        # 7. Create Simulation record
        simulation = Simulation(
            simulation_id=uuid.uuid4(),
            seed=self.seed,
            current_time=self.clock.now,
            status=SimulationStatus.CREATED,
            configuration={
                'historical_days': self.historical_days,
                'stores': len(STORES),
                'products': len(PRODUCTS),
                'customers': len(CUSTOMERS),
            },
        )
        db.add(simulation)
        await db.commit()
        return simulation

    async def advance_time(self, db: AsyncSession, simulation_id: uuid.UUID, hours: int) -> dict[str, Any]:
        """Advance simulation time, generate new orders, handle batch expiry.
        
        Returns summary of what happened during the time advance.
        """
        if self.clock is None:
            raise RuntimeError('Simulation not initialized. Call initialize() first.')

        old_time = self.clock.now
        new_time = self.clock.advance(hours)

        # Generate orders for the advanced period
        orders_created = await self._generate_orders_for_period(db, old_time, new_time)

        # Handle batch expiry
        expired_batches = await self._expire_batches(db, new_time)

        # Process arriving store transfers & supplier PO deliveries
        delivered_transfers = await process_arriving_transfers(db, new_time)
        delivered_pos = await process_supplier_deliveries(db, new_time)

        # Update simulation record
        sim = await db.get(Simulation, simulation_id)
        if sim:
            sim.current_time = new_time
            sim.status = SimulationStatus.RUNNING

        # Create time advance event
        event = Event(
            event_id=uuid.uuid4(),
            event_type='TIME_ADVANCED',
            timestamp=new_time,
            entity_type='simulation',
            entity_id=simulation_id,
            payload={
                'from': old_time.isoformat(),
                'to': new_time.isoformat(),
                'hours': hours,
                'orders_created': orders_created,
                'batches_expired': expired_batches,
                'transfers_delivered': len(delivered_transfers),
                'pos_delivered': len(delivered_pos),
            },
        )
        db.add(event)
        await db.commit()

        return {
            'current_time': new_time.isoformat(),
            'hours_advanced': hours,
            'orders_created': orders_created,
            'batches_expired': expired_batches,
            'transfers_delivered': len(delivered_transfers),
            'pos_delivered': len(delivered_pos),
        }

    async def reset(self, db: AsyncSession, simulation_id: uuid.UUID) -> dict[str, Any]:
        """Reset simulation: clear generated data, re-seed, restart clock."""
        # Delete in dependency order
        await db.execute(delete(OrderItem))
        await db.execute(delete(Order))
        await db.execute(delete(Event))
        await db.execute(delete(Batch))
        await db.execute(delete(Inventory))
        await db.execute(delete(Customer))
        await db.execute(delete(Product))
        await db.execute(delete(Supplier))
        await db.execute(delete(Store))
        await db.execute(delete(Simulation))
        await db.commit()

        # Clear in-flight transfers and purchase orders
        clear_active_transfers()
        clear_active_pos()

        # Re-initialize RNG
        self.rng = random.Random(self.seed)
        self.clock = None

        # Re-seed and regenerate
        simulation = await self.initialize(db)
        return {
            'simulation_id': str(simulation.simulation_id),
            'status': 'reset_complete',
            'current_time': self.clock.now.isoformat() if self.clock else None,
        }


    # ---- PRIVATE METHODS ----

    async def _seed_base_data(self, db: AsyncSession) -> None:
        """Seed stores, suppliers, products, and customers."""
        # Stores
        for s in STORES:
            store = Store(
                store_id=s.store_id,
                name=s.name,
                latitude=s.latitude,
                longitude=s.longitude,
                operating_status=StoreStatus.ACTIVE,
            )
            db.add(store)
            self._store_map[s.name] = s.store_id

        # Suppliers
        for s in SUPPLIERS:
            supplier = Supplier(
                supplier_id=s.supplier_id,
                name=s.name,
                lead_time_hours=s.lead_time_hours,
                status=SupplierStatus.ACTIVE,
            )
            db.add(supplier)
            self._supplier_map[s.name] = s.supplier_id

        await db.flush()

        # Products
        self._product_list = list(PRODUCTS)
        for p in PRODUCTS:
            product = Product(
                product_id=p.product_id,
                name=p.name,
                category=ProductCategory(p.category),
                unit=p.unit,
                shelf_life_hours=p.shelf_life_hours,
                base_price=p.base_price,
                supplier_id=self._supplier_map[p.supplier_name],
                substitution_group=p.substitution_group,
            )
            db.add(product)

        await db.flush()

        # Customers
        for c in CUSTOMERS:
            customer = Customer(
                customer_id=c.customer_id,
                name=c.name,
                home_store_id=self._store_map[c.home_store_name],
            )
            db.add(customer)

        await db.flush()

    async def _create_initial_inventory(self, db: AsyncSession) -> None:
        """Create initial inventory and batches for all store-product pairs."""
        for store_seed in STORES:
            for prod_seed in PRODUCTS:
                # Initial quantity: 2-4 days of mean demand
                initial_qty = int(prod_seed.daily_demand_mean * self.rng.uniform(2.0, 4.0))

                inventory = Inventory(
                    id=uuid.uuid4(),
                    store_id=store_seed.store_id,
                    product_id=prod_seed.product_id,
                    quantity=initial_qty,
                )
                db.add(inventory)

                # Create a batch for perishable stock
                batch_received = self.clock.now - timedelta(
                    hours=self.rng.randint(0, min(24, prod_seed.shelf_life_hours // 4))
                )
                batch = Batch(
                    batch_id=uuid.uuid4(),
                    store_id=store_seed.store_id,
                    product_id=prod_seed.product_id,
                    quantity=initial_qty,
                    received_at=batch_received,
                    expires_at=batch_received + timedelta(hours=prod_seed.shelf_life_hours),
                )
                db.add(batch)

        await db.flush()

    async def _generate_historical_orders(self, db: AsyncSession) -> None:
        """Generate orders day by day for the historical period."""
        for day_offset in range(self.historical_days):
            day_start = self.clock.start_time + timedelta(days=day_offset)
            day_end = day_start + timedelta(days=1)
            await self._generate_orders_for_period(db, day_start, day_end)

            # Periodic restocking every 3 days
            if day_offset > 0 and day_offset % 3 == 0:
                await self._restock_inventory(db, day_start)

    async def _generate_orders_for_period(
        self, db: AsyncSession, start: datetime, end: datetime
    ) -> int:
        """Generate orders for all customers within a time period.
        
        Returns count of orders created.
        """
        hours_in_period = (end - start).total_seconds() / 3600
        orders_created = 0

        if not self._store_map:
            store_res = await db.execute(select(Store))
            stores = store_res.scalars().all()
            self._store_map = {s.name: s.store_id for s in stores}

        for cust_seed in CUSTOMERS:
            # Probability of ordering in this period
            order_prob = hours_in_period / (cust_seed.order_frequency_days * 24)
            if self.rng.random() > order_prob:
                continue

            # Determine order time
            order_time = start + timedelta(
                hours=self.rng.uniform(0, hours_in_period)
            )

            # Weekend demand adjustment (Saturday=5, Sunday=6)
            is_weekend = order_time.weekday() >= 5

            # Pick random products for this order
            num_items = max(1, int(self.rng.gauss(
                cust_seed.avg_items_per_order, 1.5
            )))
            num_items = min(num_items, len(PRODUCTS))
            selected_products = self.rng.sample(PRODUCTS, num_items)

            store_id = self._store_map[cust_seed.home_store_name]
            order_id = uuid.uuid4()

            order = Order(
                order_id=order_id,
                customer_id=cust_seed.customer_id,
                store_id=store_id,
                created_at=order_time,
                status=OrderStatus.DELIVERED,
            )
            db.add(order)

            for prod_seed in selected_products:
                # Quantity: 1-3 with demand characteristics
                qty = max(1, int(self.rng.gauss(1.5, 0.5)))
                if is_weekend:
                    qty = max(1, int(qty * prod_seed.weekend_multiplier))

                item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    product_id=prod_seed.product_id,
                    quantity=qty,
                    price=prod_seed.base_price,
                )
                db.add(item)

                # Deduct from inventory using FIFO batch depletion
                await self._deduct_inventory(db, store_id, prod_seed.product_id, qty)

            orders_created += 1

        if orders_created > 0:
            await db.flush()

        return orders_created

    async def _deduct_inventory(
        self, db: AsyncSession, store_id: uuid.UUID, product_id: uuid.UUID, qty: int
    ) -> None:
        """Deduct quantity from active batches (FIFO) and synchronize inventory. Floor at 0."""
        batch_res = await db.execute(
            select(Batch)
            .where(
                Batch.store_id == store_id,
                Batch.product_id == product_id,
                Batch.quantity > 0,
            )
            .order_by(Batch.expires_at.asc(), Batch.received_at.asc())
        )
        batches = batch_res.scalars().all()

        rem = qty
        for b in batches:
            if rem <= 0:
                break
            deduct = min(b.quantity, rem)
            b.quantity -= deduct
            rem -= deduct

        inv_res = await db.execute(
            select(Inventory).where(
                Inventory.store_id == store_id,
                Inventory.product_id == product_id,
            )
        )
        inv = inv_res.scalar_one_or_none()
        if inv:
            inv.quantity = sum(b.quantity for b in batches)

    async def _restock_inventory(self, db: AsyncSession, restock_time: datetime) -> None:
        """Restock inventory for all stores/products (simulated supplier delivery)."""
        restock_naive = restock_time.replace(tzinfo=None) if restock_time.tzinfo else restock_time
        for store_seed in STORES:
            for prod_seed in PRODUCTS:
                # Count unexpired active batches
                active_sum_res = await db.execute(
                    select(func.coalesce(func.sum(Batch.quantity), 0)).where(
                        Batch.store_id == store_seed.store_id,
                        Batch.product_id == prod_seed.product_id,
                        Batch.quantity > 0,
                        Batch.expires_at > restock_naive,
                    )
                )
                active_qty = active_sum_res.scalar()

                if active_qty < prod_seed.daily_demand_mean * 2:
                    restock_qty = int(prod_seed.daily_demand_mean * self.rng.uniform(2.5, 3.5))

                    batch = Batch(
                        batch_id=uuid.uuid4(),
                        store_id=store_seed.store_id,
                        product_id=prod_seed.product_id,
                        quantity=restock_qty,
                        received_at=restock_naive,
                        expires_at=restock_naive + timedelta(hours=prod_seed.shelf_life_hours),
                    )
                    db.add(batch)

                    # Synchronize inventory
                    inv_res = await db.execute(
                        select(Inventory).where(
                            Inventory.store_id == store_seed.store_id,
                            Inventory.product_id == prod_seed.product_id,
                        )
                    )
                    inv = inv_res.scalar_one_or_none()
                    if inv:
                        inv.quantity = active_qty + restock_qty

        await db.flush()

    async def _expire_batches(self, db: AsyncSession, current_time: datetime) -> int:
        """Mark expired batches and deduct from inventory. Returns count of expired batches."""
        result = await db.execute(
            select(Batch).where(
                Batch.expires_at <= current_time,
                Batch.quantity > 0,
            )
        )
        expired = result.scalars().all()

        affected_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for batch in expired:
            affected_pairs.add((batch.store_id, batch.product_id))
            batch.quantity = 0

        for store_id, product_id in affected_pairs:
            batch_sum_res = await db.execute(
                select(func.coalesce(func.sum(Batch.quantity), 0)).where(
                    Batch.store_id == store_id,
                    Batch.product_id == product_id,
                    Batch.quantity > 0,
                )
            )
            total_active = batch_sum_res.scalar()
            inv_res = await db.execute(
                select(Inventory).where(
                    Inventory.store_id == store_id,
                    Inventory.product_id == product_id,
                )
            )
            inv = inv_res.scalar_one_or_none()
            if inv:
                inv.quantity = total_active

        if expired:
            await db.flush()

        return len(expired)

