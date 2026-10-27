"""Grocer v1.0 — Basket Change and Clear (ADR 0012, basket safety class).

Every change is previewed first and applied only from a button tap. Swiggy's
update_cart replaces the whole basket, so we always rebuild the full list and
revert if the live cart does not match what we asked for.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.integrations.commerce.schemas import CartData
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.basket_actions")


@dataclass
class BasketReply:
    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)


def _full_payload(cart: CartData) -> list[dict[str, Any]]:
    return [
        {"spinId": item.spinId, "skuId": item.skuId, "quantity": item.quantity}
        for item in cart.items
    ]


def _payload_with(
    cart: CartData,
    overrides: dict[str, int] | None = None,
    exclude: str | None = None,
) -> list[dict[str, Any]]:
    overrides = overrides or {}
    return [
        {
            "spinId": item.spinId,
            "skuId": item.skuId,
            "quantity": overrides.get(item.spinId, item.quantity),
        }
        for item in cart.items
        if item.spinId != exclude
    ]


def _find_items(cart: CartData, query: str | None) -> list[Any]:
    needle = (query or "").strip().lower()
    if not needle:
        return []
    return [item for item in cart.items if needle in item.itemName.lower()]


async def _cart(client: SwiggyClient, address_id: str | None) -> CartData:
    return await asyncio.to_thread(client.get_cart, address_id)


async def _write(client: SwiggyClient, items: list[dict[str, Any]], address_id: str | None) -> None:
    await asyncio.to_thread(client.update_cart, items, address_id)


async def handle_clear_request(client: SwiggyClient, address_id: str | None) -> BasketReply:
    cart = await _cart(client, address_id)
    if not cart.items:
        return BasketReply("Your basket is already empty.")
    return BasketReply(
        f"Clear all {len(cart.items)} items from your basket?",
        [("cart:clear", "Yes, clear"), ("cart:keep", "Keep it")],
    )


async def apply_clear(client: SwiggyClient, address_id: str | None) -> BasketReply:
    await asyncio.to_thread(client.clear_cart)
    cart = await _cart(client, address_id)
    if cart.items:
        return BasketReply(
            "Swiggy still shows items in your basket, so I stopped. Nothing was removed."
        )
    return BasketReply("Your basket is empty now.")


async def handle_change_request(
    decision: Any,
    client: SwiggyClient,
    address_id: str | None,
) -> BasketReply:
    cart = await _cart(client, address_id)
    if not cart.items:
        return BasketReply("Your basket is empty, so there's nothing to change.")

    query = decision.items[0].get("query") if decision.items else ""
    matches = _find_items(cart, query)
    if not matches:
        names = ", ".join(item.itemName for item in cart.items[:3])
        return BasketReply(
            f"I couldn't match that to an item in your basket. You have: {names}."
        )
    if len(matches) > 1:
        names = ", ".join(item.itemName for item in matches[:3])
        return BasketReply(f"Which one do you mean: {names}?")

    target = matches[0]
    action = decision.change_action

    if action == "set_quantity":
        try:
            quantity = int(decision.items[0].get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        if quantity >= 1:
            return BasketReply(
                f"Set *{target.itemName}* to quantity {quantity}?",
                [(f"cart:qty:{target.spinId}:{quantity}", f"Set to {quantity}"), ("cart:keep", "Cancel")],
            )
        action = "remove"

    if action == "remove":
        return BasketReply(
            f"Remove *{target.itemName}* from your basket?",
            [(f"cart:rm:{target.spinId}", "Yes, remove"), ("cart:keep", "Cancel")],
        )

    return BasketReply(
        f"Do you want to remove *{target.itemName}*, or change its quantity? "
        "Say 'remove it' or 'make it 2'.",
        [(f"cart:rm:{target.spinId}", "Remove it"), ("cart:keep", "Cancel")],
    )


async def apply_remove(
    client: SwiggyClient,
    address_id: str | None,
    spin_id: str,
) -> BasketReply:
    cart = await _cart(client, address_id)
    target = next((item for item in cart.items if item.spinId == spin_id), None)
    if target is None:
        return BasketReply("That item isn't in your basket any more.")

    await _write(client, _payload_with(cart, exclude=spin_id), address_id)
    after = await _cart(client, address_id)
    if any(item.spinId == spin_id for item in after.items):
        await _write(client, _full_payload(cart), address_id)
        return BasketReply(
            f"Swiggy didn't remove *{target.itemName}*, so I put your basket back."
        )
    return BasketReply(f"Removed *{target.itemName}* from your basket.")


async def apply_add_quantity(
    client: SwiggyClient,
    address_id: str | None,
    spin_id: str,
    extra: int,
) -> BasketReply:
    """Add more of an item that is already in the basket."""
    cart = await _cart(client, address_id)
    target = next((item for item in cart.items if item.spinId == spin_id), None)
    if target is None:
        return BasketReply("That item isn't in your basket any more.")
    if extra < 1:
        return BasketReply("Tell me how many more you want.")
    return await apply_set_quantity(client, address_id, spin_id, target.quantity + extra)


async def apply_set_quantity(
    client: SwiggyClient,
    address_id: str | None,
    spin_id: str,
    quantity: int,
) -> BasketReply:
    cart = await _cart(client, address_id)
    target = next((item for item in cart.items if item.spinId == spin_id), None)
    if target is None:
        return BasketReply("That item isn't in your basket any more.")
    if quantity < 1:
        return BasketReply("Quantity has to be at least 1. Say 'remove it' if you want it gone.")

    await _write(
        client,
        _payload_with(cart, overrides={spin_id: quantity}),
        address_id,
    )
    after = await _cart(client, address_id)
    updated = next((item for item in after.items if item.spinId == spin_id), None)
    if updated is None or updated.quantity != quantity:
        await _write(client, _full_payload(cart), address_id)
        return BasketReply(
            f"Swiggy didn't set *{target.itemName}* to {quantity}, so I put your basket back."
        )
    return BasketReply(f"Set *{target.itemName}* to quantity {quantity}.")


async def apply_add_new_item(
    client: SwiggyClient,
    address_id: str | None,
    spin_id: str,
    quantity: int = 1,
) -> BasketReply:
    """Add a searched product the customer picked from tappable results."""
    if quantity < 1:
        return BasketReply("Quantity has to be at least 1.")

    cart = await _cart(client, address_id)
    existing = next((item for item in cart.items if item.spinId == spin_id), None)
    if existing:
        return await apply_add_quantity(client, address_id, spin_id, quantity)

    await _write(
        client,
        _payload_with(cart) + [{"spinId": spin_id, "quantity": quantity}],
        address_id,
    )
    after = await _cart(client, address_id)
    added = next((item for item in after.items if item.spinId == spin_id), None)
    if added is None:
        await _write(client, _full_payload(cart), address_id)
        return BasketReply("Swiggy didn't add that item, so I put your basket back.")

    return BasketReply(
        f"Added *{added.itemName}* x{added.quantity}. "
        f"Basket total: {after.billBreakdown.toPay.value}"
    )
