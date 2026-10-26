"""Grocer v1.0 — Command-Line Verification & Test Driver.

Programmatically drives Grocer the way a real WhatsApp customer and Meta Cloud
API webhook does: HMAC-SHA256 signing, interactive button taps, GPS pins, and
database inspection.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncpg
import httpx

from backend.config import settings


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def make_whatsapp_payload(
    wa_id: str,
    text: str | None = None,
    button_id: str | None = None,
    button_title: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[dict[str, Any], str]:
    msg_id = f"wamid.verify_{int(time.time() * 1000)}"
    timestamp = str(int(time.time()))

    msg: dict[str, Any] = {
        "from": wa_id,
        "id": msg_id,
        "timestamp": timestamp,
    }

    if button_id:
        msg["type"] = "interactive"
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": button_id, "title": button_title or "Tap"},
        }
    elif latitude is not None and longitude is not None:
        msg["type"] = "location"
        msg["location"] = {
            "latitude": latitude,
            "longitude": longitude,
            "name": "Delivery Pin",
            "address": "Customer Geolocation",
        }
    else:
        msg["type"] = "text"
        msg["text"] = {"body": text or "hello"}

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
                                {"profile": {"name": "Test Customer"}, "wa_id": wa_id}
                            ],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }
    return payload, msg_id


async def run_doctor(base_url: str) -> bool:
    print(f"=== Grocer Doctor Check ({base_url}) ===")
    all_ok = True

    # 1. Check Meta WhatsApp Webhook GET challenge
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{base_url}/api/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
                    "hub.challenge": "doctor_challenge_123",
                },
            )
            if resp.status_code == 200 and resp.text == "doctor_challenge_123":
                print("[PASS] WhatsApp Webhook GET challenge verified (200 OK).")
            else:
                print(f"[FAIL] Webhook GET challenge returned {resp.status_code}: {resp.text}")
                all_ok = False
    except Exception as exc:
        print(f"[FAIL] Could not reach server at {base_url}: {exc}")
        all_ok = False

    # 2. Check Supabase Database
    try:
        pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=2,
            ssl="require",
            timeout=5.0,
        )
        async with pool.acquire() as conn:
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'grocer';
                """
            )
            names = [r["table_name"] for r in tables]
            expected = {"users", "inbound_messages", "oauth_tokens", "sessions", "approvals", "checkouts"}
            missing = expected - set(names)
            if not missing:
                print(f"[PASS] Database 6/6 tables verified: {sorted(names)}")
            else:
                print(f"[FAIL] Missing database tables: {missing}")
                all_ok = False
        await pool.close()
    except Exception as exc:
        print(f"[FAIL] Database connection error: {exc}")
        all_ok = False

    return all_ok


async def send_simulated_message(
    base_url: str,
    wa_id: str,
    text: str | None = None,
    button_id: str | None = None,
    button_title: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    payload, msg_id = make_whatsapp_payload(
        wa_id=wa_id,
        text=text,
        button_id=button_id,
        button_title=button_title,
        latitude=latitude,
        longitude=longitude,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{base_url}/api/whatsapp/webhook",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        result = {
            "status_code": resp.status_code,
            "response": resp.json() if resp.status_code == 200 else resp.text,
            "msg_id": msg_id,
        }
        print(json.dumps(result, indent=2))
        return result


async def inspect_db_state(wa_id: str) -> None:
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=1,
        max_size=2,
        ssl="require",
        timeout=5.0,
    )
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, wa_id, created_at FROM grocer.users WHERE wa_id = $1;",
            wa_id,
        )
        if not user:
            print(f"No user found for wa_id={wa_id}")
            await pool.close()
            return

        user_id = user["id"]
        messages = await conn.fetch(
            """
            SELECT wa_message_id, message_type, status, created_at
            FROM grocer.inbound_messages
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 5;
            """,
            user_id,
        )
        approvals = await conn.fetch(
            """
            SELECT id, status, to_pay_paise, created_at
            FROM grocer.approvals
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 3;
            """,
            user_id,
        )

        print(f"\n=== DB State for User {user_id} ({wa_id}) ===")
        print(f"Recent inbound messages: {len(messages)}")
        for m in messages:
            print(f"  - [{m['created_at'].strftime('%H:%M:%S')}] {m['wa_message_id']}: type={m['message_type']}, status={m['status']}")
        print(f"Recent approvals: {len(approvals)}")
        for a in approvals:
            print(f"  - [{a['created_at'].strftime('%H:%M:%S')}] approval={a['id']}: total={a['to_pay_paise']} paise, status={a['status']}")

    await pool.close()


def main():
    parser = argparse.ArgumentParser(description="Grocer v1.0 Test Driver & Verifier")
    subparsers = parser.add_subparsers(dest="cmd")

    doc_p = subparsers.add_parser("doctor")
    doc_p.add_argument("--url", default="http://127.0.0.1:8000")

    txt_p = subparsers.add_parser("send-text")
    txt_p.add_argument("--url", default="http://127.0.0.1:8000")
    txt_p.add_argument("--phone", default="919876543210")
    txt_p.add_argument("--text", required=True)

    btn_p = subparsers.add_parser("send-button")
    btn_p.add_argument("--url", default="http://127.0.0.1:8000")
    btn_p.add_argument("--phone", default="919876543210")
    btn_p.add_argument("--button-id", required=True)
    btn_p.add_argument("--title", default="Tap")

    loc_p = subparsers.add_parser("send-location")
    loc_p.add_argument("--url", default="http://127.0.0.1:8000")
    loc_p.add_argument("--phone", default="919876543210")
    loc_p.add_argument("--lat", type=float, required=True)
    loc_p.add_argument("--lng", type=float, required=True)

    insp_p = subparsers.add_parser("inspect-db")
    insp_p.add_argument("--phone", default="919876543210")

    args = parser.parse_args()

    if args.cmd == "doctor":
        ok = asyncio.run(run_doctor(args.url))
        sys.exit(0 if ok else 1)
    elif args.cmd == "send-text":
        asyncio.run(send_simulated_message(args.url, args.phone, text=args.text))
    elif args.cmd == "send-button":
        asyncio.run(send_simulated_message(args.url, args.phone, button_id=args.button_id, button_title=args.title))
    elif args.cmd == "send-location":
        asyncio.run(send_simulated_message(args.url, args.phone, latitude=args.lat, longitude=args.lng))
    elif args.cmd == "inspect-db":
        asyncio.run(inspect_db_state(args.phone))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
