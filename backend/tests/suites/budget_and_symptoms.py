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
@pytest.mark.parametrize("request_text, products, kept_spin, left_out, cap", [
    ("Add milk and bread under 80", ["milk", "bread"], "SPIN-MILK-500ML", "bread", 80),
    ("Get pasta and sauce, at most 100 rupees", ["pasta", "sauce"], "SPIN-PASTA-PENNE-500G", "sauce", 100),
    ("Need oil plus eggs within 180", ["oil", "eggs"], "SPIN-OIL-1L", "eggs", 180),
])
async def test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage(
    postgres_pool, monkeypatch, request_text, products, kept_spin, left_out, cap,
):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    async def mock_variant_picker(prompt, *args, **kwargs):
        # mock: pick cheapest / smallest pack matching requested query so rupee cap test is meaningful
        import re
        qm = re.search(r"Customer request:\s*'([^']+)'", prompt)
        q = qm.group(1).casefold() if qm else ""
        cands = re.findall(r"ID:\s*(\d+)\s*\|\s*Name:\s*([^|\n]+)[^\n]*?Price:\s*.*?([\d.]+)", prompt)
        matching = [c for c in cands if re.search(r"\b" + re.escape(q) + r"\b", c[1], re.IGNORECASE)] or cands
        if matching:
            cheapest_id = min(matching, key=lambda c: float(c[2]))[0]
            return {"action": "pick", "candidate_id": str(cheapest_id), "reason": "mock: pick cheapest pack"}, None
        return {"action": "pick", "candidate_id": "1", "reason": "mock: pick default"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": item} for item in products]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary

    async def stub_budget_cap(_text):
        return cap

    engine._read_budget_cap = stub_budget_cap
    app = create_app()
    app.state.agent_engine = engine
    store = PostgresMessageStore(postgres_pool)
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook(f"wamid.plain-budget-{cap}", request_text)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
    _, reply = await store.response_for_message(f"wamid.plain-budget-{cap}")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert [item.spin_id for item in cart.items] == [kept_spin], (reply.text, cart.items)
    assert cart.grand_total <= cap
    assert left_out in reply.text.casefold()
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_query", ["Bournvita", "tofu"])
async def test_missing_requested_item_requires_review_before_checkout(postgres_pool, monkeypatch, missing_query):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def mock_variant_picker(*args, **kwargs):
        return {"action": "pick", "candidate_id": "1", "reason": "mock: bread pick"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker
    calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [
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

    async def mock_gemini_structured(*args, **kwargs):
        # mock: variant picker and item drop guard
        schema = kwargs.get("response_schema") or (args[2] if len(args) > 2 else {})
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if "missing_items" in props:
            return {"missing_items": omitted}, None
        return {"action": "pick", "candidate_id": "1", "reason": "mock: pick item"}, None

    engine.gemini.generate_structured_with_reason = mock_gemini_structured

    async def incomplete_model(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket",
            "args": {"add": [{"query": query} for query in model_items]},
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
    for item in omitted:
        assert item.casefold() in reply.text.casefold()
    if omitted:
        assert not any(
            action.id == "confirm_order" or action.id.startswith("confirm_order:")
            for action in reply.interactive_actions
        )
        assert reply.conversation_state == "NEEDS_DECISION"
    else:
        assert any(
            action.id == "confirm_order" or action.id.startswith("confirm_order:")
            for action in reply.interactive_actions
        )
        assert reply.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    await engine.close()


@pytest.mark.asyncio
async def test_provider_dropped_manage_basket_item_is_named_before_partial_review(postgres_pool, monkeypatch):
    commerce = MockCommerceAdapter()
    commerce.inject_partial_cart_drop("SPIN-MILK-1L")
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    async def mock_variant_picker(*args, **kwargs):
        return {"action": "pick", "candidate_id": "1", "reason": "mock: pick item"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker
    calls = 0

    async def add_two(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [
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
    _, reply = await store.response_for_message("wamid.dropped-request")
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert {item.spin_id for item in cart.items} == {"SPIN-BREAD-400G"}
    assert "milk" in reply.text.casefold(), repr(reply.text)
    assert reply.conversation_state == "NEEDS_DECISION"
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)
    await engine.close()


@pytest.mark.asyncio
async def test_symptom_message_suggests_groceries_without_adding_medicine(
    postgres_pool, monkeypatch,
):
    store = PostgresMessageStore(postgres_pool)
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    async def mock_variant_picker(*args, **kwargs):
        schema = kwargs.get("response_schema") or (args[1] if len(args) > 1 else {})
        if isinstance(schema, dict) and "candidate_id" in schema.get("properties", {}):
            return {"action": "pick", "candidate_id": "1", "reason": "mock: ginger pick"}, None
        return {"verdict": "supported", "reason": "mock: claims supported"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker

    calls = 0
    async def model_reply(_history, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [{"query": "Vicks"}, {"query": "ginger"}]},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [{"text": "I cannot add medicine like Vicks, but ginger can help soothe a cold. Would you like me to add ginger?"}]}}]}

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
    await engine.close()


