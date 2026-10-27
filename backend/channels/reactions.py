"""One quiet reaction per inbound message, chosen by outcome, not by the model.

A reaction means "done". Errors, outages and plain chat get none.
"""

from __future__ import annotations

from typing import Any

_READ_REACTIONS: dict[str, str] = {
    "list_addresses": "🏠",
    "view_basket": "🛒",
    "order_history": "📦",
    "track_order": "🛵",
    "list_coupons": "🎟️",
    "payment_options": "💳",
}

_STATUS_REACTIONS: dict[str, str] = {
    "cart_updated": "🛒",
    "item_choices": "❓",
    "basket_quantity_choice": "❓",
    "location_pin_requested": "📍",
}


def reaction_for_result(result: dict[str, Any]) -> str | None:
    status = str(result.get("status") or "")
    if status == "capability_answered":
        return _READ_REACTIONS.get(str(result.get("capability") or ""))
    return _STATUS_REACTIONS.get(status)
