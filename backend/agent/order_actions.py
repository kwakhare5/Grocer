"""Grocer v1.0 — Reorder from Past Orders or Usual Items (ADR 0012).

Rebuilding a basket is a write, so the customer sees the exact items and prices
first. The confirmation tap re-resolves live stock and prices, then verifies the
cart Swiggy returns and reverts if anything is missing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.candidate_search import CandidateItem, search_catalog
from backend.integrations.commerce.schemas import CartData, OrderHistoryItem
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.order_actions")

MAX_REORDER_ITEMS = 10
USUAL_WORDS = (
    "usual",
    "regular",
    "everyday",
    "every week",
    "favourite",
    "favorite",
    "go to",
    "goto",
    "my items",
)


@dataclass
class OrderReply:
    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _Line:
    spin_id: str
    sku_id: str
    name: str
    quantity: int
    price_paise: int


@dataclass
class _Plan:
    label: str
    source: str | None = None
    lines: list[_Line] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    error: str | None = None


def _wants_usuals(message: str) -> bool:
    text = (message or "").lower()
    return any(word in text for word in USUAL_WORDS)


def _pick(candidates: list[CandidateItem]) -> CandidateItem | None:
    return candidates[0] if candidates else None


async def _resolve_names(
    client: SwiggyClient,
    address_id: str | None,
    wanted: list[tuple[str, int]],
) -> tuple[list[_Line], list[str]]:
    lines: list[_Line] = []
    missing: list[str] = []
    for name, quantity in wanted[:MAX_REORDER_ITEMS]:
        candidates = await asyncio.to_thread(
            search_catalog,
            query=name,
            address_id=address_id,
            swiggy_client=client,
        )
        candidate = _pick(candidates)
        if candidate is None:
            missing.append(name)
            continue
        lines.append(
            _Line(
                spin_id=candidate.spin_id,
                sku_id=candidate.sku_id,
                name=candidate.display_name,
                quantity=max(1, quantity),
                price_paise=candidate.offer_price_paise,
            )
        )
    return lines, missing


async def _order_items(
    client: SwiggyClient, order: OrderHistoryItem
) -> list[tuple[str, int]]:
    try:
        details = await asyncio.to_thread(client.get_order_details, order.orderId)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        logger.warning("Order details failed for %s: %s", order.orderId, exc)
        details = None

    if details and details.items:
        return [(item.name, item.quantity) for item in details.items if not item.removed]
    return [
        (str(item.get("name") or ""), int(item.get("quantity") or 1))
        for item in order.items
        if isinstance(item, dict) and item.get("name")
    ]


async def _last_order(
    client: SwiggyClient, order_ref: str | None
) -> tuple[OrderHistoryItem | None, str | None]:
    data = await asyncio.to_thread(
        client.get_orders, count=10, order_type="INSTAMART", active_only=False
    )
    if not data.orders:
        return None, None
    if order_ref and order_ref not in {"last", ""}:
        match = next((order for order in data.orders if order.orderId == order_ref), None)
        if match is None:
            return None, "I couldn't find that order in your last 10 Instamart orders."
        return match, None
    return data.orders[0], None


async def _usual_plan(client: SwiggyClient, address_id: str | None) -> _Plan:
    data = await asyncio.to_thread(client.your_go_to_items, address_id)
    wanted: list[tuple[str, int]] = []
    for product in data.products:
        variation = next(
            (v for v in product.variations if v.isInStockAndAvailable), None
        )
        if variation is not None:
            wanted.append((variation.displayName, 1))
    if not wanted:
        return _Plan(label="", error=(
            "I don't see any usual items on your account yet. Tell me what you "
            "need and I'll build your basket."
        ))
    lines, missing = await _resolve_names(client, address_id, wanted)
    return _Plan(label="your usual items", source="go", lines=lines, missing=missing)


async def _order_plan(
    client: SwiggyClient, address_id: str | None, order_ref: str | None
) -> _Plan:
    order, error = await _last_order(client, order_ref)
    if error:
        return _Plan(label="", error=error)
    if order is None:
        return _Plan(label="", error=(
            "You don't have any Instamart orders in the last 15 days. Tell me what "
            "you need and I'll build your basket."
        ))

    wanted = await _order_items(client, order)
    if not wanted:
        return _Plan(label="", error=(
            "Swiggy didn't share the items from that order. Tell me what you need "
            "and I'll add it."
        ))

    lines, missing = await _resolve_names(client, address_id, wanted)
    when = (order.createdAt or "")[:10]
    label = f"your last order (#{order.orderId}, {when})"
    return _Plan(label=label, source=f"order:{order.orderId}", lines=lines, missing=missing)


async def _build_plan(
    client: SwiggyClient,
    address_id: str | None,
    source: str | None,
    message: str = "",
) -> _Plan:
    if source == "go" or (source is None and _wants_usuals(message)):
        return await _usual_plan(client, address_id)
    if source and source.startswith("order:"):
        return await _order_plan(client, address_id, source.split(":", 1)[1])
    return await _order_plan(client, address_id, source)


def _preview(plan: _Plan, basket_has_items: bool) -> OrderReply:
    if plan.error:
        return OrderReply(plan.error)
    if not plan.lines:
        return OrderReply(
            "None of the items from " + plan.label + " are in stock right now. "
            "Nothing was added."
        )

    total_paise = sum(line.price_paise * line.quantity for line in plan.lines)
    lines = [f"📦 Here's {plan.label}:"]
    for line in plan.lines:
        lines.append(
            f"• {line.name} x{line.quantity} — "
            f"{format_paise_to_rupees(line.price_paise)}"
        )
    if plan.missing:
        lines.append("Not available now: " + ", ".join(plan.missing) + ".")
    if basket_has_items:
        lines.append("I'll add these to your current basket.")
    lines.append(
        f"*Estimated item total: {format_paise_to_rupees(total_paise)}.* "
        "Fees and coupons are applied at checkout."
    )
    lines.append("Add all of these to your basket?")
    return OrderReply(
        "\n".join(lines),
        [(f"reorder:{plan.source}", "Add all"), ("cart:keep", "Cancel")],
    )


async def handle_reorder_request(
    decision: Any,
    client: SwiggyClient,
    address_id: str | None,
    message: str = "",
) -> OrderReply:
    try:
        plan = await _build_plan(
            client, address_id, decision.order_ref, message=message
        )
        cart = await asyncio.to_thread(client.get_cart, address_id)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        logger.warning("Reorder preview failed: %s", exc)
        return OrderReply("I couldn't read your past orders just now. Please try again.")

    return _preview(plan, basket_has_items=bool(cart.items))


def _payload_with(lines: list[_Line], cart: CartData) -> tuple[list[dict[str, Any]], dict[str, int]]:
    expected = {item.spinId: item.quantity for item in cart.items}
    for line in lines:
        expected[line.spin_id] = expected.get(line.spin_id, 0) + line.quantity
    skus = {line.spin_id: line.sku_id for line in lines}
    skus.update({item.spinId: item.skuId for item in cart.items})
    payload = [
        {"spinId": spin_id, "skuId": skus.get(spin_id), "quantity": quantity}
        for spin_id, quantity in expected.items()
    ]
    return payload, expected


async def apply_reorder(
    client: SwiggyClient,
    address_id: str | None,
    source: str,
) -> OrderReply:
    try:
        plan = await _build_plan(client, address_id, source)
        if plan.error or not plan.lines:
            return _preview(plan, basket_has_items=False)

        cart = await asyncio.to_thread(client.get_cart, address_id)
        original = [
            {"spinId": item.spinId, "skuId": item.skuId, "quantity": item.quantity}
            for item in cart.items
        ]
        payload, expected = _payload_with(plan.lines, cart)
        await asyncio.to_thread(client.update_cart, payload, address_id)
        after = await asyncio.to_thread(client.get_cart, address_id)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        logger.warning("Reorder apply failed: %s", exc)
        return OrderReply("That reorder didn't go through. Nothing was changed.")

    actual = {item.spinId: item.quantity for item in after.items}
    if any(actual.get(spin_id, 0) < quantity for spin_id, quantity in expected.items()):
        try:
            await asyncio.to_thread(client.update_cart, original, address_id)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
            logger.error("Reorder revert failed: %s", exc)
        return OrderReply(
            "Swiggy didn't add everything, so I put your basket back. Nothing was changed."
        )

    added = len(plan.lines)
    reply = f"Added {added} item{'s' if added != 1 else ''} from {plan.label} to your basket."
    if plan.missing:
        reply += " Not available now: " + ", ".join(plan.missing) + "."
    reply += " Say 'checkout' when you're ready to pay."
    return OrderReply(reply)
