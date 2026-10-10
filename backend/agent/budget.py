"""Extract explicit order-wide and ingredient-only rupee limits."""
from __future__ import annotations

import re

_AMOUNT = r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)"
_CURRENCY = r"(?:₹|rs\.?|inr|rupees?)"
_TOTAL_PATTERNS = (
    re.compile(rf"(?i)\b(?:total|overall|budget(?:\s+of)?)\s*(?:under|below|up\s+to|of|is|:)?\s*(?:{_CURRENCY}\s*)?{_AMOUNT}\b"),
    re.compile(rf"(?i)\b(?:under|below|max(?:imum)?)\s*{_CURRENCY}\s*{_AMOUNT}\b"),
    re.compile(rf"(?i)\b(?:under|below|max(?:imum)?)\s*{_AMOUNT}\s*{_CURRENCY}\b"),
    re.compile(
        rf"(?i)\b(?:under|below|within|at\s+most|no\s+more\s+than|up\s+to|max(?:imum)?)\s*"
        rf"(?:{_CURRENCY}\s*)?{_AMOUNT}\b(?!\s*(?:g|kg|ml|l|litres?|pieces?|pcs|mins?|minutes?|hours?|hrs?|items?|products?|days?|seconds?|sec|percent|%|steps?|times?)\b)"
    ),
)


def extract_total_budget(text: str) -> float | None:
    for pattern in _TOTAL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if re.match(r"(?i)\s*(?:each|per\s+item|apiece)\b", text[match.end():]):
            continue
        amount = float(match.group(1).replace(",", ""))
        return amount if amount > 0 else None
    return None


_SCOPED_INGREDIENTS = re.compile(
    rf"(?is)\bingredients?\b.{0,80}?\b(?:under|below|within)\s*"
    rf"(?:{_CURRENCY}\s*)?(?P<amount>{_AMOUNT})\b"
)
_EXTRAS_CLAUSE = re.compile(r"(?is)\b(?:(?:and\s+)?(?:also\s+)?add|plus)\b\s+(?P<extras>.+)$")


def extract_ingredient_budget(text: str) -> tuple[float, str] | None:
    """Read an explicit ingredient-only cap and any separately named extras."""
    match = _SCOPED_INGREDIENTS.search(text)
    if not match:
        return None
    amount = float(match.group("amount").replace(",", ""))
    extras = _EXTRAS_CLAUSE.search(text[match.end():])
    return (amount, extras.group("extras") if extras else "") if amount > 0 else None


def is_explicit_extra(query: str, extras_text: str) -> bool:
    """Classify only an item named in the customer's explicit extra clause."""
    words = re.findall(r"[\w]+", query.casefold())
    words = [word for word in words if len(word) >= 4 and word not in {
        "fresh", "green", "brown", "whole", "large", "small", "organic",
    }]
    return bool(words and any(re.search(rf"\b{re.escape(w)}\b", extras_text.casefold()) for w in words))

