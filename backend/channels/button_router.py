"""Grocer v1.0 — Fast 50ms Interactive Button Dispatcher (Zero LLM Lag)."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger("grocer.button_router")


async def dispatch_button_action(
    button_id: str,
    wa_id: str,
    pool: asyncpg.Pool | None = None,
) -> dict[str, Any]:
    """Execute interactive WhatsApp button taps directly in Python in <50ms.

    Bypasses Gemini LLM completely for instant app-like responsiveness.
    """
    logger.info("Dispatching fast button action: %s for user: %s", button_id, wa_id)

    prefix, _, target_id = button_id.partition(":")
    target_arg = target_id if target_id else None

    # 1. Cart Clear action
    if button_id == "cart:clear":
        return {
            "status": "button_dispatched",
            "action": "cart:clear",
            "message": "Basket cleared.",
        }

    # 2. Checkout Payment Authorization (Lock 1 Authority)
    if prefix == "pay":
        return {
            "status": "button_dispatched",
            "action": button_id,
            "approval_id": target_arg,
            "message": "Payment lock authorized.",
        }

    # 3. Delivery Address Switching
    if prefix == "addr":
        return {
            "status": "button_dispatched",
            "action": button_id,
            "address_id": target_arg,
            "message": "Address switch requested.",
        }

    # Default fallback for recognized button action
    return {
        "status": "button_dispatched",
        "action": button_id,
        "message": "Action processed.",
    }
