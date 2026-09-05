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
    RiskConfig,
    BatchInfo,
    MultiBatchSpoilageInput,
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

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()
        self.stockout_calculator = StockoutCalculator(config=self.config)
        self.spoilage_calculator = SpoilageCalculator(config=self.config)

    async def run(self, db: AsyncSession, now: Optional[datetime] = None) -> int:
        """Scan all inventory and batches, evaluate risks, persist rows and emit events.

        Returns total number of active Risk items evaluated.
        """
        if now is None:
            now = _naive_now()
        else:
            now = now.replace(tzinfo=None) if now.tzinfo is not None else now


        # 1. Load Products & Suppliers
        prod_result = await db.execute(select(Product, Supplier).join(Supplier, Product.supplier_id == Supplier.supplier_id))
        products_map: dict[uuid.UUID, tuple[Product, Supplier]] = {}
        for row in prod_result.all():
            products_map[row.Product.product_id] = (row.Product, row.Supplier)

        # 2. Load latest Forecasts indexed by (store_id, product_id, horizon_hours)
        fc_result = await db.execute(select(Forecast).order_by(Forecast.created_at.desc()))
        forecasts_by_scope_horizon: dict[tuple[uuid.UUID, uuid.UUID, int], Forecast] = {}
        for fc in fc_result.scalars().all():
            h_key = (fc.store_id, fc.product_id, fc.forecast_window_hours)
            if h_key not in forecasts_by_scope_horizon:
                forecasts_by_scope_horizon[h_key] = fc

        def get_demand_and_confidence(store_id: uuid.UUID, product_id: uuid.UUID, category: Optional[str] = None) -> tuple[float, float, float]:
            """Returns (demand_24h, demand_48h, confidence) with multi-horizon interpolation & cold-start fallback."""
            fc_24 = forecasts_by_scope_horizon.get((store_id, product_id, 24))
            fc_48 = forecasts_by_scope_horizon.get((store_id, product_id, 48))
            fc_12 = forecasts_by_scope_horizon.get((store_id, product_id, 12))
            fc_6 = forecasts_by_scope_horizon.get((store_id, product_id, 6))

            if fc_24:
                d24 = fc_24.predicted_demand
                conf = fc_24.confidence
                d48 = fc_48.predicted_demand if fc_48 else d24 * 2.0
                return d24, d48, conf
            elif fc_12:
                d24 = fc_12.predicted_demand * 2.0
                conf = fc_12.confidence
                d48 = fc_48.predicted_demand if fc_48 else d24 * 2.0
                return d24, d48, conf
            elif fc_6:
                d24 = fc_6.predicted_demand * 4.0
                conf = fc_6.confidence
                d48 = fc_48.predicted_demand if fc_48 else d24 * 2.0
                return d24, d48, conf
            else:
                # Cold-start seed priors based on category velocity
                cat_priors = {
                    "dairy": 16.0,
                    "bakery": 14.0,
                    "produce": 12.0,
                    "staples": 8.0,
                    "packaged": 10.0,
                }
                d24 = cat_priors.get(category.lower() if category else "", 12.0)
                d48 = d24 * 2.0
                return d24, d48, 0.3  # Low confidence prior

        # 3. Load all Inventory items
        inv_result = await db.execute(select(Inventory))
        inventory_items = inv_result.scalars().all()

        # 4. Load all Batches (active, not expired)
        batch_result = await db.execute(select(Batch).order_by(Batch.expires_at.asc()))
        batches_by_key: dict[tuple[uuid.UUID, uuid.UUID], list[Batch]] = {}
        for b in batch_result.scalars().all():
            exp = b.expires_at.replace(tzinfo=None) if b.expires_at.tzinfo is not None else b.expires_at
            if exp > now and b.quantity > 0:
                batches_by_key.setdefault((b.store_id, b.product_id), []).append(b)

        # 5. Load existing ACTIVE risks to deduplicate
        active_risks_res = await db.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))
        existing_active_risks: dict[tuple[uuid.UUID, uuid.UUID, RiskType], Risk] = {}
        for r in active_risks_res.scalars().all():
            existing_active_risks[(r.store_id, r.product_id, r.risk_type)] = r

        count = 0

        # 6. Evaluate Stockout Risk
        for inv in inventory_items:
            prod_supp = products_map.get(inv.product_id)
            if not prod_supp:
                continue
            product, supplier = prod_supp

            cat_val = product.category.value if hasattr(product.category, "value") else str(product.category)
            demand_24h, demand_48h, confidence = get_demand_and_confidence(inv.store_id, inv.product_id, cat_val)

            stockout_in = StockoutInput(
                store_id=inv.store_id,
                product_id=inv.product_id,
                current_quantity=inv.quantity,
                forecast_demand_24h=demand_24h,
                forecast_demand_48h=demand_48h,
                lead_time_hours=supplier.lead_time_hours,
                forecast_confidence=confidence,
            )
            so_res = self.stockout_calculator.evaluate(stockout_in)

            # Record or update risk if WARNING or CRITICAL (or probability >= 0.25)
            if so_res.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL) or so_res.probability >= 0.25:
                hours_to_event = so_res.expected_hours_to_event
                if hours_to_event == float("inf") or hours_to_event > 720:
                    hours_to_event = 720.0
                expected_time = now + timedelta(hours=hours_to_event)
                severity_enum = RiskSeverity(so_res.severity.value)

                existing = existing_active_risks.get((inv.store_id, inv.product_id, RiskType.STOCKOUT))
                if existing:
                    existing.probability = so_res.probability
                    existing.severity = severity_enum
                    existing.expected_time = expected_time
                else:
                    risk_id = uuid.uuid4()
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
                    existing_active_risks[(inv.store_id, inv.product_id, RiskType.STOCKOUT)] = risk_row

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

        # 7. Evaluate Spoilage Risk
        for (store_id, product_id), batches in batches_by_key.items():
            if not batches:
                continue
            prod_supp = products_map.get(product_id)
            if not prod_supp:
                continue
            product, _ = prod_supp

            cat_val = product.category.value if hasattr(product.category, "value") else str(product.category)
            demand_24h, _, confidence = get_demand_and_confidence(store_id, product_id, cat_val)
            hourly_demand = demand_24h / 24.0

            batch_infos = [
                BatchInfo(
                    batch_id=b.batch_id,
                    quantity=b.quantity,
                    hours_to_expiry=max(0.0, ((b.expires_at.replace(tzinfo=None) if b.expires_at.tzinfo else b.expires_at) - now).total_seconds() / 3600.0),
                )
                for b in batches
            ]

            multi_sp_in = MultiBatchSpoilageInput(
                store_id=store_id,
                product_id=product_id,
                batches=batch_infos,
                hourly_demand=hourly_demand,
                shelf_life_hours=product.shelf_life_hours,
                forecast_confidence=confidence,
            )
            sp_res = self.spoilage_calculator.evaluate_batches(multi_sp_in)

            if sp_res.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL) or sp_res.probability >= 0.25:
                hours_to_event = sp_res.expected_hours_to_event
                if hours_to_event == float("inf") or hours_to_event > 720:
                    hours_to_event = 720.0
                expected_time = now + timedelta(hours=hours_to_event)
                severity_enum = RiskSeverity(sp_res.severity.value)

                existing = existing_active_risks.get((store_id, product_id, RiskType.SPOILAGE))
                if existing:
                    existing.probability = sp_res.probability
                    existing.severity = severity_enum
                    existing.expected_time = expected_time
                else:
                    risk_id = uuid.uuid4()
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
                    existing_active_risks[(store_id, product_id, RiskType.SPOILAGE)] = risk_row

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
