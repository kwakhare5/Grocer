"""Intent Parser — WhatsApp natural language → validated IntentContract (Spec Section 5, Section 12).

Architecture:
    WhatsApp text → RuleBasedExtractor → DeterministicValidator → IntentContract

The RuleBasedExtractor uses deterministic regex/heuristic extraction.
The DeterministicValidator always runs and has final authority over the output
(Spec Section 12.3: "LLM interprets and proposes. Deterministic code enforces and verifies.").
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.config import settings
from backend.intent.enums import (
    AmbiguitySeverity,
    BrandTolerance,
    ConstraintType,
    PreferenceType,
    SubstitutionTolerance,
)
from backend.intent.models import (
    Ambiguity,
    AuthorizationScope,
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    HardConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    QuantityRules,
    SoftPreference,
    SourceContext,
    SubstitutionPolicy,
)

# ---------------------------------------------------------------------------
# Unit normalization tables
# ---------------------------------------------------------------------------

_UNIT_MAP: dict[str, str] = {
    "litre": "L", "litres": "L", "liter": "L", "liters": "L", "l": "L", "lt": "L",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml",
    "pcs": "pcs", "piece": "pcs", "pieces": "pcs", "pc": "pcs",
    "pack": "pack", "packs": "pack", "packet": "pack", "packets": "pack",
    "dozen": "dozen", "doz": "dozen",
    "unit": "units", "units": "units",
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


# ---------------------------------------------------------------------------
# RuleBasedExtractor
# ---------------------------------------------------------------------------

class RuleBasedExtractor:
    """Deterministic pattern-based extraction of intent fields from natural language."""

    def _detect_greeting(self, text: str) -> bool:
        return bool(
            re.match(
                r"^(?:hi|hello|hey|good\s+morning|good\s+evening|namaste)(?:\s+grocer)?[\s!.,?]*$",
                text.strip(),
                re.I,
            )
        )

    def extract(self, text: str) -> dict:
        """Extract raw intent fields from text. Returns a dict of candidate fields."""
        is_greeting = self._detect_greeting(text)
        result: dict = {
            "is_greeting": is_greeting,
            "goal": "greeting" if is_greeting else self._extract_goal(text),
            "items": [] if is_greeting else self._extract_items(text),
            "budget": None if is_greeting else self._extract_budget(text),
            "dietary_constraints": [] if is_greeting else self._extract_dietary(text),
            "brand_preferences": [] if is_greeting else self._extract_brand_preferences(text),
            "substitution_policy": {} if is_greeting else self._extract_substitution_policy(text),
            "soft_preferences": [] if is_greeting else self._extract_soft_preferences(text),
            "ambiguities": [],
        }

        if not is_greeting:
            # Detect contradictions
            contradictions = self._detect_contradictions(text, result)
            result["ambiguities"].extend(contradictions)

            # Detect vague quantities
            vague = self._detect_vague_quantities(text, result["items"])
            result["ambiguities"].extend(vague)

        return result

    def _extract_goal(self, text: str) -> str:
        """Extract the high-level shopping goal."""
        for pattern, goal in _GOAL_PATTERNS:
            if pattern.search(text):
                return goal
        # Fallback: use abbreviated text as goal
        words = text.split()
        return " ".join(words[:8]) if len(words) > 8 else text

    def _extract_budget(self, text: str) -> Optional[dict]:
        """Extract budget constraint from text."""
        # Patterns: "under ₹2,000", "within 1500", "budget 3000", "less than Rs 2000"
        budget_patterns = [
            re.compile(r"(?:under|within|below|less\s+than|max(?:imum)?|budget\s*(?:of|is|:)?)\s*(?:₹|rs\.?|inr\.?\s*)?\s*([\d,]+)", re.I),
            re.compile(r"(?:₹|rs\.?|inr\.?\s*)\s*([\d,]+)\s*(?:budget|max|limit)", re.I),
            re.compile(r"(?:₹|rs\.?)\s*([\d,]+)", re.I),
        ]

        for pattern in budget_patterns:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        return {"max_budget": amount, "currency": "INR", "is_hard": True}
                except ValueError:
                    continue
        return None

    def _extract_items(self, text: str) -> list[dict]:
        """Extract individual shopping items with quantities and units."""
        items: list[dict] = []
        seen_names: set[str] = set()

        # Pattern: "2L milk", "1kg rice", "6 eggs", "2 litres of milk", "a dozen eggs"
        qty_unit_item = re.compile(
            r"(\d+(?:\.\d+)?)\s*"                          # quantity
            r"(litres?|liters?|l|lt|kg|kgs?|kilos?|g|gms?|grams?|ml|pcs?|pieces?|packs?|packets?|dozen|doz)?\s*"  # unit
            r"(?:of\s+)?"                                   # optional "of"
            r"((?:(?!and\b|or\b|also\b|plus\b|under\b|below\b|within\b|budget\b)[a-zA-Z\s])+)",  # item name
            re.I,
        )

        for match in qty_unit_item.finditer(text):
            qty = float(match.group(1))
            raw_unit = (match.group(2) or "").strip().lower()
            name = match.group(3).strip().rstrip(",. ")
            # Clean trailing conjunctions
            name = re.sub(r"\s+(?:and|or|also|plus|under|below|within)\s*$", "", name, flags=re.I).strip()
            # Strip leading verbs/articles/conversational phrases
            name = re.sub(
                r"^(?:get|buy|add|order|and|also|plus|with|the|my|some|a|an|of|i want|we want|want|need|give me|send me|bhai|please)\s+",
                "",
                name,
                flags=re.I,
            ).strip()
            if not name or name.lower() in seen_names or name.lower() in _STOP_WORDS or len(name) < 2:
                continue
            unit = _UNIT_MAP.get(raw_unit, "units") if raw_unit else "units"
            item = self._build_item(name, qty, unit, quantity_is_explicit=True)
            items.append(item)
            seen_names.add(name.lower())

        # Pattern: word-number items like "eggs 6", "bread 2"
        item_qty = re.compile(
            r"\b((?:(?!and\b|or\b|also\b|plus\b|under\b|below\b|within\b|budget\b)[a-zA-Z\s])+?)\s+"
            r"(\d+(?:\.\d+)?)\s*"
            r"(litres?|liters?|l|kg|kgs?|g|gms?|ml|pcs?|pieces?|packs?|dozen)?\b",
            re.I,
        )

        for match in item_qty.finditer(text):
            name = match.group(1).strip().rstrip(",. ")
            name = re.sub(r"\s+(?:and|or|also|plus|of)\s*$", "", name, flags=re.I).strip()
            name = re.sub(
                r"^(?:get|buy|add|order|and|also|plus|with|the|my|some|a|an|of|i want|we want|want|need|give me|send me|bhai|please)\s+",
                "",
                name,
                flags=re.I,
            ).strip()
            if not name or name.lower() in seen_names or name.lower() in _STOP_WORDS or len(name) < 2:
                continue
            if any(term in name.lower() for term in ("want", "need", "give", "send", "please", "bhai")):
                continue

            qty = float(match.group(2))
            raw_unit = (match.group(3) or "").strip().lower()
            unit = _UNIT_MAP.get(raw_unit, "units") if raw_unit else "units"
            item = self._build_item(name, qty, unit, quantity_is_explicit=True)
            items.append(item)
            seen_names.add(name.lower())

        # Pattern: bare items without quantities — "bread", "milk", "rice"
        # Only match known grocery keywords not already captured
        for keyword, category in _CATEGORY_HINTS.items():
            if keyword in text.lower() and keyword not in seen_names:
                # Check it's a standalone word
                if re.search(rf"\b{re.escape(keyword)}\b", text, re.I):
                    # Skip if it's part of a brand or modifier phrase we already captured
                    already = any(keyword in item["name"].lower() for item in items)
                    if not already:
                        items.append(self._build_item(keyword.title(), 1.0, "units"))
                        seen_names.add(keyword)

        # Pattern: conversational swap/replacement phrases if no items captured yet
        if not items:
            m = re.match(r"^(?:make\s+it|switch\s+to|change(?:\s+it)?\s+to|get\s+me|send\s+me)\s+(.+)$", text.strip(), re.I)
            if m:
                cand_name = m.group(1).strip().rstrip(",. ")
                cand_name = re.sub(r"\s+(?:instead|please)\s*$", "", cand_name, flags=re.I).strip()
                if cand_name and cand_name.lower() not in _STOP_WORDS and len(cand_name) >= 2:
                    items.append(self._build_item(cand_name.title(), 1.0, "units"))
                    seen_names.add(cand_name.lower())
            else:
                m = re.match(r"^(?:replace|change|swap)\s+(.+?)\s+(?:with|to|for)\s+(.+)$", text.strip(), re.I)
                if m:
                    cand_name = m.group(2).strip().rstrip(",. ")
                    if cand_name and cand_name.lower() not in _STOP_WORDS and len(cand_name) >= 2:
                        items.append(self._build_item(cand_name.title(), 1.0, "units"))
                        seen_names.add(cand_name.lower())

        return items

    def _build_item(
        self,
        name: str,
        quantity: float,
        unit: str,
        *,
        quantity_is_explicit: bool = False,
    ) -> dict:
        """Build an item dict with category hint."""
        name_lower = name.lower().strip()
        category = None
        for keyword, cat in _CATEGORY_HINTS.items():
            if keyword in name_lower:
                category = cat
                break

        # Extract brand from name if it looks like "Amul milk" or "Mother Dairy milk"
        # Try progressively longer prefixes as brand, check if remaining suffix is a known product
        brand = None
        words = name.split()
        if len(words) >= 2:
            for split_at in range(1, len(words)):
                prefix = " ".join(words[:split_at])
                suffix_lower = " ".join(words[split_at:]).lower()
                if prefix[0].isupper() and suffix_lower in _CATEGORY_HINTS:
                    brand = prefix
                    name = " ".join(words[split_at:]).title()
                    break

        return {
            "name": name.strip(),
            "quantity": quantity,
            "unit": unit,
            "quantity_is_explicit": quantity_is_explicit,
            "brand_preference": brand,
            "category": category,
            "is_essential": True,
        }

    def _extract_dietary(self, text: str) -> list[dict]:
        """Extract dietary constraints (always hard)."""
        constraints: list[dict] = []
        text_lower = text.lower()

        for tag in _DIETARY_TAGS:
            if tag in text_lower:
                # Check for negation patterns: "not vegetarian" / "non vegetarian" excluded
                # But "no non-veg" should trigger vegetarian
                if re.search(rf"\b(?:not|non|no)\s+{re.escape(tag)}\b", text_lower):
                    continue
                constraints.append({"tag": tag, "is_hard": True})

        # "no non-veg" / "no nonveg" → vegetarian
        if re.search(r"\bno\s+non[\s-]?veg\b", text_lower):
            if not any(c["tag"] == "vegetarian" for c in constraints):
                constraints.append({"tag": "vegetarian", "is_hard": True})

        # "only veg" → vegetarian
        if re.search(r"\bonly\s+veg\b", text_lower) and not any(c["tag"] == "vegetarian" for c in constraints):
            constraints.append({"tag": "vegetarian", "is_hard": True})

        return constraints

    def _extract_brand_preferences(self, text: str) -> list[dict]:
        """Extract brand-level preferences and hard locks."""
        preferences: list[dict] = []

        # Pattern: "don't replace X with another brand" / "only X brand for Y"
        no_replace = re.compile(
            r"(?:don['']?t|do\s+not|never)\s+(?:replace|substitute|swap|change)\s+"
            r"(?:the\s+|my\s+)?(\w+(?:\s+\w+)?)\s+"
            r"(?:with|for|to)\s+(?:another|different|other)\s+(?:brand|product|variant)",
            re.I,
        )
        for match in no_replace.finditer(text):
            product = match.group(1).strip().lower()
            preferences.append({
                "product_or_category": product,
                "preferred_brand": "",  # Brand lock without specifying which brand = keep current
                "is_hard": True,
                "alternative_brands": [],
            })

        return preferences

    def _extract_substitution_policy(self, text: str) -> Optional[dict]:
        """Extract substitution preferences."""
        text_lower = text.lower()

        # Explicit no-substitution
        if re.search(r"\bno\s+substitut(?:ion|e|es|ing)\b", text_lower):
            return {
                "allow_substitutions": False,
                "brand_tolerance": "same_brand",
                "pack_size_tolerance": "strict",
            }

        # Flexible substitution
        if re.search(r"\b(?:you\s+can|feel\s+free\s+to|okay\s+to)\s+(?:replace|substitute|swap)\b", text_lower):
            return {
                "allow_substitutions": True,
                "brand_tolerance": "any",
                "pack_size_tolerance": "flexible",
            }

        # Brand lock implies strict brand tolerance
        if re.search(r"(?:don['']?t|do\s+not|never)\s+(?:replace|substitute|swap|change)", text_lower):
            return {
                "allow_substitutions": True,
                "brand_tolerance": "same_brand",
                "pack_size_tolerance": "reasonable",
            }

        return None

    def _extract_soft_preferences(self, text: str) -> list[dict]:
        """Extract soft (relaxable) preferences."""
        prefs: list[dict] = []
        text_lower = text.lower()

        # "use my usual brands" / "my regular brands" / "usual brands"
        if re.search(r"\b(?:my\s+)?(?:usual|regular|preferred|favorite)\s+brands?\b", text_lower):
            prefs.append({
                "preference_type": "brand",
                "target": "brand:all",
                "preference": "usual_brands",
                "weight": 0.8,
            })

        # "cheapest" / "lowest price"
        if re.search(r"\b(?:cheap(?:est)?|lowest\s+price|budget\s+friendly|value)\b", text_lower):
            prefs.append({
                "preference_type": "price_sensitivity",
                "target": "price:all",
                "preference": "lowest_price",
                "weight": 0.7,
            })

        return prefs

    def _detect_contradictions(self, text: str, result: dict) -> list[dict]:
        """Detect contradictions between dietary constraints and requested items."""
        ambiguities: list[dict] = []
        text_lower = text.lower()

        is_vegetarian = any(
            dc["tag"] == "vegetarian" for dc in result.get("dietary_constraints", [])
        )

        if is_vegetarian:
            for item in result.get("items", []):
                item_name_lower = item["name"].lower()
                for non_veg in _NON_VEG_ITEMS:
                    if non_veg in item_name_lower:
                        ambiguities.append({
                            "field": f"items:{item['name']}",
                            "description": (
                                f"Contradictory request: '{item['name']}' is non-vegetarian "
                                f"but vegetarian constraint is specified"
                            ),
                            "severity": "high",
                            "candidate_options": [
                                f"Remove {item['name']} from basket",
                                "Remove vegetarian constraint",
                            ],
                            "suggested_clarification": (
                                f"You asked for vegetarian items but also requested {item['name']}. "
                                f"Should I skip {item['name']} or remove the vegetarian restriction?"
                            ),
                        })
                        break

        return ambiguities

    def _detect_vague_quantities(self, text: str, items: list[dict]) -> list[dict]:
        """Detect vaguely specified quantities."""
        ambiguities: list[dict] = []
        text_lower = text.lower()

        # Check for vague quantifiers with no specific number
        vague_patterns = [
            (re.compile(r"\bsome\s+(\w+)\b", re.I), "some"),
            (re.compile(r"\ba\s+(?:few|bit\s+of|little)\s+(\w+)\b", re.I), "a few"),
            (re.compile(r"\bget\s+(\w+)\b", re.I), None),  # bare "get X" without quantity
        ]

        for pattern, quantifier in vague_patterns:
            for match in pattern.finditer(text):
                product = match.group(1).strip().lower()
                # Only flag if it matches a known category and wasn't parsed with a number
                if product in _CATEGORY_HINTS:
                    has_specific = any(
                        product in item["name"].lower() and item["quantity"] != 1.0
                        for item in items
                    )
                    if not has_specific and quantifier:
                        ambiguities.append({
                            "field": f"items:{product}",
                            "description": f"Vague quantity '{quantifier} {product}' — no specific amount",
                            "severity": "medium",
                            "candidate_options": [],
                            "suggested_clarification": f"How much {product} would you like? (e.g., 500g, 1kg)",
                        })

        return ambiguities


# ---------------------------------------------------------------------------
# DeterministicValidator
# ---------------------------------------------------------------------------

class DeterministicValidator:
    """Post-extraction validation and invariant enforcement (Spec Section 12.2)."""

    def validate(self, raw: dict, text: str, session_id: str, customer_id: Optional[str]) -> IntentContract:
        """Build and validate an IntentContract from raw extraction output."""
        now = datetime.now(timezone.utc)

        # Build model instances from raw dicts
        items = [IntentItem(**item) for item in raw.get("items", [])]

        budget = None
        if raw.get("budget"):
            budget = BudgetConstraint(**raw["budget"])

        dietary = [DietaryConstraint(**dc) for dc in raw.get("dietary_constraints", [])]

        brand_prefs = []
        for bp in raw.get("brand_preferences", []):
            brand_prefs.append(BrandPreference(**bp))

        sub_policy_raw = raw.get("substitution_policy")
        sub_policy = SubstitutionPolicy()
        if sub_policy_raw:
            sub_policy = SubstitutionPolicy(
                allow_substitutions=sub_policy_raw.get("allow_substitutions", True),
                brand_tolerance=BrandTolerance(sub_policy_raw.get("brand_tolerance", "usual_brands")),
                pack_size_tolerance=SubstitutionTolerance(sub_policy_raw.get("pack_size_tolerance", "reasonable")),
            )

        soft_prefs = []
        for sp in raw.get("soft_preferences", []):
            soft_prefs.append(SoftPreference(
                preference_type=PreferenceType(sp["preference_type"]),
                target=sp["target"],
                preference=sp["preference"],
                weight=sp.get("weight", 1.0),
            ))

        ambiguities = []
        for amb in raw.get("ambiguities", []):
            ambiguities.append(Ambiguity(
                field=amb["field"],
                description=amb["description"],
                severity=AmbiguitySeverity(amb["severity"]),
                candidate_options=amb.get("candidate_options", []),
                suggested_clarification=amb.get("suggested_clarification"),
            ))

        # Compute confidence: start at 1.0, deduct for ambiguities
        confidence = 1.0
        for amb in ambiguities:
            if amb.severity == AmbiguitySeverity.HIGH:
                confidence -= 0.3
            elif amb.severity == AmbiguitySeverity.MEDIUM:
                confidence -= 0.15
            elif amb.severity == AmbiguitySeverity.LOW:
                confidence -= 0.05
        confidence = max(0.0, min(1.0, confidence))

        is_greeting = bool(raw.get("is_greeting", False))

        # Flag missing critical info
        if not items and not raw.get("goal", "").strip() and not is_greeting:
            ambiguities.append(Ambiguity(
                field="goal",
                description="No specific items or clear goal could be extracted from the request",
                severity=AmbiguitySeverity.HIGH,
                suggested_clarification="Could you tell me what groceries you need?",
            ))
            confidence = max(0.0, confidence - 0.3)

        source_context = SourceContext(
            channel="whatsapp",
            raw_text=text,
            customer_id=customer_id,
            received_at=now,
        )

        # Build contract — Pydantic model_validator handles invariant sync
        contract = IntentContract(
            intent_id=str(uuid.uuid4()),
            session_id=session_id,
            goal=raw.get("goal", "greeting" if is_greeting else "grocery request"),
            is_greeting=is_greeting,
            items=items,
            budget=budget,
            dietary_constraints=dietary,
            brand_preferences=brand_prefs,
            substitution_policy=sub_policy,
            soft_preferences=soft_prefs,
            ambiguities=ambiguities,
            confidence=confidence,
            source_context=source_context,
            authorization_scope=AuthorizationScope(),
            created_at=now,
            updated_at=now,
            version=1,
        )

        return contract


# ---------------------------------------------------------------------------
# GeminiIntentExtractor — LLM Natural Language Intent Parser
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class GeminiIntentExtractor:
    """LLM-based natural language intent extractor using Google Gemini (Spec Section 12)."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self._api_key}"
            if self._api_key
            else None
        )

    def extract(self, text: str) -> Optional[dict]:
        """Extract structured intent fields using Gemini. Returns raw dict or None on failure."""
        if not self._url or "PYTEST_CURRENT_TEST" in os.environ:
            return None

        system_prompt = (
            "You are the Grocer WhatsApp natural language grocery intent parser.\n"
            "Given a user message on WhatsApp, extract a clean JSON object with this schema:\n"
            "{\n"
            '  "is_greeting": boolean (true ONLY if the user message is purely a greeting like \'hi\', \'hello\', \'hey\' with NO grocery items requested),\n'
            '  "goal": string (e.g. "grocery request", "dairy restock"),\n'
            '  "items": [\n'
            "    {\n"
            '      "name": string (clean product name, e.g. "Dairy Milk", "Milk", "Brown Bread"),\n'
            '      "quantity": number,\n'
            '      "unit": string ("units", "L", "kg", "g", "pack")\n'
            "    }\n"
            "  ],\n"
            '  "budget": number or null (e.g. 300 if \'under 300\', otherwise null),\n'
            '  "dietary_constraints": [string] (e.g. ["vegetarian"] if mentioned, otherwise [])\n'
            "}\n"
            "Never include conversational phrases (like 'i want', 'send me', 'bhai') in item names.\n"
            "Output strictly valid JSON only. Do not wrap in markdown fences."
        )

        try:
            payload = {
                "contents": [
                    {"parts": [{"text": f"{system_prompt}\n\nUser message: \"{text}\""}]}
                ]
            }
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(self._url, json=payload)
            if resp.status_code != 200:
                logger.warning("Gemini extraction returned status %d: %s", resp.status_code, resp.text[:120])
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0]:
                return None

            raw_text = parts[0]["text"].strip()
            clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text)
            clean_json = re.sub(r"\s*```$", "", clean_json)
            extracted = json.loads(clean_json)

            is_greeting = bool(extracted.get("is_greeting", False))

            items = []
            for item in extracted.get("items", []):
                name = str(item.get("name", "")).strip()
                if not name or name.lower() in _STOP_WORDS:
                    continue
                qty = float(item.get("quantity", 1.0))
                unit = _UNIT_MAP.get(str(item.get("unit", "units")).lower(), "units")
                items.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "quantity_rules": {"quantity_is_explicit": True},
                    "is_essential": True,
                })

            budget_val = extracted.get("budget")
            budget_dict = None
            if budget_val and isinstance(budget_val, (int, float)) and budget_val > 0:
                budget_dict = {"max_budget": float(budget_val), "currency": "INR", "is_hard": True}

            dietary = [
                {"tag": d.lower(), "is_hard": True}
                for d in extracted.get("dietary_constraints", [])
                if isinstance(d, str) and d.lower() in _DIETARY_TAGS
            ]

            return {
                "is_greeting": is_greeting,
                "goal": "greeting" if is_greeting else extracted.get("goal", "grocery request"),
                "items": [] if is_greeting else items,
                "budget": None if is_greeting else budget_dict,
                "dietary_constraints": [] if is_greeting else dietary,
                "brand_preferences": [],
                "substitution_policy": {},
                "soft_preferences": [],
                "ambiguities": [],
            }
        except Exception as exc:
            logger.warning("Gemini intent extraction failed, falling back to rule-based: %s", exc)
            return None


# ---------------------------------------------------------------------------
# IntentParser — public interface
# ---------------------------------------------------------------------------

class IntentParser:
    """Parse WhatsApp natural language into a validated IntentContract.

    Architecture (Spec Section 12):
        text → LLM (Gemini) / RuleBasedExtractor → DeterministicValidator → IntentContract

    The deterministic validator always has final authority.
    """

    def __init__(self) -> None:
        self._llm_extractor = GeminiIntentExtractor()
        self._rule_extractor = RuleBasedExtractor()
        self._validator = DeterministicValidator()

    def parse(
        self,
        text: str,
        session_id: str,
        customer_id: Optional[str] = None,
    ) -> IntentContract:
        """Parse natural language text into a validated IntentContract.

        Args:
            text: Raw WhatsApp message text.
            session_id: Active session identifier.
            customer_id: Optional customer profile ID for memory lookup.

        Returns:
            A fully validated IntentContract with confidence and ambiguity tracking.
        """
        # 1. Attempt LLM extraction first (handles messy natural language, Hinglish, conversational styles)
        raw = self._llm_extractor.extract(text)

        # 2. Fall back to deterministic rule-based extractor if offline or disabled
        if raw is None:
            raw = self._rule_extractor.extract(text)

        # 3. Validate, enforce invariants, and build contract
        contract = self._validator.validate(raw, text, session_id, customer_id)

        return contract
