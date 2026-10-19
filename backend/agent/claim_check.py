"""Async reply claim judgment using Gemini structured output."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("grocer.agent.claim_check")

CLAIM_CHECK_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "claims_cart_or_order": {
            "type": "STRING",
            "enum": ["yes", "no", "unclear"],
            "description": "Whether this reply states or implies a cart item, price, total, delivery fee, or order status.",
        },
    },
    "required": ["claims_cart_or_order"],
}

CLAIM_CHECK_PROMPT = (
    "Assistant reply:\n\"{reply_text}\"\n\n"
    "Does this reply state or imply a cart item, price, total, delivery fee or order status? "
    "Answer with 'yes', 'no', or 'unclear'."
)


async def check_reply_claims(
    client_or_text: Any = None,
    text: str = "",
    *,
    client: Any = None,
    timeout: float = 5.0,
) -> str:
    """Judge if an assistant reply states or implies cart items, prices, totals, fees, or order status.

    Returns 'yes', 'no', or 'unclear'.
    Any error or timeout returns 'unclear'.
    """
    if isinstance(client_or_text, str):
        target_client = client
        reply_text = client_or_text
    else:
        target_client = client or client_or_text
        reply_text = text

    if not reply_text or not reply_text.strip():
        return "no"

    if not target_client or not getattr(target_client, "api_key", None):
        return "unclear"

    prompt = CLAIM_CHECK_PROMPT.format(reply_text=reply_text.strip())

    try:
        async with asyncio.timeout(timeout):
            res = await target_client.generate_structured(
                model="gemini-3.5-flash-lite",
                prompt=prompt,
                response_schema=CLAIM_CHECK_SCHEMA,
            )
        if isinstance(res, dict):
            val = str(res.get("claims_cart_or_order", "")).strip().casefold()
            if val in {"yes", "no", "unclear"}:
                return val
        return "unclear"
    except Exception as exc:
        logger.warning("Claim check failed: %r", exc)
        return "unclear"


async def is_unclaimed_chat(
    client_or_text: Any = None,
    text: str = "",
    *,
    client: Any = None,
    timeout: float = 5.0,
) -> bool:
    """Return True only if the check explicitly answers 'no' (pure conversational chat)."""
    val = await check_reply_claims(client_or_text, text, client=client, timeout=timeout)
    return val == "no"
