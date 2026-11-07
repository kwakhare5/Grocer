"""Grocer — WhatsApp Cloud API Webhook Route & Ingestion Shield."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from backend.channels.button_router import dispatch_button_action
from backend.channels.reactions import reaction_for_result
from backend.channels.turn_pipeline import run_commerce_turn
from backend.channels.whatsapp_crypto import verify_signature, verify_webhook_challenge
from backend.channels.whatsapp_parser import parse_webhook_payload
from backend.config import settings
from backend.database import get_db_pool
from backend.observability import begin_turn, end_turn, set_turn_context

logger = logging.getLogger("grocer.channels.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

_READ_TASKS: set[asyncio.Task[Any]] = set()
_REACTION_TASKS: set[asyncio.Task[Any]] = set()

# A quick second message waits for the first turn instead of being lost. The
# wait stays inside Meta's webhook window; a turn still running after that
# gets an honest "send it again" reply.
CONCURRENCY_WAIT_SECONDS = 12.0
CONCURRENCY_POLL_SECONDS = 0.2

# Abuse limits: one person cannot burn the free AI or Swiggy calls for everyone.
MAX_MESSAGES_PER_HOUR = 20


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


def _login_url(wa_id: str) -> str:
    """The bot issues the link, so the link names the number being connected."""
    from backend.channels.link_tokens import issue_link_token

    return f"https://grocerr.vercel.app?t={issue_link_token(wa_id)}"


def _swiggy_tool_error_reply(exc: Exception) -> str:
    from backend.agent.read_actions import swiggy_failure_reply

    return swiggy_failure_reply(exc)


async def _park_and_prompt(
    conn: Any,
    inbound_id: Any,
    wa_id: str,
    wa_client: Any,
    *,
    first_connect: bool = False,
) -> None:
    """Mark the inbound row replayable and send the signed connect link."""
    await conn.execute(
        "UPDATE grocer.inbound_messages SET status = 'awaiting_link' WHERE id = $1;",
        inbound_id,
    )
    if first_connect:
        body_text = (
            "👋 *Welcome to Grocer!*\n\n"
            "Connect your Swiggy account to shop Instamart. Tap below, sign in, "
            "and I'll run your message automatically when you're back."
        )
        button_text = "Connect Swiggy"
    else:
        body_text = (
            "⚠️ *Your Swiggy login needs a security refresh.*\n\n"
            "Tap below to reconnect your account. Your grocery list has been saved "
            "and will resume automatically:"
        )
        button_text = "Reconnect Swiggy"
    await wa_client.send_cta_url_button(
        to_wa_id=wa_id,
        body_text=body_text,
        button_text=button_text,
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
async def webhook_route(request: Request) -> dict[str, Any]:
    return await handle_webhook(request)


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
                begin_turn(msg.wa_message_id)
                set_turn_context(capability="button")
                action_res: dict[str, Any] = {}
                try:
                    action_res = await dispatch_button_action(
                        msg.button_id,
                        msg.sender_wa_id,
                        pool,
                        swiggy_client=swiggy_client,
                        message_type=msg.message_type,
                        wa_client=wa_client,
                    )
                finally:
                    end_turn(action_res.get("status", "error"))
                results.append(action_res)
                continue

            # 7a. Per-user volume cap. One sender cannot burn the free AI budget
            # or the store calls for everyone else.
            if not msg.button_id:
                recent_count = await conn.fetchval(
                    "SELECT count(*) FROM grocer.inbound_messages "
                    "WHERE user_id = $1 AND created_at > now() - interval '1 hour';",
                    user_id,
                )
                if int(recent_count or 0) > MAX_MESSAGES_PER_HOUR:
                    await conn.execute(
                        "UPDATE grocer.inbound_messages SET status = 'rate_limited' "
                        "WHERE id = $1;",
                        inbound_id,
                    )
                    # One warning per hour, then silent drops: a spammer must not
                    # turn the bot into an outbound message amplifier.
                    if int(recent_count or 0) == MAX_MESSAGES_PER_HOUR + 1:
                        await wa_client.send_text_message(
                            to_wa_id=msg.sender_wa_id,
                            text=(
                                "You're sending messages too fast. Give me a few minutes, "
                                "then try again."
                            ),
                        )
                    results.append(
                        {"status": "rate_limited", "wa_message_id": msg.wa_message_id}
                    )
                    continue

            # 7b. Photos, voice notes and stickers get one honest reply, not silence.
            if msg.message_type == "unsupported":
                raw_type = str((msg.raw_payload or {}).get("type") or "").lower()
                if raw_type == "reaction":
                    results.append(
                        {"status": "ignored_reaction", "wa_message_id": msg.wa_message_id}
                    )
                    continue
                await conn.execute(
                    "UPDATE grocer.inbound_messages SET status = 'unsupported_message' "
                    "WHERE id = $1;",
                    inbound_id,
                )
                await wa_client.send_text_message(
                    to_wa_id=msg.sender_wa_id,
                    text=(
                        "I can only read text and location pins right now. "
                        "Please type what you need."
                    ),
                )
                results.append(
                    {"status": "unsupported_message", "wa_message_id": msg.wa_message_id}
                )
                continue

            # 7c. Website connect code. The typed number must send its own code
            # before any login link leaves the bot.
            if msg.text and msg.text.strip().lower().startswith("connect "):
                from backend.channels.link_tokens import verify_link_token

                code = msg.text.strip().split(None, 1)[1].strip()
                typed_wa_id = verify_link_token(code)
                if typed_wa_id is None:
                    await conn.execute(
                        "UPDATE grocer.inbound_messages SET status = 'connect_invalid' "
                        "WHERE id = $1;",
                        inbound_id,
                    )
                    await wa_client.send_text_message(
                        to_wa_id=msg.sender_wa_id,
                        text=(
                            "That connect code is invalid or expired. "
                            "Enter your number on the website again for a fresh one."
                        ),
                    )
                    results.append({"status": "connect_invalid"})
                    continue
                if typed_wa_id != msg.sender_wa_id:
                    await conn.execute(
                        "UPDATE grocer.inbound_messages SET status = 'connect_mismatch' "
                        "WHERE id = $1;",
                        inbound_id,
                    )
                    await wa_client.send_text_message(
                        to_wa_id=msg.sender_wa_id,
                        text=(
                            "That code belongs to a different number. "
                            "Message me from the number you entered on the website."
                        ),
                    )
                    results.append({"status": "connect_mismatch"})
                    continue

                await conn.execute(
                    "UPDATE grocer.inbound_messages SET status = 'connect_confirmed' "
                    "WHERE id = $1;",
                    inbound_id,
                )
                await wa_client.send_cta_url_button(
                    to_wa_id=msg.sender_wa_id,
                    body_text=(
                        "*Number confirmed.* Tap below to sign in to Swiggy. "
                        "I'll be ready in your chat when you're back."
                    ),
                    button_text="Connect Swiggy",
                    url=_login_url(msg.sender_wa_id),
                )
                results.append({"status": "connect_confirmed"})
                continue

            # 8. Deterministic admin/privacy commands (DPDP) take priority over commerce
            if msg.text and msg.text.strip().lower() == "delete my data":
                from backend.agent.dpdp import handle_delete_my_data

                cmd_res = await handle_delete_my_data(conn, str(user_id))
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
                    SwiggyToolError,
                )
                from backend.integrations.commerce.token_vault import (
                    refresh_user_token,
                    resolve_user_token,
                )

                wa_client = wa_client or WhatsAppClient()

                user_token = await resolve_user_token(user_id)
                if not user_token:
                    if msg.text:
                        await _park_and_prompt(
                            conn,
                            inbound_id,
                            msg.sender_wa_id,
                            wa_client,
                            first_connect=True,
                        )
                    else:
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

                begin_turn(msg.wa_message_id)
                trace_status = "error"
                try:
                    turn_result = await run_commerce_turn(client, msg, user_id, conn, wa_client)
                    trace_status = turn_result.get("status", "ok")
                    _react_in_background(wa_client, msg, turn_result)
                    results.append(turn_result)
                except SwiggyToolError as exc:
                    trace_status = "swiggy_error"
                    await wa_client.send_text_message(
                        to_wa_id=msg.sender_wa_id,
                        text=_swiggy_tool_error_reply(exc),
                    )
                    results.append(
                        {"status": "swiggy_error", "error_message": str(exc)}
                    )
                except SwiggyAuthExpiredError:
                    # Try a silent refresh before parking (Gate 1). Park only if it fails.
                    new_token = await refresh_user_token(user_id, force=True)
                    retried = False
                    if new_token:
                        try:
                            turn_result = await run_commerce_turn(
                                SwiggyClient(auth_token=new_token),
                                msg,
                                user_id,
                                conn,
                                wa_client,
                            )
                            trace_status = turn_result.get("status", "ok")
                            _react_in_background(wa_client, msg, turn_result)
                            results.append(turn_result)
                            retried = True
                        except SwiggyAuthExpiredError:
                            retried = False
                        except SwiggyToolError as exc:
                            trace_status = "swiggy_error"
                            await wa_client.send_text_message(
                                to_wa_id=msg.sender_wa_id,
                                text=_swiggy_tool_error_reply(exc),
                            )
                            results.append(
                                {"status": "swiggy_error", "error_message": str(exc)}
                            )
                            retried = True
                    if not retried:
                        await _park_and_prompt(
                            conn, inbound_id, msg.sender_wa_id, wa_client
                        )
                        results.append({"status": "auth_expired", "wa_id": msg.sender_wa_id})
                        trace_status = "auth_expired"
                finally:
                    end_turn(trace_status)
                continue

            results.append({"status": "processed", "wa_message_id": msg.wa_message_id})

    # Single-message response preservation for caller convenience
    if len(results) == 1:
        return results[0]

    return {"status": "ok", "processed": len(results), "results": results}
