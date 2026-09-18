"""WhatsApp Business Webhook API routes (GET challenge & POST event handler)."""
from __future__ import annotations

import asyncio
import json
import logging
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.channels.models import NormalizedOutgoingResponse
from backend.config import settings

logger = logging.getLogger("grocer.api.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
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
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str | int]:
    """Meta WhatsApp Webhook event receiver with signature validation and duplicate event filtering."""
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

    processed_count = 0
    failed_count = 0
    for incoming in incoming_messages:
        try:
            task_message = incoming.model_copy(
                update={
                    "customer_id": default_whatsapp_adapter.map_sender_to_customer_id(
                        incoming.sender_id
                    )
                }
            )
            engine = getattr(request.app.state, "agent_engine", None)
            if not engine:
                raise RuntimeError("Agent engine is not configured.")
            response = await engine.handle_message(task_message)

            if not await default_whatsapp_adapter.send_response(response):
                raise RuntimeError("WhatsApp response delivery failed.")
            processed_count += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception(
                "Agent dispatch failed for message_id=%s error=%s",
                incoming.message_id,
                exc,
            )
            recovery = NormalizedOutgoingResponse(
                recipient_id=incoming.sender_id,
                channel=incoming.channel,
                text=(
                    "I had a brief glitch processing that. Your basket is unchanged. "
                    "Please try sending your message again!"
                ),
                conversation_state="READY",
            )
            if await default_whatsapp_adapter.send_response(recovery):
                processed_count += 1
            else:
                failed_count += 1

    if failed_count:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="One or more messages could not be delivered.",
        )

    return {"status": "ok", "processed": processed_count}
