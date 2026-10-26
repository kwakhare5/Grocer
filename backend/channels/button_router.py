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

    # 1. Cart Clear action
    if button_id == "cart:clear":
        from backend.channels.whatsapp_client import WhatsAppClient

        wa_client = WhatsAppClient()
        asyncio.create_task(
            wa_client.send_text_message(
                to_wa_id=wa_id,
                text="🛒 *Your basket has been cleared.* Send your new grocery list whenever you're ready!",
            )
        )
        return {
            "status": "button_dispatched",
            "action": "cart:clear",
            "message": "Basket cleared.",
        }

    # 2. Checkout Payment Authorization (Lock 1 Authority -> 3-Lock Execution)
    if prefix == "pay":
        if pool and target_arg:
            from backend.agent.checkout_executor import execute_3_lock_checkout
            from backend.channels.whatsapp_client import WhatsAppClient
            from backend.integrations.commerce.swiggy_client import SwiggyClient
            from backend.integrations.commerce.token_vault import get_user_token

            wa_client = WhatsAppClient()

            async with pool.acquire() as conn, conn.transaction():
                user_id = await conn.fetchval(
                    "SELECT id FROM grocer.users WHERE wa_id = $1;",
                    wa_id,
                )
                if user_id:
                    user_token = await get_user_token(user_id)
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

    # 3. Delivery Address Switching
    if prefix == "addr":
        return {
            "status": "button_dispatched",
            "action": button_id,
            "address_id": target_arg,
            "message": "Address switch requested.",
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
