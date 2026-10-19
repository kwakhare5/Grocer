"""Planning clarification, plan repair, and English catalog search tests."""
from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.engine import GroceryAgentEngine
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.main import create_app
from backend.tests.suites.helpers import _interactive_webhook, _webhook

@pytest.mark.asyncio
async def test_planning_clarification_reaches_customer_without_false_cart_claim(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    model_calls = 0

    async def model_question(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {"candidates": [{"content": {"parts": [
                {"text": "Do you prefer toned or full cream milk?"},
            ]}}]}
        elif model_calls == 2:
            assert len(_history) == 3
            assert _history[0]["role"] == "user"
            assert "milk" in _history[0]["parts"][0]["text"].casefold()
            assert _history[1]["role"] == "model"
            assert "toned or full cream" in _history[1]["parts"][0]["text"].casefold()
            assert _history[2]["role"] == "user"
            assert _history[2]["parts"][0]["text"] == "Full cream"
            assert "use delivery address" not in _history[2]["parts"][0]["text"].casefold()
            for entry in _history:
                for part in entry.get("parts", []):
                    text = part.get("text", "")
                    assert "i want milk but ask me what kind first (" not in text.casefold()
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [{"query": "full cream milk"}]},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [
            {"text": "I've added full cream milk to your basket."},
        ]}}]}

    engine._call_llm = model_question  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    monkeypatch.setattr("backend.agent.react_coordinator.check_reply_claims", AsyncMock(return_value="no"))
    body, headers = _webhook("wamid.clarify-milk", "I want milk but ask me what kind first")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.clarify-milk")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook(
            "wamid.clarify-milk-address", choice.id, choice.title,
        )
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.clarify-milk-address")
    assert "toned or full cream" in reply.text.casefold()
    assert "added" not in reply.text.casefold()
    answer_body, answer_headers = _webhook("wamid.clarify-milk-answer", "Full cream")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=answer_body, headers=answer_headers)).status_code == 200
    _, answer_reply = await store.response_for_message("wamid.clarify-milk-answer")
    assert "milk" in answer_reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
async def test_hinglish_groceries_search_english_catalog_without_losing_user_items(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [
                {"query": "milk"}, {"query": "rice"},
            ]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.english", "Milk and rice please")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.english")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.english-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.english-address")
    assert "milk" in reply.text.casefold()
    assert "rice" in reply.text.casefold()
    await engine.close()


__all__ = [
    "test_planning_clarification_reaches_customer_without_false_cart_claim",
    "test_hinglish_groceries_search_english_catalog_without_losing_user_items",
]


