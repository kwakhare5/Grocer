"""Grocer — location-pin and typed-address onboarding."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("grocer.channels.onboarding")


async def handle_onboarding(
    conn: Any,
    msg: Any,
    user_id: Any,
    wa_client: Any,
    client: Any,
) -> dict[str, Any] | None:
    """Run one onboarding step; None means the message is not onboarding."""
    from backend.agent.address_lifecycle import (
        AddressOnboardingFlow,
        OnboardingStep,
    )

    if (
        msg.message_type == "location"
        and msg.latitude is not None
        and msg.longitude is not None
    ):
        try:
            flow = AddressOnboardingFlow(client)
            turn = flow.start_from_location(msg.latitude, msg.longitude)
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
            logger.warning("Onboarding geocode failed: %s", exc)
            await wa_client.send_text_message(
                to_wa_id=msg.sender_wa_id,
                text="Sorry, I couldn't resolve that location. Please share your pin again.",
            )
            return {
                "status": "onboarding_location_failed",
                "wa_id": msg.sender_wa_id,
            }

        await conn.execute(
            """
            INSERT INTO grocer.sessions (
                user_id, onboarding_state, onboarding_context,
                delivery_latitude, delivery_longitude, last_active_at
            )
            VALUES ($1, $2, $3::jsonb, $4, $5, now())
            ON CONFLICT (user_id) DO UPDATE SET
                onboarding_state = $2,
                onboarding_context = $3::jsonb,
                delivery_latitude = $4,
                delivery_longitude = $5,
                last_active_at = now();
            """,
            user_id,
            turn.next_step.value,
            json.dumps(turn.context),
            msg.latitude,
            msg.longitude,
        )
        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id, text=turn.prompt
        )
        return {
            "status": "onboarding_location_captured",
            "wa_id": msg.sender_wa_id,
        }

    session_onboarding = await conn.fetchrow(
        "SELECT onboarding_state, onboarding_context FROM grocer.sessions WHERE user_id = $1;",
        user_id,
    )
    onboarding_state = (
        session_onboarding["onboarding_state"] if session_onboarding else None
    )
    onboarding_ctx = (
        json.loads(session_onboarding["onboarding_context"])
        if session_onboarding and session_onboarding["onboarding_context"]
        else {}
    )

    if onboarding_state and onboarding_state != OnboardingStep.DONE.value:
        try:
            flow = AddressOnboardingFlow(client)
            turn = flow.advance(
                step=onboarding_state,
                context=onboarding_ctx,
                text=msg.text,
                wa_id=msg.sender_wa_id,
            )
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
            logger.warning("Onboarding step failed: %s", exc)
            await wa_client.send_text_message(
                to_wa_id=msg.sender_wa_id,
                text="Something went wrong saving your address. Please try again.",
            )
            return {
                "status": "onboarding_failed",
                "wa_id": msg.sender_wa_id,
            }

        if turn.completed and turn.address_id:
            await conn.execute(
                """
                INSERT INTO grocer.sessions (user_id, active_address_id, onboarding_state, onboarding_context, last_active_at)
                VALUES ($1, $2, NULL, NULL, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    active_address_id = $2,
                    onboarding_state = NULL,
                    onboarding_context = NULL,
                    last_active_at = now();
                """,
                user_id,
                turn.address_id,
            )
            await conn.execute(
                "UPDATE grocer.users SET display_name = $1, updated_at = now() WHERE id = $2;",
                turn.context.get("name") or "",
                user_id,
            )
            lat = turn.context.get("latitude")
            lng = turn.context.get("longitude")
            if lat is not None and lng is not None:
                await conn.execute(
                    """
                    INSERT INTO grocer.address_coords (address_id, user_id, latitude, longitude)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (address_id) DO UPDATE SET
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude;
                    """,
                    turn.address_id,
                    user_id,
                    lat,
                    lng,
                )
        else:
            await conn.execute(
                """
                INSERT INTO grocer.sessions (user_id, onboarding_state, onboarding_context, last_active_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    onboarding_state = $2,
                    onboarding_context = $3::jsonb,
                    last_active_at = now();
                """,
                user_id,
                turn.next_step.value,
                json.dumps(turn.context),
            )

        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id, text=turn.prompt
        )
        return {
            "status": "onboarding_advanced",
            "wa_id": msg.sender_wa_id,
            "step": turn.next_step.value,
        }

    return None
