"""The evaluator must say whether the model or the rules produced the pick."""

from __future__ import annotations

from backend.agent import candidate_evaluator
from backend.agent.candidate_search import CandidateItem
from backend.agent.llm import LLMResult


def _candidate() -> CandidateItem:
    return CandidateItem(
        spin_id="spin-milk-1l",
        sku_id="sku-milk-1l",
        product_id="prod-milk",
        display_name="Amul Milk 1L",
        brand_name="Amul",
        quantity_description="1 L",
        mrp_paise=7400,
        offer_price_paise=7200,
        is_in_stock=True,
    )


def test_model_path_is_marked_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        candidate_evaluator,
        "complete_json",
        lambda *args, **kwargs: LLMResult(
            {"intent_type": "add_to_basket", "selected_spin_id": "spin-milk-1l"},
            "groq",
            latency_ms=12,
        ),
    )

    result = candidate_evaluator.evaluate_customer_intent("milk", [_candidate()])

    assert result.source == "llm"


def test_fallback_path_is_marked(monkeypatch) -> None:
    monkeypatch.setattr(
        candidate_evaluator,
        "complete_json",
        lambda *args, **kwargs: LLMResult(None, "groq", "offline", latency_ms=8),
    )

    result = candidate_evaluator.evaluate_customer_intent("milk", [_candidate()])

    assert result.source == "fallback"
