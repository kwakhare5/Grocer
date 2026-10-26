"""Grocer v1.0 — WhatsApp Message & Receipt Formatters.

Handles WhatsApp copy styling adhering to DESIGN.md and PRD specifications:
1. Multi-store split order receipt styling (ADR 0007).
2. Swiggy Care phone escalation instructions (080-67466729, ADR 0007).
3. Post-order addition advisories and 1-tap reorder buttons (ADR 0009).
4. Pure integer paise math; zero floating-point formatting.
"""

from __future__ import annotations

from typing import Any

from backend.agent.candidate_evaluator import format_paise_to_rupees

SWIGGY_CARE_PHONE = "080-67466729"


def format_multi_store_split_receipt(
    order_ids: list[str],
    store_names: list[str],
    total_paise: int,
) -> str:
    """Format unified receipt with split tracking links for multi-store fulfillment (ADR 0007)."""
    lines = [
        "📦 *Multi-Store Order Confirmed*",
        f"Your items will arrive in {len(order_ids)} separate deliveries from nearby dark stores.",
        f"*Total Paid:* {format_paise_to_rupees(total_paise)}",
        "-----------------------------------",
    ]
    for idx, (oid, sname) in enumerate(zip(order_ids, store_names), start=1):
        lines.append(f"• Delivery {idx} ({sname}): order #{oid}")
        lines.append(f"  Live Tracking: https://swiggy.com/track/{oid}")
    lines.append("-----------------------------------")
    return "\n".join(lines)


def get_order_cancellation_instructions(order_id: str) -> str:
    """Instruct customer on Swiggy Care phone escalation protocol (ADR 0007)."""
    return (
        f"To cancel your Instamart order #{order_id}, please call Swiggy Customer Care directly at "
        f"*{SWIGGY_CARE_PHONE}*. Instamart orders are packed immediately at the dark store, so phone escalation "
        f"is required to halt delivery partner dispatch."
    )


def handle_post_order_addition(
    order_id: str,
    item_name: str,
    item_price_paise: int,
    order_is_packing: bool = True,
) -> dict[str, Any]:
    """Advise customer on post-order addition protocol (ADR 0009).

    Explains that active order is sealed/packing at dark store, and offers 1-tap separate order.
    """
    price_rs = format_paise_to_rupees(item_price_paise)
    if order_is_packing:
        explanation = (
            f"Your order #{order_id} is already being packed at the dark store and cannot be modified. "
            f"Would you like me to place a quick separate order for {item_name} ({price_rs}) to the same address?"
        )
    else:
        explanation = (
            f"Your order #{order_id} has already dispatched. "
            f"Would you like to start a fresh order for {item_name} ({price_rs})?"
        )

    buttons = [
        {"id": f"post_add:{order_id}:{item_name}", "title": f"Order {item_name} Now"},
        {"id": "post_add:cancel", "title": "Never Mind"},
    ]

    return {
        "text": explanation,
        "buttons": buttons,
    }
