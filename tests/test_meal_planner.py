"""Grocer v1.0 — Recipe plan: propose, price, and write only on a tap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.meal_planner import (
    build_meal_plan,
    decode_plan,
    encode_plan,
    resolve_plan_items,
)
from backend.agent.router import Capability, RoutingDecision, SafetyClass
from backend.integrations.commerce.schemas import SearchProductsData, ToolEnvelope

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> FixtureSwiggyClient:
    raw = json.loads((FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8"))
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return FixtureSwiggyClient(catalog_data=envelope.data)


def _decision() -> RoutingDecision:
    return RoutingDecision(
        capability=Capability.PLAN_MEAL,
        safety=SafetyClass.READ,
        confidence=0.95,
        items=[
            {"query": "milk", "quantity": 2},
            {"query": "bread", "quantity": 1},
        ],
        dish="breakfast",
        servings=2,
    )


@pytest.mark.asyncio
async def test_plan_shows_every_ingredient_and_waits_for_a_tap(swiggy_client):
    text, buttons = await build_meal_plan(_decision(), swiggy_client, "addr_01HXYZ")

    assert "Breakfast for 2" in text
    assert "Milk" in text
    assert "Bread" in text
    assert "×2" in text
    assert "Assuming you have salt, oil and common spices." in text
    assert buttons[0][1] == "Add all"
    assert buttons[1] == ("plan:pick", "Let me pick")

    token = buttons[0][0].removeprefix("plan:add:")
    assert decode_plan(token) == [("milk", 2), ("bread", 1)]


@pytest.mark.asyncio
async def test_add_all_rebuilds_the_same_plan_from_live_stock(swiggy_client):
    _text, buttons = await build_meal_plan(_decision(), swiggy_client, "addr_01HXYZ")
    token = buttons[0][0].removeprefix("plan:add:")

    items, error = await resolve_plan_items(swiggy_client, "addr_01HXYZ", token)

    assert error is None
    assert [(item.spin_id, item.quantity) for item in items] == [
        ("spin_amul_1l", 2),
        ("spin_bread_white", 1),
    ]


@pytest.mark.asyncio
async def test_missing_ingredient_blocks_the_whole_plan(swiggy_client):
    button_id = encode_plan([("milk", 1), ("unicorn steak", 1)])
    assert button_id is not None

    items, error = await resolve_plan_items(
        swiggy_client, "addr_01HXYZ", button_id.removeprefix("plan:add:")
    )

    assert items is None
    assert "unicorn steak" in error
    assert "Nothing was added" in error


def test_plan_button_stays_inside_whatsapp_limits():
    button_id = encode_plan([(f"ingredient number {i}", 2) for i in range(8)])
    assert button_id is not None
    assert len(button_id) <= 250
    assert decode_plan(button_id.removeprefix("plan:add:")) is not None
    assert decode_plan("not-base64") is None
    assert decode_plan("") is None
