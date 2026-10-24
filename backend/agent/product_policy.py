"""WhatsApp grocery replenishment product policy checks."""
from __future__ import annotations

# Swiggy Instamart categories that represent prescription drugs or clinical pharmacy items
_RESTRICTED_CATEGORIES = frozenset({
    "prescription",
    "prescription_drugs",
    "prescription_medicines",
    "rx",
    "rx_drugs",
    "pharmacy_rx",
    "medicines",
    "pharmacy",
})

# Permitted OTC categories even in health/wellness aisles
_PERMITTED_CATEGORIES = frozenset({
    "first_aid",
    "first aid",
    "otc",
    "otc_wellness",
    "digestive_care",
    "digestives",
    "pain_relief_balms",
    "balms",
    "personal_care",
    "hygiene",
    "oral_care",
    "groceries",
    "dairy",
    "staples",
})


_PERMITTED_FIRST_AID_KEYWORDS = frozenset({
    "band-aid", "band aid", "bandage", "bandages", "cotton", "ors", "dettol",
    "savlon", "burnol", "eno", "moov", "vicks", "volini", "iodex", "lozenge",
    "strepsils", "condom", "condoms", "pad", "pads", "napkin", "napkins",
    "sanitary", "antiseptic", "first aid", "electral", "omgel"
})


def is_restricted_medical_product(name: str, category: str | None = None) -> bool:
    """Check if an item is a restricted prescription drug using Swiggy catalog category metadata.

    Prescription drugs are strictly prohibited. Daily OTC wellness, first aid, and grocery items are permitted.
    """
    if name:
        low_name = name.casefold()
        if any(kw in low_name for kw in _PERMITTED_FIRST_AID_KEYWORDS):
            return False

    if not category:
        return False
    norm_cat = category.strip().casefold()
    if norm_cat in _PERMITTED_CATEGORIES:
        return False
    return norm_cat in _RESTRICTED_CATEGORIES
