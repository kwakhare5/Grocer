"""Extract only clearly stated order-wide rupee limits."""
from __future__ import annotations

import re

_AMOUNT = r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)"
_CURRENCY = r"(?:₹|rs\.?|inr|rupees?)"
_TOTAL_PATTERNS = (
    re.compile(rf"(?i)\b(?:total|overall|budget(?:\s+of)?)\s*(?:under|below|up\s+to|of|is|:)?\s*(?:{_CURRENCY}\s*)?{_AMOUNT}\b"),
    re.compile(rf"(?i)\b(?:under|below|max(?:imum)?)\s*{_CURRENCY}\s*{_AMOUNT}\b"),
    re.compile(rf"(?i)\b(?:under|below|max(?:imum)?)\s*{_AMOUNT}\s*{_CURRENCY}\b"),
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
