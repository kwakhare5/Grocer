"""Grocer v1.0 — WhatsApp HMAC-SHA256 Signature & Webhook Challenge Verification."""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(
    payload_bytes: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    """Validate X-Hub-Signature-256 header using constant-time comparison."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_hash = signature_header[7:]
    mac = hmac.new(app_secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    computed_hash = mac.hexdigest()

    return hmac.compare_digest(computed_hash, expected_hash)


def verify_webhook_challenge(
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
    expected_token: str,
) -> str | None:
    """Validate Meta GET webhook handshake and return challenge if valid."""
    if mode == "subscribe" and verify_token == expected_token and challenge:
        return challenge
    return None
