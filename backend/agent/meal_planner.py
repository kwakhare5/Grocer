"""Grocer v1.0 — Recipe plan, confirmed before any write (ADR 0009).

The model names the dish, the people count and the amount of each ingredient.
Python searches the live store, turns amounts into whole packs, prices the plan
and stores it until the customer taps. Nothing is written before the tap.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.candidate_search import CandidateItem, search_catalog_full
from backend.agent.composite_cart import TargetCartItem
from backend.agent.router import RoutingDecision

logger = logging.getLogger("grocer.meal_planner")

MAX_PLAN_ITEMS = 8
MAX_PACKS_PER_ITEM = 20
PLAN_TTL_MINUTES = 30
_ASSUMPTIONS = "Assuming you have salt, oil and common spices."

# Base units: grams, millilitres, pieces. Everything the store prints folds in.
_UNIT_SCALES: dict[str, tuple[str, float]] = {
    "g": ("g", 1),
    "gm": ("g", 1),
    "gms": ("g", 1),
    "gram": ("g", 1),
    "grams": ("g", 1),
    "kg": ("g", 1000),
    "kgs": ("g", 1000),
    "kilo": ("g", 1000),
    "kilos": ("g", 1000),
    "kilogram": ("g", 1000),
    "kilograms": ("g", 1000),
    "ml": ("ml", 1),
    "millilitre": ("ml", 1),
    "millilitres": ("ml", 1),
    "milliliter": ("ml", 1),
    "milliliters": ("ml", 1),
    "l": ("ml", 1000),
    "lt": ("ml", 1000),
    "ltr": ("ml", 1000),
    "litre": ("ml", 1000),
    "litres": ("ml", 1000),
    "liter": ("ml", 1000),
    "liters": ("ml", 1000),
    "piece": ("count", 1),
    "pieces": ("count", 1),
    "pc": ("count", 1),
    "pcs": ("count", 1),
    "count": ("count", 1),
    "counts": ("count", 1),
    "unit": ("count", 1),
    "units": ("count", 1),
    "nos": ("count", 1),
    "no": ("count", 1),
    "ea": ("count", 1),
    "each": ("count", 1),
    "dozen": ("count", 12),
}

_PACK_OF = re.compile(r"pack\s+of\s+(\d+)", re.IGNORECASE)
_NUMBER_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)")
_PICK_WORDS = re.compile(r"\band\b", re.IGNORECASE)
_PICK_SHAPE = re.compile(r"[\d\s,&]+")


def measure(amount: Any, unit: str | None) -> tuple[str, float] | None:
    """Return (family, base amount) for a number and a unit, or None."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    scaled = _UNIT_SCALES.get((unit or "").strip().lower().rstrip("."))
    if not scaled:
        return None
    family, scale = scaled
    return family, value * scale


def parse_pack_size(description: str | None) -> tuple[str, float] | None:
    """Read a store pack size ('500 g', '1 L', '6 pieces') into base units."""
    text = description or ""
    pack_of = _PACK_OF.search(text)
    if pack_of:
        return "count", float(pack_of.group(1))
    match = _NUMBER_UNIT.search(text)
    if not match:
        return None
    return measure(match.group(1), match.group(2))


def packs_for(
    amount: Any,
    unit: str | None,
    quantity_description: str | None,
) -> int | None:
    """Whole packs needed for an amount, or None when the sizes cannot be compared."""
    needed = measure(amount, unit)
    pack = parse_pack_size(quantity_description)
    if not needed or not pack or needed[0] != pack[0] or pack[1] <= 0:
        return None
    return max(1, math.ceil(needed[1] / pack[1]))


def parse_pick_indexes(text: str, item_count: int) -> list[int] | None:
    """Read a numbered reply like '1 and 3' against the plan on screen."""
    if item_count <= 0 or not text:
        return None
    remainder = _PICK_WORDS.sub(" ", text.strip())
    if not remainder or not _PICK_SHAPE.fullmatch(remainder):
        return None
    picks: list[int] = []
    for chunk in re.findall(r"\d+", remainder):
        index = int(chunk)
        if index < 1 or index > item_count:
            return None
        if index not in picks:
            picks.append(index)
    return picks or None


def plan_items(plan: Any) -> list[dict[str, Any]]:
    """The usable ingredient rows of a stored plan."""
    if not isinstance(plan, dict):
        return []
    raw = plan.get("items")
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw[:MAX_PLAN_ITEMS]:
        if isinstance(entry, dict) and str(entry.get("query") or "").strip():
            items.append(entry)
    return items


def _wanted_ingredients(
    decision: RoutingDecision,
) -> list[tuple[str, float | None, str | None, int]]:
    items: list[tuple[str, float | None, str | None, int]] = []
    for raw in decision.items[:MAX_PLAN_ITEMS]:
        query = str(raw.get("query") or "").strip()
        if not query:
            continue
        try:
            fallback = max(1, min(MAX_PACKS_PER_ITEM, int(raw.get("quantity") or 1)))
        except (TypeError, ValueError):
            fallback = 1
        amount: float | None = None
        unit: str | None = None
        if measure(raw.get("amount"), str(raw.get("unit") or "")) is not None:
            amount = float(raw["amount"])
            unit = str(raw.get("unit") or "").strip().lower() or None
        items.append((query, amount, unit, fallback))
    return items


def _packs(candidate: CandidateItem, amount: Any, unit: str | None, fallback: int) -> int:
    computed = packs_for(amount, unit, candidate.quantity_description)
    packs = computed if computed is not None else fallback
    return max(1, min(MAX_PACKS_PER_ITEM, packs))


def _pick(
    candidates: list[CandidateItem], preferred_spin: str | None = None
) -> CandidateItem | None:
    """The confirmed SKU, never a lookalike. No stored SKU means first in stock."""
    if preferred_spin:
        return next(
            (c for c in candidates if c.spin_id == preferred_spin),
            None,
        )
    return candidates[0] if candidates else None


async def clear_pending_plan(conn: Any, user_id: Any) -> None:
    await conn.execute(
        "UPDATE grocer.sessions SET pending_plan = NULL, "
        "pending_plan_expires_at = NULL WHERE user_id = $1;",
        user_id,
    )


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
) -> tuple[str, list[tuple[str, str]], dict[str, Any] | None]:
    dish = (decision.dish or "").strip()
    ingredients = _wanted_ingredients(decision)
    if not dish or not decision.servings or not ingredients:
        return "Which dish should I plan, and for how many people?", [], None

    servings = decision.servings
    results = await asyncio.gather(
        *(_search_one(client, address_id, query) for query, _amount, _unit, _fallback in ingredients)
    )

    lines = [f"🍳 *{dish.title()} for {servings}*", ""]
    total_paise = 0
    plan_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    capped: list[str] = []

    for (query, amount, unit, fallback), candidates in zip(ingredients, results, strict=True):
        candidate = _pick(candidates)
        if candidate is None:
            missing.append(query)
            continue
        allowed = _packs(candidate, amount, unit, fallback)
        if candidate.max_quantity is not None and allowed > candidate.max_quantity:
            allowed = max(0, candidate.max_quantity)
            capped.append(f"{query} capped at {allowed}")
        if allowed <= 0:
            missing.append(query)
            continue
        price = candidate.offer_price_paise
        total_paise += price * allowed
        lines.append(
            f"{len(plan_rows) + 1}. {candidate.display_name} "
            f"({candidate.quantity_description}) ×{allowed} — "
            f"{format_paise_to_rupees(price)} each"
        )
        plan_rows.append(
            {
                "query": query,
                "amount": amount,
                "unit": unit,
                "packs": allowed,
                "spin_id": candidate.spin_id,
                "sku_id": candidate.sku_id,
                "name": candidate.display_name,
                "size": candidate.quantity_description,
                "price_paise": price,
            }
        )

    if not plan_rows:
        return (
            (
                f"I couldn't find the ingredients for {dish.title()} at your local "
                "store right now. Nothing was added."
            ),
            [],
            None,
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
    extra = (
        sum(1 for raw in decision.items if str(raw.get("query") or "").strip())
        - MAX_PLAN_ITEMS
    )
    if extra > 0:
        lines.append(
            f"⚠️ I planned the first {MAX_PLAN_ITEMS} ingredients. "
            f"Ask me for the other {extra} separately."
        )

    buttons: list[tuple[str, str]] = [
        ("plan:add", "Add in-stock" if missing else "Add all"),
        ("plan:pick", "Let me pick"),
    ]
    plan = {
        "dish": dish,
        "servings": servings,
        "items": plan_rows,
        "total_paise": total_paise,
        "missing": missing,
    }
    return "\n".join(lines), buttons, plan


async def resolve_plan_items(
    client: Any,
    address_id: str | None,
    plan: Any,
    indexes: list[int] | None = None,
) -> tuple[list[TargetCartItem], list[str], str | None]:
    """Rebuild the confirmed plan from live stock.

    Without `indexes` the whole plan must be available or nothing is written.
    With `indexes` the chosen rows are added and the missing ones are named.
    """
    rows = plan_items(plan)
    if not rows:
        return [], [], "That plan is not available any more. Ask me to plan the meal again."

    if indexes is None:
        chosen = list(range(len(rows)))
    else:
        chosen = [index - 1 for index in indexes if 1 <= index <= len(rows)]
        if not chosen:
            return [], [], "Which numbers should I add?"

    results = await asyncio.gather(
        *(_search_one(client, address_id, str(rows[index].get("query"))) for index in chosen)
    )

    selected: list[TargetCartItem] = []
    missing: list[str] = []
    for index, candidates in zip(chosen, results, strict=True):
        row = rows[index]
        query = str(row.get("query") or "").strip()
        candidate = _pick(candidates, str(row.get("spin_id") or "") or None)
        if candidate is None:
            missing.append(query)
            continue
        try:
            fallback = max(1, min(MAX_PACKS_PER_ITEM, int(row.get("packs") or 1)))
        except (TypeError, ValueError):
            fallback = 1
        pack_count = _packs(candidate, row.get("amount"), row.get("unit"), fallback)
        if candidate.max_quantity is not None:
            pack_count = min(pack_count, candidate.max_quantity)
        if pack_count <= 0:
            missing.append(query)
            continue
        selected.append(
            TargetCartItem(
                spin_id=candidate.spin_id,
                sku_id=candidate.sku_id,
                quantity=pack_count,
                item_name=candidate.display_name,
                price_paise=candidate.offer_price_paise,
                max_quantity=candidate.max_quantity,
                max_quantity_message=candidate.max_quantity_message,
            )
        )

    if missing and indexes is None:
        return (
            [],
            missing,
            "These ingredients are not in stock right now: "
            + ", ".join(missing)
            + ". Nothing was added. Ask me to plan it again.",
        )
    if not selected:
        return (
            [],
            missing,
            "Nothing from that plan is in stock right now. Nothing was added.",
        )
    return selected, missing, None
