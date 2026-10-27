"""Grocer v1.0 — Basket Change and Clear Tests (ADR 0012, basket safety class).

Runs against committed Swiggy fixtures. No live cart is touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from backend.agent.basket_actions import (
    apply_add_quantity,
    apply_clear,
    apply_keep_only_new,
    apply_remove,
    apply_set_quantity,
    apply_swap,
    handle_change_request,
    handle_clear_request,
    parse_fresh_items,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ADDRESS_ID = "addr_01HXYZ"
SPIN = "spin_amul_1l"


@dataclass
class FakeDecision:
    items: list[dict[str, Any]] = field(default_factory=list)
    change_action: str | None = None


@pytest.fixture
def client() -> SwiggyClient:
    return SwiggyClient(fixtures_dir=FIXTURES_DIR)


@pytest.mark.asyncio
async def test_clear_preview_does_not_touch_the_cart(client):
    reply = await handle_clear_request(client, ADDRESS_ID)
    assert reply.buttons
    assert "1 items" in reply.text
    assert len(client.get_cart().items) == 1


@pytest.mark.asyncio
async def test_clear_applies_and_verifies(client):
    reply = await apply_clear(client, ADDRESS_ID)
    assert "empty" in reply.text
    assert client.get_cart().items == []


@pytest.mark.asyncio
async def test_remove_preview_names_the_item(client):
    decision = FakeDecision(items=[{"query": "amul", "quantity": 1}], change_action="remove")
    reply = await handle_change_request(decision, client, ADDRESS_ID)
    assert "Remove" in reply.text
    assert reply.buttons[0][0] == f"cart:rm:{SPIN}"


@pytest.mark.asyncio
async def test_remove_applies_and_verifies(client):
    reply = await apply_remove(client, ADDRESS_ID, SPIN)
    assert "Removed" in reply.text
    assert all(item.spinId != SPIN for item in client.get_cart().items)


@pytest.mark.asyncio
async def test_set_quantity_preview_and_apply(client):
    decision = FakeDecision(items=[{"query": "milk", "quantity": 5}], change_action="set_quantity")
    preview = await handle_change_request(decision, client, ADDRESS_ID)
    assert preview.buttons[0][0] == f"cart:qty:{SPIN}:5"

    reply = await apply_set_quantity(client, ADDRESS_ID, SPIN, 5)
    assert "quantity 5" in reply.text
    updated = next(item for item in client.get_cart().items if item.spinId == SPIN)
    assert updated.quantity == 5


@pytest.mark.asyncio
async def test_add_quantity_increments_the_existing_item(client):
    reply = await apply_add_quantity(client, ADDRESS_ID, SPIN, 3)
    assert "quantity 5" in reply.text
    updated = next(item for item in client.get_cart().items if item.spinId == SPIN)
    assert updated.quantity == 5


@pytest.mark.asyncio
async def test_change_without_an_action_asks_instead_of_guessing(client):
    decision = FakeDecision(items=[{"query": "milk"}], change_action=None)
    reply = await handle_change_request(decision, client, ADDRESS_ID)
    assert "remove" in reply.text.lower()


@pytest.mark.asyncio
async def test_unknown_item_does_not_write(client):
    decision = FakeDecision(items=[{"query": "chocolate"}], change_action="remove")
    reply = await handle_change_request(decision, client, ADDRESS_ID)
    assert "couldn't match" in reply.text
    assert len(client.get_cart().items) == 1


def test_fresh_button_parser_accepts_real_lines_and_rejects_bad_ones():
    assert parse_fresh_items("cart:fresh:spin_a:sku_a:2|spin_b:sku_b:1") == [
        {"spinId": "spin_a", "skuId": "sku_a", "quantity": 2},
        {"spinId": "spin_b", "skuId": "sku_b", "quantity": 1},
    ]
    assert parse_fresh_items("cart:fresh:bad") is None
    assert parse_fresh_items("cart:fresh:spin_a:sku_a:0") is None


@pytest.mark.asyncio
async def test_keep_only_new_clears_the_old_cart_and_readds_the_new_item(client):
    cart, err = await apply_keep_only_new(
        client, ADDRESS_ID, "cart:fresh:spin_bread_white:sku_bread:1"
    )
    assert err == ""
    assert [item.spinId for item in cart.items] == ["spin_bread_white"]
    assert all(item.spinId != SPIN for item in cart.items)


@pytest.mark.asyncio
async def test_swap_replaces_the_old_item_and_keeps_the_quantity(client):
    reply = await apply_swap(
        client, ADDRESS_ID, SPIN, "spin_nandini_500ml", "sku_nandini"
    )
    assert "Swapped" in reply.text
    cart = client.get_cart()
    assert all(item.spinId != SPIN for item in cart.items)
    new_item = next(item for item in cart.items if item.spinId == "spin_nandini_500ml")
    assert new_item.quantity == 2
