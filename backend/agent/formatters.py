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
) -> str:
    """Deterministically format verified cart state into a clean WhatsApp receipt card."""
    if not cart.items:
        return "🛒 *Your Basket is empty.*"
    if cart.currency != "INR":
        return "⚠️ The provider basket is not priced in INR. Checkout is unavailable."

    clean_loc = clean_address(delivery_location)
    item_lines = [
        f"• {it.quantity}x {it.name} ({it.pack_size}) — {_format_inr(it.total_price)}"
        for it in cart.items
    ]
    items_block = "\n".join(item_lines)

    lines = [
        f"🛒 *Your Basket*",
        items_block,
        "",
    ]
    if not cart.billing_complete:
        lines.append("*Provider bill:* calculating total...")
    elif cart.bill_lines:
        lines.extend(
            f"*{line['label']}:* {_format_inr(float(line['value']))}"
            for line in cart.bill_lines
        )
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
