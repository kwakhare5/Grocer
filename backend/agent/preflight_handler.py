"""Preflight message processing: callbacks, fast paths, cart sync, address resolution."""
from __future__ import annotations

import logging
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from backend.agent import confirmation_check
from backend.agent.address_resolver import (
    match_explicit_address,
    match_pending_address_choice,
)
from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.drift_guard import check_cart_drift
from backend.agent.formatters import format_cart_receipt
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


async def execute_preflight(
    engine: Any, message: NormalizedIncomingMessage, customer_id: str
) -> PreflightResult:
    """Execute pre-turn validation, fast paths, cart inspection, and address resolution."""
    history = engine.get_history(customer_id)
    session = engine.get_session(customer_id)

    is_clear_confirm_tap = (
        message.interactive_id == "clear_cart_confirm"
        or (message.interactive_id is not None and message.interactive_id.startswith("clear_cart_confirm:"))
    )
    if not is_clear_confirm_tap:
        session.pending_cart_clear = None

    incoming_text = message.text.strip()
    planning_request_text = incoming_text
    action_map = {
        "proceed_checkout": "Proceed to checkout and review my order.",
        "modify_cart": "I would like to change something in my cart.",
        "start_fresh": "Please clear my cart and start fresh.",
        "clear_cart": "Please clear my cart and start fresh.",
    }
    if message.interactive_id in action_map:
        incoming_text = action_map[message.interactive_id]

    current_time = time.time()
    last_seen = engine._last_interaction_time.get(customer_id)
    engine._last_interaction_time[customer_id] = current_time
    is_inactive_session = last_seen is not None and (current_time - last_seen) > 1800
    if is_inactive_session:
        engine._order_address_confirmed.pop(customer_id, None)
        engine._awaiting_address_choice.pop(customer_id, None)
        engine._customer_address.pop(customer_id, None)
        session.pending_approval = None
        session.selected_payment_id = None

    budget_cap = await engine._read_budget_cap(incoming_text)
    if budget_cap is not None:
        session.budget_inr = float(budget_cap)
        logger.info("Captured whole-basket budget cap: ₹%.2f for %s", budget_cap, customer_id)

    norm_text = incoming_text.casefold().strip("!.? \t\n")

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

    if is_inactive_session and (not current_cart or not current_cart.items):
        history = []
        engine._history[customer_id] = history

    approved_address = engine._customer_address.get(customer_id) or (
        current_cart.address_id if current_cart else ""
    ) or ""
    if current_cart and not current_cart.address_id and approved_address:
        current_cart.address_id = approved_address
    observed_fingerprint = cart_fingerprint(current_cart, approved_address) if current_cart else None

    if session.pending_approval is not None:
        fingerprint_valid = (
            bool(session.known_cart_fingerprint)
            and observed_fingerprint is not None
            and observed_fingerprint == session.known_cart_fingerprint
            and observed_fingerprint == session.pending_approval.fingerprint
        )
        if not fingerprint_valid:
            if not session.known_cart_fingerprint:
                session.external_cart_pending = True
            session.pending_approval = None
            session.selected_payment_id = None

    is_clear_confirm_tap = (
        message.interactive_id == "clear_cart_confirm"
        or (message.interactive_id is not None and message.interactive_id.startswith("clear_cart_confirm:"))
    )
    if is_clear_confirm_tap:
        incoming_token = (
            message.interactive_id.removeprefix("clear_cart_confirm:")
            if message.interactive_id.startswith("clear_cart_confirm:")
            else ""
        )
        clear_approval = session.pending_cart_clear
        is_token_valid = (
            bool(incoming_token)
            and clear_approval is not None
            and clear_approval.token == incoming_token
            and clear_approval.expires_at > current_time
        )
        fingerprint_matches = (
            is_token_valid
            and observed_fingerprint is not None
            and clear_approval is not None
            and clear_approval.fingerprint == observed_fingerprint
        )
        if fingerprint_matches:
            try:
                clear_res = await engine.tools.clear_cart()
                verified_cart = await engine.commerce.get_cart() if clear_res.get("success") else None
            except Exception as exc:
                logger.warning("Clear cart failed: %s", exc)
                clear_res = {"success": False}
                verified_cart = None

            if not clear_res.get("success") or verified_cart is None or verified_cart.items:
                return PreflightResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text="I couldn't verify that your basket is empty. Please check it before trying again.",
                        conversation_state="FAILED",
                    ),
                    current_cart=verified_cart or current_cart,
                )

            session.clear_all()
            session.unresolved_items.clear()
            session.known_cart_fingerprint = None
            session.external_cart_pending = False
            session.budget_inr = None
            session.pending_cart_clear = None
            session.pending_approval = None
            engine.reset_customer_order_address(customer_id)
            engine._history.pop(customer_id, None)
            if getattr(engine, "attempt_store", None):
                try:
                    await engine.attempt_store.clear_unresolved_hold(customer_id, commerce=engine.commerce)
                except Exception as exc:
                    logger.warning("Clear hold failed: %s", exc)

            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="🗑️ *Basket Cleared!*\n\nYour basket is now completely empty. What groceries can I get for you today?",
                    conversation_state="READY",
                ),
                current_cart=verified_cart,
            )
        else:
            session.pending_cart_clear = None
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="Your basket changed or the request expired. Please review your basket before trying again.",
                    conversation_state="NEEDS_DECISION",
                ),
                current_cart=current_cart,
            )

    is_awaiting_checkout = (
        session.pending_approval is not None
        and session.pending_approval.expires_at > current_time
    )
    is_confirm_tap = (
        message.interactive_id == "confirm_order"
        or (message.interactive_id is not None and message.interactive_id.startswith("confirm_order:"))
    )
    user_confirmed = False

    if is_confirm_tap:
        incoming_token = (
            message.interactive_id.removeprefix("confirm_order:")
            if message.interactive_id.startswith("confirm_order:")
            else ""
        )
        approval = session.pending_approval
        is_token_valid = (
            bool(incoming_token)
            and approval is not None
            and approval.token == incoming_token
            and approval.expires_at > current_time
        )
        if is_token_valid:
            user_confirmed = True
        else:
            try:
                current_cart = await engine.commerce.get_cart()
            except Exception:
                pass
            approved_address = engine._customer_address.get(customer_id) or (
                current_cart.address_id if current_cart else ""
            ) or ""
            if current_cart and not current_cart.address_id and approved_address:
                current_cart.address_id = approved_address
            approval_ok = bool(
                current_cart
                and approved_address
                and engine._record_pending_approval(customer_id, current_cart, approved_address)
            )
            if approval_ok:
                new_token = session.pending_approval.token
                receipt = format_cart_receipt(
                    current_cart, engine._customer_address_label.get(customer_id) or approved_address
                )
                return PreflightResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text=(
                            "Your previous order confirmation expired or the basket changed. "
                            "Please review your basket and confirm:\n\n"
                            f"{receipt}"
                        ),
                        interactive_actions=[
                            InteractiveAction(action_type="button", id=f"confirm_order:{new_token}", title="Confirm Order"),
                            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                        ],
                        requires_confirmation=True,
                        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                        order_total=current_cart.grand_total,
                    ),
                    current_cart=current_cart,
                    address_id=approved_address,
                )
            else:
                session.pending_approval = None
                return PreflightResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text="Your previous order confirmation expired or the basket changed. Please review your basket before ordering.",
                        conversation_state="NEEDS_DECISION",
                    ),
                    current_cart=current_cart,
                )
    elif is_awaiting_checkout and not message.interactive_id:
        short_context = (
            format_cart_receipt(current_cart, session.address_label or "Home", allow_checkout_prompt=False)
            if current_cart
            else ""
        )
        user_confirmed = await confirmation_check.is_confirmed(
            engine.gemini,
            incoming_text,
            context=short_context,
        )

    drift_resp = await check_cart_drift(
        session=session,
        current_cart=current_cart,
        norm_text=norm_text,
        user_confirmed=user_confirmed,
        message=message,
        confirmation_check=confirmation_check,
        client=engine.gemini,
    )
    if drift_resp is not None:
        return PreflightResult(early_response=drift_resp)

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
        if not engine._record_pending_approval(customer_id, current_cart, approved_address):
            return PreflightResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't verify the current basket and delivery address. Please review them before ordering.",
                    conversation_state="NEEDS_DECISION",
                )
            )
        token = session.pending_approval.token
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=(
                    format_cart_receipt(current_cart, session.address_label or approved_address)
                    + f"\n\nPayment: {selected.label}. Do you want to place this order to this address?"
                ),
                interactive_actions=[
                    InteractiveAction(action_type="button", id=f"confirm_order:{token}", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )
        )

    if message.interactive_id == "accept_partial_basket":
        if not session.budget_blocked_items or not current_cart:
            return PreflightResult(early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="I couldn't verify a partial basket to keep. Please ask me to show your cart.",
                conversation_state="NEEDS_DECISION",
            ))
        approved_address = session.address_id or current_cart.address_id or ""
        if not engine._record_pending_approval(customer_id, current_cart, approved_address):
            return PreflightResult(early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="I couldn't verify the current basket and delivery address. Please review the basket again.",
                conversation_state="NEEDS_DECISION",
            ))
        session.budget_blocked_items.clear()
        token = session.pending_approval.token
        return PreflightResult(early_response=NormalizedOutgoingResponse(
            recipient_id=message.sender_id, channel=message.channel,
            text="Okay, I'll keep only these items. Please review the basket before placing an order.\n\n"
            + format_cart_receipt(current_cart, session.address_label or "Home"),
            interactive_actions=[
                InteractiveAction(action_type="button", id=f"confirm_order:{token}", title="Confirm Order"),
                InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            ],
            conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
            order_total=current_cart.grand_total,
        ))

    if session.pending_variant_selection:
        session.pending_variant_selection = None
        session.pending_request_text = incoming_text

    if customer_id in engine._awaiting_address_choice:
        pending_addrs = engine._awaiting_address_choice[customer_id]
        chosen_addr = match_pending_address_choice(
            pending_addrs, norm_text, message.interactive_id
        )
        if not chosen_addr:
            return PreflightResult(early_response=engine._address_choice_response(message, pending_addrs))

        engine._awaiting_address_choice.pop(customer_id, None)
        address_id = chosen_addr["address_id"]
        engine._customer_address[customer_id] = address_id
        engine._customer_address_label[customer_id] = (
            chosen_addr.get("clean_address") or chosen_addr.get("street") or chosen_addr.get("label") or "Home"
        )
        engine._order_address_confirmed[customer_id] = True
        if session.pending_request_text:
            planning_request_text = session.pending_request_text
            incoming_text = (
                f"{session.pending_request_text}\n"
                f"Use delivery address: {engine._customer_address_label[customer_id]} (ID: {address_id})."
            )

    address_id = engine._customer_address.get(customer_id)
    if not address_id:
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

    if (
        getattr(session, "pending_clarification", False)
        and session.pending_request_text
        and not user_confirmed
    ):
        planning_request_text = f"{session.pending_request_text} ({incoming_text})"
        session.pending_request_text = None
        session.pending_clarification = False

    return PreflightResult(
        early_response=None,
        incoming_text=incoming_text,
        planning_request_text=planning_request_text,
        user_confirmed=user_confirmed,
        current_cart=current_cart,
        address_id=address_id,
    )
