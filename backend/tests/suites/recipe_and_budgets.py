"""Recipe ingredient decomposition, budget caps, and review gating tests."""
from __future__ import annotations

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.engine import GroceryAgentEngine
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.exceptions import ProviderRateLimitedError
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
)
from backend.main import create_app
from backend.tests.suites.helpers import (
    _interactive_webhook,
    _webhook,
)

RECIPE_AND_EXTRAS_REQUEST_TEXTS = [
    ("Make pizza ingredients under ₹1,000 and also add bread, Bournvita, tissues and a pencil",
     ("pizza base", "pizza sauce", "mozzarella", "bread", "bournvita", "tissues", "pencil")),
    ("I need 2 packets of 500 ml milk and one brown bread, under ₹130. No eggs.",
     ("milk", "bread")),
    ("Pasta tonight for two. Please get pasta, sauce and cheese, plus tissues for the house.",
     ("pasta", "sauce", "cheese", "tissues")),
    ("Pick up toothpaste, shampoo and garbage bags for the flat.",
     ("toothpaste", "shampoo", "garbage bags")),
    ("We're making chai: add milk, ginger and tea.",
     ("milk", "ginger", "tea")),
    ("Need olive oil, mushrooms and paneer.",
     ("olive oil", "mushroom", "paneer")),
    ("Please add dishwash liquid, handwash and a matchbox.",
     ("dishwash", "handwash", "matchbox")),
    ("Get dahi, onions and potatoes; skip paneer.",
     ("dahi", "onions", "potatoes")),
    ("Put tea, coffee and sugar on the shopping list.",
     ("tea", "coffee", "sugar")),
    ("I have pizza base and mozzarella at home. Please get pizza sauce, mushrooms and tissues.",
     ("pizza sauce", "mushroom", "tissues")),
    ("Milk, yogurt, flour, rice, ginger, onion and potato for this week.",
     ("milk", "yogurt", "flour", "rice", "ginger", "onion", "potato")),
    ("Need dishwash liquid, floor cleaner, garbage bags; plus bananas.",
     ("dishwash", "floor cleaner", "garbage bags", "banana")),
    ("For sandwiches get brown bread, cucumber, tomato and cheese slices; also a toothbrush.",
     ("brown bread", "cucumber", "tomato", "cheese", "toothbrush")),
    ("Buy olive oil and two packs of oats. No sugar.",
     ("olive oil", "oats")),
    ("We have pasta and sauce already. Just get cheese, mushrooms and tissues.",
     ("cheese", "mushroom", "tissues")),
    ("Grab batteries, a notebook, pencils, and a packet of biscuits.",
     ("batteries", "notebook", "pencil", "biscuit")),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("parallel_calls", ["single", "split", "with_cart", "same_address"])
async def test_long_recipe_request_uses_one_product_choice_batch(postgres_pool, monkeypatch, parallel_calls):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def mock_variant_picker(prompt, *args, **kwargs):
        # mock: candidate picker
        return {"action": "pick", "candidate_id": "1", "reason": "mock: item pick"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker
    model_calls = 0
    invalid_protocol_calls = 0

    async def model_boundary(contents, **kwargs):
        nonlocal model_calls, invalid_protocol_calls
        model_calls += 1
        if model_calls > 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [{"query": "eggs"}]},
            }}]}}]}

        choice_tool = next(tool for tool in RAW_TOOL_DECLARATIONS if tool["name"] == "manage_basket")
        assert "budget_cap_inr" not in choice_tool["parameters"]["properties"]

        if parallel_calls == "split":
            parts = [
                {"functionCall": {"name": "manage_basket", "args": {"add": [
                    {"query": "pizza base"}, {"query": "pizza sauce"}, {"query": "mozzarella"},
                ]}}},
                {"functionCall": {"name": "manage_basket", "args": {"add": [
                    {"query": "bread"}, {"query": "Bournvita"},
                    {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        elif parallel_calls == "with_cart":
            parts = [
                {"functionCall": {"name": "get_cart", "args": {}}},
                {"functionCall": {"name": "manage_basket", "args": {"add": [
                    {"query": "pizza base"}, {"query": "pizza sauce"},
                    {"query": "mozzarella"}, {"query": "bread"},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        elif parallel_calls == "same_address":
            parts = [
                {"functionCall": {"name": "select_delivery_address", "args": {"address_id": "addr-bandra-1"}}},
                {"functionCall": {"name": "manage_basket", "args": {"add": [
                    {"query": "pizza base"}, {"query": "pizza sauce"},
                    {"query": "mozzarella"}, {"query": "bread"},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        else:
            parts = [
                {"functionCall": {"name": "manage_basket", "args": {"add": [
                    {"query": "pizza base"}, {"query": "pizza sauce"},
                    {"query": "mozzarella"}, {"query": "bread"},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        return {"candidates": [{"content": {"parts": parts}}]}

    engine._call_llm = model_boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook(
        "wamid.long-recipe", "Make pizza ingredients under ₹1,000 and also add bread, Bournvita, tissues and a pencil",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        result = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        _, address_reply = await store.response_for_message("wamid.long-recipe")
        choice = address_reply.interactive_actions[0]
        if parallel_calls == "with_cart":
            with commerce.customer_scope(customer_id):
                await commerce.update_cart(
                    [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
                    address_id="addr-bandra-1",
                )
        choice_body, choice_headers = _interactive_webhook(
            "wamid.long-recipe-address", choice.id, choice.title,
        )
        selected = await client.post(
            "/api/whatsapp/webhook", content=choice_body, headers=choice_headers,
        )
    _, reply = await store.response_for_message("wamid.long-recipe-address")
    assert result.status_code == 200
    assert selected.status_code == 200
    assert model_calls == 1
    assert "pizza base" in reply.text.casefold()
    for item in ("pizza sauce", "mozzarella", "bread", "bournvita", "tissues", "pencil"):
        assert item in reply.text.casefold()
    if parallel_calls == "with_cart":
        assert "milk" in reply.text.casefold()
    assert "maximum processing steps" not in reply.text.casefold()
    assert len(default_whatsapp_adapter.outbound_messages) == 2
    accept_body, accept_headers = _interactive_webhook(
        "wamid.long-recipe-accept", "accept_partial_basket", "Keep These Items"
    )
    eggs_body, eggs_headers = _webhook("wamid.long-recipe-eggs", "add eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=accept_body, headers=accept_headers)).status_code == 200
        assert (await client.post("/api/whatsapp/webhook", content=eggs_body, headers=eggs_headers)).status_code == 200
    _, eggs_reply = await store.response_for_message("wamid.long-recipe-eggs")
    assert "eggs" in eggs_reply.text.casefold()
    assert invalid_protocol_calls == 0
    assert model_calls == 2
    await engine.close()


@pytest.mark.asyncio
async def test_long_list_checks_every_item_in_paced_batches(postgres_pool, monkeypatch):
    class TrackingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.search_calls = []
            self.active = 0
            self.waves = []
            self._current_wave = []

        async def search_products(self, address_id, query):
            self.search_calls.append(query)
            self._current_wave.append(query)
            self.active += 1
            await asyncio.sleep(0.005)
            self.active -= 1
            if self.active == 0:
                self.waves.append(list(self._current_wave))
                self._current_wave.clear()
            return await super().search_products(address_id, query)

    queries = ["milk", "bread", "eggs", "tomato", "coke", "maggi", "atta", "rice", "dal"]
    commerce = TrackingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def mock_variant_picker(*args, **kwargs):
        return {"action": "pick", "candidate_id": "1", "reason": "mock: default item pick"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": query} for query in queries]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    body, headers = _webhook("wamid.long-list", "Add milk, bread, eggs, tomato, coke, maggi, atta, rice and dal")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.long-list")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook("wamid.long-list-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.long-list-address")

    # Assert 9 items are searched in 3 groups of 3
    assert len(commerce.search_calls) == 9
    assert len(commerce.waves) == 3
    for wave in commerce.waves:
        assert len(wave) == 3

    # Assert all 9 results used in cart
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert len(cart.items) == 9
    assert reply.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("generic_error_first", [False, True])
async def test_catalog_rate_limit_stops_remaining_search_waves(postgres_pool, monkeypatch, generic_error_first):
    class RateLimitedCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.search_calls = 0

        async def search_products(self, address_id, query):
            self.search_calls += 1
            if generic_error_first and self.search_calls == 1:
                raise RuntimeError("temporary catalogue fault")
            if self.search_calls == (2 if generic_error_first else 1):
                raise ProviderRateLimitedError(30)
            return await super().search_products(address_id, query)

    commerce = RateLimitedCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": query} for query in (
                "milk", "bread", "eggs", "tomato", "coke", "maggi", "atta", "rice",
            )]},
        }}]}}]}

    engine._call_llm = model_reply  # external model boundary
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.search-rate-limit", "Add milk, bread, eggs, tomato, coke, maggi, atta and rice")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.search-rate-limit")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook("wamid.search-rate-limit-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.search-rate-limit-address")
    assert commerce.search_calls <= 3
    assert "limiting requests" in reply.text.casefold()
    assert engine.get_session(default_whatsapp_adapter.map_sender_to_customer_id("919999988888")).pending_request_text
    await engine.close()


from backend.tests.suites.budget_and_symptoms import (
    test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage,
    test_missing_requested_item_requires_review_before_checkout,
    test_model_cannot_silently_drop_explicit_shopping_items,
    test_provider_dropped_manage_basket_item_is_named_before_partial_review,
    test_symptom_message_suggests_groceries_without_adding_medicine,
)

__all__ = [
    "RECIPE_AND_EXTRAS_REQUEST_TEXTS",
    "test_long_recipe_request_uses_one_product_choice_batch",
    "test_long_list_checks_every_item_in_paced_batches",
    "test_catalog_rate_limit_stops_remaining_search_waves",
    "test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage",
    "test_missing_requested_item_requires_review_before_checkout",
    "test_model_cannot_silently_drop_explicit_shopping_items",
    "test_provider_dropped_manage_basket_item_is_named_before_partial_review",
    "test_symptom_message_suggests_groceries_without_adding_medicine",
]
