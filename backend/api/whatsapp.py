"""WhatsApp Business Webhook API routes (GET challenge & POST event handler)."""
from __future__ import annotations

import asyncio
import json
import logging
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.intent.orchestrator import GrocerOrchestrator

logger = logging.getLogger("grocer.api.whatsapp")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
_orchestrator = GrocerOrchestrator()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta WhatsApp Webhook verification endpoint (Spec §18)."""
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
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed JSON: {exc}")

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
        if not default_whatsapp_adapter.reserve_message(incoming.message_id):
            continue
        try:
            pending_response = default_whatsapp_adapter.pending_delivery(
                incoming.message_id
            )
            if pending_response is not None:
                if not await default_whatsapp_adapter.send_response(pending_response):
                    raise RuntimeError("WhatsApp response delivery retry failed.")
            else:
                await default_whatsapp_adapter.dispatch(incoming, _orchestrator)
            default_whatsapp_adapter.mark_processed(incoming.message_id)
            processed_count += 1
        except asyncio.CancelledError:
            default_whatsapp_adapter.release_message(incoming.message_id)
            raise
        except Exception as exc:
            default_whatsapp_adapter.release_message(incoming.message_id)
            logger.error("WhatsApp dispatch failed: %s", type(exc).__name__)
            failed_count += 1

    if failed_count:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="One or more messages could not be delivered.",
        )

    return {"status": "ok", "processed": processed_count}
