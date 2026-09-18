"""Taxonomies, keyword dictionaries, and regex patterns for natural language grocery parsing."""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Unit normalization tables (including packaging format containers)
# ---------------------------------------------------------------------------

_UNIT_MAP: dict[str, str] = {
    "litre": "L", "litres": "L", "liter": "L", "liters": "L", "l": "L", "lt": "L",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml",
    "pcs": "pcs", "piece": "pcs", "pieces": "pcs", "pc": "pcs",
    "pack": "pack", "packs": "pack", "packet": "pack", "packets": "pack",
    "can": "can", "cans": "can", "tin": "can", "tins": "can",
    "bottle": "bottle", "bottles": "bottle",
    "pouch": "pouch", "pouches": "pouch", "sachet": "sachet", "sachets": "sachet",
    "tetrapak": "tetrapak", "tetrapack": "tetrapak", "box": "box", "boxes": "box",
    "strip": "strip", "strips": "strip", "bar": "bar", "bars": "bar",
    "dozen": "dozen", "doz": "dozen",
    "unit": "units", "units": "units",
}

# Standalone packaging container formats
_PACKAGING_DESCRIPTORS: set[str] = {
    "can", "cans", "tin", "tins", "bottle", "bottles", "pouch", "pouches",
    "sachet", "sachets", "tetrapak", "tetrapack", "box", "boxes", "packet", "packets",
    "pack", "packs", "bar", "bars", "cup", "cups", "tub", "tubs", "jar", "jars",
}

_QUANTITY_WORDS: dict[str, float] = {
    "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0,
    "four": 4.0, "five": 5.0, "six": 6.0, "half": 0.5,
    "dozen": 12.0, "a dozen": 12.0,
}

# Dietary keywords that are always hard constraints
_DIETARY_TAGS: set[str] = {
    "vegetarian", "vegan", "halal", "kosher", "jain",
    "gluten-free", "gluten free", "dairy-free", "dairy free",
    "egg-free", "eggless", "sugar-free", "sugar free",
}

# Common grocery categories for item classification
_CATEGORY_HINTS: dict[str, str] = {
    "milk": "dairy", "curd": "dairy", "yogurt": "dairy", "paneer": "dairy",
    "butter": "dairy", "ghee": "dairy", "cheese": "dairy", "cream": "dairy",
    "bread": "bakery", "bun": "bakery", "pav": "bakery", "roti": "bakery",
    "egg": "poultry", "eggs": "poultry", "chicken": "poultry", "mutton": "meat",
    "fish": "seafood", "prawn": "seafood", "shrimp": "seafood",
    "rice": "staples", "atta": "staples", "flour": "staples", "dal": "staples",
    "sugar": "staples", "salt": "staples", "oil": "staples", "tea": "staples",
    "coffee": "staples",
    "apple": "produce", "apples": "produce", "banana": "produce", "bananas": "produce",
    "tomato": "produce", "tomatoes": "produce",
    "onion": "produce", "onions": "produce", "potato": "produce", "potatoes": "produce",
    "fruit": "produce", "fruits": "produce",
    "vegetable": "produce", "vegetables": "produce", "sabzi": "produce",
    # Beverages & Cold Drinks
    "coke": "beverages", "coca cola": "beverages", "pepsi": "beverages", "thums up": "beverages",
    "sprite": "beverages", "fanta": "beverages", "soda": "beverages", "juice": "beverages",
    "water": "beverages", "drink": "beverages", "cold drink": "beverages", "beverage": "beverages",
    # Snacks & Confectionery
    "biscuit": "snacks", "biscuits": "snacks", "cookies": "snacks", "cookie": "snacks",
    "chips": "snacks", "namkeen": "snacks", "maggi": "snacks", "noodles": "snacks",
    "snack": "snacks", "rusk": "snacks", "chocolate": "snacks",
    # Pharma & Wellness
    "vicks": "pharma", "balm": "pharma", "crocin": "pharma", "paracetamol": "pharma",
    "dettol": "pharma", "bandaid": "pharma",
    # Personal Care
    "soap": "personal_care", "shampoo": "personal_care", "toothpaste": "personal_care",
}

# Non-vegetarian items for contradiction detection
_NON_VEG_ITEMS: set[str] = {
    "chicken", "mutton", "lamb", "fish", "prawn", "shrimp",
    "pork", "beef", "meat", "egg", "eggs",
}

# Common English words that should never be treated as item names
_STOP_WORDS: set[str] = {
    "get", "buy", "add", "order", "want", "need", "give", "send",
    "my", "me", "the", "a", "an", "some", "and", "or", "also", "plus",
    "with", "under", "within", "below", "above", "for", "from", "to",
    "in", "on", "at", "of", "is", "it", "this", "that", "i", "we",
    "only", "just", "please", "ok", "okay", "yes", "no", "not",
    "i want", "we want", "give me", "send me", "can you", "bhai",
}

# Goal pattern keywords
_GOAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:weekly|week['']?s?)\s*(?:grocer(?:ies|y)|restock|essentials|shopping)\b", re.I), "weekly grocery restock"),
    (re.compile(r"\b(?:monthly|month['']?s?)\s*(?:grocer(?:ies|y)|restock|essentials|shopping)\b", re.I), "monthly grocery restock"),
    (re.compile(r"\b(?:daily|today['']?s?)\s*(?:grocer(?:ies|y)|essentials|needs)\b", re.I), "daily essentials"),
    (re.compile(r"\bbreakfast\s*(?:restock|items?|essentials|shopping)?\b", re.I), "breakfast restock"),
    (re.compile(r"\b(?:grocer(?:ies|y)|restock|essentials|shopping)\b", re.I), "grocery restock"),
    (re.compile(r"\bget\b.*\b(?:items?|stuff|things)\b", re.I), "grocery restock"),
]
