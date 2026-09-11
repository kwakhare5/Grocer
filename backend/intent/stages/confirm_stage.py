"""Stage 4: Confirmation Stage.

Handles receipt calculation with mathematical fee transparency, clean delivery address badges,
cryptographic token validation, and final order confirmation.
"""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import DeliveryAddress
from backend.intent.session import BasketSummary


def _msg_confirmation_basket(basket: BasketSummary) -> str:
    """Render clean, well-spaced order confirmation receipt for WhatsApp."""
    lines = ["🧾 *Order Confirmation*", ""]
    for item in basket.items:
        lines.append(f"• {item.quantity} × {item.name} ({item.pack_size}) — ₹{item.line_total:,.0f}")

    lines.append("")
    lines.append("────────────────────")
    lines.append(f"• Items: ₹{basket.item_total:,.0f}")
    lines.append(f"• Delivery: ₹{basket.delivery_fee:,.0f}")
    lines.append(f"• Packaging: ₹{basket.packaging_fee:,.0f}")

    # Explicit fee reconciliation so grand total math is transparent to the exact rupee
    base_cost = basket.item_total + basket.delivery_fee + basket.packaging_fee - basket.discount
    extra_fees = round(basket.grand_total - base_cost, 2)
    if extra_fees > 0:
        lines.append(f"• Fees & Taxes: ₹{extra_fees:,.0f}")

    if basket.discount > 0:
        lines.append(f"• Discount: -₹{basket.discount:,.0f}")
    else:
        lines.append("• Discount: ₹0")

    lines.append("────────────────────")
    lines.append(f"*Total: ₹{basket.grand_total:,.0f}*")
    lines.append("")

    addr_text = basket.address_display or basket.address_id or "Saved Address"
    lines.append(f"📍 *Delivering to Address:*\n{addr_text}")
    lines.append("")

    pay_text = basket.selected_payment_option_label or basket.selected_payment_method or "Pay on Delivery"
    lines.append(f"💳 *Payment:*\n{pay_text}")

    if basket.recovery_notes:
        lines.append("")
        lines.append(f"🔄 *Substitutions:* {'; '.join(basket.recovery_notes)}")

    lines.append("")
    lines.append("Tap below or reply *confirm* to place this order with Swiggy Instamart.")
    return "\n".join(lines)


def _display_address(address: DeliveryAddress) -> str:
    """Format delivery address with label and full address details."""
    parts = []
    street = getattr(address, "street", "") or ""
    if street.strip():
        parts.append(street.strip())
    landmark = getattr(address, "landmark", None)
    if landmark and landmark.strip():
        parts.append(landmark.strip())
    city = getattr(address, "city", None)
    if city and city.strip():
        if city.strip().lower() not in street.lower():
            parts.append(city.strip())

    full_address = ", ".join(parts) if parts else "Saved Address"
    label = (getattr(address, "label", "") or "").strip()
    if label:
        return f"{label}: {full_address}"
    return full_address


def _msg_clarification(question: str, options: list[Any]) -> str:
    lines = [question, ""]
    for opt in options:
        lines.append(f"  {opt.index}. {opt.name} — ₹{opt.price:,.0f}")
    lines.append("")
    lines.append("Reply with the number of your choice.")
    return "\n".join(lines)


def _msg_failed(reason: str) -> str:
    return (
        f"I couldn't complete your basket: {reason}. "
        "Please adjust your request or try again."
    )


def _msg_ordered(order_id: str, total: Optional[float], address_display: Optional[str] = None) -> str:
    lines = ["🎉 *Order Placed with Swiggy Instamart!*", ""]
    lines.append(f"*Order ID:* #{order_id}")
    if total is not None:
        lines.append(f"*Total Amount:* ₹{total:,.0f}")
    lines.append("*Status:* Confirmed (Preparing)")
    lines.append("*ETA:* 12–15 mins")
    if address_display:
        lines.append("")
        lines.append(f"📍 *Delivered to:*\n{address_display}")
    lines.append("")
    lines.append(f"🛵 *Track your order live on Swiggy:*\nhttps://swiggy.com/track/{order_id}")
    return "\n".join(lines)


def _msg_payment_pending(order_id: Optional[str], payment_url: Optional[str]) -> str:
    order_note = f" for order #{order_id}" if order_id else ""
    action = f"\n\n📱 *Complete payment here:*\n{payment_url}" if payment_url else ""
    return f"Payment is pending{order_note}.{action}\n\nI will report success as soon as your payment confirms."

