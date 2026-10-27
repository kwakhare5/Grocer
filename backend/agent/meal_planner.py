"""Grocer v1.0 — Recipe plan, confirmed before any write (ADR 0009).

The model names the dish, the people count and the packs. Python searches the
live store, prices the plan and waits for a tap. Nothing is written before it.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.candidate_search import CandidateItem, search_catalog_full
from backend.agent.composite_cart import TargetCartItem
from backend.agent.router import RoutingDecision

logger = logging.getLogger("grocer.meal_planner")

MAX_PLAN_ITEMS = 8
MAX_BUTTON_ID = 250
_ASSUMPTIONS = "Assuming you have salt, oil and common spices."


def encode_plan(items: list[tuple[str, int]]) -> str | None:
    raw = "|".join(
        f"{query.replace('|', ' ').replace('~', ' ')}~{quantity}"
        for query, quantity in items[:MAX_PLAN_ITEMS]
    )
    token = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    button_id = "plan:add:" + token
    return button_id if len(button_id) <= MAX_BUTTON_ID else None


def decode_plan(token: str) -> list[tuple[str, int]] | None:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None

    items: list[tuple[str, int]] = []
    for part in raw.split("|"):
        query, separator, quantity_text = part.rpartition("~")
        if not separator or not query.strip():
            return None
        try:
            quantity = int(quantity_text)
        except ValueError:
            return None
        if quantity < 1 or quantity > 20:
            return None
        items.append((query.strip(), quantity))
    return items if items and len(items) <= MAX_PLAN_ITEMS else None


def _wanted_ingredients(decision: RoutingDecision) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for raw in decision.items[:MAX_PLAN_ITEMS]:
        query = str(raw.get("query") or "").strip()
        if not query:
            continue
        try:
            quantity = max(1, min(20, int(raw.get("quantity") or 1)))
        except (TypeError, ValueError):
            quantity = 1
        items.append((query, quantity))
    return items


def _pick(candidates: list[CandidateItem]) -> CandidateItem | None:
    return candidates[0] if candidates else None


async def _search_one(
    client: Any, address_id: str | None, query: str
) -> list[CandidateItem]:
    try:
        outcome = await asyncio.to_thread(
            search_catalog_full,
            query=query,
            swiggy_client=client,
            address_id=address_id,
        )
        return outcome.candidates
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
        logger.warning("Meal plan search failed for %s: %s", query, exc)
        return []


async def build_meal_plan(
    decision: RoutingDecision,
    client: Any,
    address_id: str | None,
) -> tuple[str, list[tuple[str, str]]]:
    dish = (decision.dish or "").strip()
    ingredients = _wanted_ingredients(decision)
    if not dish or not decision.servings or not ingredients:
        return "Which dish should I plan, and for how many people?", []

    servings = decision.servings
    results = await asyncio.gather(
        *(_search_one(client, address_id, query) for query, _quantity in ingredients)
    )

    lines = [f"🍳 *{dish.title()} for {servings}*", ""]
    total_paise = 0
    buttons: list[tuple[str, str]] = []
    plan_items: list[tuple[str, int]] = []
    missing: list[str] = []
    capped: list[str] = []

    for index, ((query, quantity), candidates) in enumerate(
        zip(ingredients, results, strict=True), start=1
    ):
        candidate = _pick(candidates)
        if candidate is None:
            missing.append(query)
            continue
        allowed = quantity
        if candidate.max_quantity is not None and allowed > candidate.max_quantity:
            allowed = max(0, candidate.max_quantity)
            capped.append(f"{query} capped at {allowed}")
        if allowed <= 0:
            missing.append(query)
            continue
        price = candidate.offer_price_paise
        total_paise += price * allowed
        lines.append(
            f"{index}. {candidate.display_name} ({candidate.quantity_description}) "
            f"×{allowed} — {format_paise_to_rupees(price)} each"
        )
        plan_items.append((query, allowed))

    if not plan_items:
        return (
            (
                f"I couldn't find the ingredients for {dish.title()} at your local "
                "store right now. Nothing was added."
            ),
            [],
        )

    lines.append("")
    lines.append(
        f"*Estimated items: {format_paise_to_rupees(total_paise)}.* "
        "Fees and coupons are applied at checkout."
    )
    lines.append(_ASSUMPTIONS)
    if missing:
        lines.append(f"Not at this store: {', '.join(missing)}.")
    if capped:
        lines.append("⚠️ " + "; ".join(capped) + ".")

    add_button = encode_plan(plan_items)
    if add_button:
        label = "Add in-stock" if missing else "Add all"
        buttons.append((add_button, label))
    buttons.append(("plan:pick", "Let me pick"))

    return "\n".join(lines), buttons[:3]


async def resolve_plan_items(
    client: Any,
    address_id: str | None,
    token: str,
) -> tuple[list[TargetCartItem] | None, str | None]:
    """Rebuild the confirmed plan from live stock. All in, or nothing written."""
    items = decode_plan(token)
    if not items:
        return None, "That plan link is not valid. Ask me to plan the meal again."

    results = await asyncio.gather(
        *(_search_one(client, address_id, query) for query, _quantity in items)
    )
    selected: list[TargetCartItem] = []
    missing: list[str] = []
    for (query, quantity), candidates in zip(items, results, strict=True):
        candidate = _pick(candidates)
        if candidate is None:
            missing.append(query)
            continue
        allowed = quantity
        if candidate.max_quantity is not None:
            allowed = min(allowed, candidate.max_quantity)
        if allowed <= 0:
            missing.append(query)
            continue
        selected.append(
            TargetCartItem(
                spin_id=candidate.spin_id,
                sku_id=candidate.sku_id,
                quantity=allowed,
                item_name=candidate.display_name,
                price_paise=candidate.offer_price_paise,
                max_quantity=candidate.max_quantity,
                max_quantity_message=candidate.max_quantity_message,
            )
        )

    if missing:
        return (
            None,
            "These ingredients are not in stock right now: "
            + ", ".join(missing)
            + ". Nothing was added. Ask me to plan it again.",
        )
    return selected, None
