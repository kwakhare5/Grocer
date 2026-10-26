"""Grocer v1.0 — Phase 3 Composite Cart & Commerce Engine Tests.

Tests:
1. Target Cart Assembly: update_cart overwrites safely by preserving existing items.
2. Read-After-Write Verification: get_cart diffing verifies actual dark-store state.
3. Out-of-Stock Reconciliation: Missing/dropped items appear under "Not added" receipt card.
4. 1-Tap Go-To Items Reorder: Gracefully adds available frequent items and flags unavailable.
5. Address Switching Mid-Basket: ADR 0007 warns, clears cart, and rebuilds available items.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agent.composite_cart import (
    CompositeCartManager,
    TargetCartItem,
)
from backend.integrations.commerce.schemas import (
    CartData,
    SearchProductsData,
    ToolEnvelope,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FakeSwiggyStore:
    """Deterministic in-memory Swiggy store simulator for contract testing."""

    def __init__(
        self,
        initial_cart: CartData | None = None,
        go_to_data: SearchProductsData | None = None,
    ):
        self.cart = initial_cart
        self.go_to_data = go_to_data
        self.stock_inventory: dict[str, int] = {
            "spin_amul_1l": 10,
            "spin_bread_white": 5,
            "spin_eggs_6": 0,  # Out of stock
            "spin_nandini_500ml": 8,
        }
        self.update_cart_calls: list[list[dict]] = []
        self.cleared_cart = False
        self.clear_cart_called = False

    def get_cart(self, address_id: str | None = None) -> CartData:
        if self.cart is None or self.cleared_cart:
            return CartData(
                cartId="cart_empty",
                cartTotalAmount="0.00",
                items=[],
                billBreakdown={
                    "lineItems": [{"label": "Item Total", "value": "₹0.00"}],
                    "toPay": {"label": "To Pay", "value": "₹0.00"},
                },
            )
        return self.cart

    def update_cart(self, items: list[dict], address_id: str | None = None) -> CartData:
        self.update_cart_calls.append(items)
        self.cleared_cart = False

        accepted_items = []
        removed_items = []
        item_total_paise = 0

        for it in items:
            spin_id = it["spinId"]
            qty = it["quantity"]
            avail_stock = self.stock_inventory.get(spin_id, 0)
            if avail_stock <= 0:
                removed_items.append(
                    {
                        "spinId": spin_id,
                        "skuId": f"sku_{spin_id}",
                        "productId": f"prod_{spin_id}",
                        "itemName": it.get("itemName", spin_id),
                        "quantity": qty,
                        "isInStockAndAvailable": False,
                        "mrp": it.get("mrp", 50.0),
                        "discountedFinalPrice": it.get("price", 50.0),
                    }
                )
            else:
                accepted_qty = min(qty, avail_stock)
                price = it.get("price", 50.0)
                accepted_items.append(
                    {
                        "spinId": spin_id,
                        "skuId": f"sku_{spin_id}",
                        "productId": f"prod_{spin_id}",
                        "itemName": it.get("itemName", spin_id),
                        "quantity": accepted_qty,
                        "isInStockAndAvailable": True,
                        "mrp": it.get("mrp", price),
                        "discountedFinalPrice": price,
                    }
                )
                item_total_paise += round(price * accepted_qty * 100)

        total_rs = f"{item_total_paise / 100:.2f}"
        to_pay_rs = f"{(item_total_paise + 500) / 100:.2f}"  # + 5.00 handling

        self.cart = CartData(
            cartId="cart_live_123",
            cartTotalAmount=total_rs,
            items=accepted_items,
            billBreakdown={
                "lineItems": [
                    {"label": "Item Total", "value": f"₹{total_rs}"},
                    {"label": "Handling Charge", "value": "₹5.00"},
                ],
                "toPay": {"label": "To Pay", "value": f"₹{to_pay_rs}"},
            },
            removedOutOfStockItems=removed_items,
        )
        return self.cart

    def clear_cart(self) -> dict:
        self.cleared_cart = True
        self.clear_cart_called = True
        self.cart = None
        return {"verified": True}

    def your_go_to_items(self, address_id: str | None = None) -> SearchProductsData:
        if self.go_to_data:
            return self.go_to_data
        raw = json.loads(
            (FIXTURES_DIR / "your_go_to_items.json").read_text(encoding="utf-8")
        )
        return ToolEnvelope[SearchProductsData].model_validate(raw).data


@pytest.fixture
def initial_cart_fixture() -> CartData:
    raw = json.loads((FIXTURES_DIR / "get_cart.json").read_text(encoding="utf-8"))
    return ToolEnvelope[CartData].model_validate(raw).data


def test_destructive_cart_assembly_preserves_existing_items(initial_cart_fixture):
    """Adding an item must preserve the existing milk already in the cart."""
    store = FakeSwiggyStore(initial_cart=initial_cart_fixture)
    manager = CompositeCartManager(store)

    # Initial cart has 2x Amul Taaza Milk (spin_amul_1l)
    assert len(store.cart.items) == 1
    assert store.cart.items[0].spinId == "spin_amul_1l"

    # Now customer adds 1x White Bread (spin_bread_white)
    result = manager.assemble_and_update_cart(
        items_to_add=[
            TargetCartItem(
                spin_id="spin_bread_white",
                quantity=1,
                item_name="Modern White Bread 400g",
                price=40.0,
            )
        ]
    )

    # Must send BOTH existing milk (2) and new bread (1) in destructive update_cart
    assert len(store.update_cart_calls) == 1
    sent_items = store.update_cart_calls[0]
    sent_spins = {item["spinId"]: item["quantity"] for item in sent_items}
    assert sent_spins["spin_amul_1l"] == 2
    assert sent_spins["spin_bread_white"] == 1

    # Cart now contains both items
    assert len(result.cart.items) == 2
    assert any(it.spinId == "spin_bread_white" for it in result.cart.items)
    assert any(it.spinId == "spin_amul_1l" for it in result.cart.items)


def test_read_after_write_verification_and_out_of_stock_card(initial_cart_fixture):
    """Out of stock item (spin_eggs_6) must not crash or wipe cart; must appear in 'Not added' card."""
    store = FakeSwiggyStore(initial_cart=initial_cart_fixture)
    manager = CompositeCartManager(store)

    result = manager.assemble_and_update_cart(
        items_to_add=[
            TargetCartItem(
                spin_id="spin_eggs_6",
                quantity=1,
                item_name="Farm Fresh Eggs 6-Pack",
                price=60.0,
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


def test_go_to_items_1_tap_reorder_partial_stock(initial_cart_fixture):
    """1-Tap reorder adds available frequent items and isolates unavailable ones (ADR 0010)."""
    store = FakeSwiggyStore(initial_cart=initial_cart_fixture)
    manager = CompositeCartManager(store)

    result = manager.reorder_go_to_items(address_id="addr_01HXYZ")

    # Nandini milk (spin_nandini_500ml) from fixture is in stock
    assert any(it.spinId == "spin_nandini_500ml" for it in result.cart.items)
    assert "🛒 *Your Basket" in result.receipt_text


def test_address_switch_mid_basket_clears_and_rebuilds(initial_cart_fixture):
    """Switching address clears cart and warns about dark-store inventory change (ADR 0007)."""
    store = FakeSwiggyStore(initial_cart=initial_cart_fixture)
    manager = CompositeCartManager(store)

    switch_plan = manager.plan_address_switch(
        new_address_id="addr_new_whitefield",
        current_address_name="Bellandur Home",
        new_address_name="Whitefield Office",
    )

    assert switch_plan.has_active_basket is True
    assert "switch_rebuild:addr_new_whitefield" in switch_plan.confirm_action_id
    assert "Switch & Rebuild Basket" in switch_plan.prompt_text

    # Execute switch
    rebuilt_result = manager.execute_address_switch(
        new_address_id="addr_new_whitefield",
    )
    assert store.clear_cart_called is True
    assert rebuilt_result is not None
