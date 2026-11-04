"""Grocer — Website-first WhatsApp connect.

The site may name a number, but the code it mints only becomes a Swiggy login
link after that same number sends it to the bot on WhatsApp. Nothing here
stores the typed number.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.channels.link_tokens import issue_link_token

router = APIRouter(prefix="/api/auth/whatsapp", tags=["auth"])

CONNECT_TOKEN_TTL_SECONDS = 600
CONNECT_RATE_WINDOW_SECONDS = 600
CONNECT_RATE_MAX = 5
_CONNECT_RATE_CLEANUP_AT = 5000

_attempts: dict[str, deque[float]] = defaultdict(deque)
_INDIAN_MOBILE = re.compile(r"[6-9]\d{9}")


class StartRequest(BaseModel):
    phone: str = Field(..., max_length=24)


class StartResponse(BaseModel):
    token: str
    expiresIn: int


def normalize_indian_mobile(raw: str) -> str | None:
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return f"91{digits}" if _INDIAN_MOBILE.fullmatch(digits) else None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_ok(ip: str, now: float) -> bool:
    if len(_attempts) > _CONNECT_RATE_CLEANUP_AT:
        stale = [
            key
            for key, hits in _attempts.items()
            if not hits or hits[-1] <= now - CONNECT_RATE_WINDOW_SECONDS
        ]
        for key in stale:
            _attempts.pop(key, None)

    hits = _attempts[ip]
    while hits and hits[0] <= now - CONNECT_RATE_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= CONNECT_RATE_MAX:
        return False
    hits.append(now)
    return True


@router.post("/start", response_model=StartResponse)
async def start_connect(req: StartRequest, request: Request) -> StartResponse:
    if not _rate_ok(_client_ip(request), time.time()):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Wait a few minutes, then try again.",
        )

    wa_id = normalize_indian_mobile(req.phone)
    if wa_id is None:
        raise HTTPException(
            status_code=422,
            detail="Enter a 10-digit Indian mobile number.",
        )

    return StartResponse(
        token=issue_link_token(wa_id, ttl_seconds=CONNECT_TOKEN_TTL_SECONDS),
        expiresIn=CONNECT_TOKEN_TTL_SECONDS,
    )
