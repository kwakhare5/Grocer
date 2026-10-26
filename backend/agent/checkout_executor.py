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
from dataclasses import dataclass
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
        pre_orders = swiggy_client.get_orders(limit=10)
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

    # 7. Format WhatsApp CTA URL button (enforcing HTTPS)
    bridge_url = checkout_res.bridgeUrl or ""
    cta_btn = format_whatsapp_cta_url_button(bridge_url, approval.to_pay_paise)

    # 8. Record pending payment state
    await conn.execute(
        """
        UPDATE grocer.checkouts
        SET status = 'pending_payment',
            swiggy_order_id = $1,
            paas_id = $2,
            bridge_url = $3,
            response_total_paise = $4,
            updated_at = now()
        WHERE id = $5;
        """,
        checkout_res.orderId,
        checkout_res.paasId,
        bridge_url,
        approval.to_pay_paise,
        checkout_db_id,
    )

    receipt = (
        f"💳 *Order #{checkout_res.orderId} Initiated*\n"
        f"Total: {format_paise_to_rupees(approval.to_pay_paise)}\n"
        f"Delivering to: {checkout_res.deliveryLabel or 'Saved Address'}\n\n"
        f"Tap the secure button below to pay via UPI or card on Swiggy."
    )

    return CheckoutExecutionResult(
        success=True,
        order_id=checkout_res.orderId,
        paas_id=checkout_res.paasId,
        bridge_url=bridge_url,
        cta_button=cta_btn,
        receipt_text=receipt,
    )


async def check_and_settle_payment(
    conn: Any,
    swiggy_client: SwiggyClient,
    user_id: str,
    approval_id: str,
    order_id: str,
    paas_id: str | None = None,
) -> SettlementResult:
    """Poll Swiggy check_payment_status and finalize post-payment state transitions."""
    status_data: PaymentStatusData = swiggy_client.check_payment_status(
        paas_id=paas_id,
        order_id=order_id,
    )

    is_confirmed = (
        status_data.status == "SUCCESS"
        or status_data.isTerminalSuccess
        or status_data.confirmed is True
        or status_data.orderStatus == "PLACED"
    )

    if not is_confirmed:
        return SettlementResult(
            confirmed=False,
            order_id=order_id,
            status=status_data.status,
            message="Payment is still pending. Waiting for settlement.",
        )

    # 1. Update checkouts and approvals to completed state
    await conn.execute(
        """
        UPDATE grocer.checkouts
        SET status = 'placed', updated_at = now()
        WHERE approval_id = $1;
        """,
        approval_id,
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

    # 3. Transition to real-time GPS rider tracking (track_order)
    try:
        tracking = swiggy_client.track_order(order_id)
        eta_desc = tracking.status.etaText or (
            f"{tracking.status.etaMinutes} mins" if tracking.status.etaMinutes else "10-15 mins"
        )
        map_url = f"https://swiggy.com/track/{order_id}"
        msg = (
            f"🎉 *Payment Confirmed!* Swiggy dark store is packing order #{order_id}.\n"
            f"🛵 Status: {tracking.status.statusMessage} ({eta_desc})\n"
            f"Live Map: {map_url}"
        )
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError):
        tracking = None
        msg = f"🎉 *Payment Confirmed!* Swiggy dark store is packing order #{order_id}."

    return SettlementResult(
        confirmed=True,
        order_id=order_id,
        status="PLACED",
        tracking=tracking,
        message=msg,
    )


async def poll_pending_checkouts_batch(
    pool: asyncpg.Pool,
    swiggy_client: SwiggyClient,
    max_age_minutes: int = 5,
) -> list[SettlementResult]:
    """Durable background poller checking pending Swiggy checkouts using PostgreSQL FOR UPDATE SKIP LOCKED.

    Picks pending payments, checks status against Swiggy MCP, and finalizes settlement or marks timed out.
    """
    results: list[SettlementResult] = []
    async with pool.acquire() as conn, conn.transaction():
        # Atomic row lock on eligible pending checkout records
        rows = await conn.fetch(
            """
            SELECT id, approval_id, user_id, swiggy_order_id, paas_id, created_at
            FROM grocer.checkouts
            WHERE status = 'pending_payment'
              AND created_at > now() - interval '5 minutes'
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 10;
            """
        )

        for row in rows:
            approval_id = str(row["approval_id"])
            user_id = str(row["user_id"])
            order_id = row["swiggy_order_id"]
            paas_id = row["paas_id"]

            if not order_id:
                continue

            res = await check_and_settle_payment(
                conn=conn,
                swiggy_client=swiggy_client,
                user_id=user_id,
                approval_id=approval_id,
                order_id=order_id,
                paas_id=paas_id,
            )
            results.append(res)

        # Mark expired/timed-out pending checkouts older than 5 minutes as failed
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
    swiggy_client: SwiggyClient,
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

            try:
                delivery_status = swiggy_client.get_delivery_status(order_id)
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
