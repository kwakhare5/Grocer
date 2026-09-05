"""Supplier Order & Lead-Time Simulation Service for GROCER v2.

Handles:
- Purchase order (PO) creation with realistic supplier lead times
- In-transit shipment tracking
- Supplier delivery delays and disruptions
- Delivery processing: receipt into new batches and inventory synchronization
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Supplier, Store, Product, Inventory, Batch, Event


@dataclass
class PurchaseOrder:
    po_id: uuid.UUID
    supplier_id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    ordered_at: datetime
    expected_arrival: datetime
    status: str = 'in_transit'  # 'in_transit' | 'delayed' | 'delivered' | 'cancelled'
    delay_hours: int = 0


# Active PO registry
_active_pos: list[PurchaseOrder] = []


def get_active_pos() -> list[PurchaseOrder]:
    """Retrieve all pending or in-transit supplier purchase orders."""
    return [po for po in _active_pos if po.status in ('in_transit', 'delayed')]


def clear_active_pos() -> None:
    """Reset active purchase orders."""
    global _active_pos
    _active_pos = []


async def create_purchase_order(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: int,
    current_time: datetime,
    delay_hours: int = 0,
) -> PurchaseOrder:
    """Create a new supplier purchase order with expected arrival based on lead time."""
    if quantity <= 0:
        raise ValueError("Purchase order quantity must be positive")

    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise ValueError(f"Supplier {supplier_id} not found")

    total_lead_time = supplier.lead_time_hours + delay_hours
    expected_arrival = current_time + timedelta(hours=total_lead_time)

    po = PurchaseOrder(
        po_id=uuid.uuid4(),
        supplier_id=supplier_id,
        store_id=store_id,
        product_id=product_id,
        quantity=quantity,
        ordered_at=current_time,
        expected_arrival=expected_arrival,
        status='delayed' if delay_hours > 0 else 'in_transit',
        delay_hours=delay_hours,
    )
    _active_pos.append(po)

    # Record event
    event = Event(
        event_id=uuid.uuid4(),
        event_type='PURCHASE_ORDER_PLACED',
        timestamp=current_time,
        entity_type='purchase_order',
        entity_id=po.po_id,
        payload={
            'supplier_id': str(supplier_id),
            'store_id': str(store_id),
            'product_id': str(product_id),
            'quantity': quantity,
            'lead_time_hours': supplier.lead_time_hours,
            'expected_arrival': expected_arrival.isoformat(),
        },
    )
    db.add(event)
    await db.flush()

    return po


def apply_supplier_delay(po_id: uuid.UUID, additional_hours: int) -> PurchaseOrder:
    """Apply an unexpected shipment delay to an existing purchase order."""
    po = next((p for p in _active_pos if p.po_id == po_id), None)
    if not po:
        raise ValueError(f"Purchase order {po_id} not found")

    po.delay_hours += additional_hours
    po.expected_arrival += timedelta(hours=additional_hours)
    po.status = 'delayed'
    return po


async def process_supplier_deliveries(
    db: AsyncSession, current_time: datetime
) -> list[PurchaseOrder]:
    """Process arriving supplier purchase orders and add newly received batches to inventory."""
    delivered: list[PurchaseOrder] = []
    current_naive = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time

    for po in _active_pos:
        arr_naive = po.expected_arrival.replace(tzinfo=None) if po.expected_arrival.tzinfo else po.expected_arrival
        if po.status in ('in_transit', 'delayed') and current_naive >= arr_naive:
            # Get product shelf life
            product = await db.get(Product, po.product_id)
            shelf_life = product.shelf_life_hours if product else 72

            # Create fresh received batch
            new_batch = Batch(
                batch_id=uuid.uuid4(),
                store_id=po.store_id,
                product_id=po.product_id,
                quantity=po.quantity,
                received_at=current_naive,
                expires_at=current_naive + timedelta(hours=shelf_life),
            )
            db.add(new_batch)

            # Synchronize store inventory
            inv_res = await db.execute(
                select(Inventory).where(
                    Inventory.store_id == po.store_id,
                    Inventory.product_id == po.product_id,
                )
            )
            inv = inv_res.scalar_one_or_none()
            if inv:
                await db.flush()
                active_sum_res = await db.execute(
                    select(func.coalesce(func.sum(Batch.quantity), 0)).where(
                        Batch.store_id == po.store_id,
                        Batch.product_id == po.product_id,
                        Batch.quantity > 0,
                    )
                )
                inv.quantity = active_sum_res.scalar()

            po.status = 'delivered'
            delivered.append(po)

            event = Event(
                event_id=uuid.uuid4(),
                event_type='PURCHASE_ORDER_DELIVERED',
                timestamp=current_time,
                entity_type='purchase_order',
                entity_id=po.po_id,
                payload={
                    'supplier_id': str(po.supplier_id),
                    'store_id': str(po.store_id),
                    'product_id': str(po.product_id),
                    'quantity': po.quantity,
                },
            )
            db.add(event)

    if delivered:
        await db.flush()

    return delivered
