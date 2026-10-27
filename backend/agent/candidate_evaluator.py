"""Grocer v1.0 — Candidate Evaluator (one LLM brain).

Evaluates user queries against dark-store candidate items. The LLM goes through
`backend.agent.llm.complete_json`, never a provider SDK directly.
Implements:
1. Strict Rank-1 prevention (no blind res[0] on discretionary snacks/drinks or ambiguous matches).
2. Smart Kirana Defaults for vague staples (ADR 0004) with a physical [Change items] button.
3. Zero-Address Onboarding flow (ADR 0010) requesting a WhatsApp GPS pin.
4. Honest rupee formatting preserving paise; zero float formatting.
5. A deterministic fallback when the LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.candidate_search import CandidateItem
from backend.agent.llm import complete_json
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


class ExtractedGroceryItem(BaseModel):
    """Target grocery item parsed from customer dialogue."""

    model_config = ConfigDict(extra="ignore")

    query: str
    quantity: int = 1
    unit: str | None = None


class CandidateEvaluationResult(BaseModel):
    """Evaluation result detailing intent, selected item, or follow-up actions."""

    model_config = ConfigDict(extra="ignore")

    intent_type: IntentType
    selected_candidate: CandidateItem | None = None
    is_vague_staple: bool = False
    disambiguation_options: list[DisambiguationOption] = Field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
    conversational_response: str | None = None
    request_location_pin: bool = False


def _call_llm_candidate_evaluator(
    query: str,
    candidates: list[CandidateItem],
    address_count: int = 1,
) -> CandidateEvaluationResult | None:
    """Ask the configured LLM to evaluate candidates. Python still owns safety."""
    candidates_json = [c.model_dump() for c in candidates]
    system_prompt = f"""You evaluate product candidates for Grocer, a WhatsApp Instamart grocery assistant.
Saved address count: {address_count}
Rules:
1. If address_count == 0, return intent_type="zero_address_onboarding".
2. If query is a general inquiry (delivery fee, timing, stock inquiry), return intent_type="conversational_qa".
3. If query is a discretionary snack or drink without a specific brand or flavor (chips, cold coffee, biscuits), NEVER pick rank-1. Return intent_type="disambiguation" with 2-3 options.
4. If query is an unqualified staple (milk, eggs, bread, pyaz, atta), return intent_type="add_to_basket", is_vague_staple=true, and select the bestseller.
5. Match brand and size constraints accurately.
6. Never invent a spin_id. Use only ids from the candidates.

Return JSON only:
{{
  "intent_type": "add_to_basket" | "disambiguation" | "conversational_qa" | "zero_address_onboarding",
  "selected_spin_id": string | null,
  "is_vague_staple": boolean,
  "disambiguation_spin_ids": [string],
  "message": string | null
}}"""
    user_prompt = json.dumps(
        {"query": query, "address_count": address_count, "candidates": candidates_json}
    )
    result = complete_json(system_prompt, user_prompt)
    if not result.ok or not result.data:
        logger.warning(
            "Candidate evaluation LLM unavailable after %sms: %s",
            result.latency_ms,
            result.error,
        )
        return None
    parsed = result.data
    raw_intent = parsed.get("intent_type", "conversational_qa")
    try:
        intent = IntentType(raw_intent)
    except ValueError:
        return None
    logger.info(
        "candidate decision %s",
        json.dumps(
            {
                "query": query,
                "intent": intent.value,
                "selected_spin": parsed.get("selected_spin_id"),
                "candidates": len(candidates),
                "vague_staple": bool(parsed.get("is_vague_staple")),
                "latency_ms": result.latency_ms,
            },
            ensure_ascii=True,
        ),
    )

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
            # The model named an id outside the list. Never quietly take rank 1.
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

    return None


def evaluate_customer_intent(
    query: str,
    candidates: list[CandidateItem] | None = None,
    address_count: int = 1,
) -> CandidateEvaluationResult:
    """Evaluate a query against candidate dark-store items.

    Asks the configured LLM first; falls back to deterministic matching when the
    LLM is unavailable. The LLM never calls Swiggy and never picks outside the
    candidate list.
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

    # 2. Ask the configured LLM first
    llm_result = _call_llm_candidate_evaluator(
        query=raw_query,
        candidates=candidates,
        address_count=address_count,
    )
    if llm_result is not None:
        return llm_result

    # 3. Deterministic fallback when the LLM is unavailable
    words = re.findall(r"\b\w+\b", lower_query)

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
            if is_staple or len(candidates) == 1:
                selected = candidates[0]
            else:
                # A vague request with several distinct products must never
                # silently take rank 1.
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
