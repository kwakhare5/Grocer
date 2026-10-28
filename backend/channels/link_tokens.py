"""Grocer — Signed OAuth Link Tokens.

The bot sends the link, so the link itself proves which WhatsApp number is
logging in. The landing page can no longer name an arbitrary phone number.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from backend.config import settings

LINK_TOKEN_TTL_SECONDS = 3600


def _sign(body: str) -> str:
    return hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def issue_link_token(wa_id: str, ttl_seconds: int = LINK_TOKEN_TTL_SECONDS) -> str:
    body = f"{wa_id}.{int(time.time()) + ttl_seconds}"
    return f"{body}.{_sign(body)}"


def verify_link_token(token: str, now: float | None = None) -> str | None:
    """Return the WhatsApp id when the token is genuine and unexpired."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    wa_id, expiry_text, signature = parts
    if not wa_id.isdigit() or not expiry_text.isdigit():
        return None
    if not hmac.compare_digest(signature, _sign(f"{wa_id}.{expiry_text}")):
        return None
    if int(expiry_text) < int(now if now is not None else time.time()):
        return None
    return wa_id
