"""Grocer v1.0 — Phase 3 Composite Cart & Commerce Engine Tests.

Strictly verified against committed real Swiggy MCP staging fixtures. Zero fake mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agent.composite_cart import (
    CompositeCartManager,
    TargetCartItem,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return SwiggyClient(fixtures_dir=FIXTURES_DIR)


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


def test_go_to_items_proposal_and_1_tap_reorder(swiggy_client):
    """Top 3–5 Go-to items proposal card and 1-tap reorder (ADR 0008:10 & ADR 0010)."""
    manager = CompositeCartManager(swiggy_client)

    proposal = manager.propose_go_to_items(address_id="addr_01HXYZ")
    assert "Your Go-To Items" in proposal.card_text
    assert proposal.action_id == "goto:add_all"
    assert len(proposal.items) >= 1
    assert proposal.items[0].spin_id == "spin_nandini_500ml"

    # Execute 1-tap reorder
    result = manager.reorder_go_to_items(address_id="addr_01HXYZ")
    assert any(it.spinId == "spin_nandini_500ml" for it in result.cart.items)
    assert "🛒 *Your Basket" in result.receipt_text


def test_address_switch_mid_basket_clears_and_rebuilds(swiggy_client):
    """Switching address clears cart and warns about dark-store inventory change (ADR 0007)."""
    manager = CompositeCartManager(swiggy_client)

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
    assert swiggy_client.clear_cart_called is True
    assert rebuilt_result is not None
