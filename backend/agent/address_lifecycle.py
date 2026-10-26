"""Grocer v1.0 — Address & Account Lifecycle Management.

Implements:
1. Two-Step Pin Geocoding Onboarding (ADR 0008).
2. Address Deletion Guardrail (ADR 0007): Strictly blocks address deletion during live deliveries.
3. Interactive Address Deletion Confirmation Button (ADR 0007).
4. One-Time Destination Anchoring & Session Revert (ADR 0009).
5. 5-Day Token Expiry Detection & JIT Parked Message Replay (ADR 0010).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.integrations.commerce.schemas import GetAddressesData


class PinGeocodeStep(str, Enum):
    AWAITING_FLAT_NUMBER = "awaiting_flat_number"
    COMPLETED = "completed"


@dataclass
class Step1GeocodeResult:
    next_step: PinGeocodeStep
    street_formatted_address: str
    prompt_message: str


@dataclass
class Step2CreateResult:
    address_id: str
    full_address_line: str


@dataclass
class DeletionCheckResult:
    can_delete: bool
    active_order_id: str | None = None
    block_reason: str = ""
    confirmation_action_id: str = ""


class OneTimeDestinationSession:
    """Manages delivery address destination for remote orders (ADR 0009)."""

    def __init__(self, primary_address_id: str) -> None:
        self.primary_address_id = primary_address_id
        self.one_time_destination_id: str | None = None

    @property
    def active_delivery_address_id(self) -> str:
        return self.one_time_destination_id or self.primary_address_id

    def set_one_time_destination(self, destination_id: str) -> None:
        self.one_time_destination_id = destination_id

    def reset_after_order(self) -> None:
        self.one_time_destination_id = None


class TokenParkedRequestManager:
    """Parks pending commerce requests upon 401 token expiry and replays on auth (ADR 0010)."""

    def __init__(self) -> None:
        # In-memory vault; synced to grocer.inbound_messages (status='awaiting_link')
        self._parked: dict[str, dict[str, Any]] = {}

    def park_request(self, user_id: str, action: str, payload: dict[str, Any]) -> str:
        token = secrets.token_urlsafe(16)
        self._parked[user_id] = {
            "token": token,
            "action": action,
            "payload": payload,
        }
        return token

    def has_parked_request(self, user_id: str) -> bool:
        return user_id in self._parked

    def get_reconnect_button_payload(self, parked_token: str) -> dict[str, str]:
        return {
            "title": "Reconnect Swiggy",
            "action_id": f"connect_swiggy:{parked_token}",
        }

    def pop_and_replay_request(self, user_id: str) -> dict[str, Any] | None:
        return self._parked.pop(user_id, None)


class AddressLifecycleManager:
    """Handles address discovery, pin geocoding, and deletion safety checks."""

    def __init__(self, swiggy_client: Any) -> None:
        self.client = swiggy_client

    def list_addresses(self, page: int = 1, page_size: int = 10) -> GetAddressesData:
        return self.client.get_addresses(page=page, page_size=page_size)

    def handle_gps_pin_step1(self, lat: float, lon: float) -> Step1GeocodeResult:
        """Step 1: Geocode GPS coordinates via recommend_address (ADR 0008)."""
        rec = self.client.recommend_address(latitude=lat, longitude=lon)
        formatted_address = (
            rec.get("formattedAddress")
            if isinstance(rec, dict)
            else getattr(rec, "formattedAddress", "")
        )

        prompt = (
            f"📍 Found your location near *{formatted_address}*.\n\n"
            "Please reply with your flat or house number and building name so riders find you easily."
        )

        return Step1GeocodeResult(
            next_step=PinGeocodeStep.AWAITING_FLAT_NUMBER,
            street_formatted_address=formatted_address,
            prompt_message=prompt,
        )

    def handle_flat_number_step2(
        self,
        lat: float,
        lon: float,
        street_address: str,
        flat_and_building: str,
        tag: str = "Home",
    ) -> Step2CreateResult:
        """Step 2: Combine house details with geocoded street and create address in Swiggy."""
        full_line = f"{flat_and_building.strip()}, {street_address.strip()}"
        res = self.client.create_address(
            address_line=full_line,
            latitude=lat,
            longitude=lon,
            tag=tag,
        )
        address_id = (
            res.get("addressId")
            if isinstance(res, dict)
            else getattr(res, "addressId", "")
        )
        return Step2CreateResult(
            address_id=address_id,
            full_address_line=full_line,
        )

    def can_delete_address(self, address_id: str) -> DeletionCheckResult:
        """Check if an address can be safely deleted or is locked by an active delivery (ADR 0007)."""
        orders_data = self.client.get_orders(offset=0, limit=20)
        active_statuses = {"CONFIRMED", "PACKING", "OUT_FOR_DELIVERY", "IN_TRANSIT"}

        for order in orders_data.orders:
            # Check if order is active and targeting this address
            is_active = getattr(order, "isActive", False) or (
                order.status.upper() in active_statuses
            )
            deliv_addr = getattr(order, "deliveryAddress", None) or {}
            target_addr_id = (
                deliv_addr.get("id")
                if isinstance(deliv_addr, dict)
                else getattr(deliv_addr, "id", None)
            )

            if is_active and target_addr_id == address_id:
                return DeletionCheckResult(
                    can_delete=False,
                    active_order_id=order.orderId,
                    block_reason=f"Cannot delete address while an active delivery (#{order.orderId}) is in transit to it.",
                )

        return DeletionCheckResult(
            can_delete=True,
            confirmation_action_id=f"delete_address_confirm:{address_id}",
        )

    def confirm_delete_address(self, address_id: str) -> bool:
        """Enforce deletion guardrail before triggering delete_address MCP tool."""
        check = self.can_delete_address(address_id)
        if not check.can_delete:
            raise ValueError(check.block_reason)

        self.client.delete_address(address_id=address_id)
        return True
