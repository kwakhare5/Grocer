"""Grocer — WhatsApp Cloud API Webhook Route & Ingestion Shield."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from backend.channels.button_router import dispatch_button_action, send_receipt
from backend.channels.reactions import reaction_for_result
from backend.channels.whatsapp_crypto import verify_signature, verify_webhook_challenge
from backend.channels.whatsapp_parser import parse_webhook_payload
from backend.config import settings
from backend.database import get_db_pool

logger = logging.getLogger("grocer.channels.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

_READ_TASKS: set[asyncio.Task[Any]] = set()
_REACTION_TASKS: set[asyncio.Task[Any]] = set()

# A quick second message waits for the first turn instead of being lost. The
# wait stays inside Meta's webhook window; a turn still running after that
# gets an honest "send it again" reply.
CONCURRENCY_WAIT_SECONDS = 12.0
CONCURRENCY_POLL_SECONDS = 0.2


def _mark_read_in_background(wa_client: Any, message_id: str) -> None:
    """Blue ticks must never add Meta latency to the turn."""
    task = asyncio.create_task(wa_client.mark_read(message_id))
    _READ_TASKS.add(task)
    task.add_done_callback(_READ_TASKS.discard)


def _react_in_background(wa_client: Any, msg: Any, result: dict[str, Any]) -> None:
    """One reaction, after the reply lands. Never blocks or fails the turn."""
    emoji = reaction_for_result(result)
    if not emoji:
        return
    task = asyncio.create_task(
        wa_client.send_reaction(
            to_wa_id=msg.sender_wa_id,
            message_id=msg.wa_message_id,
            emoji=emoji,
        )
    )
    _REACTION_TASKS.add(task)
    task.add_done_callback(_REACTION_TASKS.discard)


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


def _login_url(wa_id: str) -> str:
    """The bot issues the link, so the link names the number being connected."""
    from backend.channels.link_tokens import issue_link_token

    return f"https://grocerr.vercel.app?t={issue_link_token(wa_id)}"


async def _park_and_prompt(
    conn: Any,
    inbound_id: Any,
    wa_id: str,
    wa_client: Any,
) -> None:
    """Mark the inbound row replayable and send the signed reconnect link."""
    await conn.execute(
        "UPDATE grocer.inbound_messages SET status = 'awaiting_link' WHERE id = $1;",
        inbound_id,
    )
    await wa_client.send_cta_url_button(
        to_wa_id=wa_id,
        body_text=(
            "⚠️ *Your Swiggy login needs a security refresh.*\n\n"
            "Tap below to reconnect your account. Your grocery list has been saved "
            "and will resume automatically:"
        ),
        button_text="Reconnect Swiggy",
        url=_login_url(wa_id),
    )


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
    wa_client: Any | None = None,
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

        async with pool.acquire() as conn:
            # 4-5 commit before the turn. If the turn dies mid-way, Meta's retry
            # must still hit the dedupe row instead of repeating a cart write.
            async with conn.transaction():
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

            # 5a. Blue ticks and a typing bubble while the turn runs.
            from backend.channels.whatsapp_client import WhatsAppClient

            wa_client = wa_client or WhatsAppClient()
            _mark_read_in_background(wa_client, msg.wa_message_id)

            # 6. Per-User Session Advisory Lock (Fast concurrency serialization).
            # Session-scoped so it survives the commit above; asyncpg releases it
            # when this connection returns to the pool. A second quick message
            # waits its turn and is then answered against the fresh cart.
            deadline = time.monotonic() + CONCURRENCY_WAIT_SECONDS
            lock_acquired = False
            while True:
                lock_acquired = await conn.fetchval(
                    "SELECT pg_try_advisory_lock(hashtext($1));",
                    str(user_id),
                )
                if lock_acquired or time.monotonic() >= deadline:
                    break
                await asyncio.sleep(CONCURRENCY_POLL_SECONDS)
            if not lock_acquired:
                logger.warning(
                    "User %s still locked after %.1fs; asking for a resend",
                    user_id,
                    CONCURRENCY_WAIT_SECONDS,
                )
                await conn.execute(
                    "UPDATE grocer.inbound_messages SET status = 'concurrency_wait_timeout' WHERE id = $1;",
                    inbound_id,
                )
                await wa_client.send_text_message(
                    to_wa_id=msg.sender_wa_id,
                    text=(
                        "I'm still finishing your last message. "
                        "Give me a few seconds, then send that again."
                    ),
                )
                results.append(
                    {
                        "status": "concurrency_wait_timeout",
                        "wa_message_id": msg.wa_message_id,
                    }
                )
                continue

            # 7. Fast 50ms Button Dispatcher for interactive replies
            if msg.button_id:
                action_res = await dispatch_button_action(
                    msg.button_id,
                    msg.sender_wa_id,
                    pool,
                    swiggy_client=swiggy_client,
                    message_type=msg.message_type,
                    wa_client=wa_client,
                )
                results.append(action_res)
                continue

            # 8. Deterministic admin/privacy commands (DPDP) take priority over commerce
            if msg.text:
                from backend.channels.command_router import dispatch_text_command

                cmd_res = await dispatch_text_command(msg.text, str(user_id), conn)
                if cmd_res is not None:
                    from backend.channels.whatsapp_client import WhatsAppClient

                    wa_client = wa_client or WhatsAppClient()
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

                wa_client = wa_client or WhatsAppClient()

                user_token = await resolve_user_token(user_id)
                if not user_token:
                    login_url = _login_url(msg.sender_wa_id)
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
                    evaluate_customer_intents_batch,
                    format_paise_to_rupees,
                )
                from backend.agent.candidate_search import search_catalog_full
                from backend.agent.composite_cart import (
                    MAX_RECEIPT_ITEM_LINES,
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

                    # 0. A numbered reply to the plan on screen picks items with
                    # no model call. Only number-shaped text is taken.
                    pending_plan = session_row["pending_plan"] if session_row else None
                    plan_fresh = bool(session_row and session_row["plan_fresh"])
                    from backend.agent.meal_planner import (
                        clear_pending_plan,
                        parse_pick_indexes,
                        plan_items,
                    )

                    if pending_plan and not plan_fresh:
                        await clear_pending_plan(conn, user_id)
                    if pending_plan and plan_fresh:
                        try:
                            plan = (
                                json.loads(pending_plan)
                                if isinstance(pending_plan, str)
                                else pending_plan
                            )
                        except (json.JSONDecodeError, TypeError, ValueError):
                            plan = None
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
                                await remember(
                                    "Added the items you picked from the plan."
                                )
                            return picked

                    # 1. Capability routing (ADR 0012). Read capabilities are answered
                    # here and can never write. Basket requests continue below.
                    from backend.agent.read_actions import (
                        NOT_READY_REPLY,
                        build_read_reply,
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
                        coords: tuple[float, float] | None = None
                        if decision.capability is Capability.TRACK_ORDER:
                            coord_row = await conn.fetchrow(
                                "SELECT latitude, longitude FROM grocer.address_coords WHERE address_id = $1;",
                                active_addr_id,
                            )
                            if coord_row:
                                coords = (coord_row["latitude"], coord_row["longitude"])
                            else:
                                session_coords = await conn.fetchrow(
                                    "SELECT delivery_latitude, delivery_longitude FROM grocer.sessions WHERE user_id = $1;",
                                    user_id,
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
                            decision, turn_client, active_addr_id, coords
                        )
                        reply_text = read_reply.text
                        if read_reply.buttons:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=reply_text,
                                buttons=read_reply.buttons,
                            )
                        else:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=reply_text
                            )
                        notice = _basket_notice(
                            session_row["last_active_at"] if session_row else None,
                            live_cart,
                        )
                        if notice:
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=notice[0],
                                buttons=notice[1],
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
                        if read_reply.pending_plan:
                            from backend.agent.meal_planner import PLAN_TTL_MINUTES

                            await conn.execute(
                                "UPDATE grocer.sessions SET pending_plan = $2::jsonb, "
                                "pending_plan_expires_at = now() + ($3 * interval '1 minute') "
                                "WHERE user_id = $1;",
                                user_id,
                                json.dumps(read_reply.pending_plan),
                                PLAN_TTL_MINUTES,
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

                    if decision.capability is Capability.REPORT_ISSUE:
                        from backend.agent.order_actions import handle_report_issue

                        report = await handle_report_issue(decision, turn_client)
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id, text=report.text
                        )
                        await remember(report.text)
                        return {
                            "status": "issue_reported",
                            "wa_id": msg.sender_wa_id,
                        }

                    if decision.capability is Capability.ADD_ADDRESS:
                        from backend.agent.address_lifecycle import (
                            AddressOnboardingFlow,
                        )

                        try:
                            turn = AddressOnboardingFlow(turn_client).start_from_text(
                                msg.text or ""
                            )
                        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                            logger.warning("Typed address start failed: %s", exc)
                            turn = None

                        if turn is None:
                            add_text = (
                                "I couldn't read that address. Send the full address with "
                                "the area and PIN, or share a WhatsApp location pin."
                            )
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id, text=add_text
                            )
                            await remember(add_text)
                            return {
                                "status": "address_add_failed",
                                "wa_id": msg.sender_wa_id,
                            }

                        await conn.execute(
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
                            user_id,
                            turn.next_step.value,
                            json.dumps(turn.context),
                        )
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id, text=turn.prompt
                        )
                        await remember(turn.prompt)
                        return {
                            "status": "address_add_started",
                            "wa_id": msg.sender_wa_id,
                            "step": turn.next_step.value,
                        }

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

                    # Adding one item that is already in the basket is ambiguous:
                    # ask whether it means "set the total" or "add more". A list of
                    # several items is a plain add; asking there would drop the rest.
                    if (
                        decision.capability is Capability.ADD_ITEMS
                        and len(decision.items) == 1
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
                                f"({existing.quantity}) in your basket. Add {add_qty} more, "
                                f"or make the total {add_qty}?"
                            )
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=prompt_text,
                                buttons=[
                                    (
                                        f"cart:addqty:{existing.spinId}:{add_qty}",
                                        f"Add {add_qty} more"[:20],
                                    ),
                                    (
                                        f"cart:qty:{existing.spinId}:{add_qty}",
                                        f"Make total {add_qty}"[:20],
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

                    # 2. Items come from the router. No second classification call.
                    extracted_items: list[ExtractedGroceryItem] = []
                    for item in decision.items:
                        query_text = str(item.get("query") or "").strip()
                        if not query_text:
                            continue
                        try:
                            quantity = max(1, int(item.get("quantity") or 1))
                        except (TypeError, ValueError):
                            quantity = 1
                        extracted_items.append(
                            ExtractedGroceryItem(
                                query=query_text,
                                quantity=quantity,
                                unit=str(item.get("unit") or "") or None,
                            )
                        )
                    if not extracted_items:
                        extracted_items = [ExtractedGroceryItem(query=msg.text, quantity=1)]

                    # 1a. The same words asked twice share one search and one
                    # evaluation; the quantities add up.
                    from backend.integrations.commerce.swiggy_client import (
                        normalize_query,
                    )

                    merged_items: dict[str, ExtractedGroceryItem] = {}
                    for target in extracted_items:
                        key = normalize_query(target.query).lower()
                        if key in merged_items:
                            merged_items[key].quantity += target.quantity
                        else:
                            merged_items[key] = target
                    extracted_items = list(merged_items.values())

                    async def search_one(
                        target: ExtractedGroceryItem,
                        sw_client: SwiggyClient = turn_client,
                        addr_id: str | None = active_addr_id,
                    ):
                        outcome = await asyncio.to_thread(
                            search_catalog_full,
                            query=target.query,
                            swiggy_client=sw_client,
                            address_id=addr_id,
                        )
                        return target, outcome.candidates, outcome.alternatives

                    search_results = await asyncio.gather(
                        *(search_one(target) for target in extracted_items)
                    )
                    evaluations = await asyncio.to_thread(
                        evaluate_customer_intents_batch,
                        [
                            (target.query, cands)
                            for target, cands, _alternatives in search_results
                        ],
                        address_count,
                        msg.text,
                    )

                    items_to_add: list[TargetCartItem] = []
                    choice_prompts: list[tuple[Any, list[Any]]] = []
                    unfound_queries: list[str] = []
                    alternative_hints: list[str] = []
                    vague_spins: set[str] = set()

                    for (target, cands, alternatives), evaluation in zip(
                        search_results, evaluations, strict=True
                    ):
                        if evaluation.selected_candidate:
                            cand = evaluation.selected_candidate
                            if evaluation.is_vague_staple:
                                vague_spins.add(cand.spin_id)
                            items_to_add.append(
                                TargetCartItem(
                                    spin_id=cand.spin_id,
                                    sku_id=cand.sku_id,
                                    quantity=target.quantity,
                                    item_name=cand.display_name,
                                    price_paise=cand.offer_price_paise,
                                    max_quantity=cand.max_quantity,
                                    max_quantity_message=cand.max_quantity_message,
                                )
                            )
                        elif evaluation.intent_type == IntentType.DISAMBIGUATION:
                            choice_prompts.append((target, cands))
                        else:
                            unfound_queries.append(target.query)
                            if alternatives:
                                alternative_hints.append(
                                    f"{target.query} → {', '.join(alternatives)}"
                                )

                    if (
                        not items_to_add
                        and len(search_results) == 1
                        and len(search_results[0][1]) >= 2
                    ):
                        target, cands, alternatives = search_results[0]
                        choice_text, choice_buttons = format_disambiguation_choices(
                            target.query, cands, target.quantity
                        )
                        if alternatives:
                            choice_text += f"\n\nSimilar: {', '.join(alternatives)}"
                        await wa_client.send_quick_reply_buttons(
                            to_wa_id=msg.sender_wa_id,
                            body_text=choice_text,
                            buttons=choice_buttons,
                        )
                        await remember(choice_text)
                        return {
                            "status": "item_choices",
                            "wa_id": msg.sender_wa_id,
                            "candidates": len(cands),
                        }

                    if not items_to_add and choice_prompts:
                        for target, cands in choice_prompts[:2]:
                            choice_text, choice_buttons = format_disambiguation_choices(
                                target.query, cands, target.quantity
                            )
                            await wa_client.send_quick_reply_buttons(
                                to_wa_id=msg.sender_wa_id,
                                body_text=choice_text,
                                buttons=choice_buttons,
                            )
                        if unfound_queries:
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id,
                                text=(
                                    "I couldn't find at this store: "
                                    + ", ".join(unfound_queries)
                                    + "."
                                ),
                            )
                        await remember("Asked which product to pick")
                        return {
                            "status": "item_choices",
                            "wa_id": msg.sender_wa_id,
                            "candidates": len(choice_prompts),
                        }

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
                            receipt_body += f"\n\n⚠️ *Not found at store:* {detail}"
                        cap_paise = await conn.fetchval(
                            "SELECT budget_cap_paise FROM grocer.sessions WHERE user_id = $1;",
                            user_id,
                        ) or settings.DEFAULT_BUDGET_CAP_PAISE
                        if approval.to_pay_paise > int(cap_paise):
                            receipt_body += (
                                f"\n\n⚠️ This is above your "
                                f"{format_paise_to_rupees(int(cap_paise))} safety cap. "
                                "You'll be asked to raise it when you tap Pay."
                            )

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
                                target.query, cands, target.quantity
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

                try:
                    turn_result = await run_turn(client, msg, user_id, conn, wa_client)
                    _react_in_background(wa_client, msg, turn_result)
                    results.append(turn_result)
                except SwiggyAuthExpiredError:
                    # Try a silent refresh before parking (Gate 1). Park only if it fails.
                    new_token = await refresh_user_token(user_id, force=True)
                    retried = False
                    if new_token:
                        try:
                            turn_result = await run_turn(
                                SwiggyClient(auth_token=new_token),
                                msg,
                                user_id,
                                conn,
                                wa_client,
                            )
                            _react_in_background(wa_client, msg, turn_result)
                            results.append(turn_result)
                            retried = True
                        except SwiggyAuthExpiredError:
                            retried = False
                    if not retried:
                        await _park_and_prompt(
                            conn, inbound_id, msg.sender_wa_id, wa_client
                        )
                        results.append({"status": "auth_expired", "wa_id": msg.sender_wa_id})
                continue

            results.append({"status": "processed", "wa_message_id": msg.wa_message_id})

    # Single-message response preservation for caller convenience
    if len(results) == 1:
        return results[0]

    return {"status": "ok", "processed": len(results), "results": results}
