"""Grocer v1.0 — WhatsApp Cloud API Webhook Route & Ingestion Shield."""

from __future__ import annotations

import asyncio
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
    7. Routes location pins through onboarding and text through the grocery pipeline.
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

            # 8. Deterministic admin/privacy commands (DPDP) take priority over commerce
            if msg.text:
                from backend.channels.command_router import dispatch_text_command

                cmd_res = await dispatch_text_command(msg.text, str(user_id), conn)
                if cmd_res is not None:
                    from backend.channels.whatsapp_client import WhatsAppClient

                    wa_client = WhatsAppClient()
                    if cmd_res.get("message"):
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=cmd_res["message"],
                        )
                    results.append(cmd_res)
                    continue

            # 9. Commerce + onboarding: requires a live Swiggy token
            if msg.message_type == "location" or msg.text:
                from backend.channels.whatsapp_client import WhatsAppClient
                from backend.integrations.commerce.swiggy_client import (
                    SwiggyAuthExpiredError,
                    SwiggyClient,
                )
                from backend.integrations.commerce.token_vault import (
                    refresh_user_token,
                    resolve_user_token,
                )

                wa_client = WhatsAppClient()

                user_token = await resolve_user_token(user_id)
                if not user_token:
                    login_url = f"https://grocerr.vercel.app?phone={msg.sender_wa_id}"
                    await wa_client.send_cta_url_button(
                        to_wa_id=msg.sender_wa_id,
                        body_text=(
                            "👋 *Welcome to Grocer!*\n\n"
                            "Connect your Swiggy account to shop Instamart in 10-15 minutes:"
                        ),
                        button_text="Connect Swiggy",
                        url=login_url,
                    )
                    results.append({"status": "auth_required", "wa_id": msg.sender_wa_id})
                    continue

                client = swiggy_client or SwiggyClient(auth_token=user_token)

                # 9a. WhatsApp location pin -> geocode + persist delivery coords
                if (
                    msg.message_type == "location"
                    and msg.latitude is not None
                    and msg.longitude is not None
                ):
                    from backend.agent.address_lifecycle import (
                        AddressOnboardingFlow,
                        OnboardingStep,
                    )

                    try:
                        flow = AddressOnboardingFlow(client)
                        turn = flow.start_from_location(msg.latitude, msg.longitude)
                    except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                        logger.warning("Onboarding geocode failed: %s", exc)
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text="Sorry, I couldn't resolve that location. Please share your pin again.",
                        )
                        results.append(
                            {"status": "onboarding_location_failed", "wa_id": msg.sender_wa_id}
                        )
                        continue

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
                    results.append(
                        {"status": "onboarding_location_captured", "wa_id": msg.sender_wa_id}
                    )
                    continue

                # 9b. Onboarding follow-up text (flat -> name -> city+PIN)
                from backend.agent.address_lifecycle import (
                    AddressOnboardingFlow,
                    OnboardingStep,
                )

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
                        results.append(
                            {"status": "onboarding_failed", "wa_id": msg.sender_wa_id}
                        )
                        continue

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
                    results.append(
                        {
                            "status": "onboarding_advanced",
                            "wa_id": msg.sender_wa_id,
                            "step": turn.next_step.value,
                        }
                    )
                    continue

                # 9c. Conversational grocery pipeline (refresh-on-401 retry)
                from backend.agent.approval import create_checkout_approval
                from backend.agent.candidate_evaluator import (
                    ExtractedGroceryItem,
                    IntentType,
                    evaluate_customer_intent,
                    format_paise_to_rupees,
                    orchestrate_conversational_turn,
                )
                from backend.agent.candidate_search import search_catalog
                from backend.agent.composite_cart import (
                    CompositeCartManager,
                    TargetCartItem,
                )

                async def run_turn(
                    turn_client: SwiggyClient,
                    msg: Any,
                    user_id: Any,
                    conn: Any,
                    wa_client: Any,
                ) -> dict[str, Any]:
                    # Resolve active address and past dialogue history
                    session_row = await conn.fetchrow(
                        "SELECT active_address_id, history FROM grocer.sessions WHERE user_id = $1;",
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

                    async def remember(reply_text: str) -> None:
                        session_history.append({"role": "user", "text": msg.text})
                        session_history.append({"role": "assistant", "text": reply_text})
                        await conn.execute(
                            """
                            INSERT INTO grocer.sessions (user_id, history, last_active_at)
                            VALUES ($1, $2::jsonb, now())
                            ON CONFLICT (user_id) DO UPDATE SET history = $2::jsonb, last_active_at = now();
                            """,
                            user_id,
                            json.dumps(session_history[-12:]),
                        )

                    address_count = 1
                    if not active_addr_id:
                        try:
                            addrs = turn_client.get_addresses()
                            address_count = len(addrs.addresses)
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
                            else:
                                address_count = 0
                        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as addr_err:
                            logger.warning("Could not fetch user addresses: %s", addr_err)

                    # 1. Capability routing (ADR 0012). Read capabilities are answered
                    # here and can never write. Basket requests continue below.
                    from backend.agent.read_actions import (
                        NOT_READY_REPLY,
                        answer_read_capability,
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
                        reply_text = await answer_read_capability(
                            decision, turn_client, active_addr_id
                        )
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id, text=reply_text
                        )
                        session_history.append({"role": "user", "text": msg.text})
                        session_history.append({"role": "assistant", "text": reply_text})
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
                            "status": "capability_answered",
                            "capability": decision.capability.value,
                            "wa_id": msg.sender_wa_id,
                        }

                    if decision.capability is Capability.SWITCH_ADDRESS:
                        from backend.agent.address_actions import handle_switch_request

                        addr_reply = await handle_switch_request(
                            decision, turn_client, conn, user_id, active_addr_id
                        )
                        if addr_reply.buttons:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=addr_reply.text,
                                buttons=addr_reply.buttons,
                            )
                        else:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=addr_reply.text
                            )
                        await remember(addr_reply.text)
                        return {
                            "status": "address_switch_requested",
                            "wa_id": msg.sender_wa_id,
                        }

                    if decision.capability is Capability.DELETE_ADDRESS:
                        from backend.agent.address_actions import handle_delete_request

                        addr_reply = await handle_delete_request(
                            decision, turn_client, active_addr_id
                        )
                        if addr_reply.buttons:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=addr_reply.text,
                                buttons=addr_reply.buttons,
                            )
                        else:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=addr_reply.text
                            )
                        await remember(addr_reply.text)
                        return {
                            "status": "address_delete_requested",
                            "wa_id": msg.sender_wa_id,
                        }

                    if decision.capability is Capability.ADD_ADDRESS:
                        add_text = (
                            "Share your WhatsApp location pin and I'll add that address "
                            "to your Swiggy account."
                        )
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id, text=add_text
                        )
                        await remember(add_text)
                        return {"status": "address_add_requested", "wa_id": msg.sender_wa_id}

                    if decision.capability in (
                        Capability.CLEAR_BASKET,
                        Capability.CHANGE_ITEM,
                    ):
                        from backend.agent.basket_actions import (
                            BasketReply,
                            handle_change_request,
                            handle_clear_request,
                        )

                        try:
                            if decision.capability is Capability.CLEAR_BASKET:
                                basket_reply = await handle_clear_request(
                                    turn_client, active_addr_id
                                )
                            else:
                                basket_reply = await handle_change_request(
                                    decision, turn_client, active_addr_id
                                )
                        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                            logger.warning("Basket change failed: %s", exc)
                            basket_reply = BasketReply(
                                "I couldn't read your basket just now. Please try again."
                            )

                        if basket_reply.buttons:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=basket_reply.text,
                                buttons=basket_reply.buttons,
                            )
                        else:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=basket_reply.text
                            )
                        await remember(basket_reply.text)
                        return {
                            "status": "basket_change_requested",
                            "capability": decision.capability.value,
                            "wa_id": msg.sender_wa_id,
                        }

                    if decision.capability is Capability.REORDER:
                        from backend.agent.order_actions import (
                            OrderReply,
                            handle_reorder_request,
                        )

                        try:
                            order_reply = await handle_reorder_request(
                                decision, turn_client, active_addr_id, msg.text
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

                        if order_reply.buttons:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=order_reply.text,
                                buttons=order_reply.buttons,
                            )
                        else:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=order_reply.text
                            )
                        await remember(order_reply.text)
                        return {
                            "status": "reorder_requested",
                            "wa_id": msg.sender_wa_id,
                        }

                    # Adding an item that is already in the basket is ambiguous:
                    # ask whether it means "set the total" or "add more".
                    if (
                        decision.capability is Capability.ADD_ITEMS
                        and decision.items
                        and live_cart is not None
                    ):
                        wanted = str(decision.items[0].get("query") or "").strip().lower()
                        existing = next(
                            (
                                item
                                for item in live_cart.items
                                if wanted and wanted in item.itemName.lower()
                            ),
                            None,
                        )
                        if existing:
                            try:
                                add_qty = max(1, int(decision.items[0].get("quantity") or 1))
                            except (TypeError, ValueError):
                                add_qty = 1
                            prompt_text = (
                                f"You already have *{existing.itemName}* "
                                f"({existing.quantity}) in your basket. Do you want the "
                                f"total to be {add_qty}, or {add_qty} more?"
                            )
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=prompt_text,
                                buttons=[
                                    (
                                        f"cart:qty:{existing.spinId}:{add_qty}",
                                        f"Set to {add_qty}"[:20],
                                    ),
                                    (
                                        f"cart:addqty:{existing.spinId}:{add_qty}",
                                        f"Add {add_qty} more"[:20],
                                    ),
                                ],
                            )
                            await remember(prompt_text)
                            return {
                                "status": "basket_quantity_choice",
                                "wa_id": msg.sender_wa_id,
                            }

                    if decision.capability is not Capability.ADD_ITEMS:
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id, text=NOT_READY_REPLY
                        )
                        return {
                            "status": "capability_unavailable",
                            "capability": decision.capability.value,
                            "wa_id": msg.sender_wa_id,
                        }

                    # 2. Single-Pass Conversational Intent & Item Extraction (ADR 0011)
                    turn_result = orchestrate_conversational_turn(
                        message=msg.text,
                        history=session_history,
                        address_count=address_count,
                    )

                    # Handle Chit-Chat Greetings & Conversational Q&A
                    if turn_result.intent_type in [
                        IntentType.GREETING,
                        IntentType.CONVERSATIONAL_QA,
                    ]:
                        reply_text = (
                            turn_result.conversational_reply
                            or "Hey! What groceries do you need today?"
                        )
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=reply_text,
                        )
                        session_history.append({"role": "user", "text": msg.text})
                        session_history.append({"role": "assistant", "text": reply_text})
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
                            "status": "conversational_replied",
                            "intent": turn_result.intent_type.value,
                            "wa_id": msg.sender_wa_id,
                        }

                    # Handle Cold-Start Zero-Address Onboarding (ADR 0010)
                    if turn_result.intent_type == IntentType.ZERO_ADDRESS_ONBOARDING:
                        prompt_text = (
                            turn_result.conversational_reply
                            or "Welcome to Grocer! Please share your WhatsApp delivery location pin or address so I can check your local dark store."
                        )
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=prompt_text,
                        )
                        return {
                            "status": "location_pin_requested",
                            "wa_id": msg.sender_wa_id,
                        }

                    # Handle Recipe Checklist Proposals (ADR 0009)
                    if turn_result.intent_type == IntentType.RECIPE_CHECKLIST:
                        recipe_lines = [f"🍳 *{turn_result.recipe_name or 'Recipe'} Checklist*:\n"]
                        for r_item in turn_result.recipe_items:
                            qty_desc = f" ({r_item.quantity})" if r_item.quantity else ""
                            recipe_lines.append(f"• {r_item.name}{qty_desc}")
                        if turn_result.assumed_pantry_staples:
                            recipe_lines.append(
                                f"\n_Pantry staples assumed:_ {', '.join(turn_result.assumed_pantry_staples)}"
                            )
                        recipe_body = "\n".join(recipe_lines)
                        buttons = [
                            (act["id"], act["title"][:20])
                            for act in turn_result.suggested_actions[:3]
                        ] or [("recipe:add:all", "Add All Items")]
                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=msg.sender_wa_id,
                            body_text=recipe_body,
                            buttons=buttons,
                        )
                        session_history.append({"role": "user", "text": msg.text})
                        session_history.append({"role": "assistant", "text": recipe_body})
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
                            "status": "recipe_proposed",
                            "recipe": turn_result.recipe_name,
                            "wa_id": msg.sender_wa_id,
                        }

                    # 2. Grocery List Intent: Parallel Search & Candidate Evaluation (ADR 0011)
                    extracted_items = turn_result.extracted_items
                    if not extracted_items:
                        extracted_items = [ExtractedGroceryItem(query=msg.text, quantity=1)]

                    async def search_and_eval(
                        target: ExtractedGroceryItem,
                        sw_client: SwiggyClient = turn_client,
                        addr_id: str | None = active_addr_id,
                        addr_cnt: int = address_count,
                    ):
                        cands = await asyncio.to_thread(
                            search_catalog,
                            query=target.query,
                            swiggy_client=sw_client,
                            address_id=addr_id,
                        )
                        eval_res = evaluate_customer_intent(
                            query=target.query,
                            candidates=cands,
                            address_count=addr_cnt,
                        )
                        return target, cands, eval_res

                    search_results = await asyncio.gather(
                        *(search_and_eval(target) for target in extracted_items)
                    )

                    items_to_add: list[TargetCartItem] = []
                    disambiguation_notes: list[str] = []
                    unfound_queries: list[str] = []

                    for target, cands, evaluation in search_results:
                        if evaluation.selected_candidate:
                            cand = evaluation.selected_candidate
                            items_to_add.append(
                                TargetCartItem(
                                    spin_id=cand.spin_id,
                                    sku_id=cand.sku_id,
                                    quantity=target.quantity,
                                    item_name=cand.display_name,
                                    price_paise=cand.offer_price_paise,
                                )
                            )
                        elif (
                            evaluation.intent_type == IntentType.DISAMBIGUATION
                            and evaluation.message
                        ):
                            disambiguation_notes.append(evaluation.message)
                        else:
                            unfound_queries.append(target.query)

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
                        if disambiguation_notes:
                            receipt_body += "\n\n💡 *" + "\n".join(disambiguation_notes) + "*"
                        if unfound_queries:
                            receipt_body += (
                                f"\n\n⚠️ *Not found at store:* {', '.join(unfound_queries)}"
                            )

                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=msg.sender_wa_id,
                            body_text=receipt_body,
                            buttons=[
                                (f"pay:{approval.id}", f"Pay {to_pay_formatted}"),
                                ("cart:clear", "Clear Basket"),
                            ],
                        )

                        session_history.append({"role": "user", "text": msg.text})
                        session_history.append(
                            {
                                "role": "assistant",
                                "text": f"Basket updated. Total {to_pay_formatted}",
                            }
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

                    await wa_client.send_text_message(
                        to_wa_id=msg.sender_wa_id,
                        text=f"Sorry, I couldn't find items matching '{msg.text}' at your local dark store. Could you try a different brand or item name?",
                    )
                    return {"status": "no_match", "query": msg.text}

                try:
                    results.append(await run_turn(client, msg, user_id, conn, wa_client))
                except SwiggyAuthExpiredError:
                    # Try a silent refresh before parking (Gate 1). Park only if it fails.
                    new_token = await refresh_user_token(user_id, force=True)
                    retried = False
                    if new_token:
                        try:
                            results.append(
                                await run_turn(
                                    SwiggyClient(auth_token=new_token),
                                    msg,
                                    user_id,
                                    conn,
                                    wa_client,
                                )
                            )
                            retried = True
                        except SwiggyAuthExpiredError:
                            retried = False
                    if not retried:
                        await conn.execute(
                            "UPDATE grocer.inbound_messages SET status = 'parked' WHERE id = $1;",
                            inbound_id,
                        )
                        login_url = f"https://grocerr.vercel.app?phone={msg.sender_wa_id}"
                        await wa_client.send_cta_url_button(
                            to_wa_id=msg.sender_wa_id,
                            body_text=(
                                "⚠️ *Your Swiggy login needs a security refresh.*\n\n"
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
