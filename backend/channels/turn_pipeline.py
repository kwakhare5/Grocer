"""Grocer — One conversational turn: route, read, plan, add, receipt."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from backend.agent.approval import create_checkout_approval
from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.agent.composite_cart import MAX_RECEIPT_ITEM_LINES, CompositeCartManager
from backend.agent.customer_advocate import get_session_budget_cap
from backend.channels.button_router import format_cap_warning, send_receipt
from backend.integrations.commerce.swiggy_client import SwiggyClient
from backend.observability import set_turn_context

logger = logging.getLogger("grocer.channels.turn_pipeline")


def _fresh_button_id(added_lines: list[Any]) -> str | None:
    """Encode the just-added lines so 'Keep only new' needs no stored state."""
    parts: list[str] = []
    for item in added_lines:
        if item.quantity < 1 or not item.sku_id:
            return None
        parts.append(f"{item.spin_id}:{item.sku_id}:{item.quantity}")
    if not parts:
        return None
    encoded = "cart:fresh:" + "|".join(parts)
    return encoded if len(encoded) <= 250 else None


async def run_commerce_turn(
    turn_client: SwiggyClient,
    msg: Any,
    user_id: Any,
    conn: Any,
    wa_client: Any,
) -> dict[str, Any]:
    # Resolve active address and past dialogue history
    session_row = await conn.fetchrow(
        "SELECT active_address_id, history, last_active_at, "
        "pending_plan, (pending_plan_expires_at > now()) AS plan_fresh "
        "FROM grocer.sessions WHERE user_id = $1;",
        user_id,
    )
    active_addr_id = (
        session_row["active_address_id"] if session_row else None
    )
    raw_history = session_row["history"] if session_row else None
    if raw_history:
        try:
            session_history = (
                json.loads(raw_history)
                if isinstance(raw_history, str)
                else raw_history
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            session_history = []
    else:
        session_history = []

    from backend.agent.address_actions import ensure_active_address

    address_count = 1
    if not active_addr_id:
        try:
            active_addr_id = await ensure_active_address(
                conn, user_id, turn_client
            )
            address_count = 1 if active_addr_id else 0
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as addr_err:
            logger.warning("Could not fetch user addresses: %s", addr_err)

    from backend.channels.turn_context import TurnContext

    ctx = TurnContext(
        conn=conn,
        user_id=user_id,
        wa_id=msg.sender_wa_id,
        text=msg.text,
        client=turn_client,
        wa_client=wa_client,
        address_id=active_addr_id,
        history=session_history,
        session_row=session_row,
    )

    # 0. A numbered reply to the plan on screen picks items with
    # no model call. Only number-shaped text is taken.
    pending_plan = session_row["pending_plan"] if session_row else None
    plan_fresh = bool(session_row and session_row["plan_fresh"])
    from backend.agent.meal_planner import (
        clear_pending_plan,
        decode_pending_plan,
        parse_pick_indexes,
        plan_items,
    )

    if pending_plan and not plan_fresh:
        await clear_pending_plan(conn, user_id)
    plan = decode_pending_plan(pending_plan, plan_fresh)
    if plan is not None:
        indexes = parse_pick_indexes(msg.text, len(plan_items(plan)))
        if indexes and not active_addr_id:
            await wa_client.send_text_message(
                to_wa_id=msg.sender_wa_id,
                text="Share your delivery location pin and I'll add the plan.",
            )
            return {
                "status": "location_pin_requested",
                "wa_id": msg.sender_wa_id,
            }
        if indexes:
            from backend.channels.button_router import confirm_plan

            try:
                picked = await confirm_plan(
                    conn,
                    wa_client,
                    msg.sender_wa_id,
                    user_id,
                    active_addr_id,
                    turn_client,
                    plan,
                    indexes,
                )
            except (
                ValueError,
                KeyError,
                RuntimeError,
                OSError,
                httpx.HTTPError,
            ) as exc:
                logger.warning("Plan pick failed: %s", exc)
                picked = None
            if picked is None:
                await wa_client.send_text_message(
                    to_wa_id=msg.sender_wa_id,
                    text="That plan didn't finish. Ask me for your basket before paying.",
                )
                return {
                    "status": "plan_add_failed",
                    "wa_id": msg.sender_wa_id,
                }
            if picked["status"] == "plan_picked":
                await ctx.remember(
                    "Added the items you picked from the plan."
                )
            return picked

    # 1. Capability routing (ADR 0012). Read capabilities are answered
    # here and can never write. Basket requests continue below.
    from backend.agent.read_actions import (
        NOT_READY_REPLY,
        format_disambiguation_choices,
    )
    from backend.agent.router import (
        Capability,
        SafetyClass,
        route_message,
    )

    basket_summary: list[dict[str, Any]] = []
    live_cart = None
    try:
        live_cart = await asyncio.to_thread(
            turn_client.get_cart, active_addr_id
        )
        basket_summary = [
            {"name": item.itemName, "quantity": item.quantity}
            for item in live_cart.items
        ]
    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as cart_err:
        logger.warning("Could not read basket for routing: %s", cart_err)

    decision = await asyncio.to_thread(
        route_message, msg.text, session_history, None, basket_summary
    )
    set_turn_context(
        capability=decision.capability.value,
        safety=decision.safety.value,
    )

    if address_count == 0:
        prompt_text = (
            decision.reply
            if decision.capability is Capability.CHAT
            else None
        ) or (
            "Please share your WhatsApp delivery location pin or an address "
            "so I can check your local Instamart store."
        )
        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id, text=prompt_text
        )
        return {
            "status": "location_pin_requested",
            "wa_id": msg.sender_wa_id,
        }

    if decision.safety is SafetyClass.READ:
        from backend.channels.turn_read import (
            answer_read_capability,
        )

        return await answer_read_capability(ctx, decision, live_cart)

    if decision.capability in (
        Capability.SWITCH_ADDRESS,
        Capability.DELETE_ADDRESS,
    ):
        from backend.channels.turn_address import (
            handle_address_capability,
        )

        return await handle_address_capability(ctx, decision)

    if decision.capability is Capability.REPORT_ISSUE:
        from backend.agent.order_actions import handle_report_issue

        report = await handle_report_issue(decision, turn_client)
        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id, text=report.text
        )
        await ctx.remember(report.text)
        return {
            "status": "issue_reported",
            "wa_id": msg.sender_wa_id,
        }

    if decision.capability is Capability.ADD_ADDRESS:
        from backend.channels.turn_address import (
            handle_address_capability,
        )

        return await handle_address_capability(ctx, decision)

    if decision.capability in (
        Capability.CLEAR_BASKET,
        Capability.SET_ITEM,
        Capability.REMOVE_ITEM,
        Capability.REORDER,
    ):
        from backend.channels.turn_basket import (
            handle_basket_capability,
        )

        return await handle_basket_capability(ctx, decision)

    # A request to add is just an add. Python reads the basket and
    # increments the existing line, so no "add or set?" question.
    if decision.capability is not Capability.ADD_ITEMS:
        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id, text=NOT_READY_REPLY
        )
        return {
            "status": "capability_unavailable",
            "capability": decision.capability.value,
            "wa_id": msg.sender_wa_id,
        }

    # 2. Items come from the router. No second classification call.
    from backend.channels.turn_add import describe_item, plan_add

    add_plan = await plan_add(ctx, decision, address_count)
    if isinstance(add_plan, dict):
        return add_plan

    items_to_add = add_plan.items_to_add
    choice_prompts = add_plan.choice_prompts
    unfound_queries = add_plan.unfound_queries
    alternative_hints = add_plan.alternative_hints
    vague_spins = add_plan.vague_spins

    if items_to_add:
        cart_mgr = CompositeCartManager(turn_client)
        cart_res = cart_mgr.assemble_and_update_cart(
            items_to_add=items_to_add,
            address_id=active_addr_id,
            auto_optimize_coupons=True,
        )

        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=cart_res.cart,
            address_id=active_addr_id or "default",
        )

        to_pay_formatted = format_paise_to_rupees(approval.to_pay_paise)
        receipt_body = cart_res.receipt_text
        if unfound_queries:
            detail = ", ".join(unfound_queries)
            if alternative_hints:
                detail += "\nSimilar: " + "; ".join(alternative_hints)
            receipt_body += f"\n\n⚠️ *Not added:* {detail}"
        pending_names = [
            describe_item(target) for target, _ in choice_prompts
        ]
        if pending_names:
            receipt_body += (
                "\n\n⚠️ *Waiting for your pick:* "
                + ", ".join(pending_names)
            )
        cap_paise = await get_session_budget_cap(conn, user_id)
        if approval.to_pay_paise > int(cap_paise):
            receipt_body += format_cap_warning(cap_paise)

        buttons: list[tuple[str, str]] = [
            (f"pay:{approval.id}", f"Pay {to_pay_formatted}")
        ]
        if len(cart_res.cart.items) > MAX_RECEIPT_ITEM_LINES:
            buttons.append(("cart:view", "View basket"))
        fresh_id = _fresh_button_id(cart_res.added_lines)
        if cart_res.baseline_count and fresh_id and len(buttons) < 3:
            buttons.append((fresh_id, "Keep only new"))
        if (
            len(vague_spins) == 1
            and len(items_to_add) == 1
            and len(buttons) < 3
        ):
            buttons.append(
                (f"item:change:{next(iter(vague_spins))}", "Change item")
            )

        await send_receipt(
            wa_client,
            msg.sender_wa_id,
            receipt_body,
            buttons,
        )

        for target, cands in choice_prompts[:2]:
            choice_text, choice_buttons = format_disambiguation_choices(
                describe_item(target), cands, target.quantity
            )
            await wa_client.send_quick_reply_buttons(
                to_wa_id=msg.sender_wa_id,
                body_text=choice_text,
                buttons=choice_buttons,
            )

        session_history.append({"role": "user", "text": msg.text})
        session_history.append(
            {"role": "assistant", "text": receipt_body}
        )
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, history, last_active_at)
            VALUES ($1, $2::jsonb, now())
            ON CONFLICT (user_id) DO UPDATE SET history = $2::jsonb, last_active_at = now();
            """,
            user_id,
            json.dumps(session_history[-12:]),
        )
        return {
            "status": "cart_updated",
            "approval_id": approval.id,
            "to_pay_paise": approval.to_pay_paise,
        }

    suffix = ""
    if alternative_hints:
        suffix = "\n\nSimilar items: " + "; ".join(alternative_hints)
    await wa_client.send_text_message(
        to_wa_id=msg.sender_wa_id,
        text=(
            f"Sorry, I couldn't find items matching '{msg.text}' at your "
            f"local dark store. Could you try a different brand or item name?{suffix}"
        ),
    )
    return {"status": "no_match", "query": msg.text}

