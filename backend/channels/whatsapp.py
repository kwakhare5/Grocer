"""Official WhatsApp Business Platform Channel Adapter for GROCER.

Supports:
- Webhook verification (GET challenge verification) via whatsapp_crypto
- HMAC-SHA256 signature verification (X-Hub-Signature-256) via whatsapp_crypto
- Meta Cloud API payload parsing via whatsapp_parser
- Rich interactive message construction & chunking via whatsapp_formatter
- Outbound delivery via Meta Graph API v20.0 with test-mode recording
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from backend.config import settings
from backend.channels.models import (
    ChannelType,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.channels.whatsapp_crypto import (
    verify_signature as _crypto_verify_signature,
    verify_webhook_challenge as _crypto_verify_challenge,
)
from backend.channels.whatsapp_formatter import (
    build_message_payloads as _format_build_payloads,
    format_whatsapp_payload as _format_single_payload,
    mask_recipient,
)
from backend.channels.whatsapp_parser import (
    parse_webhook_payload as _parse_webhook_payload,
)
from backend.identity import whatsapp_customer_id

logger = logging.getLogger("grocer.channels.whatsapp")

META_GRAPH_API_URL = "https://graph.facebook.com/v20.0"


def _mask_recipient(phone: str) -> str:
    return mask_recipient(phone)


class WhatsAppChannelAdapter:
    """Authoritative adapter for WhatsApp Business Cloud API."""

    def __init__(
        self,
        verify_token: Optional[str] = None,
        app_secret: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: float = 10.0,
        record_only: bool = False,
    ) -> None:
        self.channel_type = ChannelType.WHATSAPP
        self._verify_token = verify_token
        self._app_secret = app_secret
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self.timeout = timeout
        self.record_only = record_only

        # Record of outbound messages for testing and inspection
        self.outbound_messages: list[dict[str, Any]] = []
        # Persistent HTTP/2 client for outbound messages and status updates
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def verify_token(self) -> Optional[str]:
        return self._verify_token or os.environ.get("WHATSAPP_VERIFY_TOKEN")

    @verify_token.setter
    def verify_token(self, val: str) -> None:
        self._verify_token = val

    @property
    def app_secret(self) -> Optional[str]:
        return self._app_secret or os.environ.get("WHATSAPP_APP_SECRET")

    @property
    def phone_number_id(self) -> Optional[str]:
        return self._phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token or os.environ.get("WHATSAPP_ACCESS_TOKEN")

    def __repr__(self) -> str:
        token_masked = "***" if self.access_token else "none"
        secret_masked = "***" if self.app_secret else "none"
        return f"WhatsAppChannelAdapter(phone_id={self.phone_number_id}, token={token_masked}, secret={secret_masked})"

    def map_sender_to_customer_id(self, sender_id: str) -> str:
        """Pseudonymize the phone number before it enters commerce/session state."""
        clean_sender = sender_id.removesuffix("_silent").removesuffix("_test")
        return whatsapp_customer_id(
            clean_sender, self.app_secret or settings.WHATSAPP_APP_SECRET
        )

    # -----------------------------------------------------------------------
    # 1. Webhook Verification (GET)
    # -----------------------------------------------------------------------

    def verify_webhook_challenge(
        self,
        mode: Optional[str],
        token: Optional[str],
        challenge: Optional[str],
    ) -> tuple[bool, str]:
        """Verify Meta webhook registration challenge."""
        return _crypto_verify_challenge(self.verify_token, mode, token, challenge)

    # -----------------------------------------------------------------------
    # 2. Signature Verification (POST HMAC-SHA256)
    # -----------------------------------------------------------------------

    def verify_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Verify X-Hub-Signature-256 header using app secret."""
        return _crypto_verify_signature(self.app_secret, payload_bytes, signature_header)

    # -----------------------------------------------------------------------
    # 3. Payload Parsing
    # -----------------------------------------------------------------------

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[NormalizedIncomingMessage]:
        """Extract and normalize inbound WhatsApp messages from Meta webhook payload."""
        return _parse_webhook_payload(payload)

    # -----------------------------------------------------------------------
    # 4. Outbound WhatsApp Message Formatting
    # -----------------------------------------------------------------------

    def format_whatsapp_payload(self, response: NormalizedOutgoingResponse) -> dict[str, Any]:
        """Build Meta WhatsApp Cloud API JSON payload."""
        return _format_single_payload(response)

    def build_message_payloads(self, response: NormalizedOutgoingResponse) -> list[dict[str, Any]]:
        """Construct ordered text chunks followed by actions, without truncating a receipt."""
        return _format_build_payloads(response)

    # -----------------------------------------------------------------------
    # 5. Outbound Delivery
    # -----------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent HTTP/2 client for Meta Graph API."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def mark_message_read(self, message_id: str) -> bool:
        """Mark an incoming WhatsApp message as read to display blue ticks immediately."""
        if self.record_only or not self.phone_number_id or not self.access_token:
            return False
        url = f"{META_GRAPH_API_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        try:
            client = await self._get_client()
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code in (200, 201):
                logger.info("WhatsApp message_id=%s marked as read.", message_id)
                return True
            logger.debug("Failed to mark message read: HTTP %d %s", res.status_code, res.text)
            return False
        except Exception as exc:
            logger.debug("mark_message_read error for message_id=%s: %s", message_id, exc)
            return False

    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """Send formatted response via Meta WhatsApp Cloud API using pooled connection."""
        payloads = self.build_message_payloads(response)

        if self.record_only or response.recipient_id.endswith(("_silent", "_test")):
            self.outbound_messages.extend(payloads)
            logger.info("Silent test delivery recorded for %s; skipping Meta Graph API outbound.", _mask_recipient(response.recipient_id))
            return True

        if not self.phone_number_id or not self.access_token:
            logger.error("WhatsApp delivery credentials are not configured.")
            return False

        url = f"{META_GRAPH_API_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            client = await self._get_client()
            for payload in payloads:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code in (200, 201):
                    logger.info("WhatsApp message delivered to %s.", _mask_recipient(response.recipient_id))
                else:
                    logger.error("WhatsApp API returned HTTP %d for %s", res.status_code, _mask_recipient(response.recipient_id))
                    return False
            return True
        except Exception as exc:
            logger.error("Failed to deliver WhatsApp message: %s", type(exc).__name__)
            return False


# Singleton instance
default_whatsapp_adapter = WhatsAppChannelAdapter()

__all__ = [
    "WhatsAppChannelAdapter",
    "_mask_recipient",
    "default_whatsapp_adapter",
]
