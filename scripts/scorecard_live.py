"""Grocer — live scorecard against the deployed app.

Posts signed Meta-style webhooks to the live deployment with the real router,
the real Groq model and the real Swiggy MCP. Reads each reply back from the
session history and scores it against fixed phrases.

This measures understanding and delivery, not the internals. It never calls
checkout and never places an order.

Usage:
    python scripts/scorecard_live.py --start 1 --end 13
    python scripts/scorecard_live.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncpg
import httpx

from backend.config import settings

OUT_PATH = ROOT / ".scratch" / "scorecard_live.json"
OUTAGE_COPY = "ai is offline"


@dataclass(frozen=True)
class LiveCase:
    name: str
    text: str
    must: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    category: str = "general"
    note: str = ""


CASES: tuple[LiveCase, ...] = (
    LiveCase("basket read", "what's in my basket?", ("basket",), category="read"),
    LiveCase("addresses", "show my addresses", ("address",), category="read"),
    LiveCase("payment options", "show payment options", ("upi",), category="read"),
    LiveCase("coupons", "what coupons do i have?", ("coupon",), category="read"),
    LiveCase("store open", "is the store open right now?", category="read"),
    LiveCase("order history", "show my orders", category="read", note="honest empty is a pass"),
    LiveCase("last bill", "show my last bill", category="read", note="honest empty is a pass"),
    LiveCase("track order", "where is my order?", category="read", note="honest empty is a pass"),
    LiveCase("add milk", "add 1 litre milk", ("milk",), category="add"),
    LiveCase("multi add", "add 6 eggs and brown bread", ("egg", "bread"), category="add"),
    LiveCase("more milk", "add 1 more milk", ("milk",), category="add"),
    LiveCase("vague milk", "milk", ("milk",), category="add"),
    LiveCase(
        "batch add",
        "add 200g paneer, 1 packet gulab jamun and 500g rice",
        ("paneer", "rice"),
        category="add",
        note="rice may be named as not added, but must never vanish",
    ),
    LiveCase("recipe plan", "make pasta for 3 people", ("pasta",), category="recipe"),
    LiveCase("coupon apply", "apply the best coupon", ("coupon",), category="coupon"),
    LiveCase("cap", "add 5 kg almonds", ("cap",), category="truth"),
    LiveCase("no match", "add dragon fruit", ("dragon",), category="truth"),
    LiveCase("hinglish", "bhai 1 litre doodh aur 6 ande bhejo", ("milk",), category="add"),
    LiveCase(
        "contradiction",
        "add milk and then remove the milk",
        category="truth",
        note="either order is fine if the reply is clear",
    ),
    LiveCase("usual", "get my usual", category="reorder", note="honest empty is a pass"),
    LiveCase("cash", "can i pay cash on delivery?", ("cash",), category="truth"),
    LiveCase("cheap item", "add a single banana", ("banana",), category="add"),
    LiveCase("report", "report a problem with my last order", category="support"),
    LiveCase("remove paneer", "remove the paneer", category="change"),
    LiveCase("double text 1", "add sugar", ("sugar",), category="add"),
    LiveCase("double text 2", "and salt", ("salt",), category="add"),
)


def _payload(wa_id: str, text: str) -> tuple[dict, str]:
    msg_id = f"wamid.score_{int(time.time() * 1000)}_{abs(hash(text)) % 10000}"
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
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": msg_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    return payload, msg_id


async def _active_user(pool: asyncpg.Pool) -> tuple[str, str]:
    row = await pool.fetchrow(
        """
        SELECT s.user_id, u.wa_id
        FROM grocer.sessions s JOIN grocer.users u ON u.id = s.user_id
        ORDER BY s.last_active_at DESC LIMIT 1;
        """
    )
    if row is None:
        raise RuntimeError("no user with a session; open the bot once first")
    return str(row["user_id"]), row["wa_id"]


async def _history(pool: asyncpg.Pool, user_id: str) -> list[dict]:
    row = await pool.fetchrow(
        "SELECT history FROM grocer.sessions WHERE user_id = $1::uuid;", user_id
    )
    history = row["history"] if row else []
    if isinstance(history, str):
        history = json.loads(history)
    return history or []


def _score(case: LiveCase, reply: str) -> list[str]:
    said = reply.lower()
    problems: list[str] = []
    if OUTAGE_COPY in said:
        problems.append("answered with the AI-offline copy")
    for phrase in case.must:
        if phrase.lower() not in said:
            problems.append(f"reply never said {phrase!r}")
    for phrase in case.must_not:
        if phrase.lower() in said:
            problems.append(f"reply wrongly said {phrase!r}")
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser(description="Live scorecard")
    parser.add_argument("--base-url", default="https://grocer-backend-qwk4.onrender.com")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=len(CASES))
    parser.add_argument("--pause", type=float, default=22.0)
    args = parser.parse_args()

    selected = CASES[args.start - 1 : args.end]
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL, min_size=1, max_size=1, ssl="require", timeout=15
    )
    user_id, wa_id = await _active_user(pool)
    print(f"live scorecard: {len(selected)} cases against {args.base_url}", flush=True)
    print(f"user {wa_id[:4]}****{wa_id[-2:]}", flush=True)

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for offset, case in enumerate(selected):
            index = args.start + offset
            payload, msg_id = _payload(wa_id, case.text)
            body = json.dumps(payload).encode()
            signature = "sha256=" + hmac.new(
                settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256
            ).hexdigest()
            started = time.monotonic()
            error = None
            status = None
            try:
                response = await client.post(
                    f"{args.base_url}/api/whatsapp/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": signature,
                    },
                )
                status = response.status_code
            except Exception as exc:  # noqa: BLE001 - report, never hide
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = round((time.monotonic() - started) * 1000)

            await asyncio.sleep(2.5)
            reply = "(no reply found)"
            history = await _history(pool, user_id)
            for position in range(len(history) - 1, -1, -1):
                if (
                    history[position].get("role") == "user"
                    and str(history[position].get("text", "")).strip() == case.text
                ):
                    reply = next(
                        (
                            entry.get("text", "")
                            for entry in history[position + 1 :]
                            if entry.get("role") == "assistant"
                        ),
                        "(user turn stored, no assistant reply)",
                    )
                    break

            problems = _score(case, reply)
            if status != 200:
                problems.insert(0, f"http {status}")
            if error:
                problems.insert(0, error)

            passed = not problems
            rows.append(
                {
                    "index": index,
                    "name": case.name,
                    "category": case.category,
                    "note": case.note,
                    "sent": case.text,
                    "http": status,
                    "latency_ms": latency_ms,
                    "reply": reply,
                    "passed": passed,
                    "problems": problems,
                    "msg_id": msg_id,
                }
            )
            print(
                f"[{index:02d}] {'PASS' if passed else 'FAIL'} {case.name:<16} "
                f"http={status} {latency_ms}ms",
                flush=True,
            )
            print(f"   > {case.text}", flush=True)
            print(f"   < {reply[:400]}", flush=True)
            if problems:
                for problem in problems:
                    print(f"   ! {problem}", flush=True)
            if offset != len(selected) - 1 and case.name != "double text 1":
                await asyncio.sleep(args.pause)

    await pool.close()

    per_category: dict[str, list[bool]] = {}
    for row in rows:
        per_category.setdefault(row["category"], []).append(row["passed"])
    passed_total = sum(1 for row in rows if row["passed"])
    print("\n" + "=" * 58)
    for category, results in per_category.items():
        print(f"  {category:<12} {sum(results)}/{len(results)}")
    print(f"  {'TOTAL':<12} {passed_total}/{len(rows)}  "
          f"{passed_total / len(rows) * 100:.1f}%")
    print("=" * 58)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "mode": "live",
                "base_url": args.base_url,
                "ran_at": datetime.now(UTC).isoformat(),
                "total": len(rows),
                "passed": passed_total,
                "percent": round(passed_total / len(rows) * 100, 1),
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"raw: {OUT_PATH}")
    return 0 if passed_total == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
