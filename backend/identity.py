"""Stable, secret-backed customer identity helpers."""
from __future__ import annotations

import hashlib
import hmac


def whatsapp_customer_id(phone_number: str, app_secret: str | None) -> str:
    """Return a pseudonymous customer ID without retaining a phone number."""
    if not app_secret:
        raise RuntimeError("WhatsApp identity is not configured.")

    digits = "".join(character for character in phone_number if character.isdigit())
    if not digits:
        raise ValueError("A valid WhatsApp phone number is required.")

    normalized = digits[-10:] if len(digits) >= 10 else digits
    digest = hmac.new(
        app_secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"cust_wa_{digest[:24]}"
