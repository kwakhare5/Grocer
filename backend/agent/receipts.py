"""Interactive WhatsApp message formatting and receipt card builders."""
from __future__ import annotations

import logging
from typing import Any

from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings

logger = logging.getLogger("grocer.agent.receipts")


def build_connect_url(ticket: str, base_url: str | None = None) -> str:
    """Generate customer-scoped one-time authentication link."""
    base = (base_url or settings.CONNECT_BASE_URL or "https://grocerr.vercel.app").rstrip("/")
    return f"{base}/?connect_ticket={ticket}"


async def build_auth_expired_response(
    message: NormalizedIncomingMessage,
    base_url: str | None = None,
) -> NormalizedOutgoingResponse:
    """Generate re-connection response with a one-time login link."""
    from backend.integrations.commerce.connect_tickets import default_connect_tickets

    try:
        ticket = await default_connect_tickets.issue(message.customer_id or "")
        instructions = (
            "Your Swiggy login needs reconnecting. Open this one-time link from your WhatsApp chat:\n\n"
            f"👉 {build_connect_url(ticket, base_url)}\n\n"
            "The link expires in 10 minutes. After connecting, message me again."
        )
    except Exception:
        logger.exception("Could not issue a customer-scoped Swiggy connection link.")
        instructions = "Swiggy connection is temporarily unavailable. Please message me again shortly."

    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=instructions,
        conversation_state="AUTH_REQUIRED",
    )


def build_address_choice_response(
    message: NormalizedIncomingMessage,
    addresses: list[dict[str, Any]],
) -> NormalizedOutgoingResponse:
    """Format an interactive address selection card with quick-reply buttons."""
    lines = []
    for index, address in enumerate(addresses, 1):
        lbl = address.get("label") or f"Address {index}"
        details = address.get("clean_address") or address.get("street") or lbl
        lines.append(f"*{index}. {lbl}* — {details}")
    prompt = "📍 *Which address should I use?*\n\n" + "\n".join(lines)
    prompt += "\n\nReply with the number (e.g. 1), label (e.g. Home), or tap a button."

    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=prompt,
        interactive_actions=[
            InteractiveAction(
                action_type="button",
                id=f"addr_choice_{address.get('_choice_code') or address.get('address_id')}",
                title=f"{index}. {str(address.get('label') or f'Address {index}')}"[:20],
            )
            for index, address in enumerate(addresses[:3], 1)
        ],
        conversation_state="NEEDS_DECISION",
    )
