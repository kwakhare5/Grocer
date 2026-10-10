"""Planning clarification, plan repair, and English catalog search tests."""
from __future__ import annotations

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
        if model_calls > 1:
            assert "milk" in _history[0]["parts"][0]["text"].casefold()
            assert "full cream" in _history[0]["parts"][0]["text"].casefold()
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [{"query": "full cream milk"}]},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [
            {"text": "Do you prefer toned or full cream milk?"},
        ]}}]}

    engine._call_llm = model_question  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
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
    assert "full cream milk" in answer_reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("request_text,first_items,repaired_items,required_queries", [
    (
        "I need 2 packets of 500 ml milk and one brown bread, under ₹130. No eggs.",
        ["milk", "brown bread"],
        [{"query": "milk", "quantity": 2, "preferred_pack_size": "500 ml"},
         {"query": "brown bread", "quantity": 1}],
        ("milk", "brown bread"),
    ),
    (
        "Make pizza ingredients under ₹1,000 and also add bread, Bournvita, tissues and a pencil",
        [{"query": "pizza ingredients"}, {"query": "bread"}, {"query": "Bournvita"},
         {"query": "tissues"}, {"query": "pencil"}],
        [{"query": query} for query in (
            "pizza base", "pizza sauce", "mozzarella", "bread", "Bournvita", "tissues", "pencil",
        )],
        ("pizza base", "pizza sauce", "mozzarella", "bread", "Bournvita", "tissues", "pencil"),
    ),
])
async def test_invalid_model_plan_is_repaired_before_catalog_search(
    postgres_pool, monkeypatch, request_text, first_items, repaired_items, required_queries,
):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True
    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        items = first_items if model_calls == 1 else repaired_items
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": items},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    body, headers = _webhook("wamid.repair-plan", request_text)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.repair-plan")
        if (address_reply.interactive_actions
                and address_reply.interactive_actions[0].id.startswith("addr_choice_")):
            choice = address_reply.interactive_actions[0]
            choice_body, choice_headers = _interactive_webhook(
                "wamid.repair-plan-address", choice.id, choice.title,
            )
            assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message(
        "wamid.repair-plan-address" if (address_reply.interactive_actions
                                        and address_reply.interactive_actions[0].id.startswith("addr_choice_"))
        else "wamid.repair-plan"
    )
    proposal = engine.get_session(customer_id).pending_variant_selection
    assert model_calls == 2
    assert proposal is not None, reply.text
    accounted = [group["query"].casefold() for group in proposal["groups"]]
    accounted += [item.casefold() for item in proposal.get("unavailable_items", [])]
    for query in required_queries:
        assert query.casefold() in accounted
    if "milk" in required_queries:
        milk = next(group for group in proposal["groups"] if group["query"] == "milk")
        assert milk["quantity"] == 2
        assert all(option["pack_size"] == "500 ml" for option in milk["options"])
    with commerce.customer_scope(customer_id):
        assert not (await commerce.get_cart()).items
    await engine.close()


@pytest.mark.asyncio
async def test_hinglish_groceries_search_english_catalog_without_losing_user_items(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [
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


