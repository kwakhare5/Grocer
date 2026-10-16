"""WhatsApp webhook challenge and HMAC-SHA256 signature verification."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

logger = logging.getLogger("grocer.channels.whatsapp.crypto")


def verify_webhook_challenge(
    verify_token: Optional[str],
    mode: Optional[str],
    token: Optional[str],
    challenge: Optional[str],
) -> tuple[bool, str]:
    """Verify Meta webhook registration challenge."""
    if (
        mode == "subscribe"
        and verify_token is not None
        and token is not None
        and hmac.compare_digest(token, verify_token)
    ):
        logger.info("WhatsApp webhook challenge verified successfully.")
        return True, challenge or ""
    logger.warning("WhatsApp webhook challenge verification failed.")
    return False, "Forbidden"


def verify_signature(
    app_secret: Optional[str],
    payload_bytes: bytes,
    signature_header: Optional[str],
) -> bool:
    """Verify X-Hub-Signature-256 header using app secret.

    Header format: sha256={hex_digest}
    """
    if not app_secret:
        logger.error("WHATSAPP_APP_SECRET is required for webhook verification.")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header.")
        return False

    expected_sig = signature_header[7:]
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_sig, computed_sig)
    if not is_valid:
        logger.warning("Invalid WhatsApp webhook HMAC-SHA256 signature.")
    return is_valid
