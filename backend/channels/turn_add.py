"""The add path's search and evaluation stage — no cart writes here."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from backend.agent.candidate_evaluator import (
    ExtractedGroceryItem,
    IntentType,
    evaluate_customer_intents_batch,
)
from backend.agent.candidate_search import search_catalog_full
from backend.agent.composite_cart import TargetCartItem
from backend.agent.meal_planner import (
    exact_packs_for,
    measure,
    measure_from_text,
    pack_plan,
)
from backend.agent.read_actions import format_disambiguation_choices
from backend.channels.turn_context import TurnContext
from backend.integrations.commerce.swiggy_client import normalize_query

# Abuse limits: one person cannot burn the free Swiggy calls for everyone.
MAX_ITEMS_PER_MESSAGE = 10
MAX_ITEM_QUANTITY = 99


@dataclass
class AddPlan:
    """What the router asked for, turned into cart lines or a question."""

    items_to_add: list[TargetCartItem] = field(default_factory=list)
    choice_prompts: list[tuple[ExtractedGroceryItem, list[Any]]] = field(
        default_factory=list
    )
    unfound_queries: list[str] = field(default_factory=list)
    alternative_hints: list[str] = field(default_factory=list)
    vague_spins: set[str] = field(default_factory=set)


def describe_item(target: ExtractedGroceryItem) -> str:
    if target.amount is None:
        return target.query
    return f"{target.query} {target.amount:g} {target.unit or ''}".strip()


def _packs_for(target: ExtractedGroceryItem, cand: Any) -> int | None:
    if target.unit in {"pack", "packs", "packet", "packets"}:
        packs = int(target.amount or target.quantity)
        return max(1, min(MAX_ITEM_QUANTITY, packs))
    if target.amount is not None and target.unit:
        return exact_packs_for(
            target.amount,
            target.unit,
            cand.quantity_description or cand.display_name,
        )
    return max(1, min(MAX_ITEM_QUANTITY, target.quantity))


def _sizes(cands: list[Any]) -> list[str]:
    found: list[str] = []
    for cand in cands:
        size = (cand.quantity_description or "").strip()
        if size and size not in found:
            found.append(size)
    return found[:3]


def _extract(decision_items: Any, fallback_text: str) -> list[ExtractedGroceryItem]:
    extracted_items: list[ExtractedGroceryItem] = []
    for item in decision_items:
        query_text = str(item.get("query") or "").strip()
        if not query_text:
            continue
        try:
            quantity = max(
                1,
                min(MAX_ITEM_QUANTITY, int(item.get("quantity") or 1)),
            )
        except (TypeError, ValueError):
            quantity = 1

        unit = str(item.get("unit") or "").strip().lower() or None
        amount: float | None = None
        raw_amount = item.get("amount")
        if raw_amount is not None:
            try:
                amount = float(raw_amount)
            except (TypeError, ValueError):
                amount = None

        if amount is None:
            measured = measure_from_text(query_text)
            if measured:
                amount, unit = measured[1], measured[0]
        elif unit not in {None, "pack", "packs", "packet", "packets"}:
            if measure(amount, unit) is None:
                measured = measure_from_text(query_text)
                if measured:
                    amount, unit = measured[1], measured[0]
                else:
                    amount, unit = None, None
        if amount is not None and amount <= 0:
            amount = None
        if amount is not None and unit is None:
            # A bare number ("6 eggs") is a count, not a pack count.
            unit = "count"

        extracted_items.append(
            ExtractedGroceryItem(
                query=query_text,
                quantity=quantity,
                amount=amount,
                unit=unit,
            )
        )
    if not extracted_items:
        return [ExtractedGroceryItem(query=fallback_text, quantity=1)]
    return extracted_items


def _merge(extracted_items: list[ExtractedGroceryItem]) -> list[ExtractedGroceryItem]:
    merged_items: dict[tuple[str, str | None, float | None], ExtractedGroceryItem] = {}
    for target in extracted_items:
        key = (
            normalize_query(target.query).lower(),
            target.unit,
            target.amount,
        )
        if key in merged_items:
            merged = merged_items[key]
            merged.quantity += target.quantity
            if merged.amount is not None and target.amount is not None:
                merged.amount += target.amount
        else:
            merged_items[key] = target
    return list(merged_items.values())


async def plan_add(
    ctx: TurnContext,
    decision: Any,
    address_count: int,
) -> AddPlan | dict[str, Any]:
    """Search and evaluate. A returned dict means the turn already answered."""
    extracted_items = _extract(decision.items, ctx.text)

    if len(extracted_items) > MAX_ITEMS_PER_MESSAGE:
        await ctx.wa_client.send_text_message(
            to_wa_id=ctx.wa_id,
            text=(
                f"I can handle up to {MAX_ITEMS_PER_MESSAGE} items in one "
                "message. Please split that into two messages."
            ),
        )
        return {"status": "too_many_items", "wa_id": ctx.wa_id}

    # 1a. The same words, size and amount share one search and one
    # evaluation; the pack counts add up.
    extracted_items = _merge(extracted_items)

    async def search_one(target: ExtractedGroceryItem):
        outcome = await asyncio.to_thread(
            search_catalog_full,
            query=target.query,
            swiggy_client=ctx.client,
            address_id=ctx.address_id,
        )
        return target, outcome.candidates, outcome.alternatives

    search_results = await asyncio.gather(
        *(search_one(target) for target in extracted_items)
    )
    evaluations = await asyncio.to_thread(
        evaluate_customer_intents_batch,
        [
            (describe_item(target), cands)
            for target, cands, _alternatives in search_results
        ],
        address_count,
        ctx.text,
    )

    plan = AddPlan()

    def _queue(cand: Any, packs: int) -> None:
        plan.items_to_add.append(
            TargetCartItem(
                spin_id=cand.spin_id,
                sku_id=cand.sku_id,
                quantity=packs,
                item_name=cand.display_name,
                price_paise=cand.offer_price_paise,
                max_quantity=cand.max_quantity,
                max_quantity_message=cand.max_quantity_message,
            )
        )

    for (target, cands, alternatives), evaluation in zip(
        search_results, evaluations, strict=True
    ):
        if evaluation.selected_candidate:
            cand = evaluation.selected_candidate
            packs = _packs_for(target, cand)
            if packs is None:
                # The picked pack does not fit the amount. Take the fewest
                # packs that add up exactly before troubling the customer
                # with a question.
                exact_plan = pack_plan(
                    target.amount,
                    target.unit,
                    [
                        (
                            option.spin_id,
                            option.quantity_description or option.display_name,
                        )
                        for option in cands
                    ],
                )
                if exact_plan:
                    by_spin = {option.spin_id: option for option in cands}
                    for spin_id, count in exact_plan:
                        _queue(by_spin[spin_id], count)
                else:
                    plan.unfound_queries.append(describe_item(target))
                    sizes = _sizes(cands)
                    if sizes:
                        plan.alternative_hints.append(
                            f"{describe_item(target)} → {', '.join(sizes)}"
                        )
                continue
            if evaluation.is_vague_staple:
                plan.vague_spins.add(cand.spin_id)
            _queue(cand, packs)
        elif evaluation.intent_type == IntentType.DISAMBIGUATION:
            plan.choice_prompts.append((target, cands))
        else:
            plan.unfound_queries.append(describe_item(target))
            if alternatives:
                plan.alternative_hints.append(
                    f"{describe_item(target)} → {', '.join(alternatives)}"
                )

    if (
        not plan.items_to_add
        and not plan.choice_prompts
        and len(search_results) == 1
        and len(search_results[0][1]) >= 2
    ):
        target, cands, alternatives = search_results[0]
        if target.amount is not None and target.unit:
            exact_cands = [
                option for option in cands if _packs_for(target, option) is not None
            ]
            cands = exact_cands or cands
        choice_text, choice_buttons = format_disambiguation_choices(
            describe_item(target), cands, target.quantity
        )
        if alternatives:
            choice_text += f"\n\nSimilar: {', '.join(alternatives)}"
        await ctx.wa_client.send_quick_reply_buttons(
            to_wa_id=ctx.wa_id,
            body_text=choice_text,
            buttons=choice_buttons,
        )
        await ctx.remember(choice_text)
        return {
            "status": "item_choices",
            "wa_id": ctx.wa_id,
            "candidates": len(cands),
        }

    if not plan.items_to_add and plan.choice_prompts:
        asked: list[str] = []
        for target, cands in plan.choice_prompts[:2]:
            choice_text, choice_buttons = format_disambiguation_choices(
                describe_item(target), cands, target.quantity
            )
            await ctx.wa_client.send_quick_reply_buttons(
                to_wa_id=ctx.wa_id,
                body_text=choice_text,
                buttons=choice_buttons,
            )
            asked.append(choice_text)
        if plan.unfound_queries:
            detail = ", ".join(plan.unfound_queries)
            if plan.alternative_hints:
                detail += "\nSimilar: " + "; ".join(plan.alternative_hints)
            await ctx.wa_client.send_text_message(
                to_wa_id=ctx.wa_id,
                text=f"I couldn't find at this store: {detail}.",
            )
        await ctx.remember("\n\n".join(asked))
        return {
            "status": "item_choices",
            "wa_id": ctx.wa_id,
            "candidates": len(plan.choice_prompts),
        }

    return plan
