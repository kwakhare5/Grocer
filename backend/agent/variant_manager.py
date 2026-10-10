"""Product variant selection, proposal staging, live price verification, and customer choice resolution."""
from __future__ import annotations

import logging
import math
import re
from typing import Any, Optional

from backend.agent.product_policy import is_restricted_medical_product
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.variant_manager")


def _matches_requested_product(query: str, product: dict[str, Any]) -> bool:
    """Reject loose provider search hits that do not contain the requested product words."""
    words = [
        word for word in re.findall(r"[\w]+", query.casefold())
        if word not in {"a", "an", "the", "of", "for"}
    ]
    name = " ".join(
        str(product.get(field) or "")
        for field in ("brand", "name", "pack_size", "product_name")
    ).casefold()
    return bool(words) and all(word in name for word in words)


async def execute_prepare_variant_choices(
    tools: Any,
    items: list[dict[str, Any]],
    address_id: str,
) -> dict[str, Any]:
    """Resolve every requested item to customer-visible SKU choices without writing the cart."""
    if not address_id or not isinstance(items, list) or not 1 <= len(items) <= 30:
        return {"success": False, "error": "INVALID_CART_PROPOSAL"}
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            return {"success": False, "error": "INVALID_CART_PROPOSAL"}
        query, quantity = item.get("query"), item.get("quantity", 1)
        if not isinstance(query, str) or not query.strip() or type(quantity) is not int or not 1 <= quantity <= 99:
            return {"success": False, "error": "INVALID_CART_PROPOSAL"}
        normalized.append({
            "query": query.strip(),
            "quantity": quantity,
            "preferred_pack_size": str(item.get("preferred_pack_size") or "").strip(),
        })

    search = await tools.batch_search_products([item["query"] for item in normalized], address_id)
    if not search.get("success"):
        return search
    groups: list[dict[str, Any]] = []
    unavailable: list[str] = []
    restricted: list[str] = []
    for index, (item, result) in enumerate(zip(normalized, search["results"], strict=True), 1):
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"],
                "retry_after_seconds": result.get("retry_after_seconds"),
            }
        options: list[dict[str, Any]] = []
        seen: set[str] = set()
        for product in result.get("products", []):
            if not _matches_requested_product(item["query"], product):
                continue
            if is_restricted_medical_product(
                str(product.get("name") or ""), str(product.get("category") or "")
            ):
                restricted.append(item["query"])
                continue
            spin_id, sku_id = product.get("spin_id"), product.get("sku_id")
            if not isinstance(spin_id, str) or not spin_id or spin_id in seen or not isinstance(sku_id, str):
                continue
            pack = str(product.get("pack_size") or "")
            preferred = item["preferred_pack_size"].casefold()
            if preferred and preferred not in (pack + " " + str(product.get("name") or "")).casefold():
                continue
            price = product.get("price")
            if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price < 0:
                continue
            seen.add(spin_id)
            options.append({
                "code": f"{index}{chr(64 + len(options) + 1)}",
                "spin_id": spin_id,
                "sku_id": sku_id,
                "name": str(product.get("name") or item["query"]),
                "pack_size": pack,
                "price": float(price),
                "max_quantity": product.get("max_quantity"),
            })
        if options:
            groups.append({
                "query": item["query"],
                "quantity": item["quantity"],
                "options": options[:6],
                "more_available": len(options) > 6,
            })
        elif item["query"] not in restricted:
            unavailable.append(item["query"])
    return {
        "success": True,
        "needs_variant_choice": bool(groups),
        "groups": groups,
        "unavailable_items": unavailable,
        "restricted_items": list(dict.fromkeys(restricted)),
    }


def cart_proposal_state(cart: Optional[CommerceCart]) -> Optional[dict[str, Any]]:
    """Capture normalized snapshot of live cart state to detect concurrent mutations."""
    if cart is None:
        return None
    return {
        "cart_id": cart.cart_id,
        "address_id": cart.address_id,
        "grand_total": cart.grand_total,
        "items": sorted(
            ([item.spin_id, item.sku_id, item.quantity] for item in cart.items),
            key=lambda entry: entry[0],
        ),
    }


def build_variant_choice_response(
    message: NormalizedIncomingMessage,
    proposal: dict[str, Any],
    prefix: str = "",
) -> NormalizedOutgoingResponse:
    """Format structured variant options (1A, 1B, 2A...) for WhatsApp customer display."""
    lines = [prefix, "Choose the exact products to add:"] if prefix else ["Choose the exact products to add:"]
    for index, group in enumerate(proposal["groups"], 1):
        lines.append(f"\n*{index}. {group['query']} × {group['quantity']}*")
        for option in group["options"]:
            lines.append(
                f"{option['code']} — {option['name']} ({option['pack_size']}) — ₹{option['price']:g}"
            )
        if group.get("more_available"):
            lines.append("More versions are available. Tell me a brand or pack size if none of these fit.")
    if proposal.get("unavailable_items"):
        lines.append("\nUnavailable: " + ", ".join(proposal["unavailable_items"]))
    if proposal.get("restricted_items"):
        lines.append("\nCannot add medical products here: " + ", ".join(proposal["restricted_items"]))
    examples = " ".join(group["options"][0]["code"] for group in proposal["groups"])
    lines.append(f"\nReply with one code for each item, for example: {examples}. Nothing has been added yet.")
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text="\n".join(part for part in lines if part),
        conversation_state="NEEDS_DECISION",
    )


async def handle_variant_choice(
    engine: Any,
    message: NormalizedIncomingMessage,
    customer_id: str,
    current_cart: Optional[CommerceCart],
) -> NormalizedOutgoingResponse:
    """Validate customer choice codes against staged proposal, recheck prices, and apply atomic cart update."""
    session = engine.get_session(customer_id)
    proposal = session.pending_variant_selection
    assert proposal is not None
    if message.text.casefold().strip() in {"cancel", "never mind", "start over"}:
        session.pending_variant_selection = None
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="Okay, I cancelled those product choices. Your basket was not changed.",
            conversation_state="READY",
        )
    if (
        current_cart is None
        or cart_proposal_state(current_cart) != proposal.get("cart_state")
        or engine._customer_address.get(customer_id) != proposal.get("address_id")
    ):
        session.pending_variant_selection = None
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="Your Swiggy basket or address changed. Please tell me what to add again so I can show fresh choices.",
            conversation_state="NEEDS_DECISION",
        )

    codes = re.findall(r"\b\d{1,2}[A-F]\b", message.text.upper())
    selected: list[dict[str, Any]] = []
    for group in proposal["groups"]:
        matches = [option for option in group["options"] if option["code"] in codes]
        if len(matches) != 1:
            return build_variant_choice_response(
                message, proposal, "Please give one listed code for each item.",
            )
        selected.append({
            "query": group["query"],
            "quantity": group["quantity"],
            "option": matches[0],
        })
    if len(codes) != len(selected):
        return build_variant_choice_response(
            message, proposal, "I couldn't match every code to a requested item."
        )

    fresh = await engine.tools.prepare_variant_choices(
        [{"query": group["query"], "quantity": group["quantity"]} for group in proposal["groups"]],
        proposal["address_id"],
    )
    if fresh.get("error") == "AUTH_EXPIRED":
        return await engine._auth_expired_response(message)
    if fresh.get("error") == "RATE_LIMITED":
        seconds = fresh.get("retry_after_seconds")
        wait = f"{seconds} seconds" if isinstance(seconds, int) else "a little while"
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=f"Swiggy is limiting requests. Please wait {wait}, then send the same choice codes. I kept your choices.",
            conversation_state="RECOVERING",
        )
    if not fresh.get("success"):
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="I couldn't recheck those products. Your basket was not changed. Please send the same choice codes again later.",
            conversation_state="RECOVERING",
        )
    fresh_by_query: dict[str, list[dict[str, Any]]] = {}
    for group in fresh["groups"]:
        fresh_by_query.setdefault(group["query"], []).append(group)
    for item in selected:
        option = item["option"]
        matching_groups = fresh_by_query.get(item["query"], [])
        matching_group = matching_groups.pop(0) if matching_groups else {}
        live = next(
            (
                candidate for candidate in matching_group.get("options", [])
                if candidate["spin_id"] == option["spin_id"]
                and candidate["sku_id"] == option["sku_id"]
            ),
            None,
        )
        if live is None or live["price"] != option["price"]:
            session.pending_variant_selection = {
                **fresh,
                "address_id": proposal["address_id"],
                "cart_state": proposal["cart_state"],
            } if fresh["groups"] else None
            if session.pending_variant_selection:
                return build_variant_choice_response(
                    message,
                    session.pending_variant_selection,
                    "A product's price or availability changed. Please choose again:",
                )
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="Those products are no longer available. Your basket was not changed.",
                conversation_state="NEEDS_DECISION",
            )
        item["option"] = live

    result = await engine.tools.add_selected_variants(
        selected,
        proposal["address_id"],
        current_cart,
        proposal["cart_state"],
        delivery_location=engine._customer_address_label.get(customer_id, "Home"),
        budget_cap_inr=session.budget_inr,
        ingredient_budget_inr=session.ingredient_budget_inr,
        ingredient_extras_text=session.ingredient_extras_text or "",
        ingredient_spin_ids=session.ingredient_spin_ids,
    )
    if result.get("error") == "AUTH_EXPIRED":
        return await engine._auth_expired_response(message)
    if result.get("error") == "RATE_LIMITED":
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="Swiggy is limiting requests. Please wait and then ask me to show your basket before retrying.",
            conversation_state="RECOVERING",
        )
    if not result.get("success"):
        if result.get("error") in {"CART_WRITE_UNVERIFIED", "BUDGET_ROLLBACK_UNVERIFIED"}:
            session.external_cart_pending = True
            session.pending_approval = None
        if result.get("error") not in {"CART_UNAVAILABLE", "SEARCH_UNAVAILABLE"}:
            session.pending_variant_selection = None
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=result.get("message") or "I couldn't verify the basket change. Please show your basket before trying again.",
            conversation_state="NEEDS_DECISION",
        )

    session.pending_variant_selection = None
    session.pending_request_text = None
    session.ingredient_spin_ids = result.get("ingredient_spin_ids", session.ingredient_spin_ids)
    session.known_cart_fingerprint = result.get("verified_fingerprint")
    missing = list(dict.fromkeys(
        proposal.get("unavailable_items", [])
        + proposal.get("restricted_items", [])
        + result.get("budget_blocked_items", [])
    ))
    note = f"I couldn't add: {', '.join(missing)}. Please tell me what to change.\n\n" if missing else ""
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=note + result["formatted_receipt"],
        conversation_state="NEEDS_DECISION" if missing else "AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[] if missing else [
            InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
        order_total=result["grand_total"],
    )
