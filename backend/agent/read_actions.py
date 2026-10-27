"""Grocer v1.0 — Read-Only Capability Handlers (ADR 0012).

Every function here answers from live Swiggy data and never writes: no cart,
no address, no money. Anything not implemented yet says so plainly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.candidate_search import search_catalog_full
from backend.agent.composite_cart import format_cart_receipt
from backend.agent.formatters import SWIGGY_CARE_PHONE
from backend.agent.router import Capability, RoutingDecision
from backend.integrations.commerce.swiggy_client import (
    SwiggyAuthExpiredError,
    SwiggyClient,
)

logger = logging.getLogger("grocer.read_actions")

NOT_READY_REPLY = (
    "I can't do that yet. Right now I can check prices and stock, show your "
    "basket, list or switch addresses, show your orders, track a delivery, "
    "show coupons and show payment options."
)


@dataclass
class ReadReply:
    """A text answer with optional tappable follow-ups."""

    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)


async def _item_info(decision: RoutingDecision, client: SwiggyClient, address_id: str | None) -> str:
    query = (decision.items[0].get("query") if decision.items else "").strip()
    if not query:
        return "Which product should I check?"

    if not address_id:
        # Search needs a store; fall back to the customer's default address.
        from backend.agent.address_actions import resolve_default_address

        addresses = await asyncio.to_thread(client.get_addresses)
        default = resolve_default_address(addresses)
        address_id = default.id if default else None

    outcome = await asyncio.to_thread(
        search_catalog_full,
        query=query,
        address_id=address_id,
        swiggy_client=client,
    )
    candidates = outcome.candidates
    if not candidates:
        if outcome.alternatives:
            return (
                f"I couldn't find '{query}' in stock right now. "
                f"Similar items at this store: {', '.join(outcome.alternatives)}."
            )
        return f"I couldn't find '{query}' at your local Instamart store right now."

    lines = [f"Here's what I found for *{query}*:"]
    for cand in candidates[:3]:
        price = format_paise_to_rupees(cand.offer_price_paise)
        was = (
            f" (was {format_paise_to_rupees(cand.mrp_paise)})"
            if cand.mrp_paise > cand.offer_price_paise
            else ""
        )
        lines.append(f"• {cand.display_name} ({cand.quantity_description}) — {price}{was}")
    lines.append("\nIn stock now. Want me to add any of these to your basket?")
    return "\n".join(lines)


async def _store_info(client: SwiggyClient, address_id: str | None) -> str:
    cart = await asyncio.to_thread(client.get_cart, address_id)
    if not cart.items:
        return (
            "Swiggy doesn't share the dark store name or a delivery window before "
            "an order is placed.\n\n"
            "Add items to your basket and I can show the exact delivery fee and total."
        )

    lines = ["*Your current delivery quote:*"]
    for line in cart.billBreakdown.lineItems[:6]:
        lines.append(f"• {line.label}: {line.value}")
    lines.append(f"*To pay: {cart.billBreakdown.toPay.value}*")
    lines.append(
        "\nSwiggy doesn't share the dark store name or a delivery window before "
        "an order is placed."
    )
    return "\n".join(lines)


async def _list_coupons(client: SwiggyClient, address_id: str | None) -> str:
    data = await asyncio.to_thread(client.list_coupons, address_id)
    usable = [coupon for coupon in data.availableCoupons if coupon.isApplicable]
    if not usable:
        return "No coupons are available for your basket right now."

    lines = ["*Coupons you can use:*"]
    for coupon in usable[:5]:
        lines.append(f"• *{coupon.couponCode}* — {coupon.title}")
        if coupon.description:
            lines.append(f"  {coupon.description[:90]}")
    return "\n".join(lines)


def _short_address(line: str, max_segments: int = 4) -> str:
    """Keep the two useful ends of a long geocoded line, not the whole wall."""
    parts = [part.strip() for part in line.split(",") if part.strip()]
    if len(parts) <= max_segments:
        return ", ".join(parts)
    return ", ".join(parts[:2] + ["…"] + parts[-2:])


async def _list_addresses(client: SwiggyClient) -> ReadReply:
    data = await asyncio.to_thread(client.get_addresses)
    if not data.addresses:
        return ReadReply(
            "You have no saved Swiggy addresses yet. Share a location pin to add one."
        )

    default_id = data.resolution.defaultAddressId
    lines = ["*Your saved addresses*", ""]
    buttons: list[tuple[str, str]] = []
    for index, addr in enumerate(data.addresses[:10], start=1):
        label = addr.addressTag or addr.addressCategory or "Address"
        marker = " · default" if addr.id == default_id else ""
        lines.append(f"{index}. *{label}*{marker}")
        lines.append(f"   {_short_address(addr.addressLine)}")
        lines.append("")
        if addr.id != default_id and len(buttons) < 3:
            buttons.append((f"addr:set:{addr.id}", f"Switch to {label}"[:20]))

    if buttons:
        lines.append("Tap a button to switch, or tell me the label.")
    return ReadReply("\n".join(lines).strip(), buttons)


async def _view_basket(client: SwiggyClient, address_id: str | None) -> ReadReply:
    cart = await asyncio.to_thread(client.get_cart, address_id)
    if not cart.items:
        return ReadReply("Your basket is empty. Tell me what you need and I'll add it.")
    return ReadReply(format_cart_receipt(cart))


async def _order_history(client: SwiggyClient) -> str:
    data = await asyncio.to_thread(
        client.get_orders, count=10, order_type="INSTAMART", active_only=False
    )
    if not data.orders:
        return "You have no Instamart orders in the last 15 days."

    lines = ["*Your recent Instamart orders:*"]
    for order in data.orders[:10]:
        when = (order.createdAt or "")[:10]
        total = format_paise_to_rupees(order.total_amount_paise)
        lines.append(f"• #{order.orderId} — {order.status} — {total} — {when}")
    return "\n".join(lines)


async def _track_order(
    decision: RoutingDecision,
    client: SwiggyClient,
    coords: tuple[float, float] | None = None,
) -> str:
    data = await asyncio.to_thread(
        client.get_orders, count=10, order_type="INSTAMART", active_only=True
    )
    active = [
        order
        for order in data.orders
        if order.isActive and (not decision.order_ref or decision.order_ref in (order.orderId, "last"))
    ]
    if not active:
        return "You have no active order right now."

    order = active[0]
    if coords:
        tracking = None
        try:
            tracking = await asyncio.to_thread(
                client.track_order, order.orderId, coords[0], coords[1]
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
            OSError,
            SwiggyAuthExpiredError,
        ) as exc:
            logger.warning("track_order failed for %s: %s", order.orderId, exc)

        if tracking:
            status = tracking.status.statusMessage
            eta = tracking.status.etaText or (
                f"{tracking.status.etaMinutes} mins" if tracking.status.etaMinutes else None
            )
            lines = [
                f"*Order #{order.orderId}*",
                f"Status: {status}" + (f" — ETA {eta}" if eta else ""),
            ]
            store = (tracking.storeInfo or {}).get("name")
            if store:
                lines.append(f"Store: {store}")
            lines.append(f"Live map: https://swiggy.com/track/{order.orderId}")
            if len(active) > 1:
                lines.append(
                    f"\nYou have {len(active)} active orders. Ask about a specific order number for details."
                )
            return "\n".join(lines)

    # No saved coordinates: the status tool still answers without a map position.
    delivery = None
    try:
        delivery = await asyncio.to_thread(client.get_delivery_status, order.orderId)
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        RuntimeError,
        OSError,
        SwiggyAuthExpiredError,
    ) as exc:
        logger.warning("get_delivery_status failed for %s: %s", order.orderId, exc)

    if delivery:
        lines = [
            f"*Order #{order.orderId}*",
            f"Status: {delivery.statusText or 'in progress'}",
        ]
        if delivery.etaText:
            lines.append(f"ETA: {delivery.etaText}")
        lines.append(
            "Share your WhatsApp location pin and I can show the rider on the map."
        )
        return "\n".join(lines)

    return f"Order #{order.orderId} is {order.status}. Swiggy didn't return a live rider update just now."


async def _payment_options(client: SwiggyClient) -> str:
    data = await asyncio.to_thread(client.get_payment_options)
    names = [
        method.displayName or method.id
        for method in data.allMethods
        if method.enabled is not False
    ]
    if not names:
        return "No payment methods are available for your account right now."
    return "*Payment methods available:*\n" + "\n".join(f"• {name}" for name in names)


def _cancel_help() -> str:
    return (
        "I can't cancel an order from here. Please call Swiggy customer care at "
        f"*{SWIGGY_CARE_PHONE}* with your order number and they'll cancel it for you."
    )


def format_disambiguation_choices(
    query: str,
    candidates: list[Any],
    quantity: int = 1,
) -> tuple[str, list[tuple[str, str]]]:
    """Build tappable choices for a vague request like 'milk'."""
    choices = candidates[:3]
    lines = [f"Which *{query}* did you mean?"]
    for index, cand in enumerate(choices, start=1):
        lines.append(
            f"{index}. {cand.display_name} ({cand.quantity_description}) — "
            f"{format_paise_to_rupees(cand.offer_price_paise)}"
        )
    buttons = [
        (f"cart:add:{cand.spin_id}:{quantity}", cand.display_name[:20])
        for cand in choices
    ]
    return "\n".join(lines), buttons


async def build_read_reply(
    decision: RoutingDecision,
    client: SwiggyClient,
    address_id: str | None,
    coords: tuple[float, float] | None = None,
) -> ReadReply:
    """Answer a read capability. Never writes to Swiggy or the database."""
    try:
        if decision.capability is Capability.CHAT:
            return ReadReply(decision.reply or "Hey! What do you need from Instamart?")
        if decision.capability is Capability.ITEM_INFO:
            return ReadReply(await _item_info(decision, client, address_id))
        if decision.capability is Capability.STORE_INFO:
            return ReadReply(await _store_info(client, address_id))
        if decision.capability is Capability.LIST_COUPONS:
            return ReadReply(await _list_coupons(client, address_id))
        if decision.capability is Capability.LIST_ADDRESSES:
            return await _list_addresses(client)
        if decision.capability is Capability.VIEW_BASKET:
            return await _view_basket(client, address_id)
        if decision.capability is Capability.ORDER_HISTORY:
            return ReadReply(await _order_history(client))
        if decision.capability is Capability.TRACK_ORDER:
            return ReadReply(await _track_order(decision, client, coords))
        if decision.capability is Capability.PAYMENT_OPTIONS:
            return ReadReply(await _payment_options(client))
        if decision.capability is Capability.CANCEL_HELP:
            return ReadReply(_cancel_help())
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        OSError,
        SwiggyAuthExpiredError,
    ) as exc:
        logger.warning("Read capability %s failed: %s", decision.capability.value, exc)
        return ReadReply("I couldn't fetch that from Swiggy just now. Please try again in a moment.")

    return ReadReply(NOT_READY_REPLY)


async def answer_read_capability(
    decision: RoutingDecision,
    client: SwiggyClient,
    address_id: str | None,
    coords: tuple[float, float] | None = None,
) -> str:
    """Text-only wrapper kept for tests and simple callers."""
    return (await build_read_reply(decision, client, address_id, coords)).text
