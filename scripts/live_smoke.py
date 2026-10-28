"""Grocer — Live smoke test against the real Swiggy MCP and Groq.

Manual, live, and read-only for the account except for one cart add/restore.
It never calls checkout. The checkout stage only proves the deploy lock stops
the call before any Swiggy request is made.

Usage:
    python scripts/live_smoke.py
    python scripts/live_smoke.py --stage reads
    python scripts/live_smoke.py --stage cart
    python scripts/live_smoke.py --stage chat
    python scripts/live_smoke.py --stage lock
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.checkout_executor import execute_3_lock_checkout
from backend.agent.read_actions import answer_read_capability
from backend.agent.router import SafetyClass, route_message
from backend.config import settings
from backend.database import close_db_pool, get_db_pool
from backend.integrations.commerce.swiggy_client import SwiggyClient
from backend.integrations.commerce.token_vault import resolve_user_token

CHAT_CASES = (
    "how much is a 1 litre milk",
    "milk ka price kya hai",
    "do u have eggs",
    "show my addresses",
    "what did i order last time",
    "any coupons today",
    "what payment methods do you accept",
    "add 2 litres of milk",
    "hmm let me think",
    "where is my order",
)


class ForbiddenClient:
    """Any call means the checkout lock failed."""

    def __getattr__(self, name: str):
        raise AssertionError(f"Swiggy method '{name}' ran while checkout is locked")


def _section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)


async def _live_user() -> tuple[str, str, SwiggyClient]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT user_id FROM grocer.oauth_tokens ORDER BY updated_at DESC LIMIT 1;"
        )
    if not user_id:
        raise SystemExit("No stored Swiggy token. Connect the account first.")
    token = await resolve_user_token(user_id)
    if not token:
        raise SystemExit("Stored Swiggy token is unusable; reconnect the account.")
    return str(user_id), token, SwiggyClient(auth_token=token)


def _default_address(client: SwiggyClient) -> tuple[str | None, str]:
    data = client.get_addresses()
    address_id = data.resolution.defaultAddressId or (
        data.addresses[0].id if data.addresses else None
    )
    label = next((a.addressCategory or a.addressTag or "" for a in data.addresses), "")
    return address_id, label


async def stage_reads(client: SwiggyClient, address_id: str | None) -> None:
    _section("1. Live reads")

    addresses = await asyncio.to_thread(client.get_addresses)
    print(f"addresses: {len(addresses.addresses)} (default {addresses.resolution.defaultAddressId})")
    for addr in addresses.addresses[:5]:
        label = addr.addressCategory or addr.addressTag or "Address"
        print(f"  - {label}: {addr.addressLine[:34]}…")

    products = await asyncio.to_thread(
        client.search_products, "milk", address_id, None, None, 0
    )
    print(f"\nsearch 'milk': {len(products.products)} products")
    for product in products.products[:3]:
        variation = product.variations[0] if product.variations else None
        price = (
            format_paise_to_rupees(variation.price.offer_price_paise)
            if variation
            else "?"
        )
        stock = variation.isInStockAndAvailable if variation else "?"
        print(f"  - {product.displayName} / {variation.displayName if variation else ''}: "
              f"{price}, in stock={stock}")

    cart = await asyncio.to_thread(client.get_cart, address_id)
    print(f"\ncart: {len(cart.items)} items, to pay {cart.billBreakdown.toPay.value}")

    orders = await asyncio.to_thread(client.get_orders, 10, "INSTAMART", False)
    print(f"orders (last 15 days): {len(orders.orders)}")
    for order in orders.orders[:3]:
        print(f"  - #{order.orderId} {order.status} "
              f"{format_paise_to_rupees(order.total_amount_paise)}")

    options = await asyncio.to_thread(client.get_payment_options, address_id)
    methods = [m.displayName or m.id for m in options.allMethods if m.enabled is not False]
    print(f"payment methods: {', '.join(methods[:6]) or 'none'}")

    coupons = await asyncio.to_thread(client.list_coupons, address_id)
    usable = [c.couponCode for c in coupons.availableCoupons if c.isApplicable]
    print(f"coupons for this cart: {', '.join(usable[:5]) or 'none'}")


async def stage_cart(client: SwiggyClient, address_id: str | None) -> None:
    _section("2. Live cart add and restore")

    original = await asyncio.to_thread(client.get_cart, address_id)
    original_items = [{"spinId": i.spinId, "quantity": i.quantity} for i in original.items]
    print(f"snapshot: {len(original_items)} items, to pay {original.billBreakdown.toPay.value}")

    products = await asyncio.to_thread(
        client.search_products, "milk", address_id, None, None, 0
    )
    if not products.products:
        raise SystemExit("Search returned no milk; nothing to add.")
    product = products.products[0]
    variation = product.variations[0] if product.variations else None
    if variation is None:
        raise SystemExit("First product has no variation to add.")
    print(f"adding: {product.displayName} / {variation.displayName} (spin {variation.spinId})")

    added_cart = await asyncio.to_thread(
        client.update_cart,
        original_items + [{"spinId": variation.spinId, "quantity": 1}],
        address_id,
    )
    spins = [i.spinId for i in added_cart.items]
    assert variation.spinId in spins, "added item missing from live cart"
    added_line = next(i for i in added_cart.items if i.spinId == variation.spinId)
    print(f"after add: {len(added_cart.items)} items, to pay {added_cart.billBreakdown.toPay.value}")
    print(f"verified line: {added_line.itemName} x{added_line.quantity}")
    if added_cart.removedOutOfStockItems:
        print(f"out of stock: {[i.itemName for i in added_cart.removedOutOfStockItems]}")

    restored = await asyncio.to_thread(client.update_cart, original_items, address_id)
    restored_items = sorted((i.spinId, i.quantity) for i in restored.items)
    expected = sorted((i["spinId"], i["quantity"]) for i in original_items)
    assert restored_items == expected, f"cart restore mismatch: {restored_items} != {expected}"
    print(f"restored: {len(restored.items)} items, to pay {restored.billBreakdown.toPay.value}")


async def stage_chat(client: SwiggyClient, address_id: str | None) -> None:
    _section("3. Live Groq chat pass (no cart writes)")

    for index, text in enumerate(CHAT_CASES, start=1):
        decision = await asyncio.to_thread(route_message, text, None, "groq", [])
        if decision.error:
            print(f"{index:02d} {text!r}: LLM error {decision.error[:80]}")
            continue
        print(
            f"\n{index:02d} {text!r}\n"
            f"    route: {decision.capability.value} "
            f"({decision.safety.value}, conf {decision.confidence:.2f})"
        )
        if decision.safety is SafetyClass.READ:
            answer = await answer_read_capability(decision, client, address_id)
            for line in answer.splitlines():
                print(f"    {line}")
        elif decision.items:
            print(f"    items: {decision.items}")
        if index != len(CHAT_CASES):
            await asyncio.sleep(4)  # Groq free tier: 8k tokens/minute


async def stage_lock() -> None:
    _section("4. Checkout deploy lock")
    res = await execute_3_lock_checkout(
        pool=None,
        swiggy_client=ForbiddenClient(),
        user_id=str(uuid.uuid4()),
        approval_id=str(uuid.uuid4()),
        message_type="button_reply",
        button_id=None,
    )
    print(f"success={res.success}")
    print(f"message={res.error_message}")
    assert res.success is False and "locked" in (res.error_message or "").lower()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Live Grocer smoke test")
    parser.add_argument(
        "--stage",
        default="all",
        choices=("all", "reads", "cart", "chat", "lock"),
    )
    args = parser.parse_args()

    print(f"LIVE_CHECKOUT_ENABLED={settings.LIVE_CHECKOUT_ENABLED}")
    print(f"Swiggy base URL={settings.SWIGGY_MCP_BASE_URL}")
    started = time.time()

    _, _, client = await _live_user()
    address_id, _ = _default_address(client)
    print(f"user loaded, address_id={address_id}")
    print("(wa_id and token are not printed)")

    if args.stage in ("all", "reads"):
        await stage_reads(client, address_id)
    if args.stage in ("all", "cart"):
        await stage_cart(client, address_id)
    if args.stage in ("all", "chat"):
        await stage_chat(client, address_id)
    if args.stage in ("all", "lock"):
        await stage_lock()

    await close_db_pool()
    print(f"\nDone in {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
