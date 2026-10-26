"""Grocer v1.0 — 3-Lock Payment Safety Gate & Checkout Executor.

Enforces:
1. Lock 1 (Authority): Physical button tap only (`pay:<approval_id>`); text "yes" strictly rejected.
2. Lock 2 (Truth): Live cart re-verification (100% in stock, integer paise match, ₹1 price drift abort, ₹1,000 launch cap).
3. Lock 3 (Exactly-Once): Atomic PostgreSQL CAS on grocer.approvals + pre-checkout order snapshot.
4. WhatsApp CTA URL Button: HTTPS bridgeUrl strictly formatted; upi:// schemes rejected.
5. Durable Background Poller: check_payment_status monitoring with FOR UPDATE SKIP LOCKED.
6. Post-Payment Session Reset (ADR 0010): Purges session basket on settlement.
7. Multi-Store Split Orders (ADR 0007): Unified receipt with split tracking.
8. Order Cancellation Escalation (ADR 0007): Swiggy Care phone escalation (080-67466729).
9. Post-Order Additions (ADR 0009): Dark store locked order protection + separate 1-tap reorder.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import httpx

from backend.agent.approval import (
    ApprovalRecord,
    compute_cart_fingerprint,
)
from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.customer_advocate import extract_cart_to_pay_paise
from backend.agent.formatters import (
    SWIGGY_CARE_PHONE,
    format_multi_store_split_receipt,
    get_order_cancellation_instructions,
    handle_post_order_addition,
)
from backend.integrations.commerce.schemas import (
    CartData,
    CheckoutData,
    PaymentStatusData,
    TrackOrderData,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.checkout_executor")

DEFAULT_LAUNCH_CAP_PAISE = 100000  # ₹1,000 launch safety cap

__all__ = [
    "DEFAULT_LAUNCH_CAP_PAISE",
    "SWIGGY_CARE_PHONE",
    "CheckoutExecutionResult",
    "CheckoutLockError",
    "LockValidationResult",
    "SettlementResult",
    "check_and_settle_payment",
    "execute_3_lock_checkout",
    "format_multi_store_split_receipt",
    "format_whatsapp_cta_url_button",
    "get_order_cancellation_instructions",
    "handle_post_order_addition",
    "poll_in_flight_deliveries_batch",
    "poll_pending_checkouts_batch",
    "verify_lock_1_authority",
    "verify_lock_2_truth",
]


class CheckoutLockError(Exception):
    """Raised when any of the 3 checkout locks fail."""


@dataclass
class LockValidationResult:
    passed: bool
    lock_name: str
    reason: str = ""


@dataclass
class CheckoutExecutionResult:
    success: bool
    order_id: str | None = None
    paas_id: str | None = None
    bridge_url: str | None = None
    cta_button: dict[str, Any] | None = None
    receipt_text: str = ""
    error_message: str | None = None
    order_ids: list[str] = field(default_factory=list)


@dataclass
class SettlementResult:
    confirmed: bool
    order_id: str
    status: str
    tracking: TrackOrderData | None = None
    message: str = ""


def verify_lock_1_authority(
    message_type: str,
    button_id: str | None,
    expected_approval_id: str | None = None,
) -> LockValidationResult:
    """Lock 1: Customer must physically tap the WhatsApp interactive button [Pay ₹X].

    Text 'yes', 'confirm', or 'proceed' is strictly rejected.
    If expected_approval_id is passed, button_id must match pay:<expected_approval_id>.
    """
    if not (message_type in ("button_reply", "interactive") and button_id and button_id.startswith("pay:")):
        return LockValidationResult(
            passed=False,
            lock_name="Lock 1 (Authority)",
            reason=(
                "An order can only be placed by physically tapping the WhatsApp payment button. "
                "Typing 'yes', 'proceed', or 'confirm' cannot authorize spending money."
            ),
        )

    if expected_approval_id:
        expected_btn = f"pay:{expected_approval_id}"
        if button_id != expected_btn:
            return LockValidationResult(
                passed=False,
                lock_name="Lock 1 (Authority)",
                reason=(
                    "This payment button does not match the active receipt approval. "
                    "Please tap the button on your latest receipt."
                ),
            )

    return LockValidationResult(passed=True, lock_name="Lock 1 (Authority)")


def verify_lock_2_truth(
    approval: ApprovalRecord,
    live_cart: CartData,
    max_launch_cap_paise: int = DEFAULT_LAUNCH_CAP_PAISE,
) -> LockValidationResult:
    """Lock 2: Live cart re-verification against approved receipt.

    Checks:
    1. 100% in stock and serviceable (zero removed or out-of-stock items).
    2. Canonical SHA-256 fingerprint matches approved items and destination.
    3. Price drift check: aborts if live price shifted by >= ₹1 (100 paise) per ADR 0002.
    4. Launch safety cap check (default ₹1,000).
    """
    if not live_cart.items:
        return LockValidationResult(
            passed=False,
            lock_name="Lock 2 (Truth)",
            reason="Your basket is empty. Please add items before checking out.",
        )

    if bool(live_cart.removedOutOfStockItems):
        return LockValidationResult(
            passed=False,
            lock_name="Lock 2 (Truth)",
            reason="Some items in your basket just went out of stock. Please review your updated basket.",
        )

    for it in live_cart.items:
        if not it.isInStockAndAvailable:
            return LockValidationResult(
                passed=False,
                lock_name="Lock 2 (Truth)",
                reason=f"'{it.itemName}' is currently unavailable at your local dark store.",
            )

    live_to_pay_paise = extract_cart_to_pay_paise(live_cart)

    # Price drift check (ADR 0002): abort if price changed by ₹1 or more
    price_drift_paise = abs(live_to_pay_paise - approval.to_pay_paise)
    if price_drift_paise >= 100:
        drift_rs = format_paise_to_rupees(price_drift_paise)
        return LockValidationResult(
            passed=False,
            lock_name="Lock 2 (Truth)",
            reason=(
                f"Store price shifted by {drift_rs} since your receipt was shown. "
                "Checkout aborted to protect your wallet. Please review your updated receipt."
            ),
        )

    # Canonical fingerprint match (verifies basket items, quantities, paise, and destination)
    live_fingerprint = compute_cart_fingerprint(
        items=live_cart.items,
        to_pay_paise=live_to_pay_paise,
        address_id=approval.address_id,
    )
    if live_fingerprint != approval.fingerprint:
        return LockValidationResult(
            passed=False,
            lock_name="Lock 2 (Truth)",
            reason="Basket contents changed since approval. Please review your updated receipt.",
        )

    # Launch safety cap check (ADR 0006)
    if live_to_pay_paise > max_launch_cap_paise:
        cap_rs = format_paise_to_rupees(max_launch_cap_paise)
        return LockValidationResult(
            passed=False,
            lock_name="Lock 2 (Truth)",
            reason=(
                f"Order total exceeds the {cap_rs} launch safety limit. "
                "Please tap 'Raise Limit' to authorize larger orders."
            ),
        )

    return LockValidationResult(passed=True, lock_name="Lock 2 (Truth)")


def format_whatsapp_cta_url_button(bridge_url: str, amount_paise: int) -> dict[str, Any]:
    """Format Swiggy HTTPS bridgeUrl into WhatsApp CTA URL button.

    Strictly rejects 'upi://' schemes per Meta WhatsApp API requirements.
    """
    if not bridge_url.startswith("https://"):
        raise ValueError(f"Strict scheme violation: bridgeUrl must use 'https://', got '{bridge_url}'")

    amount_rs = format_paise_to_rupees(amount_paise)
    return {
        "type": "cta_url",
        "parameters": {
            "display_text": f"Pay {amount_rs} (UPI / Card)",
            "url": bridge_url,
        },
    }


async def execute_3_lock_checkout(
    conn: Any,
    swiggy_client: SwiggyClient,
    user_id: str,
    approval_id: str,
    message_type: str,
    button_id: str | None,
    payment_method: str = "UPI",
) -> CheckoutExecutionResult:
    """Execute the full 3-Lock Safety Gate checkout sequence.

    1. Lock 1: Verify physical button authorization and approval ID match.
    2. Lock 3: Atomic PostgreSQL CAS on grocer.approvals (status: 'shown' -> 'consuming').
    3. Lock 2: Verify live dark store cart (truth, stock, paise match, drift).
    4. Snapshot pre-checkout order IDs.
    5. Place order via Swiggy MCP checkout tool.
    6. Deliver HTTPS bridgeUrl via WhatsApp CTA URL button.
    """
    # 1. Lock 1 (Authority) with strict approval ID verification
    l1 = verify_lock_1_authority(message_type, button_id, expected_approval_id=approval_id)
    if not l1.passed:
        return CheckoutExecutionResult(success=False, error_message=l1.reason)

    # 2. Lock 3 (Exactly-Once Atomic CAS)
    cas_row = await conn.fetchrow(
        """
        UPDATE grocer.approvals
        SET status = 'consuming'
        WHERE id = $1 AND status = 'shown' AND expires_at > now()
        RETURNING id, user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at;
        """,
        approval_id,
    )

    if not cas_row:
        logger.warning("Lock 3 CAS failed for approval %s: already consumed, expired, or absent", approval_id)
        return CheckoutExecutionResult(
            success=False,
            error_message="This payment request has already been processed or has expired. Please create a fresh basket.",
        )

    approval = ApprovalRecord(
        id=str(cas_row["id"]),
        user_id=str(cas_row["user_id"]),
        fingerprint=cas_row["fingerprint"],
        to_pay_paise=int(cas_row["to_pay_paise"]),
        address_id=cas_row["address_id"],
        snapshot=json.loads(cas_row["snapshot"]) if isinstance(cas_row["snapshot"], str) else cas_row["snapshot"],
        status=cas_row["status"],
        expires_at=cas_row["expires_at"],
    )

    # 3. Lock 2 (Truth / Live Cart Re-verification)
    live_cart = swiggy_client.get_cart(address_id=approval.address_id)
    session_row = await conn.fetchrow(
        "SELECT budget_cap_paise FROM grocer.sessions WHERE user_id = $1::uuid;",
        user_id,
    )
    budget_cap = (
        int(session_row["budget_cap_paise"])
        if session_row and session_row["budget_cap_paise"]
        else DEFAULT_LAUNCH_CAP_PAISE
    )
    l2 = verify_lock_2_truth(approval, live_cart, max_launch_cap_paise=budget_cap)
    if not l2.passed:
        # Revert CAS state to expired on validation failure
        await conn.execute("UPDATE grocer.approvals SET status = 'expired' WHERE id = $1::uuid;", approval_id)
        if "launch safety limit" in l2.reason:
            live_to_pay = extract_cart_to_pay_paise(live_cart)
            return CheckoutExecutionResult(
                success=False,
                error_message=l2.reason,
                cta_button={
                    "type": "button",
                    "sub_type": "quick_reply",
                    "parameters": {
                        "button_id": f"budget:raise:{approval_id}:{live_to_pay}",
                        "title": f"Raise Limit to {format_paise_to_rupees(live_to_pay)}",
                    },
                },
            )
        return CheckoutExecutionResult(success=False, error_message=l2.reason)

    # 4. Snapshot pre-checkout order IDs (Fail safe with warning on external call drop)
    try:
        pre_orders = swiggy_client.get_orders(count=10, order_type="INSTAMART", active_only=True)
        known_order_ids = [o.orderId for o in pre_orders.orders]
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning("Pre-checkout order snapshot failed; proceeding with empty baseline: %s", exc)
        known_order_ids = []

    # 5. Insert inflight record into grocer.checkouts
    checkout_db_id = await conn.fetchval(
        """
        INSERT INTO grocer.checkouts (
            approval_id,
            user_id,
            payment_method,
            address_id,
            known_order_ids,
            status,
            approved_to_pay_paise
        )
        VALUES ($1, $2, $3, $4, $5, 'attempting', $6)
        RETURNING id;
        """,
        approval.id,
        user_id,
        payment_method.lower(),
        approval.address_id,
        json.dumps(known_order_ids),
        approval.to_pay_paise,
    )

    # 6. Call live Swiggy MCP checkout tool
    try:
        checkout_res: CheckoutData = swiggy_client.checkout(
            payment_method=payment_method,
            address_id=approval.address_id,
        )
    except Exception:
        await conn.execute(
            "UPDATE grocer.checkouts SET status = 'failed' WHERE id = $1;",
            checkout_db_id,
        )
        await conn.execute(
            "UPDATE grocer.approvals SET status = 'expired' WHERE id = $1;",
            approval_id,
        )
        logger.exception("Swiggy checkout tool call failed")
        return CheckoutExecutionResult(
            success=False,
            error_message="Swiggy checkout service encountered a temporary error. Please try again in a moment.",
        )

    # 7. Collect every order id: one order normally, one per dark store when split
    if checkout_res.orders:
        order_ids = [o.orderId for o in checkout_res.orders if o.orderId]
        split_failures = [o for o in checkout_res.orders if not o.orderId or o.error]
    else:
        order_ids = [checkout_res.orderId] if checkout_res.orderId else []
        split_failures = []

    if not order_ids:
        await conn.execute(
            "UPDATE grocer.checkouts SET status = 'failed' WHERE id = $1;",
            checkout_db_id,
        )
        await conn.execute(
            "UPDATE grocer.approvals SET status = 'expired' WHERE id = $1;",
            approval_id,
        )
        reason = next((o.error for o in split_failures if o.error), None)
        return CheckoutExecutionResult(
            success=False,
            error_message=reason or "Swiggy did not return an order id. Nothing was placed.",
        )

    # 8. Format WhatsApp CTA URL button (enforcing HTTPS) when Swiggy returned a pay link
    bridge_url = checkout_res.bridgeUrl or None
    cta_btn = (
        format_whatsapp_cta_url_button(bridge_url, approval.to_pay_paise) if bridge_url else None
    )

    # Cash and Swiggy Money place the order inline: nothing to poll for payment.
    placed_inline = (
        (checkout_res.paymentMethod or "").upper() in {"CASH", "COD", "SWIGGYPAY"}
        and not checkout_res.paasId
    )

    # 9. Record payment state and every order id
    await conn.execute(
        """
        UPDATE grocer.checkouts
        SET status = $1,
            swiggy_order_id = $2,
            swiggy_order_ids = $3::jsonb,
            paas_id = $4,
            bridge_url = $5,
            response_total_paise = $6,
            updated_at = now()
        WHERE id = $7;
        """,
        "placed" if placed_inline else "pending_payment",
        order_ids[0],
        json.dumps(order_ids),
        checkout_res.paasId,
        bridge_url,
        approval.to_pay_paise,
        checkout_db_id,
    )
    if placed_inline:
        await conn.execute(
            "UPDATE grocer.approvals SET status = 'consumed' WHERE id = $1;",
            approval_id,
        )
        await conn.execute(
            """
            UPDATE grocer.sessions
            SET history = '[]'::jsonb, one_time_destination_id = NULL, last_active_at = now()
            WHERE user_id = $1;
            """,
            user_id,
        )

    total = format_paise_to_rupees(approval.to_pay_paise)
    destination = checkout_res.deliveryLabel or "Saved Address"
    if len(order_ids) > 1:
        lines = [f"Order #{oid}" for oid in order_ids]
        receipt = (
            f"🛒 *Split across {len(order_ids)} dark stores*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}\n\n"
            + "\n".join(lines)
        )
        if split_failures:
            receipt += f"\n\n⚠️ {len(split_failures)} part of your basket could not be ordered."
        if bridge_url:
            receipt += "\n\nTap the secure button below to pay via UPI or card on Swiggy."
    elif bridge_url:
        receipt = (
            f"💳 *Order #{order_ids[0]} Initiated*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}\n\n"
            f"Tap the secure button below to pay via UPI or card on Swiggy."
        )
    else:
        receipt = (
            f"✅ *Order #{order_ids[0]} placed*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}"
        )
    if len(order_ids) == 1 and split_failures:
        receipt += f"\n\n⚠️ {len(split_failures)} item group could not be ordered."

    return CheckoutExecutionResult(
        success=True,
        order_id=order_ids[0],
        paas_id=checkout_res.paasId,
        bridge_url=bridge_url,
        cta_button=cta_btn,
        receipt_text=receipt,
        order_ids=order_ids,
    )


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
        status_data: PaymentStatusData = swiggy_client.check_payment_status(
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
                confirm_res = swiggy_client.confirm_order(order_id=oid, paas_id=paas_id)
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
            one_time_destination_id = NULL,
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
            swiggy_client.track_order(primary_order_id, lat, lng)
            if lat is not None and lng is not None
            else None
        )
        eta_desc = tracking.status.etaText if tracking else None
        if not eta_desc and tracking and tracking.status.etaMinutes:
            eta_desc = f"{tracking.status.etaMinutes} mins"
        if tracking:
            map_url = f"https://swiggy.com/track/{primary_order_id}"
            msg = (
                f"🎉 *Payment Confirmed!* Swiggy dark store is packing {order_label}.\n"
                f"🛵 Status: {tracking.status.statusMessage} ({eta_desc or '10-15 mins'})\n"
                f"Live Map: {map_url}"
            )
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


async def _client_for_user(user_id: str) -> SwiggyClient | None:
    """Build a Swiggy client with this user's token, refreshing it once if expired."""
    from backend.integrations.commerce.token_vault import resolve_user_token

    token = await resolve_user_token(uuid.UUID(user_id))
    return SwiggyClient(auth_token=token) if token else None


async def poll_pending_checkouts_batch(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient | None = None,
    max_age_minutes: int = 5,
) -> list[SettlementResult]:
    """Durable background poller checking pending Swiggy checkouts using PostgreSQL FOR UPDATE SKIP LOCKED.

    Picks pending payments, checks status against Swiggy MCP, and finalizes settlement or marks timed out.
    When no client is passed, each row uses its own customer's token.
    """
    results: list[SettlementResult] = []
    async with pool.acquire() as conn, conn.transaction():
        # Atomic row lock on eligible pending checkout records
        rows = await conn.fetch(
            """
            SELECT id, approval_id, user_id, swiggy_order_id, swiggy_order_ids, paas_id, created_at
            FROM grocer.checkouts
            WHERE (status = 'pending_payment' AND created_at > now() - interval '5 minutes')
               OR (status = 'confirming' AND created_at > now() - interval '2 hours')
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 10;
            """
        )

        for row in rows:
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

            client = swiggy_client or await _client_for_user(user_id)
            if client is None:
                logger.warning("Skipping checkout %s: no usable Swiggy token", approval_id)
                continue

            res = await check_and_settle_payment(
                conn=conn,
                swiggy_client=client,
                user_id=user_id,
                approval_id=approval_id,
                order_ids=order_ids,
                paas_id=paas_id,
            )
            results.append(res)

        # Mark never-paid checkouts older than 5 minutes as failed. Rows in
        # 'confirming' are left alone because money may already have moved.
        await conn.execute(
            """
            UPDATE grocer.checkouts
            SET status = 'failed', updated_at = now()
            WHERE status = 'pending_payment'
              AND created_at <= now() - interval '5 minutes';
            """
        )

    return results


async def poll_in_flight_deliveries_batch(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient | None = None,
    order_id: str | None = None,
    user_id: str | None = None,
    limit: int = 20,
) -> list[Any]:
    """Poll in-flight 'placed' orders and transition through Picked Up and Delivered milestones."""
    from backend.agent.delivery_tracker import (
        MILESTONE_CONFIRMED,
        MILESTONE_DELIVERED,
        MILESTONE_PICKED_UP,
        format_milestone_notification,
        resolve_delivery_milestone,
    )

    notifications: list[Any] = []
    async with pool.acquire() as conn, conn.transaction():
        # Build dynamic query supporting optional order_id/user_id filtering
        conditions = ["status IN ('placed', 'out_for_delivery')", "created_at > now() - interval '2 hours'"]
        params: list[Any] = []
        if order_id:
            params.append(order_id)
            conditions.append(f"swiggy_order_id = ${len(params)}")
        if user_id:
            params.append(user_id)
            conditions.append(f"user_id = ${len(params)}::uuid")

        params.append(limit)
        limit_param = f"${len(params)}"

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT id, user_id, swiggy_order_id, status
            FROM grocer.checkouts
            WHERE {where_clause}
            ORDER BY created_at DESC
            FOR UPDATE SKIP LOCKED
            LIMIT {limit_param};
        """
        rows = await conn.fetch(query, *params)

        for row in rows:
            checkout_id = row["id"]
            order_id = row["swiggy_order_id"]
            current_status = row["status"]
            if not order_id:
                continue

            client = swiggy_client or await _client_for_user(str(row["user_id"]))
            if client is None:
                logger.warning("Skipping delivery poll for %s: no usable Swiggy token", order_id)
                continue

            try:
                delivery_status = client.get_delivery_status(order_id)
                milestone = resolve_delivery_milestone(
                    status_text=delivery_status.statusText,
                    delivered=delivery_status.delivered,
                    cancelled=delivery_status.cancelled,
                )
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.warning("Failed to poll delivery status for %s: %s", order_id, exc)
                continue

            if not milestone:
                continue

            # Check if order transitioned to DELIVERED
            if milestone == MILESTONE_DELIVERED and current_status != "delivered":
                await conn.execute(
                    "UPDATE grocer.checkouts SET status = 'delivered', updated_at = now() WHERE id = $1::uuid;",
                    checkout_id,
                )
                note = format_milestone_notification(order_id, MILESTONE_DELIVERED)
                notifications.append(note)
            elif milestone == MILESTONE_PICKED_UP and current_status != "out_for_delivery":
                await conn.execute(
                    "UPDATE grocer.checkouts SET status = 'out_for_delivery', updated_at = now() WHERE id = $1::uuid;",
                    checkout_id,
                )
                note = format_milestone_notification(
                    order_id,
                    MILESTONE_PICKED_UP,
                    eta_text=delivery_status.etaText,
                )
                notifications.append(note)
            elif milestone == MILESTONE_CONFIRMED and current_status == "placed":
                note = format_milestone_notification(
                    order_id,
                    MILESTONE_CONFIRMED,
                    eta_text=delivery_status.etaText,
                )
                notifications.append(note)

    return notifications
