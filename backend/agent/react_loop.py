"""ReAct loop coordination and cart edit validation helpers.
Re-exported from react_coordinator.py for clean domain consolidation.
"""
from __future__ import annotations

import re
from typing import Any

from backend.agent.react_coordinator import (
    merge_redundant_function_calls,
    validate_cart_edit_calls,
)


def is_invalid_item_plan(calls: list[dict[str, Any]]) -> bool:
    """Validate that quick_add_items calls contain safe, concrete product queries."""
    for call in calls:
        if call.get("name") != "quick_add_items":
            continue
        args = call.get("args")
        items = args.get("items") if isinstance(args, dict) else None
        if not isinstance(items, list) or not 1 <= len(items) <= 45:
            return True
        for item in items:
            if not isinstance(item, dict):
                return True
            query = item.get("query")
            quantity = item.get("quantity", 1)
            if (
                not isinstance(query, str)
                or not query.strip()
                or type(quantity) is not int
                or not 1 <= quantity <= 99
                or (
                    bool(
                        re.search(r"^(?:(?:all\s+)?(?:the\s+)?(?:ingredients?|groceries|recipe|items?|stuff))$", query.strip(), re.IGNORECASE)
                        or query.strip().casefold().endswith((" ingredients", " ingredient", " groceries"))
                        or re.search(r"\b(?:ingredients?|groceries|recipe)\s+(?:for|of)\b", query.strip(), re.IGNORECASE)
                    )
                    and not bool(re.search(r"\b(?:masala|mix|powder|paste|sauce|kit|seasoning)\b", query.strip(), re.IGNORECASE))
                )
            ):
                return True
    return False


def build_recipe_repair_prompt(planning_request_text: str) -> str:
    """Build repair instruction prompt when Gemini proposes invalid or abstract items."""
    return (
        f"Customer request: {planning_request_text}\n\n"
        "Your previous plan was not safe to search. Call quick_add_items with "
        "concrete product queries, one object per item, and the customer's "
        "quantity and pack-size details. Expand any named meal into ingredients."
    )


__all__ = [
    "validate_cart_edit_calls",
    "merge_redundant_function_calls",
    "is_invalid_item_plan",
    "build_recipe_repair_prompt",
]
