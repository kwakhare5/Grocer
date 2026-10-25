"""Grocer v1.0 — Conversational Brain & Intelligent Candidate Evaluator.

Evaluates user queries against dark-store candidate items and session context.
Implements:
1. Strict Rank-1 prevention (no blind res[0] on discretionary snacks/drinks or ambiguous matches).
2. Smart Kirana Defaults for vague staples (ADR 0004) with physical [Change items] button.
3. Conversational Recipe Checklists (ADR 0009) with core items vs pantry staples and per-item toggles.
4. Conversational Q&A without forced receipt cards or shopping cart appends.
5. Zero-Address Onboarding flow (ADR 0010) requesting WhatsApp GPS location pins.
6. Honest rupee formatting preserving paise; strictly zero float formatting.
7. Gemini 3.5 Flash integration via official google.genai SDK.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.candidate_search import CandidateItem
from backend.config import settings
from backend.integrations.commerce.swiggy_client import normalize_query

logger = logging.getLogger(__name__)


def format_paise_to_rupees(paise: int) -> str:
    """Format integer paise to honest rupee string without float formatters or floor loss."""
    rupees = paise // 100
    fraction = paise % 100
    if fraction == 0:
        return f"₹{rupees}"
    return f"₹{rupees}.{fraction:02d}"


class IntentType(str, Enum):
    """Classification of customer intent in WhatsApp dialogue."""

    ADD_TO_BASKET = "add_to_basket"
    DISAMBIGUATION = "disambiguation"
    RECIPE_CHECKLIST = "recipe_checklist"
    CONVERSATIONAL_QA = "conversational_qa"
    ZERO_ADDRESS_ONBOARDING = "zero_address_onboarding"


class DisambiguationOption(BaseModel):
    """Candidate option presented to user during disambiguation."""

    model_config = ConfigDict(extra="ignore")

    spin_id: str
    display_name: str
    quantity_description: str
    price_paise: int

    @classmethod
    def from_candidate(cls, c: CandidateItem) -> DisambiguationOption:
        """Create option from candidate item."""
        return cls(
            spin_id=c.spin_id,
            display_name=c.display_name,
            quantity_description=c.quantity_description,
            price_paise=c.offer_price_paise,
        )


class RecipeItem(BaseModel):
    """Core ingredient item in a recipe checklist."""

    model_config = ConfigDict(extra="ignore")

    name: str
    quantity: str | None = None
    is_optional: bool = False
    toggle_action_id: str | None = None


class CandidateEvaluationResult(BaseModel):
    """Evaluation result detailing intent, selected item, or follow-up actions."""

    model_config = ConfigDict(extra="ignore")

    intent_type: IntentType
    selected_candidate: CandidateItem | None = None
    is_vague_staple: bool = False
    disambiguation_options: list[DisambiguationOption] = Field(default_factory=list)
    recipe_name: str | None = None
    recipe_items: list[RecipeItem] = Field(default_factory=list)
    assumed_pantry_staples: list[str] = Field(default_factory=list)
    suggested_actions: list[dict] = Field(default_factory=list)
    message: str | None = None
    request_location_pin: bool = False


# Known vague staple keywords (ADR 0004)
VAGUE_STAPLE_KEYWORDS: dict[str, str] = {
    "milk": "spin_amul_500ml",
    "doodh": "spin_amul_1l",
    "eggs": "spin_eggs_6",
    "egg": "spin_eggs_6",
    "anda": "spin_eggs_6",
    "bread": "spin_bread_white",
    "pyaz": "spin_onion_1kg",
    "onion": "spin_onion_1kg",
    "onions": "spin_onion_1kg",
    "kanda": "spin_onion_1kg",
    "atta": "spin_atta_5kg",
}

# High-variety discretionary categories requiring disambiguation (ADR 0004)
DISCRETIONARY_CATEGORIES: set[str] = {
    "chips",
    "cold coffee",
    "coffee",
    "biscuits",
    "biscuit",
    "soda",
    "namkeen",
}

# Canonical Recipe Definition (ADR 0009)
_CHAI_RECIPE: dict[str, Any] = {
    "name": "Chai",
    "items": [
        RecipeItem(
            name="Amul Taaza Milk",
            quantity="500 ml",
            toggle_action_id="recipe:toggle:milk",
        ),
        RecipeItem(
            name="Taj Mahal Tea Leaves",
            quantity="250 g",
            toggle_action_id="recipe:toggle:tea",
        ),
        RecipeItem(
            name="Fresh Ginger",
            quantity="100 g",
            toggle_action_id="recipe:toggle:ginger",
        ),
        RecipeItem(
            name="Madhur Sugar",
            quantity="1 kg",
            toggle_action_id="recipe:toggle:sugar",
        ),
    ],
    "assumed_staples": ["Water"],
    "add_action_id": "recipe:add:chai",
    "pick_action_id": "recipe:pick:chai",
}

_AGLIO_OLIO_RECIPE: dict[str, Any] = {
    "name": "Aglio Olio Pasta",
    "items": [
        RecipeItem(
            name="Borges Spaghetti Pasta",
            quantity="500 g",
            toggle_action_id="recipe:toggle:spaghetti",
        ),
        RecipeItem(
            name="Figaro Extra Virgin Olive Oil",
            quantity="250 ml",
            toggle_action_id="recipe:toggle:olive_oil",
        ),
        RecipeItem(
            name="Fresh Garlic",
            quantity="100 g",
            toggle_action_id="recipe:toggle:garlic",
        ),
        RecipeItem(
            name="Amul Parmesan Cheese Block",
            quantity="200 g",
            toggle_action_id="recipe:toggle:cheese",
        ),
    ],
    "assumed_staples": ["Salt", "Chili flakes"],
    "add_action_id": "recipe:add:aglio_olio",
    "pick_action_id": "recipe:pick:aglio_olio",
}

RECIPE_REGISTRY: dict[str, dict[str, Any]] = {
    "chai": _CHAI_RECIPE,
    "tea": _CHAI_RECIPE,
    "aglio olio": _AGLIO_OLIO_RECIPE,
}


def _call_gemini_candidate_evaluator(
    query: str,
    candidates: list[CandidateItem],
    address_count: int = 1,
) -> CandidateEvaluationResult | None:
    """Call Google Gemini 3.5 Flash to evaluate candidates conversationally."""
    if not settings.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        candidates_json = [c.model_dump() for c in candidates]

        prompt = f"""You are the Conversational Brain of Grocer, a WhatsApp Instamart grocery assistant.
User query: {query}
Saved address count: {address_count}
Available candidates in hyper-local dark store:
{json.dumps(candidates_json, indent=2)}

Rules:
1. If address_count == 0, return intent_type="zero_address_onboarding" requesting delivery location pin.
2. If query is a general inquiry (delivery fee, timing, stock inquiry), return intent_type="conversational_qa".
3. If query is a recipe (e.g. making chai, pasta), return intent_type="recipe_checklist".
4. If query is a discretionary snack/drink without specific brand/flavor (e.g. chips, cold coffee, biscuits), NEVER pick rank-1. Return intent_type="disambiguation" with 2-3 options.
5. If query is an unqualified staple (milk, eggs, bread, pyaz, atta), return intent_type="add_to_basket", is_vague_staple=true, and select bestseller.
6. Match brand and size constraints accurately.

Respond ONLY with valid JSON matching the schema:
{{
  "intent_type": "add_to_basket" | "disambiguation" | "recipe_checklist" | "conversational_qa" | "zero_address_onboarding",
  "selected_spin_id": string | null,
  "is_vague_staple": boolean,
  "disambiguation_spin_ids": [string],
  "recipe_name": string | null,
  "message": string | null
}}"""

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            return None

        parsed = json.loads(response.text)
        intent = IntentType(parsed.get("intent_type", "conversational_qa"))

        if intent == IntentType.ZERO_ADDRESS_ONBOARDING:
            return CandidateEvaluationResult(
                intent_type=IntentType.ZERO_ADDRESS_ONBOARDING,
                message="Welcome to Grocer! Please share your WhatsApp delivery location pin or address so I can check your local dark store.",
                request_location_pin=True,
            )

        if intent == IntentType.CONVERSATIONAL_QA:
            return CandidateEvaluationResult(
                intent_type=IntentType.CONVERSATIONAL_QA,
                message=parsed.get(
                    "message", "Instamart delivery is free for orders over ₹199."
                ),
            )

        if intent == IntentType.DISAMBIGUATION:
            opt_spins = parsed.get("disambiguation_spin_ids", [])
            options = [
                DisambiguationOption.from_candidate(c)
                for c in candidates
                if c.spin_id in opt_spins
            ]
            if not options and len(candidates) >= 2:
                options = [
                    DisambiguationOption.from_candidate(c) for c in candidates[:3]
                ]

            options_str = " and ".join(
                f"{opt.display_name} for {format_paise_to_rupees(opt.price_paise)}"
                for opt in options[:2]
            )
            return CandidateEvaluationResult(
                intent_type=IntentType.DISAMBIGUATION,
                disambiguation_options=options,
                message=f"We have {options_str}. Which one would you like?",
            )

        if intent == IntentType.ADD_TO_BASKET:
            selected_spin = parsed.get("selected_spin_id")
            selected = next((c for c in candidates if c.spin_id == selected_spin), None)
            if not selected and candidates:
                selected = candidates[0]

            is_vague = parsed.get("is_vague_staple", False)
            actions = []
            if is_vague and selected:
                actions.append(
                    {
                        "title": "Change items",
                        "id": f"item:change:{selected.spin_id}",
                    }
                )

            return CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=selected,
                is_vague_staple=is_vague,
                suggested_actions=actions,
            )

    except (APIError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        logger.warning(
            "Gemini candidate evaluation call failed; using deterministic fallback: %s",
            exc,
        )
        return None

    return None


def evaluate_customer_intent(
    query: str,
    candidates: list[CandidateItem],
    address_count: int = 1,
) -> CandidateEvaluationResult:
    """Evaluate customer query against candidate dark-store items and account context."""
    raw_query = query.strip()
    lower_query = normalize_query(raw_query).lower()

    # 1. Zero-Address Onboarding Gate (ADR 0010)
    if address_count == 0:
        return CandidateEvaluationResult(
            intent_type=IntentType.ZERO_ADDRESS_ONBOARDING,
            message="Welcome to Grocer! Please share your WhatsApp delivery location pin or address so I can check your local dark store.",
            request_location_pin=True,
        )

    # 2. Conversational Q&A Inquiry (PRD Journey 3)
    words_set = set(re.findall(r"\b\w+\b", lower_query))
    qa_word_triggers = {"fee", "charge", "charges", "timing", "hours"}
    qa_phrase_triggers = [
        "delivery fee",
        "store open",
        "open right now",
        "how much is delivery",
        "what is the delivery",
        "what addresses",
        "which address",
    ]
    is_qa = any(w in words_set for w in qa_word_triggers) or any(
        phrase in lower_query for phrase in qa_phrase_triggers
    )
    if is_qa and not any(cmd in lower_query for cmd in ["add", "buy", "get", "order"]):
        return CandidateEvaluationResult(
            intent_type=IntentType.CONVERSATIONAL_QA,
            message="Instamart delivery is free for orders over ₹199. Standard delivery fee is ₹25-35 depending on distance.",
        )

    # 3. Conversational Recipe Proposal (ADR 0009)
    recipe_indicators = ["making", "recipe", "for 2", "tonight", "cook"]
    for recipe_key, recipe_data in RECIPE_REGISTRY.items():
        if recipe_key in lower_query and any(
            ind in lower_query for ind in recipe_indicators
        ):
            num_items = len(recipe_data["items"])
            actions = [
                {
                    "title": f"Add All {num_items} Items",
                    "id": recipe_data["add_action_id"],
                },
                {"title": "Let Me Pick", "id": recipe_data["pick_action_id"]},
            ]
            return CandidateEvaluationResult(
                intent_type=IntentType.RECIPE_CHECKLIST,
                recipe_name=recipe_data["name"],
                recipe_items=recipe_data["items"],
                assumed_pantry_staples=recipe_data["assumed_staples"],
                suggested_actions=actions,
            )

    # 4. Discretionary High-Variety Disambiguation (ADR 0004 & Rank-1 Prevention)
    words = re.findall(r"\b\w+\b", lower_query)
    for category in DISCRETIONARY_CATEGORIES:
        if category in lower_query:
            specific_brands = [
                "lay's",
                "lays",
                "bingo",
                "nescafe",
                "sleepy owl",
                "parle-g",
                "good day",
                "oreo",
            ]
            is_specific = any(b in lower_query for b in specific_brands)
            if not is_specific and len(candidates) >= 2:
                options = [
                    DisambiguationOption.from_candidate(c) for c in candidates[:3]
                ]
                options_str = " and ".join(
                    f"{opt.display_name} for {format_paise_to_rupees(opt.price_paise)}"
                    for opt in options[:2]
                )
                message = f"We have {options_str}. Which one would you like?"
                return CandidateEvaluationResult(
                    intent_type=IntentType.DISAMBIGUATION,
                    disambiguation_options=options,
                    message=message,
                )

    # 5. Vague Staples Auto-Selection (ADR 0004) with [Change items] Button
    has_size_constraint = any(
        s in lower_query
        for s in [
            "1l",
            "1 l",
            "1 litre",
            "1 liter",
            "500ml",
            "500 ml",
            "1kg",
            "1 kg",
            "5kg",
            "5 kg",
            "6 pack",
            "pack of 6",
            "6 pcs",
        ]
    )
    has_brand_constraint = any(
        b in lower_query
        for b in [
            "amul",
            "nandini",
            "eggoz",
            "modern",
            "the health factory",
            "aashirvaad",
            "madhur",
            "mother dairy",
            "zero maida",
        ]
    )
    is_unqualified = not has_size_constraint and not has_brand_constraint

    if is_unqualified:
        for staple, default_spin in VAGUE_STAPLE_KEYWORDS.items():
            if staple in words and len(words) <= 3:
                match_cand = next(
                    (c for c in candidates if c.spin_id == default_spin), None
                )
                if not match_cand and candidates:
                    match_cand = candidates[0]

                if match_cand:
                    change_action = {
                        "title": "Change items",
                        "id": f"item:change:{match_cand.spin_id}",
                    }
                    return CandidateEvaluationResult(
                        intent_type=IntentType.ADD_TO_BASKET,
                        selected_candidate=match_cand,
                        is_vague_staple=True,
                        suggested_actions=[change_action],
                    )

    # 6. Specific Variant Matching with Strict Rank-1 Prevention
    if candidates:
        selected: CandidateItem | None = None

        # Match pack size constraints
        if (
            "1l" in lower_query
            or "1 l" in lower_query
            or "1 litre" in lower_query
            or "1 liter" in lower_query
        ):
            selected = next(
                (c for c in candidates if "1 l" in c.quantity_description.lower()),
                None,
            )
        elif "500ml" in lower_query or "500 ml" in lower_query:
            selected = next(
                (c for c in candidates if "500 ml" in c.quantity_description.lower()),
                None,
            )
        elif "5kg" in lower_query or "5 kg" in lower_query:
            selected = next(
                (c for c in candidates if "5 kg" in c.quantity_description.lower()),
                None,
            )
        elif "1kg" in lower_query or "1 kg" in lower_query:
            selected = next(
                (c for c in candidates if "1 kg" in c.quantity_description.lower()),
                None,
            )

        # Match brand if requested
        if not selected:
            for c in candidates:
                if c.brand_name and c.brand_name.lower() in lower_query:
                    selected = c
                    break

        # Rank-1 Prevention Guardrail: If no variant matched and multiple distinct items exist,
        # prompt the user conversationally rather than silently grabbing index 0
        if not selected:
            if len(candidates) >= 2:
                options = [
                    DisambiguationOption.from_candidate(c) for c in candidates[:3]
                ]
                options_str = " and ".join(
                    f"{opt.display_name} for {format_paise_to_rupees(opt.price_paise)}"
                    for opt in options[:2]
                )
                return CandidateEvaluationResult(
                    intent_type=IntentType.DISAMBIGUATION,
                    disambiguation_options=options,
                    message=f"We have {options_str}. Which one would you prefer?",
                )
            selected = candidates[0]

        return CandidateEvaluationResult(
            intent_type=IntentType.ADD_TO_BASKET,
            selected_candidate=selected,
            is_vague_staple=False,
        )

    # No candidates matched
    return CandidateEvaluationResult(
        intent_type=IntentType.CONVERSATIONAL_QA,
        message="I couldn't find that item at your local dark store. Would you like me to check an alternative?",
    )
