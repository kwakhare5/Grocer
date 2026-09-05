"""Agent execution tools -- spec section 20.

All tools are typed async functions that accept a db session and typed arguments.
Mutation tools validate the approval state server-side before applying any change.
The agent never gets unrestricted DB access -- it uses these typed functions only.

Permission model:
  READ tools: always callable.
  MUTATION tools: require recommendation.status == APPROVED. Raise PermissionError otherwise.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Recommendation, Inventory, Risk, Store, Batch, Product, Action
from backend.models.enums import RecommendationStatus, ActionType, ActionStatus
from backend.services.decision.models import SafeExcessCalculator, DEFAULT_WEIGHTS
from backend.events.bus import bus


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enum_val(v: Any) -> str:
    """Return .value if enum, else str."""
    return v.value if hasattr(v, "value") else str(v)


# ---------------------------------------------------------------------------
# READ TOOLS
# ---------------------------------------------------------------------------

async def get_recommendation(db: AsyncSession, recommendation_id: uuid.UUID) -> dict | None:
    """Return a dict snapshot of the Recommendation row, or None if not found."""
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return None
    return {
        "recommendation_id": str(rec.recommendation_id),
        "risk_id":           str(rec.risk_id),
        "action_type":       _enum_val(rec.action_type),
        "quantity":          rec.quantity,
        "source_store_id":   str(rec.source_store_id) if rec.source_store_id else None,
        "destination_store_id": str(rec.destination_store_id) if rec.destination_store_id else None,
        "score":             rec.score,
        "confidence":        rec.confidence,
        "reason_codes":      rec.reason_codes,
        "alternatives":      rec.alternatives,
        "status":            _enum_val(rec.status),
        "created_at":        rec.created_at.isoformat() if rec.created_at else None,
    }


async def get_inventory(
    db: AsyncSession,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
) -> dict:
    """Return current inventory quantity for (store, product)."""
    result = await db.execute(
        select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
    )
    inv = result.scalar_one_or_none()
    return {
        "store_id":   str(store_id),
        "product_id": str(product_id),
        "quantity":   inv.quantity if inv else 0,
    }


async def validate_transfer(
    db: AsyncSession,
    recommendation_id: uuid.UUID,
) -> dict:
    """Read-only validation: re-check whether the approved transfer is still feasible.

    Returns {"feasible": bool, "reason": str, "source_quantity": int, "transfer_quantity": int}
    """
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return {"feasible": False, "reason": "recommendation_not_found", "source_quantity": 0, "transfer_quantity": 0}

    if rec.source_store_id is None:
        return {"feasible": False, "reason": "no_source_store", "source_quantity": 0, "transfer_quantity": rec.quantity}

    risk = await db.get(Risk, rec.risk_id)
    if risk is None:
        return {"feasible": False, "reason": "linked_risk_not_found", "source_quantity": 0, "transfer_quantity": rec.quantity}
    product_id = risk.product_id

    # Get current source inventory
    src_inv = await get_inventory(db, rec.source_store_id, product_id)
    src_qty = src_inv["quantity"]
    transfer_qty = rec.quantity

    # Check basic feasibility: source must have enough total units
    if src_qty < transfer_qty:
        return {
            "feasible": False,
            "reason": f"insufficient_source_inventory: have {src_qty}, need {transfer_qty}",
            "source_quantity": src_qty,
            "transfer_quantity": transfer_qty,
        }

    # Check batch expiry constraints if batches exist
    now = _naive_now()
    batch_res = await db.execute(
        select(Batch).where(
            Batch.store_id == rec.source_store_id,
            Batch.product_id == product_id,
            Batch.quantity > 0,
        )
    )
    all_batches = batch_res.scalars().all()
    if all_batches:
        active_unexpired = [b for b in all_batches if b.expires_at > now]
        active_batch_qty = sum(b.quantity for b in active_unexpired)
        if not active_unexpired or active_batch_qty == 0:
            return {
                "feasible": False,
                "reason": "expired_batch: source inventory has expired and cannot be transferred",
                "source_quantity": src_qty,
                "transfer_quantity": transfer_qty,
            }
        if active_batch_qty < transfer_qty:
            return {
                "feasible": False,
                "reason": f"insufficient_source_inventory: have {active_batch_qty} non-expired units, need {transfer_qty}",
                "source_quantity": src_qty,
                "transfer_quantity": transfer_qty,
            }

    return {
        "feasible": True,
        "reason": "ok",
        "source_quantity": src_qty,
        "transfer_quantity": transfer_qty,
    }


async def validate_reorder(
    db: AsyncSession,
    recommendation_id: uuid.UUID,
) -> dict:
    """Read-only validation: check reorder is still relevant."""
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return {"feasible": False, "reason": "recommendation_not_found"}
    return {"feasible": True, "reason": "ok", "reorder_quantity": rec.quantity}


# ---------------------------------------------------------------------------
# MUTATION TOOLS
# All mutation tools check approval status before proceeding (spec section 18).
# ---------------------------------------------------------------------------

def _assert_approved(rec: Recommendation) -> None:
    """Raise PermissionError if the recommendation is not in APPROVED status."""
    status_str = _enum_val(rec.status).lower()
    if status_str == "executed":
        raise PermissionError(
            f"Cannot execute recommendation {rec.recommendation_id}: already executed (idempotency guard)."
        )
    if status_str != "approved":
        raise PermissionError(
            f"Cannot execute recommendation {rec.recommendation_id}: "
            f"status is '{status_str}', expected 'approved'. "
            "Human approval is required before agent execution (spec section 18 LOCKED)."
        )


async def create_transfer(
    db: AsyncSession,
    recommendation_id: uuid.UUID,
) -> dict:
    """MUTATION: Apply a stock transfer from source to destination store.

    Validates approval, checks current source quantity and batch expiry, adjusts
    Batch and Inventory rows via FIFO deduction, emits TRANSFER_EXECUTED event.
    """
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return {"success": False, "error": "recommendation_not_found"}

    if _enum_val(rec.status).lower() == "executed":
        return {"success": False, "error": "already executed"}

    _assert_approved(rec)

    if rec.source_store_id is None:
        return {"success": False, "error": "no_source_store_id in recommendation"}

    # Load risk to get product_id
    risk = await db.get(Risk, rec.risk_id)
    if risk is None:
        return {"success": False, "error": "linked_risk_not_found"}
    product_id = risk.product_id

    transfer_qty = rec.quantity
    now = _naive_now()

    # Transition linked Action to EXECUTING if present
    act_res = await db.execute(
        select(Action).where(Action.recommendation_id == recommendation_id)
    )
    action = act_res.scalars().first()
    if action:
        action.status = ActionStatus.EXECUTING
        await db.flush()

    # Load source and destination inventory
    src_result = await db.execute(
        select(Inventory).where(
            Inventory.store_id == rec.source_store_id,
            Inventory.product_id == product_id,
        )
    )
    src_inv = src_result.scalar_one_or_none()

    dest_result = await db.execute(
        select(Inventory).where(
            Inventory.store_id == rec.destination_store_id,
            Inventory.product_id == product_id,
        )
    )
    dest_inv = dest_result.scalar_one_or_none()

    if src_inv is None:
        return {"success": False, "error": "source_inventory_not_found"}

    if src_inv.quantity < transfer_qty:
        return {
            "success": False,
            "error": f"stale_inventory: source has {src_inv.quantity}, needed {transfer_qty}",
            "stale": True,
        }

    # FIFO Batch deduction and validation
    batch_res = await db.execute(
        select(Batch)
        .where(
            Batch.store_id == rec.source_store_id,
            Batch.product_id == product_id,
            Batch.quantity > 0,
        )
        .order_by(Batch.expires_at.asc(), Batch.received_at.asc())
    )
    all_source_batches = batch_res.scalars().all()

    if all_source_batches:
        unexpired_batches = [b for b in all_source_batches if b.expires_at > now]
        available_batch_qty = sum(b.quantity for b in unexpired_batches)

        if not unexpired_batches or available_batch_qty == 0:
            return {
                "success": False,
                "error": "expired_batch: source inventory has expired and cannot be transferred",
                "stale": True,
            }

        if available_batch_qty < transfer_qty:
            return {
                "success": False,
                "error": f"insufficient_source_inventory: have {available_batch_qty} non-expired units, needed {transfer_qty}",
                "stale": True,
            }

        # Deduct from source batches using FIFO and create matching destination batches
        rem = transfer_qty
        for b in unexpired_batches:
            if rem <= 0:
                break
            take = min(b.quantity, rem)
            b.quantity -= take
            rem -= take

            # Add destination batch with identical shelf life expiry
            dest_batch = Batch(
                batch_id=uuid.uuid4(),
                store_id=rec.destination_store_id,
                product_id=product_id,
                quantity=take,
                received_at=now,
                expires_at=b.expires_at,
            )
            db.add(dest_batch)

    # Apply aggregate inventory changes
    src_inv.quantity -= transfer_qty
    if dest_inv is not None:
        dest_inv.quantity += transfer_qty
    else:
        new_inv = Inventory(
            store_id=rec.destination_store_id,
            product_id=product_id,
            quantity=transfer_qty,
        )
        db.add(new_inv)

    await db.flush()

    # Emit event
    await bus.publish(
        db,
        "TRANSFER_EXECUTED",
        "recommendation",
        recommendation_id,
        {
            "recommendation_id": str(recommendation_id),
            "source_store_id":   str(rec.source_store_id),
            "destination_store_id": str(rec.destination_store_id),
            "product_id":        str(product_id),
            "quantity":          transfer_qty,
        },
        persist=True,
    )

    return {
        "success": True,
        "transferred_quantity": transfer_qty,
        "source_store_id": str(rec.source_store_id),
        "destination_store_id": str(rec.destination_store_id),
        "product_id": str(product_id),
    }


async def create_reorder(
    db: AsyncSession,
    recommendation_id: uuid.UUID,
) -> dict:
    """MUTATION: Place a reorder (simulated: increase destination inventory and create delivery batch)."""
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return {"success": False, "error": "recommendation_not_found"}

    if _enum_val(rec.status).lower() == "executed":
        return {"success": False, "error": "already executed"}

    _assert_approved(rec)

    risk = await db.get(Risk, rec.risk_id)
    if risk is None:
        return {"success": False, "error": "linked_risk_not_found"}
    product_id = risk.product_id
    store_id = rec.destination_store_id or risk.store_id

    reorder_qty = rec.quantity
    now = _naive_now()

    # Transition linked Action to EXECUTING if present
    act_res = await db.execute(
        select(Action).where(Action.recommendation_id == recommendation_id)
    )
    action = act_res.scalars().first()
    if action:
        action.status = ActionStatus.EXECUTING
        await db.flush()

    # Load product to determine shelf life
    product = await db.get(Product, product_id)
    shelf_life = product.shelf_life_hours if product and product.shelf_life_hours else 72

    # Create newly delivered batch
    new_batch = Batch(
        batch_id=uuid.uuid4(),
        store_id=store_id,
        product_id=product_id,
        quantity=reorder_qty,
        received_at=now,
        expires_at=now + timedelta(hours=shelf_life),
    )
    db.add(new_batch)

    inv_result = await db.execute(
        select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
    )
    inv = inv_result.scalar_one_or_none()

    if inv is not None:
        inv.quantity += reorder_qty
    else:
        db.add(Inventory(store_id=store_id, product_id=product_id, quantity=reorder_qty))

    await db.flush()

    await bus.publish(
        db,
        "REORDER_EXECUTED",
        "recommendation",
        recommendation_id,
        {
            "recommendation_id": str(recommendation_id),
            "store_id":   str(store_id),
            "product_id": str(product_id),
            "quantity":   reorder_qty,
        },
        persist=True,
    )

    return {"success": True, "reordered_quantity": reorder_qty, "store_id": str(store_id)}


async def apply_discount(
    db: AsyncSession,
    recommendation_id: uuid.UUID,
) -> dict:
    """MUTATION: Apply discount (simulated: emits DISCOUNT_APPLIED event, no price mutation).

    In a real system this would push price override to the POS / app.
    In the simulator we record the intent via the event bus.
    """
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        return {"success": False, "error": "recommendation_not_found"}

    if _enum_val(rec.status).lower() == "executed":
        return {"success": False, "error": "already executed"}

    _assert_approved(rec)

    risk = await db.get(Risk, rec.risk_id)
    if risk is None:
        return {"success": False, "error": "linked_risk_not_found"}

    # Transition linked Action to EXECUTING if present
    act_res = await db.execute(
        select(Action).where(Action.recommendation_id == recommendation_id)
    )
    action = act_res.scalars().first()
    if action:
        action.status = ActionStatus.EXECUTING
        await db.flush()

    discount_pct = 0.20

    await bus.publish(
        db,
        "DISCOUNT_APPLIED",
        "recommendation",
        recommendation_id,
        {
            "recommendation_id": str(recommendation_id),
            "store_id":    str(risk.store_id),
            "product_id":  str(risk.product_id),
            "discount_pct": discount_pct,
            "at_risk_quantity": rec.quantity,
        },
        persist=True,
    )

    return {"success": True, "discount_pct": discount_pct, "at_risk_quantity": rec.quantity}


async def recalculate_options(
    db: AsyncSession,
    risk_id: uuid.UUID,
) -> dict:
    """Trigger Decision Engine re-evaluation for a risk.

    Returns {"new_recommendation_id": str | None, "action_type": str | None}.
    """
    from backend.services.decision.engine import DecisionOrchestrator
    orchestrator = DecisionOrchestrator()
    new_rec = await orchestrator.run(db, risk_id)
    if new_rec is None:
        return {"new_recommendation_id": None, "action_type": None}
    return {
        "new_recommendation_id": str(new_rec.recommendation_id),
        "action_type": _enum_val(new_rec.action_type),
    }


async def log_agent_event(
    db: AsyncSession,
    event_type: str,
    entity_id: uuid.UUID,
    payload: dict,
) -> dict:
    """Write an audit event to the EventBus."""
    await bus.publish(db, event_type, "agent", entity_id, payload, persist=True)
    return {"event_type": event_type, "entity_id": str(entity_id)}
