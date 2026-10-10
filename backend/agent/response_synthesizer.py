"""Outbound WhatsApp response synthesis, receipt formatting, interactive action attachment, and history pruning."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

from backend.agent.formatters import format_cart_receipt
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)

logger = logging.getLogger("grocer.agent.response_synthesizer")

_NON_ENGLISH_RE = re.compile(
    r"[\u0900-\u097F]|\b(?:aapke|aapka|meri|mera|hata|hatao|chahiye|karo|kardo|nahin|theek|hain|hota|paas|jankari|bhai|bhau)\b",
    re.IGNORECASE,
)


def _ensure_english_only(text: str) -> str:
    """Intercept and cleanse any non-English tokens from outbound customer messages."""
    if not text:
        return text
    if _NON_ENGLISH_RE.search(text):
        logger.warning("Deterministic guard: non-English tokens intercepted in outbound text. Cleansing to English.")
        receipt_match = re.search(r"🛒\s*\*?Your Basket.*", text, flags=re.DOTALL | re.IGNORECASE)
        if receipt_match:
            return f"I can only assist with groceries on Swiggy Instamart in English.\n\n{receipt_match.group(0)}"
        return "I can only help you shop for groceries on Swiggy Instamart in English. What grocery items would you like to order today?"
    return text


async def synthesize_turn_response(
    engine: Any,
    message: NormalizedIncomingMessage,
    customer_id: str,
    *,
    final_text: str,
    actions: list[InteractiveAction],
    conv_state: str,
    last_cart_receipt: Optional[str],
    last_cart_total: Optional[float],
    out_order_id: Optional[str],
    out_order_total: Optional[float],
    out_bridge_url: Optional[str],
    address_changed: bool,
    suggestion_only: bool,
    suggested_items: list[str],
    restricted_items: list[str],
    search_failed_items: list[str],
    budget_blocked_items: list[str],
    unavailable_items: list[str],
    reduced_items: list[str],
    guarded_change_message: Optional[str],
    pending_request_needs_retry: bool,
    step_limit_reached: bool,
    checkout_executed: bool,
    user_confirmed: bool,
    incoming_text: str,
    addr_lbl: Optional[str],
) -> NormalizedOutgoingResponse:
    """Build and format the final NormalizedOutgoingResponse for WhatsApp."""
    session = engine.get_session(customer_id)
    history = engine.get_history(customer_id)
    current_cart = None

    if step_limit_reached:
        receipt_str = last_cart_receipt
        if receipt_str:
            final_text = (
                "I've added the available items to your basket, but reached the maximum processing steps for this turn before completing all remaining searches.\n\n"
                f"{receipt_str}\n\n"
                "👉 Reply to continue resolving the remaining items before basket approval."
            )
        else:
            final_text = (
                "I reached the maximum processing steps for this request. "
                "Please tell me which specific item you'd like me to add or search next!"
            )
        actions = [
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            InteractiveAction(action_type="button", id="start_fresh", title="Clear Cart"),
        ]
        conv_state = "NEEDS_DECISION"
    elif last_cart_receipt:
        amnesiac_phrases = (
            "what would you like to order",
            "what can i get for you",
            "what do you want to order",
            "how can i help with your groceries",
            "what groceries",
            "what would you like",
        )
        is_amnesiac = any(p in final_text.casefold() for p in amnesiac_phrases)
        if address_changed and is_amnesiac:
            logger.info(
                "Deterministic address-change guard triggered: overriding amnesiac text for %s",
                addr_lbl,
            )
            final_text = f"I've updated your delivery address to *{addr_lbl}*! 📍\n\n{last_cart_receipt}"
        elif last_cart_receipt not in final_text:
            basket_match = re.search(r"🛒\s*\*?Your Basket.*", final_text, flags=re.DOTALL | re.IGNORECASE)
            if basket_match:
                intro = final_text[: basket_match.start()].strip()
                final_text = f"{intro}\n\n{last_cart_receipt}" if intro else last_cart_receipt
            elif not final_text.strip() or final_text.strip() == "How can I help with your groceries today?":
                if address_changed:
                    final_text = f"I've updated your delivery address to *{addr_lbl}*! 📍\n\n{last_cart_receipt}"
                else:
                    final_text = last_cart_receipt
            else:
                final_text = f"{final_text.strip()}\n\n{last_cart_receipt}"

        actions = [
            InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ]
        conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

    elif any(
        phrase in final_text.casefold()
        for phrase in (
            "place this order",
            "confirm order",
            "shall i place",
            "would you like me to place",
            "reply *confirm*",
            "reply confirm",
            "place order",
            "confirm to place order",
        )
    ):
        actions = [
            InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ]
        conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

    if suggestion_only:
        if not suggested_items:
            suggested_items = (
                ["ginger", "lemon", "honey", "tea"]
                if any(word in incoming_text.casefold() for word in ("cold", "cough", "throat"))
                else ["water", "tea", "a light snack"]
            )
        options = ", ".join(suggested_items[:5])
        final_text = (
            "I can suggest groceries, but I can't add medical products here. "
            f"You could choose from: {options}. Which would you like me to add?"
        )
        actions = []
        conv_state = "NEEDS_DECISION"
        session.pending_request_text = None
    elif restricted_items:
        restricted = ", ".join(dict.fromkeys(restricted_items))
        receipt = last_cart_receipt or ""
        final_text = (
            f"I can't add medical products through this WhatsApp shopping flow: {restricted}. "
            "I can help you choose groceries instead."
        )
        if receipt:
            final_text += f"\n\n{receipt}"
        actions = []
        conv_state = "NEEDS_DECISION"
    elif search_failed_items:
        unchecked = ", ".join(dict.fromkeys(search_failed_items))
        receipt = last_cart_receipt or ""
        final_text = (
            f"I couldn't check {unchecked} with Swiggy right now, so I don't know whether "
            "those items are available. I saved your request. Reply *try again* to continue."
        )
        if receipt:
            final_text += f"\n\n{receipt}"
        session.pending_request_text = session.pending_request_text or message.text.strip()
        actions = []
        conv_state = "NEEDS_DECISION"

    if guarded_change_message:
        final_text = guarded_change_message
        actions = []
        conv_state = "NEEDS_DECISION"

    if budget_blocked_items or unavailable_items or reduced_items:
        blocked = list(dict.fromkeys(budget_blocked_items))
        unavailable = list(dict.fromkeys(unavailable_items))
        reduced = list(dict.fromkeys(reduced_items))
        session.budget_blocked_items = blocked + unavailable + reduced
        session.pending_approval = None
        receipt = last_cart_receipt or "Your basket is empty."
        scoped_note = ""
        if session.ingredient_budget_inr is not None:
            try:
                current_cart = await engine.commerce.get_cart()
            except Exception:
                current_cart = None
            if current_cart:
                ingredient_total = sum(
                    item.total_price
                    for item in current_cart.items
                    if item.spin_id in session.ingredient_spin_ids
                )
                scoped_note = (
                    f"Ingredient items: ₹{ingredient_total:,.2f} of "
                    f"₹{session.ingredient_budget_inr:,.2f}. "
                    "Extras and shared fees are outside that limit; the full payable total is below. "
                )
        has_items_in_basket = bool(last_cart_receipt and "Your Basket is empty" not in last_cart_receipt and last_cart_total)
        if has_items_in_basket:
            basket_followup = (
                "I kept the items that fit in the order you listed them. "
                "Would you like to keep this partial basket or change something?\n\n"
                + receipt
            )
            actions = [
                InteractiveAction(action_type="button", id="accept_partial_basket", title="Keep These Items"),
                InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            ]
        else:
            basket_followup = (
                "Would you like to try searching for something else or check another delivery location?\n\n"
                + receipt
            )
            actions = [
                InteractiveAction(action_type="button", id="modify_cart", title="Try Other Items"),
            ]

        final_text = (
            (
                (
                    "These recipe ingredients did not fit your ingredient-price limit: "
                    if session.ingredient_budget_inr is not None
                    else "These requested items did not fit your budget: "
                )
                + ", ".join(blocked)
                + ". "
                if blocked
                else ""
            )
            + ("These requested items were unavailable: " + ", ".join(unavailable) + ". " if unavailable else "")
            + ("Swiggy reduced these quantities: " + ", ".join(reduced) + ". " if reduced else "")
            + scoped_note
            + basket_followup
        )
        conv_state = "NEEDS_DECISION"

    if (not final_text.strip() or final_text.strip() == "How can I help with your groceries today?") and last_cart_receipt:
        final_text = last_cart_receipt
    if out_order_total is None and last_cart_total is not None:
        out_order_total = last_cart_total

    if any(action.id == "confirm_order" for action in actions):
        if session.budget_blocked_items:
            session.pending_approval = None
            actions = [action for action in actions if action.id != "confirm_order"]
            conv_state = "NEEDS_DECISION"
            final_text = (
                "Some requested items were left out: "
                + ", ".join(session.budget_blocked_items)
                + ". Please review this partial basket and choose Keep These Items or tell me what to change."
            )
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=final_text,
                interactive_actions=[
                    InteractiveAction(action_type="button", id="accept_partial_basket", title="Keep These Items"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state=conv_state,
            )
        unresolved = engine.get_session(customer_id).unresolved_items
        if unresolved:
            engine.get_session(customer_id).pending_approval = None
            actions = [action for action in actions if action.id != "confirm_order"]
            conv_state = "NEEDS_DECISION"
            final_text = (
                "Swiggy changed or omitted a requested item. Please resolve these before approval: "
                + ", ".join(str(item.get("name") or item.get("query") or "requested item") for item in unresolved)
            )
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=final_text,
                interactive_actions=actions,
                conversation_state=conv_state,
            )
        try:
            reviewed_cart = await engine.commerce.get_cart()
        except Exception:
            reviewed_cart = None
        approved_address = engine._customer_address.get(customer_id) or (
            reviewed_cart.address_id if reviewed_cart else None
        )
        if reviewed_cart and not reviewed_cart.address_id and approved_address:
            reviewed_cart.address_id = approved_address

        approval_ok = bool(
            reviewed_cart
            and approved_address
            and engine._record_pending_approval(customer_id, reviewed_cart, approved_address)
        )

        if not approval_ok:
            engine.get_session(customer_id).pending_approval = None
            actions = [action for action in actions if action.id != "confirm_order"]
            if user_confirmed:
                conv_state = "NEEDS_DECISION"
                final_text = "I couldn't verify the complete basket and delivery address. Please review them before ordering."
            else:
                actions = [
                    InteractiveAction(action_type="button", id="proceed_checkout", title="Proceed to Checkout"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
        else:
            receipt = format_cart_receipt(
                reviewed_cart, engine._customer_address_label.get(customer_id) or approved_address
            )
            basket_pattern = r"🛒\s*\*?Your Basket.*"
            if re.search(basket_pattern, final_text, flags=re.DOTALL | re.IGNORECASE):
                intro = re.sub(basket_pattern, "", final_text, flags=re.DOTALL | re.IGNORECASE).strip()
                intro = re.sub(r"👉\s*Reply\s*\*?Confirm\*?.*", "", intro, flags=re.IGNORECASE).strip()
                final_text = f"{intro}\n\n{receipt}" if intro else receipt
            elif final_text and final_text.strip():
                clean_intro = re.sub(r"👉\s*Reply\s*\*?Confirm\*?.*", "", final_text, flags=re.IGNORECASE).strip()
                final_text = f"{clean_intro}\n\n{receipt}" if clean_intro else receipt
            else:
                final_text = receipt
            out_order_total = reviewed_cart.grand_total
            conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
    elif not checkout_executed:
        engine.get_session(customer_id).pending_approval = None

    if (
        last_cart_receipt
        and not session.unresolved_items
        and not pending_request_needs_retry
        and not search_failed_items
    ):
        session.pending_request_text = None

    final_text = _ensure_english_only(final_text)

    if history and history[-1].get("role") == "user":
        history.append({
            "role": "model",
            "parts": [{"text": final_text or "How can I help with your groceries today?"}],
            "recorded_at": time.time(),
        })
    engine._prune_history(customer_id)

    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=final_text or "How can I help with your groceries today?",
        interactive_actions=actions,
        requires_confirmation=bool(actions),
        conversation_state=conv_state,
        order_id=out_order_id,
        order_total=out_order_total,
        payment_bridge_url=out_bridge_url,
    )
