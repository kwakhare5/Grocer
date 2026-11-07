"""Grocer — 3-Lock Payment Safety Gate & Order Placement.

Enforces:
1. Lock 1 (Authority): Physical button tap only (`pay:<approval_id>`); text "yes" strictly rejected.
2. Lock 2 (Truth): Live cart re-verification (100% in stock, integer paise match, ₹1 price drift abort, ₹1,000 launch cap).
3. Lock 3 (Exactly-Once): Atomic PostgreSQL CAS on grocer.approvals + pre-checkout order snapshot.
4. WhatsApp CTA URL Button: HTTPS bridgeUrl strictly formatted; upi:// schemes rejected.
5. Multi-Store Split Orders (ADR 0007): Unified receipt with split tracking.

Settlement, reconciliation, and background pollers live in checkout_settlement.
"""

from __future__ import annotations

import asyncio
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
from backend.agent.customer_advocate import (
    extract_cart_to_pay_paise,
    get_session_budget_cap,
    parse_price_to_paise,
)
from backend.config import settings
from backend.integrations.commerce.schemas import (
    CartData,
    CheckoutData,
)
from backend.integrations.commerce.swiggy_client import (
    SwiggyAuthExpiredError,
    SwiggyClient,
)

logger = logging.getLogger("grocer.checkout_executor")

CHECKOUT_RECONCILE_WAIT_SECONDS = 3.0


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
    max_launch_cap_paise: int = settings.DEFAULT_BUDGET_CAP_PAISE,
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
            "display_text": f"Pay {amount_rs} via UPI",
            "url": bridge_url,
        },
    }


class CheckoutNotPlacedError(Exception):
    """The checkout call failed and get_orders confirmed that no order exists."""


class CheckoutUnconfirmedError(Exception):
    """The checkout call failed and get_orders could not prove either way."""


@dataclass
class _PlacedOrder:
    order_ids: list[str]
    paas_id: str | None
    bridge_url: str | None
    delivery_label: str | None
    response_total_paise: int
    payment_method: str
    split_failures: list[Any] = field(default_factory=list)
    recovered: bool = False


def _placed_from_response(
    res: CheckoutData, fallback_total_paise: int
) -> _PlacedOrder:
    if res.orders:
        order_ids = [o.orderId for o in res.orders if o.orderId]
        split_failures = [o for o in res.orders if not o.orderId or o.error]
    else:
        order_ids = [res.orderId] if res.orderId else []
        split_failures = []
    response_total = parse_price_to_paise(res.cartTotal) if res.cartTotal else 0
    return _PlacedOrder(
        order_ids=order_ids,
        paas_id=res.paasId,
        bridge_url=res.bridgeUrl or None,
        delivery_label=res.deliveryLabel,
        response_total_paise=response_total or fallback_total_paise,
        payment_method=res.paymentMethod,
        split_failures=split_failures,
    )


def _new_order_ids(orders: Any, known_order_ids: list[str]) -> list[str]:
    known = set(known_order_ids)
    return [o.orderId for o in orders.orders if o.orderId and o.orderId not in known]


async def _orders_after_failure(
    swiggy_client: SwiggyClient, known_order_ids: list[str]
) -> list[str] | None:
    """Compare active orders with the pre-checkout snapshot. None means unverifiable."""
    await asyncio.sleep(CHECKOUT_RECONCILE_WAIT_SECONDS)
    try:
        orders = await asyncio.to_thread(
            swiggy_client.get_orders, 20, "INSTAMART", True
        )
    except (
        httpx.HTTPError,
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        SwiggyAuthExpiredError,
    ) as exc:
        logger.warning("get_orders reconcile failed: %s", exc)
        return None
    return _new_order_ids(orders, known_order_ids)


async def _place_order(
    swiggy_client: SwiggyClient,
    payment_method: str,
    address_id: str,
    known_order_ids: list[str],
    fallback_total_paise: int,
) -> _PlacedOrder:
    """Call checkout once, reconcile on failure, retry once, reconcile again."""
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            res = await asyncio.to_thread(
                swiggy_client.checkout,
                payment_method=payment_method,
                address_id=address_id,
            )
        except SwiggyAuthExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001 - every failure must be reconciled
            last_error = exc
            logger.warning("Swiggy checkout call failed: %s", exc)
        else:
            placed = _placed_from_response(res, fallback_total_paise)
            if placed.order_ids:
                return placed
            last_error = RuntimeError("Swiggy returned no order id")

        new_order_ids = await _orders_after_failure(swiggy_client, known_order_ids)
        if new_order_ids is None:
            raise CheckoutUnconfirmedError(str(last_error)) from last_error
        if new_order_ids:
            logger.warning("Checkout recovered from get_orders: %s", new_order_ids)
            return _PlacedOrder(
                order_ids=new_order_ids,
                paas_id=None,
                bridge_url=None,
                delivery_label=None,
                response_total_paise=fallback_total_paise,
                payment_method=payment_method,
                recovered=True,
            )

    raise CheckoutNotPlacedError(str(last_error)) from last_error


async def _set_approval_status(
    pool: Any, approval_uuid: uuid.UUID, status: str
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE grocer.approvals SET status = $2 WHERE id = $1;",
            approval_uuid,
            status,
        )


async def _finish_failed(
    pool: Any,
    checkout_db_id: Any,
    approval_uuid: uuid.UUID,
    checkout_status: str,
    revert_approval: bool,
) -> None:
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "UPDATE grocer.checkouts SET status = $2, updated_at = now() WHERE id = $1;",
            checkout_db_id,
            checkout_status,
        )
        if revert_approval:
            await conn.execute(
                "UPDATE grocer.approvals SET status = 'shown' WHERE id = $1 AND status = 'consuming';",
                approval_uuid,
            )


async def execute_3_lock_checkout(
    pool: Any,
    swiggy_client: SwiggyClient,
    user_id: str,
    approval_id: str,
    message_type: str,
    button_id: str | None,
    payment_method: str = "UPI",
) -> CheckoutExecutionResult:
    """Execute the 3-Lock gate without holding a transaction across the network.

    Lock 1 (authority) is checked first, then the approval is claimed with a
    single atomic UPDATE bound to this user, then the live cart is checked. The
    Swiggy checkout call runs after every claim has committed, so a crash can
    never roll the claim back and let the same approval order twice.
    """
    if not settings.LIVE_CHECKOUT_ENABLED:
        logger.warning("Checkout blocked: LIVE_CHECKOUT_ENABLED is false")
        return CheckoutExecutionResult(
            success=False,
            error_message="Checkout is locked on this build. No order was placed and nothing was charged.",
        )

    # 1. Lock 1 (Authority) with strict approval ID verification
    l1 = verify_lock_1_authority(message_type, button_id, expected_approval_id=approval_id)
    if not l1.passed:
        return CheckoutExecutionResult(success=False, error_message=l1.reason)

    try:
        approval_uuid = uuid.UUID(approval_id)
        user_uuid = uuid.UUID(user_id)
    except (AttributeError, ValueError):
        return CheckoutExecutionResult(
            success=False,
            error_message="This payment request has already been processed or has expired. Please create a fresh basket.",
        )

    # 2. Lock 3 (Exactly-Once): claim the approval and commit before any network call.
    async with pool.acquire() as conn:
        cas_row = await conn.fetchrow(
            """
            UPDATE grocer.approvals
            SET status = 'consuming'
            WHERE id = $1 AND user_id = $2 AND status = 'shown' AND expires_at > now()
            RETURNING id, user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at;
            """,
            approval_uuid,
            user_uuid,
        )

    if not cas_row:
        logger.warning(
            "Lock 3 CAS failed for approval %s, user %s: already consumed, expired, absent, or owned by someone else",
            approval_id,
            user_id,
        )
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
    try:
        live_cart = await asyncio.to_thread(swiggy_client.get_cart, approval.address_id)
    except SwiggyAuthExpiredError:
        await _set_approval_status(pool, approval_uuid, "shown")
        return CheckoutExecutionResult(
            success=False,
            error_message="Your Swiggy login expired. Reconnect your account, then tap pay again.",
        )
    except (httpx.HTTPError, OSError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning("Live cart check failed for approval %s: %s", approval_id, exc)
        await _set_approval_status(pool, approval_uuid, "shown")
        return CheckoutExecutionResult(
            success=False,
            error_message="I couldn't check your live basket with Swiggy just now. Nothing was ordered. Please tap pay again.",
        )

    async with pool.acquire() as conn:
        budget_cap = await get_session_budget_cap(conn, user_uuid)
    l2 = verify_lock_2_truth(approval, live_cart, max_launch_cap_paise=budget_cap)
    if not l2.passed:
        if "launch safety limit" in l2.reason:
            # Keep the receipt payable: raising the cap must not force a new basket.
            await _set_approval_status(pool, approval_uuid, "shown")
            live_to_pay = extract_cart_to_pay_paise(live_cart)
            return CheckoutExecutionResult(
                success=False,
                error_message=l2.reason,
                cta_button={
                    "type": "button",
                    "sub_type": "quick_reply",
                    "parameters": {
                        "button_id": f"budget:raise:{approval.id}:{live_to_pay}",
                        "title": f"Raise Limit to {format_paise_to_rupees(live_to_pay)}",
                    },
                },
            )
        await _set_approval_status(pool, approval_uuid, "expired")
        return CheckoutExecutionResult(success=False, error_message=l2.reason)

    # 4. Snapshot active orders before the checkout call. Without this baseline a
    # failed call cannot be reconciled safely, so refuse rather than guess.
    try:
        pre_orders = await asyncio.to_thread(
            swiggy_client.get_orders, 10, "INSTAMART", True
        )
        known_order_ids = [o.orderId for o in pre_orders.orders if o.orderId]
    except (httpx.HTTPError, OSError, ValueError, KeyError, RuntimeError, SwiggyAuthExpiredError) as exc:
        logger.warning("Pre-checkout order snapshot failed: %s", exc)
        await _set_approval_status(pool, approval_uuid, "shown")
        return CheckoutExecutionResult(
            success=False,
            error_message="I couldn't confirm with Swiggy that no order already exists. Nothing was ordered. Please tap pay again.",
        )

    # 5. Record the attempt before calling Swiggy. The partial unique index keeps
    # one in-flight checkout per customer while this row is visible to recovery.
    try:
        async with pool.acquire() as conn:
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
                approval_uuid,
                user_uuid,
                payment_method.lower(),
                approval.address_id,
                json.dumps(known_order_ids),
                approval.to_pay_paise,
            )
    except asyncpg.UniqueViolationError:
        await _set_approval_status(pool, approval_uuid, "shown")
        return CheckoutExecutionResult(
            success=False,
            error_message="You already have an order in progress. Finish or wait for that one before paying for another.",
        )

    # 6. Place the order. No transaction is open here.
    try:
        placed = await _place_order(
            swiggy_client,
            payment_method=payment_method,
            address_id=approval.address_id,
            known_order_ids=known_order_ids,
            fallback_total_paise=approval.to_pay_paise,
        )
    except SwiggyAuthExpiredError:
        await _finish_failed(pool, checkout_db_id, approval_uuid, "failed", revert_approval=True)
        return CheckoutExecutionResult(
            success=False,
            error_message="Your Swiggy login expired before the order was placed. Nothing was charged. Reconnect and tap pay again.",
        )
    except CheckoutUnconfirmedError as exc:
        logger.error("Checkout outcome unknown for approval %s: %s", approval_id, exc)
        await _finish_failed(pool, checkout_db_id, approval_uuid, "unknown", revert_approval=False)
        return CheckoutExecutionResult(
            success=False,
            error_message=(
                "Swiggy did not confirm the order and its order list is unreachable. "
                "Do not tap pay again. I'm checking with Swiggy and will message you here."
            ),
        )
    except CheckoutNotPlacedError as exc:
        logger.warning("Checkout not placed for approval %s: %s", approval_id, exc)
        await _finish_failed(pool, checkout_db_id, approval_uuid, "failed", revert_approval=True)
        return CheckoutExecutionResult(
            success=False,
            error_message="Swiggy did not place the order and nothing was charged. You can tap pay again.",
        )

    # 7. Record the result and consume the approval in one short transaction.
    placed_inline = (
        (placed.payment_method or "").upper() in {"CASH", "COD", "SWIGGYPAY"}
        and not placed.paas_id
    )
    if placed.recovered:
        checkout_status = "confirming"
    else:
        checkout_status = "placed" if placed_inline else "pending_payment"

    async with pool.acquire() as conn, conn.transaction():
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
            checkout_status,
            placed.order_ids[0],
            json.dumps(placed.order_ids),
            placed.paas_id,
            placed.bridge_url,
            placed.response_total_paise,
            checkout_db_id,
        )
        await conn.execute(
            "UPDATE grocer.approvals SET status = 'consumed' WHERE id = $1;",
            approval_uuid,
        )
        if placed_inline:
            await conn.execute(
                """
                UPDATE grocer.sessions
                SET history = '[]'::jsonb, last_active_at = now()
                WHERE user_id = $1;
                """,
                user_uuid,
            )

    total = format_paise_to_rupees(placed.response_total_paise)
    destination = placed.delivery_label or "Saved Address"
    order_ids = placed.order_ids
    bridge_url = placed.bridge_url
    cta_btn = (
        format_whatsapp_cta_url_button(bridge_url, placed.response_total_paise)
        if bridge_url
        else None
    )

    if placed.recovered:
        receipt = (
            f"⏳ *Order #{order_ids[0]} created*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}\n\n"
            + (
                "Swiggy was slow to respond, so I confirmed it through your order list. "
                "Pay for it in the Swiggy app; I'll keep checking and message you when it is paid."
            )
        )
    elif len(order_ids) > 1:
        lines = [f"Order #{oid}" for oid in order_ids]
        receipt = (
            f"🛒 *Split across {len(order_ids)} dark stores*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}\n\n"
            + "\n".join(lines)
        )
        if placed.split_failures:
            receipt += f"\n\n⚠️ {len(placed.split_failures)} part of your basket could not be ordered."
        if bridge_url:
            receipt += "\n\nTap the secure button below to pay via UPI on Swiggy."
    elif bridge_url:
        receipt = (
            f"💳 *Order #{order_ids[0]} Initiated*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}\n\n"
            f"Tap the secure button below to pay via UPI on Swiggy."
        )
    else:
        receipt = (
            f"✅ *Order #{order_ids[0]} placed*\n"
            f"Total: {total}\n"
            f"Delivering to: {destination}"
        )
    if len(order_ids) == 1 and placed.split_failures:
        receipt += f"\n\n⚠️ {len(placed.split_failures)} item group could not be ordered."

    return CheckoutExecutionResult(
        success=True,
        order_id=order_ids[0],
        paas_id=placed.paas_id,
        bridge_url=bridge_url,
        cta_button=cta_btn,
        receipt_text=receipt,
        order_ids=order_ids,
    )
