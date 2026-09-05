"""Operational Scenario Driver for GROCER v2 (Phase 2).

Encapsulates the 5 canonical benchmark scenarios:
1. normal: Baseline controlled stochastic Poisson demand across all 5 stores.
2. demand_spike: 2.5x morning surge on perishables (dairy, bakery).
3. supplier_delay: +24h to +48h delay on supplier purchase orders.
4. expiry_wave: Compression of batch expiration dates creating near-term spoilage risk.
5. network_imbalance: Extreme spatial skew (excess in Bandra, critical deficit in Andheri).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Store, Product, Inventory, Batch, Event, Simulation
from backend.services.simulation.seed_data import STORES, PRODUCTS

SCENARIO_NAMES = [
    'normal',
    'demand_spike',
    'supplier_delay',
    'expiry_wave',
    'network_imbalance',
]


@dataclass
class ScenarioConfig:
    name: str
    description: str
    demand_multiplier_by_category: dict[str, float] = field(default_factory=dict)
    supplier_lead_time_delay_hours: int = 0
    perishable_shelf_life_scale: float = 1.0


_SCENARIO_CONFIGS: dict[str, ScenarioConfig] = {
    'normal': ScenarioConfig(
        name='normal',
        description='Standard operational baseline with controlled stochastic demand.',
        demand_multiplier_by_category={'dairy': 1.0, 'bakery': 1.0, 'produce': 1.0, 'staples': 1.0, 'packaged': 1.0},
        supplier_lead_time_delay_hours=0,
    ),
    'demand_spike': ScenarioConfig(
        name='demand_spike',
        description='Morning surge with +250% demand on dairy and bakery perishables.',
        demand_multiplier_by_category={'dairy': 2.5, 'bakery': 2.0, 'produce': 1.8, 'staples': 1.0, 'packaged': 1.1},
        supplier_lead_time_delay_hours=0,
    ),
    'supplier_delay': ScenarioConfig(
        name='supplier_delay',
        description='Supply chain disruption adding +24h delay to arriving supplier purchase orders.',
        demand_multiplier_by_category={'dairy': 1.0, 'bakery': 1.0, 'produce': 1.0, 'staples': 1.0, 'packaged': 1.0},
        supplier_lead_time_delay_hours=24,
    ),
    'expiry_wave': ScenarioConfig(
        name='expiry_wave',
        description='Perishable batches expiring within 6-12 hours with low baseline sell-through.',
        demand_multiplier_by_category={'dairy': 0.8, 'bakery': 0.8, 'produce': 0.7, 'staples': 1.0, 'packaged': 1.0},
        supplier_lead_time_delay_hours=0,
        perishable_shelf_life_scale=0.2,
    ),
    'network_imbalance': ScenarioConfig(
        name='network_imbalance',
        description='Asymmetric spatial distribution with excess in Bandra and critical stockout risk in Andheri.',
        demand_multiplier_by_category={'dairy': 1.2, 'bakery': 1.1, 'produce': 1.0, 'staples': 1.0, 'packaged': 1.0},
        supplier_lead_time_delay_hours=0,
    ),
}


def get_scenario_config(scenario_name: str) -> ScenarioConfig:
    """Retrieve scenario configuration parameters."""
    if scenario_name not in _SCENARIO_CONFIGS:
        raise ValueError(f"Unknown scenario '{scenario_name}'. Available: {SCENARIO_NAMES}")
    return _SCENARIO_CONFIGS[scenario_name]


async def apply_scenario(
    db: AsyncSession,
    engine: Any,
    scenario_name: str,
) -> dict[str, Any]:
    """Inject scenario conditions into the live simulation database."""
    config = get_scenario_config(scenario_name)
    now = engine.clock.now
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now

    if scenario_name == 'network_imbalance':
        # Drain Andheri milk to <= 4 units and inflate Bandra milk to >= 80 units
        all_stores = (await db.execute(select(Store))).scalars().all()
        bandra = next((s for s in all_stores if 'Bandra' in s.name), None)
        andheri = next((s for s in all_stores if 'Andheri' in s.name), None)

        all_prods = (await db.execute(select(Product))).scalars().all()
        milk = next((p for p in all_prods if 'Toned Milk' in p.name), None)

        if bandra and andheri and milk:
            # Drain Andheri active batches down to 3 units
            andheri_batches = (await db.execute(
                select(Batch).where(
                    Batch.store_id == andheri.store_id,
                    Batch.product_id == milk.product_id,
                    Batch.quantity > 0,
                )
            )).scalars().all()
            for idx, b in enumerate(andheri_batches):
                b.quantity = 3 if idx == 0 else 0

            # Inflate Bandra active batches up to 85 units
            bandra_batches = (await db.execute(
                select(Batch).where(
                    Batch.store_id == bandra.store_id,
                    Batch.product_id == milk.product_id,
                    Batch.quantity > 0,
                )
            )).scalars().all()
            if bandra_batches:
                bandra_batches[0].quantity = 85
            else:
                db.add(Batch(
                    batch_id=uuid.uuid4(),
                    store_id=bandra.store_id,
                    product_id=milk.product_id,
                    quantity=85,
                    received_at=now_naive,
                    expires_at=now_naive + timedelta(hours=72),
                ))

            # Sync Inventories
            andheri_inv = (await db.execute(
                select(Inventory).where(Inventory.store_id == andheri.store_id, Inventory.product_id == milk.product_id)
            )).scalar_one_or_none()
            if andheri_inv:
                andheri_inv.quantity = 3

            bandra_inv = (await db.execute(
                select(Inventory).where(Inventory.store_id == bandra.store_id, Inventory.product_id == milk.product_id)
            )).scalar_one_or_none()
            if bandra_inv:
                bandra_inv.quantity = 85

    elif scenario_name == 'expiry_wave':
        # Compress perishable batches to expire within 6 to 10 hours
        perishable_prods = (await db.execute(
            select(Product).where(Product.category.in_(['dairy', 'bakery']))
        )).scalars().all()
        prod_ids = [p.product_id for p in perishable_prods]

        batches = (await db.execute(
            select(Batch).where(
                Batch.product_id.in_(prod_ids),
                Batch.quantity > 0,
                Batch.expires_at > now_naive,
            )
        )).scalars().all()

        for idx, b in enumerate(batches):
            hours_left = 6 + (idx % 4)  # 6, 7, 8, 9 hours
            b.expires_at = now_naive + timedelta(hours=hours_left)

    # Record event
    event = Event(
        event_id=uuid.uuid4(),
        event_type='SCENARIO_APPLIED',
        timestamp=now,
        entity_type='scenario',
        entity_id=uuid.uuid4(),
        payload={
            'scenario': scenario_name,
            'description': config.description,
            'demand_multipliers': config.demand_multiplier_by_category,
            'supplier_delay_hours': config.supplier_lead_time_delay_hours,
        },
    )
    db.add(event)
    await db.flush()

    return {
        'scenario': scenario_name,
        'status': 'applied',
        'description': config.description,
        'demand_multipliers': config.demand_multiplier_by_category,
        'supplier_delay_hours': config.supplier_lead_time_delay_hours,
    }

