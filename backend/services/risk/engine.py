"""GROCER v2 Risk Engine.

Orchestrates risk detection across inventory, forecasts, and batch states:
  1. Scan store inventory and compare against 24h/48h demand forecasts.
  2. Compute stockout risk with StockoutCalculator (spec §5.1).
  3. Scan perishable batches and compute spoilage risk with SpoilageCalculator (spec §5.2).
  4. Persist Risk records to DB (spec §29.10).
  5. Emit RISK_DETECTED events via in-process EventBus (spec §30).
  6. Support risk resolution and status transitions (ACTIVE -> RESOLVED).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Risk, Inventory, Batch, Product, Supplier, Forecast
from backend.models.enums import RiskType, RiskSeverity, RiskStatus
from backend.events.bus import bus
from backend.services.risk.models import (
    StockoutInput,
    SpoilageInput,
    StockoutCalculator,
    SpoilageCalculator,
    RiskResult,
    RiskSeverityLevel,
    DiscountTier,
)


def _naive_now() -> datetime:
    """Return naive current UTC datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RiskEngine:
    """Detects inventory stockout and batch spoilage risks.

    Usage:
        engine = RiskEngine()
        count = await engine.run(db)
        await engine.resolve(db, risk_id)
    """

    def __init__(self) -> None:
        self.stockout_calculator = StockoutCalculator()
        self.spoilage_calculator = SpoilageCalculator()

    async def run(self, db: AsyncSession) -> int:
        """Scan all inventory and batches, evaluate risks, persist rows and emit events.

        Returns total number of Risk rows created.
        """
        now = _naive_now()

        # 1. Load Products & Suppliers
        prod_result = await db.execute(select(Product, Supplier).join(Supplier, Product.supplier_id == Supplier.supplier_id))
        products_map: dict[uuid.UUID, tuple[Product, Supplier]] = {}
        for row in prod_result.all():
            products_map[row.Product.product_id] = (row.Product, row.Supplier)

        # 2. Load latest Forecast for each (store, product)
        fc_result = await db.execute(select(Forecast).order_by(Forecast.created_at.desc()))
        forecasts_map: dict[tuple[uuid.UUID, uuid.UUID], Forecast] = {}
        for fc in fc_result.scalars().all():
            key = (fc.store_id, fc.product_id)
            if key not in forecasts_map:
                forecasts_map[key] = fc

        # 3. Load all Inventory items
        inv_result = await db.execute(select(Inventory))
        inventory_items = inv_result.scalars().all()

        # 4. Load all Batches (active, not expired)
        batch_result = await db.execute(select(Batch).order_by(Batch.expires_at.asc()))
        batches_by_key: dict[tuple[uuid.UUID, uuid.UUID], list[Batch]] = {}
        for b in batch_result.scalars().all():
            # Check expiry with naive datetime
            exp = b.expires_at.replace(tzinfo=None) if b.expires_at.tzinfo is not None else b.expires_at
            if exp > now and b.quantity > 0:
                batches_by_key.setdefault((b.store_id, b.product_id), []).append(b)

        count = 0

        # 5. Evaluate Stockout Risk
        for inv in inventory_items:
            key = (inv.store_id, inv.product_id)
            prod_supp = products_map.get(inv.product_id)
            if not prod_supp:
                continue
            product, supplier = prod_supp

            forecast = forecasts_map.get(key)
            if forecast:
                demand_24h = forecast.predicted_demand
                demand_48h = demand_24h * 2.0
            else:
                demand_24h = 10.0
                demand_48h = 20.0

            stockout_in = StockoutInput(
                store_id=inv.store_id,
                product_id=inv.product_id,
                current_quantity=inv.quantity,
                forecast_demand_24h=demand_24h,
                forecast_demand_48h=demand_48h,
                lead_time_hours=supplier.lead_time_hours,
            )
            so_res = self.stockout_calculator.evaluate(stockout_in)

            # Record risk if WARNING or CRITICAL (or probability >= 0.25)
            if so_res.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL) or so_res.probability >= 0.25:
                risk_id = uuid.uuid4()
                hours_to_event = so_res.expected_hours_to_event
                if hours_to_event == float("inf") or hours_to_event > 720:
                    hours_to_event = 720.0
                expected_time = now + timedelta(hours=hours_to_event)

                severity_enum = RiskSeverity(so_res.severity.value)
                risk_row = Risk(
                    risk_id=risk_id,
                    store_id=inv.store_id,
                    product_id=inv.product_id,
                    risk_type=RiskType.STOCKOUT,
                    severity=severity_enum,
                    probability=so_res.probability,
                    expected_time=expected_time,
                    status=RiskStatus.ACTIVE,
                    created_at=now,
                )
                db.add(risk_row)
                await db.flush()

                await bus.publish(
                    db,
                    "RISK_DETECTED",
                    "risk",
                    risk_id,
                    {
                        "risk_id": str(risk_id),
                        "store_id": str(inv.store_id),
                        "product_id": str(inv.product_id),
                        "risk_type": RiskType.STOCKOUT.value,
                        "severity": severity_enum.value,
                        "probability": so_res.probability,
                        "expected_time": expected_time.isoformat(),
                    },
                    persist=True,
                )
                count += 1

        # 6. Evaluate Spoilage Risk
        for (store_id, product_id), batches in batches_by_key.items():
            if not batches:
                continue
            prod_supp = products_map.get(product_id)
            if not prod_supp:
                continue
            product, _ = prod_supp

            soonest_batch = batches[0]
            exp = soonest_batch.expires_at.replace(tzinfo=None) if soonest_batch.expires_at.tzinfo is not None else soonest_batch.expires_at
            hours_to_expiry = max(0.0, (exp - now).total_seconds() / 3600.0)

            forecast = forecasts_map.get((store_id, product_id))
            demand_24h = forecast.predicted_demand if forecast else 10.0
            hourly_demand = demand_24h / 24.0
            forecast_demand_before_expiry = hourly_demand * hours_to_expiry

            total_qty = sum(b.quantity for b in batches)

            spoilage_in = SpoilageInput(
                store_id=store_id,
                product_id=product_id,
                at_risk_quantity=soonest_batch.quantity,
                total_quantity=total_qty,
                min_hours_to_expiry=hours_to_expiry,
                forecast_demand_before_expiry=forecast_demand_before_expiry,
                shelf_life_hours=product.shelf_life_hours,
            )
            sp_res = self.spoilage_calculator.evaluate(spoilage_in)

            if sp_res.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL) or sp_res.probability >= 0.25:
                risk_id = uuid.uuid4()
                expected_time = now + timedelta(hours=sp_res.expected_hours_to_event)
                severity_enum = RiskSeverity(sp_res.severity.value)

                risk_row = Risk(
                    risk_id=risk_id,
                    store_id=store_id,
                    product_id=product_id,
                    risk_type=RiskType.SPOILAGE,
                    severity=severity_enum,
                    probability=sp_res.probability,
                    expected_time=expected_time,
                    status=RiskStatus.ACTIVE,
                    created_at=now,
                )
                db.add(risk_row)
                await db.flush()

                await bus.publish(
                    db,
                    "RISK_DETECTED",
                    "risk",
                    risk_id,
                    {
                        "risk_id": str(risk_id),
                        "store_id": str(store_id),
                        "product_id": str(product_id),
                        "risk_type": RiskType.SPOILAGE.value,
                        "severity": severity_enum.value,
                        "probability": sp_res.probability,
                        "expected_time": expected_time.isoformat(),
                        "discount_tier": sp_res.discount_tier.value,
                        "net_spoilage_quantity": sp_res.net_spoilage_quantity,
                    },
                    persist=True,
                )
                count += 1

        return count

    async def resolve(self, db: AsyncSession, risk_id: uuid.UUID) -> Optional[Risk]:
        """Mark an active risk as RESOLVED and emit RISK_RESOLVED event."""
        risk = await db.get(Risk, risk_id)
        if not risk:
            return None

        risk.status = RiskStatus.RESOLVED
        await db.flush()

        await bus.publish(
            db,
            "RISK_RESOLVED",
            "risk",
            risk_id,
            {
                "risk_id": str(risk_id),
                "status": RiskStatus.RESOLVED.value,
            },
            persist=True,
        )
        return risk
