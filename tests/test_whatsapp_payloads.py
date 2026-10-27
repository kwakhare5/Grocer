"""Grocer v1.0 — Outbound WhatsApp payload shape (no network)."""

from __future__ import annotations

import pytest

from backend.channels.whatsapp_client import (
    build_buttons_payload,
    build_cta_payload,
    build_text_payload,
)


def test_text_payload_shape():
    payload = build_text_payload("+919876543210", "Hello from Grocer!")
    assert payload["to"] == "+919876543210"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hello from Grocer!"


def test_buttons_payload_shape_and_limits():
    buttons = [("pay:appr_123", "Pay ₹149"), ("cart:clear", "Clear Basket")]
    payload = build_buttons_payload("919876543210", "Your total is ₹149", buttons)
    interactive = payload["interactive"]
    assert interactive["type"] == "button"
    assert len(interactive["action"]["buttons"]) == 2
    assert interactive["action"]["buttons"][0]["reply"]["id"] == "pay:appr_123"

    long_title = build_buttons_payload("9198", "x", [("a:b", "x" * 30)])
    assert len(long_title["interactive"]["action"]["buttons"][0]["reply"]["title"]) == 20

    four = build_buttons_payload("9198", "x", [("a:1", "1"), ("a:2", "2"), ("a:3", "3"), ("a:4", "4")])
    assert len(four["interactive"]["action"]["buttons"]) == 3


def test_cta_payload_requires_https():
    payload = build_cta_payload(
        "919876543210",
        "Complete your payment on Swiggy",
        "Pay on Swiggy",
        "https://swiggy.com/pay/bridge_123",
    )
    action = payload["interactive"]["action"]
    assert action["name"] == "cta_url"
    assert action["parameters"]["url"] == "https://swiggy.com/pay/bridge_123"

    with pytest.raises(ValueError, match="Strict scheme violation"):
        build_cta_payload("9198", "x", "Pay", "upi://pay?pa=swiggy@icici")
