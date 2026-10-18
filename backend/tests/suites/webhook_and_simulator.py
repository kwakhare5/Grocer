"""Local simulator, unknown meta delivery, and restart reconciliation tests."""
from __future__ import annotations

import time
import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent import confirmation_check
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
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    app.state.agent_engine = engine
    app.state.message_store = PostgresMessageStore(postgres_pool)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)

    sender = "919999988888"
    customer_id = default_whatsapp_adapter.map_sender_to_customer_id(sender)
    address_id = "addr-bandra-1"
    session = engine.get_session(customer_id)
    session.address_id = address_id
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id=address_id,
        )
        cart = await commerce.get_cart()

    from backend.agent.session_manager import record_pending_cart_clear
    session = engine.get_session(customer_id)
    assert record_pending_cart_clear(session, cart, address_id)
    token = session.pending_cart_clear.token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/simulator/chat",
            headers={"Authorization": "Bearer local-test-secret"},
            json={"text": "Clear", "interactive_id": f"clear_cart_confirm:{token}"},
        )
    assert response.status_code == 200
    assert "couldn't verify" in response.json()["text"].casefold()
    assert "cleared" not in response.json()["text"].casefold()


@pytest.mark.asyncio
async def test_preflight_resets_stale_clear_cart_ask_on_unrelated_turn():
    from backend.agent.preflight_handler import execute_preflight
    from backend.agent.session_manager import record_pending_cart_clear

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = "919999988888"
    address_id = "addr-bandra-1"
    session = engine.get_session(customer_id)
    session.address_id = address_id
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id=address_id,
        )
        cart = await commerce.get_cart()

    session = engine.get_session(customer_id)
    assert record_pending_cart_clear(session, cart, address_id)
    assert session.pending_cart_clear is not None

    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-unrelated",
        text="add bread",
        timestamp=int(time.time()),
    )
    await execute_preflight(engine, msg, customer_id)
    assert session.pending_cart_clear is None


@pytest.mark.asyncio
async def test_missing_known_fingerprint_clears_pending_approval_and_sets_external_cart_pending():
    from backend.agent.approval import PendingApproval, cart_fingerprint
    from backend.agent.preflight_handler import execute_preflight

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    customer_id = "919999988888"
    address_id = "addr-bandra-1"
    session = engine.get_session(customer_id)
    session.address_id = address_id
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id=address_id,
        )
        cart = await commerce.get_cart()

    session = engine.get_session(customer_id)
    fp = cart_fingerprint(cart, address_id)
    session.pending_approval = PendingApproval(
        token="test-token-123",
        fingerprint=fp,
        expires_at=time.time() + 300,
    )
    session.known_cart_fingerprint = None
    session.external_cart_pending = False

    # 1. Confirm tap entry path: pending_approval is cleared and external_cart_pending is set
    msg_tap = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-confirm-tap",
        text="Confirm Order",
        interactive_id="confirm_order:test-token-123",
        timestamp=int(time.time()),
    )
    result_tap = await execute_preflight(engine, msg_tap, customer_id)
    assert session.pending_approval is None
    assert session.external_cart_pending is True
    assert result_tap.early_response is not None
    assert "expired or the basket changed" in result_tap.early_response.text.casefold()

    # 2. Typed path: when known_cart_fingerprint is missing, external_cart_pending forces check_cart_drift review
    session.pending_approval = PendingApproval(
        token="test-token-456",
        fingerprint=fp,
        expires_at=time.time() + 300,
    )
    session.known_cart_fingerprint = None
    session.external_cart_pending = False

    msg_typed = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-typed",
        text="place order",
        timestamp=int(time.time()),
    )
    result_typed = await execute_preflight(engine, msg_typed, customer_id)
    assert session.pending_approval is None
    assert session.external_cart_pending is True
    assert result_typed.early_response is not None
    assert "swiggy cart changed outside this chat" in result_typed.early_response.text.casefold()


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
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
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

    async def _mock_is_confirmed(*_args, **_kwargs):
        return True

    monkeypatch.setattr(confirmation_check, "is_confirmed", _mock_is_confirmed)
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
