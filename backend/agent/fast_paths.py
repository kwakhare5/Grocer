"""Deterministic 0ms fast-path responders for GROCER WhatsApp engine."""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

from backend.agent.formatters import format_cart_receipt
from backend.agent.guards import is_hesitation, is_reset_command
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.fast_paths")


async def handle_reset_fast_path(
    norm_text: str,
    message: NormalizedIncomingMessage,
    customer_id: str,
    session: Any,
    tools: Any,
    commerce: Any,
    reset_order_address_fn: Callable[[str], None],
    clear_history_fn: Callable[[str], None],
    clear_hold_fn: Optional[Callable[[str], Any]] = None,
    address_id: Optional[str] = None,
) -> Optional[NormalizedOutgoingResponse]:
    """If user issued a reset/clear basket command, propose confirmation button bound to current cart."""
    is_clear_intent = (
        is_reset_command(norm_text)
        or message.interactive_id in {"start_fresh", "clear_cart"}
    )
    if not is_clear_intent:
        return None

    try:
        current_cart = await commerce.get_cart()
    except Exception as exc:
        logger.warning("Fast-path get_cart failed: %s", exc)
        current_cart = None

    if not current_cart or not current_cart.items:
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="Your basket is already empty. What groceries would you like to add?",
            conversation_state="READY",
        )

    target_address = (
        address_id
        or getattr(session, "address_id", None)
        or (current_cart.address_id if current_cart else None)
        or ""
    )
    if current_cart and not current_cart.address_id and target_address:
        current_cart.address_id = target_address

    from backend.agent.session_manager import record_pending_cart_clear

    if not record_pending_cart_clear(session, current_cart, target_address) or not getattr(session, "pending_cart_clear", None):
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="I couldn't verify your basket right now. Please check your basket and try again.",
            conversation_state="FAILED",
        )

    token = session.pending_cart_clear.token
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text="Clear cart? This will remove all items from your basket.",
        interactive_actions=[
            InteractiveAction(action_type="button", id=f"clear_cart_confirm:{token}", title="Clear Cart"),
            InteractiveAction(action_type="button", id="modify_cart", title="Keep Cart"),
        ],
        requires_confirmation=True,
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        order_total=current_cart.grand_total,
    )


def handle_greeting_or_cancellation_fast_path(
    norm_text: str,
    message: NormalizedIncomingMessage,
    is_awaiting_address: bool,
) -> Optional[NormalizedOutgoingResponse]:
    """Return deterministic response for greetings or order cancellation queries."""
    if norm_text == "cancel order":
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=(
                "I haven't cancelled an order. If you mean your current basket, "
                "reply 'clear cart'. For an order already placed, check its status in Swiggy."
            ),
            conversation_state="NEEDS_DECISION",
        )

    return None


def handle_cart_read_fast_path(
    norm_text: str,
    message: NormalizedIncomingMessage,
    current_cart: Optional[CommerceCart],
    address_label: Optional[str] = None,
) -> Optional[NormalizedOutgoingResponse]:
    """Return deterministic response when user asks to view or check cart."""
    cart_read = (
        norm_text in {"cart", "basket", "my cart", "my basket", "view cart", "show cart", "check cart", "view basket", "show basket"}
        or bool(re.search(r"^(?:please\s+)?(?:show|view|see|check|display)\s+(?:my\s+|the\s+)?(?:cart|basket)$", norm_text))
        or bool(re.search(r"^what(?:'s|\s+is)\s+(?:in\s+)?(?:my\s+|the\s+)?(?:cart|basket)\??$", norm_text))
    )
    if not cart_read:
        return None

    if current_cart is None:
        text, state = "I couldn't read your current basket. Please try again shortly.", "FAILED"
    elif not current_cart.items:
        text, state = "Your basket is empty. What groceries would you like to add?", "READY"
    else:
        text = format_cart_receipt(current_cart, address_label or "Saved Address", allow_checkout_prompt=False)
        state = "NEEDS_DECISION"

    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=text,
        conversation_state=state,
    )


def handle_hesitation_fast_path(
    norm_text: str,
    message: NormalizedIncomingMessage,
    current_cart: Optional[CommerceCart],
    address_label: Optional[str] = None,
) -> Optional[NormalizedOutgoingResponse]:
    """Return hold confirmation when active basket exists and user hesitates."""
    if not (is_hesitation(norm_text) and current_cart and current_cart.items):
        return None

    loc = address_label or "Home"
    receipt = format_cart_receipt(current_cart, delivery_location=loc)
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=(
            "No problem, I've kept your basket on hold! 🛒\n\n"
            "Your groceries are still saved. Whenever you're ready, let me know if you want to add/remove items, switch delivery address, or clear your basket.\n\n"
            f"{receipt}"
        ),
        interactive_actions=[
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            InteractiveAction(action_type="button", id="start_fresh", title="Clear Cart"),
        ],
        requires_confirmation=True,
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        order_total=current_cart.grand_total,
    )
