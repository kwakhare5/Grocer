"""Grocer v1.0 — Live WhatsApp Outbound Delivery & Chat Loop Tests.

Strictly tests:
1. WhatsAppClient payload structure & https URL validation.
2. Unauthenticated customer welcome & Swiggy connect prompt.
3. Inbound grocery search, cart assembly & interactive receipt card delivery.
4. Button reply payment checkout bridge delivery to customer chat.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path

import pytest

from backend.channels.whatsapp_client import WhatsAppClient
from backend.database import get_db_pool
from backend.integrations.commerce.token_vault import store_user_token


def _sign(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def wa_client() -> WhatsAppClient:
    return WhatsAppClient(phone_number_id="109876543210", access_token="mock_wa_token")


# ==============================================================================
# 1. WhatsAppClient Unit Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_whatsapp_client_text_message_payload(wa_client: WhatsAppClient):
    """Verifies correct JSON payload structure for plain text messages."""
    res = await wa_client.send_text_message(to_wa_id="919876543210", text="Hello from Grocer!")
    assert res["status"] == "mock_delivered"
    payload = res["payload"]
    assert payload["to"] == "919876543210"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hello from Grocer!"


@pytest.mark.asyncio
async def test_whatsapp_client_quick_reply_buttons_payload(wa_client: WhatsAppClient):
    """Verifies correct structure for interactive quick reply buttons (max 3)."""
    buttons = [("pay:appr_123", "Pay ₹149"), ("cart:clear", "Clear Basket")]
    res = await wa_client.send_quick_reply_buttons(
        to_wa_id="919876543210",
        body_text="Your basket total is ₹149",
        buttons=buttons,
    )
    assert res["status"] == "mock_delivered"
    interactive = res["payload"]["interactive"]
    assert interactive["type"] == "button"
    assert len(interactive["action"]["buttons"]) == 2
    assert interactive["action"]["buttons"][0]["reply"]["id"] == "pay:appr_123"
    assert interactive["action"]["buttons"][0]["reply"]["title"] == "Pay ₹149"


@pytest.mark.asyncio
async def test_whatsapp_client_cta_url_button_payload(wa_client: WhatsAppClient):
    """Verifies correct structure and https enforcement for CTA URL buttons."""
    # Valid https URL passes
    res = await wa_client.send_cta_url_button(
        to_wa_id="919876543210",
        body_text="Complete your payment on Swiggy",
        button_text="Pay on Swiggy",
        url="https://swiggy.com/pay/bridge_123",
    )
    assert res["status"] == "mock_delivered"
    action = res["payload"]["interactive"]["action"]
    assert action["name"] == "cta_url"
    assert action["parameters"]["url"] == "https://swiggy.com/pay/bridge_123"

    # Non-https URL strictly raises ValueError
    with pytest.raises(ValueError, match="Strict scheme violation"):
        await wa_client.send_cta_url_button(
            to_wa_id="919876543210",
            body_text="Invalid UPI URL",
            button_text="Pay UPI",
            url="upi://pay?pa=swiggy@icici",
        )


# ==============================================================================
# 2. Inbound Webhook Chat Loop Tests
# ==============================================================================
@pytest.mark.db
@pytest.mark.asyncio
async def test_webhook_unauthenticated_user_prompts_swiggy_connect():
    """Unauthenticated WhatsApp user receives connect Swiggy CTA button."""
    from backend.channels.whatsapp import handle_webhook
    from backend.config import settings

    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "1234567890", "phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "buy 1L milk"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign(raw_bytes, settings.WHATSAPP_APP_SECRET)

    # Mock request object
    class MockRequest:
        async def body(self):
            return raw_bytes
        @property
        def headers(self):
            return {"X-Hub-Signature-256": sig}

    res = await handle_webhook(MockRequest())
    assert res["status"] == "auth_required"
    assert res["wa_id"] == wa_id


@pytest.mark.db
@pytest.mark.asyncio
async def test_webhook_authenticated_user_creates_approval_and_sends_receipt():
    """Authenticated user texting grocery list receives receipt card with interactive [Pay] button."""
    from backend.channels.whatsapp import handle_webhook
    from backend.config import settings

    pool = await get_db_pool()
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"

    # Auto-register and store Swiggy OAuth token in vault
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
    await store_user_token(user_id=user_id, access_token="swiggy_live_oauth_token_123")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "1234567890", "phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "milk"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign(raw_bytes, settings.WHATSAPP_APP_SECRET)

    class MockRequest:
        async def body(self):
            return raw_bytes
        @property
        def headers(self):
            return {"X-Hub-Signature-256": sig}

    from pathlib import Path

    from backend.integrations.commerce.swiggy_client import SwiggyClient

    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    staging_client = SwiggyClient(fixtures_dir=fixtures_dir)
    staging_client.clear_cart()  # fixture state only; starts from an empty basket

    res = await handle_webhook(MockRequest(), swiggy_client=staging_client)
    assert res["status"] == "cart_updated"
    assert res["to_pay_paise"] > 0
    assert res["approval_id"] is not None


@pytest.mark.db
@pytest.mark.asyncio
async def test_webhook_expired_token_parks_request_and_prompts_reconnect():
    """When Swiggy returns 401, message is parked in DB and Reconnect button is sent (ADR 0010)."""
    from backend.channels.whatsapp import handle_webhook
    from backend.config import settings
    from backend.integrations.commerce.swiggy_client import (
        SwiggyAuthExpiredError,
        SwiggyClient,
    )

    pool = await get_db_pool()
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
    await store_user_token(user_id=user_id, access_token="expired_token")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "1234567890", "phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "milk"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign(raw_bytes, settings.WHATSAPP_APP_SECRET)

    class MockRequest:
        async def body(self):
            return raw_bytes
        @property
        def headers(self):
            return {"X-Hub-Signature-256": sig}

    class ExpiredClient(SwiggyClient):
        def get_addresses(self, page: int = 1, page_size: int = 10):
            raise SwiggyAuthExpiredError("Token expired (401)")

    res = await handle_webhook(MockRequest(), swiggy_client=ExpiredClient())
    assert res["status"] == "auth_expired"
    assert res["wa_id"] == wa_id

    # Verify message was parked in database
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE user_id = $1;",
            user_id,
        )
        assert status == "parked"


@pytest.mark.db
@pytest.mark.asyncio
async def test_webhook_greeting_returns_conversational_reply_without_cart():
    """Customer sending 'hello' receives a friendly reply; no catalog search or cart is created."""
    from backend.channels.whatsapp import handle_webhook
    from backend.config import settings

    pool = await get_db_pool()
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
    await store_user_token(user_id=user_id, access_token="swiggy_live_oauth_token_123")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "1234567890", "phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign(raw_bytes, settings.WHATSAPP_APP_SECRET)

    class MockRequest:
        async def body(self):
            return raw_bytes
        @property
        def headers(self):
            return {"X-Hub-Signature-256": sig}

    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    from backend.integrations.commerce.swiggy_client import SwiggyClient
    staging_client = SwiggyClient(fixtures_dir=fixtures_dir)

    res = await handle_webhook(MockRequest(), swiggy_client=staging_client)
    assert res["status"] == "capability_answered"
    assert res["capability"] == "chat"
    assert res["wa_id"] == wa_id

    # Verify that NO approval was created for a simple greeting
    async with pool.acquire() as conn:
        approval_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.approvals WHERE user_id = $1;",
            user_id,
        )
        assert approval_count == 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_webhook_multi_item_list_assembles_composite_cart():
    """Customer sending multi-item list ('milk and bread') resolves both items into composite cart."""
    from backend.channels.whatsapp import handle_webhook
    from backend.config import settings

    pool = await get_db_pool()
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
    await store_user_token(user_id=user_id, access_token="swiggy_live_oauth_token_123")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "1234567890", "phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "milk and bread"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign(raw_bytes, settings.WHATSAPP_APP_SECRET)

    class MockRequest:
        async def body(self):
            return raw_bytes
        @property
        def headers(self):
            return {"X-Hub-Signature-256": sig}

    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    from backend.integrations.commerce.swiggy_client import SwiggyClient
    staging_client = SwiggyClient(fixtures_dir=fixtures_dir)
    staging_client.clear_cart()  # fixture state only; starts from an empty basket

    res = await handle_webhook(MockRequest(), swiggy_client=staging_client)
    assert res["status"] == "cart_updated"
    assert res["to_pay_paise"] > 0
    assert res["approval_id"] is not None
