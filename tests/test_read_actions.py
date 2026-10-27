"""Grocer v1.0 — Read Capability Tests (offline, fixture-backed).

Covers the Gate 2 answers that do not need a live account: honest store info,
real tracking with and without map coordinates, and tappable choices for a
vague request like "milk".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agent.candidate_search import CandidateItem
from backend.agent.read_actions import (
    answer_read_capability,
    format_disambiguation_choices,
)
from backend.agent.router import Capability, RoutingDecision, SafetyClass
from backend.integrations.commerce.schemas import (
    DeliveryStatusData,
    OrderHistoryItem,
    OrdersListData,
    TrackOrderData,
    TrackOrderStatus,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

pytestmark = pytest.mark.scripted


def _decision(capability: Capability, order_ref: str | None = None) -> RoutingDecision:
    return RoutingDecision(
        capability=capability,
        safety=SafetyClass.READ,
        confidence=0.99,
        order_ref=order_ref,
    )


pytestmark = pytest.mark.scripted

def _active_order(order_id: str = "189456789012") -> OrderHistoryItem:
    return OrderHistoryItem(
        orderId=order_id,
        status="PLACED",
        createdAt="2026-10-27T10:00:00Z",
        itemCount=2,
        totalAmount=149.0,
        isActive=True,
    )


class TrackingClient:
    """Fixture client with one active order; records tracking calls."""

    def __init__(self, active: bool = True) -> None:
        self.active = active
        self.track_calls: list[tuple[str, float, float]] = []

    def get_orders(
        self, count: int = 10, order_type: str = "INSTAMART", active_only: bool = False
    ) -> OrdersListData:
        return OrdersListData(orders=[_active_order()] if self.active else [])

    def track_order(self, order_id: str, lat: float, lng: float) -> TrackOrderData:
        self.track_calls.append((order_id, lat, lng))
        return TrackOrderData(
            orderId=order_id,
            orderTitle="Instamart order",
            orderSubtitle="Delivering to Home",
            status=TrackOrderStatus(statusMessage="On the way", etaMinutes=8),
            storeInfo={"name": "Swiggy Instamart Pod - Bellandur"},
            itemCount=2,
        )

    def get_delivery_status(self, order_id: str) -> DeliveryStatusData:
        return DeliveryStatusData(
            orderId=order_id,
            statusText="Packed",
            etaText="12 mins",
        )


class EmptyTrackingClient(TrackingClient):
    def get_orders(
        self, count: int = 10, order_type: str = "INSTAMART", active_only: bool = False
    ) -> OrdersListData:
        return OrdersListData(orders=[])

    def get_delivery_status(self, order_id: str) -> DeliveryStatusData:
        raise AssertionError("delivery status must not be polled without an order")


@pytest.mark.asyncio
async def test_track_order_uses_real_tracking_tool_with_coords():
    client = TrackingClient()
    answer = await answer_read_capability(
        _decision(Capability.TRACK_ORDER),
        client,
        "addr_01HXYZ",
        coords=(12.9352, 77.6245),
    )
    assert client.track_calls == [("189456789012", 12.9352, 77.6245)]
    assert "On the way" in answer
    assert "ETA 8 mins" in answer
    assert "Swiggy Instamart Pod - Bellandur" in answer
    assert "swiggy.com/track/189456789012" in answer


@pytest.mark.asyncio
async def test_track_order_without_coords_uses_delivery_status():
    client = TrackingClient()
    answer = await answer_read_capability(
        _decision(Capability.TRACK_ORDER), client, "addr_01HXYZ"
    )
    assert client.track_calls == []
    assert "Packed" in answer
    assert "ETA: 12 mins" in answer
    assert "location pin" in answer


@pytest.mark.asyncio
async def test_track_order_with_no_active_order_says_so():
    answer = await answer_read_capability(
        _decision(Capability.TRACK_ORDER), EmptyTrackingClient(), "addr_01HXYZ"
    )
    assert answer == "You have no active order right now."


@pytest.mark.asyncio
async def test_store_info_is_honest_about_store_and_window():
    client = SwiggyClient(fixtures_dir=FIXTURES_DIR)
    answer = await answer_read_capability(
        _decision(Capability.STORE_INFO), client, "addr_01HXYZ"
    )
    assert "delivery quote" in answer.lower()
    assert "doesn't share the dark store name or a delivery window" in answer


def test_disambiguation_choices_are_tappable_real_products():
    candidates = [
        CandidateItem(
            spin_id="spin_a",
            sku_id="sku_a",
            product_id="prod_a",
            display_name="Chitale Dairy Cow Milk",
            quantity_description="500 ml",
            mrp_paise=3400,
            offer_price_paise=3200,
            is_in_stock=True,
        ),
        CandidateItem(
            spin_id="spin_b",
            sku_id="sku_b",
            product_id="prod_b",
            display_name="Amul Taaza Toned Milk",
            quantity_description="1 ltr",
            mrp_paise=7400,
            offer_price_paise=7200,
            is_in_stock=True,
        ),
    ]

    text, buttons = format_disambiguation_choices("milk", candidates, quantity=2)

    assert "Which *milk* did you mean?" in text
    assert "Chitale Dairy Cow Milk (500 ml) — ₹32" in text
    assert buttons == [
        ("cart:add:spin_a:2", "Chitale Dairy Cow Mi"),
        ("cart:add:spin_b:2", "Amul Taaza Toned Mil"),
    ]
