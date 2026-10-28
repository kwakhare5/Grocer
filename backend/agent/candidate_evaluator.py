"""Grocer — Candidate Evaluator (one LLM brain).

Evaluates user queries against dark-store candidate items. The LLM goes through
`backend.agent.llm.complete_json`, never a provider SDK directly.
Implements:
1. Strict Rank-1 prevention (no blind res[0] on discretionary snacks/drinks or ambiguous matches).
2. Smart Kirana Defaults for vague staples (ADR 0004) with a physical [Change items] button.
3. Zero-address and conversational results, with copy owned by the router.
4. Honest rupee formatting preserving paise; zero float formatting.
5. A deterministic fallback when the LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

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

    CONVERSATIONAL_QA = "conversational_qa"
    GROCERY_LIST = "grocery_list"
    DISAMBIGUATION = "disambiguation"
    ADD_TO_BASKET = "add_to_basket"
    ZERO_ADDRESS_ONBOARDING = "zero_address_onboarding"


class ExtractedGroceryItem(BaseModel):
    """Target grocery item parsed from customer dialogue."""

    model_config = ConfigDict(extra="ignore")

    query: str
    quantity: int = 1
    amount: float | None = None
    unit: str | None = None


class CandidateEvaluationResult(BaseModel):
    """Evaluation result detailing intent, selected item, or follow-up actions."""

    model_config = ConfigDict(extra="ignore")

    intent_type: IntentType
    selected_candidate: CandidateItem | None = None
    is_vague_staple: bool = False


_CANDIDATE_RULES = """Rules:
1. If address_count == 0, return intent_type="zero_address_onboarding".
2. If query is a general inquiry (delivery fee, timing, stock inquiry), return intent_type="conversational_qa".
3. If query is a discretionary snack or drink without a specific brand or flavor (chips, cold coffee, biscuits), NEVER pick rank-1. Return intent_type="disambiguation" with 2-3 options.
4. If query is an unqualified staple (milk, eggs, bread, pyaz, atta), return intent_type="add_to_basket", is_vague_staple=true, and select the bestseller.
5. Match brand and size constraints accurately.
6. Never invent a spin_id. Use only ids from the candidates."""


def _single_system_prompt(address_count: int) -> str:
    return (
        "You evaluate product candidates for Grocer, a WhatsApp Instamart grocery assistant.\n"
        f"Saved address count: {address_count}\n"
        f"{_CANDIDATE_RULES}\n\n"
        "Return JSON only:\n"
        '{"intent_type": "add_to_basket" | "disambiguation" | "conversational_qa" | '
        '"zero_address_onboarding", "selected_spin_id": string | null, '
        '"is_vague_staple": boolean}'
    )


def _batch_system_prompt(address_count: int) -> str:
    return (
        "You evaluate product candidates for Grocer, a WhatsApp Instamart grocery assistant.\n"
        f"Saved address count: {address_count}\n"
        f"{_CANDIDATE_RULES}\n\n"
        "Evaluate every item in the list. Use its index. Never merge items.\n"
        "Use the customer's full message for brand, size and flavour hints.\n"
        "Return JSON only:\n"
        '{"items": [{"index": <int>, "intent_type": "add_to_basket" | '
        '"disambiguation" | "conversational_qa" | "zero_address_onboarding", '
        '"selected_spin_id": string | null, "is_vague_staple": boolean}]}'
    )


def _call_llm_candidate_evaluator(
    query: str,
    candidates: list[CandidateItem],
    address_count: int = 1,
    message: str | None = None,
) -> CandidateEvaluationResult | None:
    """Ask the configured LLM to evaluate candidates. Python still owns safety."""
    candidates_json = [c.model_dump() for c in candidates]
    system_prompt = _single_system_prompt(address_count)
    user_prompt = json.dumps(
        {
            "query": query,
            "message": message,
            "address_count": address_count,
            "candidates": candidates_json,
        }
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
        return CandidateEvaluationResult(intent_type=IntentType.ZERO_ADDRESS_ONBOARDING)

    if intent == IntentType.CONVERSATIONAL_QA:
        return CandidateEvaluationResult(intent_type=IntentType.CONVERSATIONAL_QA)

    if intent == IntentType.DISAMBIGUATION:
        return CandidateEvaluationResult(intent_type=IntentType.DISAMBIGUATION)

    if intent == IntentType.ADD_TO_BASKET:
        selected_spin = parsed.get("selected_spin_id")
        selected = next(
            (c for c in candidates if c.spin_id == selected_spin),
            None,
        )
        if not selected and candidates:
            return CandidateEvaluationResult(intent_type=IntentType.DISAMBIGUATION)

        return CandidateEvaluationResult(
            intent_type=IntentType.ADD_TO_BASKET,
            selected_candidate=selected,
            is_vague_staple=bool(parsed.get("is_vague_staple", False)),
        )

    return None


def evaluate_customer_intent(
    query: str,
    candidates: list[CandidateItem] | None = None,
    address_count: int = 1,
    message: str | None = None,
) -> CandidateEvaluationResult:
    """Evaluate a query against candidate dark-store items.

    Asks the configured LLM first; falls back to deterministic matching when the
    LLM is unavailable. The LLM never calls Swiggy and never picks outside the
    candidate list.
    """
    candidates = candidates or []

    # 1. Zero-Address Onboarding Gate (ADR 0010)
    if address_count == 0:
        return CandidateEvaluationResult(intent_type=IntentType.ZERO_ADDRESS_ONBOARDING)

    # 2. Ask the configured LLM first
    llm_result = _call_llm_candidate_evaluator(
        query=query,
        candidates=candidates,
        address_count=address_count,
        message=message,
    )
    if llm_result is not None:
        return llm_result

    return _deterministic_evaluate(query, candidates, address_count)


_NOISE_QUERY_WORDS = frozenset(
    {
        "and", "the", "for", "with", "of", "pack", "packs", "packet", "packets",
        "kg", "gm", "gms", "gram", "grams", "ml", "ltr", "litre", "litres",
        "liter", "liters", "pcs", "piece", "pieces", "dozen", "count",
    }
)


def _deterministic_evaluate(
    query: str,
    candidates: list[CandidateItem] | None = None,
    address_count: int = 1,
) -> CandidateEvaluationResult:
    """Ranking rules when the model is unavailable or a batch entry is bad."""
    candidates = candidates or []
    if address_count == 0:
        return CandidateEvaluationResult(intent_type=IntentType.ZERO_ADDRESS_ONBOARDING)
    lower_query = normalize_query(query.strip()).lower()
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

        # Rank by how many of the customer's words the candidate matches, so a
        # qualifier ("brown bread") outranks a candidate that shares one word.
        if not selected:
            ranked: list[tuple[int, int, CandidateItem]] = []
            for order, candidate in enumerate(candidates):
                haystack = " ".join(
                    (
                        candidate.display_name or "",
                        candidate.brand_name or "",
                        candidate.quantity_description or "",
                    )
                ).lower()
                score = sum(
                    1
                    for w in words
                    if len(w) >= 3
                    and w not in _NOISE_QUERY_WORDS
                    and w in haystack
                )
                ranked.append((score, -order, candidate))
            best = max(ranked, key=lambda row: (row[0], row[1]))
            if best[0] > 0:
                selected = best[2]

        # Discretionary items without specific brand/flavor (e.g. chips, biscuits)
        discretionary_hints = ["chips", "coffee", "biscuits", "biscuit", "namkeen"]
        is_discretionary = any(h in lower_query for h in discretionary_hints)
        if is_discretionary and not selected and len(candidates) >= 2:
            return CandidateEvaluationResult(intent_type=IntentType.DISAMBIGUATION)

        # Unqualified staple check (milk, eggs, bread, pyaz, atta)
        staple_terms = ["milk", "doodh", "eggs", "egg", "anda", "bread", "pyaz", "onion", "atta"]
        is_staple = any(st in words for st in staple_terms) and len(words) <= 3

        if not selected and candidates:
            if is_staple or len(candidates) == 1:
                selected = candidates[0]
            else:
                # A vague request with several distinct products must never
                # silently take rank 1.
                return CandidateEvaluationResult(intent_type=IntentType.DISAMBIGUATION)

        if is_staple and selected:
            return CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=selected,
                is_vague_staple=True,
            )

        if selected:
            return CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=selected,
                is_vague_staple=False,
            )

    return CandidateEvaluationResult(intent_type=IntentType.CONVERSATIONAL_QA)


def _parse_evaluation(
    parsed: dict[str, Any],
    candidates: list[CandidateItem],
) -> CandidateEvaluationResult | None:
    raw_intent = parsed.get("intent_type", "conversational_qa")
    try:
        intent = IntentType(raw_intent)
    except ValueError:
        return None

    if intent is IntentType.ADD_TO_BASKET:
        selected_spin = parsed.get("selected_spin_id")
        selected = next(
            (c for c in candidates if c.spin_id == selected_spin),
            None,
        )
        if selected is None:
            return None
        return CandidateEvaluationResult(
            intent_type=intent,
            selected_candidate=selected,
            is_vague_staple=bool(parsed.get("is_vague_staple", False)),
        )

    return CandidateEvaluationResult(intent_type=intent)


def parse_batch_evaluations(
    payload: dict[str, Any] | None,
    targets: list[tuple[str, list[CandidateItem]]],
) -> list[CandidateEvaluationResult | None]:
    """Parse a batch answer by index. A missing or bad entry stays None."""
    results: list[CandidateEvaluationResult | None] = [None] * len(targets)
    if not isinstance(payload, dict):
        return results

    entries = payload.get("items")
    if not isinstance(entries, list):
        return results

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(targets):
            results[index] = _parse_evaluation(entry, targets[index][1])
    return results


def evaluate_customer_intents_batch(
    targets: list[tuple[str, list[CandidateItem]]],
    address_count: int = 1,
    message: str | None = None,
) -> list[CandidateEvaluationResult]:
    """Evaluate every item in a turn with one model call.

    One call instead of one per item keeps a multi-item add inside the free
    tier. Any missing or invalid entry falls back to the deterministic rules,
    with no extra model call.
    """
    targets = [(query, candidates or []) for query, candidates in targets]
    if not targets:
        return []
    if len(targets) == 1:
        return [
            evaluate_customer_intent(
                targets[0][0],
                targets[0][1],
                address_count=address_count,
                message=message,
            )
        ]

    items = [
        {
            "index": index,
            "query": query,
            "candidates": [candidate.model_dump() for candidate in candidates],
        }
        for index, (query, candidates) in enumerate(targets)
    ]
    result = complete_json(
        _batch_system_prompt(address_count),
        json.dumps(
            {
                "message": message,
                "address_count": address_count,
                "items": items,
            }
        ),
    )
    parsed = parse_batch_evaluations(result.data, targets)
    final: list[CandidateEvaluationResult] = []
    fallbacks = 0
    for index, (query, candidates) in enumerate(targets):
        if parsed[index] is None:
            fallbacks += 1
            final.append(_deterministic_evaluate(query, candidates, address_count))
        else:
            final.append(parsed[index])

    logger.info(
        "batch candidate decision %s",
        json.dumps(
            {
                "items": len(targets),
                "selected": [
                    item.selected_candidate.spin_id if item.selected_candidate else None
                    for item in final
                ],
                "fallbacks": fallbacks,
                "latency_ms": result.latency_ms,
                "error": result.error,
            },
            ensure_ascii=True,
        ),
    )
    return final
