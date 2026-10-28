"""Grocer v1.0 — Reorder Tests (ADR 0012, basket safety class).

Runs against committed real Swiggy fixture shapes. No live cart is touched.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.order_actions import apply_reorder, handle_reorder_request
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ADDRESS_ID = "addr_01HXYZ"
ORDER_ID = "189456789012"
MILK_SPIN = "spin_amul_1l"


@dataclass
class FakeDecision:
    items: list[dict[str, Any]] = field(default_factory=list)
    order_ref: str | None = None


@pytest.fixture
def client() -> SwiggyClient:
    return FixtureSwiggyClient(FIXTURES_DIR)


def _cart_quantity(client: SwiggyClient, spin_id: str) -> int:
    return next(
        (item.quantity for item in client.get_cart().items if item.spinId == spin_id), 0
    )


@pytest.mark.asyncio
async def test_last_order_preview_names_items_and_does_not_write(client):
    reply = await handle_reorder_request(
        FakeDecision(order_ref="last"), client, ADDRESS_ID, "same as last time"
    )
    assert "Amul Taaza Homogenised Toned Milk (1 L) x2" in reply.text
    assert reply.buttons[0][0] == f"reorder:order:{ORDER_ID}"
    assert client.last_update_items == []
    assert _cart_quantity(client, MILK_SPIN) == 2


@pytest.mark.asyncio
async def test_apply_last_order_adds_to_existing_basket(client):
    reply = await apply_reorder(client, ADDRESS_ID, f"order:{ORDER_ID}")
    assert "Added 1 item" in reply.text
    assert _cart_quantity(client, MILK_SPIN) == 4


@pytest.mark.asyncio
async def test_usual_items_preview_uses_go_to_button(client):
    reply = await handle_reorder_request(
        FakeDecision(), client, ADDRESS_ID, "reorder my usual items"
    )
    assert reply.buttons[0][0] == "reorder:go"
    assert "Amul" in reply.text
    assert client.last_update_items == []


@pytest.mark.asyncio
async def test_apply_usual_items_adds_quantity(client):
    reply = await apply_reorder(client, ADDRESS_ID, "go")
    assert "Added 1 item" in reply.text
    # The fixture search always returns Amul 1 L, so the usual item folds into it.
    assert _cart_quantity(client, MILK_SPIN) == 3


@pytest.mark.asyncio
async def test_unknown_order_id_writes_nothing(client):
    reply = await handle_reorder_request(
        FakeDecision(order_ref="000000000000"), client, ADDRESS_ID
    )
    assert "couldn't find that order" in reply.text
    assert reply.buttons == []
    assert client.last_update_items == []


@pytest.mark.asyncio
async def test_no_past_orders_says_so_and_writes_nothing(tmp_path: Path):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_DIR, fixtures)
    (fixtures / "get_orders.json").write_text(
        json.dumps({"success": True, "data": {"orders": [], "hasMore": False}}),
        encoding="utf-8",
    )
    client = FixtureSwiggyClient(fixtures)

    reply = await handle_reorder_request(
        FakeDecision(order_ref="last"), client, ADDRESS_ID, "repeat my last order"
    )
    assert "don't have any Instamart orders" in reply.text
    assert reply.buttons == []
    assert client.last_update_items == []


@pytest.mark.asyncio
async def test_apply_reorder_reports_coupon_savings(client, monkeypatch):
    from backend.agent import customer_advocate
    from backend.agent.customer_advocate import CouponOptimizationResult

    def fake_optimize(cart, swiggy_client, address_id=None):
        return CouponOptimizationResult(
            original_to_pay_paise=1000,
            final_to_pay_paise=900,
            applied_coupon="SAVE10",
            savings_paise=100,
            final_cart=cart,
        )

    monkeypatch.setattr(customer_advocate, "optimize_coupons", fake_optimize)

    reply = await apply_reorder(client, ADDRESS_ID, f"order:{ORDER_ID}")

    assert "Coupon SAVE10: you save ₹1." in reply.text
