"""Grocer — Fast 50ms Interactive Button Dispatcher (Zero LLM Lag)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import asyncpg
import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees

logger = logging.getLogger("grocer.button_router")


RECEIPT_BODY_LIMIT = 1024
RECEIPT_FOLLOW_UP = "Ready when you are. Tap below to pay or clear the basket."
BUTTON_UNAVAILABLE = (
    "I couldn't complete that just now. Nothing changed. Please try again."
)
BUTTON_UNKNOWN_USER = (
    "I couldn't find your account for that button. "
    "Send your message again and I'll rebuild it."
)
BUTTON_STALE = "That button is out of date. Send your request again and I'll rebuild it."
AUTH_EXPIRED = "Your Swiggy login has expired. Please reconnect your account."

_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def _log_background_result(task: asyncio.Task[Any]) -> None:
    _BACKGROUND_TASKS.discard(task)
    if not task.cancelled():
        exc = task.exception()
        if exc:
            logger.warning("Background WhatsApp send failed: %s", exc)


def _spawn(coro: Any) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_log_background_result)


async def _fetch_user_id(conn: Any, wa_id: str) -> Any:
    return await conn.fetchval(
        "SELECT id FROM grocer.users WHERE wa_id = $1;", wa_id
    )


async def _fetch_active_address(conn: Any, user_id: Any) -> Any:
    return await conn.fetchval(
        "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
        user_id,
    )


async def _load_button_context(conn: Any, wa_id: str) -> tuple[Any, Any]:
    user_id = await _fetch_user_id(conn, wa_id)
    if not user_id:
        return None, None
    return user_id, await _fetch_active_address(conn, user_id)


def _auth_result(
    button_id: str,
    *,
    message: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "auth_required", "action": button_id}
    if message is not None:
        result["message"] = message
    if approval_id is not None:
        result["approval_id"] = approval_id
    return result


def format_cap_warning(cap_paise: int) -> str:
    """The one cap warning used by every receipt path."""
    return (
        f"\n\n⚠️ This is above your "
        f"{format_paise_to_rupees(int(cap_paise))} safety cap. "
        "You'll be asked to raise it when you tap Pay."
    )


def build_pay_receipt(
    body: str,
    approval: Any,
    cap_paise: int,
    *,
    warnings: list[str] | None = None,
    extra_buttons: list[tuple[str, str]] | None = None,
    include_clear: bool = False,
) -> tuple[str, list[tuple[str, str]]]:
    """One pay button, one cap check and one button order for every add receipt."""
    for warning in warnings or []:
        body += warning
    if approval.to_pay_paise > int(cap_paise):
        body += format_cap_warning(cap_paise)

    buttons = [
        (
            f"pay:{approval.id}",
            f"Pay {format_paise_to_rupees(int(approval.to_pay_paise))}",
        )
    ]
    buttons.extend(extra_buttons or [])
    if include_clear:
        buttons.append(("cart:clear", "Clear basket"))
    return body, buttons[:3]


async def _reply_and_return(
    wa_client: Any,
    wa_id: str,
    button_id: str,
    text: str,
    status: str = "button_unavailable",
) -> dict[str, Any]:
    await wa_client.send_text_message(to_wa_id=wa_id, text=text)
    return {"status": status, "action": button_id, "message": text}


async def send_receipt(
    wa_client: Any,
    wa_id: str,
    body: str,
    buttons: list[tuple[str, str]],
) -> None:
    """A long basket is never cut off: full body as text, buttons in a short follow-up."""
    if len(body) <= RECEIPT_BODY_LIMIT:
        await wa_client.send_quick_reply_buttons(
            to_wa_id=wa_id, body_text=body, buttons=buttons
        )
        return
    await wa_client.send_text_message(to_wa_id=wa_id, text=body)
    await wa_client.send_quick_reply_buttons(
        to_wa_id=wa_id, body_text=RECEIPT_FOLLOW_UP, buttons=buttons
    )


async def send_add_receipt(
    conn: Any,
    wa_client: Any,
    wa_id: str,
    user_id: Any,
    active: str | None,
    cart: Any,
    status: str,
    action: str | None,
) -> dict[str, Any]:
    """One payable receipt for any button path that writes the basket."""
    from backend.agent.approval import create_checkout_approval
    from backend.agent.composite_cart import format_cart_receipt
    from backend.agent.customer_advocate import get_session_budget_cap

    approval = await create_checkout_approval(
        conn=conn,
        user_id=str(user_id),
        cart=cart,
        address_id=active or "default",
    )
    body = format_cart_receipt(cart)
    cap_paise = await get_session_budget_cap(conn, user_id)
    body, buttons = build_pay_receipt(
        body, approval, cap_paise, include_clear=True
    )
    await send_receipt(wa_client, wa_id, body, buttons)
    return {
        "status": status,
        "action": action,
        "approval_id": str(approval.id),
        "to_pay_paise": approval.to_pay_paise,
    }


async def confirm_plan(
    conn: Any,
    wa_client: Any,
    wa_id: str,
    user_id: Any,
    active: str | None,
    client: Any,
    plan: Any,
    indexes: list[int] | None = None,
) -> dict[str, Any]:
    """Write the confirmed rows of a stored plan, then one payable receipt."""
    from backend.agent.composite_cart import CompositeCartManager
    from backend.agent.meal_planner import clear_pending_plan, resolve_plan_items

    items, missing, error = await resolve_plan_items(client, active, plan, indexes)
    if error or not items:
        text = error or "Nothing from that plan is in stock right now."
        await wa_client.send_text_message(to_wa_id=wa_id, text=text)
        return {"status": "plan_unavailable", "message": text}
    manager = CompositeCartManager(client)
    cart_res = await asyncio.to_thread(
        manager.assemble_and_update_cart,
        items_to_add=items,
        address_id=active,
        auto_optimize_coupons=True,
    )
    await clear_pending_plan(conn, user_id)
    result = await send_add_receipt(
        conn,
        wa_client,
        wa_id,
        user_id,
        active,
        cart_res.cart,
        "plan_picked" if indexes else "plan_added",
        "plan:pick" if indexes else "plan:add",
    )
    if missing:
        await wa_client.send_text_message(
            to_wa_id=wa_id,
            text="Not at this store right now: " + ", ".join(missing) + ".",
        )
    return result


async def dispatch_button_action(
    button_id: str,
    wa_id: str,
    pool: asyncpg.Pool | None = None,
    swiggy_client: Any | None = None,
    message_type: str = "button_reply",
    wa_client: Any | None = None,
) -> dict[str, Any]:
    """Execute interactive WhatsApp button taps directly in Python in <50ms.

    Bypasses Gemini LLM completely for instant app-like responsiveness.
    """
    logger.info("Dispatching fast button action: %s", button_id)

    prefix, _, target_id = button_id.partition(":")
    target_arg = target_id if target_id else None

    # 1. Basket clear / remove / quantity confirmation taps
    if prefix == "cart":
        from backend.agent.basket_actions import (
            BasketReply,
            apply_add_new_item,
            apply_add_quantity,
            apply_clear,
            apply_remove,
            apply_set_quantity,
            apply_swap,
        )
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.token_vault import resolve_user_client

        wa_client = wa_client or WhatsAppClient()

        if button_id == "cart:keep":
            text = "Okay, your basket is unchanged."
            _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=text))
            return {"status": "basket_kept", "action": button_id, "message": text}

        if not pool:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        async with pool.acquire() as conn:
            user_id, active = await _load_button_context(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client, wa_id, button_id, BUTTON_UNKNOWN_USER, "unknown_user"
                )

            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                _spawn(
                    wa_client.send_text_message(to_wa_id=wa_id, text=AUTH_EXPIRED)
                )
                return _auth_result(button_id)

            special_result: dict[str, Any] | None = None
            try:
                if button_id == "cart:view":
                    from backend.agent.composite_cart import format_cart_receipt

                    cart = await asyncio.to_thread(client.get_cart, active)
                    reply = BasketReply(format_cart_receipt(cart, max_item_lines=60))
                elif button_id == "cart:clear":
                    reply = await apply_clear(client, active)
                elif button_id.startswith("cart:fresh:"):
                    from backend.agent.basket_actions import apply_keep_only_new

                    cart, err = await apply_keep_only_new(client, active, button_id)
                    if err or not cart.items:
                        reply = BasketReply(err or "Your basket is empty.")
                    else:
                        special_result = await send_add_receipt(
                            conn,
                            wa_client,
                            wa_id,
                            user_id,
                            active,
                            cart,
                            "cart_fresh",
                            button_id,
                        )
                else:
                    action, _, rest = (target_arg or "").partition(":")
                    if action == "rm":
                        reply = await apply_remove(client, active, rest)
                    elif action == "qty":
                        spin_id, _, quantity_text = rest.rpartition(":")
                        reply = await apply_set_quantity(
                            client, active, spin_id, int(quantity_text)
                        )
                    elif action == "addqty":
                        spin_id, _, quantity_text = rest.rpartition(":")
                        reply = await apply_add_quantity(
                            client, active, spin_id, int(quantity_text)
                        )
                    elif action == "add":
                        spin_id, _, quantity_text = rest.rpartition(":")
                        reply = await apply_add_new_item(
                            client, active, spin_id, int(quantity_text)
                        )
                    elif action == "swap":
                        old_spin, _, remainder = rest.partition(":")
                        new_spin, _, new_sku = remainder.partition(":")
                        reply = await apply_swap(
                            client, active, old_spin, new_spin, new_sku
                        )
                    else:
                        reply = BasketReply("Nothing changed.")
            except (ValueError, KeyError, RuntimeError, OSError, httpx.HTTPError) as exc:
                logger.warning("Basket button action failed: %s", exc)
                reply = BasketReply("That change didn't go through. Nothing was changed.")

        if special_result is not None:
            return special_result
        _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {"status": "basket_updated", "action": button_id, "message": reply.text}

    # 1b. Meal plan confirmation taps (ADR 0009). The plan is stored, not encoded.
    if prefix == "plan" and target_arg:
        from backend.agent.meal_planner import (
            clear_pending_plan,
            decode_pending_plan,
            plan_items,
        )
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.swiggy_client import SwiggyAuthExpiredError
        from backend.integrations.commerce.token_vault import resolve_user_client

        wa_client = wa_client or WhatsAppClient()

        if target_arg not in {"add", "pick"} or not pool:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        async with pool.acquire() as conn:
            user_id = await _fetch_user_id(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client, wa_id, button_id, BUTTON_UNKNOWN_USER, "unknown_user"
                )

            row = await conn.fetchrow(
                "SELECT active_address_id, pending_plan, "
                "(pending_plan_expires_at > now()) AS plan_fresh "
                "FROM grocer.sessions WHERE user_id = $1;",
                user_id,
            )
            active = row["active_address_id"] if row else None
            plan = decode_pending_plan(
                row["pending_plan"] if row else None,
                bool(row and row["plan_fresh"]),
            )
            if not plan_items(plan):
                await clear_pending_plan(conn, user_id)
                text = "That plan expired. Ask me to plan the meal again."
                await wa_client.send_text_message(to_wa_id=wa_id, text=text)
                return {
                    "status": "plan_unavailable",
                    "action": button_id,
                    "message": text,
                }

            if target_arg == "pick":
                text = "Reply with the numbers you want, like 1 and 3. I'll add only those."
                await wa_client.send_text_message(to_wa_id=wa_id, text=text)
                return {
                    "status": "plan_pick_requested",
                    "action": button_id,
                    "message": text,
                }

            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                await wa_client.send_text_message(to_wa_id=wa_id, text=AUTH_EXPIRED)
                return _auth_result(button_id)

            try:
                confirmed = await confirm_plan(
                    conn, wa_client, wa_id, user_id, active, client, plan
                )
                confirmed.setdefault("action", button_id)
                return confirmed
            except (
                ValueError,
                KeyError,
                RuntimeError,
                OSError,
                httpx.HTTPError,
                SwiggyAuthExpiredError,
            ) as exc:
                logger.warning("Meal plan add failed: %s", exc)

        await wa_client.send_text_message(
            to_wa_id=wa_id,
            text="That plan didn't finish. Ask me for your basket before paying.",
        )
        return {"status": "plan_add_failed", "action": button_id}

    # 2. Reorder confirmation taps
    if prefix == "reorder":
        from backend.agent.order_actions import OrderReply, apply_reorder
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.token_vault import resolve_user_client

        wa_client = wa_client or WhatsAppClient()

        if not pool or not target_arg:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        async with pool.acquire() as conn:
            user_id, active = await _load_button_context(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client, wa_id, button_id, BUTTON_UNKNOWN_USER, "unknown_user"
                )

            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                _spawn(
                    wa_client.send_text_message(to_wa_id=wa_id, text=AUTH_EXPIRED)
                )
                return _auth_result(button_id)

            try:
                reply = await apply_reorder(client, active, target_arg)
            except (ValueError, KeyError, RuntimeError, OSError) as exc:
                logger.warning("Reorder button action failed: %s", exc)
                reply = OrderReply("That reorder didn't go through. Nothing was changed.")

        _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {"status": "reorder_applied", "action": button_id, "message": reply.text}

    # 3. Checkout Payment Authorization (Lock 1 Authority -> 3-Lock Execution)
    if prefix == "pay":
        from backend.channels.whatsapp_client import WhatsAppClient

        wa_client = wa_client or WhatsAppClient()
        if pool and target_arg:
            from backend.agent.checkout_executor import execute_3_lock_checkout
            from backend.integrations.commerce.token_vault import resolve_user_client

            async with pool.acquire() as conn:
                user_id = await _fetch_user_id(conn, wa_id)

            if user_id:
                client = swiggy_client or await resolve_user_client(user_id)
                if client is None:
                    # The approval is untouched: nothing was claimed, so the same
                    # button still works once the customer reconnects.
                    return _auth_result(
                        button_id,
                        approval_id=target_arg,
                        message=AUTH_EXPIRED,
                    )

                checkout_res = await execute_3_lock_checkout(
                    pool=pool,
                    swiggy_client=client,
                    user_id=str(user_id),
                    approval_id=target_arg,
                    message_type=message_type,
                    button_id=button_id,
                )

                if checkout_res.success and checkout_res.bridge_url:
                    _spawn(
                        wa_client.send_cta_url_button(
                            to_wa_id=wa_id,
                            body_text=(
                                f"💳 *Order #{checkout_res.order_id} initiated!*\n\n"
                                f"Tap below to complete your payment on Swiggy within 5 minutes:"
                            ),
                            button_text="Pay on Swiggy",
                            url=checkout_res.bridge_url,
                        )
                    )
                elif checkout_res.success and checkout_res.receipt_text:
                    # Cash/COD and split orders have no payment link to tap.
                    _spawn(
                        wa_client.send_text_message(
                            to_wa_id=wa_id,
                            text=checkout_res.receipt_text,
                        )
                    )
                elif not checkout_res.success and checkout_res.error_message:
                    if checkout_res.cta_button and checkout_res.cta_button.get("parameters"):
                        btn_param = checkout_res.cta_button["parameters"]
                        _spawn(
                            wa_client.send_quick_reply_buttons(
                                to_wa_id=wa_id,
                                body_text=f"⚠️ *Payment Notice:*\n\n{checkout_res.error_message}",
                                buttons=[(btn_param["button_id"], btn_param["title"])],
                            )
                        )
                    else:
                        _spawn(
                            wa_client.send_text_message(
                                to_wa_id=wa_id,
                                text=f"⚠️ *Payment Notice:*\n\n{checkout_res.error_message}",
                            )
                        )

                return {
                    "status": "checkout_executed" if checkout_res.success else "checkout_failed",
                    "action": button_id,
                    "approval_id": target_arg,
                    "order_id": checkout_res.order_id,
                    "bridge_url": checkout_res.bridge_url,
                    "cta_button": checkout_res.cta_button,
                    "receipt_text": checkout_res.receipt_text,
                    "error_message": checkout_res.error_message,
                    "message": "Payment lock authorized and checkout executed.",
                }

        text = (
            "I couldn't start the payment just now. Nothing was charged. "
            "Please try again."
        )
        await wa_client.send_text_message(to_wa_id=wa_id, text=text)
        return {
            "status": "checkout_unavailable",
            "action": button_id,
            "approval_id": target_arg,
            "message": text,
        }

    # 3. Delivery Address Switch / Delete confirmation tap
    if prefix == "addr":
        from backend.agent.address_actions import apply_delete, apply_switch
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.token_vault import resolve_user_client

        wa_client = wa_client or WhatsAppClient()
        action, _, address_id = (target_arg or "").partition(":")

        if action == "keep" or not address_id:
            text = "Okay, nothing changed."
            _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=text))
            return {"status": "address_kept", "action": button_id, "message": text}

        if not pool:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        async with pool.acquire() as conn:
            user_id, active = await _load_button_context(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client, wa_id, button_id, BUTTON_UNKNOWN_USER, "unknown_user"
                )

            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                _spawn(
                    wa_client.send_text_message(to_wa_id=wa_id, text=AUTH_EXPIRED)
                )
                return _auth_result(button_id)

            if action == "set":
                reply = await apply_switch(client, conn, user_id, address_id)
            else:
                reply = await apply_delete(client, active, address_id)

        _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {
            "status": "address_updated",
            "action": button_id,
            "message": reply.text,
        }

    # 3b. Change a vague staple: show real replacements for the same item.
    if prefix == "item":
        from backend.agent.basket_actions import BasketReply
        from backend.agent.candidate_search import search_catalog
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.token_vault import resolve_user_client

        wa_client = wa_client or WhatsAppClient()
        action, _, spin_id = (target_arg or "").partition(":")
        if action != "change" or not spin_id:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_STALE, "invalid_button"
            )
        if not pool:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        async with pool.acquire() as conn:
            user_id = await _fetch_user_id(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client, wa_id, button_id, BUTTON_UNKNOWN_USER, "unknown_user"
                )
            active = await _fetch_active_address(conn, user_id)
            client = swiggy_client or await resolve_user_client(user_id)
            if client is None:
                _spawn(
                    wa_client.send_text_message(to_wa_id=wa_id, text=AUTH_EXPIRED)
                )
                return _auth_result(button_id)

            try:
                cart = await asyncio.to_thread(client.get_cart, active)
                current = next(
                    (item for item in cart.items if item.spinId == spin_id), None
                )
                if current is None:
                    reply = BasketReply("That item isn't in your basket any more.")
                else:
                    candidates = await asyncio.to_thread(
                        search_catalog,
                        query=current.itemName,
                        address_id=active,
                        swiggy_client=client,
                    )
                    options = [
                        cand for cand in candidates if cand.spin_id != spin_id
                    ][:3]
                    if not options:
                        reply = BasketReply(
                            "I couldn't find another size or brand for that item right now."
                        )
                    else:
                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=wa_id,
                            body_text=f"Pick a replacement for *{current.itemName}*:",
                            buttons=[
                                (
                                    f"cart:swap:{spin_id}:{opt.spin_id}:{opt.sku_id}",
                                    opt.display_name[:20],
                                )
                                for opt in options
                            ],
                        )
                        return {
                            "status": "item_choices",
                            "action": button_id,
                            "candidates": len(options),
                        }
            except (
                ValueError,
                KeyError,
                RuntimeError,
                OSError,
                httpx.HTTPError,
            ) as exc:
                logger.warning("Item change failed: %s", exc)
                reply = BasketReply(
                    "I couldn't load alternatives just now. Please try again."
                )

        _spawn(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {
            "status": "item_change",
            "action": button_id,
            "message": reply.text,
        }

    # 4. Budget Cap Raise Action (ADR 0006)
    if prefix == "budget" and target_arg and target_arg.startswith("raise"):
        from backend.agent.candidate_evaluator import format_paise_to_rupees
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.config import settings

        wa_client = wa_client or WhatsAppClient()
        parts = target_arg.split(":")
        if len(parts) != 3:
            return await _reply_and_return(
                wa_client,
                wa_id,
                button_id,
                "That limit change did not go through. Nothing was changed.",
                "invalid_button",
            )
        approval_id, limit_text = parts[1], parts[2]

        new_limit = int(limit_text) if limit_text.isdigit() else None
        if new_limit is None or not (
            settings.DEFAULT_BUDGET_CAP_PAISE
            < new_limit
            <= settings.MAX_BUDGET_CAP_PAISE
        ):
            return await _reply_and_return(
                wa_client,
                wa_id,
                button_id,
                "That limit change did not go through. Nothing was changed.",
                "invalid_button",
            )
        if not pool:
            return await _reply_and_return(
                wa_client, wa_id, button_id, BUTTON_UNAVAILABLE
            )

        from backend.agent.customer_advocate import raise_session_budget_cap

        pay_button: tuple[str, str] | None = None
        async with pool.acquire() as conn:
            user_id = await _fetch_user_id(conn, wa_id)
            if not user_id:
                return await _reply_and_return(
                    wa_client,
                    wa_id,
                    button_id,
                    BUTTON_UNKNOWN_USER,
                    "unknown_user",
                )
            await raise_session_budget_cap(conn, str(user_id), new_limit)
            if approval_id:
                try:
                    approval_uuid = uuid.UUID(approval_id)
                except ValueError:
                    approval_uuid = None
                if approval_uuid:
                    row = await conn.fetchrow(
                        """
                        SELECT to_pay_paise FROM grocer.approvals
                        WHERE id = $1 AND user_id = $2 AND status = 'shown' AND expires_at > now();
                        """,
                        approval_uuid,
                        user_id,
                    )
                    if row:
                        pay_button = (
                            f"pay:{approval_id}",
                            f"Pay {format_paise_to_rupees(int(row['to_pay_paise']))}",
                        )

        if pay_button:
            _spawn(
                wa_client.send_quick_reply_buttons(
                    to_wa_id=wa_id,
                    body_text=(
                        f"🛡️ *Launch Safety Cap Raised!*\nYour limit is now "
                        f"{format_paise_to_rupees(new_limit)}. Tap below to pay."
                    ),
                    buttons=[pay_button],
                )
            )
        else:
            _spawn(
                wa_client.send_text_message(
                    to_wa_id=wa_id,
                    text=(
                        f"🛡️ *Launch Safety Cap Raised!*\nYour spending limit is now "
                        f"{format_paise_to_rupees(new_limit)}. Build your receipt again to pay."
                    ),
                )
            )

        return {
            "status": "button_dispatched",
            "action": button_id,
            "approval_id": approval_id,
            "new_limit_paise": new_limit,
            "message": f"Spending limit raised to {format_paise_to_rupees(new_limit)}. You can now proceed to pay.",
        }

    # Default fallback for a button id this build no longer knows.
    from backend.channels.whatsapp_client import WhatsAppClient

    wa_client = wa_client or WhatsAppClient()
    return await _reply_and_return(
        wa_client, wa_id, button_id, BUTTON_STALE, "unknown_action"
    )
