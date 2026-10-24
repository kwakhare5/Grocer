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
from backend.config import settings


def _get_supabase_dsn() -> str:
    dsn = os.environ.get("GROCER_E2E_DATABASE_URL") or settings.DATABASE_URL or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "Live Supabase DATABASE_URL is required for tests. "
            "Please check .env or set GROCER_E2E_DATABASE_URL."
        )
    return dsn


@pytest.fixture
async def postgres_pool():
    dsn = _get_supabase_dsn()
    ssl_opt = "require" if ("supabase.co" in dsn or "sslmode=require" in dsn) else False
    # If asyncpg receives sslmode in query string, clean or pass ssl
    clean_dsn = dsn.split("?")[0] if "?" in dsn else dsn
    pool = await asyncpg.create_pool(clean_dsn, ssl=ssl_opt, min_size=1, max_size=3)
    root = Path(__file__).resolve().parents[3] / "migrations"
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='grocer_internal' AND table_name='inbound_messages'"
        )
        if not exists:
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
                "010_drop_replenishment.up.sql",
                "011_queue_indexes.up.sql",
            ):
                await conn.execute((root / name).read_text(encoding="utf-8"))
        await conn.execute(
            "TRUNCATE grocer_internal.task_state, grocer_internal.checkout_attempts, grocer_internal.outbound_messages, grocer_internal.inbound_messages RESTART IDENTITY CASCADE"
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
