"""Planning, item safety, and ordinal cart edit tests."""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient, MockTransport, Response

from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.engine import GroceryAgentEngine
from backend.agent.replenishment import PostgresReplenishmentStore
from backend.agent.task_state import PostgresTaskStateStore
from backend.api.whatsapp import drain_message_queue
from backend.channels.message_store import PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.exceptions import ProviderAuthError, ProviderRateLimitedError
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceOrderResult,
    OrderLineItem,
    OrderSummary,
    PaymentOption,
    PaymentStatusResult,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.main import create_app
from backend.tests.suites.helpers import (
    _interactive_webhook,
    _local_dsn,
    _webhook,
    configure_e2e_secrets,
    postgres_pool,
)

@pytest.mark.asyncio
async def test_model_cannot_add_unselected_sku_with_direct_cart_tool(postgres_pool, monkeypatch):
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)

    class CountingCommerce(MockCommerceAdapter):
        cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def unsafe_model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "update_cart", "args": {"items": [{
                "spin_id": "SPIN-MILK-1L", "sku_id": "SPIN-MILK-1L", "quantity": 1,
            }]},
        }}]}}]}

    engine._call_llm = unsafe_model_reply
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    body, headers = _webhook("wamid.unselected-sku", "Add milk")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.unselected-sku")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.unselected-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.unselected-address")
    assert commerce.cart_writes == 0
    assert reply.conversation_state != "AWAITING_CHECKOUT_CONFIRMATION"
    assert "choose" in reply.text.casefold() or "variant" in reply.text.casefold()


@pytest.mark.asyncio
async def test_new_item_planning_keeps_provider_cart_and_write_tools_out_of_model_request(postgres_pool, monkeypatch):
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id="addr-bandra-1",
        )
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    async def model_boundary(contents, planning_only=False, **kwargs):
        assert planning_only is True
        assert kwargs.get("cart") is None or not kwargs.get("cart").items
        model_input = json.dumps(contents)
        assert "SPIN-MILK" not in model_input
        assert "Amul Taaza Milk" not in model_input
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": "eggs"}]},
        }}]}}]}

    engine._call_llm = model_boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.safe-planning", "Please add eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.safe-planning")
    assert "eggs" in reply.text.casefold()
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert [(item.spin_id, item.quantity) for item in cart.items] == [("SPIN-MILK-1L", 1)]
    await engine.close()


@pytest.mark.asyncio
async def test_new_item_plan_cannot_switch_address_or_migrate_existing_cart(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id="addr-bandra-1",
        )
    baseline_writes = commerce.cart_writes
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    async def unsafe_model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "select_delivery_address", "args": {"address_id": "addr-pune-1"},
        }}]}}]}

    engine._call_llm = unsafe_model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.unsafe-plan-address", "Please add eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.unsafe-plan-address")
    assert commerce.cart_writes == baseline_writes
    assert engine._customer_address[customer_id] == "addr-bandra-1"
    assert "nothing changed" in reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
async def test_cart_edit_cannot_change_a_different_item_than_customer_named(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        await commerce.update_cart([
            CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", sku_id="SPIN-BREAD-400G", quantity=1),
        ], address_id="addr-bandra-1")
    baseline_writes = commerce.cart_writes
    proposed_edit = {"spin_id": "SPIN-BREAD-400G", "sku_id": "SPIN-BREAD-400G", "quantity": 0}

    async def wrong_item_model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "update_cart", "args": {"items": [proposed_edit]},
        }}]}}]}

    engine._call_llm = wrong_item_model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.wrong-cart-edit", "Remove the milk")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.wrong-cart-edit")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert commerce.cart_writes == baseline_writes
    assert {item.spin_id for item in cart.items} == {"SPIN-MILK-1L", "SPIN-BREAD-400G"}
    assert "bread" in reply.text.casefold() or "couldn't" in reply.text.casefold()

    proposed_edit = {"spin_id": "SPIN-MILK-1L", "sku_id": "SPIN-MILK-1L", "quantity": 5}
    body, headers = _webhook("wamid.wrong-cart-quantity", "Remove the milk")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, quantity_reply = await store.response_for_message("wamid.wrong-cart-quantity")
    assert commerce.cart_writes == baseline_writes
    assert "nothing changed" in quantity_reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
async def test_cart_edit_supports_ordinal_references_like_second_one_to_two(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        await commerce.update_cart([
            CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", sku_id="SPIN-BREAD-400G", quantity=1),
        ], address_id="addr-bandra-1")
    baseline_writes = commerce.cart_writes
    proposed_edit = {"spin_id": "SPIN-BREAD-400G", "sku_id": "SPIN-BREAD-400G", "quantity": 2}

    call_count = 0

    async def valid_ordinal_model_reply(_history, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "update_cart", "args": {"items": [proposed_edit], "address_id": "addr-bandra-1"},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [{"text": "I've updated the bread quantity to 2."}]}}]}

    engine._call_llm = valid_ordinal_model_reply
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.ordinal-cart-edit", "make the second one two")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.ordinal-cart-edit")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert commerce.cart_writes == baseline_writes + 1
    bread_item = next(item for item in cart.items if item.spin_id == "SPIN-BREAD-400G")
    assert bread_item.quantity == 2
    assert "bread" in reply.text.casefold() or "basket" in reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("model_queries", [("eggs",), ("milk", "bread", "eggs", "bananas")])
async def test_new_item_plan_keeps_only_the_explicit_list_in_customer_order(
    postgres_pool, monkeypatch, model_queries,
):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")

    async def incomplete_model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": query} for query in model_queries]},
        }}]}}]}

    engine._call_llm = incomplete_model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.omitted-before-plus", "Get milk and bread, plus eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.omitted-before-plus")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook(
            "wamid.omitted-before-plus-address", choice.id, choice.title,
        )
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.omitted-before-plus-address")
    proposal = engine.get_session(customer_id).pending_variant_selection
    assert proposal is not None, reply.text
    assert [group["query"] for group in proposal["groups"]] == ["milk", "bread", "eggs"]
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items
    await engine.close()


@pytest.mark.asyncio
async def test_planning_reply_cannot_claim_an_unchecked_item_was_added(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def false_model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "I added eggs to your basket for ₹70."}]}}]}

    engine._call_llm = false_model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.false-add-claim", "Please add eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.false-add-claim")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.false-add-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.false-add-address")
    assert "I added eggs" not in reply.text
    assert "₹70" not in reply.text
    assert "haven't checked" in reply.text.casefold()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items
    await engine.close()


from backend.tests.suites.planning_repairs import (
    test_planning_clarification_reaches_customer_without_false_cart_claim,
    test_invalid_model_plan_is_repaired_before_catalog_search,
    test_hinglish_groceries_search_english_catalog_without_losing_user_items,
)

__all__ = [
    "test_crashed_turn_recovers_then_later_whatsapp_message_gets_reply",
    "test_greeting_does_not_ask_for_delivery_address_or_use_swiggy",
    "test_show_cart_does_not_demand_an_address",
    "test_food_already_at_home_does_not_select_home_delivery_address",
    "test_model_cannot_add_unselected_sku_with_direct_cart_tool",
    "test_new_item_planning_keeps_provider_cart_and_write_tools_out_of_model_request",
    "test_new_item_plan_cannot_switch_address_or_migrate_existing_cart",
    "test_cart_edit_cannot_change_a_different_item_than_customer_named",
    "test_cart_edit_supports_ordinal_references_like_second_one_to_two",
    "test_new_item_plan_keeps_only_the_explicit_list_in_customer_order",
    "test_planning_reply_cannot_claim_an_unchecked_item_was_added",
    "test_planning_clarification_reaches_customer_without_false_cart_claim",
    "test_invalid_model_plan_is_repaired_before_catalog_search",
    "test_hinglish_groceries_search_english_catalog_without_losing_user_items",
]
