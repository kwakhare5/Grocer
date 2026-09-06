"""Official WhatsApp Business Platform Channel Adapter (Spec §18, §19, Phase D).

Supports:
- Webhook verification (GET challenge verification)
- HMAC-SHA256 signature verification (X-Hub-Signature-256)
- Meta Cloud API payload parsing (text, quick reply buttons, interactive list replies)
- Replay attack & duplicate event protection
- Stable customer and session mapping
- Rich interactive message construction (Lists, Reply Buttons)
- Outbound delivery via Meta Graph API v20.0 with test-mode recording
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Optional
import httpx

from backend.channels.base import BaseChannelAdapter
from backend.channels.models import (
    ChannelType,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)

logger = logging.getLogger("grocer.channels.whatsapp")

META_GRAPH_API_URL = "https://graph.facebook.com/v20.0"


class WhatsAppChannelAdapter(BaseChannelAdapter):
    """Authoritative adapter for WhatsApp Business Cloud API."""

    def __init__(
        self,
        verify_token: str = "grocer_whatsapp_verify_token",
        app_secret: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(channel_type=ChannelType.WHATSAPP)
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.phone_number_id = phone_number_id
        self._access_token = access_token
        self.timeout = timeout

        # Deduplication cache: message_id -> timestamp (1 hour TTL)
        self._processed_message_ids: dict[str, float] = {}
        # Record of outbound messages for testing and inspection
        self.outbound_messages: list[dict[str, Any]] = []

    def __repr__(self) -> str:
        token_masked = "***" if self._access_token else "none"
        secret_masked = "***" if self.app_secret else "none"
        return f"WhatsAppChannelAdapter(phone_id={self.phone_number_id}, token={token_masked}, secret={secret_masked})"

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
        if mode == "subscribe" and token == self.verify_token:
            logger.info("WhatsApp webhook challenge verified successfully.")
            return True, challenge or ""
        logger.warning("WhatsApp webhook challenge verification failed.")
        return False, "Forbidden"

    # -----------------------------------------------------------------------
    # 2. Signature Verification (POST HMAC-SHA256)
    # -----------------------------------------------------------------------

    def verify_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Verify X-Hub-Signature-256 header using app secret.

        Header format: sha256={hex_digest}
        """
        if not self.app_secret:
            # If no secret configured in development, log warning and allow
            logger.warning("WHATSAPP_APP_SECRET not configured; skipping HMAC verification.")
            return True

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Missing or malformed X-Hub-Signature-256 header.")
            return False

        expected_sig = signature_header[7:]
        computed_sig = hmac.new(
            self.app_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_sig, computed_sig)
        if not is_valid:
            logger.warning("Invalid WhatsApp webhook HMAC-SHA256 signature.")
        return is_valid

    # -----------------------------------------------------------------------
    # 3. Payload Parsing & Deduplication
    # -----------------------------------------------------------------------

    def is_duplicate(self, message_id: str) -> bool:
        """Check and record message ID in deduplication cache."""
        now = time.time()
        # Prune entries older than 3600s (1 hour)
        self._processed_message_ids = {
            mid: ts for mid, ts in self._processed_message_ids.items() if now - ts < 3600.0
        }

        if message_id in self._processed_message_ids:
            logger.info("Duplicate WhatsApp event ignored: message_id=%s", message_id)
            return True

        self._processed_message_ids[message_id] = now
        return False

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[NormalizedIncomingMessage]:
        """Extract and normalize inbound WhatsApp messages from Meta webhook payload."""
        incoming_messages: list[NormalizedIncomingMessage] = []
        entries = payload.get("entry", [])

        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                val = change.get("value", {})
                messages = val.get("messages", [])

                for msg in messages:
                    msg_id = msg.get("id", "")
                    sender_phone = msg.get("from", "")
                    msg_type = msg.get("type", "text")

                    if not msg_id or not sender_phone:
                        continue

                    # Filter out duplicate webhook deliveries
                    if self.is_duplicate(msg_id):
                        continue

                    text_body = ""
                    interactive_type = None
                    interactive_id = None

                    if msg_type == "text":
                        text_body = msg.get("text", {}).get("body", "").strip()

                    elif msg_type == "interactive":
                        interactive_obj = msg.get("interactive", {})
                        interactive_type = interactive_obj.get("type")

                        if interactive_type == "button_reply":
                            btn = interactive_obj.get("button_reply", {})
                            interactive_id = btn.get("id")
                            text_body = btn.get("title", "")

                        elif interactive_type == "list_reply":
                            list_item = interactive_obj.get("list_reply", {})
                            interactive_id = list_item.get("id")
                            text_body = list_item.get("title", "")

                    if text_body or interactive_id:
                        incoming_messages.append(
                            NormalizedIncomingMessage(
                                sender_id=sender_phone,
                                channel=ChannelType.WHATSAPP,
                                text=text_body,
                                message_id=msg_id,
                                interactive_type=interactive_type,
                                interactive_id=interactive_id,
                                raw_payload=msg,
                            )
                        )

        return incoming_messages

    # -----------------------------------------------------------------------
    # 4. Outbound WhatsApp Message Formatting
    # -----------------------------------------------------------------------

    def format_whatsapp_payload(self, response: NormalizedOutgoingResponse) -> dict[str, Any]:
        """Build Meta WhatsApp Cloud API JSON payload."""
        to_number = response.recipient_id.replace("+", "").strip()

        # If interactive actions exist (e.g. clarification options or confirmation buttons)
        if response.interactive_actions:
            # 1. Decision List Reply (for alternative options)
            if response.conversation_state == "NEEDS_DECISION":
                rows = [
                    {
                        "id": action.id,
                        "title": action.title[:24],
                        "description": (action.description or "")[:72],
                    }
                    for action in response.interactive_actions
                ]
                return {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to_number,
                    "type": "interactive",
                    "interactive": {
                        "type": "list",
                        "header": {"type": "text", "text": "Alternative Options"},
                        "body": {"text": response.text},
                        "footer": {"text": "GROCER Intent Assistant"},
                        "action": {
                            "button": response.interactive_button_text or "Choose Option",
                            "sections": [
                                {
                                    "title": "Available Replacements",
                                    "rows": rows[:10],  # Meta allows max 10 rows
                                }
                            ],
                        },
                    },
                }

            # 2. Confirmation Quick Reply Buttons (max 3 buttons)
            elif response.conversation_state == "AWAITING_CONFIRMATION":
                buttons = [
                    {
                        "type": "reply",
                        "reply": {
                            "id": action.id,
                            "title": action.title[:20],  # Meta max 20 chars
                        },
                    }
                    for action in response.interactive_actions[:3]
                ]
                return {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to_number,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": response.text},
                        "action": {"buttons": buttons},
                    },
                }

        # 3. Standard Text Message
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": response.text},
        }

    # -----------------------------------------------------------------------
    # 5. Outbound Delivery
    # -----------------------------------------------------------------------

    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """Send formatted response via Meta WhatsApp Cloud API or record for test inspection."""
        payload = self.format_whatsapp_payload(response)
        self.outbound_messages.append(payload)

        if not self.phone_number_id or not self._access_token:
            logger.info("WhatsApp credentials not set; recorded outbound message to test queue.")
            return True

        url = f"{META_GRAPH_API_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code in (200, 201):
                    logger.info("WhatsApp message delivered to %s", response.recipient_id)
                    return True
                logger.error("WhatsApp API returned error %d: %s", res.status_code, res.text)
                return False
        except Exception as exc:
            logger.error("Failed to deliver WhatsApp message: %s", exc)
            return False


# Singleton instance
default_whatsapp_adapter = WhatsAppChannelAdapter()
