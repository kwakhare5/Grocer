"""Item drop guard to ensure every item requested by a customer has an explicit outcome."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.config import SMALL_CHECK_MODEL

logger = logging.getLogger("grocer.agent.item_drop_guard")

ITEM_DROP_GUARD_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "missing_items": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Items requested by the customer that have no outcome at all.",
        },
    },
    "required": ["missing_items"],
}


def build_item_drop_guard_prompt(
    customer_message: str,
    added_items: list[str],
    unavailable_items: list[str],
    restricted_items: list[str],
    pending_items: list[str],
    removed_items: Optional[list[str]] = None,
) -> str:
    """Build the item drop verification prompt expressing plain principles without example words or product names."""
    added_str = ", ".join(added_items) if added_items else "None"
    unavailable_str = ", ".join(unavailable_items) if unavailable_items else "None"
    restricted_str = ", ".join(restricted_items) if restricted_items else "None"
    pending_str = ", ".join(pending_items) if pending_items else "None"
    removed_str = ", ".join(removed_items) if removed_items else "None"

    return (
        "You are verifying that every item requested by a customer in a shopping message has been addressed.\n\n"
        f"Customer message:\n\"{customer_message.strip()}\"\n\n"
        "Turn outcome:\n"
        f"- Added to basket: {added_str}\n"
        f"- Removed by customer request: {removed_str}\n"
        f"- Unavailable / Out of stock: {unavailable_str}\n"
        f"- Restricted: {restricted_str}\n"
        f"- Needs choice / Selection pending: {pending_str}\n\n"
        "Rules:\n"
        "1. Identify every product or item the customer explicitly requested to purchase or add.\n"
        "2. An item is accounted for if it appears in any category of the turn outcome above (added, removed, unavailable, restricted, or needs choice / selection pending), even under a slightly different brand or phrasing.\n"
        "3. Items explicitly removed from the basket by customer request are intentional deletions and must not be marked as missing.\n"
        "4. If an item was explicitly excluded, negated, or mentioned as already owned, it is not a requested item and must not be marked as missing.\n"
        "5. General greetings, conversational filler, dietary notes, budget constraints, delivery instructions, and quantity or packaging descriptors are not items.\n"
        "6. Return the list of requested items that have no outcome at all from this turn. If all requested items have an outcome, return an empty list."
    )


async def check_for_dropped_items(
    client: Any,
    customer_message: str,
    *,
    added_items: list[str],
    unavailable_items: list[str],
    restricted_items: list[str],
    pending_items: list[str],
    removed_items: Optional[list[str]] = None,
) -> list[str]:
    """Check whether any requested items were omitted without outcome using SMALL_CHECK_MODEL."""
    if not client or not getattr(client, "api_key", None):
        logger.debug("Item drop guard skipped: no client or api_key configured")
        return []
    if not customer_message.strip():
        return []

    prompt = build_item_drop_guard_prompt(
        customer_message=customer_message,
        added_items=added_items,
        unavailable_items=unavailable_items,
        restricted_items=restricted_items,
        pending_items=pending_items,
        removed_items=removed_items,
    )

    async def _invoke() -> list[str]:
        if hasattr(client, "generate_structured_with_reason"):
            out = await client.generate_structured_with_reason(
                model=SMALL_CHECK_MODEL,
                prompt=prompt,
                response_schema=ITEM_DROP_GUARD_SCHEMA,
            )
            res, reason = out if isinstance(out, tuple) else (out, None)
            if res is None:
                raise RuntimeError(f"Gemini returned no result: {reason}")
        elif hasattr(client, "generate_structured"):
            res = await client.generate_structured(
                model=SMALL_CHECK_MODEL,
                prompt=prompt,
                response_schema=ITEM_DROP_GUARD_SCHEMA,
            )
            if res is None:
                raise RuntimeError("Gemini generate_structured returned None")
        else:
            return []

        if isinstance(res, dict):
            raw_missing = res.get("missing_items", [])
            if isinstance(raw_missing, list):
                return [str(item).strip() for item in raw_missing if str(item).strip()]
        return []

    # If the guard call fails: retry once, then log a warning and continue
    try:
        return await _invoke()
    except Exception as exc:
        logger.debug("Item drop guard call failed (%s), retrying once...", exc)
        try:
            return await _invoke()
        except Exception as retry_exc:
            logger.warning("Item drop guard call failed on retry: %s; continuing turn", retry_exc)
            return []
