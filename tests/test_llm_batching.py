"""Grocer v1.0 — One batched item evaluation and one Groq queue.

Pure parsing and orchestration tests. No network, no database, no live model.
"""

from __future__ import annotations

import httpx
import pytest

from backend.agent import candidate_evaluator
from backend.agent.candidate_evaluator import (
    CandidateEvaluationResult,
    IntentType,
    evaluate_customer_intents_batch,
    parse_batch_evaluations,
)
from backend.agent.candidate_search import CandidateItem
from backend.agent.llm import (
    LLMResult,
    _GroqGate,
    _parse_duration_seconds,
    _retry_wait_seconds,
)

pytestmark = pytest.mark.scripted


def _candidate(spin_id: str, name: str) -> CandidateItem:
    return CandidateItem(
        spin_id=spin_id,
        sku_id=f"sku_{spin_id}",
        product_id=f"prod_{spin_id}",
        display_name=name,
        quantity_description="1 pack",
        mrp_paise=1000,
        offer_price_paise=900,
        is_in_stock=True,
    )


MILK = _candidate("spin_milk", "Amul Milk")
BREAD = _candidate("spin_bread", "Modern Bread")


def test_groq_duration_parser_handles_seconds_ms_and_minutes():
    assert _parse_duration_seconds("7.5s") == 7.5
    assert _parse_duration_seconds("250ms") == 0.25
    assert _parse_duration_seconds("1m2.5s") == 62.5
    assert _parse_duration_seconds("2") == 2.0
    assert _parse_duration_seconds(None) is None
    assert _parse_duration_seconds("soon") is None


def test_retry_wait_reads_headers_then_the_error_message():
    header = httpx.Response(429, headers={"retry-after": "2.5"})
    assert _retry_wait_seconds(header) == 2.5

    reset = httpx.Response(
        429, headers={"x-ratelimit-reset-tokens": "1m2.5s"}
    )
    assert _retry_wait_seconds(reset) == 60.0

    body = httpx.Response(
        429,
        json={
            "error": {
                "message": "Rate limit reached. Please try again in 7.5s."
            }
        },
    )
    assert _retry_wait_seconds(body) == 7.5


def test_gate_refuses_a_wait_that_would_blow_the_turn_budget():
    import time

    gate = _GroqGate()
    gate.block_for(60)
    assert gate.wait(deadline=time.monotonic() + 5) is False


def test_batch_parser_keeps_each_index_and_rejects_a_bad_spin():
    targets = [("milk", [MILK]), ("bread", [BREAD])]
    parsed = parse_batch_evaluations(
        {
            "items": [
                {
                    "index": 0,
                    "intent_type": "add_to_basket",
                    "selected_spin_id": "spin_milk",
                    "is_vague_staple": True,
                },
                {
                    "index": 1,
                    "intent_type": "add_to_basket",
                    "selected_spin_id": "spin_does_not_exist",
                },
            ]
        },
        targets,
    )
    assert parsed[0] is not None
    assert parsed[0].selected_candidate is not None
    assert parsed[0].selected_candidate.spin_id == "spin_milk"
    assert parsed[0].is_vague_staple is True
    assert parsed[1] is None


def test_batch_parser_marks_missing_entries_as_none():
    parsed = parse_batch_evaluations(
        {"items": [{"index": 1, "intent_type": "disambiguation"}]},
        [("milk", [MILK]), ("bread", [BREAD])],
    )
    assert parsed[0] is None
    assert parsed[1] is not None
    assert parsed[1].intent_type is IntentType.DISAMBIGUATION


def test_one_batch_call_selects_every_item(monkeypatch):
    calls: list[str] = []

    def fake_complete(
        system_prompt: str, user_prompt: str, provider: str | None = None
    ) -> LLMResult:
        calls.append(user_prompt)
        return LLMResult(
            {
                "items": [
                    {
                        "index": 0,
                        "intent_type": "add_to_basket",
                        "selected_spin_id": "spin_milk",
                    },
                    {
                        "index": 1,
                        "intent_type": "add_to_basket",
                        "selected_spin_id": "spin_bread",
                    },
                ]
            },
            "groq",
        )

    monkeypatch.setattr(candidate_evaluator, "complete_json", fake_complete)
    results = evaluate_customer_intents_batch(
        [("milk", [MILK]), ("bread", [BREAD])]
    )

    assert len(calls) == 1
    assert [r.selected_candidate.spin_id for r in results] == [
        "spin_milk",
        "spin_bread",
    ]


def test_a_malformed_batch_falls_back_without_a_second_call(monkeypatch):
    calls = 0

    def fake_complete(
        system_prompt: str, user_prompt: str, provider: str | None = None
    ) -> LLMResult:
        nonlocal calls
        calls += 1
        return LLMResult({"items": []}, "groq")

    monkeypatch.setattr(candidate_evaluator, "complete_json", fake_complete)
    results = evaluate_customer_intents_batch(
        [("milk", [MILK]), ("bread", [BREAD])]
    )

    assert calls == 1
    assert all(isinstance(result, CandidateEvaluationResult) for result in results)
    assert [r.selected_candidate.spin_id for r in results] == [
        "spin_milk",
        "spin_bread",
    ]
