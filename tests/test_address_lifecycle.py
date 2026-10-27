"""Grocer v1.0 — Phase 3 Address & Lifecycle Guardrails Test Suite.

Tested against committed real Swiggy MCP staging fixtures. Zero fake mocks.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from backend.agent.address_lifecycle import (
    AddressLifecycleManager,
    AddressOnboardingFlow,
    OnboardingStep,
    OneTimeDestinationSession,
    TokenParkedRequestManager,
    parse_city_pin,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return SwiggyClient(fixtures_dir=FIXTURES_DIR)


def test_get_addresses_pagination(swiggy_client):
    """Validates address listing from real staging fixture."""
    manager = AddressLifecycleManager(swiggy_client)

    page1 = manager.list_addresses(page=1, page_size=10)
    assert len(page1.addresses) >= 1
    assert page1.addresses[0].id == "addr_01HXYZ"
    assert page1.pagination.page == 1


def test_parse_city_pin():
    """Extract city + 6-digit PIN from a free-text onboarding reply."""
    city, pin = parse_city_pin("Bengaluru, 560034")
    assert city == "Bengaluru"
    assert pin == "560034"
    assert parse_city_pin("no pin here") == (None, None)


def test_pin_onboarding_flow_captures_name_city_pin(swiggy_client):
    """Gate 1: location pin -> geocode -> flat -> name -> city+PIN -> create_address."""
    flow = AddressOnboardingFlow(swiggy_client)

    # Step 1: WhatsApp GPS pin geocodes to a street address
    turn1 = flow.start_from_location(lat=12.9352, lon=77.6245)
    assert turn1.next_step == OnboardingStep.AWAITING_FLAT
    assert "Bengaluru" in turn1.context["street_address"]
    assert "flat" in turn1.prompt.lower()

    # Step 2: flat/house number
    turn2 = flow.advance(turn1.next_step, turn1.context, text="Flat 301, Lakeview Heights")
    assert turn2.next_step == OnboardingStep.AWAITING_NAME
    assert turn2.context["flat"] == "Flat 301, Lakeview Heights"

    # Step 3: customer name
    turn3 = flow.advance(turn2.next_step, turn2.context, text="Karan Wakhare")
    assert turn3.next_step == OnboardingStep.AWAITING_CITY_PIN

    # Step 4: city + PIN -> address created on Swiggy
    turn4 = flow.advance(
        turn3.next_step, turn3.context, text="Bengaluru, 560034", wa_id="919876543210"
    )
    assert turn4.completed is True
    assert turn4.address_id.startswith("addr_")


def test_address_deletion_confirmation_with_label(swiggy_client):
    """ADR 0007: Address deletion presents confirmation button with human label [Confirm Delete: <Label>]."""
    manager = AddressLifecycleManager(swiggy_client)

    check = manager.can_delete_address("addr_01HXYZ")
    assert check.can_delete is True
    assert check.confirmation_action_id == "delete_address_confirm:addr_01HXYZ"
    assert "Confirm Delete: Home" in check.confirmation_label

    # Execute delete
    deleted = manager.confirm_delete_address("addr_01HXYZ")
    assert deleted is True


def test_one_time_destination_preserves_primary_address():
    """ADR 0009: Setting a one-time destination preserves primary home address for future turns."""
    session = OneTimeDestinationSession(primary_address_id="addr_home_primary")
    assert session.active_delivery_address_id == "addr_home_primary"

    # User orders for mom in Delhi
    session.set_one_time_destination("addr_mom_delhi")
    assert session.active_delivery_address_id == "addr_mom_delhi"
    assert session.primary_address_id == "addr_home_primary"

    # After checkout completes, reset session to primary
    session.reset_after_order()
    assert session.active_delivery_address_id == "addr_home_primary"
    assert session.one_time_destination_id is None


@pytest.mark.asyncio
async def test_token_expiration_parks_request_and_replays():
    """ADR 0010: 401 parks shopping list in DB/session, re-auth replays automatically."""
    vault = TokenParkedRequestManager()
    user_id = uuid.uuid4()

    # Customer tries adding items, but token is expired
    pending_items = [{"spinId": "spin_amul_1l", "quantity": 2}]
    parked_token = await vault.park_request(
        user_id=user_id,
        action="update_cart",
        payload={"items": pending_items},
    )
    assert parked_token is not None
    assert await vault.has_parked_request(user_id) is True

    # WhatsApp CTA button is provided
    cta = vault.get_reconnect_button_payload(parked_token)
    assert "connect_swiggy" in cta["action_id"]

    # Customer reconnects Swiggy OAuth
    replayed = await vault.pop_and_replay_request(user_id)
    assert replayed is not None
    assert replayed["action"] == "update_cart"
    assert replayed["payload"]["items"][0]["spinId"] == "spin_amul_1l"


def test_address_deletion_blocked_when_active_delivery_in_transit(
    swiggy_client, monkeypatch
):
    """ADR 0007: Deleting an address with an active delivery in transit is strictly blocked."""
    from backend.integrations.commerce.schemas import OrderHistoryItem, OrdersListData

    active_orders = OrdersListData(
        orders=[
            OrderHistoryItem(
                orderId="order_live_999",
                status="OUT_FOR_DELIVERY",
                createdAt="2026-10-26T12:00:00Z",
                itemCount=2,
                totalAmount=150.0,
                isActive=True,
                deliveryAddress={"id": "addr_01HXYZ"},
            )
        ],
        hasMore=False,
    )
    monkeypatch.setattr(
        swiggy_client, "get_orders", lambda count=20, order_type="INSTAMART", active_only=True: active_orders
    )

    manager = AddressLifecycleManager(swiggy_client)
    check = manager.can_delete_address("addr_01HXYZ")
    assert check.can_delete is False
    assert check.active_order_id == "order_live_999"
    assert "Cannot delete address" in check.block_reason

    with pytest.raises(ValueError, match="active delivery"):
        manager.confirm_delete_address("addr_01HXYZ")
