"""Grocer v1.0 — Customer Advocate Engine (Layer 4).

Enforces:
1. Small-Cart Fee Shock Protection (ADR 0009).
2. Pure integer paise math discipline; zero floating-point formatting.
3. Radical price transparency and wallet championship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.integrations.commerce.schemas import CartData


@dataclass
class SmallCartFeeWarning:
    item_total_paise: int
    fee_paise: int
    threshold_paise: int
    shortfall_paise: int
    warning_text: str
    action_buttons: list[dict[str, str]] = field(default_factory=list)


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

    # Trigger warning if fee exceeds 35% of item total or cart is below threshold
    is_fee_shock = (fee_paise * 100) > (item_total_paise * 35)
    is_below_free_threshold = item_total_paise < free_delivery_threshold_paise and fee_paise > 0

    if not (is_fee_shock or is_below_free_threshold):
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
