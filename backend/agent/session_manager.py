"""Customer session state serialization, task state persistence, and history compaction."""
from __future__ import annotations

import time
from typing import Any, Optional

from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.session import CustomerSession
from backend.integrations.commerce.models import CommerceCart


def record_pending_approval(
    session: CustomerSession, cart: CommerceCart, address_id: str
) -> bool:
    """Record pending order approval with 15-minute TTL."""
    fingerprint = cart_fingerprint(cart, address_id)
    session.pending_approval = (
        PendingApproval(fingerprint=fingerprint, expires_at=time.time() + 900)
        if fingerprint
        else None
    )
    if fingerprint:
        session.known_cart_fingerprint = fingerprint
    return fingerprint is not None


def prune_history_entries(
    history: list[dict[str, Any]],
    has_state_store: bool = False,
    max_user_turns: int = 20,
) -> list[dict[str, Any]]:
    """Keep conversation history bounded by whole user turn boundaries and compact past search returns."""
    if not history:
        return []

    hist = list(history)
    if has_state_store:
        cutoff_time = time.time() - 30 * 86400
        hist = [
            entry
            for entry in hist
            if isinstance(entry.get("recorded_at"), (int, float))
            and entry["recorded_at"] > cutoff_time
        ]

    # Identify turn start indices: user messages with user text (not function responses)
    user_turn_starts = [
        i
        for i, entry in enumerate(hist)
        if entry.get("role") == "user"
        and any("text" in p for p in entry.get("parts", []))
    ]

    if len(user_turn_starts) > max_user_turns:
        cutoff = user_turn_starts[-max_user_turns]
        hist = hist[cutoff:]
    elif not user_turn_starts and len(hist) > 12:
        hist = hist[-12:]

    # Compact bulky product search returns from older turns while preserving variants
    for entry in hist[:-2]:
        if entry.get("role") == "user" and "parts" in entry:
            for part in entry["parts"]:
                fn_resp = part.get("functionResponse", {})
                content = fn_resp.get("response", {}).get("content", {})
                if isinstance(content, dict) and "products" in content and len(content.get("products", [])) > 2:
                    compacted_products = []
                    for p in content["products"][:2]:
                        variants = p.get("variants") or []
                        first_var = variants[0] if variants and isinstance(variants[0], dict) else {}
                        compacted_products.append({
                            "product_id": p.get("product_id"),
                            "name": p.get("name") or first_var.get("name"),
                            "spin_id": p.get("spin_id") or first_var.get("spin_id"),
                            "sku_id": p.get("sku_id") or first_var.get("sku_id"),
                            "price": p.get("price") or first_var.get("price"),
                            "pack_size": p.get("pack_size") or first_var.get("pack_size"),
                        })
                    content["products"] = compacted_products

    return hist


def restore_task_state_dict(
    customer_id: str,
    state: dict[str, Any] | None,
    customer_address: dict[str, str],
    customer_address_label: dict[str, str],
    order_address_confirmed: dict[str, bool],
    awaiting_address_choice: dict[str, Any],
    last_interaction_time: dict[str, float],
) -> tuple[CustomerSession, list[dict[str, Any]]]:
    """Restore customer session and address lock mappings from persistent task state."""
    state = state or {}
    history = state.get("history") or []

    for mapping, field in (
        (customer_address, "address_id"),
        (customer_address_label, "address_label"),
        (order_address_confirmed, "order_address_confirmed"),
        (awaiting_address_choice, "awaiting_address_choice"),
        (last_interaction_time, "last_active_ts"),
    ):
        mapping.pop(customer_id, None)
        if state.get(field) is not None:
            mapping[customer_id] = state[field]

    approval = state.get("pending_approval")
    session = CustomerSession(
        customer_id=customer_id,
        history=history,
        budget_inr=state.get("budget_inr"),
        ingredient_budget_inr=state.get("ingredient_budget_inr"),
        ingredient_extras_text=state.get("ingredient_extras_text"),
        ingredient_spin_ids=state.get("ingredient_spin_ids") or [],
        pending_approval=PendingApproval(**approval) if approval else None,
        unresolved_items=state.get("unresolved_items") or [],
        budget_blocked_items=state.get("budget_blocked_items") or [],
        known_cart_fingerprint=state.get("known_cart_fingerprint"),
        external_cart_pending=bool(state.get("external_cart_pending", False)),
        pending_request_text=state.get("pending_request_text"),
        pending_variant_selection=state.get("pending_variant_selection"),
        selected_payment_id=state.get("selected_payment_id"),
        selected_payment_kind=state.get("selected_payment_kind"),
        selected_payment_method=state.get("selected_payment_method"),
        selected_payment_label=state.get("selected_payment_label"),
    )
    return session, history


def dump_task_state_dict(
    session: CustomerSession,
    history: list[dict[str, Any]],
    address_id: Optional[str],
    address_label: Optional[str],
    order_address_confirmed: bool,
    awaiting_address_choice: Any,
    last_active_ts: Optional[float],
) -> dict[str, Any]:
    """Serialize customer session state into JSON-safe dictionary for Postgres."""
    approval = session.pending_approval
    return {
        "history": history,
        "address_id": address_id,
        "address_label": address_label,
        "order_address_confirmed": order_address_confirmed,
        "awaiting_address_choice": awaiting_address_choice,
        "last_active_ts": last_active_ts,
        "budget_inr": session.budget_inr,
        "ingredient_budget_inr": session.ingredient_budget_inr,
        "ingredient_extras_text": session.ingredient_extras_text,
        "ingredient_spin_ids": session.ingredient_spin_ids,
        "pending_approval": (
            {"fingerprint": approval.fingerprint, "expires_at": approval.expires_at}
            if approval
            else None
        ),
        "unresolved_items": session.unresolved_items,
        "budget_blocked_items": session.budget_blocked_items,
        "known_cart_fingerprint": session.known_cart_fingerprint,
        "external_cart_pending": session.external_cart_pending,
        "pending_request_text": session.pending_request_text,
        "pending_variant_selection": session.pending_variant_selection,
        "selected_payment_id": session.selected_payment_id,
        "selected_payment_kind": session.selected_payment_kind,
        "selected_payment_method": session.selected_payment_method,
        "selected_payment_label": session.selected_payment_label,
    }
