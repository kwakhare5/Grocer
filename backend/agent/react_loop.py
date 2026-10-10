"""ReAct function calling, multi-item intent validation, and recipe repair turn coordination."""
from __future__ import annotations

import re
from typing import Any, Optional


def validate_cart_edit_calls(
    function_calls: list[dict[str, Any]],
    current_cart: Any,
    planning_request_text: str,
) -> bool:
    """Ensure update_cart function calls modify valid active cart items with non-negative quantities."""
    cart_edits = [call for call in function_calls if call.get("name") == "update_cart"]
    if not cart_edits:
        return True
    if not current_cart or not getattr(current_cart, "items", None):
        return True

    cart_by_spin = {item.spin_id: item for item in current_cart.items}
    for call in cart_edits:
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        items = args.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                return False
            spin_id = item.get("spin_id")
            if not spin_id or spin_id not in cart_by_spin:
                return False
            quantity = item.get("quantity")
            if quantity is None or not isinstance(quantity, int) or quantity < 0:
                return False
            if planning_request_text:
                req_lower = planning_request_text.casefold()
                target_item = cart_by_spin[spin_id]
                item_name_tokens = {t for t in re.split(r"\W+", target_item.name.casefold()) if len(t) > 2}
                spin_tokens = {t for t in re.split(r"\W+", str(spin_id).casefold()) if len(t) > 2}
                has_ordinal = any(w in req_lower for w in ("first", "second", "third", "1st", "2nd", "3rd", "one", "two"))
                matches_request = has_ordinal or any(t in req_lower for t in item_name_tokens | spin_tokens)
                if not matches_request:
                    return False
                if any(w in req_lower for w in ("remove", "delete", "drop")) and quantity > 0:
                    return False
    return True


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
                or re.search(r"\b(?:ingredients?|groceries|recipe|items|stuff)\b", query, re.IGNORECASE)
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


def merge_redundant_function_calls(
    function_calls: list[dict[str, Any]],
    address_id: str,
    parts: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Merge parallel quick_add_items calls into a single batch if appropriate."""
    current_parts = list(parts) if parts is not None else []
    include_cart_in_choices = False
    if len(function_calls) > 1 and any(
        call.get("name") == "quick_add_items" for call in function_calls
    ):
        redundant_addresses = all(
            isinstance(call.get("args"), dict) and call["args"].get("address_id") == address_id
            for call in function_calls
            if call.get("name") == "select_delivery_address"
        )
        if redundant_addresses and all(
            call.get("name") in {"quick_add_items", "get_cart", "select_delivery_address"}
            for call in function_calls
        ):
            include_cart_in_choices = any(call.get("name") == "get_cart" for call in function_calls)
            batches = [
                call["args"].get("items") if isinstance(call.get("args"), dict) else None
                for call in function_calls
                if call.get("name") == "quick_add_items"
            ]
            if all(isinstance(batch, list) for batch in batches):
                merged = [item for batch in batches for item in batch]
                if 1 <= len(merged) <= 30:
                    first_add = next(call for call in function_calls if call.get("name") == "quick_add_items")
                    new_calls = [{**first_add, "args": {"items": merged}}]
                    new_parts = [part for part in current_parts if "functionCall" not in part]
                    new_parts.append({"functionCall": new_calls[0]})
                    return new_calls, new_parts, include_cart_in_choices
    return function_calls, current_parts, include_cart_in_choices

