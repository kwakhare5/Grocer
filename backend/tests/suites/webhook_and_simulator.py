"""Local simulator, unknown meta delivery, and restart reconciliation tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.engine import GroceryAgentEngine
from backend.api.whatsapp import drain_message_queue
from backend.channels.message_store import PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceOrderResult,
    PaymentOption,
    PaymentStatusResult,
)
from backend.main import create_app
from backend.tests.suites.helpers import _webhook

@pytest.mark.asyncio
async def test_local_simulator_clear_failure_never_claims_empty_basket(postgres_pool, monkeypatch):
    class FailingClearAdapter(MockCommerceAdapter):
        async def clear_cart(self, cart_id=None):
            raise RuntimeError("provider clear unavailable")

    monkeypatch.setattr(settings, "SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "SIMULATOR_ACCESS_TOKEN", "local-test-secret")
    monkeypatch.setattr(settings, "SIMULATOR_SENDER_ID", "919999988888")
    monkeypatch.setattr(settings, "COMMERCE_ADAPTER_TYPE", "mock")
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "review")
    app = create_app()
    commerce = FailingClearAdapter()
    app.state.agent_engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/simulator/chat", headers={"Authorization": "Bearer local-test-secret"},
            json={"text": "delete all"},
        )
    assert response.status_code == 200
    assert "couldn't verify" in response.json()["text"].casefold()
    assert "cleared" not in response.json()["text"].casefold()


@pytest.mark.asyncio
async def test_unknown_meta_delivery_does_not_freeze_later_customer_message(postgres_pool, monkeypatch):
    store = PostgresMessageStore(postgres_pool)
    engine = GroceryAgentEngine(MockCommerceAdapter(), gemini_api_key="local-test")
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    sender = "919999988888"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id(sender)
    first = NormalizedIncomingMessage(
        message_id="wamid.undelivered", channel=ChannelType.WHATSAPP,
        sender_id=sender, customer_id=customer_id, text="show cart",
    )
    await store.enqueue_many([first])
    claimed = await store.claim_next()
    assert claimed is not None
    await store.stage_response(claimed[0], NormalizedOutgoingResponse(
        recipient_id=sender, channel=ChannelType.WHATSAPP,
        text="Your basket is empty.", conversation_state="READY",
    ))
    sending = await store.claim_outbound()
    assert sending is not None
    await postgres_pool.execute(
        "UPDATE grocer_internal.outbound_messages SET sending_started_at=now()-interval '10 minutes' WHERE id=$1",
        sending[0],
    )
    body, headers = _webhook("wamid.after-failure", "hello")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        result = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert result.status_code == 200
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.outbound_messages WHERE id=$1", sending[0]
    ) == "UNKNOWN"
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.inbound_messages WHERE message_id='wamid.after-failure'"
    ) == "PROCESSED"
    assert len(default_whatsapp_adapter.outbound_messages) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("paid,already_confirmed,missing_metadata", [
    (True, True, False), (True, False, False), (False, False, False), (False, False, True),
])
async def test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart(
    postgres_pool, monkeypatch, paid, already_confirmed, missing_metadata,
):
    class PendingCommerce(MockCommerceAdapter):
        def __init__(self):
            super().__init__()
            self.checkout_calls = 0
            self.confirm_calls = 0

        async def get_payment_options(self, cart_id=None, address_id=None):
            return [PaymentOption(id="upi-app-test", kind="intent", method="UPI", label="UPI app")]

        async def checkout(self, *args, **kwargs):
            self.checkout_calls += 1
            assert kwargs.get("payment_option_id") == "upi-app-test"
            return CommerceOrderResult(
                order_id="order-whatsapp", status="PAYMENT_PENDING",
                paas_id=None if missing_metadata else "paas-whatsapp",
                bridge_url="https://pay.swiggy.com/bridge/test", grand_total=116,
                polling_interval_ms=None if missing_metadata else 10000,
                max_time_to_poll_ms=None if missing_metadata else 60000,
            )

        async def check_payment_status(self, paas_id, order_id=None):
            assert (paas_id, order_id) == ("paas-whatsapp", "order-whatsapp")
            return PaymentStatusResult(
                paas_id=paas_id, order_id=order_id, status="paid" if paid else "failed",
                terminal=True, is_terminal_success=paid, is_terminal_failure=not paid,
                confirmed=already_confirmed,
                order_status="ORDER_PLACED" if already_confirmed else None,
            )

        async def confirm_order(self, order_id, paas_id):
            self.confirm_calls += 1
            return CommerceOrderResult(order_id=order_id, paas_id=paas_id, status="ORDER_PLACED")

    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()
    commerce = PendingCommerce()
    store = PostgresMessageStore(postgres_pool)
    attempts = PostgresCheckoutAttemptStore(postgres_pool)
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", attempt_store=attempts)
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id("919999988888")
    with commerce.customer_scope(customer_id):
        cart = await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id="addr-bandra-1",
        )
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    session = engine.get_session(customer_id)
    session.selected_payment_id = "upi-app-test"
    session.selected_payment_kind = "intent"
    session.selected_payment_method = "UPI"

    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "checkout", "args": {"cart_id": cart.cart_id, "address_id": "addr-bandra-1"},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [{"text": "Please complete payment."}]}}]}

    engine._call_llm = model_reply  # external model boundary
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    body, headers = _webhook("wamid.payment-confirm", "confirm order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        first = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert first.status_code == 200
    _, pending = await store.response_for_message("wamid.payment-confirm")
    assert commerce.checkout_calls == 1
    attempt_id = await postgres_pool.fetchval(
        "SELECT id FROM grocer_internal.checkout_attempts WHERE customer_id=$1", customer_id,
    )
    assert attempt_id
    if missing_metadata:
        assert pending.conversation_state == "RECOVERING"
        assert "couldn't verify" in pending.text.casefold()
        assert await postgres_pool.fetchval(
            "SELECT status FROM grocer_internal.checkout_attempts WHERE id=$1", attempt_id,
        ) == "UNKNOWN"
        assert await attempts.reconcile_due_payment(commerce) == 0
        assert len(default_whatsapp_adapter.outbound_messages) == 1
        return
    assert pending.conversation_state == "AWAITING_PAYMENT"
    assert "https://pay.swiggy.com/bridge/test" in pending.text
    restarted = PostgresCheckoutAttemptStore(postgres_pool)
    await postgres_pool.execute(
        """UPDATE grocer_internal.outbound_messages SET status='QUEUED', sent_at=NULL
           WHERE inbound_id=(SELECT id FROM grocer_internal.inbound_messages WHERE message_id='wamid.payment-confirm')"""
    )
    assert await restarted.reconcile_due_payment(commerce) == 0
    await postgres_pool.execute(
        """UPDATE grocer_internal.outbound_messages SET status='SENT', sent_at=now()
           WHERE inbound_id=(SELECT id FROM grocer_internal.inbound_messages WHERE message_id='wamid.payment-confirm')"""
    )
    assert await restarted.reconcile_due_payment(commerce) == 1
    await drain_message_queue(store, engine)
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.checkout_attempts WHERE id=$1", attempt_id,
    ) == ("PLACED" if paid else "PAYMENT_FAILED")
    assert await postgres_pool.fetchval(
        "SELECT status FROM grocer_internal.outbound_messages WHERE payment_attempt_id=$1", attempt_id,
    ) == "SENT"
    assert commerce.checkout_calls == 1
    assert commerce.confirm_calls == (0 if already_confirmed or not paid else 1)
    assert len(default_whatsapp_adapter.outbound_messages) == 2
