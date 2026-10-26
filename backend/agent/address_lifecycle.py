"""Grocer v1.0 — Address & Account Lifecycle Management.

Implements:
1. Two-Step Pin Geocoding Onboarding (ADR 0008).
2. Address Deletion Guardrail (ADR 0007): Strictly blocks address deletion during live deliveries.
3. Interactive Address Deletion Confirmation Button with Label (ADR 0007).
4. One-Time Destination Anchoring & Session Revert (ADR 0009).
5. 5-Day Token Expiry Detection & PostgreSQL Parked Message Replay (ADR 0010).
"""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

import asyncpg

from backend.database import get_db_pool
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
    confirmation_label: str = ""


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
    """Parks pending commerce requests upon 401 token expiry into PostgreSQL and replays on auth (ADR 0010)."""

    def __init__(self) -> None:
        self._memory_backup: dict[str, dict[str, Any]] = {}

    async def park_request(
        self,
        user_id: uuid.UUID | str,
        action: str,
        payload: dict[str, Any],
    ) -> str:
        """Park uncommitted request in grocer.inbound_messages (status='awaiting_link')."""
        uid = (
            uuid.UUID(str(user_id))
            if isinstance(user_id, str) and "-" in str(user_id)
            else None
        )
        token = secrets.token_urlsafe(16)
        pack = {"action": action, "payload": payload, "token": token}

        if uid is not None:
            try:
                pool = await get_db_pool()
                wa_msg_id = f"parked_{uid}_{secrets.token_hex(4)}"
                await pool.execute(
                    """
                    INSERT INTO grocer.inbound_messages (wa_message_id, user_id, message_type, raw_payload, status)
                    VALUES ($1, $2, 'awaiting_link', $3::jsonb, 'awaiting_link');
                    """,
                    wa_msg_id,
                    uid,
                    json.dumps(pack),
                )
            except (asyncpg.PostgresError, OSError, ConnectionError):
                self._memory_backup[str(user_id)] = pack
        else:
            self._memory_backup[str(user_id)] = pack

        return token

    async def has_parked_request(self, user_id: uuid.UUID | str) -> bool:
        """Check if an un-replayed parked request exists."""
        uid = (
            uuid.UUID(str(user_id))
            if isinstance(user_id, str) and "-" in str(user_id)
            else None
        )
        if uid is not None:
            try:
                pool = await get_db_pool()
                row = await pool.fetchrow(
                    """
                    SELECT id FROM grocer.inbound_messages
                    WHERE user_id = $1 AND status = 'awaiting_link'
                    LIMIT 1;
                    """,
                    uid,
                )
                if row:
                    return True
            except (asyncpg.PostgresError, OSError, ConnectionError):
                pass

        return str(user_id) in self._memory_backup

    def get_reconnect_button_payload(self, parked_token: str) -> dict[str, str]:
        """Generate WhatsApp CTA button payload (ADR 0010)."""
        return {
            "title": "Reconnect Swiggy",
            "action_id": f"connect_swiggy:{parked_token}",
        }

    async def pop_and_replay_request(
        self, user_id: uuid.UUID | str
    ) -> dict[str, Any] | None:
        """Atomically claim and retrieve the parked request for replay."""
        uid = (
            uuid.UUID(str(user_id))
            if isinstance(user_id, str) and "-" in str(user_id)
            else None
        )
        if uid is not None:
            try:
                pool = await get_db_pool()
                row = await pool.fetchrow(
                    """
                    UPDATE grocer.inbound_messages
                    SET status = 'processing'
                    WHERE id = (
                        SELECT id FROM grocer.inbound_messages
                        WHERE user_id = $1 AND status = 'awaiting_link'
                        ORDER BY created_at DESC LIMIT 1
                    )
                    RETURNING raw_payload;
                    """,
                    uid,
                )
                if row and row["raw_payload"]:
                    val = row["raw_payload"]
                    return json.loads(val) if isinstance(val, str) else val
            except (asyncpg.PostgresError, OSError, ConnectionError):
                pass

        return self._memory_backup.pop(str(user_id), None)


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
            rec.formattedAddress
            if hasattr(rec, "formattedAddress")
            else rec.get("formattedAddress", "")
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
            res.addressId if hasattr(res, "addressId") else res.get("addressId", "")
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

        # Lookup address label for button presentation
        label = "Address"
        try:
            addr_list = self.client.get_addresses(page=1, page_size=20)
            for a in addr_list.addresses:
                if a.id == address_id:
                    label = a.addressTag or a.addressCategory or "Address"
                    break
        except (KeyError, ValueError, AttributeError):
            label = "Address"

        return DeletionCheckResult(
            can_delete=True,
            confirmation_action_id=f"delete_address_confirm:{address_id}",
            confirmation_label=f"Confirm Delete: {label}",
        )

    def confirm_delete_address(self, address_id: str) -> bool:
        """Enforce deletion guardrail before triggering delete_address MCP tool."""
        check = self.can_delete_address(address_id)
        if not check.can_delete:
            raise ValueError(check.block_reason)

        self.client.delete_address(address_id=address_id)
        return True
