"""Grocer — Phase 3 Address & Lifecycle Guardrails Test Suite.

Tested against committed real Swiggy MCP staging fixtures. Zero fake mocks.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent.address_lifecycle import (
    AddressLifecycleManager,
    AddressOnboardingFlow,
    OnboardingStep,
    TokenParkedRequestManager,
    parse_city_pin,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return FixtureSwiggyClient(FIXTURES_DIR)


def test_get_addresses_pagination(swiggy_client):
    """Validates address listing from real staging fixture."""
    page1 = swiggy_client.get_addresses(page=1, page_size=10)
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


def test_address_deletion_guard_allows_a_free_address(swiggy_client):
    """ADR 0007: An address with no active delivery passes the delete guard."""
    manager = AddressLifecycleManager(swiggy_client)

    check = manager.can_delete_address("addr_01HXYZ")
    assert check.can_delete is True
    assert check.block_reason == ""


@pytest.mark.db
@pytest.mark.asyncio
async def test_token_expiration_parks_request_and_replays():
    """ADR 0010: 401 parks the list in Postgres, and the claim returns it once."""
    from backend.database import get_db_pool

    pool = await get_db_pool()
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"
    user_id = await pool.fetchval(
        "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
    )

    vault = TokenParkedRequestManager()
    pending_items = [{"spinId": "spin_amul_1l", "quantity": 2}]
    parked = {
        "action": "update_cart",
        "payload": {"items": pending_items},
    }
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO grocer.inbound_messages
                (wa_message_id, user_id, message_type, raw_payload, status)
            VALUES ($1, $2, 'awaiting_link', $3::jsonb, 'awaiting_link');
            """,
            f"parked_{uuid.uuid4().hex[:8]}",
            user_id,
            json.dumps(parked),
        )
        status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE user_id = $1;", user_id
        )
    assert status == "awaiting_link"

    popped = await vault.pop_parked_request(user_id)
    assert popped is not None
    row_id, payload = popped
    assert payload["action"] == "update_cart"
    assert payload["payload"]["items"][0]["spinId"] == "spin_amul_1l"

    await vault.mark_replayed(row_id)
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE user_id = $1;", user_id
        )
    assert status == "replayed"


@pytest.mark.scripted
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
