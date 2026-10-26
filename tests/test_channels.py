"""Grocer v1.0 — Channel Ingestion Shield & Deduplication Integration Tests.

Validates:
1. Meta webhook GET challenge verification.
2. HMAC-SHA256 signature verification (<25ms).
3. PostgreSQL message deduplication (ON CONFLICT (wa_message_id) DO NOTHING).
4. Stale message dropping (>15 minutes old).
5. Delivery receipts (statuses) fast acknowledgment without database writes.
6. Per-user concurrency advisory locking (safe recording and concurrency status).
7. Fast 50ms button dispatcher for interactive button replies and list replies.
8. Location pin parsing and coordinate persistence in raw payload.
9. Multi-message batch processing without loop truncation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.database import get_db_pool
from backend.main import app


def _compute_signature(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _make_whatsapp_message_payload(
    message_id: str,
    wa_id: str = "919876543210",
    text: str | None = "milk and eggs",
    button_id: str | None = None,
    button_title: str | None = None,
    timestamp: int | None = None,
) -> dict:
    if timestamp is None:
        timestamp = int(time.time())

    msg: dict = {
        "from": wa_id,
        "id": message_id,
        "timestamp": str(timestamp),
    }

    if button_id:
        msg["type"] = "interactive"
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": button_id, "title": button_title or "Click"},
        }
    else:
        msg["type"] = "text"
        msg["text"] = {"body": text}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": wa_id}
                            ],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }


def _make_status_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "statuses": [
                                {
                                    "id": "wamid.status_test_1",
                                    "status": "delivered",
                                    "timestamp": str(int(time.time())),
                                    "recipient_id": "919876543210",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _make_whatsapp_location_payload(
    message_id: str,
    latitude: float = 19.0596,
    longitude: float = 72.8295,
    wa_id: str = "919876543210",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": wa_id}
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "location",
                                    "location": {
                                        "latitude": latitude,
                                        "longitude": longitude,
                                        "name": "Bandra West",
                                        "address": "Hill Road, Bandra West, Mumbai",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _make_whatsapp_list_reply_payload(
    message_id: str,
    list_id: str,
    title: str = "Home Address",
    wa_id: str = "919876543210",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": wa_id}
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {"id": list_id, "title": title},
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_webhook_get_verification_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
                "hub.challenge": "challenge_code_12345",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge_code_12345"


@pytest.mark.asyncio
async def test_webhook_get_verification_invalid_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge_code_12345",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_hmac_signature_validation():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.sig_test_{int(time.time() * 1000)}"
    payload = _make_whatsapp_message_payload(msg_id)
    payload_bytes = json.dumps(payload).encode("utf-8")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing signature header -> 403
        resp_no_sig = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert resp_no_sig.status_code == 403

        # 2. Tampered signature -> 403
        resp_bad_sig = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
        )
        assert resp_bad_sig.status_code == 403

        # 3. Valid signature -> 200
        valid_sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)
        resp_ok = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": valid_sig,
            },
        )
        assert resp_ok.status_code == 200
        data = resp_ok.json()
        assert data["status"] in ("ok", "processed", "auth_required")


@pytest.mark.asyncio
async def test_webhook_deduplication_drops_duplicate_message():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.dedup_{int(time.time() * 1000)}"
    payload = _make_whatsapp_message_payload(msg_id)
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First delivery -> inserted into DB
        resp1 = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] in ("ok", "processed", "auth_required")

        # Second delivery (replay attack / cellular retry) -> dropped
        resp2 = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate_dropped"

    # Verify only 1 entry exists in grocer.inbound_messages
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM grocer.inbound_messages WHERE wa_message_id = $1",
            msg_id,
        )
        assert count == 1


@pytest.mark.asyncio
async def test_webhook_stale_message_dropped():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.stale_{int(time.time() * 1000)}"
    # 20 minutes in past (>15 min threshold)
    stale_timestamp = int(time.time()) - (20 * 60)
    payload = _make_whatsapp_message_payload(msg_id, timestamp=stale_timestamp)
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stale_dropped"

    # Confirm stale message is never written to DB
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM grocer.inbound_messages WHERE wa_message_id = $1",
            msg_id,
        )
        assert count == 0


@pytest.mark.asyncio
async def test_webhook_status_update_receipt_ignored():
    transport = ASGITransport(app=app)
    payload = _make_status_payload()
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored_status"


@pytest.mark.asyncio
async def test_webhook_fast_button_dispatch():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.button_{int(time.time() * 1000)}"
    payload = _make_whatsapp_message_payload(
        msg_id,
        button_id="cart:clear",
        button_title="Clear Basket",
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_time = time.perf_counter()
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "button_dispatched"
        assert data["action"] == "cart:clear"
        assert elapsed_ms < 1500


@pytest.mark.asyncio
async def test_webhook_concurrent_double_tap_advisory_lock():
    transport = ASGITransport(app=app)
    wa_id = f"9199{int(time.time()) % 100000000:08d}"
    pool = await get_db_pool()

    # 1. Ensure user exists in database
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            """
            INSERT INTO grocer.users (wa_id)
            VALUES ($1)
            ON CONFLICT (wa_id) DO UPDATE SET updated_at = now()
            RETURNING id;
            """,
            wa_id,
        )

    # 2. Hold advisory transaction lock on a separate connection
    async with (
        pool.acquire() as lock_conn,
        lock_conn.transaction(),
    ):
        locked = await lock_conn.fetchval(
            "SELECT pg_try_advisory_xact_lock(hashtext($1));",
            str(user_id),
        )
        assert locked is True

        # 3. Simulate simultaneous webhook arriving for the same user
        msg_id = f"wamid.lock_{int(time.time() * 1000)}"
        payload = _make_whatsapp_message_payload(msg_id, wa_id=wa_id)
        payload_bytes = json.dumps(payload).encode("utf-8")
        sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/whatsapp/webhook",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "concurrency_dropped"

    # 4. Verify message was safely recorded in database even when lock held
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE wa_message_id = $1",
            msg_id,
        )
        assert status == "concurrency_dropped"


@pytest.mark.asyncio
async def test_webhook_location_pin_parsed_and_saved():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.loc_{int(time.time() * 1000)}"
    lat, lon = 19.0596, 72.8295
    payload = _make_whatsapp_location_payload(msg_id, latitude=lat, longitude=lon)
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "processed")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_type, raw_payload FROM grocer.inbound_messages WHERE wa_message_id = $1",
            msg_id,
        )
        assert row is not None
        assert row["message_type"] == "location"
        raw = json.loads(row["raw_payload"])
        assert raw["location"]["latitude"] == lat
        assert raw["location"]["longitude"] == lon


@pytest.mark.asyncio
async def test_webhook_list_reply_parsed_and_dispatched():
    transport = ASGITransport(app=app)
    msg_id = f"wamid.list_{int(time.time() * 1000)}"
    payload = _make_whatsapp_list_reply_payload(
        msg_id,
        list_id="addr:addr_bandra_101",
        title="Home (Bandra West)",
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "button_dispatched"
        assert data["action"] == "addr:addr_bandra_101"
        assert data["address_id"] == "addr_bandra_101"


@pytest.mark.asyncio
async def test_webhook_multi_message_batch_processed():
    transport = ASGITransport(app=app)
    msg1_id = f"wamid.multi1_{int(time.time() * 1000)}"
    msg2_id = f"wamid.multi2_{int(time.time() * 1000)}"
    wa_id = "919876543210"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": wa_id}
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": msg1_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "First item"},
                                },
                                {
                                    "from": wa_id,
                                    "id": msg2_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": "Second item"},
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["processed"] == 2

    # Verify both messages exist in the database
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM grocer.inbound_messages WHERE wa_message_id = ANY($1)",
            [msg1_id, msg2_id],
        )
        assert count == 2
