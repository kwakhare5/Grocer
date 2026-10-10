"""Recipe ingredient decomposition, budget caps, and review gating tests."""
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
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
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
@pytest.mark.parametrize("parallel_calls", ["single", "split", "with_cart", "same_address"])
async def test_long_recipe_request_uses_one_product_choice_batch(postgres_pool, monkeypatch, parallel_calls):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    model_calls = 0
    invalid_protocol_calls = 0

    async def model_boundary(contents, planning_only=False, **kwargs):
        nonlocal model_calls, invalid_protocol_calls
        model_calls += 1
        if model_calls > 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "quick_add_items", "args": {"items": [{"query": "eggs"}]},
            }}]}}]}

        choice_tool = next(tool for tool in RAW_TOOL_DECLARATIONS if tool["name"] == "quick_add_items")
        assert "budget_cap_inr" not in choice_tool["parameters"]["properties"]

        if parallel_calls == "split":
            parts = [
                {"functionCall": {"name": "quick_add_items", "args": {"items": [
                    {"query": "pizza base"}, {"query": "pizza sauce"}, {"query": "mozzarella"},
                ]}}},
                {"functionCall": {"name": "quick_add_items", "args": {"items": [
                    {"query": "bread"}, {"query": "Bournvita"},
                    {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        elif parallel_calls == "with_cart":
            parts = [
                {"functionCall": {"name": "get_cart", "args": {}}},
                {"functionCall": {"name": "quick_add_items", "args": {"items": [
                    {"query": "pizza base"}, {"query": "pizza sauce"},
                    {"query": "mozzarella"}, {"query": "bread"},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        elif parallel_calls == "same_address":
            parts = [
                {"functionCall": {"name": "select_delivery_address", "args": {"address_id": "addr-bandra-1"}}},
                {"functionCall": {"name": "quick_add_items", "args": {"items": [
                    {"query": "pizza base"}, {"query": "pizza sauce"},
                    {"query": "mozzarella"}, {"query": "bread"},
                    {"query": "Bournvita"}, {"query": "tissues"}, {"query": "pencil"},
                ]}}},
            ]
        else:
            parts = [
                {"functionCall": {"name": "quick_add_items", "args": {"items": [
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
    assert engine.get_session(customer_id).pending_variant_selection is not None
    assert "pizza base" in reply.text.casefold()
    for item in ("pizza sauce", "mozzarella", "bread", "bournvita", "tissues", "pencil"):
        assert item in reply.text.casefold()
    if parallel_calls == "with_cart":
        assert "milk" in reply.text.casefold()
    assert "maximum processing steps" not in reply.text.casefold()
    assert len(default_whatsapp_adapter.outbound_messages) == 2
    cancel_body, cancel_headers = _webhook("wamid.long-recipe-cancel", "cancel")
    eggs_body, eggs_headers = _webhook("wamid.long-recipe-eggs", "add eggs")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=cancel_body, headers=cancel_headers)).status_code == 200
        assert (await client.post("/api/whatsapp/webhook", content=eggs_body, headers=eggs_headers)).status_code == 200
    _, eggs_reply = await store.response_for_message("wamid.long-recipe-eggs")
    assert "eggs" in eggs_reply.text.casefold()
    assert invalid_protocol_calls == 0
    assert model_calls == 2
    assert engine.get_session(customer_id).pending_variant_selection is not None
    await engine.close()


@pytest.mark.asyncio
async def test_long_list_checks_every_item_in_paced_batches(postgres_pool, monkeypatch):
    class TrackingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.search_started = []

        async def search_products(self, address_id, query):
            self.search_started.append(time.monotonic())
            return await super().search_products(address_id, query)

    queries = ["milk", "bread", "eggs", "tomato", "coke", "maggi", "atta",
               "rice", "dal", "sugar", "oil"]
    commerce = TrackingCommerce()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")

    async def model_reply(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "quick_add_items", "args": {"items": [{"query": query} for query in queries]},
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
    body, headers = _webhook("wamid.long-list", "Add milk, bread, eggs, tomato, coke, maggi, atta, rice, dal, sugar and oil")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.long-list")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook("wamid.long-list-address", choice.id, choice.title)
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.long-list-address")
    proposal = engine.get_session(customer_id).pending_variant_selection
    assert proposal is not None, reply.text
    accounted = [group["query"] for group in proposal["groups"]] + proposal.get("unavailable_items", [])
    assert accounted == queries
    assert len(commerce.search_started) == 11
    assert commerce.search_started[8] - commerce.search_started[0] >= 5.5
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
            "name": "quick_add_items", "args": {"items": [{"query": query} for query in (
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


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("GROCER_REAL_MODEL_E2E") != "1", reason="Opt-in real model call")
@pytest.mark.parametrize("request_text, required_items", [
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
])
async def test_real_model_presents_recipe_and_extras_choices_over_whatsapp_path(
    postgres_pool, monkeypatch, request_text, required_items,
):
    assert settings.GEMINI_API_KEY, "Real model E2E needs a configured Gemini key"
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key=settings.GEMINI_API_KEY)
    real_call = engine._call_llm
    raw_tool_calls = []

    async def record_model_call(*args, **kwargs):
        response = await real_call(*args, **kwargs)
        if response:
            raw_tool_calls.extend(part["functionCall"] for candidate in response.get("candidates", [])
                                  for part in candidate.get("content", {}).get("parts", [])
                                  if "functionCall" in part)
        return response

    engine._call_llm = record_model_call
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    body, headers = _webhook("wamid.real-recipe", request_text)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.post("/api/whatsapp/webhook", content=body, headers=headers)).status_code == 200
        _, address_reply = await store.response_for_message("wamid.real-recipe")
        choice = address_reply.interactive_actions[0]
        choice_body, choice_headers = _interactive_webhook(
            "wamid.real-recipe-address", choice.id, choice.title,
        )
        assert (await client.post("/api/whatsapp/webhook", content=choice_body, headers=choice_headers)).status_code == 200
    _, reply = await store.response_for_message("wamid.real-recipe-address")
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    tool_calls = [part["functionCall"] for entry in engine.get_history(customer_id)
                  for part in entry.get("parts", []) if "functionCall" in part]
    assert reply.conversation_state == "NEEDS_DECISION", (
        reply.text, [(call.get("name"), len(call.get("args", {}).get("items", []))) for call in tool_calls]
    )
    for item in required_items:
        assert item in reply.text.casefold(), (
            item, reply.text, [(call.get("name"), call.get("args", {}).get("address_id"),
                                len(call.get("args", {}).get("items", []))) for call in raw_tool_calls]
        )
    proposal = engine.get_session(customer_id).pending_variant_selection
    assert proposal is not None
    accounted = [str(group["query"]).casefold() for group in proposal["groups"]]
    accounted += [str(item).casefold() for item in proposal.get("unavailable_items", [])]
    accounted += [str(item).casefold() for item in proposal.get("restricted_items", [])]
    for item in required_items:
        if item == "pizza sauce":
            assert any(
                "pizza" in group["query"].casefold()
                and "sauce" in group["query"].casefold()
                and any(
                    "pizza" in option["name"].casefold()
                    and "sauce" in option["name"].casefold()
                    for option in group["options"]
                )
                for group in proposal["groups"]
            ), (item, proposal["groups"])
        else:
            assert any(item in query for query in accounted), (item, accounted)
    if "500 ml milk" in request_text:
        milk_groups = [group for group in proposal["groups"] if "milk" in group["query"].casefold()]
        assert len(milk_groups) == 1 and milk_groups[0]["quantity"] == 2
        assert all("500" in option["pack_size"] for option in milk_groups[0]["options"])
        assert not any("egg" in query for query in accounted)
    if "skip paneer" in request_text:
        assert not any("paneer" in query for query in accounted)
    assert "nothing has been added" in reply.text.casefold(), reply.text
    assert len(default_whatsapp_adapter.outbound_messages) == 2
    await engine.close()


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


from backend.tests.suites.budget_and_symptoms import (
    test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage,
    test_missing_requested_item_requires_review_before_checkout,
    test_recipe_request_cannot_silently_omit_pizza_base,
    test_model_cannot_silently_drop_explicit_shopping_items,
    test_provider_dropped_quick_add_item_is_named_before_partial_review,
    test_symptom_message_suggests_groceries_without_adding_medicine,
)

__all__ = [
    "test_long_recipe_request_uses_one_product_choice_batch",
    "test_long_list_checks_every_item_in_paced_batches",
    "test_catalog_rate_limit_stops_remaining_search_waves",
    "test_real_model_presents_recipe_and_extras_choices_over_whatsapp_path",
    "test_pizza_ingredient_cap_keeps_extras_even_when_whole_basket_exceeds_cap",
    "test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage",
    "test_missing_requested_item_requires_review_before_checkout",
    "test_recipe_request_cannot_silently_omit_pizza_base",
    "test_model_cannot_silently_drop_explicit_shopping_items",
    "test_provider_dropped_quick_add_item_is_named_before_partial_review",
    "test_symptom_message_suggests_groceries_without_adding_medicine",
]
