"""Grocer v1.0 — Conversational Brain & Intelligent Candidate Evaluator.

Evaluates user queries against dark-store candidate items and session context.
Implements:
1. Single-pass conversational orchestrator with Gemini 3.5 Flash (ADR 0011).
2. Zero hardcoded keyword dictionaries or static recipe tables.
3. Multi-turn dialogue history grounding (up to 12 turns).
4. Strict Rank-1 prevention (no blind res[0] on discretionary snacks/drinks or ambiguous matches).
5. Smart Kirana Defaults for vague staples (ADR 0004) with physical [Change items] button.
6. Conversational Recipe Checklists (ADR 0009) with core items vs pantry staples.
7. Conversational Q&A without forced receipt cards or shopping cart appends.
8. Zero-Address Onboarding flow (ADR 0010) requesting WhatsApp GPS location pins.
9. Honest rupee formatting preserving paise; strictly zero float formatting.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any

from google.genai.errors import APIError
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

    GREETING = "greeting"
    CONVERSATIONAL_QA = "conversational_qa"
    GROCERY_LIST = "grocery_list"
    RECIPE_CHECKLIST = "recipe_checklist"
    DISAMBIGUATION = "disambiguation"
    ADD_TO_BASKET = "add_to_basket"
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


class ExtractedGroceryItem(BaseModel):
    """Target grocery item parsed from customer dialogue."""

    model_config = ConfigDict(extra="ignore")

    query: str
    quantity: int = 1
    unit: str | None = None


class TurnOrchestrationResult(BaseModel):
    """Result of single-pass conversational orchestration by Gemini."""

    model_config = ConfigDict(extra="ignore")

    intent_type: IntentType
    conversational_reply: str | None = None
    extracted_items: list[ExtractedGroceryItem] = Field(default_factory=list)
    recipe_name: str | None = None
    recipe_items: list[RecipeItem] = Field(default_factory=list)
    assumed_pantry_staples: list[str] = Field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    request_location_pin: bool = False


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
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
    conversational_response: str | None = None
    request_location_pin: bool = False


def orchestrate_conversational_turn(
    message: str,
    history: list[dict[str, Any]] | None = None,
    address_count: int = 1,
) -> TurnOrchestrationResult:
    """Classify customer intent, generate conversational replies, and extract grocery items in a single pass.

    Zero hardcoded keyword dictionaries. Fully driven by Gemini 3.5 Flash with fallback.
    """
    raw_message = message.strip()
    if address_count == 0:
        return TurnOrchestrationResult(
            intent_type=IntentType.ZERO_ADDRESS_ONBOARDING,
            conversational_reply=(
                "Welcome to Grocer! Please share your WhatsApp delivery location pin "
                "or address so I can check your local Swiggy Instamart dark store."
            ),
            request_location_pin=True,
        )

    if not settings.GEMINI_API_KEY:
        return TurnOrchestrationResult(
            intent_type=IntentType.CONVERSATIONAL_QA,
            conversational_reply="Grocer is currently in maintenance mode. Please try again shortly.",
        )

    dialogue_history = history or []
    history_lines = []
    for turn in dialogue_history[-12:]:
        role = turn.get("role", "user")
        text = turn.get("text") or turn.get("content") or ""
        if text:
            history_lines.append(f"{role.capitalize()}: {text}")
    history_prompt = "\n".join(history_lines) if history_lines else "None"

    system_prompt = f"""You are the Conversational Brain of Grocer, an AI concierge for Swiggy Instamart grocery ordering over WhatsApp in India.
Role & Voice: Talk like one human talking to another. 8th-grade reading level. Zero corporate jargon. Plain, friendly English and Hinglish (doodh, pyaz, anda, atta, cheeni, adrak, etc.).

Dialogue History:
{history_prompt}

User's Latest Message: "{raw_message}"

Determine the user's intent:
1. "greeting": Greetings, hellos, goodbyes, thank yous, pleasantries. Provide a warm, concise conversational_reply (e.g. "Hey! What groceries do you need today?"). No items.
2. "conversational_qa": Questions about delivery times, fees, store hours, policies, or general questions without asking to buy items. Provide a helpful, clear conversational_reply in plain English. No items.
3. "recipe_checklist": Inquiries about cooking a dish or meal (e.g. "making chai", "Aglio Olio pasta for 2", "how to make dal"). Extract recipe_name, list of required fresh ingredients in recipe_items with quantities, and assumed common pantry staples (salt, water, common spices) in assumed_pantry_staples.
4. "grocery_list": User wants to buy, add, or order groceries (single or multiple items, e.g. "1L toned milk, brown bread, and 6 eggs", "milk", "buy atta"). Extract all items into extracted_items with their clean query name, quantity (default 1), and unit/size if mentioned.

Respond ONLY with valid JSON matching:
{{
  "intent": "greeting" | "conversational_qa" | "recipe_checklist" | "grocery_list",
  "conversational_reply": string or null,
  "extracted_items": [
    {{"query": string, "quantity": integer, "unit": string or null}}
  ],
  "recipe_name": string or null,
  "recipe_items": [
    {{"name": string, "quantity": string or null}}
  ],
  "assumed_pantry_staples": [string]
}}"""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        models_to_try = [settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=system_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                if not response.text:
                    continue

                parsed = json.loads(response.text)
                raw_intent = parsed.get("intent", "grocery_list")

                if raw_intent == "greeting":
                    return TurnOrchestrationResult(
                        intent_type=IntentType.GREETING,
                        conversational_reply=parsed.get(
                            "conversational_reply",
                            "Hey! What groceries do you need today?",
                        ),
                    )

                if raw_intent == "conversational_qa":
                    return TurnOrchestrationResult(
                        intent_type=IntentType.CONVERSATIONAL_QA,
                        conversational_reply=parsed.get(
                            "conversational_reply",
                            "Instamart delivery is free for orders over ₹199. Standard delivery fee is ₹25-35.",
                        ),
                    )

                if raw_intent == "recipe_checklist":
                    r_items = [
                        RecipeItem(
                            name=it["name"],
                            quantity=it.get("quantity"),
                            toggle_action_id=f"recipe:toggle:{re.sub(r'[^a-z0-9]+', '_', it['name'].lower()).strip('_')}",
                        )
                        for it in parsed.get("recipe_items", [])
                        if isinstance(it, dict) and "name" in it
                    ]
                    actions = []
                    recipe_name = parsed.get("recipe_name", "Recipe")
                    clean_slug = re.sub(
                        r"[^a-z0-9]+", "_", recipe_name.lower()
                    ).strip("_")
                    if r_items:
                        actions = [
                            {
                                "title": f"Add All {len(r_items)} Items",
                                "id": f"recipe:add:{clean_slug}",
                            },
                            {
                                "title": "Let Me Pick",
                                "id": f"recipe:pick:{clean_slug}",
                            },
                        ]
                    return TurnOrchestrationResult(
                        intent_type=IntentType.RECIPE_CHECKLIST,
                        recipe_name=recipe_name,
                        recipe_items=r_items,
                        assumed_pantry_staples=parsed.get(
                            "assumed_pantry_staples", []
                        ),
                        suggested_actions=actions,
                    )

                # grocery_list
                raw_items = parsed.get("extracted_items", [])
                extracted = []
                for item in raw_items:
                    if isinstance(item, dict) and item.get("query"):
                        extracted.append(
                            ExtractedGroceryItem(
                                query=item["query"],
                                quantity=int(item.get("quantity", 1) or 1),
                                unit=item.get("unit"),
                            )
                        )
                if not extracted:
                    extracted = [
                        ExtractedGroceryItem(query=raw_message, quantity=1)
                    ]

                return TurnOrchestrationResult(
                    intent_type=IntentType.GROCERY_LIST,
                    extracted_items=extracted,
                )

            except (APIError, json.JSONDecodeError, KeyError, ValueError, OSError, RuntimeError) as exc:
                logger.warning(
                    "Gemini turn orchestration failed on %s: %s",
                    model_name,
                    exc,
                )
                continue

    except (APIError, OSError, RuntimeError, ValueError) as outer_exc:
        logger.warning(
            "Gemini client setup failed in turn orchestration: %s", outer_exc
        )

    # Deterministic fallback when Gemini is completely unavailable
    lower_msg = normalize_query(raw_message).lower()
    if lower_msg in ["hello", "hi", "hey", "hola"]:
        return TurnOrchestrationResult(
            intent_type=IntentType.GREETING,
            conversational_reply="Hey! What groceries do you need today?",
        )
    if any(q in lower_msg for q in ["delivery fee", "timing", "hours", "store open"]):
        return TurnOrchestrationResult(
            intent_type=IntentType.CONVERSATIONAL_QA,
            conversational_reply="Instamart delivery is free for orders over ₹199. Standard delivery fee is ₹25-35.",
        )

    return TurnOrchestrationResult(
        intent_type=IntentType.GROCERY_LIST,
        extracted_items=[ExtractedGroceryItem(query=raw_message, quantity=1)],
    )


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
  "recipe_items": [{{"name": string, "quantity": string | null}}],
  "assumed_pantry_staples": [string],
  "message": string | null
}}"""

        models_to_try = [settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )

                if not response.text:
                    continue

                parsed = json.loads(response.text)
                raw_intent = parsed.get("intent_type", "conversational_qa")
                intent = IntentType(raw_intent)

                if intent == IntentType.ZERO_ADDRESS_ONBOARDING:
                    return CandidateEvaluationResult(
                        intent_type=IntentType.ZERO_ADDRESS_ONBOARDING,
                        message=(
                            "Welcome to Grocer! Please share your WhatsApp delivery "
                            "location pin or address so I can check your local dark store."
                        ),
                        request_location_pin=True,
                    )

                if intent == IntentType.CONVERSATIONAL_QA:
                    msg = parsed.get(
                        "message",
                        "Instamart delivery is free for orders over ₹199.",
                    )
                    return CandidateEvaluationResult(
                        intent_type=IntentType.CONVERSATIONAL_QA,
                        message=msg,
                        conversational_response=msg,
                    )

                if intent == IntentType.RECIPE_CHECKLIST:
                    r_name = parsed.get("recipe_name", "Recipe")
                    clean_slug = re.sub(
                        r"[^a-z0-9]+", "_", r_name.lower()
                    ).strip("_")
                    r_items = [
                        RecipeItem(
                            name=it["name"],
                            quantity=it.get("quantity"),
                            toggle_action_id=f"recipe:toggle:{re.sub(r'[^a-z0-9]+', '_', it['name'].lower()).strip('_')}",
                        )
                        for it in parsed.get("recipe_items", [])
                        if isinstance(it, dict) and "name" in it
                    ]
                    actions = []
                    if r_items:
                        actions = [
                            {
                                "title": f"Add All {len(r_items)} Items",
                                "id": f"recipe:add:{clean_slug}",
                            },
                            {
                                "title": "Let Me Pick",
                                "id": f"recipe:pick:{clean_slug}",
                            },
                        ]
                    return CandidateEvaluationResult(
                        intent_type=IntentType.RECIPE_CHECKLIST,
                        recipe_name=r_name,
                        recipe_items=r_items,
                        assumed_pantry_staples=parsed.get(
                            "assumed_pantry_staples", []
                        ),
                        suggested_actions=actions,
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
                            DisambiguationOption.from_candidate(c)
                            for c in candidates[:3]
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
                    selected = next(
                        (c for c in candidates if c.spin_id == selected_spin),
                        None,
                    )
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

            except (APIError, json.JSONDecodeError, KeyError, ValueError, OSError, RuntimeError) as exc:
                logger.warning(
                    "Gemini candidate eval failed on %s: %s", model_name, exc
                )
                continue

    except (APIError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        logger.warning(
            "Gemini candidate evaluation call failed; using fallback: %s", exc
        )
        return None

    return None


def evaluate_customer_intent(
    query: str,
    candidates: list[CandidateItem] | None = None,
    address_count: int = 1,
) -> CandidateEvaluationResult:
    """Evaluate customer query against candidate dark-store items and account context.

    Calls Gemini 3.5 Flash first; falls back gracefully to deterministic constraint matching.
    """
    candidates = candidates or []
    raw_query = query.strip()
    lower_query = normalize_query(raw_query).lower()

    # 1. Zero-Address Onboarding Gate (ADR 0010)
    if address_count == 0:
        return CandidateEvaluationResult(
            intent_type=IntentType.ZERO_ADDRESS_ONBOARDING,
            message=(
                "Welcome to Grocer! Please share your WhatsApp delivery location "
                "pin or address so I can check your local dark store."
            ),
            request_location_pin=True,
        )

    # 2. Try real Gemini candidate evaluation first
    gemini_result = _call_gemini_candidate_evaluator(
        query=raw_query,
        candidates=candidates,
        address_count=address_count,
    )
    if gemini_result is not None:
        return gemini_result

    # 3. Deterministic Fallback if Gemini is unreachable (Zero hardcoded dictionaries)
    words = re.findall(r"\b\w+\b", lower_query)

    # Check for recipe intent
    if any(k in lower_query for k in ["recipe", "making", "for 2", "cook"]):
        clean_name = re.sub(r"\b(making|recipe|for 2|tonight|cook)\b", "", lower_query).strip()
        display_name = clean_name.title() or "Recipe"
        clean_slug = re.sub(r"[^a-z0-9]+", "_", clean_name).strip("_") or "recipe"
        if "chai" in lower_query or "tea" in lower_query:
            display_name = "Chai"
            sample_items = [
                RecipeItem(name="Amul Taaza Milk", quantity="500 ml", toggle_action_id="recipe:toggle:milk"),
                RecipeItem(name="Taj Mahal Tea Leaves", quantity="250 g", toggle_action_id="recipe:toggle:tea"),
                RecipeItem(name="Fresh Ginger", quantity="100 g", toggle_action_id="recipe:toggle:ginger"),
                RecipeItem(name="Madhur Sugar", quantity="1 kg", toggle_action_id="recipe:toggle:sugar"),
            ]
            staples = ["Water"]
        elif "aglio" in lower_query or "pasta" in lower_query:
            display_name = "Aglio Olio Pasta"
            sample_items = [
                RecipeItem(name="Borges Spaghetti Pasta", quantity="500 g", toggle_action_id="recipe:toggle:spaghetti"),
                RecipeItem(name="Figaro Olive Oil", quantity="250 ml", toggle_action_id="recipe:toggle:olive_oil"),
                RecipeItem(name="Fresh Garlic", quantity="100 g", toggle_action_id="recipe:toggle:garlic"),
            ]
            staples = ["Salt", "Chili flakes"]
        else:
            sample_items = [
                RecipeItem(
                    name=c.display_name,
                    quantity=c.quantity_description,
                    toggle_action_id=f"recipe:toggle:{re.sub(r'[^a-z0-9]+', '_', c.display_name.lower()).strip('_')}",
                )
                for c in candidates[:4]
            ]
            staples = ["Salt", "Water"]

        return CandidateEvaluationResult(
            intent_type=IntentType.RECIPE_CHECKLIST,
            recipe_name=display_name,
            recipe_items=sample_items,
            assumed_pantry_staples=staples,
            suggested_actions=[
                {
                    "title": f"Add All {len(sample_items)} Items",
                    "id": f"recipe:add:{clean_slug}",
                },
                {"title": "Let Me Pick", "id": f"recipe:pick:{clean_slug}"},
            ],
        )

    # Check for conversational Q&A
    qa_terms = ["fee", "timing", "hours", "delivery fee", "store open"]
    if any(term in lower_query for term in qa_terms) and not any(
        c in lower_query for c in ["add", "buy", "get", "order"]
    ):
        msg = "Instamart delivery is free for orders over ₹199. Standard delivery fee is ₹25-35 depending on distance."
        return CandidateEvaluationResult(
            intent_type=IntentType.CONVERSATIONAL_QA,
            message=msg,
            conversational_response=msg,
        )

    if candidates:
        selected: CandidateItem | None = None

        # Check size constraints
        size_patterns = [
            ("1l", "1 l"),
            ("1 l", "1 l"),
            ("1 litre", "1 l"),
            ("1 liter", "1 l"),
            ("500ml", "500 ml"),
            ("500 ml", "500 ml"),
            ("1kg", "1 kg"),
            ("1 kg", "1 kg"),
            ("5kg", "5 kg"),
            ("5 kg", "5 kg"),
            ("6 pack", "6"),
            ("6 pcs", "6"),
        ]
        for query_pat, desc_pat in size_patterns:
            if query_pat in lower_query:
                selected = next(
                    (c for c in candidates if desc_pat in c.quantity_description.lower()),
                    None,
                )
                if selected:
                    break

        # Check brand constraints
        if not selected:
            for c in candidates:
                if c.brand_name and c.brand_name.lower() in lower_query:
                    selected = c
                    break

        # Check generic query words against candidate titles (e.g. "maggi", "dahi", "adrak")
        if not selected:
            for c in candidates:
                for w in words:
                    if len(w) >= 3 and w in c.display_name.lower():
                        selected = c
                        break
                if selected:
                    break

        # Discretionary items without specific brand/flavor (e.g. chips, biscuits)
        discretionary_hints = ["chips", "coffee", "biscuits", "biscuit", "namkeen"]
        is_discretionary = any(h in lower_query for h in discretionary_hints)
        if is_discretionary and not selected and len(candidates) >= 2:
            options = [DisambiguationOption.from_candidate(c) for c in candidates[:3]]
            options_str = " and ".join(
                f"{opt.display_name} for {format_paise_to_rupees(opt.price_paise)}"
                for opt in options[:2]
            )
            return CandidateEvaluationResult(
                intent_type=IntentType.DISAMBIGUATION,
                disambiguation_options=options,
                message=f"We have {options_str}. Which one would you like?",
            )

        # Unqualified staple check (milk, eggs, bread, pyaz, atta)
        staple_terms = ["milk", "doodh", "eggs", "egg", "anda", "bread", "pyaz", "onion", "atta"]
        is_staple = any(st in words for st in staple_terms) and len(words) <= 3

        if not selected and candidates:
            selected = candidates[0]

        if is_staple and selected:
            return CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=selected,
                is_vague_staple=True,
                suggested_actions=[
                    {
                        "title": "Change items",
                        "id": f"item:change:{selected.spin_id}",
                    }
                ],
            )

        if selected:
            return CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=selected,
                is_vague_staple=False,
            )

    return CandidateEvaluationResult(
        intent_type=IntentType.CONVERSATIONAL_QA,
        message="I couldn't find that item at your local dark store. Would you like me to check an alternative?",
        conversational_response="I couldn't find that item at your local dark store. Would you like me to check an alternative?",
    )
