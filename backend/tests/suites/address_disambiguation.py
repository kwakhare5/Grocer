"""Address disambiguation and outage recovery tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from backend.agent.engine import GroceryAgentEngine
from backend.agent.task_state import PostgresTaskStateStore
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.main import create_app
from backend.tests.suites.helpers import _interactive_webhook, _webhook


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
async def test_retry_preserves_pending_grocery_basket_during_address_disambiguation(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = PostgresMessageStore(postgres_pool)
    store = app.state.message_store
    model_prompts = []

    async def mock_model(history, **_kwargs):
        if len(model_prompts) == 0:
            model_prompts.append("turn-1-failed")
            return None
        prompt = next(
            part["text"] for entry in reversed(history) if entry.get("role") == "user"
            for part in entry.get("parts", []) if "text" in part
        )
        model_prompts.append(prompt)
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": "eggs"}, {"query": "paracetamol"}, {"query": "milk"}]},
        }}]}}]}

    engine._call_llm = mock_model
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("918237803170")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        b1, h1 = _webhook("wamid.retry-test-1", "2 packet eggs, 1 strip paracetamol, and half litre toned milk under 120", sender="918237803170")
        r1 = await client.post("/api/whatsapp/webhook", content=b1, headers=h1)
        assert r1.status_code == 200
        _, reply1 = await store.response_for_message("wamid.retry-test-1")
        assert "try again" in reply1.text.casefold()

        session = engine.get_session(customer_id)
        assert session.pending_request_text == "2 packet eggs, 1 strip paracetamol, and half litre toned milk under 120"

        b2, h2 = _webhook("wamid.retry-test-2", "try again", sender="918237803170")
        r2 = await client.post("/api/whatsapp/webhook", content=b2, headers=h2)
        assert r2.status_code == 200
        _, reply2 = await store.response_for_message("wamid.retry-test-2")
        assert reply2.interactive_actions or "1." in reply2.text
        assert session.pending_request_text == "2 packet eggs, 1 strip paracetamol, and half litre toned milk under 120"

        b3, h3 = _webhook("wamid.retry-test-3", "2", sender="918237803170")
        r3 = await client.post("/api/whatsapp/webhook", content=b3, headers=h3)
        assert r3.status_code == 200
        _, reply3 = await store.response_for_message("wamid.retry-test-3")

        assert len(model_prompts) >= 2
        last_prompt = model_prompts[-1].casefold()
        assert "eggs" in last_prompt and "paracetamol" in last_prompt and "milk" in last_prompt
        assert "try again" not in last_prompt
