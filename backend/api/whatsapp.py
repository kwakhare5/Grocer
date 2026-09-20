"""WhatsApp Business Webhook API routes (GET challenge & POST event handler)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.channels.models import NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.config import settings

logger = logging.getLogger("grocer.api.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


async def _dispatch_task_message(task_message: NormalizedIncomingMessage, engine: Any) -> None:
    """Asynchronously process agent turn and deliver reply via WhatsApp Cloud API."""
    try:
        response = await engine.handle_message(task_message)
        if not await default_whatsapp_adapter.send_response(response):
            logger.error("WhatsApp response delivery failed for message_id=%s", task_message.message_id)
        default_whatsapp_adapter.mark_processed(task_message.message_id)
    except asyncio.CancelledError:
        default_whatsapp_adapter.release_message(task_message.message_id)
        raise
    except Exception as exc:
        logger.exception(
            "Agent dispatch failed for message_id=%s error=%s",
            task_message.message_id,
            exc,
        )
        recovery = NormalizedOutgoingResponse(
            recipient_id=task_message.sender_id,
            channel=task_message.channel,
            text=(
                "I had a brief glitch processing that. Your basket is unchanged. "
                "Please try sending your message again!"
            ),
            conversation_state="READY",
        )
        await default_whatsapp_adapter.send_response(recovery)
        default_whatsapp_adapter.mark_processed(task_message.message_id)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta WhatsApp Webhook verification endpoint (Spec Section 18)."""
    is_valid, challenge_or_err = default_whatsapp_adapter.verify_webhook_challenge(
        mode=hub_mode,
        token=hub_verify_token,
        challenge=hub_challenge,
    )
    if is_valid:
        return PlainTextResponse(content=challenge_or_err, status_code=status.HTTP_200_OK)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str | int]:
    """Meta WhatsApp Webhook event receiver with fast background dispatch and duplicate event filtering."""
    body_bytes = await request.body()
    if len(body_bytes) > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large.",
        )

    # Signature verification
    if not default_whatsapp_adapter.verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WhatsApp webhook signature.",
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON.")

    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid WhatsApp webhook envelope.",
        )

    incoming_messages = default_whatsapp_adapter.parse_webhook_payload(payload)
    logger.info("Parsed %d incoming message(s) from WhatsApp webhook", len(incoming_messages))

    engine = getattr(request.app.state, "agent_engine", None)
    if not engine:
        raise RuntimeError("Agent engine is not configured.")

    processed_count = 0
    for incoming in incoming_messages:
        # Atomic reservation check: reject duplicate or in-flight Meta webhook retries
        if not default_whatsapp_adapter.reserve_message(incoming.message_id):
            logger.info("Dropping duplicate or already in-flight WhatsApp message_id=%s", incoming.message_id)
            continue

        # Immediately mark incoming message as read (instant blue ticks within 200ms)
        asyncio.create_task(default_whatsapp_adapter.mark_message_read(incoming.message_id))

        task_message = incoming.model_copy(
            update={
                "customer_id": default_whatsapp_adapter.map_sender_to_customer_id(
                    incoming.sender_id
                )
            }
        )
        background_tasks.add_task(_dispatch_task_message, task_message, engine)
        processed_count += 1

    return {"status": "ok", "processed": processed_count}
