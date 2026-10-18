"""Replenishment consent, webhook signature validation, data deletion, and simulator tests."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.engine import GroceryAgentEngine
from backend.agent.task_state import PostgresTaskStateStore
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.main import create_app
from backend.tests.suites.helpers import (
    _webhook,
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
async def test_delete_my_data_purges_task_state_through_signed_whatsapp(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    key = Fernet.generate_key().decode()
    state_store = PostgresTaskStateStore(postgres_pool, key)
    app = create_app()
    app.state.message_store = store
    app.state.agent_engine = GroceryAgentEngine(
        MockCommerceAdapter(), gemini_api_key="local-test",
        state_store=state_store,
    )
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    await state_store.save(customer_id, {"session": "active"})
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.task_state WHERE customer_id=$1", customer_id,
    ) == 1
    await postgres_pool.execute(
        "INSERT INTO grocer_internal.oauth_tokens (customer_id, ciphertext, expires_at) VALUES ($1, $2, now())",
        customer_id, b"encrypted-token",
    )
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.oauth_tokens WHERE customer_id=$1", customer_id,
    ) == 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        body, headers = _webhook("wamid.delete-all", "delete my data")
        response = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        assert response.status_code == 200
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.task_state WHERE customer_id=$1", customer_id,
    ) == 0
    assert await postgres_pool.fetchval(
        "SELECT count(*) FROM grocer_internal.oauth_tokens WHERE customer_id=$1", customer_id,
    ) == 0
    assert await postgres_pool.fetchval(
        "SELECT to_regclass('grocer_internal.replenishment')"
    ) is None
    assert "deleted" in str(default_whatsapp_adapter.outbound_messages[-1]).casefold()


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
    "test_delete_my_data_purges_task_state_through_signed_whatsapp",
    "test_local_simulator_uses_signed_webhook_and_rejects_customer_impersonation",
    "test_local_simulator_clear_failure_never_claims_empty_basket",
    "test_unknown_meta_delivery_does_not_freeze_later_customer_message",
    "test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart",
]
