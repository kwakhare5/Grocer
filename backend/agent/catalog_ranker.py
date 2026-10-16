"""Catalog matching, token normalization, and variant ranking heuristics."""
from __future__ import annotations

import re
from typing import Any, Optional

from backend.agent.product_policy import is_restricted_medical_product


def _normalize_token(w: str) -> str:
    """Normalize English word endings for plural-invariant matching without destroying word roots."""
    w = w.casefold()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    # Only strip 'es' after s, x, z, ch, sh, or o (e.g. boxes -> box, tomatoes -> tomato)
    if w.endswith("es") and len(w) > 4 and w[-3] in {"s", "x", "z", "h", "o"}:
        return w[:-2]
    if w.endswith("s") and len(w) > 2 and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _matches_requested_product(query: str, product: dict[str, Any]) -> bool:
    """Check if product matches query, avoiding direct negative exclusions."""
    q_low = query.casefold()
    name = " ".join(
        str(product.get(field) or "")
        for field in ("brand", "product_name", "name", "pack_size")
    ).casefold()

    # Guard against accidental opposite matches (e.g., eggless cake when user asked for egg)
    if "egg" in q_low.split() and "eggless" not in q_low and "eggless" in name:
        return False
    if "sugar" in q_low.split() and "sugar-free" not in q_low and "sugar-free" in name:
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
    """Deterministically score and pick the single best product variant from provider search hits."""
    valid_candidates = []
    preferred = preferred_pack_size.casefold() if preferred_pack_size else ""
    q_low = query.casefold()
    cleaned_q = re.sub(r"'(?:d|s|m|ll|ve|re)\b", "", q_low)
    query_words = [
        w
        for w in re.findall(r"[a-z]{2,}", cleaned_q)
        if w not in {"the", "of", "for", "packet", "packets", "kg", "litre", "ltr", "like", "want", "please", "need"}
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
        brand = str(p.get("brand") or "").casefold()

        # Relevance starts with search rank from provider
        score = 100 - idx
        for qw in query_words:
            if qw in name or qw in brand:
                score += 25
        if preferred and (preferred in pack or preferred in name):
            score += 50

        # Multipack vs single household pack preferences
        is_user_requesting_bulk = bool(re.search(r"\b(?:packs?|multipacks?|combos?|bundles?|dozen|boxes?|cases?|\d+\s*x)\b", q_low))
        is_product_bundle = bool(re.search(r"\b(?:\d+\s*x\s*\d+|x\s*\d+|pack of \d+|bundle|combo|buy \d+ get \d+)\b", f"{name} {pack}"))
        if is_product_bundle and not is_user_requesting_bulk:
            score -= 100
        elif is_product_bundle and is_user_requesting_bulk:
            score += 50
        elif not is_product_bundle:
            score += 30

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
