"""Tests for Slice 6b and 6c: checkout receipt suppression, word list removal, and confirmation handling."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.agent import confirmation_check
from backend.agent.approval import PendingApproval, cart_fingerprint
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
    fake_gemini = MagicMock()
    fake_gemini.api_key = "fake-api-key"
    engine.gemini = fake_gemini
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
        if not c or not getattr(c, "items", None):
            session.pending_approval = None
            return False
        fp = cart_fingerprint(c, a) or "test-fp"
        session.pending_approval = PendingApproval(
            fingerprint=fp,
            expires_at=time.time() + 900,
            token="token-abc-123",
        )
        session.known_cart_fingerprint = fp
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
async def test_confirmation_required_turn_keeps_receipt_and_tokenized_confirm_button():
    """CONFIRMATION_REQUIRED turn, checkout_executed true, state AWAITING_CHECKOUT_CONFIRMATION:

    final actions contain confirm_order:<token>, receipt kept.
    """
    customer_id = "cust-123"
    engine, session, _ = _setup_engine(customer_id)
    receipt = "🛒 *Your Basket:*\n• Amul Taaza Milk 1L x1 — ₹54\nTotal: ₹54"

    message = NormalizedIncomingMessage(
        message_id="wamid.test-cr",
        sender_id="919999988888",
        channel="whatsapp",
        text="place order",
    )

    resp = await synthesize_turn_response(
        engine,
        message,
        customer_id,
        final_text=f"{receipt}\n\n👉 Reply *Confirm* to place order, or let me know if you'd like to change anything!",
        actions=[
            InteractiveAction(action_type="button", id="confirm_order:token-abc-123", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
        conv_state="AWAITING_CHECKOUT_CONFIRMATION",
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
        checkout_executed=True,
        user_confirmed=False,
        incoming_text="place order",
        addr_lbl="Home",
    )

    confirm_actions = [a for a in resp.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    assert confirm_actions[0].id == "confirm_order:token-abc-123"
    assert "Your Basket" in resp.text
    assert resp.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"


@pytest.mark.asyncio
async def test_failed_checkout_items_unresolved_no_stray_confirm_button_no_crash():
    """Failed checkout (ITEMS_UNRESOLVED): no stray confirm button, no crash."""
    customer_id = "cust-123"
    engine, session, _ = _setup_engine(customer_id)
    receipt = "🛒 *Your Basket:*\n• Amul Taaza Milk 1L x1 — ₹54\nTotal: ₹54"

    message = NormalizedIncomingMessage(
        message_id="wamid.test-fail",
        sender_id="919999988888",
        channel="whatsapp",
        text="place order",
    )

    session.unresolved_items = [{"name": "Organic Milk", "query": "milk"}]

    resp = await synthesize_turn_response(
        engine,
        message,
        customer_id,
        final_text="I could not place your order because some items are unresolved.",
        actions=[
            InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
        conv_state="NEEDS_DECISION",
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
        checkout_executed=True,
        user_confirmed=False,
        incoming_text="place order",
        addr_lbl="Home",
    )

    assert not any(a.id == "confirm_order" or a.id.startswith("confirm_order:") for a in resp.interactive_actions)
    assert resp.conversation_state == "NEEDS_DECISION"


@pytest.mark.asyncio
async def test_stale_bare_confirm_tap_after_order_empty_cart_no_new_approval():
    """Stale bare confirm_order tap in preflight right after an order, with an empty cart:

    no new approval is recorded.
    """
    customer_id = "cust-123"
    engine, session, _ = _setup_engine(customer_id)
    session.pending_approval = None
    session.known_cart_fingerprint = None

    empty_cart = CommerceCart(
        cart_id="cart-empty-1",
        address_id="addr-bandra-1",
        items=[],
        grand_total=0.0,
        currency="INR",
        billing_complete=True,
    )
    engine.commerce.get_cart = AsyncMock(return_value=empty_cart)

    message = NormalizedIncomingMessage(
        message_id="wamid.test-stale",
        sender_id="919999988888",
        channel="whatsapp",
        text="",
        interactive_id="confirm_order",
    )

    result = await execute_preflight(engine, message, customer_id)
    assert session.pending_approval is None
    assert result.user_confirmed is False
    assert result.early_response is not None
    assert result.early_response.conversation_state == "NEEDS_DECISION"
    assert not any(a.id.startswith("confirm_order") for a in result.early_response.interactive_actions)


@pytest.mark.asyncio
async def test_typed_yes_with_negation_does_not_confirm(monkeypatch):
    """3. Typed 'yes, but don't add milk' does not confirm (fake returns 'no').

    Same fake returns 'yes' for 'yes' (user_confirmed is True).
    Assert the fake was called in both.
    """
    customer_id = "cust-123"
    engine, session, cart = _setup_engine(customer_id)
    fp = cart_fingerprint(cart, "addr-bandra-1")
    session.pending_approval = PendingApproval(
        fingerprint=fp,
        expires_at=time.time() + 900,
        token="token-abc-123",
    )
    session.known_cart_fingerprint = fp
    session.task_state = {"state": "AWAITING_CHECKOUT_CONFIRMATION"}

    async def _fake_generate_structured(*args, **kwargs):
        prompt = kwargs.get("prompt", "")
        if "yes, but don't add" in prompt:
            return {"confirmation": "no"}
        if "yes" in prompt:
            return {"confirmation": "yes"}
        return {"confirmation": "unclear"}

    engine.gemini.generate_structured = AsyncMock(side_effect=_fake_generate_structured)

    is_confirmed_spy = AsyncMock(wraps=confirmation_check.is_confirmed)
    monkeypatch.setattr(confirmation_check, "is_confirmed", is_confirmed_spy)

    # 1. Negative confirmation: "yes, but don't add milk"
    message_neg = NormalizedIncomingMessage(
        message_id="wamid.test-3a",
        sender_id="919999988888",
        channel="whatsapp",
        text="yes, but don't add milk",
    )

    result_neg = await execute_preflight(engine, message_neg, customer_id)
    assert result_neg.user_confirmed is False
    assert is_confirmed_spy.call_count == 1
    assert "yes, but don't add milk" in is_confirmed_spy.call_args[0]
    assert engine.gemini.generate_structured.call_count == 1

    # 2. Positive confirmation: "yes"
    session.pending_approval = PendingApproval(
        fingerprint=fp,
        expires_at=time.time() + 900,
        token="token-abc-123",
    )
    session.known_cart_fingerprint = fp
    message_yes = NormalizedIncomingMessage(
        message_id="wamid.test-3b",
        sender_id="919999988888",
        channel="whatsapp",
        text="yes",
    )

    result_yes = await execute_preflight(engine, message_yes, customer_id)
    assert result_yes.user_confirmed is True
    assert is_confirmed_spy.call_count == 2
    assert "yes" in is_confirmed_spy.call_args[0]
    assert engine.gemini.generate_structured.call_count == 2


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


@pytest.mark.asyncio
async def test_accept_partial_basket_still_works():
    """Interactive accept_partial_basket clears blocked items and produces tokenized confirm button."""
    customer_id = "cust-123"
    engine, session, cart = _setup_engine(customer_id)
    session.budget_blocked_items = ["SPIN-MILK-1L"]

    message = NormalizedIncomingMessage(
        message_id="wamid.test-accept-partial",
        sender_id="919999988888",
        channel="whatsapp",
        text="",
        interactive_id="accept_partial_basket",
    )

    result = await execute_preflight(engine, message, customer_id)
    assert result.early_response is not None
    assert result.early_response.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    assert session.budget_blocked_items == []
    confirm_actions = [a for a in result.early_response.interactive_actions if a.id.startswith("confirm_order:")]
    assert len(confirm_actions) == 1
    assert confirm_actions[0].id == "confirm_order:token-abc-123"
