"""Read whole-basket spending cap in rupees using Gemini."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agent.gemini import GeminiClient

logger = logging.getLogger(__name__)


async def read_budget_cap(text: str, client: GeminiClient) -> float | None:
    """Read whole-basket spending cap in rupees using Gemini flash-lite structured output."""
    try:
        prompt = (
            f"Customer message:\n\"{text}\"\n\n"
            "Does this message state a maximum the customer wants to spend on the whole order, and if so, what is the amount in rupees?"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "has_whole_order_cap": {
                    "type": "BOOLEAN",
                    "description": "Whether the message states a maximum the customer wants to spend on the whole order.",
                },
                "amount": {
                    "type": "NUMBER",
                    "nullable": True,
                    "description": "The maximum amount in rupees.",
                },
            },
            "required": ["has_whole_order_cap"],
        }
        res = await client.generate_structured(
            model="gemini-3.5-flash-lite",
            prompt=prompt,
            response_schema=schema,
        )
        if not isinstance(res, dict):
            return None
        has_cap = res.get("has_whole_order_cap")
        amount = res.get("amount")
        if has_cap is True and isinstance(amount, (int, float)) and math.isfinite(amount) and amount > 0:
            return float(amount)
        return None
    except Exception as exc:
        logger.warning("Error reading budget cap: %r", exc)
        return None
