"""Grocer v1.0 — Fast 50ms Interactive Button Dispatcher (Zero LLM Lag)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import asyncpg
import httpx

from backend.config import settings

logger = logging.getLogger("grocer.button_router")


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
    logger.info("Dispatching fast button action: %s for user: %s", button_id, wa_id)

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
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = wa_client or WhatsAppClient()

        if button_id == "cart:keep":
            text = "Okay, your basket is unchanged."
            asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=text))
            return {"status": "basket_kept", "action": button_id, "message": text}

        if not pool:
            return {
                "status": "button_ignored",
                "action": button_id,
                "message": "Basket action needs a database connection.",
            }

        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM grocer.users WHERE wa_id = $1;", wa_id
            )
            if not user_id:
                return {"status": "unknown_user", "action": button_id}

            active = await conn.fetchval(
                "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
                user_id,
            )
            client = swiggy_client
            if client is None:
                token = await resolve_user_token(user_id)
                if not token:
                    reply = BasketReply(
                        "Your Swiggy login has expired. Please reconnect your account."
                    )
                    asyncio.create_task(
                        wa_client.send_text_message(to_wa_id=wa_id, text=reply.text)
                    )
                    return {"status": "auth_required", "action": button_id}
                client = SwiggyClient(auth_token=token)

            special_result: dict[str, Any] | None = None
            try:
                if button_id == "cart:clear":
                    reply = await apply_clear(client, active)
                elif button_id.startswith("cart:fresh:"):
                    from backend.agent.approval import create_checkout_approval
                    from backend.agent.basket_actions import apply_keep_only_new
                    from backend.agent.candidate_evaluator import format_paise_to_rupees
                    from backend.agent.composite_cart import format_cart_receipt

                    cart, err = await apply_keep_only_new(client, active, button_id)
                    if err or not cart.items:
                        reply = BasketReply(err or "Your basket is empty.")
                    else:
                        approval = await create_checkout_approval(
                            conn=conn,
                            user_id=str(user_id),
                            cart=cart,
                            address_id=active or "default",
                        )
                        body = format_cart_receipt(cart)
                        cap_paise = await conn.fetchval(
                            "SELECT budget_cap_paise FROM grocer.sessions WHERE user_id = $1;",
                            user_id,
                        ) or settings.DEFAULT_BUDGET_CAP_PAISE
                        if approval.to_pay_paise > int(cap_paise):
                            body += (
                                f"\n\n⚠️ This is above your "
                                f"{format_paise_to_rupees(int(cap_paise))} safety cap. "
                                "You'll be asked to raise it when you tap Pay."
                            )
                        pay_label = format_paise_to_rupees(approval.to_pay_paise)
                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=wa_id,
                            body_text=body,
                            buttons=[
                                (f"pay:{approval.id}", f"Pay {pay_label}"),
                                ("cart:clear", "Clear basket"),
                            ],
                        )
                        special_result = {
                            "status": "cart_fresh",
                            "action": button_id,
                            "approval_id": str(approval.id),
                            "to_pay_paise": approval.to_pay_paise,
                        }
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
        asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {"status": "basket_updated", "action": button_id, "message": reply.text}

    # 2. Reorder confirmation taps
    if prefix == "reorder":
        from backend.agent.order_actions import OrderReply, apply_reorder
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = wa_client or WhatsAppClient()

        if not pool or not target_arg:
            return {
                "status": "button_ignored",
                "action": button_id,
                "message": "Reorder needs a database connection.",
            }

        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM grocer.users WHERE wa_id = $1;", wa_id
            )
            if not user_id:
                return {"status": "unknown_user", "action": button_id}

            active = await conn.fetchval(
                "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
                user_id,
            )
            client = swiggy_client
            if client is None:
                token = await resolve_user_token(user_id)
                if not token:
                    reply = OrderReply(
                        "Your Swiggy login has expired. Please reconnect your account."
                    )
                    asyncio.create_task(
                        wa_client.send_text_message(to_wa_id=wa_id, text=reply.text)
                    )
                    return {"status": "auth_required", "action": button_id}
                client = SwiggyClient(auth_token=token)

            try:
                reply = await apply_reorder(client, active, target_arg)
            except (ValueError, KeyError, RuntimeError, OSError) as exc:
                logger.warning("Reorder button action failed: %s", exc)
                reply = OrderReply("That reorder didn't go through. Nothing was changed.")

        asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {"status": "reorder_applied", "action": button_id, "message": reply.text}

    # 3. Checkout Payment Authorization (Lock 1 Authority -> 3-Lock Execution)
    if prefix == "pay":
        if pool and target_arg:
            from backend.agent.checkout_executor import execute_3_lock_checkout
            from backend.channels.whatsapp_client import WhatsAppClient
            from backend.integrations.commerce.swiggy_client import SwiggyClient
            from backend.integrations.commerce.token_vault import resolve_user_token

            wa_client = wa_client or WhatsAppClient()

            async with pool.acquire() as conn:
                user_id = await conn.fetchval(
                    "SELECT id FROM grocer.users WHERE wa_id = $1;",
                    wa_id,
                )

            if user_id:
                user_token = await resolve_user_token(user_id)
                if not user_token and not swiggy_client:
                    # The approval is untouched: nothing was claimed, so the same
                    # button still works once the customer reconnects.
                    return {
                        "status": "auth_required",
                        "action": button_id,
                        "approval_id": target_arg,
                        "message": "Swiggy login expired. Please reconnect your account.",
                    }
                client = swiggy_client or SwiggyClient(auth_token=user_token)

                checkout_res = await execute_3_lock_checkout(
                    pool=pool,
                    swiggy_client=client,
                    user_id=str(user_id),
                    approval_id=target_arg,
                    message_type=message_type,
                    button_id=button_id,
                )

                if checkout_res.success and checkout_res.bridge_url:
                    asyncio.create_task(
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
                    asyncio.create_task(
                        wa_client.send_text_message(
                            to_wa_id=wa_id,
                            text=checkout_res.receipt_text,
                        )
                    )
                elif not checkout_res.success and checkout_res.error_message:
                    if checkout_res.cta_button and checkout_res.cta_button.get("parameters"):
                        btn_param = checkout_res.cta_button["parameters"]
                        asyncio.create_task(
                            wa_client.send_quick_reply_buttons(
                                to_wa_id=wa_id,
                                body_text=f"⚠️ *Payment Notice:*\n\n{checkout_res.error_message}",
                                buttons=[(btn_param["button_id"], btn_param["title"])],
                            )
                        )
                    else:
                        asyncio.create_task(
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

        return {
            "status": "button_dispatched",
            "action": button_id,
            "approval_id": target_arg,
            "message": "Payment lock authorized.",
        }

    # 3. Delivery Address Switch / Delete confirmation tap
    if prefix == "addr":
        from backend.agent.address_actions import (
            AddressReply,
            apply_delete,
            apply_switch,
        )
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = wa_client or WhatsAppClient()
        action, _, address_id = (target_arg or "").partition(":")

        if action == "keep" or not address_id:
            text = "Okay, nothing changed."
            asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=text))
            return {"status": "address_kept", "action": button_id, "message": text}

        if not pool:
            return {
                "status": "button_ignored",
                "action": button_id,
                "message": "Address action needs a database connection.",
            }

        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM grocer.users WHERE wa_id = $1;", wa_id
            )
            if not user_id:
                return {"status": "unknown_user", "action": button_id}

            active = await conn.fetchval(
                "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
                user_id,
            )
            client = swiggy_client
            if client is None:
                token = await resolve_user_token(user_id)
                if not token:
                    reply = AddressReply(
                        "Your Swiggy login has expired. Please reconnect your account."
                    )
                    asyncio.create_task(
                        wa_client.send_text_message(to_wa_id=wa_id, text=reply.text)
                    )
                    return {"status": "auth_required", "action": button_id}
                client = SwiggyClient(auth_token=token)

            if action == "set":
                reply = await apply_switch(client, conn, user_id, address_id)
            else:
                reply = await apply_delete(client, active, address_id)

        asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
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
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = wa_client or WhatsAppClient()
        action, _, spin_id = (target_arg or "").partition(":")
        if action != "change" or not spin_id:
            return {"status": "button_ignored", "action": button_id}
        if not pool:
            return {
                "status": "button_ignored",
                "action": button_id,
                "message": "Changing an item needs a database connection.",
            }

        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM grocer.users WHERE wa_id = $1;", wa_id
            )
            if not user_id:
                return {"status": "unknown_user", "action": button_id}
            active = await conn.fetchval(
                "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
                user_id,
            )
            client = swiggy_client
            if client is None:
                token = await resolve_user_token(user_id)
                if not token:
                    asyncio.create_task(
                        wa_client.send_text_message(
                            to_wa_id=wa_id,
                            text="Your Swiggy login has expired. Please reconnect your account.",
                        )
                    )
                    return {"status": "auth_required", "action": button_id}
                client = SwiggyClient(auth_token=token)

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

        asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {
            "status": "item_change",
            "action": button_id,
            "message": reply.text,
        }

    # 4. Budget Cap Raise Action (ADR 0006)
    if prefix == "budget" and target_arg and target_arg.startswith("raise"):
        from backend.agent.candidate_evaluator import format_paise_to_rupees
        from backend.agent.checkout_executor import DEFAULT_LAUNCH_CAP_PAISE

        # Current format: raise:<approval_id>:<paise>. Legacy: raise:<paise>.
        parts = target_arg.split(":")
        if len(parts) == 3:
            approval_id, limit_text = parts[1], parts[2]
        elif len(parts) == 2:
            approval_id, limit_text = None, parts[1]
        else:
            approval_id, limit_text = None, ""

        new_limit = int(limit_text) if limit_text.isdigit() else None
        if new_limit is None or not (DEFAULT_LAUNCH_CAP_PAISE < new_limit <= 10000000):
            return {
                "status": "button_ignored",
                "action": button_id,
                "message": "That limit change did not go through. Nothing was changed.",
            }

        if pool:
            from backend.agent.customer_advocate import raise_session_budget_cap
            from backend.channels.whatsapp_client import WhatsAppClient

            pay_button: tuple[str, str] | None = None
            async with pool.acquire() as conn:
                user_id = await conn.fetchval(
                    "SELECT id FROM grocer.users WHERE wa_id = $1;",
                    wa_id,
                )
                if user_id:
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

            wa_client = wa_client or WhatsAppClient()
            if pay_button:
                asyncio.create_task(
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
                asyncio.create_task(
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

    # Default fallback for recognized button action
    return {
        "status": "button_dispatched",
        "action": button_id,
        "message": "Action processed.",
    }
