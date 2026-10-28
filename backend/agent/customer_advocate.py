"""Grocer v1.0 — Customer Advocate Engine (Layer 4).

Enforces:
1. Pure integer paise math discipline; zero floating-point formatting.
2. Radical price transparency and wallet championship.
3. Bounded coupon trial-and-reset with net-savings check (ADR 0004 & PRD 2.4).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from backend.integrations.commerce.schemas import CartData
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.customer_advocate")


@dataclass
class CouponOptimizationResult:
    original_to_pay_paise: int
    final_to_pay_paise: int
    applied_coupon: str | None = None
    savings_paise: int = 0
    final_cart: CartData | None = None
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


def _items_match(cart: CartData, other: CartData) -> bool:
    """A coupon may change the bill, never the items or their quantities."""
    mine = {it.spinId: it.quantity for it in cart.items}
    theirs = {it.spinId: it.quantity for it in other.items}
    return mine == theirs


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
    if initial_to_pay_paise <= 0 or not (
        hasattr(swiggy_client, "list_coupons")
        and hasattr(swiggy_client, "apply_coupon")
    ):
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
            if not _items_match(cart, trial_cart):
                logger.warning(
                    "Coupon %s changed basket items; ignored", candidate.couponCode
                )
                continue
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
                best_cart = cart

        if not _items_match(cart, best_cart):
            logger.warning("Winning coupon changed basket items; not used")
        else:
            savings_paise = initial_to_pay_paise - best_to_pay_paise
            return CouponOptimizationResult(
                original_to_pay_paise=initial_to_pay_paise,
                final_to_pay_paise=best_to_pay_paise,
                applied_coupon=best_coupon,
                savings_paise=savings_paise,
                final_cart=best_cart,
                trials_conducted=trials_count,
            )

    # Revert to base cart if any coupon was tried but didn't save money
    if trials_count > 0:
        if hasattr(swiggy_client, "update_cart"):
            try:
                items_payload = [
                    {"spinId": it.spinId, "skuId": it.skuId, "quantity": it.quantity}
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
        trials_conducted=trials_count,
    )
