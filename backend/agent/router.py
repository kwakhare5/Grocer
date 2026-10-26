"""Grocer v1.0 — Capability Router with Safety Classes (ADR 0012).

The LLM names what the customer wants; Python decides whether it is allowed to
run. A read capability can never reach a write path, and anything unclear takes
the safe path: read-only information or a clarifying question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.agent.llm import complete_json
from backend.config import settings

logger = logging.getLogger("grocer.router")


class SafetyClass(str, Enum):
    READ = "read"
    BASKET = "basket"
    ACCOUNT = "account"
    MONEY = "money"


class Capability(str, Enum):
    CHAT = "chat"
    ITEM_INFO = "item_info"
    STORE_INFO = "store_info"
    LIST_ADDRESSES = "list_addresses"
    ORDER_HISTORY = "order_history"
    TRACK_ORDER = "track_order"
    LIST_COUPONS = "list_coupons"
    PAYMENT_OPTIONS = "payment_options"
    CANCEL_HELP = "cancel_help"
    ADD_ITEMS = "add_items"
    CHANGE_ITEM = "change_item"
    CLEAR_BASKET = "clear_basket"
    REORDER = "reorder"
    ADD_ADDRESS = "add_address"
    SWITCH_ADDRESS = "switch_address"
    DELETE_ADDRESS = "delete_address"
    CHECKOUT = "checkout"


@dataclass(frozen=True)
class CapabilitySpec:
    capability: Capability
    safety: SafetyClass
    description: str


# Single source of truth for the prompt, the safety map and the dispatch table.
CAPABILITY_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(Capability.CHAT, SafetyClass.READ, "Small talk, greetings, thanks, or a question that needs no live data."),
    CapabilitySpec(Capability.ITEM_INFO, SafetyClass.READ, "Price, pack sizes, stock or availability of a product. Never adds anything."),
    CapabilitySpec(Capability.STORE_INFO, SafetyClass.READ, "Which dark store serves the customer, delivery time, delivery fee or store hours."),
    CapabilitySpec(Capability.LIST_ADDRESSES, SafetyClass.READ, "Show the customer's saved delivery addresses."),
    CapabilitySpec(Capability.ORDER_HISTORY, SafetyClass.READ, "List past or active orders from the last 15 days."),
    CapabilitySpec(Capability.TRACK_ORDER, SafetyClass.READ, "Live status, rider or ETA for one specific order."),
    CapabilitySpec(Capability.LIST_COUPONS, SafetyClass.READ, "Show available coupons and savings."),
    CapabilitySpec(Capability.PAYMENT_OPTIONS, SafetyClass.READ, "Show which payment methods are available."),
    CapabilitySpec(Capability.CANCEL_HELP, SafetyClass.READ, "Customer wants to cancel. Grocer cannot cancel; it gives Swiggy care details."),
    CapabilitySpec(Capability.ADD_ITEMS, SafetyClass.BASKET, "Add one or more groceries to the basket."),
    CapabilitySpec(Capability.CHANGE_ITEM, SafetyClass.BASKET, "Change quantity, replace or remove an item already in the basket."),
    CapabilitySpec(Capability.CLEAR_BASKET, SafetyClass.BASKET, "Empty the whole basket."),
    CapabilitySpec(Capability.REORDER, SafetyClass.BASKET, "Rebuild a basket from a past order or the customer's usual items."),
    CapabilitySpec(Capability.ADD_ADDRESS, SafetyClass.ACCOUNT, "Save a new delivery address."),
    CapabilitySpec(Capability.SWITCH_ADDRESS, SafetyClass.ACCOUNT, "Change the address used for the current basket."),
    CapabilitySpec(Capability.DELETE_ADDRESS, SafetyClass.ACCOUNT, "Delete a saved address."),
    CapabilitySpec(Capability.CHECKOUT, SafetyClass.MONEY, "Customer wants to pay or place the order. Execution still requires the physical pay button."),
)

SAFETY_BY_CAPABILITY: dict[Capability, SafetyClass] = {
    spec.capability: spec.safety for spec in CAPABILITY_SPECS
}

# Writes need more certainty than reads. Money is never executed from text.
SAFETY_CONFIDENCE_FLOOR: dict[SafetyClass, float] = {
    SafetyClass.READ: 0.0,
    SafetyClass.BASKET: 0.80,
    SafetyClass.ACCOUNT: 0.85,
    SafetyClass.MONEY: 0.95,
}

SAFE_PATH_REPLY = (
    "I didn't quite catch that. Do you want me to check a product, "
    "or add something to your basket?"
)


@dataclass
class RoutingDecision:
    capability: Capability
    safety: SafetyClass
    confidence: float
    items: list[dict[str, Any]] = field(default_factory=list)
    order_ref: str | None = None
    address_ref: str | None = None
    reply: str | None = None
    safe_path: bool = False
    provider: str | None = None

    @property
    def is_write(self) -> bool:
        return self.safety is not SafetyClass.READ


def _capability_list_for_prompt() -> str:
    return "\n".join(
        f"- {spec.capability.value}: {spec.description}" for spec in CAPABILITY_SPECS
    )


def _system_prompt() -> str:
    return (
        "You route customer messages for Grocer, a Swiggy Instamart concierge on WhatsApp in India.\n"
        "Pick exactly one capability from the list. Never invent a capability.\n"
        "Price, pack size and stock questions are item_info, never add_items.\n"
        "If the customer wants a product in their basket, use add_items.\n"
        "If the message is unclear, use chat and ask one short question.\n"
        "Understand English, Hindi and Hinglish grocery words (doodh, dahi, atta, pyaz, cheeni).\n"
        "Never invent order ids, address ids or product ids. Use null when unknown.\n"
        "Always write the reply in English, whatever language the customer used. "
        "Friendly and professional, at most two short sentences, no slang.\n\n"
        "Capabilities:\n" + _capability_list_for_prompt() + "\n\n"
        "Return JSON only:\n"
        '{"capability": "<one capability>", "confidence": <0.0-1.0>, '
        '"items": [{"query": "<product words>", "quantity": <int>}], '
        '"order_ref": "<order id or last or null>", '
        '"address_ref": "<address label or id or null>", '
        '"reply": "<short reply, mainly for chat>"}'
    )


def _history_text(history: list[dict[str, Any]] | None) -> str:
    lines: list[str] = []
    for turn in (history or [])[-12:]:
        text = turn.get("text") or turn.get("content") or ""
        if text:
            lines.append(f"{turn.get('role', 'user').capitalize()}: {text}")
    return "\n".join(lines) if lines else "None"


def parse_decision(
    payload: dict[str, Any] | None,
    message: str,
    provider: str | None = None,
) -> RoutingDecision:
    """Turn a model payload into a decision, applying safety rules.

    Pure function: no network, no database. Tests call it directly.
    """
    if not payload:
        return RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=0.0,
            reply=SAFE_PATH_REPLY,
            safe_path=True,
            provider=provider,
        )

    raw_capability = str(payload.get("capability") or "").strip().lower()
    recognised = True
    try:
        capability = Capability(raw_capability)
    except ValueError:
        capability = Capability.CHAT
        recognised = False

    items = [
        item
        for item in (payload.get("items") or [])
        if isinstance(item, dict) and str(item.get("query") or "").strip()
    ]

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    safety = SAFETY_BY_CAPABILITY[capability]
    floor = max(settings.ROUTER_CONFIDENCE_FLOOR, SAFETY_CONFIDENCE_FLOOR[safety])
    reply = str(payload.get("reply") or "").strip() or None

    # Unknown or shaky. A product was named, so answer read-only; otherwise ask.
    if not recognised or confidence < floor:
        if items:
            return RoutingDecision(
                capability=Capability.ITEM_INFO,
                safety=SafetyClass.READ,
                confidence=confidence,
                items=items,
                reply=None,
                safe_path=True,
                provider=provider,
            )
        return RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=confidence,
            reply=reply or SAFE_PATH_REPLY,
            safe_path=True,
            provider=provider,
        )

    if reply is None and capability is Capability.CHAT:
        reply = "Hey! What groceries do you need?"

    return RoutingDecision(
        capability=capability,
        safety=safety,
        confidence=confidence,
        items=items,
        order_ref=payload.get("order_ref"),
        address_ref=payload.get("address_ref"),
        reply=reply,
        provider=provider,
    )


def route_message(
    message: str,
    history: list[dict[str, Any]] | None = None,
    provider: str | None = None,
) -> RoutingDecision:
    """Ask the LLM for a routing decision and apply Python's safety rules."""
    user_prompt = (
        f"Dialogue so far:\n{_history_text(history)}\n\n"
        f"Latest customer message:\n{message}"
    )
    result = complete_json(_system_prompt(), user_prompt, provider)
    if not result.ok:
        logger.warning("Router LLM unavailable: %s", result.error)
        return RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=0.0,
            reply=SAFE_PATH_REPLY,
            safe_path=True,
            provider=result.provider,
        )
    return parse_decision(result.data, message, provider=result.provider)
