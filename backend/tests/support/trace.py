"""PII-free interpretation trace helper for quantity-matrix tests."""
from __future__ import annotations

from typing import Any

from backend.intent.models import IntentItem, ResolvedMeaning


def build_interpretation_trace(
    item: IntentItem,
    *,
    catalog_evidence: list[str] | None = None,
    actual_cart_quantity: int | None = None,
    classification: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Build a PII-free trace dict for one test item's resolution lifecycle."""
    meaning: ResolvedMeaning | None = item.resolved_meaning
    requested = f"{item.quantity:g} {item.name}"
    semantic_state = (
        f"bare quantity = {item.quantity:g}"
        if meaning is not None and meaning.requested_dimension == "catalog_dependent"
        else f"{meaning.requested_dimension if meaning else item.unit} = {item.quantity:g}"
    )
    planned = (
        f"{meaning.cart_quantity} x selected SKU"
        if meaning is not None and meaning.cart_quantity is not None
        else "unresolved"
    )
    actual = (
        f"{actual_cart_quantity} x selected SKU"
        if actual_cart_quantity is not None
        else (
            f"{meaning.actual_cart_quantity} x selected SKU"
            if meaning is not None and meaning.actual_cart_quantity is not None
            else "unknown"
        )
    )
    requested_total = meaning.cart_quantity if meaning is not None else None
    accepted_total = (
        actual_cart_quantity
        if actual_cart_quantity is not None
        else (meaning.actual_cart_quantity if meaning is not None else None)
    )
    difference: Any = "unknown"
    if requested_total is not None and accepted_total is not None:
        difference = f"{requested_total - accepted_total} retail units unmet"
    return {
        "user_request": requested,
        "semantic_state": semantic_state,
        "catalog_evidence": list(catalog_evidence or []),
        "planned": planned,
        "actual_cart": actual,
        "difference": difference,
        "classification": classification or (meaning.status if meaning else "UNVERIFIABLE"),
        "next_action": next_action or "targeted recovery / clarification",
        "explanation": meaning.explanation if meaning else "",
        "clarification_required": bool(meaning.clarification_required) if meaning else True,
    }
