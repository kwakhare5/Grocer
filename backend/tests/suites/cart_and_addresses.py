"""Cart state, variant selection, address disambiguation, and rate limit tests."""
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
async def test_customer_selects_exact_variants_before_one_cart_write_after_restart(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    milk = next(product for product in commerce._products if product.product_id == "prod-milk")
    for index in range(6):
        extra = copy.deepcopy(milk.variants[0])
        extra.spin_id = f"SPIN-MILK-EXTRA-{index}"
        extra.sku_id = extra.spin_id
        extra.name = f"Amul Taaza Milk pack option {index}"
        milk.variants.append(extra)
    state_store = PostgresTaskStateStore(postgres_pool, Fernet.generate_key().decode())
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", state_store=state_store)
    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [
                    {"query": "milk"}, {"query": "bread"},
                ]},
            }}]}}]}
        return None

    engine._call_llm = model_reply
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.variant-start", "Add milk and bread")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.variant-start")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.variant-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200

    _, variant_reply = await store.response_for_message("wamid.variant-address")
    assert variant_reply.conversation_state == "NEEDS_DECISION"
    assert "1A" in variant_reply.text and "1B" in variant_reply.text and "1F" in variant_reply.text
    assert "2A" in variant_reply.text and "more" in variant_reply.text.casefold()
    assert "500 ml" in variant_reply.text and "1 L" in variant_reply.text
    assert commerce.cart_writes == 0

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        for index, bad_choice in enumerate(("1A 1A 2A", "1Z 2A", "1B"), 1):
            bad_body, bad_headers = _webhook(f"wamid.variant-bad-{index}", bad_choice)
            assert (await client.post("/api/whatsapp/webhook", content=bad_body, headers=bad_headers)).status_code == 200
            _, bad_reply = await store.response_for_message(f"wamid.variant-bad-{index}")
            assert bad_reply.conversation_state == "NEEDS_DECISION"
            assert "1A" in bad_reply.text and "2A" in bad_reply.text
            assert commerce.cart_writes == 0

    restarted = GroceryAgentEngine(commerce, gemini_api_key="local-test", state_store=state_store)

    async def unexpected_model_call(_history, **_kwargs):
        pytest.fail("Exact variant selection must use the saved proposal, not ask the model again")

    restarted._call_llm = unexpected_model_call
    app.state.agent_engine = restarted
    body, headers = _webhook("wamid.variant-choice", "1B 2A")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, final_reply = await store.response_for_message("wamid.variant-choice")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert {(item.spin_id, item.quantity) for item in cart.items} == {
        ("SPIN-MILK-500ML", 1), ("SPIN-BREAD-400G", 1),
    }
    assert commerce.cart_writes == 1
    assert "500" in final_reply.text and "bread" in final_reply.text.casefold()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    assert commerce.cart_writes == 1


@pytest.mark.asyncio
async def test_product_name_used_as_model_pack_hint_does_not_hide_valid_bread(postgres_pool, monkeypatch):
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [
                {"query": "milk", "quantity": 2, "preferred_pack_size": "500ml"},
                {"query": "brown bread", "quantity": 1, "preferred_pack_size": "brown bread"},
            ]},
        }}]}}]}

    engine._call_llm = model_reply
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.descriptive-pack", "2 milk half litre and brown bread, no white bread")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.descriptive-pack")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.descriptive-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.descriptive-address")
    assert reply.conversation_state == "NEEDS_DECISION"
    assert "1A" in reply.text and "500 ml" in reply.text
    assert "2A" in reply.text and "brown bread" in reply.text.casefold()
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items


@pytest.mark.asyncio
async def test_cart_write_with_failed_readback_never_claims_success_or_retries(postgres_pool, monkeypatch):
    class UncertainCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0
            self.fail_next_read = False

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            result = await super().update_cart(items, cart_id=cart_id, address_id=address_id)
            self.fail_next_read = True
            return result

        async def get_cart(self, cart_id=None):
            if self.fail_next_read:
                self.fail_next_read = False
                raise RuntimeError("readback unavailable")
            return await super().get_cart(cart_id)

    commerce = UncertainCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_reply
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.uncertain-start", "Add milk")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.uncertain-start")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.uncertain-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        body, headers = _webhook("wamid.uncertain-choice", "1A")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.uncertain-choice")
    assert commerce.cart_writes == 1
    assert "couldn't verify" in reply.text.casefold()
    assert reply.conversation_state != "AWAITING_CHECKOUT_CONFIRMATION"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    assert engine.get_session(customer_id).external_cart_pending


@pytest.mark.asyncio
@pytest.mark.parametrize("interference", ["price_change", "external_cart_change"])
async def test_changed_live_state_requires_fresh_review_before_selected_cart_write(
    postgres_pool, monkeypatch, interference,
):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_reply
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.changed-start", "Add milk")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.changed-start")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.changed-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        if interference == "price_change":
            commerce.inject_price_change("SPIN-MILK-1L", 99)
        else:
            customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
            with commerce.customer_scope(customer_id):
                await commerce.update_cart(
                    [CartItemUpdate(spin_id="SPIN-BREAD-400G", sku_id="SPIN-BREAD-400G", quantity=1)],
                    address_id="addr-bandra-1",
                )
        baseline_writes = commerce.cart_writes
        body, headers = _webhook("wamid.changed-choice", "1A")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.changed-choice")
    assert commerce.cart_writes == baseline_writes
    assert reply.conversation_state != "AWAITING_CHECKOUT_CONFIRMATION"
    if interference == "price_change":
        assert "price" in reply.text.casefold()
        assert "99" in reply.text
    else:
        assert "changed" in reply.text.casefold()


@pytest.mark.asyncio
async def test_customer_changes_request_while_product_choices_are_pending(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        queries = ["milk", "bread"] if model_calls == 1 else ["bread"]
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": query} for query in queries]},
        }}]}}]}

    engine._call_llm = model_reply
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.revise-start", "Add milk and bread")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.revise-start")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.revise-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        body, headers = _webhook("wamid.revise-request", "Actually, just bread")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.revise-request")
    assert model_calls == 2
    assert "bread" in reply.text.casefold()
    assert "milk" not in reply.text.casefold()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items
    body, headers = _webhook("wamid.revise-ordinal", "the first one")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert [item.spin_id for item in cart.items] == ["SPIN-BREAD-400G"]
    assert model_calls == 2


@pytest.mark.asyncio
async def test_basket_read_without_swiggy_token_sends_reconnect_link(postgres_pool, monkeypatch):
    class DisconnectedCommerce(MockCommerceAdapter):
        async def get_cart(self, cart_id=None):
            raise ProviderAuthError()

    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    engine = GroceryAgentEngine(DisconnectedCommerce(), gemini_api_key="local-test")

    async def no_model_needed(_history, **_kwargs):
        pytest.fail("An unauthenticated basket read must not invoke the model")

    engine._call_llm = no_model_needed
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.disconnected-basket", "show my basket")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.disconnected-basket")
    assert reply.conversation_state == "AUTH_REQUIRED"
    assert "connect_ticket=" in reply.text
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
async def test_real_mcp_rate_limit_stops_after_one_call_and_tells_customer_to_wait(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    commerce = SwiggyMCPAdapter(auth_token="external-boundary-test", owner_customer_id=customer_id)
    calls = []

    def swiggy_boundary(request):
        calls.append(request)
        return Response(429, headers={"Retry-After": "23"}, json={
            "success": False, "error": {"message": "Too many requests"},
        })

    commerce._client._client = AsyncClient(transport=MockTransport(swiggy_boundary))
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def no_model_needed(_history, **_kwargs):
        raise AssertionError("A rate-limited basket read should not invoke the model")

    engine._call_llm = no_model_needed
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.rate-limited-cart", "show my basket")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        second_body, second_headers = _webhook("wamid.rate-limited-again", "show my basket")
        second = await client.post("/api/whatsapp/webhook", content=second_body, headers=second_headers)
    assert response.status_code == 200
    assert second.status_code == 200
    _, reply = await store.response_for_message("wamid.rate-limited-cart")
    _, second_reply = await store.response_for_message("wamid.rate-limited-again")
    assert "23 seconds" in reply.text
    assert "wait" in second_reply.text.casefold()
    assert "empty" not in reply.text.casefold()
    assert len(calls) == 1
    assert len(default_whatsapp_adapter.outbound_messages) == 2
    await commerce._client.close()


@pytest.mark.asyncio
async def test_search_rate_limit_stops_model_loop_without_retrying_mcp(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    commerce = SwiggyMCPAdapter(auth_token="external-boundary-test", owner_customer_id=customer_id)
    tool_names = []

    def swiggy_boundary(request):
        name = json.loads(request.content)["params"]["name"]
        tool_names.append(name)
        if name == "get_cart":
            return Response(200, json={"result": {"success": True, "data": {
                "items": [], "cartTotalAmount": 0,
            }}})
        assert name == "search_products"
        return Response(429, headers={"Retry-After": "23"}, json={
            "success": False, "error": {"message": "Too many requests"},
        })

    commerce._client._client = AsyncClient(transport=MockTransport(swiggy_boundary))
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    engine._customer_address[customer_id] = "addr-selected"
    engine._customer_address_label[customer_id] = "Selected address"
    engine._order_address_confirmed[customer_id] = True
    model_calls = 0

    async def one_search(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls > 1:
            raise AssertionError("Rate limit must stop the model loop")
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "search_products", "args": {"query": "milk"},
        }}]}}]}

    engine._call_llm = one_search
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.search-rate-limited", "Find milk at my selected address")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.search-rate-limited")
    assert "23 seconds" in reply.text
    assert tool_names == ["get_cart", "search_products"]
    assert model_calls == 1
    await commerce._client.close()


from backend.tests.suites.address_disambiguation import (
    test_address_choice_model_outage_then_retry_resumes_original_whatsapp_request,
    test_retry_preserves_pending_grocery_basket_during_address_disambiguation,
)

__all__ = [
    "test_customer_selects_exact_variants_before_one_cart_write_after_restart",
    "test_product_name_used_as_model_pack_hint_does_not_hide_valid_bread",
    "test_cart_write_with_failed_readback_never_claims_success_or_retries",
    "test_changed_live_state_requires_fresh_review_before_selected_cart_write",
    "test_customer_changes_request_while_product_choices_are_pending",
    "test_basket_read_without_swiggy_token_sends_reconnect_link",
    "test_real_mcp_rate_limit_stops_after_one_call_and_tells_customer_to_wait",
    "test_search_rate_limit_stops_model_loop_without_retrying_mcp",
    "test_address_choice_model_outage_then_retry_resumes_original_whatsapp_request",
    "test_retry_preserves_pending_grocery_basket_during_address_disambiguation",
]


