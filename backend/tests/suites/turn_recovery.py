"""Turn recovery, greetings, and cart display E2E tests."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.engine import GroceryAgentEngine
from backend.channels.message_store import PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate
from backend.main import create_app
from backend.tests.suites.helpers import _webhook


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
async def test_greeting_does_not_ask_for_delivery_address_or_use_swiggy(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def unexpected_provider_call(*_args, **_kwargs):
        raise AssertionError("Greeting should not need a Swiggy call")

    commerce.search_products = unexpected_provider_call
    commerce.update_cart = unexpected_provider_call
    commerce.checkout = unexpected_provider_call
    commerce.clear_cart = unexpected_provider_call

    async def fake_model(_history, **_kwargs):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello! How can I help you today?"}]
                    }
                }
            ]
        }

    async def mock_read_budget_cap(text: str) -> float | None:
        return None

    engine._call_llm = fake_model
    engine._read_budget_cap = mock_read_budget_cap

    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"

    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.greeting", "Hi")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.greeting")
    assert "which address" not in reply.text.casefold()
    assert "address" not in reply.text.casefold()
    assert "cart" not in reply.text.casefold()
    assert "basket" not in reply.text.casefold()
    assert not reply.interactive_actions
    assert len(default_whatsapp_adapter.outbound_messages) == 1
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("populated", [False, True])
async def test_show_cart_does_not_demand_an_address(postgres_pool, monkeypatch, populated):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    step = 0

    async def scripted_call_llm(_history, **_kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "get_cart",
                                        "args": {},
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        text = "You have 1x Nandini Pure Milk 1L in your cart." if populated else "Your cart is completely empty."
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": text}]
                    }
                }
            ]
        }

    async def mock_read_budget_cap(text: str) -> float | None:
        return None

    engine._call_llm = scripted_call_llm
    engine._read_budget_cap = mock_read_budget_cap
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"

    if populated:
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
    assert len(default_whatsapp_adapter.outbound_messages) == 1
    await engine.close()


@pytest.mark.asyncio
async def test_food_already_at_home_does_not_select_home_delivery_address(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def no_model_before_address(_history, **_kwargs):
        raise AssertionError("The customer has not selected a delivery address")

    engine._call_llm = no_model_before_address
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook(
        "wamid.at-home-pantry",
        "I have pizza base and mozzarella at home. Please get pizza sauce, mushrooms and tissues.",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.at-home-pantry")
    assert "which address" in reply.text.casefold()
    assert any(action.id.startswith("addr_choice_") for action in reply.interactive_actions)
    await engine.close()
