"""Grocer — Outbound WhatsApp payload shape (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.channels.reactions import reaction_for_result
from backend.channels.whatsapp import _basket_notice
from backend.channels.whatsapp_client import (
    build_buttons_payload,
    build_cta_payload,
    build_reaction_payload,
    build_read_payload,
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


def test_read_payload_marks_read_and_types():
    payload = build_read_payload("wamid.HBgM123")
    assert payload["status"] == "read"
    assert payload["message_id"] == "wamid.HBgM123"
    assert payload["typing_indicator"] == {"type": "text"}
    assert "to" not in payload


def test_reaction_payload_shape():
    payload = build_reaction_payload("919876543210", "wamid.HBgM123", "🏠")
    assert payload["type"] == "reaction"
    assert payload["to"] == "919876543210"
    assert payload["reaction"] == {"message_id": "wamid.HBgM123", "emoji": "🏠"}


def test_reactions_are_sparse_and_match_the_outcome():
    assert (
        reaction_for_result(
            {"status": "capability_answered", "capability": "list_addresses"}
        )
        == "🏠"
    )
    assert (
        reaction_for_result({"status": "capability_answered", "capability": "view_basket"})
        == "🛒"
    )
    assert (
        reaction_for_result({"status": "capability_answered", "capability": "track_order"})
        == "🛵"
    )
    assert (
        reaction_for_result({"status": "capability_answered", "capability": "plan_meal"})
        == "🍳"
    )
    assert reaction_for_result({"status": "cart_updated"}) == "🛒"
    assert reaction_for_result({"status": "plan_picked"}) == "🛒"
    assert reaction_for_result({"status": "item_choices"}) == "❓"

    # Nothing to celebrate on chat, misses, locks or outages.
    assert reaction_for_result({"status": "capability_answered", "capability": "chat"}) is None
    assert reaction_for_result({"status": "no_match"}) is None
    assert reaction_for_result({"status": "capability_unavailable"}) is None
    assert reaction_for_result({"status": "auth_required"}) is None
    assert reaction_for_result({"status": "checkout_failed"}) is None


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


def test_old_basket_is_mentioned_only_after_an_idle_hour():

    cart = FixtureSwiggyClient(Path(__file__).parent / "fixtures").get_cart(
        "addr_01HXYZ"
    )
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    notice = _basket_notice(old, cart)
    assert notice is not None
    assert "still has" in notice[0]
    assert notice[1] == [("cart:keep", "Keep basket"), ("cart:clear", "Clear basket")]
    assert _basket_notice(datetime.now(timezone.utc), cart) is None
