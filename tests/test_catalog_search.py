"""Grocer v1.0 — Phase 2 Candidate Search & Conversational Brain Test Matrix.

Validates the 20 real customer phrases specified in TASKS.md & PRD.md:
1. Exact brand + pack query ("Amul Taaza 1L")
2. Hinglish staple query ("1 litre doodh")
3. Vague staple auto-selection: milk -> standard pack + [Change items] button
4. Vague staple auto-selection: eggs -> 6-pack + [Change items] button
5. Vague staple auto-selection: bread -> standard sliced + [Change items] button
6. Vague staple auto-selection: pyaz -> fresh 1kg onions + [Change items] button
7. Vague staple auto-selection: atta -> whole wheat 5kg/1kg + [Change items] button
8. Typo in brand query ("amul milkk")
9. Typo in staple query ("brd")
10. Typo in popular brand ("magi")
11. Hinglish item query ("dahi")
12. Hinglish item query ("cheeni 1kg")
13. Hinglish item query ("adrak")
14. Discretionary snack disambiguation: chips (2-3 options, zero blind rank-1)
15. Discretionary drink disambiguation: cold coffee (2-3 options, zero blind rank-1)
16. Discretionary snack disambiguation: biscuits (2-3 options, zero blind rank-1)
17. Recipe checklist proposal: "making chai" with per-item toggles (ADR 0009)
18. Recipe checklist proposal: "Aglio Olio pasta for 2 tonight" (ADR 0009)
19. Conversational Q&A inquiry without forced receipt card (PRD Journey 3)
20. Zero-address onboarding flow with GPS pin prompt (ADR 0010)

Also validates:
21. Honest rupee paise formatting (no floor division loss).
22. Strict rank-1 prevention (no silent res[0] on ambiguous candidate matches).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agent.candidate_evaluator import (
    IntentType,
    evaluate_customer_intent,
    format_paise_to_rupees,
)
from backend.agent.candidate_search import CandidateItem, search_catalog
from backend.integrations.commerce.schemas import (
    SearchProductsData,
    ToolEnvelope,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def catalog_fixture() -> SearchProductsData:
    raw = json.loads(
        (FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8")
    )
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return envelope.data


@pytest.fixture
def swiggy_client(catalog_fixture) -> SwiggyClient:
    return SwiggyClient(catalog_data=catalog_fixture)


# ---------------------------------------------------------------------------
# Test 1: Exact brand + pack query ("Amul Taaza 1L")
# ---------------------------------------------------------------------------
def test_phrase_01_exact_brand_and_pack(swiggy_client):
    candidates = search_catalog("Amul Taaza 1L", swiggy_client=swiggy_client)
    res = evaluate_customer_intent(
        "Amul Taaza 1L", candidates=candidates, address_count=1
    )
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_amul_1l"
    assert res.selected_candidate.offer_price_paise == 7200
    assert not res.is_vague_staple


# ---------------------------------------------------------------------------
# Test 2: Hinglish staple query ("1 litre doodh")
# ---------------------------------------------------------------------------
def test_phrase_02_hinglish_staple(swiggy_client):
    candidates = search_catalog("1 litre doodh", swiggy_client=swiggy_client)
    res = evaluate_customer_intent(
        "1 litre doodh", candidates=candidates, address_count=1
    )
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert (
        "milk" in res.selected_candidate.display_name.lower()
        or "doodh" in res.selected_candidate.display_name.lower()
    )
    assert res.selected_candidate.spin_id == "spin_amul_1l"


# ---------------------------------------------------------------------------
# Test 3: Vague staple auto-selection: milk (ADR 0004)
# ---------------------------------------------------------------------------
def test_phrase_03_vague_staple_milk(swiggy_client):
    candidates = search_catalog("milk", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("milk", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.is_vague_staple is True
    assert res.selected_candidate.spin_id in [
        "spin_amul_500ml",
        "spin_nandini_500ml",
        "spin_amul_1l",
    ]
    # Physical [Change items] WhatsApp button attached
    assert len(res.suggested_actions) == 1
    assert res.suggested_actions[0]["title"] == "Change items"
    assert "item:change:" in res.suggested_actions[0]["id"]


# ---------------------------------------------------------------------------
# Test 4: Vague staple auto-selection: eggs (ADR 0004)
# ---------------------------------------------------------------------------
def test_phrase_04_vague_staple_eggs(swiggy_client):
    candidates = search_catalog("eggs", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("eggs", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_eggs_6"
    assert res.is_vague_staple is True
    assert len(res.suggested_actions) == 1
    assert res.suggested_actions[0]["title"] == "Change items"


# ---------------------------------------------------------------------------
# Test 5: Vague staple auto-selection: bread (ADR 0004)
# ---------------------------------------------------------------------------
def test_phrase_05_vague_staple_bread(swiggy_client):
    candidates = search_catalog("bread", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("bread", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_bread_white"
    assert res.is_vague_staple is True
    assert len(res.suggested_actions) == 1
    assert res.suggested_actions[0]["title"] == "Change items"


# ---------------------------------------------------------------------------
# Test 6: Vague staple auto-selection: pyaz (Hinglish onions)
# ---------------------------------------------------------------------------
def test_phrase_06_vague_staple_pyaz(swiggy_client):
    candidates = search_catalog("pyaz", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("pyaz", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_onion_1kg"
    assert res.is_vague_staple is True
    assert len(res.suggested_actions) == 1
    assert res.suggested_actions[0]["title"] == "Change items"


# ---------------------------------------------------------------------------
# Test 7: Vague staple auto-selection: atta (Hinglish wheat flour)
# ---------------------------------------------------------------------------
def test_phrase_07_vague_staple_atta(swiggy_client):
    candidates = search_catalog("atta", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("atta", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id in ["spin_atta_5kg", "spin_atta_1kg"]
    assert res.is_vague_staple is True
    assert len(res.suggested_actions) == 1
    assert res.suggested_actions[0]["title"] == "Change items"


# ---------------------------------------------------------------------------
# Test 8: Typo in brand query ("amul milkk")
# ---------------------------------------------------------------------------
def test_phrase_08_typo_brand(swiggy_client):
    candidates = search_catalog("amul milkk", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("amul milkk", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert "amul" in res.selected_candidate.display_name.lower()


# ---------------------------------------------------------------------------
# Test 9: Typo in staple query ("brd")
# ---------------------------------------------------------------------------
def test_phrase_09_typo_staple_bread(swiggy_client):
    candidates = search_catalog("brd", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("brd", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert "bread" in res.selected_candidate.display_name.lower()


# ---------------------------------------------------------------------------
# Test 10: Typo in popular brand ("magi")
# ---------------------------------------------------------------------------
def test_phrase_10_typo_magi(swiggy_client):
    candidates = search_catalog("magi", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("magi", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_maggi_4pack"


# ---------------------------------------------------------------------------
# Test 11: Hinglish item query ("dahi")
# ---------------------------------------------------------------------------
def test_phrase_11_hinglish_dahi(swiggy_client):
    candidates = search_catalog("dahi", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("dahi", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_curd_400g"


# ---------------------------------------------------------------------------
# Test 12: Hinglish item query ("cheeni 1kg")
# ---------------------------------------------------------------------------
def test_phrase_12_hinglish_cheeni(swiggy_client):
    candidates = search_catalog("cheeni 1kg", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("cheeni 1kg", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_sugar_1kg"


# ---------------------------------------------------------------------------
# Test 13: Hinglish item query ("adrak")
# ---------------------------------------------------------------------------
def test_phrase_13_hinglish_adrak(swiggy_client):
    candidates = search_catalog("adrak", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("adrak", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.ADD_TO_BASKET
    assert res.selected_candidate is not None
    assert res.selected_candidate.spin_id == "spin_ginger_100g"


# ---------------------------------------------------------------------------
# Test 14: Discretionary snack disambiguation: chips (No blind rank-1)
# ---------------------------------------------------------------------------
def test_phrase_14_disambiguate_chips(swiggy_client):
    candidates = search_catalog("chips", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("chips", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.DISAMBIGUATION
    assert res.selected_candidate is None
    assert len(res.disambiguation_options) >= 2
    # Ensure options have display names, pack sizes, and rupee prices
    for opt in res.disambiguation_options:
        assert opt.display_name
        assert opt.quantity_description
        assert opt.price_paise > 0
    assert "Which one" in res.message or "like" in res.message


# ---------------------------------------------------------------------------
# Test 15: Discretionary drink disambiguation: cold coffee
# ---------------------------------------------------------------------------
def test_phrase_15_disambiguate_cold_coffee(swiggy_client):
    candidates = search_catalog("cold coffee", swiggy_client=swiggy_client)
    res = evaluate_customer_intent(
        "cold coffee", candidates=candidates, address_count=1
    )
    assert res.intent_type == IntentType.DISAMBIGUATION
    assert res.selected_candidate is None
    assert len(res.disambiguation_options) >= 2


# ---------------------------------------------------------------------------
# Test 16: Discretionary snack disambiguation: biscuits
# ---------------------------------------------------------------------------
def test_phrase_16_disambiguate_biscuits(swiggy_client):
    candidates = search_catalog("biscuits", swiggy_client=swiggy_client)
    res = evaluate_customer_intent("biscuits", candidates=candidates, address_count=1)
    assert res.intent_type == IntentType.DISAMBIGUATION
    assert res.selected_candidate is None
    assert len(res.disambiguation_options) >= 2


# ---------------------------------------------------------------------------
# Test 17: Recipe checklist proposal: "making chai" (ADR 0009)
# ---------------------------------------------------------------------------
def test_phrase_17_recipe_chai(swiggy_client):
    res = evaluate_customer_intent("making chai", candidates=[], address_count=1)
    assert res.intent_type == IntentType.RECIPE_CHECKLIST
    assert res.recipe_name == "Chai"
    # Core ingredients required
    item_names = [item.name.lower() for item in res.recipe_items]
    assert any("milk" in n or "tea" in n for n in item_names)
    assert any("ginger" in n or "sugar" in n for n in item_names)
    # Assumed pantry staples identified
    assert any("water" in s.lower() for s in res.assumed_pantry_staples)
    # Interactive buttons proposed
    assert len(res.suggested_actions) == 2
    assert "Add All" in res.suggested_actions[0]["title"]
    assert "Let Me Pick" in res.suggested_actions[1]["title"]
    # Per-item toggles present
    assert all(item.toggle_action_id is not None for item in res.recipe_items)


# ---------------------------------------------------------------------------
# Test 18: Recipe checklist proposal: "Aglio Olio pasta for 2 tonight" (ADR 0009)
# ---------------------------------------------------------------------------
def test_phrase_18_recipe_aglio_olio(swiggy_client):
    res = evaluate_customer_intent(
        "Aglio Olio pasta for 2 tonight", candidates=[], address_count=1
    )
    assert res.intent_type == IntentType.RECIPE_CHECKLIST
    assert "Aglio Olio" in res.recipe_name
    item_names = [item.name.lower() for item in res.recipe_items]
    assert any("spaghetti" in n or "pasta" in n for n in item_names)
    assert any("olive oil" in n for n in item_names)
    assert any("garlic" in n for n in item_names)
    # Pantry staples
    assert any(
        "salt" in s.lower() or "chili" in s.lower() for s in res.assumed_pantry_staples
    )


# ---------------------------------------------------------------------------
# Test 19: Conversational Q&A inquiry without forced receipt card
# ---------------------------------------------------------------------------
def test_phrase_19_conversational_qa(swiggy_client):
    res = evaluate_customer_intent(
        "What is the delivery fee right now?", candidates=[], address_count=1
    )
    assert res.intent_type == IntentType.CONVERSATIONAL_QA
    assert res.selected_candidate is None
    assert res.message is not None
    assert len(res.message) > 0


# ---------------------------------------------------------------------------
# Test 20: Zero-address onboarding flow with GPS pin prompt (ADR 0010)
# ---------------------------------------------------------------------------
def test_phrase_20_zero_address_onboarding(swiggy_client):
    # Customer asks for groceries but has 0 saved addresses
    res = evaluate_customer_intent("Get 1L milk", candidates=[], address_count=0)
    assert res.intent_type == IntentType.ZERO_ADDRESS_ONBOARDING
    assert res.selected_candidate is None
    assert "location" in res.message.lower() or "address" in res.message.lower()
    assert res.request_location_pin is True


# ---------------------------------------------------------------------------
# Test 21: Honest Rupee Paise Formatting (No Floor Division Loss)
# ---------------------------------------------------------------------------
def test_honest_rupee_formatting_preserves_paise():
    assert format_paise_to_rupees(7200) == "₹72"
    assert format_paise_to_rupees(7450) == "₹74.50"
    assert format_paise_to_rupees(99) == "₹0.99"
    assert format_paise_to_rupees(1005) == "₹10.05"


# ---------------------------------------------------------------------------
# Test 22: Strict Rank-1 Prevention on Ambiguous Candidate Matches
# ---------------------------------------------------------------------------
def test_strict_rank_1_prevention_on_ambiguous_matches():
    # When multiple distinct candidates exist but user query is vague and not a staple,
    # the system MUST NOT silently grab candidates[0]. It must initiate disambiguation.
    cand1 = CandidateItem(
        spin_id="spin_snack_1",
        sku_id="sku_1",
        product_id="p1",
        display_name="Crunchy Snack Box (200 g)",
        quantity_description="200 g",
        mrp_paise=10000,
        offer_price_paise=9000,
        is_in_stock=True,
    )
    cand2 = CandidateItem(
        spin_id="spin_snack_2",
        sku_id="sku_2",
        product_id="p2",
        display_name="Spicy Snack Mix (250 g)",
        quantity_description="250 g",
        mrp_paise=12000,
        offer_price_paise=11000,
        is_in_stock=True,
    )
    res = evaluate_customer_intent(
        "something to munch", candidates=[cand1, cand2], address_count=1
    )
    assert res.intent_type == IntentType.DISAMBIGUATION
    assert res.selected_candidate is None
    assert len(res.disambiguation_options) == 2
