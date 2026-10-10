"""Catalog matching, token normalization, and variant ranking heuristics."""
from __future__ import annotations

import re
from typing import Any, Optional

from backend.agent.product_policy import is_restricted_medical_product


def _normalize_token(w: str) -> str:
    """Normalize English word endings for plural-invariant matching."""
    w = w.casefold()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and len(w) > 2 and not w.endswith("ss"):
        return w[:-1]
    return w


_NEGATIVE_PAIR_EXCLUSIONS = (
    ("egg", "eggless"),
    ("sugar", "sugar-free"),
    ("caffeine", "decaf"),
    ("dairy", "dairy-free"),
    ("gluten", "gluten-free"),
    ("oil", "hair oil"),
    ("soap", "dishwash"),
    ("apple", "shampoo"),
)

_KNOWN_BRANDS = frozenset({
    "amul", "nandini", "mother dairy", "haldiram", "tata", "epigamia",
    "fortune", "aashirvaad", "britannia", "saffola", "everest", "mdh",
    "nestle", "cadbury", "modern", "lay's", "lays", "kurkure", "parle",
    "surf excel", "vim", "dettol", "colgate", "maggi", "kissan", "bingo",
    "chitale", "gowardhan", "warana", "katraj", "id", "heritage", "gemini",
})


def _matches_requested_product(query: str, product: dict[str, Any]) -> bool:
    """Reject loose provider search hits that do not contain the requested product words."""
    raw_words = [
        w for w in re.findall(r"[\w]+", query.casefold())
        if w not in {"a", "an", "the", "of", "for"}
    ]
    if not raw_words:
        return True
    name = " ".join(
        str(product.get(field) or "")
        for field in ("brand", "product_name", "name", "pack_size")
    ).casefold()

    q_low = query.casefold()
    for req, forbidden in _NEGATIVE_PAIR_EXCLUSIONS:
        if req in q_low and forbidden not in q_low and forbidden in name:
            return False

    name_tokens = {_normalize_token(t) for t in re.findall(r"[\w]+", name)}
    for rw in raw_words:
        norm_rw = _normalize_token(rw)
        if norm_rw in name or norm_rw in name_tokens or rw in name:
            continue
        return False
    return True


def _matches_item_name(query: str, item_name: str) -> bool:
    """Return True if a removal/modification query matches a cart item name."""
    if not query or not item_name:
        return False
    q_low = query.strip().casefold()
    n_low = item_name.strip().casefold()
    if q_low in n_low or n_low in q_low:
        return True
    q_words = [
        w for w in re.findall(r"\w+", q_low)
        if w not in {"the", "a", "an", "remove", "delete", "drop", "item", "please", "my"}
    ]
    if q_words and all(_normalize_token(w) in n_low or w in n_low for w in q_words):
        return True
    return False


def rank_and_select_best_variant(
    query: str,
    products: list[dict[str, Any]],
    preferred_pack_size: str = "",
) -> Optional[dict[str, Any]]:
    """Deterministically score and pick the single best product variant."""
    valid_candidates = []
    preferred = preferred_pack_size.casefold() if preferred_pack_size else ""
    q_low = query.casefold()
    req_brand = next(
        (b for b in _KNOWN_BRANDS if re.search(r"\b" + re.escape(b) + r"\b", q_low)),
        None,
    )
    query_words = [
        w.casefold()
        for w in re.findall(r"\w+", query)
        if w.casefold() not in {"a", "an", "the", "of", "for", "packet", "packets", "kg", "litre", "ltr"}
    ]

    for idx, p in enumerate(products):
        if not _matches_requested_product(query, p):
            continue
        if is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or "")):
            continue
        spin_id, sku_id = p.get("spin_id"), p.get("sku_id")
        price = p.get("price")
        if not isinstance(spin_id, str) or not isinstance(sku_id, str) or not isinstance(price, (int, float)) or price <= 0:
            continue

        name = str(p.get("name") or "").casefold()
        pack = str(p.get("pack_size") or "").casefold()

        # Strict brand omission: if a specific brand was requested, reject non-brand variants
        if req_brand and req_brand not in name and req_brand not in str(p.get("brand") or "").casefold():
            continue

        score = 100 - idx
        for qw in query_words:
            if qw in name:
                score += 25
        if preferred and (preferred in pack or preferred in name):
            score += 50

        valid_candidates.append(
            (
                score,
                {
                    "spin_id": spin_id,
                    "sku_id": sku_id,
                    "name": str(p.get("name") or query),
                    "pack_size": str(p.get("pack_size") or ""),
                    "price": float(price),
                    "max_quantity": p.get("max_quantity"),
                },
            )
        )

    if not valid_candidates:
        return None

    valid_candidates.sort(key=lambda c: c[0], reverse=True)
    return valid_candidates[0][1]
