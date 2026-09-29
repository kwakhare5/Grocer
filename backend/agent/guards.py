"""Deterministic safety guards, phrase matchers, and receipt post-processing for GROCER."""
from __future__ import annotations

import re
from typing import Optional

_ORDER_SUCCESS_PATTERNS = (
    re.compile(
        r"(?i)(?:(?:\b(?:your|the|this)\s+)?(?<!no )(?<!not )(?<!n\'t )\b(?:order|groceries|items|basket|delivery|everything|checkout|purchase)(?:\s+#?[\w-]+)?\s+)"
        r"(?:(?:has|have|is|are|was|were|got)\s+(?:now\s+|just\s+|already\s+)?(?:been\s+)?(?:successfully\s+)?)?"
        r"(?:placed|confirmed|booked|completed|complete|accepted|received|submitted|processed|dispatched|delivered|fulfilled|shipped|sent|ordered|checked\s+out|out\s+for\s+delivery)\b"
    ),
    re.compile(
        r"(?i)\b(?<!not )(?<!n\'t )(?<!never )"
        r"(?:placed|confirmed|booked|completed|submitted|processed|dispatched|delivered|fulfilled|shipped|sent|ordered|accepted)"
        r"\s+(?:an?\s+(?:grocery\s+)?order(?:\s+(?:for\s+you|with\s+\w+))?|"
        r"(?:your|the|this)\s+(?:grocery\s+)?(?:order|groceries|items|basket|purchase)|"
        r"everything)\b"
    ),
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:your|the|this)?\s*(?:order|purchase)\s+"
        r"(?:(?:has|have|is|was)\s+)?(?:successful|succeeded)\b"
    ),
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:your|the|this)?\s*(?:order|payment|purchase)\s+"
        r"(?:(?:has|have)\s+)?(?:went|gone)\s+through\b"
    ),
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:(?:your|the|this)?\s*(?:order|groceries|items|delivery|basket|delivery partner)\s+"
        r"(?:are|is|will\s+be|now)\s+"
        r"(?:(?:on\s+(?:the|its|their)\s+way)|(?:en\s+route)|(?:heading\s+your\s+way)|(?:headed\s+your\s+way)|"
        r"(?:out\s+for\s+delivery)|(?:being\s+(?:delivered|prepared|packed))|(?:arriving\s+(?:soon|shortly|\w+)))|"
        r"Swiggy\s+is\s+preparing\s+your\s+order)\b"
    ),
    re.compile(
        r"(?i)\b(?<!not )(?<!n\'t )(?<!never )"
        r"(?:successfully\s+(?:placed|ordered|confirmed|booked|completed|processed|submitted|dispatched|delivered|fulfilled|shipped|sent)|"
        r"(?:placed|ordered|confirmed|booked|completed|processed|submitted|dispatched|delivered|fulfilled|shipped|sent)\s+successfully)\b"
    ),
)

_RESET_COMMANDS = {
    "start over",
    "clear cart",
    "clear basket",
    "empty cart",
    "empty basket",
    "reset",
    "cancel order",
    "delete cart",
}

_HESITATION_PHRASES = {
    "no",
    "nope",
    "nah",
    "wait",
    "hold on",
    "not yet",
    "no wait",
    "wait a minute",
    "hold",
    "stop",
    "dont order",
    "don't order",
    "do not order",
    "not now",
    "cancel",
}

_CONFIRMATION_PHRASES = {
    "confirm",
    "confirm order",
    "yes",
    "yes please",
    "place order",
    "place the order",
    "place this order",
    "proceed",
    "checkout",
    "pay",
    "book it",
    "order it",
    "order now",
    "go ahead",
    "do it",
}


def _claims_order_success(text: str) -> bool:
    """Return True if text asserts or implies that an order has been placed, confirmed, or is en route."""
    if not text or not text.strip():
        return False
    return any(pattern.search(text) is not None for pattern in _ORDER_SUCCESS_PATTERNS)


def _explains_failure(
    text: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> bool:
    """Return True if text provides an honest explanation of a failure or contains error context."""
    if not text or not text.strip():
        return False
    lowered = text.casefold()
    if error_code and error_code.casefold() in lowered:
        return True
    if error_message and error_message.casefold() in lowered:
        return True
    failure_indicators = (
        "could not",
        "couldn't",
        "cannot",
        "can't",
        "unable",
        "failed",
        "failure",
        "error",
        "sorry",
        "unfortunately",
        "out of stock",
        "unavailable",
        "high demand",
        "issue",
        "problem",
        "unserviceable",
        "not available",
        "expired",
    )
    return any(ind in lowered for ind in failure_indicators)
