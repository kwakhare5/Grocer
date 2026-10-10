"""Deterministic 0ms fast-path responders for GROCER WhatsApp engine."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from backend.agent.guards import is_reset_command
from backend.channels.models import NormalizedIncomingMessage, NormalizedOutgoingResponse

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
) -> Optional[NormalizedOutgoingResponse]:
    """If user issued a reset/clear basket command, execute 0ms deterministic wipe."""
    if not is_reset_command(norm_text):
        return None

    try:
        clear_result = await tools.clear_cart()
        verified_cart = await commerce.get_cart() if clear_result.get("success") else None
    except Exception as exc:
        logger.warning("Fast-path clear_cart failed: %s", exc)
        clear_result = {"success": False}
        verified_cart = None

    if not clear_result.get("success") or verified_cart is None or verified_cart.items:
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="I couldn't verify that your basket is empty. Please check it before trying again.",
            conversation_state="FAILED",
        )

    clear_history_fn(customer_id)
    session.clear_all()
    reset_order_address_fn(customer_id)
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text="🗑️ *Basket Cleared!*\n\nYour basket is now completely empty. What groceries can I get for you today?",
        conversation_state="READY",
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

    if norm_text in {"hi", "hello", "hey", "namaste"} and not is_awaiting_address:
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="Hi! Tell me what grocery items you need, or ask to see your basket.",
            conversation_state="NEEDS_DECISION",
        )

    return None
