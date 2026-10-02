"""Stable, secret-backed customer identity helpers."""
from __future__ import annotations

import hashlib
import hmac
import re


def whatsapp_customer_id(phone_number: str, app_secret: str | None) -> str:
    """Return a pseudonymous customer ID without retaining a phone number."""
    if not app_secret:
        raise RuntimeError("WhatsApp identity is not configured.")

    normalized = phone_number.removeprefix("+")
    if not re.fullmatch(r"91[6-9][0-9]{9}", normalized):
        raise ValueError("A full Indian WhatsApp E.164 number is required.")
    digest = hmac.new(
        app_secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"cust_wa_{digest[:24]}"
