"""Replenishment consent, webhook signature validation, data deletion, and simulator tests."""
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


from backend.tests.suites.webhook_and_simulator import (
    test_local_simulator_clear_failure_never_claims_empty_basket,
    test_unknown_meta_delivery_does_not_freeze_later_customer_message,
    test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart,
)

__all__ = [
    "test_replayed_signed_webhook_has_one_durable_turn_and_one_reply",
    "test_forged_whatsapp_signature_never_enters_inbox",
    "test_unreviewed_whatsapp_confirmation_cannot_call_checkout",
    "test_whatsapp_replenishment_requires_consent_survives_restart_and_can_be_deleted",
    "test_customer_corrects_low_stock_estimate_without_cart_mutation",
    "test_delete_my_data_purges_consented_habits_through_signed_whatsapp",
    "test_expired_order_history_auth_gets_reconnect_link_not_false_stock_result",
    "test_opted_in_history_refresh_runs_without_chat_and_pause_stops_it",
    "test_incomplete_swiggy_order_details_do_not_become_no_habit_claim",
    "test_local_simulator_uses_signed_webhook_and_rejects_customer_impersonation",
    "test_local_simulator_clear_failure_never_claims_empty_basket",
    "test_unknown_meta_delivery_does_not_freeze_later_customer_message",
    "test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart",
]
