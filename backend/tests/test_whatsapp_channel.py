"""Tests for the active Meta WhatsApp transport and durable task webhook."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedOutgoingResponse,
)
from backend.channels.whatsapp import WhatsAppChannelAdapter, default_whatsapp_adapter
from backend.main import app


@pytest.fixture
def whatsapp_adapter() -> WhatsAppChannelAdapter:
    return WhatsAppChannelAdapter(
        verify_token="test_token_123",
        app_secret="test_app_secret_xyz",
        record_only=True,
    )


def test_webhook_challenge_and_signature(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    valid, challenge = whatsapp_adapter.verify_webhook_challenge(
        mode="subscribe", token="test_token_123", challenge="challenge"
    )
    assert valid is True
    assert challenge == "challenge"

    payload = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(b"test_app_secret_xyz", payload, hashlib.sha256).hexdigest()
    assert whatsapp_adapter.verify_signature(payload, f"sha256={digest}") is True
    assert whatsapp_adapter.verify_signature(payload, "sha256=bad") is False


def test_reservation_is_atomic_and_retryable(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    assert whatsapp_adapter.reserve_message("wamid.one") is True
    assert whatsapp_adapter.reserve_message("wamid.one") is False
    whatsapp_adapter.release_message("wamid.one")
    assert whatsapp_adapter.reserve_message("wamid.one") is True
    whatsapp_adapter.mark_processed("wamid.one")
    assert whatsapp_adapter.reserve_message("wamid.one") is False


def test_parse_text_and_interactive_messages(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [
            {
                "id": "wamid.text",
                "from": "919876543210",
                "type": "text",
                "text": {"body": "need milk"},
            },
            {
                "id": "wamid.choice",
                "from": "919876543210",
                "type": "interactive",
                "interactive": {
                    "type": "list_reply",
                    "list_reply": {"id": "choice:milk", "title": "Milk"},
                },
            },
        ]}}]}],
    }
    messages = whatsapp_adapter.parse_webhook_payload(payload)
    assert [message.message_id for message in messages] == ["wamid.text", "wamid.choice"]
    assert messages[0].text == "need milk"
    assert messages[1].interactive_id == "choice:milk"


def test_outbound_formatting_uses_buttons_and_lists(
    whatsapp_adapter: WhatsAppChannelAdapter,
) -> None:
    response = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="Choose a product.",
        conversation_state="NEEDS_PRODUCT_CHOICE",
        interactive_actions=[
            InteractiveAction(id="one", title="Milk 1L", description="₹66"),
            InteractiveAction(id="two", title="Milk 500ml", description="₹34"),
            InteractiveAction(id="three", title="Milk 250ml", description="₹20"),
            InteractiveAction(id="four", title="Milk 2L", description="₹120"),
        ],
    )
    formatted = whatsapp_adapter.format_whatsapp_payload(response)
    assert formatted["type"] == "interactive"
    assert formatted["interactive"]["type"] == "list"


@pytest.mark.asyncio
async def test_signed_webhook_reaches_active_task_service(monkeypatch) -> None:
    class FakeAgentEngine:
        def __init__(self) -> None:
            self.processed: list[str] = []

        async def handle_message(self, message):  # type: ignore[no-untyped-def]
            self.processed.append(message.message_id)
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=ChannelType.WHATSAPP,
                text="Received.",
                conversation_state="READY",
            )

    engine = FakeAgentEngine()
    monkeypatch.setattr(app.state, "agent_engine", engine, raising=False)
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "webhook-secret")
    default_whatsapp_adapter.outbound_messages.clear()

    message_id = f"wamid.{uuid.uuid4()}"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{
            "id": message_id,
            "from": "919999988888",
            "type": "text",
            "text": {"body": "hi"},
        }]}}]}],
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={signature}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        replay = await client.post("/api/whatsapp/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert engine.processed == [message_id, message_id]
    assert len(default_whatsapp_adapter.outbound_messages) == 2
