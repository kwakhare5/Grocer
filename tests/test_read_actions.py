"""Grocer v1.0 — Read Capability Tests (offline, fixture-backed).

Covers the Gate 2 answers that do not need a live account: honest store info,
real tracking with and without map coordinates, and tappable choices for a
vague request like "milk".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.candidate_search import CandidateItem
from backend.agent.read_actions import (
    answer_read_capability,
    build_read_reply,
    format_disambiguation_choices,
)
from backend.agent.router import Capability, RoutingDecision, SafetyClass
from backend.integrations.commerce.schemas import (
    AddressPagination,
    AddressResolution,
    DeliveryStatusData,
    GetAddressesData,
    OrderHistoryItem,
    OrdersListData,
    SavedAddress,
    SearchProduct,
    SearchProductsData,
    TrackOrderData,
    TrackOrderStatus,
)

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
    client = FixtureSwiggyClient(FIXTURES_DIR)
    answer = await answer_read_capability(
        _decision(Capability.STORE_INFO), client, "addr_01HXYZ"
    )
    assert "delivery quote" in answer.lower()
    assert "Items are adding to your basket right now, so the store is taking orders." in answer
    assert "doesn't share the dark store name or a delivery window" in answer


@pytest.mark.asyncio
async def test_order_bill_shows_items_and_line_items():
    client = FixtureSwiggyClient(FIXTURES_DIR)
    answer = await answer_read_capability(
        _decision(Capability.ORDER_BILL, order_ref="last"), client, "addr_01HXYZ"
    )
    assert "Bill for order #189456789012" in answer
    assert "Amul Taaza Homogenised Toned Milk x2 — ₹144" in answer
    assert "Handling Fee" in answer
    assert "Total: ₹149.00" in answer


@pytest.mark.asyncio
async def test_placed_order_add_is_truthful_and_offers_a_new_basket():
    answer = await answer_read_capability(
        _decision(Capability.PLACED_ORDER_ADD), FixtureSwiggyClient(FIXTURES_DIR), "addr"
    )
    assert "locks it" in answer
    assert "separate order" in answer


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


class AddressClient:
    def get_addresses(self) -> GetAddressesData:
        return GetAddressesData(
            addresses=[
                SavedAddress(
                    id="a1",
                    addressLine=(
                        "Flat 1204, Kingsbury, DY Patil Road, Charholi, Pune, "
                        "Maharashtra 412105, India"
                    ),
                    addressTag="Home",
                ),
                SavedAddress(
                    id="a2",
                    addressLine=(
                        "3rd floor, Shitole Nagar, Spicer College Road, Old Sangvi, "
                        "Pune, Pimpri-Chinchwad, Maharashtra 411027, India"
                    ),
                    addressTag="Work",
                ),
            ],
            pagination=AddressPagination(
                page=1, pageSize=10, total=2, totalPages=1, hasMore=False
            ),
            resolution=AddressResolution(
                defaultAddressId="a1", resolutionSource="default"
            ),
        )


class OutOfStockClient:
    def search_products(self, query: str, address_id: str | None = None) -> SearchProductsData:
        return SearchProductsData(
            products=[],
            similarProducts=[
                SearchProduct(
                    displayName="Mother Dairy Table Butter",
                    inStock=True,
                    isAvail=True,
                    productId="p_butter",
                    variations=[],
                )
            ],
        )


@pytest.mark.asyncio
async def test_view_basket_reads_the_live_cart():
    client = FixtureSwiggyClient(FIXTURES_DIR)
    reply = await build_read_reply(
        _decision(Capability.VIEW_BASKET), client, "addr_01HXYZ"
    )
    assert "Amul" in reply.text
    assert "To Pay" in reply.text
    assert reply.buttons == []


@pytest.mark.asyncio
async def test_address_list_is_short_and_switchable():
    reply = await build_read_reply(
        _decision(Capability.LIST_ADDRESSES), AddressClient(), None
    )
    assert "1. *Home* · default" in reply.text
    assert "Kingsbury" in reply.text
    assert "Spicer College Road" not in reply.text
    assert reply.buttons == [("addr:set:a2", "Switch to Work")]


@pytest.mark.asyncio
async def test_item_info_names_real_alternatives_when_out_of_stock():
    decision = RoutingDecision(
        capability=Capability.ITEM_INFO,
        safety=SafetyClass.READ,
        confidence=0.95,
        items=[{"query": "amul butter"}],
    )
    reply = await build_read_reply(decision, OutOfStockClient(), "addr_01HXYZ")
    assert "couldn't find" in reply.text
    assert "Mother Dairy Table Butter" in reply.text


@pytest.mark.asyncio
async def test_payment_options_say_upi_only():
    client = FixtureSwiggyClient(FIXTURES_DIR)
    text = await answer_read_capability(
        RoutingDecision(
            capability=Capability.PAYMENT_OPTIONS,
            safety=SafetyClass.READ,
            confidence=1.0,
        ),
        client,
        "addr_01",
    )

    assert "UPI only" in text
    assert "Google Pay" in text
    assert "Swiggy Money" in text
    assert "can't use those yet" in text
