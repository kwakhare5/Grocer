"""
Centralized fuzzy matching logic for mapping natural language item names
to canonical catalog IDs. Used by agents and initial seeders.
"""

from rapidfuzz import process, fuzz

def fuzzy_match_item(query: str, catalog: dict, threshold: float = 60.0) -> dict | None:
    """
    Find the best matching item in the catalog using RapidFuzz.
    Catalog is expected to be a dict of {item_id: {"name": "...", ...}}.
    Returns the catalog item dict (with 'id' injected) or None if no good match.
    """
    if not query or not catalog:
        return None

    names = {item_id: data["name"] for item_id, data in catalog.items()}
    match = process.extractOne(
        query.lower(),
        names,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold
    )

    if match:
        matched_name, score, item_id = match
        item_data = dict(catalog[item_id])
        item_data["id"] = item_id
        return item_data

    return None

def is_fuzzy_match(w1: str, w2: str, threshold: float = 80.0) -> bool:
    """Compare two words for fuzzy equivalence."""
    w1 = w1.lower().strip()
    w2 = w2.lower().strip()
    if not w1 or not w2:
        return False
    if w1 in w2 or w2 in w1:
        return True
    return fuzz.ratio(w1, w2) > threshold

