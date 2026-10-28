"""Basket capabilities that are not an add: change, clear and reorder."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.agent.basket_actions import (
    BasketReply,
    handle_change_request,
    handle_clear_request,
)
from backend.agent.order_actions import OrderReply, handle_reorder_request
from backend.agent.router import Capability
from backend.channels.turn_context import TurnContext

logger = logging.getLogger(__name__)


async def handle_basket_capability(
    ctx: TurnContext,
    decision: Any,
) -> dict[str, Any]:
    if decision.capability is Capability.REORDER:
        try:
            order_reply = await handle_reorder_request(
                decision, ctx.client, ctx.address_id, ctx.text
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
        ) as exc:
            logger.warning("Reorder preview failed: %s", exc)
            order_reply = OrderReply(
                "I couldn't read your past orders just now. Please try again."
            )

        await ctx.reply(order_reply)
        await ctx.remember(order_reply.text)
        return {"status": "reorder_requested", "wa_id": ctx.wa_id}

    try:
        if decision.capability is Capability.CLEAR_BASKET:
            basket_reply = await handle_clear_request(ctx.client, ctx.address_id)
        else:
            basket_reply = await handle_change_request(
                decision, ctx.client, ctx.address_id
            )
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning("Basket change failed: %s", exc)
        basket_reply = BasketReply(
            "I couldn't read your basket just now. Please try again."
        )

    await ctx.reply(basket_reply)
    await ctx.remember(basket_reply.text)
    return {
        "status": (
            "basket_change_requested" if basket_reply.buttons else "basket_changed"
        ),
        "capability": decision.capability.value,
        "wa_id": ctx.wa_id,
    }
