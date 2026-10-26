"""Grocer v1.0 — Fast 50ms Interactive Button Dispatcher (Zero LLM Lag)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg

logger = logging.getLogger("grocer.button_router")


async def dispatch_button_action(
    button_id: str,
    wa_id: str,
    pool: asyncpg.Pool | None = None,
    swiggy_client: Any | None = None,
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
            apply_add_quantity,
            apply_clear,
            apply_remove,
            apply_set_quantity,
        )
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = WhatsAppClient()

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

            try:
                if button_id == "cart:clear":
                    reply = await apply_clear(client, active)
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
                    else:
                        reply = BasketReply("Nothing changed.")
            except (ValueError, KeyError, RuntimeError, OSError) as exc:
                logger.warning("Basket button action failed: %s", exc)
                reply = BasketReply("That change didn't go through. Nothing was changed.")

        asyncio.create_task(wa_client.send_text_message(to_wa_id=wa_id, text=reply.text))
        return {"status": "basket_updated", "action": button_id, "message": reply.text}

    # 2. Reorder confirmation taps
    if prefix == "reorder":
        from backend.agent.order_actions import OrderReply, apply_reorder
        from backend.channels.whatsapp_client import WhatsAppClient
        from backend.integrations.commerce.swiggy_client import SwiggyClient
        from backend.integrations.commerce.token_vault import resolve_user_token

        wa_client = WhatsAppClient()

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

            wa_client = WhatsAppClient()

            async with pool.acquire() as conn, conn.transaction():
                user_id = await conn.fetchval(
                    "SELECT id FROM grocer.users WHERE wa_id = $1;",
                    wa_id,
                )
                if user_id:
                    user_token = await resolve_user_token(user_id)
                    if not user_token and not swiggy_client:
                        # Never spend the approval on a checkout we know will 401.
                        await conn.execute(
                            "UPDATE grocer.approvals SET status = 'expired' WHERE id = $1::uuid;",
                            target_arg,
                        )
                        return {
                            "status": "auth_required",
                            "action": button_id,
                            "approval_id": target_arg,
                            "message": "Swiggy login expired. Please reconnect your account.",
                        }
                    client = swiggy_client or SwiggyClient(auth_token=user_token)

                    checkout_res = await execute_3_lock_checkout(
                        conn=conn,
                        swiggy_client=client,
                        user_id=str(user_id),
                        approval_id=target_arg,
                        message_type="button_reply",
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

        wa_client = WhatsAppClient()
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

    # 4. Budget Cap Raise Action (ADR 0006)
    if prefix == "budget" and target_arg and target_arg.startswith("raise"):
        parts = target_arg.split(":")
        new_limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 200000
        if pool:
            from backend.agent.candidate_evaluator import format_paise_to_rupees
            from backend.agent.customer_advocate import raise_session_budget_cap
            from backend.channels.whatsapp_client import WhatsAppClient

            async with pool.acquire() as conn:
                user_id = await conn.fetchval(
                    "SELECT id FROM grocer.users WHERE wa_id = $1;",
                    wa_id,
                )
                if user_id:
                    await raise_session_budget_cap(conn, str(user_id), new_limit)

            wa_client = WhatsAppClient()
            asyncio.create_task(
                wa_client.send_text_message(
                    to_wa_id=wa_id,
                    text=f"🛡️ *Launch Safety Cap Raised!*\nYour spending limit is now {format_paise_to_rupees(new_limit)}. Tap your payment button to complete your order.",
                )
            )

        from backend.agent.candidate_evaluator import format_paise_to_rupees

        return {
            "status": "button_dispatched",
            "action": button_id,
            "new_limit_paise": new_limit,
            "message": f"Spending limit raised to {format_paise_to_rupees(new_limit)}. You can now proceed to pay.",
        }

    # Default fallback for recognized button action
    return {
        "status": "button_dispatched",
        "action": button_id,
        "message": "Action processed.",
    }
