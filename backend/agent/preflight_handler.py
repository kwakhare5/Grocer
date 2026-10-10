"""Preflight message processing: callbacks, fast paths, cart sync, address resolution."""
from __future__ import annotations

import logging
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from backend.agent.address_resolver import (
    match_explicit_address,
    match_pending_address_choice,
)
from backend.agent.approval import cart_fingerprint
from backend.agent.budget import extract_ingredient_budget, extract_total_budget
from backend.agent.fast_paths import (
    handle_greeting_or_cancellation_fast_path,
    handle_reset_fast_path,
)
from backend.agent.formatters import clean_address, format_cart_receipt
from backend.agent.guards import is_explicit_confirmation, is_hesitation
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.exceptions import ProviderAuthError, ProviderRateLimitedError
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.preflight_handler")


@dataclass
class PreflightResult:
    early_response: Optional[NormalizedOutgoingResponse] = None
    incoming_text: str = ""
    planning_request_text: str = ""
    user_confirmed: bool = False
    current_cart: Optional[CommerceCart] = None
    address_id: Optional[str] = None
    is_retry_command: bool = False


async def execute_preflight(
    engine: Any, message: NormalizedIncomingMessage, customer_id: str
) -> PreflightResult:
    """Execute pre-turn validation, fast paths, cart inspection, and address resolution."""
    history = engine.get_history(customer_id)
    session = engine.get_session(customer_id)

    incoming_text = message.text.strip()
    planning_request_text = incoming_text
    if message.interactive_id:
        if message.interactive_id == "confirm_order":
            incoming_text = "Yes, please confirm and place the order now."
        elif message.interactive_id == "proceed_checkout":
            incoming_text = "Proceed to checkout and review my order."
        elif message.interactive_id == "modify_cart":
            incoming_text = "I would like to change something in my cart."
        elif message.interactive_id in ("start_fresh", "clear_cart"):
            incoming_text = "Please clear my cart and start fresh."

    ingredient_budget = extract_ingredient_budget(incoming_text)
    budget = extract_total_budget(incoming_text) if ingredient_budget is None else None
    if ingredient_budget is not None:
        session.ingredient_budget_inr, session.ingredient_extras_text = ingredient_budget
        session.ingredient_spin_ids.clear()
        session.budget_inr = None
    elif budget is not None:
        session.budget_inr = budget
        session.ingredient_budget_inr = None
        session.ingredient_extras_text = None
        session.ingredient_spin_ids.clear()
        logger.info("Captured customer budget constraint: ₹%.2f for %s", budget, customer_id)

    norm_text = incoming_text.casefold().strip("!.? \t\n")
    is_retry_command = norm_text in {"try again", "retry"}
    if is_retry_command and session.pending_request_text:
        planning_request_text = session.pending_request_text
    if (
        session.pending_request_text
        and history
        and history[-1].get("clarification_pending")
        and not message.interactive_id
        and not re.match(r"(?i)^(?:add|buy|get|need|show|clear|cancel|start|remove)\b", norm_text)
    ):
        planning_request_text = f"{session.pending_request_text}\nCustomer clarification: {incoming_text}"

    if engine.replenishment_store is not None:
        try:
            reminder_reply = await engine.replenishment_store.reply(
                customer_id, incoming_text, engine.commerce
            )
        except ProviderAuthError:
            auth_resp = await engine._auth_expired_response(message)
            return PreflightResult(early_response=auth_resp)
        if reminder_reply is not None:
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text=reminder_reply,
                    conversation_state="NEEDS_DECISION",
                )
            )

    greet_or_cancel_resp = handle_greeting_or_cancellation_fast_path(
        norm_text=norm_text,
        message=message,
        is_awaiting_address=customer_id in engine._awaiting_address_choice,
    )
    if greet_or_cancel_resp is not None:
        return PreflightResult(early_response=greet_or_cancel_resp)

    # Fast-path: Explicit address change request
    if (
        norm_text in {"change address", "switch address", "different address", "update address"}
        or "change address" in norm_text
    ):
        try:
            addr_res = await engine.tools.get_saved_addresses(customer_id)
            if addr_res.get("success") and addr_res.get("addresses"):
                addrs = addr_res["addresses"]
                choices = [
                    {**a, "_choice_code": secrets.token_hex(3), "_choice_index": str(idx)}
                    for idx, a in enumerate(addrs, 1)
                ]
                engine._awaiting_address_choice[customer_id] = choices
                return PreflightResult(early_response=engine._address_choice_response(message, choices))
        except Exception:
            pass

    # Fast-path 1: Reset / Clear basket command
    reset_resp = await handle_reset_fast_path(
        norm_text=norm_text,
        message=message,
        customer_id=customer_id,
        session=session,
        tools=engine.tools,
        commerce=engine.commerce,
        reset_order_address_fn=engine.reset_customer_order_address,
        clear_history_fn=lambda cid: engine._history.pop(cid, None),
    )
    if reset_resp is not None:
        return PreflightResult(early_response=reset_resp)

    user_confirmed = message.interactive_id == "confirm_order" or is_explicit_confirmation(incoming_text)

    current_cart: Optional[CommerceCart] = None
    try:
        current_cart = await engine.commerce.get_cart()
    except ProviderAuthError:
        auth_resp = await engine._auth_expired_response(message)
        return PreflightResult(early_response=auth_resp)
    except ProviderRateLimitedError as exc:
        wait_text = (
            f"Please wait {exc.retry_after_seconds} seconds and try again."
            if exc.retry_after_seconds is not None
            else "Please wait and try again later."
        )
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=f"Swiggy is limiting requests right now. {wait_text}",
                conversation_state="RECOVERING",
            )
        )
    except Exception as exc:
        logger.debug("Failed to fetch initial cart for customer=%s: %s", customer_id, exc)

    if session.known_cart_fingerprint:
        observed_fingerprint = (
            cart_fingerprint(current_cart, current_cart.address_id or session.address_id or "")
            if current_cart
            else None
        )
        if observed_fingerprint != session.known_cart_fingerprint:
            session.external_cart_pending = True
            session.pending_approval = None
            session.selected_payment_id = None
    if session.external_cart_pending:
        if norm_text == "use changes" and current_cart:
            observed_fingerprint = cart_fingerprint(
                current_cart, current_cart.address_id or session.address_id or ""
            )
            if observed_fingerprint:
                session.known_cart_fingerprint = observed_fingerprint
                session.external_cart_pending = False
                return PreflightResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text="I’ve included the Swiggy cart changes. Please tell me what to change next.\n\n"
                        + format_cart_receipt(
                            current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
                        ),
                        conversation_state="NEEDS_DECISION",
                    )
                )
        receipt = (
            format_cart_receipt(
                current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
            )
            if current_cart
            else "I couldn't read the current Swiggy basket."
        )
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="The Swiggy cart changed outside this chat. Reply *use changes* to include it, "
                "or tell me how you want to restore the basket.\n\n"
                + receipt,
                conversation_state="NEEDS_DECISION",
            )
        )

    cart_read = norm_text in {"cart", "basket"} or bool(
        re.fullmatch(
            r"(?:(?:please|can you|could you)\s+)?(?:show|view|see|list)(?:\s+me)?\s+"
            r"(?:(?:my|the|your|current)\s+)?(?:cart|basket)(?:\s+(?:right\s+)?now)?"
            r"|what(?:'s| is)\s+in\s+(?:my|the|your)\s+(?:cart|basket)(?:\s+right\s+now)?",
            norm_text,
        )
    )
    if cart_read:
        if current_cart is None:
            text = "I couldn't read your current basket. Please try again shortly."
            state = "FAILED"
        elif not current_cart.items:
            text = "Your basket is empty. What groceries would you like to add?"
            state = "READY"
        else:
            text = format_cart_receipt(
                current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
            )
            state = "NEEDS_DECISION"
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=text,
                conversation_state=state,
            )
        )

    if message.interactive_id and message.interactive_id.startswith("payment_choice:"):
        selected_id = message.interactive_id.removeprefix("payment_choice:")
        approval = session.pending_approval
        approved_address = session.address_id or (current_cart.address_id if current_cart else "") or ""
        if (
            not approval
            or approval.expires_at <= time.time()
            or not current_cart
            or cart_fingerprint(current_cart, approved_address) != approval.fingerprint
        ):
            session.pending_approval = None
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="Your basket changed or the review expired. Please review it again before choosing payment.",
                    conversation_state="NEEDS_DECISION",
                )
            )
        try:
            options = await engine.commerce.get_payment_options(current_cart.cart_id, approved_address)
        except Exception:
            options = []
        selected = next(
            (
                option
                for option in options
                if option.id == selected_id
                and option.is_available
                and (
                    (option.method == "UPI" and option.kind == "intent")
                    or option.method in ("Cash", "COD", "SwiggyPay")
                )
            ),
            None,
        )
        if selected is None:
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="That payment option is no longer available. Please ask me to show the current payment options.",
                    conversation_state="NEEDS_DECISION",
                )
            )
        session.selected_payment_id = selected.id
        session.selected_payment_kind = selected.kind
        session.selected_payment_method = selected.method
        session.selected_payment_label = selected.label
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=(
                    format_cart_receipt(current_cart, session.address_label or approved_address)
                    + f"\n\nPayment: {selected.label}. Do you want to place this order to this address?"
                ),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )
        )

    if message.interactive_id == "accept_partial_basket" or norm_text in {
        "keep the partial basket",
        "keep these items",
        "accept partial basket",
    }:
        if not session.budget_blocked_items or not current_cart:
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't verify a partial basket to keep. Please ask me to show your cart.",
                    conversation_state="NEEDS_DECISION",
                )
            )
        approved_address = session.address_id or current_cart.address_id or ""
        if not engine._record_pending_approval(customer_id, current_cart, approved_address):
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't verify the current basket and delivery address. Please review the basket again.",
                    conversation_state="NEEDS_DECISION",
                )
            )
        session.budget_blocked_items.clear()
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="Okay, I'll keep only these items. Please review the basket before placing an order.\n\n"
                + format_cart_receipt(current_cart, session.address_label or "Home"),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )
        )

    # Fast-path 2: Hesitation guard when active basket exists
    if is_hesitation(norm_text) and current_cart and current_cart.items:
        loc = engine._customer_address_label.get(customer_id) or "Home"
        receipt = format_cart_receipt(current_cart, delivery_location=loc)
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=(
                    "No problem, I've kept your basket on hold! 🛒\n\n"
                    "Your groceries are still saved. Whenever you're ready, let me know if you want to add/remove items, switch delivery address, or clear your basket.\n\n"
                    f"{receipt}"
                ),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                    InteractiveAction(action_type="button", id="start_fresh", title="Clear Cart"),
                ],
                requires_confirmation=True,
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )
        )

    current_time = time.time()
    last_seen = engine._last_interaction_time.get(customer_id)
    engine._last_interaction_time[customer_id] = current_time
    if last_seen is not None and (current_time - last_seen) > 1800:
        engine._order_address_confirmed.pop(customer_id, None)
        engine._awaiting_address_choice.pop(customer_id, None)
        engine._customer_address.pop(customer_id, None)
        if not current_cart or not current_cart.items:
            history = []
            engine._history[customer_id] = history

    if customer_id in engine._awaiting_address_choice:
        pending_addrs = engine._awaiting_address_choice[customer_id]
        chosen_addr = match_pending_address_choice(
            pending_addrs, norm_text, message.interactive_id
        )
        if not chosen_addr:
            return PreflightResult(
                early_response=engine._address_choice_response(message, pending_addrs)
            )

        engine._awaiting_address_choice.pop(customer_id, None)
        address_id = chosen_addr["address_id"]
        engine._customer_address[customer_id] = address_id
        engine._customer_address_label[customer_id] = (
            chosen_addr.get("clean_address")
            or chosen_addr.get("street")
            or chosen_addr.get("label")
            or "Home"
        )
        engine._order_address_confirmed[customer_id] = True
        if session.pending_request_text:
            planning_request_text = session.pending_request_text
            incoming_text = (
                f"{session.pending_request_text}\n"
                f"Use delivery address: {engine._customer_address_label[customer_id]} (ID: {address_id})."
            )

    address_id = engine._customer_address.get(customer_id)
    has_explicit_address_intent = bool(re.search(
        r"\b(?:deliver|send|ship|bring|drop|switch|change|use)\b.*?\b(?:to|at|address|location|destination)\b"
        r"|\b(?:deliver|send|ship|switch|change)\s+to\b"
        r"|\b(?:address|location|destination)\b",
        norm_text,
    ))
    if not address_id or has_explicit_address_intent:
        try:
            addr_res = await engine.tools.get_saved_addresses(customer_id)
            if addr_res.get("error") == "AUTH_EXPIRED":
                auth_resp = await engine._auth_expired_response(message)
                return PreflightResult(early_response=auth_resp)
            if addr_res.get("success") and addr_res.get("addresses"):
                addresses = addr_res["addresses"]
                matched_explicit = match_explicit_address(addresses, norm_text)
                if matched_explicit:
                    chosen_addr = matched_explicit
                    address_id = chosen_addr["address_id"]
                    engine._customer_address[customer_id] = address_id
                    engine._customer_address_label[customer_id] = (
                        chosen_addr.get("clean_address") or chosen_addr.get("label") or "Home"
                    )
                    engine._order_address_confirmed[customer_id] = True
                elif (
                    len(addresses) > 1
                    and not (current_cart and current_cart.items)
                    and not any(k in norm_text for k in ("address", "saved address", "track", "status"))
                ):
                    session.pending_request_text = incoming_text
                    choices = [
                        {**a, "_choice_code": secrets.token_hex(3), "_choice_index": str(idx)}
                        for idx, a in enumerate(addresses, 1)
                    ]
                    engine._awaiting_address_choice[customer_id] = choices
                    return PreflightResult(
                        early_response=engine._address_choice_response(message, choices)
                    )
                elif not address_id:
                    chosen_addr = next((a for a in addresses if a.get("is_default")), addresses[0])
                    address_id = chosen_addr["address_id"]
                    engine._customer_address[customer_id] = address_id
                    engine._customer_address_label[customer_id] = (
                        chosen_addr.get("clean_address") or chosen_addr.get("label") or "Home"
                    )
                    engine._order_address_confirmed[customer_id] = True
        except Exception:
            pass

    if session.pending_request_text and is_retry_command:
        planning_request_text = session.pending_request_text
        addr_lbl = engine._customer_address_label.get(customer_id, "selected address")
        addr_val = address_id or engine._customer_address.get(customer_id, "")
        incoming_text = f"{session.pending_request_text}\nUse delivery address: {addr_lbl} (ID: {addr_val})."

    return PreflightResult(
        early_response=None,
        incoming_text=incoming_text,
        planning_request_text=planning_request_text,
        user_confirmed=user_confirmed,
        current_cart=current_cart,
        address_id=address_id,
        is_retry_command=is_retry_command,
    )
