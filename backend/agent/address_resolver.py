"""Address choice matching, intent parsing, and delivery address resolution."""
from __future__ import annotations

import re
from typing import Any, Optional

# Generic address parts and grocery adjectives that should not match as area tokens
_GENERIC_ADDR_TOKENS = frozenset({
    "road", "flat", "floor", "near", "opposite", "lane", "house", "building",
    "street", "block", "sector", "phase", "cross", "main", "layout",
    "fresh", "sweet", "white", "brown", "red", "black", "pure", "green",
})


def match_pending_address_choice(
    pending_addrs: list[dict[str, Any]],
    norm_text: str,
    interactive_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Resolve customer selection from a list of pending address choices."""
    if interactive_id:
        clean_id = (
            interactive_id.removeprefix("addr_choice_")
            .removeprefix("select_address:")
            .removeprefix("addr_")
        )
        for a in pending_addrs:
            if (
                str(a.get("_choice_code")) == clean_id
                or str(a.get("address_id")) == clean_id
                or str(a.get("id")) == clean_id
                or str(a.get("_choice_index")) == clean_id
                or str(a.get("id")) == interactive_id
                or str(a.get("address_id")) == interactive_id
            ):
                return a

    norm_text = (norm_text or "").strip().casefold()
    if not norm_text:
        return None

    # Handle numeric references: "1", "option 2", "choice 3", "#1"
    num_match = re.search(r"\b(?:option|choice|number|no\.?|#)?\s*(\d+)\b", norm_text)
    choice_num = num_match.group(1) if num_match else None

    for a in pending_addrs:
        if choice_num and str(a.get("_choice_index")) == choice_num:
            return a
        cand_values = {
            str(a.get("_choice_code", "")).casefold(),
            str(a.get("label", "")).casefold(),
            str(a.get("clean_address", "")).casefold(),
            str(a.get("id", "")).casefold(),
            str(a.get("address_id", "")).casefold(),
        }
        cand_values.discard("")
        if norm_text in cand_values:
            return a

    # Token matching with negation handling
    tokens = [t for t in re.split(r"\W+", norm_text) if len(t) > 2]
    positive_tokens = []
    for i, t in enumerate(tokens):
        # If preceded by negation, ignore
        if i > 0 and tokens[i - 1] in ("not", "dont", "never"):
            continue
        positive_tokens.append(t)

    for token in positive_tokens:
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
    if not norm_text:
        return None
    norm_text = norm_text.casefold()

    # Detect negation phrases to avoid picking negated addresses
    negated_matches = set()
    for neg_phrase in re.findall(r"\b(?:do\s+not|don't|not|never)\s+(?:send|deliver|ship)?\s*(?:to|at)?\s+([^,.;]+)", norm_text):
        negated_matches.add(neg_phrase.strip())

    candidates = []
    for a in addresses:
        lbl = str(a.get("label") or "").casefold()
        clean_addr = str(a.get("clean_address") or "").casefold()
        city = str(a.get("city") or "").casefold()
        loc = (str(a.get("area") or "") + " " + str(a.get("street") or "") + " " + city).casefold()

        is_negated = any(lbl in neg or (clean_addr and clean_addr in neg) for neg in negated_matches)
        if is_negated:
            continue

        # Check label match: "deliver to home", "deliver home", "send to pune office", "use pune office"
        if lbl and (
            re.search(
                rf"\b(?:deliver|send|ship|bring|drop|switch|change|take|use)\s*(?:to|at)?\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b(?:to|at)\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b{re.escape(lbl)}\s+(?:address|location|destination|office|home)\b",
                norm_text,
            )
            or norm_text == lbl
            or norm_text.startswith(f"{lbl} ")
        ):
            candidates.append(a)
            continue

        addr_tokens = [
            t for t in re.findall(r"[a-z]{4,}", loc)
            if t not in _GENERIC_ADDR_TOKENS and t != lbl
        ]
        if any(
            re.search(
                rf"\b(?:deliver|send|ship|bring|drop|switch|change|use)\s+(?:to|at)\s+(?:my\s+|the\s+)?{re.escape(t)}\b"
                rf"|\b(?:to|at)\s+(?:my\s+|the\s+)?{re.escape(t)}\s+(?:address|location|area|house|flat|apartment|branch)?\b",
                norm_text,
            )
            for t in addr_tokens
        ):
            candidates.append(a)

    if candidates:
        return candidates[0]

    return None
