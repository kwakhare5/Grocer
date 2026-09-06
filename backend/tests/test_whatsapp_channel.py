"""Comprehensive tests for WhatsApp Channel Adapter and Webhook API (Phase C & D)."""
from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from httpx import ASGITransport, AsyncClient

from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.main import app


@pytest.fixture
def whatsapp_adapter() -> WhatsAppChannelAdapter:
    return WhatsAppChannelAdapter(
        verify_token="test_token_123",
        app_secret="test_app_secret_xyz",
    )


# ---------------------------------------------------------------------------
# 1. Webhook Verification (GET)
# ---------------------------------------------------------------------------

def test_webhook_challenge_success(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    valid, challenge = whatsapp_adapter.verify_webhook_challenge(
        mode="subscribe",
        token="test_token_123",
        challenge="1158201444",
    )
    assert valid is True
    assert challenge == "1158201444"


def test_webhook_challenge_invalid_token(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    valid, _ = whatsapp_adapter.verify_webhook_challenge(
        mode="subscribe",
        token="wrong_token",
        challenge="1158201444",
    )
    assert valid is False


# ---------------------------------------------------------------------------
# 2. HMAC-SHA256 Signature Verification (POST)
# ---------------------------------------------------------------------------

def test_signature_verification(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    payload = b'{"object":"whatsapp_business_account"}'
    sig = hmac.new(b"test_app_secret_xyz", payload, hashlib.sha256).hexdigest()
    header = f"sha256={sig}"

    assert whatsapp_adapter.verify_signature(payload, header) is True
    assert whatsapp_adapter.verify_signature(payload, "sha256=invalid_sig") is False
    assert whatsapp_adapter.verify_signature(payload, None) is False


# ---------------------------------------------------------------------------
# 3. Payload Parsing & Deduplication
# ---------------------------------------------------------------------------

def test_parse_text_and_interactive_messages(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.msg1",
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": "get my usual groceries"},
                                },
                                {
                                    "id": "wamid.msg2",
                                    "from": "919876543210",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {"id": "choice:SPIN-MILK-500ML", "title": "Amul 500ml"},
                                    },
                                },
                            ]
                        }
                    }
                ]
            }
        ],
    }

    messages = whatsapp_adapter.parse_webhook_payload(payload)
    assert len(messages) == 2
    assert messages[0].sender_id == "919876543210"
    assert messages[0].text == "get my usual groceries"
    assert messages[0].message_id == "wamid.msg1"

    assert messages[1].interactive_type == "list_reply"
    assert messages[1].interactive_id == "choice:SPIN-MILK-500ML"
    assert messages[1].text == "Amul 500ml"

    # Deduplication test: re-parsing same payload yields 0 messages
    dup_messages = whatsapp_adapter.parse_webhook_payload(payload)
    assert len(dup_messages) == 0


# ---------------------------------------------------------------------------
# 4. Identity Mapping and Session Continuity
# ---------------------------------------------------------------------------

def test_identity_mapping_and_session_continuity(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    sender = "+91 98765-43210"
    customer_id = whatsapp_adapter.map_sender_to_customer_id(sender)
    assert customer_id == "cust_wa_919876543210"

    # Verify session ID is stable across multiple turns
    sess1 = whatsapp_adapter.get_or_create_session_id(customer_id)
    sess2 = whatsapp_adapter.get_or_create_session_id(customer_id)
    assert sess1 == sess2


# ---------------------------------------------------------------------------
# 5. Outbound Message Formatting
# ---------------------------------------------------------------------------

def test_outbound_whatsapp_formatting(whatsapp_adapter: WhatsAppChannelAdapter) -> None:
    from backend.channels.models import InteractiveAction, NormalizedOutgoingResponse

    # List formatting
    decision_resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="Milk is out of stock. Choose alternative:",
        conversation_state="NEEDS_DECISION",
        interactive_actions=[
            InteractiveAction(action_type="list_item", id="choice:SPIN-1", title="Mother Dairy 1L", description="₹62"),
            InteractiveAction(action_type="list_item", id="choice:SPIN-2", title="Amul 500ml", description="₹34"),
        ],
    )
    formatted = whatsapp_adapter.format_whatsapp_payload(decision_resp)
    assert formatted["type"] == "interactive"
    assert formatted["interactive"]["type"] == "list"
    assert len(formatted["interactive"]["action"]["sections"][0]["rows"]) == 2

    # Button formatting for confirmation
    confirm_resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="Your basket is ₹120. Confirm checkout?",
        conversation_state="AWAITING_CONFIRMATION",
        interactive_actions=[
            InteractiveAction(action_type="button", id="confirm_checkout", title="Confirm Order"),
        ],
    )
    btn_formatted = whatsapp_adapter.format_whatsapp_payload(confirm_resp)
    assert btn_formatted["type"] == "interactive"
    assert btn_formatted["interactive"]["type"] == "button"
    assert btn_formatted["interactive"]["action"]["buttons"][0]["reply"]["id"] == "confirm_checkout"


# ---------------------------------------------------------------------------
# 6. End-to-End Webhook API Routes via FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_whatsapp_webhook_get_verification() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Success verification
        res = await client.get(
            "/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=grocer_whatsapp_verify_token&hub.challenge=test_challenge_code"
        )
        assert res.status_code == 200
        assert res.text == "test_challenge_code"

        # Invalid token
        res_bad = await client.get(
            "/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=bad_token&hub.challenge=test_challenge_code"
        )
        assert res_bad.status_code == 403


@pytest.mark.asyncio
async def test_api_whatsapp_webhook_post_flow() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.e2e.test.1",
                                        "from": "919999988888",
                                        "type": "text",
                                        "text": {"body": "get 1L milk and bread"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ],
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        # In test mode without secret configured on default_whatsapp_adapter, it accepts or checks secret
        res = await client.post(
            "/api/whatsapp/webhook",
            content=body_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1
