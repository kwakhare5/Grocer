"""Grocer v1.0 — Phase 3 Address & Lifecycle Guardrails Test Suite.

Tests:
1. Address pagination and resolution from get_addresses fixture.
2. Two-step pin geocoding onboarding (ADR 0008).
3. Address Deletion Guardrail (ADR 0007): Active delivery blocks deletion.
4. Address Deletion Confirmation Button (ADR 0007): Idle address generates confirmation button.
5. One-Time Destination Anchoring (ADR 0009): Orders to friend/parent preserve home address.
6. 5-Day Token Expiration & Parked Request Replay (ADR 0010): 401 parks list, re-auth replays.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agent.address_lifecycle import (
    AddressLifecycleManager,
    OneTimeDestinationSession,
    PinGeocodeStep,
    TokenParkedRequestManager,
)
from backend.integrations.commerce.schemas import (
    GetAddressesData,
    OrdersListData,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FakeLifecycleSwiggyStore:
    def __init__(
        self,
        active_orders: list[dict] | None = None,
        addresses: list[dict] | None = None,
    ):
        self.active_orders = active_orders or []
        self.addresses = addresses or [
            {
                "id": "addr_01HXYZ",
                "addressLine": "Flat 402, Green Glen Layout, Bellandur, Bengaluru",
                "phoneNumber": "+919876543210",
                "addressCategory": "HOME",
                "addressTag": "Home",
            }
        ]
        self.created_addresses: list[dict] = []
        self.deleted_address_ids: list[str] = []

    def get_addresses(self, page: int = 1, page_size: int = 10) -> GetAddressesData:
        start = (page - 1) * page_size
        end = start + page_size
        subset = self.addresses[start:end]
        total = len(self.addresses)
        return GetAddressesData(
            addresses=subset,
            pagination={
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 1,
                "hasMore": end < total,
            },
            resolution={
                "defaultAddressId": self.addresses[0]["id"] if self.addresses else None,
                "resolutionSource": "user_selected_address",
                "needsUserClarification": False,
                "candidateAddressIds": [a["id"] for a in self.addresses],
                "scoreUsed": 1.0,
            },
        )

    def recommend_address(self, latitude: float, longitude: float) -> dict:
        return {
            "latitude": latitude,
            "longitude": longitude,
            "formattedAddress": "80 Feet Road, 4th Block, Koramangala, Bengaluru, Karnataka 560034",
        }

    def create_address(
        self, address_line: str, latitude: float, longitude: float, tag: str = "Home"
    ) -> dict:
        new_id = f"addr_gen_{len(self.created_addresses) + 1}"
        entry = {
            "id": new_id,
            "addressLine": address_line,
            "phoneNumber": "+919876543210",
            "addressCategory": tag.upper(),
            "addressTag": tag,
        }
        self.created_addresses.append(entry)
        self.addresses.append(entry)
        return {"addressId": new_id}

    def delete_address(self, address_id: str) -> dict:
        self.deleted_address_ids.append(address_id)
        self.addresses = [a for a in self.addresses if a["id"] != address_id]
        return {"statusCode": 200, "statusMessage": "Address deleted successfully"}

    def get_orders(self, offset: int = 0, limit: int = 10) -> OrdersListData:
        return OrdersListData(
            orders=self.active_orders,
            hasMore=False,
        )


def test_get_addresses_pagination():
    """Validates multi-address pagination logic."""
    many_addresses = [
        {
            "id": f"addr_{i}",
            "addressLine": f"Building {i}, Road {i}",
            "addressTag": f"Addr {i}",
        }
        for i in range(25)
    ]
    store = FakeLifecycleSwiggyStore(addresses=many_addresses)
    manager = AddressLifecycleManager(store)

    page1 = manager.list_addresses(page=1, page_size=10)
    assert len(page1.addresses) == 10
    assert page1.pagination.hasMore is True
    assert page1.pagination.total == 25

    page3 = manager.list_addresses(page=3, page_size=10)
    assert len(page3.addresses) == 5
    assert page3.pagination.hasMore is False


def test_two_step_pin_geocoding_onboarding():
    """Step 1 geocodes GPS coordinates; Step 2 asks and attaches flat/house number (ADR 0008)."""
    store = FakeLifecycleSwiggyStore()
    manager = AddressLifecycleManager(store)

    # Step 1: WhatsApp sends GPS pin
    step1_res = manager.handle_gps_pin_step1(lat=12.9352, lon=77.6245)
    assert step1_res.next_step == PinGeocodeStep.AWAITING_FLAT_NUMBER
    assert "Koramangala" in step1_res.street_formatted_address
    assert "flat or house number" in step1_res.prompt_message.lower()

    # Step 2: User provides flat/house details
    step2_res = manager.handle_flat_number_step2(
        lat=12.9352,
        lon=77.6245,
        street_address=step1_res.street_formatted_address,
        flat_and_building="Flat 301, Lakeview Heights",
        tag="Home",
    )
    assert step2_res.address_id.startswith("addr_gen_")
    assert "Flat 301, Lakeview Heights" in step2_res.full_address_line
    assert "80 Feet Road" in step2_res.full_address_line


def test_address_deletion_blocked_when_active_delivery_in_transit():
    """ADR 0007: Deleting an address with an active delivery dispatched to it is strictly blocked."""
    active_in_flight_orders = [
        {
            "orderId": "order_active_999",
            "status": "OUT_FOR_DELIVERY",
            "createdAt": "2026-10-25T11:00:00Z",
            "itemCount": 3,
            "totalAmount": 340.0,
            "isActive": True,
            "deliveryAddress": {
                "id": "addr_01HXYZ",
                "addressLine": "Flat 402, Bellandur",
            },
        }
    ]
    store = FakeLifecycleSwiggyStore(active_orders=active_in_flight_orders)
    manager = AddressLifecycleManager(store)

    check = manager.can_delete_address("addr_01HXYZ")
    assert check.can_delete is False
    assert check.active_order_id == "order_active_999"
    assert "Cannot delete address" in check.block_reason
    assert "active delivery" in check.block_reason.lower()

    # Attempting forced delete throws safety ValueError
    with pytest.raises(ValueError, match="active delivery"):
        manager.confirm_delete_address("addr_01HXYZ")


def test_address_deletion_confirmation_button_when_idle():
    """ADR 0007: Idle address deletion generates explicit confirmation button."""
    # Order is DELIVERED, not active
    completed_orders = [
        {
            "orderId": "order_past_111",
            "status": "DELIVERED",
            "createdAt": "2026-10-25T08:00:00Z",
            "itemCount": 1,
            "totalAmount": 100.0,
            "isActive": False,
            "deliveryAddress": {
                "id": "addr_01HXYZ",
            },
        }
    ]
    store = FakeLifecycleSwiggyStore(active_orders=completed_orders)
    manager = AddressLifecycleManager(store)

    check = manager.can_delete_address("addr_01HXYZ")
    assert check.can_delete is True
    assert check.confirmation_action_id == "delete_address_confirm:addr_01HXYZ"

    # Now execute delete
    deleted = manager.confirm_delete_address("addr_01HXYZ")
    assert deleted is True
    assert "addr_01HXYZ" in store.deleted_address_ids


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


def test_token_expiration_parks_request_and_replays():
    """ADR 0010: 401 parks shopping list in DB/session, re-auth replays automatically."""
    vault = TokenParkedRequestManager()
    user_id = "user_wa_919876543210"

    # Customer tries adding items, but token is expired
    pending_items = [{"spinId": "spin_amul_1l", "quantity": 2}]
    parked_token = vault.park_request(
        user_id=user_id,
        action="update_cart",
        payload={"items": pending_items},
    )
    assert parked_token is not None
    assert vault.has_parked_request(user_id) is True

    # WhatsApp CTA button is provided
    cta = vault.get_reconnect_button_payload(parked_token)
    assert "connect_swiggy" in cta["action_id"]

    # Customer reconnects Swiggy OAuth
    replayed = vault.pop_and_replay_request(user_id)
    assert replayed is not None
    assert replayed["action"] == "update_cart"
    assert replayed["payload"]["items"][0]["spinId"] == "spin_amul_1l"
    assert vault.has_parked_request(user_id) is False
