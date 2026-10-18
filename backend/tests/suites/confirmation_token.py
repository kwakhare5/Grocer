"""E2E integration test suite for cart-bound confirmation tokens and checked typed yes."""
from __future__ import annotations

import json
import time
import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent import confirmation_check
from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.engine import GroceryAgentEngine
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceOrderResult,
    PaymentOption,
)
from backend.main import create_app
from backend.tests.suites.helpers import _interactive_webhook, _webhook


class TrackingCommerce(MockCommerceAdapter):
    def __init__(self):
        super().__init__()
        self.checkout_calls = 0

    async def get_payment_options(self, cart_id=None, address_id=None):
        return [PaymentOption(id="upi-app-test", kind="intent", method="UPI", label="UPI app")]

    async def checkout(self, *args, **kwargs):
        self.checkout_calls += 1
        return CommerceOrderResult(
            order_id="order-whatsapp-test",
            status="ORDER_PLACED",
            grand_total=116,
        )


async def _setup_engine_and_cart(postgres_pool, monkeypatch):
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    commerce = TrackingCommerce()
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

    session = engine.get_session(customer_id)
    session.selected_payment_id = "upi-app-test"
    session.selected_payment_kind = "intent"
    session.selected_payment_method = "UPI"

    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store

    return commerce, engine, store, customer_id, cart, app


def _stub_checkout_model(engine, cart):
    model_calls = 0

    async def model_reply(_history, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "checkout", "args": {"cart_id": cart.cart_id, "address_id": "addr-bandra-1"},
            }}]}}]}
        return {"candidates": [{"content": {"parts": [{"text": "Your order has been placed!"}]}}]}

    engine._call_llm = model_reply


@pytest.mark.asyncio
async def test_valid_confirmation_token_confirms(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    token = engine.get_session(customer_id).pending_approval.token
    assert token

    _stub_checkout_model(engine, cart)

    body, headers = _interactive_webhook("wamid.valid-token", f"confirm_order:{token}", "Confirm Order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 1


@pytest.mark.asyncio
async def test_stale_confirmation_token_refused_with_fresh_summary_and_button(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    old_token = engine.get_session(customer_id).pending_approval.token

    _stub_checkout_model(engine, cart)

    body, headers = _interactive_webhook("wamid.stale-token", "confirm_order:wrong-stale-token", "Confirm Order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 0

    _, reply = await store.response_for_message("wamid.stale-token")
    assert reply is not None
    # Check that fresh summary and fresh confirm button are present
    confirm_actions = [a for a in reply.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    new_token = confirm_actions[0].id.removeprefix("confirm_order:")
    assert new_token != old_token
    assert new_token != "wrong-stale-token"
    assert "milk" in reply.text.casefold() or "basket" in reply.text.casefold()


@pytest.mark.asyncio
async def test_expired_approval_refused_typed_and_by_button(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    fp = cart_fingerprint(cart, "addr-bandra-1")
    session = engine.get_session(customer_id)
    session.pending_approval = PendingApproval(fingerprint=fp, expires_at=time.time() - 10, token="tok-expired")
    session.known_cart_fingerprint = fp

    _stub_checkout_model(engine, cart)

    # 1. Expired button tap: refused with fresh summary and fresh button, checkout not called
    body, headers = _interactive_webhook("wamid.expired-button", "confirm_order:tok-expired", "Confirm Order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 0
    _, reply = await store.response_for_message("wamid.expired-button")
    assert any(a.id.startswith("confirm_order:") and a.id != "confirm_order:tok-expired" for a in reply.interactive_actions)

    # 2. Expired typed yes: refused, checkout not called
    session.pending_approval = PendingApproval(fingerprint=fp, expires_at=time.time() - 10, token="tok-expired-2")
    async def _always_yes(*_args, **_kwargs):
        return True
    monkeypatch.setattr(confirmation_check, "is_confirmed", _always_yes)

    body, headers = _webhook("wamid.expired-typed", "yes")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp2 = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp2.status_code == 200
    assert commerce.checkout_calls == 0


@pytest.mark.asyncio
async def test_typed_yes_confirms_when_model_check_returns_true_refused_when_false(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")

    _stub_checkout_model(engine, cart)

    # Part A: Refused when model check returns False
    async def _mock_false(*_args, **_kwargs):
        return False
    monkeypatch.setattr(confirmation_check, "is_confirmed", _mock_false)

    body, headers = _webhook("wamid.typed-refused", "yes")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp_false = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp_false.status_code == 200
    assert commerce.checkout_calls == 0

    # Part B: Confirms when model check returns True
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    session = engine.get_session(customer_id)
    session.selected_payment_id = "upi-app-test"
    session.selected_payment_kind = "intent"
    session.selected_payment_method = "UPI"
    _stub_checkout_model(engine, cart)

    async def _mock_true(*_args, **_kwargs):
        return True
    monkeypatch.setattr(confirmation_check, "is_confirmed", _mock_true)

    body, headers = _webhook("wamid.typed-confirmed", "yes")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp_true = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp_true.status_code == 200
    assert commerce.checkout_calls == 1


@pytest.mark.asyncio
async def test_typed_confirm_order_with_no_approval_still_refused(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    engine.get_session(customer_id).pending_approval = None

    _stub_checkout_model(engine, cart)

    async def _mock_true(*_args, **_kwargs):
        return True
    monkeypatch.setattr(confirmation_check, "is_confirmed", _mock_true)

    body, headers = _webhook("wamid.no-approval-typed", "confirm order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 0


@pytest.mark.asyncio
async def test_price_change_forces_fresh_review_and_old_token_refused(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    old_token = engine.get_session(customer_id).pending_approval.token
    old_price = cart.items[0].unit_price

    # Inject a Rs 5 price change on the cart item (delta <= 10, previously bypassed by tolerance)
    commerce.inject_price_change("SPIN-MILK-1L", old_price + 5.0)

    _stub_checkout_model(engine, cart)

    body, headers = _interactive_webhook("wamid.price-drift", f"confirm_order:{old_token}", "Confirm Order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 0

    _, reply = await store.response_for_message("wamid.price-drift")
    assert reply is not None
    confirm_actions = [a for a in reply.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    new_token = confirm_actions[0].id.removeprefix("confirm_order:")
    assert new_token != old_token
    assert "milk" in reply.text.casefold() or "basket" in reply.text.casefold()


@pytest.mark.asyncio
async def test_missing_known_cart_fingerprint_with_pending_approval_refuses_confirm(postgres_pool, monkeypatch):
    commerce, engine, store, customer_id, cart, app = await _setup_engine_and_cart(postgres_pool, monkeypatch)
    assert engine._record_pending_approval(customer_id, cart, "addr-bandra-1")
    token = engine.get_session(customer_id).pending_approval.token

    # Clear known_cart_fingerprint to simulate legacy or missing state while approval is pending
    engine.get_session(customer_id).known_cart_fingerprint = None

    _stub_checkout_model(engine, cart)

    body, headers = _interactive_webhook("wamid.missing-fp", f"confirm_order:{token}", "Confirm Order")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        resp = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
    assert resp.status_code == 200
    assert commerce.checkout_calls == 0

    _, reply = await store.response_for_message("wamid.missing-fp")
    assert reply is not None
    confirm_actions = [a for a in reply.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    new_token = confirm_actions[0].id.removeprefix("confirm_order:")
    assert new_token != token


__all__ = [
    "test_valid_confirmation_token_confirms",
    "test_stale_confirmation_token_refused_with_fresh_summary_and_button",
    "test_expired_approval_refused_typed_and_by_button",
    "test_typed_yes_confirms_when_model_check_returns_true_refused_when_false",
    "test_typed_confirm_order_with_no_approval_still_refused",
    "test_price_change_forces_fresh_review_and_old_token_refused",
    "test_missing_known_cart_fingerprint_with_pending_approval_refuses_confirm",
]
