"""Shared fixtures and webhook helper utilities for WhatsApp PostgreSQL E2E test suites."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import asyncpg
import pytest

from backend.channels.whatsapp import default_whatsapp_adapter


def _local_dsn() -> str:
    dsn = os.environ.get("GROCER_E2E_DATABASE_URL", "")
    if "@127.0.0.1:" not in dsn or not dsn.endswith("/grocer_test"):
        pytest.skip("Set GROCER_E2E_DATABASE_URL to the isolated localhost grocer_test database")
    return dsn


@pytest.fixture
async def postgres_pool():
    pool = await asyncpg.create_pool(_local_dsn(), ssl=False, min_size=1, max_size=3)
    root = Path(__file__).resolve().parents[3] / "migrations"
    async with pool.acquire() as conn:
        for name in (
            "bootstrap_fresh.sql",
            "001_connect_tickets.up.sql",
            "002_messages.up.sql",
            "003_checkout_attempts.up.sql",
            "004_task_state.up.sql",
            "005_privacy_deletions.up.sql",
            "006_inbound_claimed_at.up.sql",
            "007_outbound_sending_started_at.up.sql",
            "008_payment_followups.up.sql",
            "009_replenishment.up.sql",
        ):
            await conn.execute((root / name).read_text(encoding="utf-8"))
        await conn.execute(
            "TRUNCATE grocer_internal.replenishment, grocer_internal.task_state, grocer_internal.checkout_attempts, grocer_internal.outbound_messages, grocer_internal.inbound_messages RESTART IDENTITY CASCADE"
        )
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(autouse=True)
def configure_e2e_secrets(monkeypatch):
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()


def _webhook(message_id: str, text: str, sender: str = "919999988888") -> tuple[bytes, dict[str, str]]:
    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": message_id,
                        "from": sender,
                        "type": "text",
                        "text": {"body": text},
                    }]
                }
            }]
        }],
    }).encode()
    signature = hmac.new(b"local-e2e-secret", body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={signature}"}


def _interactive_webhook(message_id: str, action_id: str, title: str, sender: str = "919999988888") -> tuple[bytes, dict[str, str]]:
    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": message_id,
                        "from": sender,
                        "type": "interactive",
                        "interactive": {
                            "type": "list_reply",
                            "list_reply": {"id": action_id, "title": title},
                        },
                    }]
                }
            }]
        }],
    }).encode()
    signature = hmac.new(b"local-e2e-secret", body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={signature}"}
