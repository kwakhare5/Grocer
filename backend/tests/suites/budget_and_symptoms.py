"""Budget limits, rupee caps, missing items, and symptom redirection tests."""
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
@pytest.mark.parametrize("request_text, products, choice_codes, kept_spin, left_out, cap", [
    ("Add milk and bread under 80", ["milk", "bread"], "1B 2A", "SPIN-MILK-500ML", "bread", 80),
    ("Get pasta and sauce, at most 100 rupees", ["pasta", "sauce"], "1A 2A",
     "SPIN-PASTA-PENNE-500G", "sauce", 100),
    ("Need oil plus eggs within 180", ["oil", "eggs"], "1A 2B", "SPIN-OIL-1L", "eggs", 180),
])
async def test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage(
    postgres_pool, monkeypatch, request_text, products, choice_codes, kept_spin, left_out, cap,
):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": item} for item in products]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.plain-budget", request_text)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.plain-budget")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.plain-budget-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        body, headers = _webhook("wamid.plain-budget-choices", choice_codes)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.plain-budget-choices")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert [item.spin_id for item in cart.items] == [kept_spin], (reply.text, cart.items)
    assert cart.grand_total <= cap
    assert left_out in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)
    await engine.close()


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
@pytest.mark.parametrize("request_text, model_items, omitted", [
    ("Add milk, bread and tissues", ["milk", "bread"], ["tissues"]),
    ("Get dal, sugar and garlic for dinner", ["dal", "garlic", "eggs"], ["sugar"]),
    ("Pick up tea, coffee and bananas for breakfast. No eggs.",
     ["tea", "coffee", "bananas", "eggs"], []),
    ("Make pizza ingredients under ₹1,000 and also add bread, Bournvita, tissues and a pencil",
     ["pizza base", "pizza sauce", "mozzarella", "bread"], ["Bournvita", "tissues", "pencil"]),
])
async def test_model_cannot_silently_drop_explicit_shopping_items(
    postgres_pool, monkeypatch, request_text, model_items, omitted,
):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def incomplete_model(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items",
            "args": {"items": [{"query": query} for query in model_items]},
        }}]}}]}

    engine._call_llm = incomplete_model  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.omitted-list", request_text)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.omitted-list")
        choice = address_reply.interactive_actions[0]
        body, headers = _interactive_webhook("wamid.omitted-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.omitted-address")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    proposal = engine.get_session(customer_id).pending_variant_selection
    assert proposal is not None, reply.text
    accounted = [group["query"].casefold() for group in proposal["groups"]]
    accounted += [item.casefold() for item in proposal["unavailable_items"]]
    accounted += [item.casefold() for item in proposal["restricted_items"]]
    for item in omitted:
        assert item.casefold() in accounted, (item, accounted, reply.text)
        assert item.casefold() in reply.text.casefold()
    if request_text.startswith("Add milk"):
        assert accounted == ["milk", "bread", "tissues"], accounted
    if request_text.startswith("Get dal"):
        assert accounted == ["dal", "sugar", "garlic"], accounted
    if request_text.startswith("Pick up"):
        assert accounted == ["tea", "coffee", "bananas"], accounted
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)
    await engine.close()


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


