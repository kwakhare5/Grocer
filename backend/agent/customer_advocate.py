"""Grocer v1.0 — Customer Advocate Engine (Layer 4).

Enforces:
1. Small-Cart Fee Shock Protection (ADR 0009).
2. Pure integer paise math discipline; zero floating-point formatting.
3. Radical price transparency and wallet championship.
4. Bounded coupon trial-and-reset with net-savings check (ADR 0004 & PRD 2.4).
5. ₹1,000 launch safety cap enforcement with 1-tap Raise Limit action (ADR 0006).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.integrations.commerce.schemas import CartData
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.customer_advocate")

DEFAULT_LAUNCH_CAP_PAISE = 100000  # ₹1,000 launch safety cap


@dataclass
class SmallCartFeeWarning:
    item_total_paise: int
    fee_paise: int
    threshold_paise: int
    shortfall_paise: int
    warning_text: str
    action_buttons: list[dict[str, str]] = field(default_factory=list)


@dataclass
class LaunchCapWarning:
    current_to_pay_paise: int
    cap_paise: int
    excess_paise: int
    warning_text: str
    action_buttons: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CouponOptimizationResult:
    original_to_pay_paise: int
    final_to_pay_paise: int
    applied_coupon: str | None = None
    savings_paise: int = 0
    final_cart: CartData | None = None
    savings_message: str | None = None
    trials_conducted: int = 0


def parse_price_to_paise(val: object) -> int:
    """Parse integer paise from int, str or number representation without float loss."""
    if isinstance(val, int):
        return val
    if not val:
        return 0
    raw = str(val).replace("₹", "").strip()
    if "." in raw:
        r, p = raw.split(".", 1)
        p = (p + "00")[:2]
        return int(r) * 100 + int(p)
    return int(raw) * 100


def extract_cart_to_pay_paise(cart: CartData) -> int:
    """Extract authoritative toPay value in integer paise from CartData."""
    if cart.billBreakdown and cart.billBreakdown.toPay and cart.billBreakdown.toPay.value:
        return parse_price_to_paise(cart.billBreakdown.toPay.value)

    # Fallback: sum item totals in paise
    return sum(it.discounted_final_price_paise * it.quantity for it in cart.items)


def check_small_cart_fee(
    cart: CartData,
    free_delivery_threshold_paise: int = 19900,  # ₹199 free delivery threshold
) -> SmallCartFeeWarning | None:
    """Warn customer if fees exceed 35% of item total (ADR 0009 Small-Cart Fee Shock)."""
    item_total_paise = sum(it.discounted_final_price_paise * it.quantity for it in cart.items)
    to_pay_paise = extract_cart_to_pay_paise(cart)
    fee_paise = max(0, to_pay_paise - item_total_paise)

    if item_total_paise <= 0:
        return None

    # Trigger warning strictly if fees exceed 35% of item total (ADR 0009 & ARCHITECTURE.md line 200)
    is_fee_shock = (fee_paise * 100) > (item_total_paise * 35)
    if not is_fee_shock:
        return None

    shortfall_paise = max(0, free_delivery_threshold_paise - item_total_paise)
    item_rs = format_paise_to_rupees(item_total_paise)
    fee_rs = format_paise_to_rupees(fee_paise)
    total_rs = format_paise_to_rupees(to_pay_paise)
    shortfall_rs = format_paise_to_rupees(shortfall_paise)

    warning_text = (
        f"⚠️ *Heads up:* Your item total is {item_rs}, but delivery and handling fees add {fee_rs} "
        f"(Total: {total_rs}). Adding {shortfall_rs} more in groceries unlocks FREE delivery."
    )

    buttons = [
        {"id": "cart:add_essentials", "title": "Add Daily Essentials"},
        {"id": "cart:proceed_checkout", "title": f"Proceed for {total_rs}"},
    ]

    return SmallCartFeeWarning(
        item_total_paise=item_total_paise,
        fee_paise=fee_paise,
        threshold_paise=free_delivery_threshold_paise,
        shortfall_paise=shortfall_paise,
        warning_text=warning_text,
        action_buttons=buttons,
    )


def check_launch_safety_cap(
    to_pay_paise: int,
    cap_paise: int = DEFAULT_LAUNCH_CAP_PAISE,
) -> LaunchCapWarning | None:
    """Enforce ₹1,000 launch safety cap with 1-tap Raise Limit action button (ADR 0006)."""
    if to_pay_paise <= cap_paise:
        return None

    excess_paise = to_pay_paise - cap_paise
    cap_rs = format_paise_to_rupees(cap_paise)
    total_rs = format_paise_to_rupees(to_pay_paise)
    suggested_new_cap_paise = ((to_pay_paise // 50000) + 1) * 50000
    suggested_rs = format_paise_to_rupees(suggested_new_cap_paise)

    warning_text = (
        f"⚠️ *Safety Limit:* Your order total is {total_rs}, exceeding the initial {cap_rs} "
        f"safety limit. Tap below to raise your limit to {suggested_rs}."
    )
    buttons = [
        {"id": f"budget:raise:{suggested_new_cap_paise}", "title": f"Raise Limit to {suggested_rs}"},
        {"id": "cart:clear", "title": "Adjust Basket"},
    ]

    return LaunchCapWarning(
        current_to_pay_paise=to_pay_paise,
        cap_paise=cap_paise,
        excess_paise=excess_paise,
        warning_text=warning_text,
        action_buttons=buttons,
    )


async def raise_session_budget_cap(
    conn_or_pool: Any,
    user_id: str,
    new_cap_paise: int,
) -> int:
    """Persist raised spending limit into customer session in PostgreSQL."""
    await conn_or_pool.execute(
        """
        UPDATE grocer.sessions
        SET budget_cap_paise = $1, last_active_at = now()
        WHERE user_id = $2;
        """,
        new_cap_paise,
        user_id,
    )
    return new_cap_paise


def optimize_coupons(
    cart: CartData,
    swiggy_client: SwiggyClient,
    address_id: str | None = None,
    max_trials: int = 2,
) -> CouponOptimizationResult:
    """Bounded coupon trial-and-reset (max 2 applicable coupons; net savings check).

    Rules:
    1. Tests up to max_trials applicable coupons to stay under turn latency budget.
    2. Net-savings guardrail: Never applies a coupon if the final payable total increases
       (e.g., dropping below a free-delivery cutoff and adding delivery/surge fees).
    3. Reverts to original cart if no tested coupon produces strictly lower toPay amount.
    """
    initial_to_pay_paise = extract_cart_to_pay_paise(cart)
    if initial_to_pay_paise <= 0:
        return CouponOptimizationResult(
            original_to_pay_paise=initial_to_pay_paise,
            final_to_pay_paise=initial_to_pay_paise,
            final_cart=cart,
        )

    try:
        coupons_data = swiggy_client.list_coupons(address_id=address_id)
        candidate_coupons = [c for c in coupons_data.availableCoupons if c.isApplicable]
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning("Failed to list coupons: %s", exc)
        return CouponOptimizationResult(
            original_to_pay_paise=initial_to_pay_paise,
            final_to_pay_paise=initial_to_pay_paise,
            final_cart=cart,
        )

    if not candidate_coupons:
        return CouponOptimizationResult(
            original_to_pay_paise=initial_to_pay_paise,
            final_to_pay_paise=initial_to_pay_paise,
            final_cart=cart,
        )

    trials_to_run = candidate_coupons[:max_trials]
    best_coupon: str | None = None
    best_to_pay_paise = initial_to_pay_paise
    best_cart: CartData = cart
    trials_count = 0

    for candidate in trials_to_run:
        trials_count += 1
        try:
            trial_cart = swiggy_client.apply_coupon(candidate.couponCode)
            trial_to_pay = extract_cart_to_pay_paise(trial_cart)

            # Net-savings check: strictly less toPay amount
            if trial_to_pay < best_to_pay_paise:
                best_to_pay_paise = trial_to_pay
                best_coupon = candidate.couponCode
                best_cart = trial_cart
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
            logger.warning("Failed to test coupon %s: %s", candidate.couponCode, exc)

    if best_coupon and best_to_pay_paise < initial_to_pay_paise:
        # If the last candidate tried was not the winning coupon, re-apply the winning coupon
        # to ensure the live remote cart matches best_cart and avoids Lock 2 price drift.
        if trials_to_run and trials_to_run[-1].couponCode != best_coupon:
            try:
                best_cart = swiggy_client.apply_coupon(best_coupon)
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.warning("Failed to re-apply best coupon %s: %s", best_coupon, exc)

        savings_paise = initial_to_pay_paise - best_to_pay_paise
        savings_rs = format_paise_to_rupees(savings_paise)
        return CouponOptimizationResult(
            original_to_pay_paise=initial_to_pay_paise,
            final_to_pay_paise=best_to_pay_paise,
            applied_coupon=best_coupon,
            savings_paise=savings_paise,
            final_cart=best_cart,
            savings_message=f"🎉 You saved {savings_rs} with coupon {best_coupon}!",
            trials_conducted=trials_count,
        )

    # Revert to base cart if any coupon was tried but didn't save money
    if trials_count > 0:
        if hasattr(swiggy_client, "update_cart"):
            try:
                items_payload = [
                    {"spinId": it.spinId, "quantity": it.quantity}
                    for it in cart.items
                ]
                swiggy_client.update_cart(items=items_payload, address_id=address_id)
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.debug("Cart reset ignored: %s", exc)
        elif hasattr(swiggy_client, "apply_coupon"):
            try:
                swiggy_client.apply_coupon("")
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.debug("Coupon reset ignored: %s", exc)

    return CouponOptimizationResult(
        original_to_pay_paise=initial_to_pay_paise,
        final_to_pay_paise=initial_to_pay_paise,
        applied_coupon=None,
        savings_paise=0,
        final_cart=cart,
        savings_message=None,
        trials_conducted=trials_count,
    )
