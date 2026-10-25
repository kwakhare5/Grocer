"""Grocer v1.0 — WhatsApp Cloud API Webhook Route & Ingestion Shield."""

from __future__ import annotations

import json
import logging
from typing import Any

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
async def handle_webhook(request: Request) -> dict[str, Any]:
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
            results.append({"status": "stale_dropped", "wa_message_id": msg.wa_message_id})
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
                results.append({"status": "duplicate_dropped", "wa_message_id": msg.wa_message_id})
                continue

            # 6. Per-User Advisory Lock (Fast concurrency serialization)
            lock_acquired = await conn.fetchval(
                "SELECT pg_try_advisory_xact_lock(hashtext($1));",
                str(user_id),
            )
            if not lock_acquired:
                logger.warning("User %s locked by concurrent action; queuing message", user_id)
                await conn.execute(
                    "UPDATE grocer.inbound_messages SET status = 'concurrency_dropped' WHERE id = $1;",
                    inbound_id,
                )
                results.append({"status": "concurrency_dropped", "wa_message_id": msg.wa_message_id})
                continue

            # 7. Fast 50ms Button Dispatcher for interactive replies
            if msg.button_id:
                action_res = await dispatch_button_action(msg.button_id, msg.sender_wa_id, pool)
                results.append(action_res)
                continue

            results.append({"status": "processed", "wa_message_id": msg.wa_message_id})

    # Single-message response preservation for caller convenience
    if len(results) == 1:
        return results[0]

    return {"status": "ok", "processed": len(results), "results": results}
