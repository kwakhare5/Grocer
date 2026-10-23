"""Formatting utilities for WhatsApp cart receipts and currency."""
from __future__ import annotations

import re
from typing import Optional
from backend.integrations.commerce.models import CommerceCart


def _format_inr(val: float | int) -> str:
    """Format numeric amount into clear Indian Rupee representation (e.g. ₹150 or ₹150.50)."""
    try:
        f = float(val)
        if f.is_integer():
            return f"₹{int(f)}"
        return f"₹{f:.2f}"
    except (ValueError, TypeError):
        return f"₹{val}"


_PLUS_CODE_RE = re.compile(r"^[A-Z0-9]{4,8}\+[A-Z0-9]{2,4}$", re.IGNORECASE)
_MICRO_HOUSING_RE = re.compile(
    r"^(?:flat|apt|apartment|house|room|shop|unit|plot|bungalow|row\s*house|sr\.?\s*no\.?|survey|phase|sector)\b"
    r"|^\d+.*(?:floor|wing|tower|block)\b"
    r"|^(?:near|opp|opposite|behind|beside|adj|adjacent)\b"
    r"|^\d+[-/][A-Za-z0-9-]+$"
    r"|^[A-Z0-9]\s*[-]?\s*(?:wing|tower|block)\b"
    r"|^(?:bldg|building|society|enclave|heights|residency|pride)\b",
    re.IGNORECASE,
)


def clean_address(
    street: str,
    city: Optional[str] = None,
    label: Optional[str] = None,
    area: Optional[str] = None,
) -> str:
    """Format address into human-readable, privacy-safe destination (Area, City) without private apartment numbers or building names."""
    if area:
        dest = area.strip(" ,")
        if city and city.casefold() not in dest.casefold():
            dest = f"{dest}, {city}"
        if label and label.casefold() not in dest.casefold():
            return f"{label} ({dest})"
        return dest

    if not street:
        base = city or "Your Saved Location"
        return f"{label} ({base})" if label and label.casefold() not in base.casefold() else base

    text = re.sub(r"^[^:]+:\s*", "", street).strip()
    text = re.sub(r",?\s*\bIndia\b\s*", "", text, flags=re.IGNORECASE).strip(" ,")

    parts = [p.strip() for p in text.split(",") if p.strip()]
    cleaned_parts: list[str] = []
    seen: set[str] = set()

    for p in parts:
        p_clean = p.strip()
        if _PLUS_CODE_RE.match(p_clean) or _MICRO_HOUSING_RE.search(p_clean):
            continue
        # Strip leading house/plot numbers (e.g. '14 Pali Hill' -> 'Pali Hill')
        p_clean = re.sub(r"^\d+[\s,/-]+", "", p_clean).strip()
        if not p_clean or p_clean.isdigit():
            continue
        p_low = p_clean.casefold()
        if city and p_low == city.casefold():
            continue
        if p_low not in seen and len(p_clean) > 1:
            seen.add(p_low)
            cleaned_parts.append(p_clean)

    # Focus on the primary locality/area (last 1-2 parts before city)
    area = ", ".join(cleaned_parts[-2:]) if len(cleaned_parts) >= 2 else (cleaned_parts[0] if cleaned_parts else "")
    res = area
    if city and city.casefold() not in res.casefold():
        res = f"{res}, {city}" if res else city

    addr_str = res or city or "Your Saved Location"
    if label and label.casefold() not in addr_str.casefold():
        return f"{label} ({addr_str})"
    return addr_str


def format_cart_receipt(
    cart: CommerceCart,
    delivery_location: str = "Home",
    allow_checkout_prompt: bool = True,
    item_reasons: Optional[dict[str, str]] = None,
    advocate_info: Optional[dict[str, Any]] = None,
) -> str:
    """Deterministically format verified cart state into a clean WhatsApp receipt card."""
    if not cart.items:
        return "🛒 *Your Basket is empty.*"
    if cart.currency != "INR":
        return "⚠️ The provider basket is not priced in INR. Checkout is unavailable."

    clean_loc = delivery_location if ("(" in delivery_location and ")" in delivery_location) else clean_address(delivery_location)
    item_lines = []
    for it in cart.items:
        r = (item_reasons.get(it.spin_id) or item_reasons.get(it.name)) if item_reasons else getattr(it, "reason", None)
        line = f"• {it.quantity}x {it.name} ({it.pack_size}) — {_format_inr(it.total_price)}"
        if r:
            line += f" — {r}"
        item_lines.append(line)
    items_block = "\n".join(item_lines)

    lines = [
        "🛒 *Your Basket*",
        items_block,
        "",
    ]
    if not cart.billing_complete:
        lines.append("*Provider bill:* calculating total...")
    elif cart.bill_lines:
        for line in cart.bill_lines:
            try:
                val = float(line.get("value", 0))
                lines.append(f"*{line.get('label', 'Item')}:* {_format_inr(val)}")
            except (ValueError, TypeError):
                lines.append(f"*{line.get('label', 'Item')}:* {line.get('value', '')}")
    else:
        lines.append(f"*Subtotal:* {_format_inr(cart.item_total)}")
        delivery_text = "FREE (₹0)" if cart.delivery_fee == 0 else _format_inr(cart.delivery_fee)
        lines.append(f"*Delivery Fee:* {delivery_text}")
        packaging_and_handling = round(cart.packaging_fee + cart.handling_fee, 2)
        if packaging_and_handling:
            lines.append(f"*Packaging & Handling:* {_format_inr(packaging_and_handling)}")
        if cart.taxes:
            lines.append(f"*Taxes (GST):* {_format_inr(cart.taxes)}")
        if cart.discount:
            lines.append(f"*Discount:* -{_format_inr(cart.discount)}")

    lines.append(
        f"*Grand Total:* {_format_inr(cart.grand_total)}"
        if cart.grand_total > 0 else "*Grand Total:* unavailable"
    )
    if not cart.billing_complete:
        lines.append("⚠️ Provider bill is incomplete. Checkout is unavailable until verified.")
    elif cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        diff = round(cart.min_order_threshold - cart.grand_total, 2)
        lines.append(f"⚠️ *Store Minimum Order:* {_format_inr(cart.min_order_threshold)} (Add {_format_inr(diff)} more to checkout)")

    if advocate_info:
        if advocate_info.get("total_savings", 0) > 0:
            lines.append(f"🎉 *Total Saved:* {_format_inr(advocate_info['total_savings'])}")
        if advocate_info.get("delivery_savings_tip"):
            lines.append(f"💡 *Customer Advocate Tip:* {advocate_info['delivery_savings_tip']}")

    lines.extend([
        "",
        f"📍 *Delivering to:* {clean_loc}",
    ])

    if not cart.billing_complete:
        lines.append("👉 Please wait while I verify the provider bill.")
    elif cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        lines.append("👉 Add items to reach the minimum order, or tell me what to add!")
    elif allow_checkout_prompt:
        lines.append("👉 Reply *Confirm* to place order, or tell me what to change!")

    return "\n".join(lines)


def build_connect_url(ticket: str, base_url: str | None = None) -> str:
    """Generate customer-scoped one-time authentication link."""
    from backend.config import settings

    base = (base_url or settings.CONNECT_BASE_URL or "https://grocerr.vercel.app").rstrip("/")
    return f"{base}/?connect_ticket={ticket}"


async def build_auth_expired_response(
    message: Any,
    base_url: str | None = None,
) -> Any:
    """Generate re-connection response with a one-time login link."""
    import logging
    from backend.channels.models import NormalizedOutgoingResponse
    from backend.integrations.commerce.connect_tickets import default_connect_tickets

    logger = logging.getLogger("grocer.agent.formatters")
    try:
        ticket = await default_connect_tickets.issue(getattr(message, "customer_id", None) or "")
        instructions = (
            "Your Swiggy login needs reconnecting. Open this one-time link from your WhatsApp chat:\n\n"
            f"👉 {build_connect_url(ticket, base_url)}\n\n"
            "The link expires in 10 minutes. After connecting, message me again."
        )
    except Exception:
        logger.exception("Could not issue a customer-scoped Swiggy connection link.")
        instructions = "Swiggy connection is temporarily unavailable. Please message me again shortly."

    return NormalizedOutgoingResponse(
        recipient_id=getattr(message, "sender_id", ""),
        channel=getattr(message, "channel", "whatsapp"),
        text=instructions,
        conversation_state="AUTH_REQUIRED",
    )


def build_address_choice_response(
    message: Any,
    addresses: list[dict[str, Any]],
) -> Any:
    """Format an interactive address selection card with quick-reply buttons."""
    from backend.channels.models import InteractiveAction, NormalizedOutgoingResponse

    lines = []
    for index, address in enumerate(addresses, 1):
        lbl = address.get("label") or f"Address {index}"
        details = address.get("clean_address") or address.get("street") or lbl
        lines.append(f"*{index}. {lbl}* — {details}")
    prompt = "📍 *Which address should I use?*\n\n" + "\n".join(lines)
    prompt += "\n\nReply with the number (e.g. 1), label (e.g. Home), or tap a button."

    return NormalizedOutgoingResponse(
        recipient_id=getattr(message, "sender_id", ""),
        channel=getattr(message, "channel", "whatsapp"),
        text=prompt,
        interactive_actions=[
            InteractiveAction(
                action_type="button",
                id=f"addr_choice_{address.get('_choice_code') or address.get('address_id')}",
                title=f"{index}. {str(address.get('label') or f'Address {index}')}"[:20],
            )
            for index, address in enumerate(addresses[:3], 1)
        ],
        conversation_state="NEEDS_DECISION",
    )

