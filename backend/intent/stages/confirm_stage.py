"""Stage 4: Confirmation Stage.

Handles receipt calculation with mathematical fee transparency, clean delivery address badges,
cryptographic token validation, and final order confirmation.
"""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import DeliveryAddress
from backend.intent.session import BasketSummary


def _msg_confirmation_basket(basket: BasketSummary) -> str:
    """Render every approval-bound fact available to conversational clients."""
    lines = ["Your basket is ready:"]
    lines.extend(
        f"- {item.quantity} x {item.name} ({item.pack_size}): ₹{item.line_total:,.0f}"
        for item in basket.items
    )
    lines.append(f"Items: ₹{basket.item_total:,.0f}")
    lines.append(f"Delivery: ₹{basket.delivery_fee:,.0f}")
    lines.append(f"Packaging: ₹{basket.packaging_fee:,.0f}")

    # Explicit fee reconciliation so grand total math is transparent to the exact rupee
    base_cost = basket.item_total + basket.delivery_fee + basket.packaging_fee - basket.discount
    extra_fees = round(basket.grand_total - base_cost, 2)
    if extra_fees > 0:
        lines.append(f"Fees & Taxes: ₹{extra_fees:,.0f}")

    lines.append(f"Discount: -₹{basket.discount:,.0f}")
    lines.extend(
        [
            f"Total: ₹{basket.grand_total:,.0f}",
            f"Address: {basket.address_display or basket.address_id or 'selected address'}",
            f"Payment: {basket.selected_payment_option_label or basket.selected_payment_method}",
        ]
    )
    if basket.recovery_notes:
        lines.append(f"Recovery: {'; '.join(basket.recovery_notes)}")
    # Purged robotic developer interpretation notes from consumer receipt
    lines.append("Confirm to place this exact order.")
    return "\n".join(lines)


def _display_address(address: DeliveryAddress) -> str:
    """Format delivery address as a clean human-readable badge."""
    label = (address.label or "").strip()
    city = (address.city or "").strip()
    street = (address.street or "").strip()
    if label and city:
        return f"{label} ({city})"
    if label and street:
        return f"{label} - {street[:30]}"
    if label:
        return label
    if city and street:
        return f"{street[:30]}, {city}"
    if street:
        return street[:40]
    return address.id


def _msg_clarification(question: str, options: list[Any]) -> str:
    lines = [question]
    for opt in options:
        lines.append(f"  {opt.index}. {opt.name} — ₹{opt.price:,.0f}")
    lines.append("Reply with the number of your choice.")
    return "\n".join(lines)


def _msg_failed(reason: str) -> str:
    return (
        f"I couldn't complete your basket: {reason}. "
        "Please adjust your request or try again."
    )


def _msg_ordered(order_id: str, total: Optional[float]) -> str:
    total_note = f" Total ₹{total:,.0f}." if total is not None else ""
    return f"Order placed.{total_note} Order ID: {order_id}."


def _msg_payment_pending(order_id: Optional[str], payment_url: Optional[str]) -> str:
    order_note = f" for order {order_id}" if order_id else ""
    action = f" Complete payment here: {payment_url}" if payment_url else ""
    return f"Payment is pending{order_note}.{action} I will report success only after confirmation."
