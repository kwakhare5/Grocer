"""Grocer v1.0 — Recipe plan: amounts to packs, stored plan, writes only on a tap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.meal_planner import (
    build_meal_plan,
    packs_for,
    parse_pick_indexes,
    plan_items,
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


def _decision(
    items: list[dict] | None = None,
    dish: str = "breakfast",
    servings: int = 2,
) -> RoutingDecision:
    return RoutingDecision(
        capability=Capability.PLAN_MEAL,
        safety=SafetyClass.READ,
        confidence=0.95,
        items=items
        or [
            {"query": "milk", "quantity": 2},
            {"query": "bread", "quantity": 1},
        ],
        dish=dish,
        servings=servings,
    )


def test_amounts_become_whole_packs():
    assert packs_for(250, "g", "200 g") == 2
    assert packs_for(1.5, "l", "1 L") == 2
    assert packs_for(1, "kg", "500 g") == 2
    assert packs_for(6, "pieces", "6 pcs") == 1
    assert packs_for(12, "pieces", "6 pcs") == 2
    assert packs_for(250, "g", "1 L") is None
    assert packs_for(250, "g", "family pack") is None
    assert packs_for(None, None, "1 L") is None


def test_numbered_replies_read_against_the_plan():
    assert parse_pick_indexes("1 and 3", 3) == [1, 3]
    assert parse_pick_indexes("1, 3", 3) == [1, 3]
    assert parse_pick_indexes("1 3", 3) == [1, 3]
    assert parse_pick_indexes("2", 3) == [2]
    assert parse_pick_indexes("1 and 1", 3) == [1]
    assert parse_pick_indexes("1 and 9", 3) is None
    assert parse_pick_indexes("0", 3) is None
    assert parse_pick_indexes("add 2 milk", 3) is None
    assert parse_pick_indexes("", 3) is None
    assert parse_pick_indexes("1", 0) is None


def test_stored_plan_shape_is_validated():
    plan = {"items": [{"query": "milk", "packs": 1}, "junk", {"packs": 2}]}
    assert [row["query"] for row in plan_items(plan)] == ["milk"]
    assert plan_items(None) == []
    assert plan_items("not a plan") == []
    assert plan_items({"items": "nope"}) == []


@pytest.mark.asyncio
async def test_plan_shows_every_ingredient_and_waits_for_a_tap(swiggy_client):
    text, buttons, plan = await build_meal_plan(
        _decision(), swiggy_client, "addr_01HXYZ"
    )

    assert "Breakfast for 2" in text
    assert "Milk" in text
    assert "Bread" in text
    assert "×2" in text
    assert "Assuming you have salt, oil and common spices." in text
    assert buttons == [("plan:add", "Add all"), ("plan:pick", "Let me pick")]
    assert plan is not None
    assert plan["dish"] == "breakfast"
    assert [row["spin_id"] for row in plan["items"]] == [
        "spin_amul_1l",
        "spin_bread_white",
    ]
    assert plan["total_paise"] == (72 * 2 + 45) * 100


@pytest.mark.asyncio
async def test_amounts_drive_the_pack_counts(swiggy_client):
    decision = _decision(
        items=[
            {"query": "cheese", "amount": 250, "unit": "g"},
            {"query": "milk", "amount": 1.5, "unit": "l"},
        ],
        dish="pasta",
        servings=4,
    )
    text, _buttons, plan = await build_meal_plan(decision, swiggy_client, "addr_01HXYZ")

    assert plan is not None
    assert [row["packs"] for row in plan["items"]] == [2, 2]
    assert plan["total_paise"] == (130 * 2 + 72 * 2) * 100
    assert "₹404" in text


@pytest.mark.asyncio
async def test_missing_ingredient_is_named_and_numbers_stay_in_order(swiggy_client):
    decision = _decision(
        items=[
            {"query": "milk", "quantity": 1},
            {"query": "unicorn steak", "quantity": 1},
            {"query": "bread", "quantity": 1},
        ]
    )
    text, buttons, plan = await build_meal_plan(decision, swiggy_client, "addr_01HXYZ")

    assert plan is not None
    assert "1. Amul" in text
    assert "2. Modern" in text
    assert "3." not in text
    assert "Not at this store: unicorn steak." in text
    assert buttons[0] == ("plan:add", "Add in-stock")


@pytest.mark.asyncio
async def test_add_all_rebuilds_the_same_plan_from_live_stock(swiggy_client):
    _text, _buttons, plan = await build_meal_plan(
        _decision(), swiggy_client, "addr_01HXYZ"
    )

    items, missing, error = await resolve_plan_items(swiggy_client, "addr_01HXYZ", plan)

    assert error is None
    assert missing == []
    assert [(item.spin_id, item.quantity) for item in items] == [
        ("spin_amul_1l", 2),
        ("spin_bread_white", 1),
    ]


@pytest.mark.asyncio
async def test_stored_spin_wins_over_the_first_result(swiggy_client):
    plan = {
        "items": [
            {
                "query": "milk",
                "packs": 1,
                "spin_id": "spin_nandini_500ml",
                "sku_id": "sku_nandini",
                "name": "Nandini Toned Fresh Milk (500 ml)",
                "size": "500 ml",
                "price_paise": 24,
            }
        ]
    }

    items, missing, error = await resolve_plan_items(swiggy_client, "addr_01HXYZ", plan)

    assert error is None
    assert missing == []
    assert [item.spin_id for item in items] == ["spin_nandini_500ml"]


@pytest.mark.asyncio
async def test_missing_ingredient_blocks_the_whole_plan(swiggy_client):
    plan = {
        "items": [
            {"query": "milk", "packs": 1},
            {"query": "unicorn steak", "packs": 1},
        ]
    }

    items, missing, error = await resolve_plan_items(swiggy_client, "addr_01HXYZ", plan)

    assert items == []
    assert missing == ["unicorn steak"]
    assert "unicorn steak" in error
    assert "Nothing was added" in error


@pytest.mark.asyncio
async def test_pick_adds_only_the_chosen_rows(swiggy_client):
    plan = {
        "items": [
            {"query": "milk", "packs": 1},
            {"query": "bread", "packs": 1},
        ]
    }

    items, missing, error = await resolve_plan_items(
        swiggy_client, "addr_01HXYZ", plan, [2]
    )

    assert error is None
    assert missing == []
    assert [(item.spin_id, item.quantity) for item in items] == [
        ("spin_bread_white", 1)
    ]


@pytest.mark.asyncio
async def test_pick_adds_the_rest_and_names_the_missing(swiggy_client):
    plan = {
        "items": [
            {"query": "milk", "packs": 1},
            {"query": "unicorn steak", "packs": 1},
        ]
    }

    items, missing, error = await resolve_plan_items(
        swiggy_client, "addr_01HXYZ", plan, [1, 2]
    )

    assert error is None
    assert missing == ["unicorn steak"]
    assert [item.spin_id for item in items] == ["spin_amul_1l"]


@pytest.mark.asyncio
async def test_a_gone_sku_blocks_add_all_instead_of_swapping(swiggy_client):
    plan = {
        "items": [
            {
                "query": "milk",
                "packs": 1,
                "spin_id": "spin_amul_gone",
                "sku_id": "sku_gone",
                "name": "Amul milk (1 L)",
                "size": "1 L",
                "price_paise": 7200,
            }
        ]
    }

    items, missing, error = await resolve_plan_items(swiggy_client, "addr_01HXYZ", plan)

    assert items == []
    assert missing == ["milk"]
    assert "Nothing was added" in error


@pytest.mark.asyncio
async def test_a_gone_sku_is_named_in_a_pick(swiggy_client):
    plan = {
        "items": [
            {"query": "milk", "packs": 1, "spin_id": "spin_amul_gone"},
            {"query": "bread", "packs": 1, "spin_id": "spin_bread_white"},
        ]
    }

    items, missing, error = await resolve_plan_items(
        swiggy_client, "addr_01HXYZ", plan, [1, 2]
    )

    assert error is None
    assert missing == ["milk"]
    assert [(item.spin_id, item.quantity) for item in items] == [
        ("spin_bread_white", 1)
    ]


@pytest.mark.asyncio
async def test_extra_ingredients_are_named_not_dropped(swiggy_client):
    decision = _decision(
        items=[
            {"query": "milk", "amount": 1, "unit": "l"},
            {"query": "bread", "amount": 400, "unit": "g"},
            {"query": "cheese", "amount": 200, "unit": "g"},
            {"query": "curd", "amount": 400, "unit": "g"},
            {"query": "sugar", "amount": 1, "unit": "kg"},
            {"query": "ginger", "amount": 100, "unit": "g"},
            {"query": "garlic", "amount": 100, "unit": "g"},
            {"query": "tea", "amount": 250, "unit": "g"},
            {"query": "onion", "amount": 1, "unit": "kg"},
        ],
        dish="big dinner",
        servings=6,
    )
    text, _buttons, plan = await build_meal_plan(decision, swiggy_client, "addr_01HXYZ")

    assert plan is not None
    assert len(plan["items"]) == 8
    assert "planned the first 8 ingredients" in text
    assert "other 1 separately" in text


@pytest.mark.asyncio
async def test_empty_plan_never_writes(swiggy_client):
    items, _missing, error = await resolve_plan_items(
        swiggy_client, "addr_01HXYZ", None
    )

    assert items == []
    assert "Ask me to plan the meal again" in error
