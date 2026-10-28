"""Address capabilities: switch, delete and the start of a typed add."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.agent.address_actions import (
    handle_delete_request,
    handle_switch_request,
)
from backend.agent.address_lifecycle import AddressOnboardingFlow
from backend.agent.router import Capability
from backend.channels.turn_context import TurnContext

logger = logging.getLogger(__name__)


async def handle_address_capability(
    ctx: TurnContext,
    decision: Any,
) -> dict[str, Any]:
    if decision.capability is Capability.SWITCH_ADDRESS:
        addr_reply = await handle_switch_request(
            decision, ctx.client, ctx.conn, ctx.user_id, ctx.address_id
        )
        await ctx.reply(addr_reply)
        await ctx.remember(addr_reply.text)
        return {"status": "address_switch_requested", "wa_id": ctx.wa_id}

    if decision.capability is Capability.DELETE_ADDRESS:
        addr_reply = await handle_delete_request(
            decision, ctx.client, ctx.address_id
        )
        await ctx.reply(addr_reply)
        await ctx.remember(addr_reply.text)
        return {"status": "address_delete_requested", "wa_id": ctx.wa_id}

    try:
        turn = AddressOnboardingFlow(ctx.client).start_from_text(ctx.text or "")
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning("Typed address start failed: %s", exc)
        turn = None

    if turn is None:
        add_text = (
            "I couldn't read that address. Send the full address with "
            "the area and PIN, or share a WhatsApp location pin."
        )
        await ctx.wa_client.send_text_message(to_wa_id=ctx.wa_id, text=add_text)
        await ctx.remember(add_text)
        return {"status": "address_add_failed", "wa_id": ctx.wa_id}

    await ctx.conn.execute(
        """
        INSERT INTO grocer.sessions (
            user_id, onboarding_state, onboarding_context, last_active_at
        )
        VALUES ($1, $2, $3::jsonb, now())
        ON CONFLICT (user_id) DO UPDATE SET
            onboarding_state = $2,
            onboarding_context = $3::jsonb,
            last_active_at = now();
        """,
        ctx.user_id,
        turn.next_step.value,
        json.dumps(turn.context),
    )
    await ctx.wa_client.send_text_message(to_wa_id=ctx.wa_id, text=turn.prompt)
    await ctx.remember(turn.prompt)
    return {
        "status": "address_add_started",
        "wa_id": ctx.wa_id,
        "step": turn.next_step.value,
    }
