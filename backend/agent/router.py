"""Grocer v1.0 — Capability Router with Safety Classes (ADR 0012).

The LLM names what the customer wants; Python decides whether it is allowed to
run. A read capability can never reach a write path, and anything unclear takes
the safe path: read-only information or a clarifying question.
"""

from __future__ import annotations

import json
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
    VIEW_BASKET = "view_basket"
    PLAN_MEAL = "plan_meal"
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
    CapabilitySpec(Capability.VIEW_BASKET, SafetyClass.READ, "Show what is currently in the basket, with quantities and the total."),
    CapabilitySpec(Capability.PLAN_MEAL, SafetyClass.READ, "Plan a dish or recipe for a number of people. Show ingredients, pack counts and a total; add only after a tap."),
    CapabilitySpec(Capability.ADD_ITEMS, SafetyClass.BASKET, "Add one or more groceries to the basket."),
    CapabilitySpec(Capability.CHANGE_ITEM, SafetyClass.BASKET, "Change quantity, replace or remove an item already in the basket."),
    CapabilitySpec(Capability.CLEAR_BASKET, SafetyClass.BASKET, "Empty the whole basket."),
    CapabilitySpec(Capability.REORDER, SafetyClass.BASKET, "Rebuild a basket from a past order or the customer's usual items."),
    CapabilitySpec(Capability.ADD_ADDRESS, SafetyClass.ACCOUNT, "Save a new delivery address."),
    CapabilitySpec(Capability.SWITCH_ADDRESS, SafetyClass.ACCOUNT, "Change the address used for the current basket."),
    CapabilitySpec(Capability.DELETE_ADDRESS, SafetyClass.ACCOUNT, "Delete a saved address."),
    CapabilitySpec(Capability.CHECKOUT, SafetyClass.MONEY, "Customer wants to pay or place the order ('place the order', 'buy now', 'checkout'). Execution still requires the physical pay button."),
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

AI_OUTAGE_REPLY = (
    "My AI is offline right now, so I couldn't read that. Nothing in your "
    "basket changed. Send that again in a minute."
)


@dataclass
class RoutingDecision:
    capability: Capability
    safety: SafetyClass
    confidence: float
    items: list[dict[str, Any]] = field(default_factory=list)
    order_ref: str | None = None
    address_ref: str | None = None
    change_action: str | None = None
    reply: str | None = None
    dish: str | None = None
    servings: int | None = None
    safe_path: bool = False
    provider: str | None = None
    error: str | None = None

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
        "Delivery time or fee for a new basket is store_info. Status, rider or ETA "
        "of an order already placed ('arrives', 'coming', 'delivered') is track_order.\n"
        "If the customer wants a product in their basket, use add_items.\n"
        "A request to make, cook or plan a dish for some people ('make pizza for 5') "
        "is plan_meal, never add_items. Put the dish in dish, the people count in "
        "servings, and the need for each ingredient in items as amount and unit: "
        "g, ml or piece ('250 g' cheese, '1 l' milk, '5 pieces' base). Never add "
        "anything; the customer confirms first. Leave salt, oil, water and common "
        "spices out; use specific grocery names like 'mozzarella cheese', not 'cheese'.\n"
        "A bare grocery list with no question ('milk and bread', '2 kg atta') is "
        "a request to add those items, so use add_items.\n"
        "If the customer asks what is already in their basket or what it costs, "
        "use view_basket.\n"
        "If the message is unclear, use chat and ask one short question.\n"
        "Understand English, Hindi and Hinglish grocery words (doodh, dahi, atta, pyaz, cheeni).\n"
        "Never invent order ids, address ids or product ids. Use null when unknown.\n"
        "If the customer names an address or label (home, work, mom's, Pune), copy that "
        "word into address_ref. If they refer to an order, put 'last' or the order number "
        "in order_ref.\n"
        "For change_item only, set change_action to remove or set_quantity, and put the "
        "target quantity in items[0].quantity when changing quantity.\n"
        "If the item is already in the basket and the customer asks to change how many "
        "or remove it, use change_item, not add_items.\n"
        "Repeating a past order or the customer's usual list ('same as last time', "
        "'my regular items') is reorder, never add_items.\n"
        "If the last assistant message was a numbered recipe plan and the customer "
        "replies with numbers, use add_items for those plan items with the same "
        "pack counts.\n"
        "Asking to remove or delete a saved address is delete_address, even when the "
        "label is vague ('my old address'). Ask which one only after choosing the "
        "capability.\n"
        "Always write the reply in English, whatever language the customer used. "
        "Friendly and professional, at most two short sentences, no slang.\n\n"
        "Capabilities:\n" + _capability_list_for_prompt() + "\n\n"
        "Examples:\n"
        'Customer: remove milk -> {"capability":"change_item","confidence":0.95,'
        '"items":[{"query":"milk","quantity":1}],"change_action":"remove"}\n'
        'Customer: make milk 3 -> {"capability":"change_item","confidence":0.95,'
        '"items":[{"query":"milk","quantity":3}],"change_action":"set_quantity"}\n'
        'Customer: add 2 eggs -> {"capability":"add_items","confidence":0.95,'
        '"items":[{"query":"eggs","quantity":2}],"change_action":null}\n'
        'Customer: add milk and bread -> {"capability":"add_items","confidence":0.95,'
        '"items":[{"query":"milk","quantity":1},{"query":"bread","quantity":1}],'
        '"change_action":null}\n'
        'Customer: get 1 litre milk and 6 eggs -> {"capability":"add_items","confidence":0.95,'
        '"items":[{"query":"milk 1 litre","quantity":1},{"query":"eggs","quantity":6}],'
        '"change_action":null}\n'
        'Customer: make pizza for 5 people -> {"capability":"plan_meal","confidence":0.95,'
        '"items":[{"query":"pizza base","amount":5,"unit":"piece"},'
        '{"query":"mozzarella cheese","amount":250,"unit":"g"},'
        '{"query":"pizza sauce","amount":200,"unit":"g"}],"dish":"pizza","servings":5,'
        '"change_action":null}\n'
        'Customer: how much is milk -> {"capability":"item_info","confidence":0.95,'
        '"items":[{"query":"milk","quantity":1}],"change_action":null}\n'
        'Customer: same as last time -> {"capability":"reorder","confidence":0.95,'
        '"items":[],"order_ref":"last"}\n\n'
        "Return JSON only:\n"
        '{"capability": "<one capability>", "confidence": <0.0-1.0>, '
        '"items": [{"query": "<product words>", "quantity": <int>, '
        '"amount": <number or null>, "unit": "<g or ml or piece or null>"}], '
        '"order_ref": "<order id or last or null>", '
        '"address_ref": "<address label or id or null>", '
        '"change_action": "<remove or set_quantity or null>", '
        '"dish": "<dish for plan_meal or null>", '
        '"servings": <people count for plan_meal or null>, '
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

    change_action = payload.get("change_action")
    if change_action not in {"remove", "set_quantity"}:
        change_action = None

    dish = str(payload.get("dish") or "").strip() or None
    try:
        servings = int(payload.get("servings") or 0) or None
    except (TypeError, ValueError):
        servings = None
    if servings is not None:
        servings = max(1, min(servings, 50))

    if reply is None and capability is Capability.CHAT:
        reply = "Hey! What groceries do you need?"

    return RoutingDecision(
        capability=capability,
        safety=safety,
        confidence=confidence,
        items=items,
        order_ref=payload.get("order_ref"),
        address_ref=payload.get("address_ref"),
        change_action=change_action,
        reply=reply,
        dish=dish,
        servings=servings,
        provider=provider,
    )


def route_message(
    message: str,
    history: list[dict[str, Any]] | None = None,
    provider: str | None = None,
    basket: list[dict[str, Any]] | None = None,
) -> RoutingDecision:
    """Ask the LLM for a routing decision and apply Python's safety rules."""
    basket_text = (
        ", ".join(
            f"{item.get('name', 'item')} x{item.get('quantity', 1)}"
            for item in (basket or [])[:10]
        )
        or "empty"
    )
    user_prompt = (
        f"Basket now: {basket_text}\n\n"
        f"Dialogue so far:\n{_history_text(history)}\n\n"
        f"Latest customer message:\n{message}"
    )
    result = complete_json(_system_prompt(), user_prompt, provider)
    if not result.ok:
        logger.warning(
            "Router LLM unavailable after %sms: %s", result.latency_ms, result.error
        )
        return RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=0.0,
            reply=AI_OUTAGE_REPLY,
            safe_path=True,
            provider=result.provider,
            error=result.error,
        )
    decision = parse_decision(result.data, message, provider=result.provider)
    logger.info(
        "route decision %s",
        json.dumps(
            {
                "capability": decision.capability.value,
                "safety": decision.safety.value,
                "confidence": round(decision.confidence, 2),
                "items": decision.items,
                "order_ref": decision.order_ref,
                "address_ref": decision.address_ref,
                "change_action": decision.change_action,
                "safe_path": decision.safe_path,
                "provider": decision.provider,
                "latency_ms": result.latency_ms,
            },
            ensure_ascii=True,
        ),
    )
    return decision
