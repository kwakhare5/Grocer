"""Layer 5 Tests: Response Delivery, Quick Buttons, Background Payment Poller & Media Ingestion."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.channels.payment_poller import PaymentPoller
from backend.channels.whatsapp import WhatsAppChannelAdapter, default_whatsapp_adapter
from backend.channels.whatsapp_formatter import (
    build_message_payloads,
    format_whatsapp_payload,
)
from backend.channels.whatsapp_media import (
    download_whatsapp_media,
    extract_groceries_from_media,
)
from backend.channels.whatsapp_parser import parse_webhook_payload
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import PaymentStatusResult


# ---------------------------------------------------------------------------
# 1. Receipt Formatters & Quick Action Buttons
# ---------------------------------------------------------------------------


def test_receipt_formatter_confirmation_buttons():
    """Verify receipt in AWAITING_CHECKOUT_CONFIRMATION formats max 3 quick-reply buttons."""
    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="🛒 *Your Basket*\n• 1x Milk — ₹30\n\n*Grand Total:* ₹30",
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[
            InteractiveAction(action_type="button", id="confirm_order:token123", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
    )
    payload = format_whatsapp_payload(resp)
    assert payload["type"] == "interactive"
    interactive = payload["interactive"]
    assert interactive["type"] == "button"
    assert len(interactive["action"]["buttons"]) == 2
    assert interactive["action"]["buttons"][0]["reply"]["id"] == "confirm_order:token123"
    assert interactive["action"]["buttons"][0]["reply"]["title"] == "Confirm Order"
    assert interactive["action"]["buttons"][1]["reply"]["id"] == "modify_cart"
    assert interactive["action"]["buttons"][1]["reply"]["title"] == "Change Items"


def test_receipt_formatter_payment_pending_buttons_and_upi():
    """Verify receipt in AWAITING_PAYMENT formats Check Payment and Change Items buttons."""
    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text=(
            "🛒 *Your order is ready for payment!*\n\n"
            "👉 *1-Tap UPI Link (Google Pay / PhonePe):*\n"
            "upi://pay?pa=swiggy@icici&pn=SwiggyInstamart&am=150.00&tr=OD-12345&cu=INR\n\n"
            "Tap *Check Payment* once paid, or *Change Items*."
        ),
        conversation_state="AWAITING_PAYMENT",
        interactive_actions=[
            InteractiveAction(action_type="button", id="check_payment:OD-12345", title="Check Payment"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
    )
    payload = format_whatsapp_payload(resp)
    assert payload["type"] == "interactive"
    interactive = payload["interactive"]
    assert interactive["type"] == "button"
    buttons = interactive["action"]["buttons"]
    assert len(buttons) == 2
    assert buttons[0]["reply"]["id"] == "check_payment:OD-12345"
    assert buttons[0]["reply"]["title"] == "Check Payment"
    assert "upi://pay?" in interactive["body"]["text"]


def test_long_receipt_chunking_never_truncates():
    """Verify build_message_payloads chunks long receipts without truncating items."""
    long_items = "\n".join(f"• 1x Grocery Item #{i} — ₹50" for i in range(1, 40))
    long_receipt = f"🛒 *Your Basket*\n{long_items}\n\n*Grand Total:* ₹1950"
    assert len(long_receipt) > 1024

    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text=long_receipt,
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[
            InteractiveAction(action_type="button", id="confirm_order:token123", title="Confirm Order"),
            InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
        ],
    )
    payloads = build_message_payloads(resp)
    assert len(payloads) >= 2
    # First payload is full un-truncated text
    assert payloads[0]["type"] == "text"
    assert "• 1x Grocery Item #1" in payloads[0]["text"]["body"]
    # Final payload contains the interactive buttons
    final_payload = payloads[-1]
    assert final_payload["type"] == "interactive"
    assert final_payload["interactive"]["type"] == "button"
    assert len(final_payload["interactive"]["action"]["buttons"]) == 2


# ---------------------------------------------------------------------------
# 2. Outbound Worker & Delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outbound_delivery_record_only_mode():
    """Verify adapter in record_only mode records outbound messages safely."""
    adapter = WhatsAppChannelAdapter(record_only=True)
    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="Hello from GROCER!",
        conversation_state="READY",
    )
    success = await adapter.send_response(resp)
    assert success is True
    assert len(adapter.outbound_messages) == 1
    assert adapter.outbound_messages[0]["text"]["body"] == "Hello from GROCER!"


@pytest.mark.asyncio
async def test_outbound_delivery_silent_test_recipient():
    """Verify recipients ending in _test or _silent bypass Meta network calls."""
    adapter = WhatsAppChannelAdapter(record_only=False, access_token="mock_token", phone_number_id="12345")
    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210_test",
        channel=ChannelType.WHATSAPP,
        text="Silent test message",
        conversation_state="READY",
    )
    success = await adapter.send_response(resp)
    assert success is True
    assert len(adapter.outbound_messages) == 1


# ---------------------------------------------------------------------------
# 3. Background Payment Poller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_poller_confirms_success():
    """Verify payment poller detects terminal success, updates state, and sends receipt."""
    commerce = MockCommerceAdapter()
    poller = PaymentPoller(commerce=commerce, interval_seconds=1, max_poll_seconds=5)

    # Mock check_payment_status to return confirmed on first check
    async def mock_check_status(paas_id: str, order_id: str | None = None):
        return PaymentStatusResult(
            paas_id=paas_id,
            order_id=order_id,
            normalized_status="PAYMENT_CONFIRMED",
            is_terminal_success=True,
            confirmed=True,
        )

    commerce.check_payment_status = mock_check_status

    task = poller.start_polling(
        customer_id="cust-test-1",
        order_id="OD-9901",
        paas_id="paas-9901",
        recipient_id="919876543210_test",
        custom_interval=1,
        custom_max_duration=3,
    )
    result = await task
    assert result is True


@pytest.mark.asyncio
async def test_payment_poller_handles_terminal_failure():
    """Verify payment poller detects failure and notifies user with retry button."""
    commerce = MockCommerceAdapter()
    poller = PaymentPoller(commerce=commerce, interval_seconds=1, max_poll_seconds=5)

    async def mock_check_status(paas_id: str, order_id: str | None = None):
        return PaymentStatusResult(
            paas_id=paas_id,
            order_id=order_id,
            normalized_status="PAYMENT_FAILED",
            is_terminal_failure=True,
        )

    commerce.check_payment_status = mock_check_status

    task = poller.start_polling(
        customer_id="cust-test-2",
        order_id="OD-9902",
        paas_id="paas-9902",
        recipient_id="919876543210_test",
        custom_interval=1,
        custom_max_duration=3,
    )
    result = await task
    assert result is False


@pytest.mark.asyncio
async def test_payment_poller_on_demand_check():
    """Verify on-demand check triggered by user tapping 'Check Payment'."""
    commerce = MockCommerceAdapter()
    poller = PaymentPoller(commerce=commerce)

    async def mock_check_status(paas_id: str, order_id: str | None = None):
        return PaymentStatusResult(
            paas_id=paas_id,
            order_id=order_id,
            normalized_status="PAYMENT_CONFIRMED",
            is_terminal_success=True,
        )

    commerce.check_payment_status = mock_check_status

    out_resp = await poller.check_on_demand(
        customer_id="cust-test-3",
        order_id="OD-9903",
        recipient_id="919876543210_test",
    )
    assert out_resp.conversation_state == "ORDER_PLACED"
    assert "Payment Verified!" in out_resp.text
    assert "OD-9903" in out_resp.text


# ---------------------------------------------------------------------------
# 4. Audio Voice Notes & Photo Ingestion
# ---------------------------------------------------------------------------


def test_parse_webhook_audio_and_image():
    """Verify Meta webhook payload parser extracts media_id, type, and caption."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.audio1",
                                    "type": "audio",
                                    "audio": {
                                        "id": "media-audio-123",
                                        "mime_type": "audio/ogg; codecs=opus",
                                    },
                                },
                                {
                                    "from": "919876543210",
                                    "id": "wamid.img1",
                                    "type": "image",
                                    "image": {
                                        "id": "media-img-456",
                                        "mime_type": "image/jpeg",
                                        "caption": "Weekly groceries",
                                    },
                                },
                            ]
                        }
                    }
                ]
            }
        ],
    }
    msgs = parse_webhook_payload(payload)
    assert len(msgs) == 2

    audio_msg = msgs[0]
    assert audio_msg.media_type == "audio"
    assert audio_msg.media_id == "media-audio-123"
    assert audio_msg.media_mime_type == "audio/ogg; codecs=opus"

    img_msg = msgs[1]
    assert img_msg.media_type == "image"
    assert img_msg.media_id == "media-img-456"
    assert img_msg.media_caption == "Weekly groceries"
    assert "Weekly groceries" in img_msg.text


@pytest.mark.asyncio
async def test_extract_groceries_from_media_multimodal():
    """Verify extract_groceries_from_media parses shopping items with Gemini."""
    mock_gemini = MagicMock()
    mock_gemini.generate_content = AsyncMock(
        return_value={
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Please add: 2 packets toned milk, 1 loaf brown bread"}]
                    }
                }
            ]
        }
    )
    result = await extract_groceries_from_media(
        gemini_client=mock_gemini,
        media_bytes=b"fake-image-bytes",
        mime_type="image/jpeg",
        media_type="image",
        caption="Breakfast list",
    )
    assert "2 packets toned milk" in result
    assert "1 loaf brown bread" in result


@pytest.mark.asyncio
async def test_extract_groceries_unclear_media_fallback():
    """Verify extract_groceries_from_media returns NO_GROCERIES_FOUND on blank image."""
    mock_gemini = MagicMock()
    mock_gemini.generate_content = AsyncMock(
        return_value={
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "NO_GROCERIES_FOUND"}]
                    }
                }
            ]
        }
    )
    result = await extract_groceries_from_media(
        gemini_client=mock_gemini,
        media_bytes=b"fake-blank-bytes",
        mime_type="image/jpeg",
        media_type="image",
    )
    assert result == "NO_GROCERIES_FOUND"


# ---------------------------------------------------------------------------
# 5. Live Production Integration Tests (Real Gemini, Real Swiggy MCP, Real Supabase)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_gemini_35_models():
    """Verify live Google Gemini 3.5 Flash and Flash-Lite API calls using configured key."""
    from backend.agent.gemini import GeminiClient
    from backend.config import settings

    if not settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY not configured")

    client = GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        primary_model="gemini-3.5-flash",
        fallback_model="gemini-3.5-flash-lite",
    )
    try:
        res = None
        for _ in range(3):
            res = await client.generate_content(
                contents=[{"role": "user", "parts": [{"text": "Extract items as comma-separated: 'Do packet Amul milk aur ek white bread chahiye'"}]}],
                system_text="You are a grocery extractor. Return clean items.",
                temperature=0.1,
            )
            if res is not None:
                break
            await asyncio.sleep(1.0)
        assert res is not None
        candidates = res.get("candidates", [])
        assert len(candidates) >= 1
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        assert "milk" in text.casefold() or "bread" in text.casefold()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_live_supabase_token_vault_and_addresses():
    """Verify live Supabase connection and real Swiggy Instamart dark store saved addresses."""
    from backend.config import settings
    from backend.integrations.commerce.token_vault import default_token_vault
    from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
    import asyncpg

    if not settings.DATABASE_URL or not settings.DATA_ENCRYPTION_KEY:
        pytest.skip("DATABASE_URL or DATA_ENCRYPTION_KEY not configured")

    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
    try:
        await default_token_vault.configure_postgres(pool, settings.DATA_ENCRYPTION_KEY)
        tok = await default_token_vault.get_token_durable("cust_c23625efe2658a26")
        if not tok and settings.SWIGGY_AUTH_TOKEN:
            await default_token_vault.store_token_durable("cust_c23625efe2658a26", settings.SWIGGY_AUTH_TOKEN, expires_in=86400 * 30)
            tok = settings.SWIGGY_AUTH_TOKEN
        assert tok is not None and len(tok) > 100

        adapter = SwiggyMCPAdapter(auth_token=tok, token_resolver=default_token_vault.get_token_durable)
        with adapter.customer_scope("cust_c23625efe2658a26"):
            addresses = await adapter.get_addresses("cust_c23625efe2658a26")
            assert len(addresses) >= 1
            # Verify Real Address Grounding
            addr = addresses[0]
            assert addr is not None, "Customer saved addresses must be present"
            assert addr.id is not None
    finally:
        await pool.close()

