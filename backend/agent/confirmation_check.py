"""Async confirmation judgment using Gemini structured output."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.config import SMALL_CHECK_MODEL

logger = logging.getLogger("grocer.agent.confirmation_check")

CONFIRMATION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "confirmation": {
            "type": "STRING",
            "enum": ["yes", "no", "unclear"],
            "description": "Whether the customer confirmed this exact order.",
        },
    },
    "required": ["confirmation"],
}


async def is_confirmed(
    client_or_text: Any = None,
    text_or_context: str = "",
    context: str = "",
    *,
    client: Any = None,
) -> bool:
    """Judge if customer confirmed this exact order via small check model structured output.

    Returns True only when the model answers 'yes'. Any error or 'unclear' counts as no (False).
    """
    if isinstance(client_or_text, str):
        target_client = client
        message_text = client_or_text
        short_context = text_or_context or context
    else:
        target_client = client or client_or_text
        message_text = text_or_context
        short_context = context

    if not target_client or not getattr(target_client, "api_key", None) or not message_text.strip():
        return False

    prompt = (
        f"Customer message:\n\"{message_text.strip()}\"\n\n"
        f"Order context:\n\"{short_context.strip()}\"\n\n"
        "Did the customer explicitly confirm and approve placing this exact order? "
        "Answer with 'yes' if they explicitly approved, 'no' if they rejected or wanted changes, "
        "or 'unclear' if it is ambiguous, a question, or not an explicit confirmation."
    )

    try:
        res = await target_client.generate_structured(
            model=SMALL_CHECK_MODEL,
            prompt=prompt,
            response_schema=CONFIRMATION_SCHEMA,
        )
        if isinstance(res, dict):
            val = str(res.get("confirmation", "")).strip().casefold()
            return val == "yes"
        return False
    except Exception as exc:
        logger.warning("Confirmation check failed: %r", exc)
        return False


check_confirmation = is_confirmed
