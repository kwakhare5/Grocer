"""Grocer v1.0 — Address Switch and Delete (ADR 0012, account safety class).

Switching changes which dark store serves the customer, so it warns when a
basket exists. Deleting is irreversible, so it needs a second, explicit tap and
never touches the last or active address.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.integrations.commerce.schemas import GetAddressesData, SavedAddress
from backend.integrations.commerce.swiggy_client import SwiggyClient

logger = logging.getLogger("grocer.address_actions")


@dataclass
class AddressReply:
    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)


def _label(address: Any) -> str:
    return address.addressTag or address.addressCategory or "Address"


def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _match(addresses: list[Any], ref: str | None) -> list[Any]:
    if not ref:
        return []
    needle = ref.strip().lower()
    if not needle:
        return []
    return [
        address
        for address in addresses
        if needle in (address.addressTag or "").lower()
        or needle in (address.addressCategory or "").lower()
        or needle == address.id.lower()
    ]


def _picker(addresses: list[Any], prefix: str) -> list[tuple[str, str]]:
    return [
        (f"{prefix}:{address.id}", _short(_label(address), 20))
        for address in addresses[:3]
    ]


def resolve_default_address(data: GetAddressesData) -> SavedAddress | None:
    """Swiggy's own default wins over list order."""
    default_id = data.resolution.defaultAddressId
    if default_id:
        for address in data.addresses:
            if address.id == default_id:
                return address
    return data.addresses[0] if data.addresses else None


async def ensure_active_address(conn: Any, user_id: Any, client: SwiggyClient) -> str | None:
    """Ground a session with no address to Swiggy's default, not addresses[0]."""
    data = await _fetch_addresses(client)
    target = resolve_default_address(data)
    if target is None:
        return None
    await _save_active_address(conn, user_id, target.id)
    return target.id


async def _fetch_addresses(client: SwiggyClient) -> GetAddressesData:
    return await asyncio.to_thread(client.get_addresses)


async def _basket_has_items(client: SwiggyClient) -> bool:
    cart = await asyncio.to_thread(client.get_cart)
    return bool(cart.items)


async def _save_active_address(conn: Any, user_id: Any, address_id: str) -> None:
    await conn.execute(
        """
        INSERT INTO grocer.sessions (user_id, active_address_id, last_active_at)
        VALUES ($1, $2, now())
        ON CONFLICT (user_id) DO UPDATE SET active_address_id = $2, last_active_at = now();
        """,
        user_id,
        address_id,
    )


async def handle_switch_request(
    decision: Any,
    client: SwiggyClient,
    conn: Any,
    user_id: Any,
    active_address_id: str | None,
) -> AddressReply:
    try:
        data = await _fetch_addresses(client)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Address list failed during switch: %s", exc)
        return AddressReply("I couldn't reach Swiggy just now. Please try again in a moment.")

    if not data.addresses:
        return AddressReply(
            "You have no saved Swiggy addresses yet. Share a WhatsApp location pin to add one."
        )

    matches = _match(data.addresses, decision.address_ref)
    candidates = matches or list(data.addresses)

    if len(candidates) > 1:
        return AddressReply(
            "Which address should I use? Switching can change which dark store serves you.",
            _picker(candidates, "addr:set"),
        )

    target = candidates[0]
    if target.id == active_address_id:
        return AddressReply(f"You're already using *{_label(target)}*.")

    if await _basket_has_items(client):
        return AddressReply(
            f"Your basket has items. Switching to *{_label(target)}* may change prices, "
            "stock or fees because it's a different dark store. Switch anyway?",
            [(f"addr:set:{target.id}", "Switch & rebuild"), ("addr:keep", "Keep current")],
        )

    await _save_active_address(conn, user_id, target.id)
    return AddressReply(
        f"Done. Your active address is now *{_label(target)}* — {_short(target.addressLine, 60)}."
    )


async def apply_switch(
    client: SwiggyClient,
    conn: Any,
    user_id: Any,
    address_id: str,
) -> AddressReply:
    """Apply a switch chosen from a button, then rebuild the basket at the new store."""
    try:
        data = await _fetch_addresses(client)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Address list failed applying switch: %s", exc)
        return AddressReply("I couldn't reach Swiggy just now. Please try again in a moment.")

    target = next((a for a in data.addresses if a.id == address_id), None)
    if target is None:
        return AddressReply("That address is no longer in your Swiggy account.")

    previous_id = await conn.fetchval(
        "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;", user_id
    )

    items: list[tuple[str, str, int]] = []
    try:
        cart = await asyncio.to_thread(client.get_cart, previous_id)
        items = [
            (item.spinId, item.itemName, item.quantity)
            for item in cart.items
            if item.isInStockAndAvailable
        ]
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Could not read the old basket before switching: %s", exc)

    await _save_active_address(conn, user_id, target.id)
    header = f"Done. Your active address is now *{_label(target)}*."

    if not items:
        return AddressReply(f"{header} Your basket is empty, so there was nothing to move.")

    try:
        await asyncio.to_thread(client.clear_cart)
        await asyncio.to_thread(
            client.update_cart,
            [{"spinId": spin_id, "quantity": quantity} for spin_id, _, quantity in items],
            target.id,
        )
        rebuilt = await asyncio.to_thread(client.get_cart, target.id)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Basket rebuild after address switch failed: %s", exc)
        return AddressReply(
            f"{header} The old basket was cleared, but Swiggy didn't rebuild it at the "
            "new store. Add your items again."
        )

    kept = {item.spinId for item in rebuilt.items}
    missing = [name for spin_id, name, _ in items if spin_id not in kept]
    moved = len(items) - len(missing)
    text = f"{header} Moved {moved} of {len(items)} items to the new store."
    if missing:
        text += f" Not available there: {', '.join(missing[:3])}."
    return AddressReply(text)


async def handle_delete_request(
    decision: Any,
    client: SwiggyClient,
    active_address_id: str | None,
) -> AddressReply:
    try:
        data = await _fetch_addresses(client)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Address list failed during delete: %s", exc)
        return AddressReply("I couldn't reach Swiggy just now. Please try again in a moment.")

    if len(data.addresses) <= 1:
        return AddressReply(
            "You only have one saved address, so I can't delete it. Add another address first."
        )

    matches = _match(data.addresses, decision.address_ref)
    if not matches:
        return AddressReply(
            "Which address should I delete?",
            _picker(data.addresses, "addr:del"),
        )
    if len(matches) > 1:
        return AddressReply(
            "Which one exactly?",
            _picker(matches, "addr:del"),
        )

    target = matches[0]
    if target.id == active_address_id:
        return AddressReply(
            f"*{_label(target)}* is your active address. Switch to another address first, "
            "then I can delete it."
        )

    return AddressReply(
        f"Delete *{_label(target)}* — {_short(target.addressLine, 60)}? This can't be undone.",
        [(f"addr:del:{target.id}", "Yes, delete"), ("addr:keep", "Cancel")],
    )


async def apply_delete(
    client: SwiggyClient,
    active_address_id: str | None,
    address_id: str,
) -> AddressReply:
    """Delete after the confirmation tap, re-checking both guards live."""
    try:
        data = await _fetch_addresses(client)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Address list failed applying delete: %s", exc)
        return AddressReply("I couldn't reach Swiggy just now. Please try again in a moment.")

    if len(data.addresses) <= 1:
        return AddressReply("I can't delete your only saved address.")
    if address_id == active_address_id:
        return AddressReply("That's your active address. Switch first, then delete.")

    target = next((a for a in data.addresses if a.id == address_id), None)
    if target is None:
        return AddressReply("That address is already gone.")

    from backend.agent.address_lifecycle import AddressLifecycleManager

    guard = await asyncio.to_thread(
        AddressLifecycleManager(client).can_delete_address, address_id
    )
    if not guard.can_delete:
        return AddressReply(guard.block_reason or "That address has an active delivery.")

    try:
        await asyncio.to_thread(client.delete_address, address_id)
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("delete_address failed: %s", exc)
        return AddressReply("Swiggy didn't delete that address. Nothing was changed.")

    return AddressReply(f"Deleted *{_label(target)}* from your Swiggy addresses.")
