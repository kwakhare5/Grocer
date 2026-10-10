"""Address choice matching, intent parsing, and delivery address resolution."""
from __future__ import annotations

import re
from typing import Any, Optional

_GENERIC_ADDR_TOKENS = frozenset({
    "road", "flat", "floor", "near", "opposite", "lane", "nagar", "pune", "maharashtra", "india",
})


def match_pending_address_choice(
    pending_addrs: list[dict[str, Any]],
    norm_text: str,
    interactive_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Resolve customer selection from a list of pending address choices."""
    if interactive_id and interactive_id.startswith("addr_choice_"):
        choice_code = interactive_id.removeprefix("addr_choice_")
        return next(
            (
                a for a in pending_addrs
                if str(a.get("_choice_code")) == choice_code
                or str(a.get("address_id")) == choice_code
                or str(a.get("_choice_index")) == choice_code
            ),
            None,
        )

    clean_num = norm_text.split(".")[0].strip() if norm_text and norm_text[0].isdigit() else norm_text
    matches = []
    for a in pending_addrs:
        candidate_values = {
            str(a.get("_choice_index", "")),
            str(a.get("_choice_code", "")).casefold(),
            str(a.get("label", "")).casefold(),
            str(a.get("clean_address", "")).casefold(),
        }
        if clean_num in candidate_values or norm_text in candidate_values:
            matches.append(a)

    if len(matches) == 1:
        return matches[0]

    tokens = [t for t in re.split(r"\W+", norm_text) if len(t) > 2]
    for token in tokens:
        token_matches = [
            a for a in pending_addrs
            if token in str(a.get("clean_address", "")).casefold()
            or token in str(a.get("label", "")).casefold()
        ]
        if len(token_matches) == 1:
            return token_matches[0]

    return None


def match_explicit_address(
    addresses: list[dict[str, Any]],
    norm_text: str,
) -> Optional[dict[str, Any]]:
    """Match explicit address mentions in incoming messages against saved addresses."""
    for a in addresses:
        lbl = str(a.get("label") or "").casefold()
        clean_addr = str(a.get("clean_address") or "").casefold()
        if lbl and (
            re.search(
                rf"\b(?:deliver|send|ship|bring|drop|switch|change|take)\b.*?\b(?:to|at)\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b(?:deliver|send|ship|switch|change|use)\s+to\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b(?:deliver|send|ship|drop)\s+at\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b{re.escape(lbl)}\s+(?:address|location|destination)\b",
                norm_text,
            )
        ):
            return a

        addr_tokens = [
            t for t in re.findall(r"[a-z]{4,}", clean_addr)
            if t not in _GENERIC_ADDR_TOKENS
        ]
        if any(t in norm_text for t in addr_tokens):
            return a

    return None
