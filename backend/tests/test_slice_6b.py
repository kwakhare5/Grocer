"""Tests for Slice 6b: checkout receipt suppression, word list removal, and confirmation handling."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.agent import confirmation_check
from backend.agent.approval import PendingApproval
from backend.agent.preflight_handler import execute_preflight
from backend.agent.response_synthesizer import synthesize_turn_response
from backend.agent.session import CustomerSession
from backend.channels.models import InteractiveAction, NormalizedIncomingMessage
from backend.integrations.commerce.models import CartItem, CommerceCart


def _setup_engine(customer_id: str = "cust-123"):
    engine = MagicMock()
    session = CustomerSession(customer_id=customer_id)
    engine.get_session.return_value = session
    engine.get_history.return_value = []
    engine._customer_address = {customer_id: "addr-bandra-1"}
    engine._customer_address_label = {customer_id: "Home"}
    engine._last_interaction_time = {}
    engine._read_budget_cap = AsyncMock(return_value=None)
    engine.gemini = MagicMock()
    commerce = MagicMock()
    cart = CommerceCart(
        cart_id="cart-test-1",
        address_id="addr-bandra-1",
        items=[
            CartItem(
                spin_id="SPIN-MILK-1L",
                name="Amul Taaza Milk 1L",
                pack_size="1 L",
                quantity=1,
                unit_price=54.0,
                total_price=54.0,
            )
        ],
        grand_total=54.0,
        currency="INR",
        billing_complete=True,
    )
    commerce.get_cart = AsyncMock(return_value=cart)
    engine.commerce = commerce

    def _record_pending_approval(cid, c, a):
        session.pending_approval = PendingApproval(
            fingerprint="test-fp",
            expires_at=time.time() + 900,
            token="token-abc-123",
        )
        return True

    engine._record_pending_approval = MagicMock(side_effect=_record_pending_approval)
    return engine, session, cart


@pytest.mark.asyncio
async def test_checkout_succeeds_get_cart_called_no_receipt_or_confirm_button():
    """1. Checkout succeeds, the model also calls get_cart in the same turn:

    final text has the order id, no receipt appended, no confirm_order action,
    state is not AWAITING_CHECKOUT_CONFIRMATION.
    """
    customer_id = "cust-123"
    engine, session, _ = _setup_engine(customer_id)
    receipt = "🛒 *Your Basket:*\n• Amul Taaza Milk 1L x1 — ₹54\nTotal: ₹54"

    message = NormalizedIncomingMessage(
        message_id="wamid.test-1",
        sender_id="919999988888",
        channel="whatsapp",
        text="place order",
    )

    resp = await synthesize_turn_response(
        engine,
        message,
        customer_id,
        final_text="Your order ORD-999 for ₹54 has been placed! Track your order here: https://swiggy.com/track/ORD-999",
        actions=[],
        conv_state="ORDER_PLACED",
        last_cart_receipt=receipt,
        last_cart_total=54.0,
        out_order_id="ORD-999",
        out_order_total=54.0,
        out_bridge_url=None,
        address_changed=False,
        suggestion_only=False,
        suggested_items=[],
        restricted_items=[],
        search_failed_items=[],
        budget_blocked_items=[],
        unavailable_items=[],
        reduced_items=[],
        guarded_change_message=None,
        pending_request_needs_retry=False,
        step_limit_reached=False,
        checkout_executed=True,
        user_confirmed=True,
        incoming_text="place order",
        addr_lbl="Home",
    )

    assert "ORD-999" in resp.text
    assert "Your Basket" not in resp.text
    assert not any(a.id == "confirm_order" or a.id.startswith("confirm_order:") for a in resp.interactive_actions)
    assert resp.conversation_state != "AWAITING_CHECKOUT_CONFIRMATION"
    assert resp.conversation_state == "ORDER_PLACED"


@pytest.mark.asyncio
async def test_normal_cart_turn_gives_tokenized_confirm_button():
    """2. A normal cart turn with a receipt still gives a tokenized confirm_order button."""
    customer_id = "cust-123"
    engine, session, _ = _setup_engine(customer_id)
    receipt = "🛒 *Your Basket:*\n• Amul Taaza Milk 1L x1 — ₹54\nTotal: ₹54"

    message = NormalizedIncomingMessage(
        message_id="wamid.test-2",
        sender_id="919999988888",
        channel="whatsapp",
        text="Add milk",
    )

    resp = await synthesize_turn_response(
        engine,
        message,
        customer_id,
        final_text="",
        actions=[],
        conv_state="READY",
        last_cart_receipt=receipt,
        last_cart_total=54.0,
        out_order_id=None,
        out_order_total=None,
        out_bridge_url=None,
        address_changed=False,
        suggestion_only=False,
        suggested_items=[],
        restricted_items=[],
        search_failed_items=[],
        budget_blocked_items=[],
        unavailable_items=[],
        reduced_items=[],
        guarded_change_message=None,
        pending_request_needs_retry=False,
        step_limit_reached=False,
        checkout_executed=False,
        user_confirmed=False,
        incoming_text="Add milk",
        addr_lbl="Home",
    )

    assert resp.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    confirm_actions = [a for a in resp.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    assert confirm_actions[0].id == "confirm_order:token-abc-123"
    assert not any(a.id == "confirm_order" for a in resp.interactive_actions)


@pytest.mark.asyncio
async def test_typed_yes_with_negation_does_not_confirm(monkeypatch):
    """3. Typed 'yes, but don't add the milk' does not confirm (is_confirmed returns not-yes)."""
    customer_id = "cust-123"
    engine, session, cart = _setup_engine(customer_id)
    session.pending_approval = PendingApproval(
        fingerprint="test-fp",
        expires_at=time.time() + 900,
        token="token-abc-123",
    )
    session.known_cart_fingerprint = "test-fp"
    session.task_state = {"state": "AWAITING_CHECKOUT_CONFIRMATION"}

    # Mock is_confirmed to return False for not-yes
    async def _mock_not_yes(*_args, **_kwargs):
        return False

    monkeypatch.setattr(confirmation_check, "is_confirmed", _mock_not_yes)

    message = NormalizedIncomingMessage(
        message_id="wamid.test-3",
        sender_id="919999988888",
        channel="whatsapp",
        text="yes, but don't add the milk",
    )

    result = await execute_preflight(engine, message, customer_id)
    assert result.user_confirmed is False


@pytest.mark.asyncio
async def test_typed_keep_these_items_does_not_map_to_accept_partial():
    """4. Typed 'keep these items' no longer maps to accept partial in preflight."""
    customer_id = "cust-123"
    engine, session, cart = _setup_engine(customer_id)
    session.budget_blocked_items = ["SPIN-MILK-1L"]

    message = NormalizedIncomingMessage(
        message_id="wamid.test-4",
        sender_id="919999988888",
        channel="whatsapp",
        text="keep these items",
    )

    result = await execute_preflight(engine, message, customer_id)
    # Must not intercept as early_response for accept_partial
    assert result.early_response is None
    # Blocked items must not be cleared by typed text
    assert session.budget_blocked_items == ["SPIN-MILK-1L"]
