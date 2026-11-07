"""Grocer — Checkout settlement, recovery, and background pollers.

Polls Swiggy payment status, reconciles interrupted checkout attempts, and
latches delivery milestones. Placement and the 3-lock gate live in
backend.agent.checkout_executor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import asyncpg
import httpx

from backend.agent.checkout_executor import _new_order_ids
from backend.integrations.commerce.schemas import PaymentStatusData, TrackOrderData
from backend.integrations.commerce.swiggy_client import (
    SwiggyAuthExpiredError,
    SwiggyClient,
)
from backend.integrations.commerce.token_vault import resolve_user_client

logger = logging.getLogger("grocer.checkout_settlement")

CHECKOUT_ATTEMPT_STALE_SECONDS = 60


@dataclass
class SettlementResult:
    confirmed: bool
    order_id: str
    status: str
    tracking: TrackOrderData | None = None
    message: str = ""


async def check_and_settle_payment(
    conn: Any,
    swiggy_client: SwiggyClient,
    user_id: str,
    approval_id: str,
    order_id: str | None = None,
    paas_id: str | None = None,
    order_ids: list[str] | None = None,
) -> SettlementResult:
    """Poll Swiggy check_payment_status for every order and finalize the checkout."""
    ids = order_ids or ([order_id] if order_id else [])
    if not ids:
        return SettlementResult(
            confirmed=False,
            order_id="",
            status="MISSING_ORDER",
            message="No Swiggy order id was recorded for this checkout.",
        )
    primary_order_id = ids[0]

    last_status = "PENDING"
    paid = 0
    for oid in ids:
        status_data: PaymentStatusData = await asyncio.to_thread(
            swiggy_client.check_payment_status,
            paas_id=paas_id,
            order_id=oid,
        )
        last_status = status_data.status
        payment_succeeded = (
            status_data.status == "SUCCESS"
            or status_data.isTerminalSuccess
            or status_data.confirmed is True
            or status_data.orderStatus == "PLACED"
        )
        if not payment_succeeded:
            continue

        # UPI checkout returns PENDING_PAYMENT; finalize explicitly only when
        # Swiggy did not auto-confirm. confirm_order is idempotent.
        if not status_data.confirmed and paas_id:
            try:
                confirm_res = await asyncio.to_thread(
                    swiggy_client.confirm_order,
                    order_id=oid,
                    paas_id=paas_id,
                )
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.warning("confirm_order failed for %s: %s", oid, exc)
                continue
            if confirm_res.result != "success":
                continue
        paid += 1

    if paid < len(ids):
        if paid:
            # Money already moved for at least one order: keep polling, never
            # let the 5-minute timeout mark it failed.
            await conn.execute(
                "UPDATE grocer.checkouts SET status = 'confirming', updated_at = now() WHERE approval_id = $1;",
                approval_id,
            )
        return SettlementResult(
            confirmed=False,
            order_id=primary_order_id,
            status="PENDING_CONFIRM" if paid else last_status,
            message="Payment is still pending. Waiting for settlement.",
        )

    # 1. Update checkouts and approvals to completed state
    await conn.execute(
        """
        UPDATE grocer.checkouts
        SET status = 'placed', swiggy_order_ids = $2::jsonb, updated_at = now()
        WHERE approval_id = $1;
        """,
        approval_id,
        json.dumps(ids),
    )
    await conn.execute(
        """
        UPDATE grocer.approvals
        SET status = 'consumed'
        WHERE id = $1;
        """,
        approval_id,
    )

    # 2. Post-Payment Session Reset (ADR 0010: clear basket and dialogue state)
    await conn.execute(
        """
        UPDATE grocer.sessions
        SET history = '[]'::jsonb,
            last_active_at = now()
        WHERE user_id = $1;
        """,
        user_id,
    )

    # 3. Transition to real-time rider tracking. track_order needs lat/lng, so use
    # coords saved when the address was created, then the pin saved on the session.
    coords = await conn.fetchrow(
        """
        SELECT ac.latitude, ac.longitude
        FROM grocer.checkouts c
        LEFT JOIN grocer.address_coords ac ON ac.address_id = c.address_id
        WHERE c.approval_id = $1;
        """,
        approval_id,
    )
    lat = coords["latitude"] if coords else None
    lng = coords["longitude"] if coords else None
    if lat is None or lng is None:
        session_coords = await conn.fetchrow(
            "SELECT delivery_latitude, delivery_longitude FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )
        lat = session_coords["delivery_latitude"] if session_coords else None
        lng = session_coords["delivery_longitude"] if session_coords else None

    order_label = (
        f"orders #{', #'.join(ids)}" if len(ids) > 1 else f"order #{primary_order_id}"
    )
    try:
        tracking = (
            await asyncio.to_thread(swiggy_client.track_order, primary_order_id, lat, lng)
            if lat is not None and lng is not None
            else None
        )
        eta_desc = tracking.status.etaText if tracking else None
        if not eta_desc and tracking and tracking.status.etaMinutes:
            eta_desc = f"{tracking.status.etaMinutes} mins"
        if tracking:
            status = tracking.status.statusMessage
            msg = (
                f"🎉 *Payment Confirmed!* Swiggy dark store is packing {order_label}.\n"
                f"🛵 Status: {status}"
            )
            if eta_desc:
                msg += f" (ETA {eta_desc})"
        else:
            msg = f"🎉 *Payment Confirmed!* Swiggy dark store is packing {order_label}."
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError):
        tracking = None
        msg = f"🎉 *Payment Confirmed!* Swiggy dark store is packing {order_label}."

    return SettlementResult(
        confirmed=True,
        order_id=primary_order_id,
        status="PLACED",
        tracking=tracking,
        message=msg,
    )


async def reconcile_attempting_checkouts(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient | None = None,
    older_than_seconds: int = CHECKOUT_ATTEMPT_STALE_SECONDS,
) -> list[str]:
    """Resolve checkouts whose process died between the Swiggy call and the record.

    A new order compared to the pre-checkout snapshot means the order exists.
    No new order means nothing was placed and the approval may be paid again.
    Returns the ids of the checkout rows that were resolved.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, approval_id, user_id, known_order_ids
            FROM grocer.checkouts
            WHERE status IN ('attempting', 'unknown')
              AND created_at <= now() - $1 * interval '1 second'
            ORDER BY created_at ASC
            LIMIT 10;
            """,
            older_than_seconds,
        )

    resolved: list[str] = []
    for row in rows:
        raw_known = row["known_order_ids"]
        known_order_ids = (
            json.loads(raw_known) if isinstance(raw_known, str) else list(raw_known or [])
        )
        user_id = str(row["user_id"])
        client = swiggy_client or await resolve_user_client(user_id)
        if client is None:
            logger.warning("Cannot reconcile checkout %s: no usable Swiggy token", row["id"])
            continue

        try:
            orders = await asyncio.to_thread(client.get_orders, 20, "INSTAMART", True)
        except (
            httpx.HTTPError,
            OSError,
            ValueError,
            KeyError,
            RuntimeError,
            SwiggyAuthExpiredError,
        ) as exc:
            logger.warning("Reconcile failed for checkout %s: %s", row["id"], exc)
            continue

        new_order_ids = _new_order_ids(orders, known_order_ids)
        async with pool.acquire() as conn, conn.transaction():
            if new_order_ids:
                await conn.execute(
                    """
                    UPDATE grocer.checkouts
                    SET status = 'confirming',
                        swiggy_order_id = $2,
                        swiggy_order_ids = $3::jsonb,
                        updated_at = now()
                    WHERE id = $1;
                    """,
                    row["id"],
                    new_order_ids[0],
                    json.dumps(new_order_ids),
                )
                await conn.execute(
                    "UPDATE grocer.approvals SET status = 'consumed' WHERE id = $1;",
                    row["approval_id"],
                )
            else:
                await conn.execute(
                    "UPDATE grocer.checkouts SET status = 'failed', updated_at = now() WHERE id = $1;",
                    row["id"],
                )
                await conn.execute(
                    "UPDATE grocer.approvals SET status = 'expired' WHERE id = $1 AND status = 'consuming';",
                    row["approval_id"],
                )
        resolved.append(str(row["id"]))

    return resolved


async def poll_pending_checkouts_batch(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient | None = None,
    max_age_minutes: int = 5,
) -> list[SettlementResult]:
    """Durable background poller checking pending Swiggy checkouts using PostgreSQL FOR UPDATE SKIP LOCKED.

    Picks pending payments, checks status against Swiggy MCP, and finalizes settlement or marks timed out.
    When no client is passed, each row uses its own customer's token.
    """
    await reconcile_attempting_checkouts(pool, swiggy_client)

    results: list[SettlementResult] = []
    # Candidates are read without locks. Each row is then claimed and settled in
    # its own short transaction, so a slow or failed checkout cannot hold the
    # whole batch or roll back settlements that already committed.
    candidates = await pool.fetch(
        """
        SELECT id
        FROM grocer.checkouts
        WHERE (status = 'pending_payment' AND created_at > now() - interval '2 hours')
           OR (status = 'confirming' AND created_at > now() - interval '2 hours')
        ORDER BY created_at ASC
        LIMIT 10;
        """
    )

    for candidate in candidates:
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, approval_id, user_id, swiggy_order_id, swiggy_order_ids, paas_id
                FROM grocer.checkouts
                WHERE id = $1
                  AND ((status = 'pending_payment' AND created_at > now() - interval '2 hours')
                    OR (status = 'confirming' AND created_at > now() - interval '2 hours'))
                FOR UPDATE SKIP LOCKED;
                """,
                candidate["id"],
            )
            if row is None:
                continue

            approval_id = str(row["approval_id"])
            user_id = str(row["user_id"])
            paas_id = row["paas_id"]

            raw_ids = row["swiggy_order_ids"]
            if isinstance(raw_ids, str):
                order_ids = json.loads(raw_ids)
            else:
                order_ids = list(raw_ids or [])
            if not order_ids and row["swiggy_order_id"]:
                order_ids = [row["swiggy_order_id"]]
            if not order_ids:
                continue

            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                logger.warning("Skipping checkout %s: no usable Swiggy token", approval_id)
                continue

            try:
                res = await check_and_settle_payment(
                    conn=conn,
                    swiggy_client=client,
                    user_id=user_id,
                    approval_id=approval_id,
                    order_ids=order_ids,
                    paas_id=paas_id,
                )
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                RuntimeError,
                OSError,
                SwiggyAuthExpiredError,
            ) as exc:
                # An unverified payment is never marked failed.
                logger.warning("Settlement failed for %s: %s", approval_id, exc)
                continue

            # Mark a never-paid checkout older than 5 minutes as failed in the
            # same row transaction. Rows in 'confirming' are left alone because
            # money may already have moved.
            await conn.execute(
                """
                UPDATE grocer.checkouts
                SET status = 'failed', updated_at = now()
                WHERE status = 'pending_payment'
                  AND created_at <= now() - interval '5 minutes'
                  AND id = $1;
                """,
                row["id"],
            )
            results.append(res)

    return results


async def poll_in_flight_deliveries_batch(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient | None = None,
    order_id: str | None = None,
    user_id: str | None = None,
    limit: int = 20,
) -> list[Any]:
    """Poll in-flight 'placed' orders and send each milestone exactly once.

    Split orders carry several order ids in one checkout row, so every id is
    polled and latched separately in `notified_milestones`.
    """
    from backend.agent.delivery_tracker import (
        MILESTONE_CONFIRMED,
        MILESTONE_DELIVERED,
        MILESTONE_PICKED_UP,
        format_milestone_notification,
        resolve_delivery_milestone,
    )

    ranks = {
        MILESTONE_CONFIRMED: 1,
        MILESTONE_PICKED_UP: 2,
        MILESTONE_DELIVERED: 3,
    }

    notifications: list[Any] = []
    # Candidate ids are read without locks; each checkout is then claimed and
    # processed in its own transaction so one slow order cannot hold the batch.
    conditions = [
        "status IN ('placed', 'out_for_delivery')",
        "created_at > now() - interval '2 hours'",
    ]
    params: list[Any] = []
    if order_id:
        params.append(order_id)
        conditions.append(f"(swiggy_order_id = ${len(params)} OR swiggy_order_ids ? ${len(params)})")
    if user_id:
        params.append(user_id)
        conditions.append(f"user_id = ${len(params)}::uuid")

    params.append(limit)
    limit_param = f"${len(params)}"
    candidates = await pool.fetch(
        f"""
        SELECT id
        FROM grocer.checkouts
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC
        LIMIT {limit_param};
        """,
        *params,
    )

    for candidate in candidates:
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, user_id, swiggy_order_id, swiggy_order_ids, status, notified_milestones
                FROM grocer.checkouts
                WHERE id = $1
                  AND status IN ('placed', 'out_for_delivery')
                  AND created_at > now() - interval '2 hours'
                FOR UPDATE SKIP LOCKED;
                """,
                candidate["id"],
            )
            if row is None:
                continue

            checkout_id = row["id"]
            current_status = row["status"]
            raw_ids = row["swiggy_order_ids"]
            order_ids = (
                json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            )
            if not order_ids and row["swiggy_order_id"]:
                order_ids = [row["swiggy_order_id"]]
            if not order_ids:
                continue

            raw_sent = row["notified_milestones"]
            sent = json.loads(raw_sent) if isinstance(raw_sent, str) else list(raw_sent or [])

            client = swiggy_client or await resolve_user_client(str(row["user_id"]))
            if client is None:
                logger.warning("Skipping delivery poll for %s: no usable Swiggy token", order_ids[0])
                continue

            best_milestone: str | None = None
            for oid in order_ids:
                try:
                    delivery_status = await asyncio.to_thread(client.get_delivery_status, oid)
                    milestone = resolve_delivery_milestone(
                        status_text=delivery_status.statusText,
                        delivered=delivery_status.delivered,
                        cancelled=delivery_status.cancelled,
                    )
                except (
                    httpx.HTTPError,
                    ValueError,
                    KeyError,
                    RuntimeError,
                    OSError,
                    SwiggyAuthExpiredError,
                ) as exc:
                    logger.warning("Failed to poll delivery status for %s: %s", oid, exc)
                    continue

                if not milestone:
                    continue
                if best_milestone is None or ranks[milestone] > ranks[best_milestone]:
                    best_milestone = milestone

                already_sent = [key for key in sent if key.startswith(f"{oid}:")]
                last_rank = max(
                    (ranks.get(key.split(":", 1)[1], 0) for key in already_sent),
                    default=0,
                )
                if ranks[milestone] <= last_rank:
                    continue

                note = format_milestone_notification(
                    oid,
                    milestone,
                    eta_text=delivery_status.etaText,
                )
                notifications.append(note)
                sent.append(f"{oid}:{milestone}")

            new_status = current_status
            if best_milestone == MILESTONE_DELIVERED:
                new_status = "delivered"
            elif best_milestone == MILESTONE_PICKED_UP:
                new_status = "out_for_delivery"

            await conn.execute(
                """
                UPDATE grocer.checkouts
                SET status = $2, notified_milestones = $3::jsonb, updated_at = now()
                WHERE id = $1::uuid;
                """,
                checkout_id,
                new_status,
                json.dumps(sent),
            )

    return notifications
