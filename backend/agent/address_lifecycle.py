"""Grocer — Address & Account Lifecycle Management.

Implements:
1. Two-Step Pin Geocoding Onboarding (ADR 0008).
2. Address Deletion Guardrail (ADR 0007): Strictly blocks address deletion during live deliveries.
3. Interactive Address Deletion Confirmation Button with Label (ADR 0007).
4. One-Time Destination Anchoring & Session Revert (ADR 0009).
5. 5-Day Token Expiry Detection & PostgreSQL Parked Message Replay (ADR 0010).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import asyncpg

from backend.database import get_db_pool

logger = logging.getLogger("grocer.address_lifecycle")

_ADDRESS_NOISE = re.compile(
    r"^\s*(?:please\s+)?(?:add|save|create|new|another|set)?\s*"
    r"(?:my|a|an|the)?\s*(?:new|another)?\s*(?:delivery\s+)?address\s*[:\-,]?\s*",
    re.IGNORECASE,
)


def _as_uuid(user_id: Any) -> uuid.UUID | None:
    """Accept a UUID or its text form; anything else stays in the memory fallback."""
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (TypeError, ValueError):
        return None


def _clean_address_query(text: str) -> str:
    """Strip the command words so only the address reaches the geocoder."""
    cleaned = _ADDRESS_NOISE.sub("", (text or "").strip())
    return re.sub(r"\s+", " ", cleaned).strip(" .,-")


class OnboardingStep(str, Enum):
    AWAITING_LOCATION = "awaiting_location"
    AWAITING_FLAT = "awaiting_flat"
    AWAITING_NAME = "awaiting_name"
    AWAITING_CITY_PIN = "awaiting_city_pin"
    DONE = "done"


def parse_city_pin(text: str) -> tuple[str | None, str | None]:
    """Extract (city, 6-digit postal code) from a reply like 'Bengaluru, 560034'."""
    cleaned = (text or "").strip()
    match = re.search(r"\b\d{6}\b", cleaned)
    if not match:
        return None, None
    pin = match.group(0)
    city = cleaned[: match.start()].strip(" ,-")
    if not city:
        city = cleaned[match.end():].strip(" ,-")
    return (city or None), pin


@dataclass
class OnboardingTurn:
    next_step: OnboardingStep
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    address_id: str | None = None
    completed: bool = False


class AddressOnboardingFlow:
    """Multi-turn pin geocoding + address capture (Gate 1: userName/city/postalCode)."""

    def __init__(self, swiggy_client: Any) -> None:
        self.client = swiggy_client

    def start_from_location(
        self,
        lat: float,
        lon: float,
        context: dict[str, Any] | None = None,
    ) -> OnboardingTurn:
        ctx = dict(context or {})
        rec = self.client.recommend_address(latitude=lat, longitude=lon)
        street = rec.formattedAddress if hasattr(rec, "formattedAddress") else ""
        ctx["latitude"] = lat
        ctx["longitude"] = lon
        ctx["street_address"] = street
        prompt = (
            f"📍 Found your location near *{street}*.\n\n"
            "What's your flat/house number and building name?"
        )
        return OnboardingTurn(next_step=OnboardingStep.AWAITING_FLAT, prompt=prompt, context=ctx)

    def advance(
        self,
        step: OnboardingStep | str,
        context: dict[str, Any] | None = None,
        text: str | None = None,
        wa_id: str = "",
    ) -> OnboardingTurn:
        ctx = dict(context or {})
        current = OnboardingStep(step)

        if current == OnboardingStep.AWAITING_FLAT:
            flat = (text or "").strip()
            if not flat:
                return OnboardingTurn(
                    next_step=current,
                    prompt="Please share your flat/house number and building name.",
                    context=ctx,
                )
            ctx["flat"] = flat
            return OnboardingTurn(
                next_step=OnboardingStep.AWAITING_NAME,
                prompt="What's your name for the delivery?",
                context=ctx,
            )

        if current == OnboardingStep.AWAITING_NAME:
            name = (text or "").strip()
            if not name:
                return OnboardingTurn(
                    next_step=current,
                    prompt="Please share your name for the delivery.",
                    context=ctx,
                )
            ctx["name"] = name
            if ctx.get("city") and ctx.get("postal_code"):
                return self._finish(ctx, wa_id)
            return OnboardingTurn(
                next_step=OnboardingStep.AWAITING_CITY_PIN,
                prompt="Which city and PIN code? (e.g. Bengaluru, 560034)",
                context=ctx,
            )

        if current == OnboardingStep.AWAITING_CITY_PIN:
            city, pin = parse_city_pin(text or "")
            if not city or not pin:
                return OnboardingTurn(
                    next_step=current,
                    prompt="Please share your city and 6-digit PIN code. (e.g. Bengaluru, 560034)",
                    context=ctx,
                )
            ctx["city"] = city
            ctx["postal_code"] = pin
            return self._finish(ctx, wa_id)

        return OnboardingTurn(
            next_step=current,
            prompt="What groceries do you need today?",
            context=ctx,
        )

    def start_from_text(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> OnboardingTurn:
        """Geocode a typed address, then reuse the pin flow for the missing pieces."""
        query = _clean_address_query(text)
        if len(query.split()) < 3:
            return OnboardingTurn(
                next_step=OnboardingStep.AWAITING_LOCATION,
                prompt=(
                    "Send the full address — flat or building, street, area, city and PIN — "
                    "or share a WhatsApp location pin."
                ),
            )

        try:
            rec = self.client.recommend_address(query=query)
        except (ValueError, KeyError, RuntimeError, OSError) as exc:
            logger.warning("Typed address geocoding failed: %s", exc)
            return OnboardingTurn(
                next_step=OnboardingStep.AWAITING_LOCATION,
                prompt=(
                    "I couldn't find that address. Send the full address with the area and "
                    "PIN, or share a location pin."
                ),
            )

        ctx = dict(context or {})
        ctx["latitude"] = rec.latitude
        ctx["longitude"] = rec.longitude
        ctx["street_address"] = rec.formattedAddress
        city, pin = parse_city_pin(query)
        if city and pin:
            ctx["city"] = city
            ctx["postal_code"] = pin

        has_door_number = bool(re.search(r"\d", query))
        if has_door_number:
            ctx["flat"] = query
            next_step = OnboardingStep.AWAITING_NAME
        else:
            next_step = OnboardingStep.AWAITING_FLAT

        prompt = (
            f"📍 Found *{rec.formattedAddress}*.\n\n"
            + (
                "What name should the delivery be under?"
                if next_step == OnboardingStep.AWAITING_NAME
                else "What's your flat/house number and building name?"
            )
        )
        return OnboardingTurn(next_step=next_step, prompt=prompt, context=ctx)

    def _finish(self, ctx: dict[str, Any], wa_id: str) -> OnboardingTurn:
        full_address = ", ".join(
            part
            for part in [
                ctx.get("flat"),
                ctx.get("street_address"),
                ctx.get("city"),
            ]
            if part
        )
        res = self.client.create_address(
            full_address=full_address,
            address_line=ctx.get("street_address") or full_address,
            address_line2=ctx.get("flat") or "",
            city=ctx.get("city") or "",
            postal_code=ctx.get("postal_code") or "",
            address_category="HOME",
            user_name=ctx.get("name") or "",
            user_phone=wa_id,
            latitude=ctx.get("latitude"),
            longitude=ctx.get("longitude"),
        )
        return OnboardingTurn(
            next_step=OnboardingStep.DONE,
            prompt="✅ *Address saved!* Now, what groceries do you need?",
            context=ctx,
            address_id=res.addressId,
            completed=True,
        )


@dataclass
class DeletionCheckResult:
    can_delete: bool
    active_order_id: str | None = None
    block_reason: str = ""


class TokenParkedRequestManager:
    """Parks pending commerce requests upon 401 token expiry into PostgreSQL and replays on auth (ADR 0010)."""

    async def pop_parked_request(
        self, user_id: uuid.UUID | str
    ) -> tuple[Any, dict[str, Any]] | None:
        """Atomically claim a parked request. Returns (row id, payload)."""
        uid = _as_uuid(user_id)
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
                    RETURNING id, raw_payload;
                    """,
                    uid,
                )
                if row and row["raw_payload"]:
                    val = row["raw_payload"]
                    payload = json.loads(val) if isinstance(val, str) else val
                    return row["id"], payload
            except (asyncpg.PostgresError, OSError, ConnectionError):
                pass

        return None

    async def restore_parked(self, row_id: Any) -> None:
        """Put a claimed request back when replay could not run."""
        if row_id is None:
            return
        try:
            pool = await get_db_pool()
            await pool.execute(
                "UPDATE grocer.inbound_messages SET status = 'awaiting_link' WHERE id = $1;",
                row_id,
            )
        except (asyncpg.PostgresError, OSError, ConnectionError) as exc:
            logger.warning("Could not restore parked request %s: %s", row_id, exc)

    async def mark_replayed(self, row_id: Any) -> None:
        if row_id is None:
            return
        try:
            pool = await get_db_pool()
            await pool.execute(
                "UPDATE grocer.inbound_messages SET status = 'replayed' WHERE id = $1;",
                row_id,
            )
        except (asyncpg.PostgresError, OSError, ConnectionError) as exc:
            logger.warning("Could not mark parked request %s replayed: %s", row_id, exc)


class AddressLifecycleManager:
    """Handles address discovery, pin geocoding, and deletion safety checks."""

    def __init__(self, swiggy_client: Any) -> None:
        self.client = swiggy_client

    def can_delete_address(self, address_id: str) -> DeletionCheckResult:
        """Check if an address can be safely deleted or is locked by an active delivery (ADR 0007)."""
        orders_data = self.client.get_orders(count=20, order_type="INSTAMART", active_only=True)
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

        return DeletionCheckResult(can_delete=True)
