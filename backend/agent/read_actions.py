"""Grocer v1.0 — Read-Only Capability Handlers (ADR 0012).

Every function here answers from live Swiggy data and never writes: no cart,
no address, no money. Anything not implemented yet says so plainly.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.candidate_search import search_catalog
from backend.agent.formatters import SWIGGY_CARE_PHONE
from backend.agent.router import Capability, RoutingDecision
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.read_actions")

NOT_READY_REPLY = (
    "I can't do that yet. Right now I can check prices and stock, list your "
    "saved addresses, show your orders, track a delivery, and show payment options."
)


async def _item_info(decision: RoutingDecision, client: SwiggyClient, address_id: str | None) -> str:
    query = (decision.items[0].get("query") if decision.items else "").strip()
    if not query:
        return "Which product should I check?"

    if not address_id:
        # Search needs a store; fall back to the customer's default address.
        addresses = await asyncio.to_thread(client.get_addresses)
        address_id = addresses.resolution.defaultAddressId or (
            addresses.addresses[0].id if addresses.addresses else None
        )

    candidates = await asyncio.to_thread(
        search_catalog,
        query=query,
        address_id=address_id,
        swiggy_client=client,
    )
    if not candidates:
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
            "Your basket is empty, so there's no live delivery quote yet. "
            "Start a basket and I can show the exact delivery fee and total."
        )

    lines = ["*Your current delivery quote:*"]
    for line in cart.billBreakdown.lineItems[:6]:
        lines.append(f"• {line.label}: {line.value}")
    lines.append(f"*To pay: {cart.billBreakdown.toPay.value}*")
    lines.append(
        "\nSwiggy doesn't share the dark store name or opening hours before an order is placed."
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


async def _list_addresses(client: SwiggyClient) -> str:
    data = await asyncio.to_thread(client.get_addresses)
    if not data.addresses:
        return "You have no saved Swiggy addresses yet. Share a location pin to add one."

    default_id = data.resolution.defaultAddressId
    lines = ["*Your saved addresses:*"]
    for addr in data.addresses[:10]:
        label = addr.addressTag or addr.addressCategory or "Address"
        marker = " ✅ default" if addr.id == default_id else ""
        lines.append(f"• {label} — {addr.addressLine}{marker}")
    return "\n".join(lines)


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


async def _track_order(decision: RoutingDecision, client: SwiggyClient) -> str:
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

    lines = ["*Your active orders:*"]
    for order in active:
        eta = f" — ETA {order.estimatedDeliveryTime}" if order.estimatedDeliveryTime else ""
        lines.append(f"• #{order.orderId} — {order.status}{eta}")
    return "\n".join(lines)


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


async def answer_read_capability(
    decision: RoutingDecision,
    client: SwiggyClient,
    address_id: str | None,
) -> str:
    """Answer a read capability. Never writes to Swiggy or the database."""
    try:
        if decision.capability is Capability.CHAT:
            return decision.reply or "Hey! What do you need from Instamart?"
        if decision.capability is Capability.ITEM_INFO:
            return await _item_info(decision, client, address_id)
        if decision.capability is Capability.STORE_INFO:
            return await _store_info(client, address_id)
        if decision.capability is Capability.LIST_COUPONS:
            return await _list_coupons(client, address_id)
        if decision.capability is Capability.LIST_ADDRESSES:
            return await _list_addresses(client)
        if decision.capability is Capability.ORDER_HISTORY:
            return await _order_history(client)
        if decision.capability is Capability.TRACK_ORDER:
            return await _track_order(decision, client)
        if decision.capability is Capability.PAYMENT_OPTIONS:
            return await _payment_options(client)
        if decision.capability is Capability.CANCEL_HELP:
            return _cancel_help()
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        logger.warning("Read capability %s failed: %s", decision.capability.value, exc)
        return "I couldn't fetch that from Swiggy just now. Please try again in a moment."

    return NOT_READY_REPLY
