"""Shared deterministic grocery quantity and product-identity semantics."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal, Optional


QuantityDimension = Literal["volume", "mass", "count", "pack_count", "catalog_dependent"]


@dataclass(frozen=True)
class NormalizedQuantity:
    """A quantity expressed in one canonical base dimension."""

    dimension: QuantityDimension
    amount: float


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PACK_RE = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|"
    r"kg|kilograms?|kilos?|g|grams?|gm|gms|"
    r"pcs?|pieces?|units?|eggs?)\b",
    re.IGNORECASE,
)
_MULTIPACK_RE = re.compile(r"(?P<count>\d+)\s*[x×]\s*", re.IGNORECASE)
_PACK_OF_RE = re.compile(
    r"(?:pack|box|tray)\s+of\s+(?P<count>\d+)\s*(?:pcs?|pieces?|units?|eggs?)?",
    re.IGNORECASE,
)

_DERIVATIVE_EXCLUSIONS: dict[str, set[str]] = {
    "bread": {"breadcrumb", "breadcrumbs", "crumb", "crumbs"},
    "butter": {"almond", "cashew", "peanut"},
    "milk": {"milkshake", "powder"},
    "rice": {"flour"},
}


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.casefold())


def _singular(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return f"{token[:-3]}y"
    if token.endswith("s") and not token.endswith("ss") and token not in {"pcs"}:
        return token[:-1]
    return token


def _product_head(value: str) -> Optional[str]:
    tokens = [_singular(token) for token in _tokens(value)]
    for token in reversed(tokens):
        if token in {
            "apple",
            "atta",
            "banana",
            "bread",
            "butter",
            "cheese",
            "coffee",
            "curd",
            "egg",
            "flour",
            "milk",
            "oil",
            "paneer",
            "rice",
            "salt",
            "sugar",
            "tea",
            "tomato",
            "yogurt",
        }:
            return token
    return tokens[-1] if tokens else None


def normalize_requested_quantity(
    quantity: float,
    unit: str,
    product_name: str,
    *,
    quantity_is_explicit: bool = True,
    pack_size_preference: Optional[str] = None,
) -> Optional[NormalizedQuantity]:
    """Normalize an intent quantity without guessing missing provider facts."""

    normalized_unit = unit.strip().casefold().replace(".", "")
    if normalized_unit in {"l", "litre", "litres", "liter", "liters", "lt"}:
        return NormalizedQuantity("volume", quantity * 1000)
    if normalized_unit in {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}:
        return NormalizedQuantity("volume", quantity)
    if normalized_unit in {"kg", "kgs", "kilogram", "kilograms", "kilo", "kilos"}:
        return NormalizedQuantity("mass", quantity * 1000)
    if normalized_unit in {"g", "gm", "gms", "gram", "grams"}:
        return NormalizedQuantity("mass", quantity)
    if normalized_unit in {"dozen", "doz"}:
        return NormalizedQuantity("count", quantity * 12)

    preferred_pack = normalize_pack_quantity(pack_size_preference or "")
    if preferred_pack is not None and normalized_unit in {"", "unit", "units"}:
        return NormalizedQuantity(
            preferred_pack.dimension,
            preferred_pack.amount * quantity,
        )

    if (
        normalized_unit in {"pc", "pcs", "piece", "pieces"}
        and quantity_is_explicit
    ):
        return NormalizedQuantity("count", quantity)
    if normalized_unit in {"", "unit", "units"} and quantity_is_explicit:
        return NormalizedQuantity("catalog_dependent", quantity)
    if normalized_unit in {
        "pack",
        "packs",
        "packet",
        "packets",
        "pc",
        "pcs",
        "piece",
        "pieces",
    }:
        return NormalizedQuantity("pack_count", quantity)
    if normalized_unit in {"", "unit", "units"}:
        return NormalizedQuantity("pack_count", quantity)
    return None


def normalize_pack_quantity(pack_size: str) -> Optional[NormalizedQuantity]:
    """Parse common provider pack labels into ml, g, or count."""

    text = pack_size.strip().casefold()
    if not text:
        return None

    pack_of = _PACK_OF_RE.search(text)
    if pack_of:
        return NormalizedQuantity("count", float(pack_of.group("count")))

    match = _PACK_RE.search(text)
    if not match:
        return None

    amount = float(match.group("amount"))
    unit = match.group("unit").casefold()
    multiplier_match = _MULTIPACK_RE.search(text[: match.start()])
    multiplier = float(multiplier_match.group("count")) if multiplier_match else 1.0

    if unit in {"l", "litre", "litres", "liter", "liters"}:
        return NormalizedQuantity("volume", amount * 1000 * multiplier)
    if unit in {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}:
        return NormalizedQuantity("volume", amount * multiplier)
    if unit in {"kg", "kilogram", "kilograms", "kilo", "kilos"}:
        return NormalizedQuantity("mass", amount * 1000 * multiplier)
    if unit in {"g", "gm", "gms", "gram", "grams"}:
        return NormalizedQuantity("mass", amount * multiplier)
    return NormalizedQuantity("count", amount * multiplier)


def required_pack_count(
    requested: NormalizedQuantity,
    pack: Optional[NormalizedQuantity],
) -> Optional[int]:
    """Return an exact pack count, rejecting underfill and silent overfill."""

    if requested.dimension == "pack_count":
        rounded = round(requested.amount)
        return int(rounded) if math.isclose(requested.amount, rounded) else None
    if requested.dimension == "catalog_dependent":
        return None
    if pack is None or pack.dimension != requested.dimension or pack.amount <= 0:
        return None

    ratio = requested.amount / pack.amount
    rounded = round(ratio)
    if rounded < 1 or not math.isclose(ratio, rounded, rel_tol=1e-9, abs_tol=1e-9):
        return None
    return int(rounded)


def product_identity_matches(
    requested_name: str,
    candidate_name: str,
    requested_category: Optional[str] = None,
    candidate_category: Optional[str] = None,
) -> bool:
    """Match a product head while excluding known derivative product classes."""

    if requested_category and candidate_category:
        if requested_category.casefold() != candidate_category.casefold():
            return False

    requested_head = _product_head(requested_name)
    if requested_head is None:
        return False

    candidate_tokens = {_singular(token) for token in _tokens(candidate_name)}
    if requested_head not in candidate_tokens:
        return False

    exclusions = _DERIVATIVE_EXCLUSIONS.get(requested_head, set())
    return not bool(candidate_tokens & exclusions)


def brand_identity_matches(
    requested_brand: str,
    *candidate_values: Optional[str],
) -> bool:
    """Match all normalized words of a possibly multi-word explicit brand."""

    requested_tokens = {_singular(token) for token in _tokens(requested_brand)}
    if not requested_tokens:
        return False
    candidate_tokens: set[str] = set()
    for value in candidate_values:
        if value:
            candidate_tokens.update(_singular(token) for token in _tokens(value))
    return requested_tokens.issubset(candidate_tokens)
