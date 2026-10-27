"""Grocer v1.0 — Capability Router & Safety Class Tests (ADR 0012).

Pure-function tests: no LLM call, no database, no Swiggy. The live routing
behaviour is graded separately by scripts/eval_router.py.
"""

from __future__ import annotations

from backend.agent.router import (
    AI_OUTAGE_REPLY,
    CAPABILITY_SPECS,
    SAFETY_BY_CAPABILITY,
    Capability,
    SafetyClass,
    parse_decision,
    route_message,
)


def test_catalog_is_complete_and_typed():
    assert {spec.capability for spec in CAPABILITY_SPECS} == set(Capability)
    assert set(SAFETY_BY_CAPABILITY) == set(Capability)


def test_valid_read_capability_is_not_a_write():
    d = parse_decision(
        {"capability": "item_info", "confidence": 0.93, "items": [{"query": "amul milk"}]},
        "how much is amul milk",
    )
    assert d.capability is Capability.ITEM_INFO
    assert d.safety is SafetyClass.READ
    assert d.is_write is False
    assert d.safe_path is False


def test_basket_capability_is_a_write():
    d = parse_decision(
        {"capability": "add_items", "confidence": 0.9, "items": [{"query": "milk", "quantity": 2}]},
        "add 2 milk",
    )
    assert d.capability is Capability.ADD_ITEMS
    assert d.safety is SafetyClass.BASKET
    assert d.is_write is True
    assert d.items[0]["quantity"] == 2


def test_low_confidence_write_falls_back_to_read_only():
    d = parse_decision(
        {"capability": "add_items", "confidence": 0.42, "items": [{"query": "milk"}]},
        "maybe milk?",
    )
    assert d.capability is Capability.ITEM_INFO
    assert d.safety is SafetyClass.READ
    assert d.safe_path is True
    assert d.is_write is False


def test_low_confidence_money_never_executes():
    d = parse_decision(
        {"capability": "checkout", "confidence": 0.7},
        "just pay",
    )
    assert d.safety is SafetyClass.READ
    assert d.capability is Capability.ITEM_INFO or d.capability is Capability.CHAT
    assert d.is_write is False


def test_unknown_capability_with_a_product_answers_read_only():
    d = parse_decision(
        {"capability": "teleport_groceries", "confidence": 0.99, "items": [{"query": "bread"}]},
        "bread?",
    )
    assert d.capability is Capability.ITEM_INFO
    assert d.safety is SafetyClass.READ
    assert d.safe_path is True


def test_unknown_capability_without_a_product_asks():
    d = parse_decision({"capability": "???", "confidence": 0.99}, "hmm")
    assert d.capability is Capability.CHAT
    assert d.safe_path is True
    assert d.reply


def test_confident_chat_is_a_normal_answer_not_a_safe_path():
    d = parse_decision(
        {"capability": "chat", "confidence": 0.98, "reply": "Hey! What do you need?"},
        "hello",
    )
    assert d.capability is Capability.CHAT
    assert d.safe_path is False
    assert d.reply == "Hey! What do you need?"


def test_missing_payload_asks_and_never_writes():
    d = parse_decision(None, "anything")
    assert d.capability is Capability.CHAT
    assert d.safety is SafetyClass.READ
    assert d.safe_path is True
    assert d.is_write is False


def test_confidence_is_clamped_and_items_without_query_are_dropped():
    d = parse_decision(
        {
            "capability": "item_info",
            "confidence": 4.2,
            "items": [{"quantity": 2}, {"query": "  eggs  "}],
        },
        "eggs",
    )
    assert d.confidence == 1.0
    assert len(d.items) == 1
    assert d.items[0]["query"] == "  eggs  "


def test_account_delete_needs_high_confidence():
    d = parse_decision(
        {"capability": "delete_address", "confidence": 0.82, "address_ref": "work"},
        "delete my work address",
    )
    assert d.capability is Capability.CHAT
    assert d.safe_path is True
    assert d.is_write is False


def test_view_basket_is_a_read_capability():
    d = parse_decision(
        {"capability": "view_basket", "confidence": 0.96}, "what's in my basket"
    )
    assert d.capability is Capability.VIEW_BASKET
    assert d.safety is SafetyClass.READ


def test_llm_outage_is_not_reported_as_customer_confusion():
    d = route_message("add milk", provider="no-such-provider")
    assert d.error is not None
    assert d.reply == AI_OUTAGE_REPLY
    assert d.reply != "I didn't quite catch that"


def test_plan_meal_is_read_only_and_parses_dish_and_servings():
    d = parse_decision(
        {
            "capability": "plan_meal",
            "confidence": 0.95,
            "items": [{"query": "pizza base", "quantity": 3}],
            "dish": "pizza",
            "servings": 5,
        },
        "make pizza for 5 people",
    )
    assert d.capability is Capability.PLAN_MEAL
    assert d.safety is SafetyClass.READ
    assert d.is_write is False
    assert d.dish == "pizza"
    assert d.servings == 5
