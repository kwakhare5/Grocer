"""Slice E2 Tests: Model-Driven Variant Selection & Ranker Decoupling.

Tests model-driven variant choice using mock GeminiClient:
- model pick used
- ask path returns the question
- unknown stock not shown as out of stock
- model failure returns candidates and does not crash
"""
from __future__ import annotations

from typing import Any, Optional
import pytest

from backend.agent.tools import SwiggyAgentTools
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter


class FakeGeminiClient:
    """Mock GeminiClient for offline unit testing of product selection."""

    def __init__(
        self,
        response: Optional[dict[str, Any]] = None,
        reason: Optional[str] = None,
        should_raise: bool = False,
    ) -> None:
        self.response = response
        self.reason = reason
        self.should_raise = should_raise
        self.last_model: Optional[str] = None
        self.last_prompt: Optional[str] = None

    async def generate_structured_with_reason(
        self,
        model: str,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        self.last_model = model
        self.last_prompt = prompt
        if self.should_raise:
            raise RuntimeError("Connection dropped to model API")
        return self.response, self.reason


@pytest.mark.asyncio
async def test_mock_model_pick_used():
    """Verify that when the model picks a candidate ID, that candidate is returned."""
    fake_client = FakeGeminiClient(
        response={"action": "pick", "candidate_id": "2", "reason": "Exact single unit requested"},
        reason=None,
    )
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce, gemini_client=fake_client)

    raw_products = [
        {
            "product_id": "PID-MILK",
            "name": "Amul Taaza Milk",
            "variants": [
                {
                    "spin_id": "SPIN-MILK-4PK",
                    "sku_id": "SKU-MILK-4PK",
                    "name": "Amul Taaza Milk 500ml x 4",
                    "pack_size": "500ml x 4",
                    "price": 120.0,
                },
                {
                    "spin_id": "SPIN-MILK-1PK",
                    "sku_id": "SKU-MILK-1PK",
                    "name": "Amul Taaza Milk 500ml",
                    "pack_size": "500ml",
                    "price": 30.0,
                },
            ],
        }
    ]

    res = await tools.select_best_variant("milk", raw_products)
    assert res is not None
    assert res["action"] == "pick"
    assert res["candidate_id"] == "2"
    assert res["spin_id"] == "SPIN-MILK-1PK"
    assert res["name"] == "Amul Taaza Milk 500ml"
    assert res["price"] == 30.0


@pytest.mark.asyncio
async def test_mock_ask_path_returns_question():
    """Verify that when the model decides to ask, the question and candidates are returned."""
    fake_client = FakeGeminiClient(
        response={
            "action": "ask",
            "question": "Which type of bread would you prefer: white or brown?",
            "reason": "Multiple distinct bread types available without customer preference",
        },
        reason=None,
    )
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce, gemini_client=fake_client)

    raw_products = [
        {
            "product_id": "PID-B1",
            "name": "White Bread",
            "variants": [
                {"spin_id": "SPIN-W-BREAD", "sku_id": "SKU-W-BREAD", "name": "White Bread 400g", "pack_size": "400g", "price": 40.0}
            ],
        },
        {
            "product_id": "PID-B2",
            "name": "Brown Bread",
            "variants": [
                {"spin_id": "SPIN-B-BREAD", "sku_id": "SKU-B-BREAD", "name": "Brown Bread 400g", "pack_size": "400g", "price": 50.0}
            ],
        },
    ]

    res = await tools.select_best_variant("bread", raw_products)
    assert res is not None
    assert res["action"] == "ask"
    assert res["question"] == "Which type of bread would you prefer: white or brown?"
    assert res["reason"] == "Multiple distinct bread types available without customer preference"
    assert len(res["candidates"]) == 2


@pytest.mark.asyncio
async def test_mock_unknown_stock_not_shown_as_out_of_stock():
    """Verify that unknown stock (None) is never displayed as 'OUT OF STOCK' to the model."""
    fake_client = FakeGeminiClient(
        response={"action": "pick", "candidate_id": "1", "reason": "Standard produce item"},
        reason=None,
    )
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce, gemini_client=fake_client)

    raw_products = [
        {
            "product_id": "PID-TOM-1",
            "name": "Organic Tomatoes",
            "variants": [
                {
                    "spin_id": "SPIN-TOM",
                    "sku_id": "SKU-TOM",
                    "name": "Organic Tomatoes 500g",
                    "pack_size": "500g",
                    "price": 35.0,
                    "in_stock": None,  # Unknown stock from provider
                }
            ],
        }
    ]

    await tools.select_best_variant("tomatoes", raw_products)
    prompt = fake_client.last_prompt
    assert prompt is not None
    assert "OUT OF STOCK" not in prompt
    assert "Organic Tomatoes 500g" in prompt


@pytest.mark.asyncio
async def test_mock_model_failure_returns_candidates_and_does_not_crash():
    """Verify that model failure/timeout returns all store candidates without falling back to word lists."""
    fake_client = FakeGeminiClient(should_raise=True)
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce, gemini_client=fake_client)

    raw_products = [
        {
            "product_id": "PID-EGGS",
            "name": "Farm Eggs",
            "variants": [
                {"spin_id": "SPIN-EGG-6", "sku_id": "SKU-EGG-6", "name": "Farm Eggs 6 pcs", "pack_size": "6 pcs", "price": 55.0},
                {"spin_id": "SPIN-EGG-12", "sku_id": "SKU-EGG-12", "name": "Farm Eggs 12 pcs", "pack_size": "12 pcs", "price": 105.0},
            ],
        }
    ]

    res = await tools.select_best_variant("eggs 6", raw_products)
    assert res is not None
    assert res["action"] == "fallback_candidates"
    assert len(res["candidates"]) == 2
    assert res["candidates"][0]["name"] == "Farm Eggs 6 pcs"
    assert res["candidates"][1]["name"] == "Farm Eggs 12 pcs"
    assert "Connection dropped to model API" in res.get("error", "")


@pytest.mark.asyncio
async def test_mock_manage_basket_integration_pick_and_ask():
    """Verify manage_basket integrates model pick into cart additions and model ask into clarifications."""
    fake_client = FakeGeminiClient(
        response={"action": "pick", "candidate_id": "1", "reason": "Standard selection"},
        reason=None,
    )
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce, gemini_client=fake_client)

    # 1. Manage basket with model pick
    async def mock_batch_search(queries, address_id):
        return {
            "success": True,
            "results": [
                {
                    "query": "milk",
                    "products": [
                        {
                            "product_id": "prod-milk",
                            "name": "Amul Taaza Milk",
                            "variants": [
                                {"spin_id": "SPIN-MILK-1L", "sku_id": "SPIN-MILK-1L", "name": "Amul Taaza Milk 1L Pouch", "price": 66.0, "pack_size": "1 L"}
                            ],
                        }
                    ],
                }
            ],
        }

    tools.batch_search_products = mock_batch_search
    mutation_pick = await tools.manage_basket(address_id="addr-bandra-1", add=[{"query": "milk", "quantity": 1}])
    assert mutation_pick["success"] is True
    assert "Amul Taaza Milk 1L Pouch" in mutation_pick.get("added_items", [])

    # 2. Manage basket with model ask
    fake_client.response = {
        "action": "ask",
        "question": "Which bread do you prefer?",
        "reason": "Multiple bread varieties available",
    }
    async def mock_batch_search_bread(queries, address_id):
        return {
            "success": True,
            "results": [
                {
                    "query": "bread",
                    "products": [
                        {
                            "product_id": "P-2",
                            "name": "White Bread",
                            "variants": [
                                {"spin_id": "SPIN-BREAD-1", "sku_id": "SKU-2", "name": "White Bread 400g", "price": 40.0}
                            ],
                        }
                    ],
                }
            ],
        }

    tools.batch_search_products = mock_batch_search_bread
    mutation_ask = await tools.manage_basket(address_id="addr-bandra-1", add=[{"query": "bread", "quantity": 1}])
    assert mutation_ask["success"] is True
    assert "clarifications_needed" in mutation_ask
    assert mutation_ask["questions"] == ["Which bread do you prefer?"]
