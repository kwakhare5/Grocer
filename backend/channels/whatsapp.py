"""Grocer v1.0 — WhatsApp Cloud API Webhook Route & Ingestion Shield."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from backend.channels.button_router import dispatch_button_action
from backend.channels.whatsapp_crypto import verify_signature, verify_webhook_challenge
from backend.channels.whatsapp_parser import parse_webhook_payload
from backend.config import settings
from backend.database import get_db_pool

logger = logging.getLogger("grocer.channels.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """Meta webhook verification endpoint."""
    mode = request.query_params.get("hub.mode")
    verify_token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    valid_challenge = verify_webhook_challenge(
        mode=mode,
        verify_token=verify_token,
        challenge=challenge,
        expected_token=settings.WHATSAPP_VERIFY_TOKEN,
    )

    if valid_challenge is not None:
        return Response(content=valid_challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    swiggy_client: Any | None = None,
) -> dict[str, Any]:
    """Inbound WhatsApp message ingestion shield (<25ms target).

    1. Validates HMAC-SHA256 signature against WHATSAPP_APP_SECRET.
    2. Drops delivery receipts (statuses) immediately.
    3. Drops stale messages (>15 min old).
    4. Enforces PostgreSQL deduplication with ON CONFLICT DO NOTHING.
    5. Acquires per-user transaction advisory lock.
    6. Dispatches interactive button taps directly to fast 50ms Python router.
    7. Supports multi-message batches without early loop truncation.
    """
    body_bytes = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    # 1. Cryptographic HMAC validation
    if not verify_signature(body_bytes, signature_header, settings.WHATSAPP_APP_SECRET):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from exc

    # 2. Parse payload
    kind, messages = parse_webhook_payload(payload)

    # Fast ACK delivery receipts
    if kind == "status":
        return {"status": "ignored_status"}

    if not messages:
        return {"status": "empty"}

    pool = await get_db_pool()
    results: list[dict[str, Any]] = []

    for msg in messages:
        # 3. Stale message latch (discard messages older than 15 minutes)
        if msg.is_stale:
            logger.warning("Dropping stale WhatsApp message: %s", msg.wa_message_id)
            results.append(
                {"status": "stale_dropped", "wa_message_id": msg.wa_message_id}
            )
            continue

        async with (
            pool.acquire() as conn,
            conn.transaction(),
        ):
            # 4. User profile lookup / auto-registration
            user_id = await conn.fetchval(
                """
                INSERT INTO grocer.users (wa_id)
                VALUES ($1)
                ON CONFLICT (wa_id) DO UPDATE SET updated_at = now()
                RETURNING id;
                """,
                msg.sender_wa_id,
            )

            # 5. PostgreSQL Message Deduplication (Atomic ON CONFLICT DO NOTHING)
            # Safe recording FIRST: message is never lost from database
            raw_payload_json = json.dumps(msg.raw_payload) if msg.raw_payload else None
            inbound_id = await conn.fetchval(
                """
                INSERT INTO grocer.inbound_messages (
                    wa_message_id,
                    user_id,
                    message_type,
                    raw_payload,
                    status
                )
                VALUES ($1, $2, $3, $4, 'received')
                ON CONFLICT (wa_message_id) DO NOTHING
                RETURNING id;
                """,
                msg.wa_message_id,
                user_id,
                msg.message_type,
                raw_payload_json,
            )

            if not inbound_id:
                logger.info("Duplicate WhatsApp message dropped: %s", msg.wa_message_id)
                results.append(
                    {"status": "duplicate_dropped", "wa_message_id": msg.wa_message_id}
                )
                continue

            # 6. Per-User Advisory Lock (Fast concurrency serialization)
            lock_acquired = await conn.fetchval(
                "SELECT pg_try_advisory_xact_lock(hashtext($1));",
                str(user_id),
            )
            if not lock_acquired:
                logger.warning(
                    "User %s locked by concurrent action; queuing message", user_id
                )
                await conn.execute(
                    "UPDATE grocer.inbound_messages SET status = 'concurrency_dropped' WHERE id = $1;",
                    inbound_id,
                )
                results.append(
                    {
                        "status": "concurrency_dropped",
                        "wa_message_id": msg.wa_message_id,
                    }
                )
                continue

            # 7. Fast 50ms Button Dispatcher for interactive replies
            if msg.button_id:
                action_res = await dispatch_button_action(
                    msg.button_id, msg.sender_wa_id, pool
                )
                results.append(action_res)
                continue

            # 8. Inbound Command Dispatcher (DPDP, admin commands)
            if msg.text:
                from backend.channels.command_router import dispatch_text_command
                from backend.channels.whatsapp_client import WhatsAppClient

                wa_client = WhatsAppClient()
                cmd_res = await dispatch_text_command(msg.text, str(user_id), conn)
                if cmd_res is not None:
                    if cmd_res.get("message"):
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=cmd_res["message"],
                        )
                    results.append(cmd_res)
                    continue

                # 9. Conversational Grocery Concierge Pipeline
                from backend.integrations.commerce.token_vault import get_user_token

                user_token = await get_user_token(user_id)
                if not user_token:
                    # User is not connected to Swiggy yet
                    login_url = f"https://grocerr.vercel.app?phone={msg.sender_wa_id}"
                    await wa_client.send_cta_url_button(
                        to_wa_id=msg.sender_wa_id,
                        body_text=(
                            "👋 *Welcome to Grocer!*\n\n"
                            "To order from Swiggy Instamart dark stores in 10-15 minutes, "
                            "please connect your Swiggy account first:"
                        ),
                        button_text="Connect Swiggy",
                        url=login_url,
                    )
                    results.append({"status": "auth_required", "wa_id": msg.sender_wa_id})
                    continue

                from backend.agent.approval import create_checkout_approval
                from backend.agent.candidate_evaluator import (
                    evaluate_customer_intent,
                    format_paise_to_rupees,
                )
                from backend.agent.candidate_search import search_catalog
                from backend.agent.composite_cart import (
                    CompositeCartManager,
                    TargetCartItem,
                )
                from backend.integrations.commerce.swiggy_client import (
                    SwiggyAuthExpiredError,
                    SwiggyClient,
                )

                client = swiggy_client or SwiggyClient(auth_token=user_token)

                try:
                    # Resolve active address
                    session_row = await conn.fetchrow(
                        "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
                        user_id,
                    )
                    active_addr_id = session_row["active_address_id"] if session_row else None
                    if not active_addr_id:
                        try:
                            addrs = client.get_addresses()
                            if addrs.addresses:
                                active_addr_id = addrs.addresses[0].id
                                await conn.execute(
                                    """
                                    INSERT INTO grocer.sessions (user_id, active_address_id, last_active_at)
                                    VALUES ($1, $2, now())
                                    ON CONFLICT (user_id) DO UPDATE SET active_address_id = $2, last_active_at = now();
                                    """,
                                    user_id,
                                    active_addr_id,
                                )
                        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as addr_err:
                            logger.warning("Could not fetch user addresses: %s", addr_err)

                    candidates = search_catalog(
                        msg.text,
                        swiggy_client=client,
                        address_id=active_addr_id,
                    )
                    evaluation = evaluate_customer_intent(msg.text, candidates)

                    if evaluation.intent_type == "conversational_qa":
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=evaluation.conversational_response
                            or "How can I help with your groceries today?",
                        )
                        results.append(
                            {"status": "conversational_replied", "wa_id": msg.sender_wa_id}
                        )
                        continue

                    if evaluation.selected_candidate:
                        cand = evaluation.selected_candidate
                        items_to_add = [
                            TargetCartItem(
                                spin_id=cand.spin_id,
                                quantity=1,
                                item_name=cand.display_name,
                                price_paise=cand.offer_price_paise,
                            )
                        ]
                        cart_mgr = CompositeCartManager(client)
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
                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=msg.sender_wa_id,
                            body_text=cart_res.receipt_text,
                            buttons=[
                                (f"pay:{approval.id}", f"Pay {to_pay_formatted}"),
                                ("cart:clear", "Clear Basket"),
                            ],
                        )
                        results.append(
                            {
                                "status": "cart_updated",
                                "approval_id": approval.id,
                                "to_pay_paise": approval.to_pay_paise,
                            }
                        )
                        continue
                    else:
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=f"Sorry, I couldn't find items matching '{msg.text}' at your local dark store. Could you try a different brand or item name?",
                        )
                        results.append({"status": "no_match", "query": msg.text})
                        continue
                except SwiggyAuthExpiredError:
                    # Token expired (401) — Park shopping list and prompt reconnection (ADR 0010)
                    await conn.execute(
                        "UPDATE grocer.inbound_messages SET status = 'parked' WHERE id = $1;",
                        inbound_id,
                    )
                    login_url = f"https://grocerr.vercel.app?phone={msg.sender_wa_id}"
                    await wa_client.send_cta_url_button(
                        to_wa_id=msg.sender_wa_id,
                        body_text=(
                            "⚠️ *Your Swiggy login needs a 5-day security refresh.*\n\n"
                            "Tap below to reconnect your account. Your grocery list has been saved and will resume automatically:"
                        ),
                        button_text="Reconnect Swiggy",
                        url=login_url,
                    )
                    results.append({"status": "auth_expired", "wa_id": msg.sender_wa_id})
                    continue

            results.append({"status": "processed", "wa_message_id": msg.wa_message_id})

    # Single-message response preservation for caller convenience
    if len(results) == 1:
        return results[0]

    return {"status": "ok", "processed": len(results), "results": results}
