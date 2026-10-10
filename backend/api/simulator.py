"""Private local chat console that drives the signed WhatsApp webhook path."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict, Field

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


class SimulatorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4096)
    interactive_id: str | None = Field(default=None, max_length=200)


def _authorize(request: Request) -> None:
    if request.client is None or request.client.host not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        raise HTTPException(status_code=403, detail="Simulator is available only on localhost.")
    provided = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.SIMULATOR_ACCESS_TOKEN}"
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Simulator access token required.")


def _customer_id() -> str:
    sender = settings.SIMULATOR_SENDER_ID
    if not sender or not sender.isdecimal() or not default_whatsapp_adapter.app_secret:
        raise HTTPException(status_code=503, detail="Simulator sender or webhook secret is unavailable.")
    return default_whatsapp_adapter.map_sender_to_customer_id(sender)


@router.post("/chat")
async def simulator_chat(message: SimulatorMessage, request: Request) -> dict:
    _authorize(request)
    customer_id = _customer_id()
    store = getattr(request.app.state, "message_store", None)
    engine = getattr(request.app.state, "agent_engine", None)
    if store is None or engine is None or not default_whatsapp_adapter.record_only:
        raise HTTPException(status_code=503, detail="Local WhatsApp test transport is unavailable.")

    message_id = f"sim.{uuid.uuid4().hex}"
    incoming: dict = {"id": message_id, "from": settings.SIMULATOR_SENDER_ID}
    if message.interactive_id:
        incoming["type"] = "interactive"
        incoming["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": message.interactive_id, "title": message.text},
        }
    else:
        incoming["type"] = "text"
        incoming["text"] = {"body": message.text}
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{
        "changes": [{"value": {"messages": [incoming]}}],
    }]}).encode()
    signature = hmac.new(default_whatsapp_adapter.app_secret.encode(), body, hashlib.sha256).hexdigest()
    async with AsyncClient(transport=ASGITransport(app=request.app), base_url="http://127.0.0.1") as client:
        intake = await client.post(
            "/api/whatsapp/webhook", content=body,
            headers={"X-Hub-Signature-256": f"sha256={signature}"},
        )
    if intake.status_code != 200:
        raise HTTPException(status_code=503, detail="Signed WhatsApp intake failed.")

    import asyncio
    staged = None
    for _ in range(30):
        staged = await store.response_for_message(message_id)
        if staged is not None:
            break
        await asyncio.sleep(0.5)

    if staged is None:
        raise HTTPException(status_code=503, detail="No durable response was staged.")
    delivery_status, response = staged
    if delivery_status != "SENT":
        raise HTTPException(status_code=503, detail="The response needs delivery review.")
    with engine.commerce.customer_scope(customer_id):
        try:
            cart = await engine.commerce.get_cart()
            cart_summary = {
                "items": [item.model_dump(mode="json") for item in cart.items],
                "grand_total": cart.grand_total,
                "address_id": cart.address_id,
                "billing_complete": cart.billing_complete,
            }
        except Exception:
            cart_summary = None
    return {
        "message_id": message_id,
        "text": response.text,
        "conversation_state": response.conversation_state,
        "interactive_actions": [action.model_dump(mode="json") for action in response.interactive_actions],
        "meta_payloads": default_whatsapp_adapter.build_message_payloads(response),
        "delivery_status": delivery_status,
        "cart": cart_summary,
        "commerce_mode": settings.COMMERCE_ADAPTER_TYPE,
        "latency_ms": engine.last_turn_latency_ms,
    }


@router.get("/state")
async def simulator_state(request: Request) -> dict:
    _authorize(request)
    customer_id = _customer_id()
    engine = getattr(request.app.state, "agent_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Agent is unavailable.")
    with engine.commerce.customer_scope(customer_id):
        try:
            cart = await engine.commerce.get_cart()
            cart_summary = {
                "items": [item.model_dump(mode="json") for item in cart.items],
                "grand_total": cart.grand_total,
                "address_id": cart.address_id,
                "billing_complete": cart.billing_complete,
            }
        except Exception:
            cart_summary = None
    return {"commerce_mode": settings.COMMERCE_ADAPTER_TYPE, "cart": cart_summary}
