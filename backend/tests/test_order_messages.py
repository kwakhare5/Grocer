"""Tests for deterministic code-written order messages and checkout outcomes."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.agent.engine import order_message, process_checkout_outcome
from backend.agent.session import CustomerSession
from backend.agent.approval import PendingApproval
from backend.channels.models import InteractiveAction
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart


def _make_dummy_engine(token: str = ""):
    engine = MagicMock()
    session = CustomerSession(customer_id="cust-123")
    if token:
        session.pending_approval = PendingApproval(
            fingerprint="test-fp",
            expires_at=9999999999.0,
            token=token,
        )
    session.address_id = "addr-1"
    session.address_label = "Home"
    engine.get_session.return_value = session
    return engine, session


def test_order_message_order_placed():
    result = {
        "status": "ORDER_PLACED",
        "order_id": "ORD-12345",
        "formatted_grand_total": "₹250",
        "tracking_url": "https://swiggy.com/track/ORD-12345",
    }
    msg = order_message(result)
    assert "ORD-12345" in msg
    assert "₹250" in msg
    assert "https://swiggy.com/track/ORD-12345" in msg


def test_order_message_payment_pending_bridge_and_upi():
    result_bridge = {
        "status": "PAYMENT_PENDING",
        "order_id": "ORD-999",
        "formatted_grand_total": "₹150.50",
        "bridge_url": "https://swiggy.com/pay/bridge-999",
    }
    msg_bridge = order_message(result_bridge)
    assert "ORD-999" in msg_bridge
    assert "₹150.50" in msg_bridge
    assert "https://swiggy.com/pay/bridge-999" in msg_bridge

    result_upi = {
        "status": "PAYMENT_PENDING",
        "order_id": "ORD-888",
        "grand_total": 300,
        "upi_intent_url": "upi://pay?order=ORD-888",
    }
    msg_upi = order_message(result_upi)
    assert "ORD-888" in msg_upi
    assert "₹300" in msg_upi
    assert "upi://pay?order=ORD-888" in msg_upi


def test_process_checkout_outcome_order_placed_drops_model_text():
    engine, _ = _make_dummy_engine()
    checkout_result = {
        "success": True,
        "status": "ORDER_PLACED",
        "order_id": "ORD-555",
        "formatted_grand_total": "₹450",
        "grand_total": 450,
        "tracking_url": "https://swiggy.com/track/ORD-555",
    }
    model_hallucination = "I have successfully confirmed and placed your groceries order!"

    conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url = process_checkout_outcome(
        engine,
        "cust-123",
        checkout_executed=True,
        checkout_result=checkout_result,
        last_cart_receipt="Cart receipt",
        current_cart=None,
        addr_lbl="Home",
        final_text=model_hallucination,
        actions=[],
        pending_request_needs_retry=False,
    )

    assert conv_state == "ORDER_PLACED"
    assert out_order_id == "ORD-555"
    assert out_order_total == 450
    assert "ORD-555" in final_text
    assert "₹450" in final_text
    assert "https://swiggy.com/track/ORD-555" in final_text
    # Model text claiming success must never leak into final message
    assert model_hallucination not in final_text
    assert "I have successfully" not in final_text


def test_process_checkout_outcome_payment_pending_keeps_model_as_extra_line():
    engine, _ = _make_dummy_engine()
    checkout_result = {
        "success": True,
        "status": "PAYMENT_PENDING",
        "order_id": "ORD-777",
        "formatted_grand_total": "₹120",
        "grand_total": 120,
        "bridge_url": "https://swiggy.com/pay/bridge-777",
    }
    model_note = "Your delivery partner will be assigned once paid."

    conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url = process_checkout_outcome(
        engine,
        "cust-123",
        checkout_executed=True,
        checkout_result=checkout_result,
        last_cart_receipt="Cart receipt",
        current_cart=None,
        addr_lbl="Home",
        final_text=model_note,
        actions=[],
        pending_request_needs_retry=False,
    )

    assert conv_state == "AWAITING_PAYMENT"
    assert out_order_id == "ORD-777"
    assert out_bridge_url == "https://swiggy.com/pay/bridge-777"
    assert "ORD-777" in final_text
    assert "₹120" in final_text
    assert "https://swiggy.com/pay/bridge-777" in final_text
    assert model_note in final_text


def test_process_checkout_outcome_partial_order():
    engine, _ = _make_dummy_engine()
    checkout_result = {
        "success": True,
        "status": "PARTIAL_ORDER",
        "success_count": 2,
        "failure_count": 1,
    }

    conv_state, final_text, actions, _, _, _ = process_checkout_outcome(
        engine,
        "cust-123",
        checkout_executed=True,
        checkout_result=checkout_result,
        last_cart_receipt=None,
        current_cart=None,
        addr_lbl="Home",
        final_text="Model partial text",
        actions=[],
        pending_request_needs_retry=False,
    )

    assert conv_state == "NEEDS_DECISION"
    assert "partial order: 2 placed and 1 failed" in final_text


def test_process_checkout_outcome_failure_live_and_non_live(monkeypatch):
    checkout_result = {
        "success": False,
        "error": "PAYMENT_FAILED",
        "message": "Bank declined transaction",
    }
    model_extra = "Please try a different card or UPI ID."

    texts = []
    for mode in ("live", "simulation"):
        monkeypatch.setattr(settings, "CHECKOUT_MODE", mode)
        engine, _ = _make_dummy_engine()
        conv_state, final_text, actions, out_id, out_total, out_bridge = process_checkout_outcome(
            engine,
            "cust-123",
            checkout_executed=True,
            checkout_result=checkout_result,
            last_cart_receipt=None,
            current_cart=None,
            addr_lbl="Home",
            final_text=model_extra,
            actions=[],
            pending_request_needs_retry=False,
        )
        assert conv_state == "FAILED"
        assert "PAYMENT_FAILED" in final_text or "Bank declined transaction" in final_text
        assert model_extra in final_text
        texts.append(final_text)

    # Live and non-live behave the same
    assert texts[0] == texts[1]


def test_process_checkout_outcome_confirmation_required_tokenized_button():
    token_val = "tok-secret-abc123"
    engine, session = _make_dummy_engine(token=token_val)
    checkout_result = {
        "success": False,
        "error": "CONFIRMATION_REQUIRED",
    }

    conv_state, final_text, actions, _, _, _ = process_checkout_outcome(
        engine,
        "cust-123",
        checkout_executed=True,
        checkout_result=checkout_result,
        last_cart_receipt="Your cart has milk",
        current_cart=None,
        addr_lbl="Home",
        final_text="",
        actions=[],
        pending_request_needs_retry=False,
    )

    assert conv_state == "AWAITING_CHECKOUT_CONFIRMATION"
    # Bare confirm_order button must NOT be present
    assert not any(a.id == "confirm_order" for a in actions)
    # Tokenized confirm button must be present
    assert any(a.id == f"confirm_order:{token_val}" for a in actions)
