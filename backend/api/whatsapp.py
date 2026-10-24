"""WhatsApp Business Webhook API routes (GET challenge & POST event handler)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.channels.message_store import PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.integrations.commerce.token_vault import default_token_vault

logger = logging.getLogger("grocer.api.whatsapp")

_DELETE_DATA_PATTERN = re.compile(
    r"^(?:please\s+)?(?:delete|purge|erase|remove)\s+(?:all\s+)?(?:my\s+)?(?:data|history|account)\.?$",
    re.IGNORECASE,
)

HEARTBEAT_INTERVAL_SECONDS = 15

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


async def drain_outbound_queue(store: PostgresMessageStore) -> int:
    """Deliver staged responses promptly without blocking on inbound turns."""
    sent = 0
    while True:
        outbound = await store.claim_outbound()
        if outbound is None:
            break
        outbound_id, customer_id, response = outbound
        delivered = False
        for attempt in range(3):
            try:
                delivered = await default_whatsapp_adapter.send_response(response)
                if delivered:
                    break
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("WhatsApp delivery attempt %d failed for outbound_id=%s", attempt + 1, outbound_id)
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
        await store.mark_outbound(outbound_id, delivered)
        if "DELETE_CUSTOMER_DATA" in response.events:
            await store.purge_customer(customer_id)
        if not delivered:
            logger.error("WhatsApp delivery needs review for outbound_id=%s", outbound_id)
        sent += 1
    return sent


async def drain_message_queue(store: PostgresMessageStore, engine: Any) -> None:
    """Deliver staged responses, then process pending messages in customer order."""
    if hasattr(store, "recover_stale_processing"):
        await store.recover_stale_processing()
    if hasattr(store, "recover_stale_outbound"):
        await store.recover_stale_outbound()
    await drain_outbound_queue(store)
    while True:

        claimed = await store.claim_next()
        if claimed is None:
            await drain_outbound_queue(store)
            return
        inbound_id, task_message = claimed

        # Debounce rapid burst typing from the same customer
        if hasattr(store, "absorb_subsequent_pending") and task_message.customer_id:
            try:
                bursts = await store.absorb_subsequent_pending(task_message.customer_id)
                for burst in bursts:
                    updates = {}
                    if burst.text.strip():
                        updates["text"] = f"{task_message.text}\n{burst.text}"
                    if not task_message.interactive_id and burst.interactive_id:
                        updates["interactive_id"] = burst.interactive_id
                    if updates:
                        task_message = task_message.model_copy(update=updates)
            except Exception:
                logger.warning("Could not absorb burst messages for inbound_id=%s", inbound_id)

        heartbeat = None
        claim_lost = False
        work_task: asyncio.Task[NormalizedOutgoingResponse] | None = None
        if hasattr(store, "heartbeat_processing"):
            async def keep_claim_alive() -> None:
                nonlocal claim_lost
                consecutive_errors = 0
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                    try:
                        updated = await store.heartbeat_processing(inbound_id)
                        consecutive_errors = 0
                        if updated == 0:
                            claim_lost = True
                            if work_task is not None and not work_task.done():
                                work_task.cancel()
                            break
                    except Exception as err:
                        consecutive_errors += 1
                        logger.warning(
                            "Heartbeat failed for inbound_id=%s (error %d/2): %s",
                            inbound_id, consecutive_errors, err,
                        )
                        if consecutive_errors >= 2:
                            claim_lost = True
                            if work_task is not None and not work_task.done():
                                work_task.cancel()
                            break
            heartbeat = asyncio.create_task(keep_claim_alive())
        try:
            if _DELETE_DATA_PATTERN.match(task_message.text.strip()):
                state_store = getattr(engine, "state_store", None)
                if state_store is None:
                    raise RuntimeError("Customer deletion requires durable task storage.")
                await store.request_deletion(task_message.customer_id)
                await state_store.delete(task_message.customer_id)
                try:
                    await default_token_vault.revoke_token_durable(task_message.customer_id)
                except Exception:
                    logger.debug("Token vault revocation skipped or pool unavailable during customer deletion.")
                await engine.forget_customer(task_message.customer_id)
                response = NormalizedOutgoingResponse(
                    recipient_id=task_message.sender_id, channel=ChannelType.WHATSAPP,
                    text=("Your shopping history and Swiggy connection have been deleted. "
                          "If an order outcome is still unresolved, its minimal record remains until it is resolved."),
                    conversation_state="READY", events=["DELETE_CUSTOMER_DATA"],
                )
            else:
                work_task = asyncio.create_task(engine.handle_message(task_message))
                response = await asyncio.wait_for(work_task, timeout=180)
            if claim_lost:
                return
            await store.stage_response(inbound_id, response)
            await drain_outbound_queue(store)
        except asyncio.CancelledError:
            if claim_lost:
                return
            raise
        except Exception:
            if claim_lost:
                return
            logger.exception("Agent turn needs review for inbound_id=%s", inbound_id)
            try:
                fallback_resp = NormalizedOutgoingResponse(
                    recipient_id=task_message.sender_id,
                    channel=task_message.channel,
                    text="I had trouble processing that grocery request. Could you please try again or rephrase?",
                    conversation_state="READY",
                )
                await store.stage_response(inbound_id, fallback_resp)
                await drain_outbound_queue(store)
            except Exception:
                try:
                    await store.mark_processing_failed(inbound_id)
                except Exception:
                    logger.exception("Failed to mark processing failed for inbound_id=%s", inbound_id)
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
            if work_task is not None and not work_task.done():
                work_task.cancel()
                try:
                    await work_task
                except (asyncio.CancelledError, Exception):
                    pass


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
    store = getattr(request.app.state, "message_store", None)
    if engine is None or store is None:
        raise HTTPException(status_code=503, detail="Durable message intake is unavailable.")

    durable_messages: list[NormalizedIncomingMessage] = []
    for incoming in incoming_messages:
        try:
            customer_id = default_whatsapp_adapter.map_sender_to_customer_id(incoming.sender_id)
        except ValueError:
            logger.info("Ignoring WhatsApp message with unsupported sender identity.")
            continue
        durable_messages.append(incoming.model_copy(update={"customer_id": customer_id}))
    try:
        processed_count = await store.enqueue_many(durable_messages)
    except Exception:
        logger.exception("Could not durably save WhatsApp messages before acknowledgement.")
        raise HTTPException(status_code=503, detail="Message intake failed.")
    if processed_count:
        background_tasks.add_task(drain_message_queue, store, engine)
        for incoming in durable_messages:
            asyncio.create_task(default_whatsapp_adapter.mark_message_read(incoming.message_id))
    return {"status": "ok", "processed": processed_count}
