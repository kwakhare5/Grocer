"""Presentation and formatting module for GROCER WhatsApp conversational interface.

Pure functions that transform domain models and session states into clean,
well-spaced, branded WhatsApp messages. Contains zero business logic, zero state,
and zero external side effects.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.models import DeliveryAddress, PaymentOption
from backend.intent.session import BasketSummary


def format_display_address(address: DeliveryAddress) -> str:
    """Format delivery address with label and full address details."""
    parts: list[str] = []
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


def format_confirmation_receipt(basket: BasketSummary) -> str:
    """Render clean, mathematically transparent order confirmation receipt for WhatsApp."""
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


def format_payment_choice(
    options: list[PaymentOption],
    address_display: Optional[str] = None,
) -> str:
    """Format grouped payment options for WhatsApp prompt."""
    lines: list[str] = []
    if address_display:
        lines.append(f"📍 *Delivering to:*\n{address_display}")
        lines.append("")

    lines.append("💳 *How would you like to pay?*")
    lines.append("")
    for index, option in enumerate(options, 1):
        lines.append(f"{index}. {option.label}")

    lines.append("")
    lines.append("Reply with the number or name of your choice.")
    return "\n".join(lines)


def format_address_prompt(
    addresses: list[DeliveryAddress],
    basket_summary: Optional[str] = None,
    error_prefix: Optional[str] = None,
) -> str:
    """Format numbered address list with optional cart summary and error prefix."""
    lines: list[str] = []
    if error_prefix:
        lines.append(error_prefix)
        lines.append("")

    if basket_summary:
        lines.append(basket_summary)
        lines.append("")

    lines.append("📍 *Where would you like this delivered?*")
    lines.append("")
    for idx, addr in enumerate(addresses, 1):
        display = format_display_address(addr)
        lines.append(f"{idx}. {display}")

    lines.append("")
    lines.append("Reply with the number or choose your address below.")
    return "\n".join(lines)


def format_clarification(question: str, options: list[Any]) -> str:
    """Format conversational choice clarification when multiple candidates exist."""
    lines = [question, ""]
    for opt in options:
        lines.append(f"  {opt.index}. {opt.name} — ₹{opt.price:,.0f}")
    lines.append("")
    lines.append("Reply with the number of your choice.")
    return "\n".join(lines)


def format_failed(reason: str) -> str:
    """Explain a failed basket action without leaking provider implementation details."""
    normalized_reason = reason.strip()
    if not normalized_reason or any(
        marker in normalized_reason.lower()
        for marker in ("http", "traceback", "exception", "mcp", "json")
    ):
        normalized_reason = "Swiggy could not complete that request"
    return (
        "*I could not complete that change*\n\n"
        f"{normalized_reason}.\n\n"
        "Your order has not been placed. Please adjust your request or try again."
    )


def format_ordered(order_id: str, total: Optional[float] = None, address_display: Optional[str] = None) -> str:
    """Format only provider-confirmed order facts."""
    lines = ["*Order placed with Swiggy Instamart*", ""]
    lines.append(f"*Order ID:* #{order_id}")
    if total is not None:
        lines.append(f"*Total Amount:* ₹{total:,.0f}")
    lines.append("*Status:* Confirmed")
    if address_display:
        lines.append("")
        lines.append(f"📍 *Delivered to:*\n{address_display}")
    lines.append("")
    lines.append("Reply *Track order* and I will check the latest status from Swiggy.")
    return "\n".join(lines)


def format_payment_pending(order_id: Optional[str] = None, payment_url: Optional[str] = None) -> str:
    """Format payment authorization prompt."""
    order_note = f" for order #{order_id}" if order_id else ""
    action = f"\n\n📱 *Complete payment here:*\n{payment_url}" if payment_url else ""
    return f"Payment is pending{order_note}.{action}\n\nI will report success as soon as your payment confirms."


def format_delivery_status(status: Any) -> str:
    """Format delivery tracking status into a user message."""
    carrier = getattr(status, "carrier", None) or "Instamart partner"
    eta = getattr(status, "eta_minutes", None)
    eta_text = f" ETA: ~{eta} mins." if eta else ""
    status_str = status.status.value if hasattr(status.status, "value") else str(status.status)
    return f"Delivery status: {status_str.replace('_', ' ').title()}. Carrier: {carrier}.{eta_text}"


def format_order_cancellation_redirect() -> str:
    """Customer support redirect message for cancellation requests."""
    return (
        "Order cancellation is not supported directly in chat. "
        "Please contact Swiggy customer support in the Swiggy app or call 080-67466729."
    )
