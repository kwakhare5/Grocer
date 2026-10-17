"""Deterministic safety guards, phrase matchers, and receipt post-processing for GROCER."""
from __future__ import annotations

import re
from typing import Any, Optional


def missing_recipe_staples(request: str, proposed_queries: list[str]) -> list[str]:
    """Keep a known recipe's indispensable base from disappearing from a model proposal."""
    missing = []
    if re.search(r"(?i)\b(?:make|making|prepare|cook)\b.{0,50}\bpizza\b|\bpizza\s+ingredients\b", request):
        if not re.search(r"(?i)\b(?:already\s+have|have|got)\b.{0,25}\b(?:pizza\s+)?(?:base|dough|crust)\b", request):
            if not any(re.search(r"(?i)\b(?:base|dough|crust)\b", query) for query in proposed_queries):
                missing.append("pizza base")

    if re.search(r"(?i)\b(?:make|making|prepare|cook)\b.{0,50}\bpasta\b|\bpasta\s+ingredients\b", request):
        if not re.search(r"(?i)\b(?:already\s+have|have|got)\b.{0,25}\b(?:pasta|penne|fusilli|spaghetti|macaroni|noodles)\b", request):
            if not any(
                re.search(r"(?i)\b(?:penne|fusilli|spaghetti|macaroni|noodles)\b", q)
                or (re.search(r"(?i)\bpasta\b", q) and not re.search(r"(?i)\b(?:sauce|masala|seasoning|mix)\b", q))
                for q in proposed_queries
            ):
                missing.append("pasta")

    if re.search(r"(?i)\b(?:make|making|prepare|cook)\b.{0,50}\bburger\b|\bburger\s+ingredients\b", request):
        if not re.search(r"(?i)\b(?:already\s+have|have|got)\b.{0,25}\b(?:burger\s+)?(?:bun|buns|bread)\b", request):
            if not any(re.search(r"(?i)\b(?:bun|buns)\b", query) for query in proposed_queries):
                missing.append("burger bun")

    return missing


def reconcile_explicit_items(request: str, proposed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep plainly enumerated products in the customer's order, even if the model omits one."""
    if not all(isinstance(item, dict) and isinstance(item.get("query"), str) for item in proposed):
        return proposed
    request = re.split(r"(?i)\nUse delivery address:", request, maxsplit=1)[0]
    extras = re.search(r"(?i)\b(?:also\s+add|and\s+add|plus)\b", request)
    first_intent = re.search(r"(?i)\b(?:pick\s+up|bring|add|buy|get|need)\b", request)
    start = first_intent if first_intent and (extras is None or first_intent.start() < extras.start()) else extras
    if start is None:
        return proposed
    clause = request[start.end():]
    clause = re.split(
        r"(?i)\b(?:under|below|within)\s*(?:₹|rs\.?|inr)?\s*[\d,]+"
        r"|\bfor\s+(?:dinner|breakfast|lunch|tonight)\b|[.!?]",
        clause, maxsplit=1,
    )[0]
    clause = re.split(r"(?i)\b(?:but\s+)?(?:no|without|except|skip|don't\s+add)\b", clause, maxsplit=1)[0]
    if clause.strip().casefold() == "and" or not clause.strip():
        return proposed
    if len(proposed) == 1 and clause.strip(" , ").casefold() == proposed[0]["query"].strip().casefold():
        return proposed
    requested = [
        re.sub(r"(?i)^(?:(?:me|please|a|an|the|some|one|plus|also\s+add)\s+)+", "", part).strip(" , ;")
        for part in re.split(r"(?i)\s*[,;]\s*|\s+and\s+|\s+plus\s+|\s*\+\s*|\s*&\s*", clause)
    ]
    requested = [part for part in requested if part and not re.match(r"(?i)^(?:no|without|except|skip)\b", part)]
    if (not requested or (extras is None and len(requested) < 2)
            or any(re.search(r"\d", part) for part in requested)):
        return proposed

    used: set[int] = set()
    ordered: list[dict[str, Any]] = []
    for part in requested:
        words = re.findall(r"\w+", part.casefold())
        full = next((index for index, item in enumerate(proposed) if index not in used
                     and all(word in re.findall(r"\w+", item["query"].casefold()) for word in words)), None)
        related = next((index for index, item in enumerate(proposed) if index not in used
                        and words[-1] in re.findall(r"\w+", item["query"].casefold())), None)
        index = full if full is not None else related
        if index is None:
            ordered.append({"query": part})
        else:
            used.add(index)
            item = proposed[index]
            ordered.append(item if full is not None else {**item, "query": part})
    return ([item for index, item in enumerate(proposed) if index not in used] + ordered
            if extras is not None and start is extras else ordered)


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

_RESET_COMMANDS = frozenset({
    "start over",
    "start fresh",
    "clear cart",
    "clear my cart",
    "clear the cart",
    "clear basket",
    "empty cart",
    "empty my cart",
    "empty basket",
    "reset",
    "reset cart",
    "delete cart",
    "delete all",
    "delete everything",
    "clear all",
    "empty all",
    "remove all",
    "scrap cart",
    "cancel cart",
    "wipe cart",
    "clear everything",
    "please clear my cart and start fresh",
})

_RESET_COMMAND_REGEX = re.compile(
    r"(?i)\b(?:clear|delete|empty|wipe|reset|cancel|scrap|remove)\s+(?:all\s+|my\s+|the\s+)?(?:cart|basket|items?|all|everything)\b"
    r"|^(?:reset|clear\s+all|empty\s+all|delete\s+all|start\s+(?:over|fresh))$"
)


def is_reset_command(text: str) -> bool:
    """Deterministically match any natural command requesting a basket purge in 0ms."""
    if not text:
        return False
    cleaned = text.strip().casefold().rstrip(".,!?")
    # If the user specifies exceptions ("except milk", "keep eggs", "save bread"), NEVER purge cart
    if re.search(r"\b(?:except|but|save|keep|leaving|apart from|other than)\b", cleaned):
        return False
    if cleaned in _RESET_COMMANDS:
        return True
    # If the user mentions a specific product/ingredient or specifies items to remove, it's not a full purge
    if re.search(r"\b(?:remove|delete|clear|drop)\s+(?:all\s+)?(?:the\s+)?(?!cart\b|basket\b|items?\b|all\b|everything\b)\b[a-z]{3,}\b", cleaned):
        return False
    return bool(_RESET_COMMAND_REGEX.search(cleaned))


_HESITATION_PHRASES = frozenset({
    "no",
    "nope",
    "nah",
    "wait",
    "wait wait",
    "hold on",
    "not yet",
    "no not yet",
    "no wait",
    "wait a minute",
    "hold",
    "stop",
    "pause",
    "dont order",
    "don't order",
    "do not order",
    "don't place it",
    "not now",
    "no thanks",
    "cancel",
})

_HESITATION_REGEX = re.compile(
    r"(?i)\b(wait|hold on|hold up|pause|stop|not yet|give me a (min|minute|sec|second)|wait a (sec|second|minute))\b"
)


def is_hesitation(text: str) -> bool:
    """Return True if text expresses hesitation, pause, or hold request."""
    if not text or not text.strip():
        return False
    cleaned = re.sub(r"\s+", " ", text.casefold()).strip(" \t\r\n.!?")
    if cleaned in _HESITATION_PHRASES:
        return True
    # Exclude common false positives: transportation stops and shopping sentences
    if re.search(r"\b(?:bus|auto|metro|train|taxi|cab|car|full|non)\s+stop\b", cleaned):
        return False
    if re.search(r"\b(?:add|buy|order|deliver|get|need|bring|send|pack|basket|cart)\b", cleaned):
        return False
    return bool(_HESITATION_REGEX.search(cleaned))


_NEGATION_CONFIRM_REGEX = re.compile(
    r"(?i)\b(don'?t|do not|never|stop|wait|hold|cancel|not now|not yet|no|nope|nah|pause|clear cart|start over)\b"
)
_SHOPPING_ITEM_OR_ACTION_REGEX = re.compile(
    r"(?i)\b(?:add|bring|need|want|remove|drop|delete|swap|change)\b"
    r"|\b(?:order|place)\s+(?!\b(?:order|now|karo|kar\s*do|the\s+order|this\s+order|my\s+order)\b)\b[\w-]+\b"
)
_AFFIRMATIVE_STANDALONE_REGEX = re.compile(
    r"(?i)^\s*(?:yes|yeah|yep|yup|haan(?:ji)?|proceed|checkout|pay|book\s+it|send\s+it|do\s+it|go\s+ahead|sounds?\s+good|looks?\s+good|good\s+to\s+go|all\s+good|perfect|theek\s+hai(?:.*?kar\s*do)?|haan\s+kar\s*do|haan\s+place\s*karo|confirm(?:\s+order)?)(?:\s+(?:please|now|boss|bhai))?\s*[.!]?$"
)
_EXPLICIT_CHECKOUT_PHRASES_REGEX = re.compile(
    r"(?i)\b(?:confirm\s+(?:the\s+|this\s+|my\s+)?order|place\s+(?:the\s+|this\s+|my\s+)?order|proceed\s+to\s+pay|proceed\s+with\s+order|order\s+now|order\s+confirm|order\s+place\s+karo|konfirm\s+order)\b"
)
_INQUIRY_OR_QUESTION_REGEX = re.compile(
    r"(?i)\?|\b(?:whether|check|tell\s+me|is|are|how\s+much|what\s+is|available|in\s+stock)\b"
)


def is_explicit_confirmation(text: str) -> bool:
    """Evaluate whether user input expresses explicit human checkout confirmation.

    CRITICAL INVARIANT: Negations ('don't confirm', 'do not order', 'not now') must
    always take precedence and reject confirmation, even if 'confirm' or 'order' appears.
    Normal grocery shopping queries (e.g. 'order 2 milk', 'add bread') and questions
    (e.g. 'please confirm whether milk is available') must never be treated as checkout
    confirmations.
    """
    if not text or not text.strip():
        return False
    cleaned = text.strip()
    if _NEGATION_CONFIRM_REGEX.search(cleaned):
        return False
    if _INQUIRY_OR_QUESTION_REGEX.search(cleaned):
        return False
    if _SHOPPING_ITEM_OR_ACTION_REGEX.search(cleaned):
        return False
    return bool(_AFFIRMATIVE_STANDALONE_REGEX.search(cleaned) or _EXPLICIT_CHECKOUT_PHRASES_REGEX.search(cleaned))


def reconcile_explicit_removals(text: str) -> list[str]:
    """Extract explicit item deletion requests from English text (e.g. 'remove bread', 'drop milk')."""
    if not text:
        return []
    pattern = r"\b(?:remove|delete|drop|take\s+out|skip|omit|without|exclude|don'?t\s+add|do\s+not\s+add|no\s+more)\s+([a-zA-Z0-9\s]+?)(?:,|and|\.|$)"
    matches = re.findall(pattern, text, re.IGNORECASE)
    cleaned = []
    for m in matches:
        item = re.sub(r"\b(?:the|a|an|please|from\s+(?:my\s+|the\s+)?(?:cart|basket))\b", "", m, flags=re.IGNORECASE).strip()
        if item:
            cleaned.append(item)
    return cleaned


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
