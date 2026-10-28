"""Grocer v1.0 — Phase 3 Composite Cart & Commerce Engine Tests.

Strictly verified against committed real Swiggy MCP staging fixtures. Zero fake mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.composite_cart import (
    CompositeCartManager,
    TargetCartItem,
    format_cart_receipt,
)
from backend.integrations.commerce.schemas import CartData, CartItem
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return FixtureSwiggyClient(FIXTURES_DIR)


def test_destructive_cart_assembly_preserves_existing_items(swiggy_client):
    """Adding an item must preserve the existing milk already in the cart."""
    manager = CompositeCartManager(swiggy_client)

    # Initial fixture cart has 2x Amul Taaza Milk (spin_amul_1l)
    initial_cart = swiggy_client.get_cart()
    assert len(initial_cart.items) == 1
    assert initial_cart.items[0].spinId == "spin_amul_1l"

    # Now customer adds 1x White Bread (spin_bread_white) with integer paise
    result = manager.assemble_and_update_cart(
        items_to_add=[
            TargetCartItem(
                spin_id="spin_bread_white",
                quantity=1,
                item_name="Modern White Bread 400g",
                price_paise=4000,
            )
        ]
    )

    # Must send BOTH existing milk (2) and new bread (1) in destructive update_cart
    sent_items = swiggy_client.last_update_items
    sent_spins = {item["spinId"]: item["quantity"] for item in sent_items}
    assert sent_spins["spin_amul_1l"] == 2
    assert sent_spins["spin_bread_white"] == 1
    # Every update_cart item must carry a real skuId (Swiggy contract)
    assert all(item.get("skuId") for item in sent_items)

    # Cart now contains both items
    assert len(result.cart.items) == 2
    assert any(it.spinId == "spin_bread_white" for it in result.cart.items)
    assert any(it.spinId == "spin_amul_1l" for it in result.cart.items)


def test_read_after_write_verification_and_out_of_stock_card(swiggy_client):
    """Out of stock item (spin_eggs_6) must not crash; must appear in 'Not added' card."""
    manager = CompositeCartManager(swiggy_client)

    result = manager.assemble_and_update_cart(
        items_to_add=[
            TargetCartItem(
                spin_id="spin_eggs_6",
                quantity=1,
                item_name="Farm Fresh Eggs 6-Pack",
                price_paise=6000,
            )
        ]
    )

    # Eggs failed to add because stock is 0
    assert len(result.dropped_out_of_stock) == 1
    assert result.dropped_out_of_stock[0].spin_id == "spin_eggs_6"

    # Milk is still intact
    assert len(result.cart.items) == 1
    assert result.cart.items[0].spinId == "spin_amul_1l"

    # Receipt text contains "Not added" section
    assert "Not added (Out of stock" in result.receipt_text
    assert "Farm Fresh Eggs 6-Pack" in result.receipt_text

def test_stock_cap_is_applied_and_shown_not_silent(swiggy_client):
    manager = CompositeCartManager(swiggy_client)
    result = manager.assemble_and_update_cart(
        items_to_add=[
            TargetCartItem(
                spin_id="spin_pizza_base",
                sku_id="sku_pizza_base",
                quantity=5,
                item_name="Pizza Base",
                price_paise=10200,
                max_quantity=2,
                max_quantity_message="Only 2 unit(s) of this item can be added per order.",
            )
        ]
    )

    pizza = next(it for it in result.cart.items if it.spinId == "spin_pizza_base")
    assert pizza.quantity == 2
    assert result.capped_items[0]["requested"] == 5
    assert result.capped_items[0]["allowed"] == 2
    assert result.baseline_count == 2
    assert "✅ *Added to your basket*" in result.receipt_text
    assert "You had 2 items" in result.receipt_text
    assert "🛒 *Your Basket (4 items)*" in result.receipt_text
    assert "＋ Pizza Base x2" in result.receipt_text
    assert "Ask *what's in my basket*" not in result.receipt_text
    assert "Only 2 unit(s) of this item can be added per order." in result.receipt_text
    assert "I asked for 5, so I added 2" in result.receipt_text


def _cart_with(items: list[CartItem]) -> CartData:
    return CartData(
        cartId="cart_test",
        cartTotalAmount="283.00",
        items=items,
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹272.00"}],
            "toPay": {"label": "To Pay", "value": "₹283.00"},
        },
    )


def _item(spin: str, name: str, qty: int, price: float) -> CartItem:
    return CartItem(
        spinId=spin,
        skuId=f"sku_{spin}",
        productId=f"prod_{spin}",
        itemName=name,
        quantity=qty,
        isInStockAndAvailable=True,
        mrp=price,
        discountedFinalPrice=price,
    )


def test_receipt_lists_full_basket_and_marks_the_added_line():
    cart = _cart_with(
        [
            _item("spin_old_milk", "Amul Taaza Milk 1L", 2, 104.0),
            _item("spin_new_milk", "Chitale Dairy Cow Milk", 1, 64.0),
        ]
    )
    text = format_cart_receipt(
        cart,
        added_items=[
            TargetCartItem(
                spin_id="spin_new_milk",
                quantity=1,
                item_name="Chitale Dairy Cow Milk",
                price_paise=6400,
            )
        ],
        baseline_count=2,
        baseline_to_pay="₹208",
    )
    assert "🛒 *Your Basket (3 items)*" in text
    assert "You had 2 items (₹208) before this add." in text
    assert "＋ Chitale Dairy Cow Milk x1 — ₹64" in text
    assert "• Amul Taaza Milk 1L x2 — ₹208" in text
    assert "Ask *what's in my basket*" not in text


def test_receipt_marks_a_merged_line_with_the_added_quantity():
    cart = _cart_with([_item("spin_old_milk", "Amul Taaza Milk 1L", 3, 104.0)])
    text = format_cart_receipt(
        cart,
        added_items=[
            TargetCartItem(
                spin_id="spin_old_milk",
                quantity=1,
                item_name="Amul Taaza Milk 1L",
                price_paise=10400,
            )
        ],
        baseline_count=2,
    )
    assert "＋ Amul Taaza Milk 1L x3 — ₹312 (added 1)" in text


def test_receipt_caps_long_baskets_with_a_count_not_an_instruction():
    items = [_item(f"spin_{i}", f"Item {i}", 1, 10.0) for i in range(12)]
    text = format_cart_receipt(_cart_with(items), max_item_lines=10)
    assert "🛒 *Your Basket (12 items)*" in text
    assert "…and 2 more items." in text
    assert "Ask *what's in my basket*" not in text


def test_small_basket_names_the_charges_before_pay():
    cart = CartData(
        cartId="cart_small",
        cartTotalAmount="30.00",
        items=[_item("spin_chips", "Chips", 1, 20.0)],
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹20.00"}],
            "toPay": {"label": "To Pay", "value": "₹30.00"},
        },
    )

    text = format_cart_receipt(cart)

    assert "Charges add ₹10 (50% of your items)" in text


def test_normal_basket_does_not_warn_about_charges():
    cart = CartData(
        cartId="cart_normal",
        cartTotalAmount="105.00",
        items=[_item("spin_atta", "Atta", 1, 100.0)],
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹105.00"}],
            "toPay": {"label": "To Pay", "value": "₹105.00"},
        },
    )

    text = format_cart_receipt(cart)

    assert "Charges add" not in text
