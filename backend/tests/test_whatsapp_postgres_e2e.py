"""Failure modes across signed Meta intake, PostgreSQL ordering, agent, and local delivery."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient, MockTransport, Response

from backend.agent.engine import GroceryAgentEngine
from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.replenishment import PostgresReplenishmentStore
from backend.agent.task_state import PostgresTaskStateStore
from backend.api.whatsapp import drain_message_queue
from backend.channels.message_store import PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.models import (
    PaymentStatusResult, CommerceOrderResult, PaymentOption, CartItemUpdate, OrderSummary, OrderLineItem,
)
from backend.main import create_app
from backend.config import settings


def _local_dsn() -> str:
    dsn = os.environ.get("GROCER_E2E_DATABASE_URL", "")
    if "@127.0.0.1:" not in dsn or not dsn.endswith("/grocer_test"):
        pytest.skip("Set GROCER_E2E_DATABASE_URL to the isolated localhost grocer_test database")
    return dsn


@pytest.fixture
async def postgres_pool():
    pool = await asyncpg.create_pool(_local_dsn(), ssl=False, min_size=1, max_size=3)
    root = Path(__file__).resolve().parents[2] / "migrations"
    async with pool.acquire() as conn:
        for name in ("bootstrap_fresh.sql", "001_connect_tickets.up.sql", "002_messages.up.sql",
                     "003_checkout_attempts.up.sql", "004_task_state.up.sql", "005_privacy_deletions.up.sql",
                     "006_inbound_claimed_at.up.sql", "007_outbound_sending_started_at.up.sql",
                     "008_payment_followups.up.sql", "009_replenishment.up.sql"):
            await conn.execute((root / name).read_text(encoding="utf-8"))
        await conn.execute("TRUNCATE grocer_internal.replenishment, grocer_internal.task_state, grocer_internal.checkout_attempts, grocer_internal.outbound_messages, grocer_internal.inbound_messages RESTART IDENTITY CASCADE")
    try:
        yield pool
    finally:
        await pool.close()


def _webhook(message_id: str, text: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messages": [{"id": message_id, "from": "919999988888", "type": "text", "text": {"body": text}}]
    }}]}]}).encode()
    signature = hmac.new(b"local-e2e-secret", body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={signature}"}


def _interactive_webhook(message_id: str, action_id: str, title: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messages": [{"id": message_id, "from": "919999988888", "type": "interactive",
                      "interactive": {"type": "list_reply", "list_reply": {"id": action_id, "title": title}}}]
    }}]}]}).encode()
    signature = hmac.new(b"local-e2e-secret", body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={signature}"}


@pytest.mark.asyncio
async def test_crashed_turn_recovers_then_later_whatsapp_message_gets_reply(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "I can help with your groceries."}]}}]}

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    sender = "919999988888"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id(sender)
    crashed = NormalizedIncomingMessage(
        message_id="wamid.crashed", channel=ChannelType.WHATSAPP,
        sender_id=sender, customer_id=customer_id, text="add milk",
    )
    await store.enqueue_many([crashed])
    await postgres_pool.execute(
        "UPDATE grocer_internal.inbound_messages SET status='PROCESSING', claimed_at=now()-interval '10 minutes' WHERE message_id=$1",
        crashed.message_id,
    )
    body, headers = _webhook("wamid.later", "hello")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        result = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert result.status_code == 200
    assert result.json()["processed"] == 1
    rows = await postgres_pool.fetch(
        "SELECT message_id, status FROM grocer_internal.inbound_messages ORDER BY id"
    )
    assert [tuple(row.values()) for row in rows] == [
        ("wamid.crashed", "PROCESSED"), ("wamid.later", "PROCESSED")
    ]
    outbound = await postgres_pool.fetch("SELECT status FROM grocer_internal.outbound_messages ORDER BY id")
    assert [row["status"] for row in outbound] == ["SENT", "SENT"]
    assert len(default_whatsapp_adapter.outbound_messages) == 2
    first_text = json.dumps(default_whatsapp_adapter.outbound_messages[0]).casefold()
    assert "review" in first_text or "verify" in first_text


@pytest.mark.asyncio
@pytest.mark.parametrize("populated", [False, True])
async def test_show_cart_does_not_demand_an_address(postgres_pool, monkeypatch, populated):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def no_model_needed(_history, **_kwargs):
        raise AssertionError("A cart read should not require a model call")

    engine._call_llm = no_model_needed
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    if populated:
        customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
        with commerce.customer_scope(customer_id):
            await commerce.update_cart(
                [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
                address_id="addr-bandra-1",
            )
    body, headers = _webhook("wamid.show-empty-cart", "show my cart")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.show-empty-cart")
    assert ("milk" if populated else "empty") in reply.text.casefold()
    assert "which address" not in reply.text.casefold()
    assert not reply.interactive_actions
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
async def test_model_cannot_add_unselected_sku_with_direct_cart_tool(postgres_pool, monkeypatch):
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
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
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
async def test_customer_selects_exact_variants_before_one_cart_write_after_restart(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.cart_writes = 0

        async def update_cart(self, items, cart_id=None, address_id=None):
            self.cart_writes += 1
            return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    commerce = CountingCommerce()
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
    assert "1A" in variant_reply.text and "1B" in variant_reply.text and "2A" in variant_reply.text
    assert "500 ml" in variant_reply.text and "1 L" in variant_reply.text
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


@pytest.mark.asyncio
async def test_address_choice_model_outage_then_retry_resumes_original_whatsapp_request(
    postgres_pool, monkeypatch,
):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    state_store = PostgresTaskStateStore(postgres_pool, Fernet.generate_key().decode())
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", state_store=state_store)
    resumed_prompt = ""

    async def model_outage(_history, **_kwargs):
        return None

    engine._call_llm = model_outage  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        first_body, first_headers = _webhook("wamid.address-1", "Add milk and bread")
        first = await client.post("/api/whatsapp/webhook", content=first_body, headers=first_headers)
        assert first.status_code == 200
        _, address_reply = await store.response_for_message("wamid.address-1")
        assert address_reply.interactive_actions
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook("wamid.address-2", choice.id, choice.title)
        second = await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)
        assert second.status_code == 200
        _, retry_reply = await store.response_for_message("wamid.address-2")
        assert "try again" in retry_reply.text.casefold()
        resumed_engine = GroceryAgentEngine(
            commerce, gemini_api_key="local-test", state_store=state_store,
        )
        resumed_calls = 0

        async def model_after_restart(history, **_kwargs):
            nonlocal resumed_calls, resumed_prompt
            resumed_calls += 1
            if resumed_calls == 1:
                resumed_prompt = next(
                    part["text"] for entry in reversed(history) if entry.get("role") == "user"
                    for part in entry.get("parts", []) if "text" in part
                )
                return {"candidates": [{"content": {"parts": [{"functionCall": {
                    "name": "quick_add_items", "args": {"items": [{"query": "milk"}, {"query": "bread"}]},
                }}]}}]}
            return None

        resumed_engine._call_llm = model_after_restart
        app.state.agent_engine = resumed_engine  # restart the agent against the same PostgreSQL state
        third_body, third_headers = _webhook("wamid.address-3", "try again")
        third = await client.post("/api/whatsapp/webhook", content=third_body, headers=third_headers)
        assert third.status_code == 200
    _, variant_reply = await store.response_for_message("wamid.address-3")
    assert variant_reply.conversation_state == "NEEDS_DECISION"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items
    choice_body, choice_headers = _webhook("wamid.address-4", "1A 2A")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, final_reply = await store.response_for_message("wamid.address-4")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert "add milk and bread" in resumed_prompt.casefold()
    assert len(cart.items) == 2
    assert "milk" in final_reply.text.casefold() and "bread" in final_reply.text.casefold()
    assert len(default_whatsapp_adapter.outbound_messages) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("request_text", [
    "Make pizza ingredients under ₹1,000 and also add bread, Bournvita, tissues and a pencil",
    "I want to make pizza. Keep the ingredients under ₹1,000, and add bread, Bournvita, tissues, and a pencil.",
])
async def test_pizza_ingredient_cap_keeps_extras_even_when_whole_basket_exceeds_cap(
    postgres_pool, monkeypatch, request_text,
):
    commerce = MockCommerceAdapter()
    state_store = PostgresTaskStateStore(postgres_pool, Fernet.generate_key().decode())
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", state_store=state_store)
    calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [
                    {"query": "olive oil", "quantity": 2},
                    {"query": "mozzarella", "quantity": 2},
                    {"query": "tomato", "quantity": 4},
                    {"query": "bread", "quantity": 5},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]},
            }}]}}]}
        return None

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    first_body, first_headers = _webhook(
        "wamid.pizza-request",
        request_text,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        first = await client.post("/api/whatsapp/webhook", content=first_body, headers=first_headers)
        assert first.status_code == 200
        _, address_reply = await store.response_for_message("wamid.pizza-request")
        assert address_reply.interactive_actions
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook(
            "wamid.pizza-address", choice.id, choice.title,
        )
        second = await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)
        assert second.status_code == 200
        _, variant_reply = await store.response_for_message("wamid.pizza-address")
        assert variant_reply.conversation_state == "NEEDS_DECISION"
        variant_body, variant_headers = _webhook("wamid.pizza-variants", "2A 3A 4A 5A")
        assert (await client.post("/api/whatsapp/webhook", content=variant_body, headers=variant_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.pizza-variants")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    by_id = {item.spin_id: item for item in cart.items}
    pizza_ids = {"SPIN-OLIVEOIL-250ML", "SPIN-CHEESE-200G", "SPIN-TOMATO-500G"}
    assert sum(by_id[spin].total_price for spin in pizza_ids if spin in by_id) <= 1000
    assert "SPIN-OLIVEOIL-250ML" in by_id and "SPIN-CHEESE-200G" in by_id
    assert "SPIN-TOMATO-500G" not in by_id
    assert by_id["SPIN-BREAD-400G"].quantity == 5
    assert cart.grand_total > 1000
    assert "tomato" in reply.text.casefold()
    assert "bournvita" in reply.text.casefold()
    assert "tissue" in reply.text.casefold()
    assert "pencil" in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"

    update_calls = 0

    async def increase_ingredient(_history, **_kwargs):
        nonlocal update_calls
        update_calls += 1
        if update_calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "update_cart", "args": {"items": [{
                    "spin_id": "SPIN-OLIVEOIL-250ML",
                    "sku_id": "SPIN-OLIVEOIL-250ML",
                    "quantity": 3,
                }]},
            }}]}}]}
        return None

    engine._call_llm = increase_ingredient
    change_body, change_headers = _webhook("wamid.pizza-over-cap", "Increase olive oil to 3")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        change = await client.post("/api/whatsapp/webhook", content=change_body, headers=change_headers)
        assert change.status_code == 200
    _, change_reply = await store.response_for_message("wamid.pizza-over-cap")
    with commerce.customer_scope(customer_id):
        unchanged = await commerce.get_cart()
    assert next(item.quantity for item in unchanged.items if item.spin_id == "SPIN-OLIVEOIL-250ML") == 2
    assert "limit" in change_reply.text.casefold() or "budget" in change_reply.text.casefold()
    assert not any(action.id == "confirm_order" for action in change_reply.interactive_actions)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_query", ["Bournvita", "pizza base"])
async def test_missing_requested_item_requires_review_before_checkout(postgres_pool, monkeypatch, missing_query):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [
                    {"query": "bread"}, {"query": missing_query},
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
        body, headers = _webhook("wamid.missing-item", f"Add bread and {missing_query}")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.missing-item")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.missing-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.missing-address")
    assert missing_query.casefold() in reply.text.casefold()
    assert "unavailable" in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)


@pytest.mark.asyncio
async def test_recipe_request_cannot_silently_omit_pizza_base(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    calls = 0

    async def incomplete_recipe(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [
                    {"query": "pizza sauce"}, {"query": "mozzarella"}, {"query": "bread"},
                ]},
            }}]}}]}
        return None

    engine._call_llm = incomplete_recipe
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.recipe-start", "I want to make pizza. Give me ingredients and add bread")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.recipe-start")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.recipe-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.recipe-address")
    assert "pizza base" in reply.text.casefold()
    assert "unavailable" in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)


@pytest.mark.asyncio
async def test_provider_dropped_quick_add_item_is_named_before_partial_review(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    commerce.inject_partial_cart_drop("SPIN-MILK-1L")
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    calls = 0

    async def add_two(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [
                    {"query": "milk"}, {"query": "bread"},
                ]},
            }}]}}]}
        return None

    engine._call_llm = add_two
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.dropped-request", "Add milk and bread")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.dropped-request")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.dropped-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, variant_reply = await store.response_for_message("wamid.dropped-address")
        assert variant_reply.conversation_state == "NEEDS_DECISION"
        body, headers = _webhook("wamid.dropped-variants", "1A 2A")
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.dropped-variants")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert {item.spin_id for item in cart.items} == {"SPIN-BREAD-400G"}
    assert "milk" in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)


@pytest.mark.asyncio
async def test_symptom_message_suggests_groceries_without_adding_medicine(
    postgres_pool, monkeypatch,
):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": "Vicks"}, {"query": "ginger"}]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.symptom", "I have a cold. What groceries could help?")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.symptom")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert not cart.items
    assert "ginger" in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
async def test_replayed_signed_webhook_has_one_durable_turn_and_one_reply(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    engine = GroceryAgentEngine(MockCommerceAdapter(), gemini_api_key="local-test")
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.replayed", "I need milk")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        first = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        replay = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json()["processed"] == 1
    assert replay.json()["processed"] == 0
    assert await postgres_pool.fetchval("SELECT count(*) FROM grocer_internal.inbound_messages") == 1
    assert await postgres_pool.fetchval("SELECT count(*) FROM grocer_internal.outbound_messages") == 1
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
async def test_forged_whatsapp_signature_never_enters_inbox(postgres_pool, monkeypatch):
    app = create_app()
    app.state.agent_engine = GroceryAgentEngine(MockCommerceAdapter(), gemini_api_key="local-test")
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    body, _ = _webhook("wamid.forged", "confirm order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post(
            "/api/whatsapp/webhook", content=body,
            headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
        )
    assert response.status_code == 401
    assert await postgres_pool.fetchval("SELECT count(*) FROM grocer_internal.inbound_messages") == 0


@pytest.mark.asyncio
async def test_unreviewed_whatsapp_confirmation_cannot_call_checkout(postgres_pool, monkeypatch):
    class GuardCommerce(MockCommerceAdapter):
        checkout_calls = 0

        async def checkout(self, *args, **kwargs):
            self.checkout_calls += 1
            raise AssertionError("Unreviewed order reached the provider")

    commerce = GuardCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test",
                                attempt_store=PostgresCheckoutAttemptStore(postgres_pool))
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.unreviewed", "confirm order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert response.status_code == 200
    assert commerce.checkout_calls == 0
    assert await postgres_pool.fetchval("SELECT count(*) FROM grocer_internal.checkout_attempts") == 0


@pytest.mark.asyncio
async def test_whatsapp_replenishment_requires_consent_survives_restart_and_can_be_deleted(
    postgres_pool, monkeypatch,
):
    class OrderHistoryCommerce(MockCommerceAdapter):
        history_reads = 0

        async def get_orders(self, count=10, active_only=False):
            self.history_reads += 1
            now = datetime.now(timezone.utc)
            return [
                OrderSummary(order_id="older", normalized_status="DELIVERED",
                             created_at=(now - timedelta(days=15)).isoformat(),
                             items=[OrderLineItem(name="Milk 1 L", quantity=1)]),
                OrderSummary(order_id="newer", normalized_status="DELIVERED",
                             created_at=(now - timedelta(days=8)).isoformat(),
                             items=[OrderLineItem(name="Milk 1 L", quantity=1)]),
            ]

    commerce = OrderHistoryCommerce()
    store = PostgresMessageStore(postgres_pool)
    habits = PostgresReplenishmentStore(postgres_pool, Fernet.generate_key().decode())
    app = create_app()
    app.state.message_store = store
    app.state.agent_engine = GroceryAgentEngine(
        commerce, gemini_api_key="local-test", replenishment_store=habits,
    )
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    async def send(client, message_id, customer_text):
        body, headers = _webhook(message_id, customer_text)
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        assert response.status_code == 200
        _, reply = await store.response_for_message(message_id)
        return reply.text.casefold()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        before = await send(client, "wamid.habit-before", "What might be running low?")
        assert "opt in" in before or "turn on" in before
        assert commerce.history_reads == 0
        opted_in = await send(client, "wamid.habit-optin", "Turn on grocery reminders daily at 9 am")
        assert "daily" in opted_in and "9" in opted_in
        customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
        assert await postgres_pool.fetchval(
            "SELECT count(*) FROM grocer_internal.replenishment WHERE customer_id=$1", customer_id,
        ) == 1
        app.state.agent_engine = GroceryAgentEngine(
            commerce, gemini_api_key="local-test", replenishment_store=habits,
        )
        low = await send(client, "wamid.habit-low", "What might be running low?")
        assert "milk" in low and "may be running low" in low
        assert commerce.history_reads >= 1
        paused = await send(client, "wamid.habit-pause", "Pause grocery reminders")
        assert "paused" in paused
        resumed = await send(client, "wamid.habit-resume", "Resume grocery reminders")
        assert "resumed" in resumed
        deleted = await send(client, "wamid.habit-delete", "Delete my reminder history")
        assert "deleted" in deleted
        assert await postgres_pool.fetchval(
            "SELECT count(*) FROM grocer_internal.replenishment WHERE customer_id=$1", customer_id,
        ) == 0
    assert len(default_whatsapp_adapter.outbound_messages) == 6


@pytest.mark.asyncio
async def test_customer_corrects_low_stock_estimate_without_cart_mutation(postgres_pool, monkeypatch):
    class HistoryCommerce(MockCommerceAdapter):
        async def get_orders(self, count=10, active_only=False):
            now = datetime.now(timezone.utc)
            return [OrderSummary(
                order_id=str(days), normalized_status="DELIVERED",
                created_at=(now - timedelta(days=days)).isoformat(),
                items=[OrderLineItem(name="Milk 1 L", quantity=1)],
            ) for days in (15, 8)]

    commerce = HistoryCommerce()
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.message_store = store
    app.state.agent_engine = GroceryAgentEngine(
        commerce, gemini_api_key="local-test",
        replenishment_store=PostgresReplenishmentStore(postgres_pool, Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)

    async def send(message_id, text):
        body, headers = _webhook(message_id, text)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
            response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        assert response.status_code == 200
        _, reply = await store.response_for_message(message_id)
        return reply.text.casefold()

    await send("wamid.correct-optin", "Turn on grocery reminders daily at 9 am")
    assert "milk" in await send("wamid.correct-due", "What might be running low?")
    assert "weekly" in await send(
        "wamid.correct-frequency", "Change reminder frequency to weekly at 8 pm",
    )
    assert "milk" in await send("wamid.correct-stilldue", "What might be running low?")
    corrected = await send("wamid.correct-stock", "I still have milk for 3 more days")
    assert "3 days" in corrected
    assert "milk" not in await send("wamid.correct-notdue", "What might be running low?")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items


@pytest.mark.asyncio
async def test_delete_my_data_purges_consented_habits_through_signed_whatsapp(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    key = Fernet.generate_key().decode()
    app = create_app()
    app.state.message_store = store
    app.state.agent_engine = GroceryAgentEngine(
        MockCommerceAdapter(), gemini_api_key="local-test",
        state_store=PostgresTaskStateStore(postgres_pool, key),
        replenishment_store=PostgresReplenishmentStore(postgres_pool, key),
    )
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        for message_id, text in (("wamid.delete-optin", "Turn on grocery reminders daily at 9 am"),
                                 ("wamid.delete-all", "delete my data")):
            body, headers = _webhook(message_id, text)
            response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
            assert response.status_code == 200
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.replenishment WHERE customer_id=$1", customer_id,
    ) == 0
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.task_state WHERE customer_id=$1", customer_id,
    ) == 0
    assert "deleted" in str(default_whatsapp_adapter.outbound_messages[-1]).casefold()


@pytest.mark.asyncio
async def test_expired_order_history_auth_gets_reconnect_link_not_false_stock_result(postgres_pool, monkeypatch):
    class ExpiredHistoryCommerce(MockCommerceAdapter):
        async def get_orders(self, count=10, active_only=False):
            raise ProviderAuthError()

    app = create_app()
    app.state.agent_engine = GroceryAgentEngine(
        ExpiredHistoryCommerce(), gemini_api_key="local-test",
        replenishment_store=PostgresReplenishmentStore(postgres_pool, Fernet.generate_key().decode()),
    )
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        for message_id, text in (("wamid.auth-optin", "Turn on grocery reminders daily at 9 am"),
                                 ("wamid.auth-check", "What might be running low?")):
            body, headers = _webhook(message_id, text)
            response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
            assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.auth-check")
    assert reply.conversation_state == "AUTH_REQUIRED"
    assert "reconnect" in reply.text.casefold()
    assert "connect_ticket=" in reply.text
    assert "enough repeated" not in reply.text.casefold()


@pytest.mark.asyncio
async def test_opted_in_history_refresh_runs_without_chat_and_pause_stops_it(postgres_pool, monkeypatch):
    class CountingCommerce(MockCommerceAdapter):
        history_reads = 0

        async def get_orders(self, count=10, active_only=False):
            self.history_reads += 1
            return []

    commerce = CountingCommerce()
    habits = PostgresReplenishmentStore(postgres_pool, Fernet.generate_key().decode())
    app = create_app()
    app.state.agent_engine = GroceryAgentEngine(
        commerce, gemini_api_key="local-test", replenishment_store=habits,
    )
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    async def send(message_id, text):
        body, headers = _webhook(message_id, text)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
            response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        assert response.status_code == 200

    assert await habits.refresh_due(commerce) == 0
    assert commerce.history_reads == 0
    await send("wamid.refresh-optin", "Turn on grocery reminders daily at 9 am")
    sent_before = len(default_whatsapp_adapter.outbound_messages)
    assert await habits.refresh_due(commerce) == 1
    assert commerce.history_reads == 1
    assert await postgres_pool.fetchval(
        "SELECT next_sync_at > now() FROM grocer_internal.replenishment"
    ) is True
    assert len(default_whatsapp_adapter.outbound_messages) == sent_before
    await send("wamid.refresh-pause", "Pause grocery reminders")
    await postgres_pool.execute("UPDATE grocer_internal.replenishment SET next_sync_at=now()-interval '1 minute'")
    assert await habits.refresh_due(commerce) == 0
    assert commerce.history_reads == 1
    await send("wamid.refresh-resume", "Resume grocery reminders")
    assert await habits.refresh_due(commerce) == 1
    assert commerce.history_reads == 2
    await send("wamid.refresh-delete", "Delete my reminder history")
    assert await habits.refresh_due(commerce) == 0
    assert commerce.history_reads == 2


@pytest.mark.asyncio
async def test_incomplete_swiggy_order_details_do_not_become_no_habit_claim(postgres_pool, monkeypatch):
    class IncompleteHistoryCommerce(MockCommerceAdapter):
        async def get_orders(self, count=10, active_only=False):
            return [OrderSummary(
                order_id="needs-details", normalized_status="DELIVERED",
                created_at=datetime.now(timezone.utc).isoformat(), items=[],
            )]

        async def get_order_details(self, order_id):
            raise RuntimeError("provider detail endpoint unavailable")

    app = create_app()
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    app.state.agent_engine = GroceryAgentEngine(
        IncompleteHistoryCommerce(), gemini_api_key="local-test",
        replenishment_store=PostgresReplenishmentStore(postgres_pool, Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        for message_id, text in (("wamid.incomplete-optin", "Turn on grocery reminders daily at 9 am"),
                                 ("wamid.incomplete-check", "What might be running low?")):
            body, headers = _webhook(message_id, text)
            response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
            assert response.status_code == 200
    _, reply = await store.response_for_message("wamid.incomplete-check")
    assert "couldn't verify" in reply.text.casefold()
    assert "don't have enough" not in reply.text.casefold()


@pytest.mark.asyncio
async def test_local_simulator_uses_signed_webhook_and_rejects_customer_impersonation(
    postgres_pool, monkeypatch,
):
    monkeypatch.setattr(settings, "SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "SIMULATOR_ACCESS_TOKEN", "local-test-secret", raising=False)
    monkeypatch.setattr(settings, "SIMULATOR_SENDER_ID", "919999988888", raising=False)
    monkeypatch.setattr(settings, "COMMERCE_ADAPTER_TYPE", "mock")
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "review")
    app = create_app()
    app.state.agent_engine = GroceryAgentEngine(MockCommerceAdapter(), gemini_api_key="local-test")
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        unauthenticated = await client.post("/api/simulator/chat", json={"text": "hello"})
        forged = await client.post(
            "/api/simulator/chat", headers={"Authorization": "Bearer local-test-secret"},
            json={"text": "hello", "customer_id": "someone-else"},
        )
        response = await client.post(
            "/api/simulator/chat", headers={"Authorization": "Bearer local-test-secret"},
            json={"text": "hello"},
        )
    assert unauthenticated.status_code == 401
    assert forged.status_code == 422
    assert response.status_code == 200
    assert response.json()["conversation_state"] == "NEEDS_DECISION"
    assert await postgres_pool.fetchval("SELECT count(*) FROM grocer_internal.inbound_messages") == 1
    assert await postgres_pool.fetchval("SELECT status FROM grocer_internal.outbound_messages") == "SENT"
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
async def test_local_simulator_clear_failure_never_claims_empty_basket(postgres_pool, monkeypatch):
    class FailingClearAdapter(MockCommerceAdapter):
        async def clear_cart(self, cart_id=None):
            raise RuntimeError("provider clear unavailable")

    monkeypatch.setattr(settings, "SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "SIMULATOR_ACCESS_TOKEN", "local-test-secret")
    monkeypatch.setattr(settings, "SIMULATOR_SENDER_ID", "919999988888")
    monkeypatch.setattr(settings, "COMMERCE_ADAPTER_TYPE", "mock")
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "review")
    app = create_app()
    commerce = FailingClearAdapter()
    app.state.agent_engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/simulator/chat", headers={"Authorization": "Bearer local-test-secret"},
            json={"text": "delete all"},
        )
    assert response.status_code == 200
    assert "couldn't verify" in response.json()["text"].casefold()
    assert "cleared" not in response.json()["text"].casefold()


@pytest.mark.asyncio
async def test_unknown_meta_delivery_does_not_freeze_later_customer_message(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    engine = GroceryAgentEngine(MockCommerceAdapter(), gemini_api_key="local-test")
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    sender = "919999988888"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id(sender)
    first = NormalizedIncomingMessage(
        message_id="wamid.undelivered", channel=ChannelType.WHATSAPP,
        sender_id=sender, customer_id=customer_id, text="show cart",
    )
    await store.enqueue_many([first])
    claimed = await store.claim_next()
    assert claimed is not None
    await store.stage_response(claimed[0], NormalizedOutgoingResponse(
        recipient_id=sender, channel=ChannelType.WHATSAPP,
        text="Your basket is empty.", conversation_state="READY",
    ))
    sending = await store.claim_outbound()
    assert sending is not None
    await postgres_pool.execute(
        "UPDATE grocer_internal.outbound_messages SET sending_started_at=now()-interval '10 minutes' WHERE id=$1",
        sending[0],
    )
    body, headers = _webhook("wamid.after-failure", "hello")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        result = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert result.status_code == 200
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.outbound_messages WHERE id=$1", sending[0]
    ) == "UNKNOWN"
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.inbound_messages WHERE message_id='wamid.after-failure'"
    ) == "PROCESSED"
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("paid,already_confirmed,missing_metadata", [
    (True, True, False), (True, False, False), (False, False, False), (False, False, True),
])
async def test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart(
    postgres_pool, monkeypatch, paid, already_confirmed, missing_metadata,
):
    class PendingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.checkout_calls = 0
            self.confirm_calls = 0

        async def get_payment_options(self, cart_id=None, address_id=None):
            return [PaymentOption(id="upi-app-test", kind="intent", method="UPI", label="UPI app")]

        async def checkout(self, *args, **kwargs):
            self.checkout_calls += 1
            assert kwargs.get("payment_option_id") == "upi-app-test"
            return CommerceOrderResult(
                order_id="order-whatsapp", status="PAYMENT_PENDING",
                paas_id=None if missing_metadata else "paas-whatsapp",
                bridge_url="https://pay.swiggy.com/bridge/test", grand_total=116,
                polling_interval_ms=None if missing_metadata else 10000,
                max_time_to_poll_ms=None if missing_metadata else 60000,
            )

        async def check_payment_status(self, paas_id, order_id=None):
            assert (paas_id, order_id) == ("paas-whatsapp", "order-whatsapp")
            return PaymentStatusResult(
                paas_id=paas_id, order_id=order_id, status="paid" if paid else "failed",
                terminal=True, is_terminal_success=paid, is_terminal_failure=not paid,
                confirmed=already_confirmed,
                order_status="ORDER_PLACED" if already_confirmed else None,
            )

        async def confirm_order(self, order_id, paas_id):
            self.confirm_calls += 1
            return CommerceOrderResult(order_id=order_id, paas_id=paas_id, status="ORDER_PLACED")

    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    commerce = PendingCommerce()
    store = PostgresMessageStore(postgres_pool)
    attempts = PostgresCheckoutAttemptStore(postgres_pool)
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", attempt_store=attempts)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id="addr-bandra-1",
        )
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    session = engine.get_session(customer_id)
    session.selected_payment_id = "upi-app-test"
    session.selected_payment_kind = "intent"
    session.selected_payment_method = "UPI"

    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "checkout", "args": {"cart_id": cart.cart_id, "address_id": "addr-bandra-1"},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [{"text": "Please complete payment."}]}}]}

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.payment-confirm", "confirm order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        first = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert first.status_code == 200
    _, pending = await store.response_for_message("wamid.payment-confirm")
    assert commerce.checkout_calls == 1
    attempt_id = await postgres_pool.fetchval(
        "SELECT id FROM grocer_internal.checkout_attempts WHERE customer_id=$1", customer_id,
    )
    assert attempt_id
    if missing_metadata:
        assert pending.conversation_state == "RECOVERING"
        assert "couldn't verify" in pending.text.casefold()
        assert await postgres_pool.fetchval(
            "SELECT status FROM grocer_internal.checkout_attempts WHERE id=$1", attempt_id,
        ) == "UNKNOWN"
        assert await attempts.reconcile_due_payment(commerce) == 0
        assert len(default_whatsapp_adapter.outbound_messages) == 1
        return
    assert pending.conversation_state == "AWAITING_PAYMENT"
    assert "https://pay.swiggy.com/bridge/test" in pending.text
    restarted = PostgresCheckoutAttemptStore(postgres_pool)
    await postgres_pool.execute(
        """UPDATE grocer_internal.outbound_messages SET status='QUEUED', sent_at=NULL
           WHERE inbound_id=(SELECT id FROM grocer_internal.inbound_messages WHERE message_id='wamid.payment-confirm')"""
    )
    assert await restarted.reconcile_due_payment(commerce) == 0
    await postgres_pool.execute(
        """UPDATE grocer_internal.outbound_messages SET status='SENT', sent_at=now()
           WHERE inbound_id=(SELECT id FROM grocer_internal.inbound_messages WHERE message_id='wamid.payment-confirm')"""
    )
    assert await restarted.reconcile_due_payment(commerce) == 1
    await drain_message_queue(store, engine)
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.checkout_attempts WHERE id=$1", attempt_id,
    ) == ("PLACED" if paid else "PAYMENT_FAILED")
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.outbound_messages WHERE payment_attempt_id=$1", attempt_id,
    ) == "SENT"
    assert commerce.checkout_calls == 1
    assert commerce.confirm_calls == (0 if already_confirmed or not paid else 1)
    assert len(default_whatsapp_adapter.outbound_messages) == 2
