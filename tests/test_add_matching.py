"""A named brand and size skip the second model call; everything else keeps it."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.candidate_evaluator import (
    CandidateEvaluationResult,
    ExtractedGroceryItem,
    IntentType,
)
from backend.agent.candidate_search import CandidateItem
from backend.channels import turn_add
from backend.channels.turn_add import _exact_brand_size_match, plan_add
from backend.integrations.commerce.schemas import SearchProductsData

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class RecordingWA:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send_text_message(self, to_wa_id: str, text: str) -> None:
        self.texts.append(text)

    async def send_quick_reply_buttons(
        self, to_wa_id: str, body_text: str, buttons: list
    ) -> None:
        self.texts.append(body_text)


def _client() -> FixtureSwiggyClient:
    raw = json.loads(
        (FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8")
    )
    return FixtureSwiggyClient(catalog_data=SearchProductsData(**raw["data"]))


def _ctx(client: FixtureSwiggyClient, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        conn=None,
        user_id="test-user",
        wa_id="919999999999",
        text=text,
        client=client,
        wa_client=RecordingWA(),
        address_id="addr_01HXYZ",
        history=[],
    )


def _candidate(spin_id: str) -> CandidateItem:
    return CandidateItem(
        spin_id=spin_id,
        sku_id=spin_id,
        product_id=spin_id,
        display_name="Amul Milk 1 L",
        brand_name="Amul",
        quantity_description="1 L",
        mrp_paise=7400,
        offer_price_paise=7200,
        is_in_stock=True,
    )


async def test_exact_brand_and_size_skips_the_second_model_call(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("the evaluator must not run for an exact brand+size match")

    monkeypatch.setattr(turn_add, "evaluate_customer_intents_batch", must_not_run)

    plan = await plan_add(
        _ctx(_client(), "add amul milk 500 ml"),
        SimpleNamespace(
            items=[{"query": "Amul milk 500 ml", "amount": 500, "unit": "ml"}]
        ),
        address_count=1,
    )

    assert [item.spin_id for item in plan.items_to_add] == ["spin_amul_500ml"]


@pytest.mark.parametrize(
    ("query", "amount", "unit", "spin_id"),
    [
        ("Nandini milk 500 ml", 500, "ml", "spin_nandini_500ml"),
        ("Aashirvaad atta 5 kg", 5, "kg", "spin_atta_5kg"),
        ("Maggi noodles 280 g", 280, "g", "spin_maggi_4pack"),
    ],
)
async def test_other_exact_products_also_skip(
    monkeypatch, query, amount, unit, spin_id
):
    def must_not_run(*args, **kwargs):
        raise AssertionError("the evaluator must not run for an exact brand+size match")

    monkeypatch.setattr(turn_add, "evaluate_customer_intents_batch", must_not_run)

    plan = await plan_add(
        _ctx(_client(), f"add {query}"),
        SimpleNamespace(items=[{"query": query, "amount": amount, "unit": unit}]),
        address_count=1,
    )

    assert [item.spin_id for item in plan.items_to_add] == [spin_id]


@pytest.mark.parametrize(
    "query",
    ["Lay's chips 50 g", "Amul milk"],
)
async def test_ambiguous_or_sizeless_queries_still_use_the_model(monkeypatch, query):
    calls = []

    def fake_evaluate(targets, address_count=1, message=None):
        calls.append(targets)
        return [
            CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=_candidate("spin_amul_1l"),
                source="llm",
            )
            for _target in targets
        ]

    monkeypatch.setattr(turn_add, "evaluate_customer_intents_batch", fake_evaluate)

    await plan_add(
        _ctx(_client(), f"add {query}"),
        SimpleNamespace(items=[{"query": query}]),
        address_count=1,
    )

    assert len(calls) == 1


async def test_vague_query_still_uses_the_model(monkeypatch):
    calls = []

    def fake_evaluate(targets, address_count=1, message=None):
        calls.append((targets, message))
        return [
            CandidateEvaluationResult(
                intent_type=IntentType.ADD_TO_BASKET,
                selected_candidate=_candidate("spin_amul_1l"),
                source="llm",
            )
            for _target in targets
        ]

    monkeypatch.setattr(turn_add, "evaluate_customer_intents_batch", fake_evaluate)

    plan = await plan_add(
        _ctx(_client(), "add milk"),
        SimpleNamespace(items=[{"query": "milk"}]),
        address_count=1,
    )

    assert len(calls) == 1
    assert [item.spin_id for item in plan.items_to_add] == ["spin_amul_1l"]


def test_two_same_brand_and_size_matches_do_not_skip():
    target = ExtractedGroceryItem(query="Amul milk 1 l")

    assert _exact_brand_size_match(
        target,
        [_candidate("spin_amul_a"), _candidate("spin_amul_b")],
    ) is None
