"""Comprehensive Layer 3 Tests: Product Discovery & Dynamic Basket Orchestrator."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.agent.item_drop_guard import (
    build_item_drop_guard_prompt,
    check_for_dropped_items,
)
from backend.agent.tools import (
    SwiggyAgentTools,
    _build_product_selection_prompt,
    _extract_candidates,
    execute_add_selected_variants,
    execute_manage_basket,
    execute_restore_cart,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
)


# --- 1. Variant Selection & Candidate Grounding ---

@pytest.mark.asyncio
async def test_select_best_variant_filters_out_of_stock_before_model():
    """select_best_variant must remove candidates with in_stock=False and return out_of_stock if all unavailable."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    oos_candidates = [
        {
            "spin_id": "SPIN-OOS",
            "sku_id": "SKU-OOS",
            "name": "Amul Taaza Milk 500ml",
            "brand": "Amul",
            "price": 27.0,
            "pack_size": "500ml",
            "in_stock": False,
        }
    ]
    res = await tools.select_best_variant("milk", oos_candidates)
    assert res is not None
    assert res.get("action") == "out_of_stock"
    assert "milk is out of stock" in res.get("reason", "")


def test_build_product_selection_prompt_enforces_locked_rules():
    """Selection prompt encodes user preference for single units over bundles and clear product names."""
    candidates = [
        {"candidate_id": "1", "name": "Milk (500 ml)", "price": 27.0, "pack_size": "500 ml"},
        {"candidate_id": "2", "name": "Milk (500 ml x 4)", "price": 100.0, "pack_size": "500 ml x 4"},
    ]
    prompt = _build_product_selection_prompt("1 pack of milk", candidates, preferred_pack_size="500ml")
    assert "1 pack of milk" in prompt
    assert "prefer the standard single unit over multi-packs" in prompt.lower()
    assert "preferred pack size: 500ml" in prompt.lower()


# --- 2. Basket Manager & Safety Gates ---

@pytest.mark.asyncio
async def test_basket_manager_medical_filter_leak():
    """Basket manager must screen out prescription medicines before variant selection."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    async def mock_batch_search(queries, address_id):
        return {
            "success": True,
            "results": [
                {
                    "query": "pain relief",
                    "products": [
                        {
                            "spin_id": "SPIN-AMOXICILLIN",
                            "sku_id": "SKU-AMOX",
                            "name": "Amoxicillin 500mg Capsule",
                            "category": "Pharmacy Prescription",
                            "price": 120.0,
                            "pack_size": "10 capsules",
                        },
                        {
                            "spin_id": "SPIN-BALM",
                            "sku_id": "SKU-BALM",
                            "name": "Tiger Balm Pain Relieving Ointment",
                            "category": "Healthcare OTC",
                            "price": 50.0,
                            "pack_size": "21ml",
                        },
                    ],
                }
            ],
        }

    tools.batch_search_products = mock_batch_search
    tools.select_best_variant = AsyncMock(
        return_value={
            "action": "pick",
            "option": {
                "spin_id": "SPIN-BALM",
                "sku_id": "SKU-BALM",
                "name": "Tiger Balm Pain Relieving Ointment",
                "price": 50.0,
            },
            "reason": "OTC pain relieving ointment",
        }
    )
    empty_cart = CommerceCart(
        cart_id="c1",
        address_id="addr-1",
        items=[],
        grand_total=0.0,
        is_serviceable=True,
    )
    balm_cart = CommerceCart(
        cart_id="c1",
        address_id="addr-1",
        items=[CartItem(spin_id="SPIN-BALM", sku_id="SKU-BALM", name="Tiger Balm", pack_size="21ml", quantity=1, unit_price=50.0, total_price=50.0)],
        grand_total=50.0,
        is_serviceable=True,
    )
    tools.commerce.update_cart = AsyncMock(return_value=balm_cart)
    tools.commerce.get_cart = AsyncMock(side_effect=[empty_cart, balm_cart])

    res = await execute_manage_basket(
        tools=tools,
        address_id="addr-1",
        add=[{"query": "pain relief", "quantity": 1}],
        current_cart=empty_cart,
    )
    assert res.get("success") is True
    added_names = [str(item) for item in res.get("added_items", [])]
    assert not any("amoxicillin" in name.casefold() for name in added_names)


@pytest.mark.asyncio
async def test_basket_manager_strict_input_validation():
    """Basket manager must reject invalid inputs with structured errors rather than silent continues."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    cart_with_item = CommerceCart(
        cart_id="c1",
        address_id="a1",
        items=[CartItem(spin_id="item-1", sku_id="item-1", name="Milk", pack_size="1L", quantity=1, unit_price=50.0, total_price=50.0)],
        grand_total=50.0,
        is_serviceable=True,
    )

    # Empty remove entry
    res_empty_remove = await execute_manage_basket(
        tools=tools,
        address_id="addr-1",
        remove=["   "],
        current_cart=cart_with_item,
    )
    assert res_empty_remove["success"] is False
    assert res_empty_remove["error"] == "INVALID_INPUT"

    # Non-integer quantity in set_quantity
    res_bad_qty = await execute_manage_basket(
        tools=tools,
        address_id="addr-1",
        set_quantity=[{"line_id": "item-1", "quantity": "invalid_number"}],
        current_cart=cart_with_item,
    )
    assert res_bad_qty["success"] is False
    assert res_bad_qty["error"] == "INVALID_INPUT"

    # Non-integer quantity in add
    res_bad_add = await execute_manage_basket(
        tools=tools,
        address_id="addr-1",
        add=[{"query": "milk", "quantity": "three"}],
        current_cart=cart_with_item,
    )
    assert res_bad_add["success"] is False
    assert res_bad_add["error"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_basket_manager_no_change_returns_full_schema():
    """When no basket mutations occur, return dictionary must include verified_fingerprint and breakdown."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    res = await execute_manage_basket(
        tools=tools,
        address_id="addr-bandra-1",
    )
    assert res["success"] is True
    assert "verified_fingerprint" in res
    assert "delivery_fee" in res
    assert "taxes" in res
    assert "total_fees" in res
    assert "formatted_receipt" in res
    assert "budget_blocked_items" in res


# --- 3. Cart Actions & Rollback ---

@pytest.mark.asyncio
async def test_cart_actions_restore_cart_fee_invariant():
    """execute_restore_cart must verify by items and quantities, tolerating delivery fee shifts."""
    commerce = MagicMock()
    before = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=100.0,
        delivery_fee=30.0,
        items=[CartItem(spin_id="SPIN-1", sku_id="SKU-1", name="Milk", pack_size="1L", quantity=2, unit_price=35.0, total_price=70.0)],
        is_serviceable=True,
    )
    after = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=180.0,
        delivery_fee=30.0,
        items=[
            CartItem(spin_id="SPIN-1", sku_id="SKU-1", name="Milk", pack_size="1L", quantity=2, unit_price=35.0, total_price=70.0),
            CartItem(spin_id="SPIN-2", sku_id="SKU-2", name="Butter", pack_size="100g", quantity=1, unit_price=80.0, total_price=80.0),
        ],
        is_serviceable=True,
    )
    restored = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=105.0,
        delivery_fee=35.0,
        items=[CartItem(spin_id="SPIN-1", sku_id="SKU-1", name="Milk", pack_size="1L", quantity=2, unit_price=35.0, total_price=70.0)],
        is_serviceable=True,
    )
    commerce.update_cart = AsyncMock()
    commerce.get_cart = AsyncMock(return_value=restored)

    success = await execute_restore_cart(commerce, before, after, address_id="a1")
    assert success is True, "Rollback should succeed despite dynamic fee shift"


@pytest.mark.asyncio
async def test_cart_actions_simultaneous_add_and_set_quantity():
    """Setting quantity on an existing item while adding updates quantity cleanly without being dropped."""
    tools = MagicMock()
    cart = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=50.0,
        items=[CartItem(spin_id="SPIN-MILK", sku_id="SKU-MILK", name="Milk", pack_size="500ml", quantity=1, unit_price=50.0, total_price=50.0)],
        is_serviceable=True,
    )
    updated_cart = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=150.0,
        items=[CartItem(spin_id="SPIN-MILK", sku_id="SKU-MILK", name="Milk", pack_size="500ml", quantity=3, unit_price=50.0, total_price=150.0)],
        is_serviceable=True,
    )
    tools.commerce.update_cart = AsyncMock(return_value=updated_cart)
    tools.commerce.get_cart = AsyncMock(side_effect=[cart, updated_cart])

    selected = [
        {"option": {"spin_id": "SPIN-MILK", "sku_id": "SKU-MILK", "name": "Milk", "price": 50.0}, "query": "milk", "quantity": 1}
    ]
    extra_updates = [
        {"spin_id": "SPIN-MILK", "sku_id": "SKU-MILK", "quantity": 3}
    ]

    res = await execute_add_selected_variants(
        tools=tools,
        selected=selected,
        address_id="a1",
        current_cart=cart,
        expected_cart_state={
            "cart_id": cart.cart_id,
            "address_id": cart.address_id,
            "grand_total": cart.grand_total,
            "items": [[it.spin_id, it.sku_id, it.quantity] for it in cart.items],
        },
        extra_updates=extra_updates,
    )
    assert res.get("success") is True


@pytest.mark.asyncio
async def test_cart_actions_set_quantity_enforces_budget_upfront():
    """set_quantity that would breach budget_cap_inr must be blocked upfront without live mutation."""
    tools = MagicMock()
    cart = CommerceCart(
        cart_id="c1",
        address_id="a1",
        grand_total=100.0,
        items=[CartItem(spin_id="SPIN-GHEE", sku_id="SKU-GHEE", name="Ghee", pack_size="500g", quantity=1, unit_price=500.0, total_price=500.0)],
        is_serviceable=True,
    )
    tools.commerce.update_cart = AsyncMock()
    tools.commerce.get_cart = AsyncMock(return_value=cart)

    res = await execute_add_selected_variants(
        tools=tools,
        selected=[],
        address_id="a1",
        current_cart=cart,
        expected_cart_state={"cart_id": "c1", "items": [["SPIN-GHEE", "SKU-GHEE", 1]]},
        budget_cap_inr=600.0,
        extra_updates=[{"spin_id": "SPIN-GHEE", "sku_id": "SKU-GHEE", "quantity": 3}],
    )
    assert res.get("success") is False
    assert res.get("error") == "BUDGET_BLOCKED"
    tools.commerce.update_cart.assert_not_called()


# --- 4. Item Drop Guard & Session Cleanup ---

@pytest.mark.asyncio
async def test_item_drop_guard_retries_on_gemini_none_response(caplog):
    """When Gemini returns (None, reason), drop guard must retry instead of failing open."""
    class FlakyClient:
        def __init__(self):
            self.api_key = "test-key"
            self.call_count = 0

        async def generate_structured_with_reason(self, model, prompt, response_schema):
            self.call_count += 1
            if self.call_count == 1:
                return None, "quota 429"
            return {"missing_items": ["bread"]}, None

    client = FlakyClient()
    with caplog.at_level(logging.DEBUG):
        missing = await check_for_dropped_items(
            client=client,
            customer_message="Bring milk and bread",
            added_items=["milk"],
            unavailable_items=[],
            restricted_items=[],
            pending_items=[],
        )
    assert client.call_count == 2, "Drop guard should have retried after initial failure"
    assert missing == ["bread"]


def test_item_drop_guard_removed_items_in_prompt():
    """Prompt must include removed items and explicitly instruct not to treat them as missing."""
    prompt = build_item_drop_guard_prompt(
        customer_message="Remove milk and add curd",
        added_items=["Curd 400g"],
        unavailable_items=[],
        restricted_items=[],
        pending_items=[],
        removed_items=["Amul Taaza Milk 500ml"],
    )
    assert "Removed by customer request: Amul Taaza Milk 500ml" in prompt
    assert "Items explicitly removed from the basket by customer request are intentional deletions" in prompt


@pytest.mark.asyncio
async def test_tools_clear_cart_returns_verified_item_count():
    """tools.clear_cart must verify cart is empty and return item_count: 0."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)
    res = await tools.clear_cart()
    assert res.get("success") is True
    assert res.get("item_count") == 0
