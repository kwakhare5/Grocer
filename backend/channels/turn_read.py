"""Read capabilities: answer from live data and never write to the basket."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from backend.agent.read_actions import build_read_reply
from backend.agent.router import Capability
from backend.channels.turn_context import TurnContext


def _basket_notice(
    last_active_at: Any,
    cart: Any,
    idle_seconds: int = 3600,
) -> tuple[str, list[tuple[str, str]]] | None:
    """A new-day reminder for a basket the customer may have forgotten."""
    if last_active_at is None or cart is None or not cart.items:
        return None
    age = datetime.now(UTC) - last_active_at
    if age.total_seconds() < idle_seconds:
        return None
    count = sum(item.quantity for item in cart.items)
    to_pay = (
        cart.billBreakdown.toPay.value
        if cart.billBreakdown and cart.billBreakdown.toPay
        else None
    )
    total = f" ({to_pay})" if to_pay else ""
    return (
        f"Your basket still has {count} items{total}. Keep it, or clear it?",
        [("cart:keep", "Keep basket"), ("cart:clear", "Clear basket")],
    )


async def answer_read_capability(
    ctx: TurnContext,
    decision: Any,
    live_cart: Any,
) -> dict[str, Any]:
    coords: tuple[float, float] | None = None
    if decision.capability is Capability.TRACK_ORDER:
        coord_row = await ctx.conn.fetchrow(
            "SELECT latitude, longitude FROM grocer.address_coords WHERE address_id = $1;",
            ctx.address_id,
        )
        if coord_row:
            coords = (coord_row["latitude"], coord_row["longitude"])
        else:
            session_coords = await ctx.conn.fetchrow(
                "SELECT delivery_latitude, delivery_longitude FROM grocer.sessions WHERE user_id = $1;",
                ctx.user_id,
            )
            if (
                session_coords
                and session_coords["delivery_latitude"] is not None
                and session_coords["delivery_longitude"] is not None
            ):
                coords = (
                    session_coords["delivery_latitude"],
                    session_coords["delivery_longitude"],
                )

    read_reply = await build_read_reply(
        decision, ctx.client, ctx.address_id, coords
    )
    await ctx.reply(read_reply)

    notice = _basket_notice(
        ctx.session_row["last_active_at"] if ctx.session_row else None,
        live_cart,
    )
    if notice:
        await ctx.wa_client.send_quick_reply_buttons(
            to_wa_id=ctx.wa_id,
            body_text=notice[0],
            buttons=notice[1],
        )

    await ctx.remember(read_reply.text)

    if read_reply.pending_plan:
        from backend.agent.meal_planner import PLAN_TTL_MINUTES

        await ctx.conn.execute(
            "UPDATE grocer.sessions SET pending_plan = $2::jsonb, "
            "pending_plan_expires_at = now() + ($3 * interval '1 minute') "
            "WHERE user_id = $1;",
            ctx.user_id,
            json.dumps(read_reply.pending_plan),
            PLAN_TTL_MINUTES,
        )

    return {
        "status": "capability_answered",
        "capability": decision.capability.value,
        "wa_id": ctx.wa_id,
    }
