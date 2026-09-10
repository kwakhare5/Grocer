"""Official WhatsApp Business Platform Channel Adapter (Spec Section 18, Section 19, Phase D).

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
import threading
import time
import os
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
import httpx

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

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
        verify_token: Optional[str] = None,
        app_secret: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: float = 10.0,
        record_only: bool = False,
    ) -> None:
        super().__init__(channel_type=ChannelType.WHATSAPP)
        self._verify_token = verify_token
        self._app_secret = app_secret
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self.timeout = timeout
        self.record_only = record_only

        # Deduplication cache: message_id -> timestamp (1 hour TTL)
        self._processed_message_ids: dict[str, float] = {}
        self._inflight_message_ids: set[str] = set()
        self._pending_responses: dict[str, NormalizedOutgoingResponse] = {}
        self._dedup_lock = threading.Lock()
        # Record of outbound messages for testing and inspection
        self.outbound_messages: list[dict[str, Any]] = []

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
        normalized = "".join(character for character in sender_id if character.isdigit())
        secret = self.app_secret
        if not normalized or not secret:
            raise ValueError("WhatsApp sender identity cannot be verified.")
        digest = hmac.new(
            secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"cust_wa_{digest[:24]}"

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
        expected = self.verify_token
        if (
            mode == "subscribe"
            and expected is not None
            and token is not None
            and hmac.compare_digest(token, expected)
        ):
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
            logger.error("WHATSAPP_APP_SECRET is required for webhook verification.")
            return False

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

    def reserve_message(self, message_id: str) -> bool:
        """Atomically reserve one event for dispatch; false means duplicate/in-flight."""
        now = time.time()
        with self._dedup_lock:
            self._processed_message_ids = {
                mid: ts
                for mid, ts in self._processed_message_ids.items()
                if now - ts < 3600.0
            }
            if (
                message_id in self._processed_message_ids
                or message_id in self._inflight_message_ids
            ):
                return False
            self._inflight_message_ids.add(message_id)
            return True

    def mark_processed(self, message_id: str) -> None:
        """Commit a reservation only after dispatch and outbound delivery succeed."""
        with self._dedup_lock:
            self._inflight_message_ids.discard(message_id)
            self._pending_responses.pop(message_id, None)
            self._processed_message_ids[message_id] = time.time()

    def release_message(self, message_id: str) -> None:
        """Release a failed reservation so Meta can retry the event."""
        with self._dedup_lock:
            self._inflight_message_ids.discard(message_id)

    def pending_delivery(
        self, message_id: str
    ) -> Optional[NormalizedOutgoingResponse]:
        """Return the already-computed outcome for a delivery-only retry."""
        with self._dedup_lock:
            return self._pending_responses.get(message_id)

    def stage_delivery(
        self, message_id: str, response: NormalizedOutgoingResponse
    ) -> None:
        """Retain the computed outcome before calling the Meta delivery API."""
        with self._dedup_lock:
            self._pending_responses[message_id] = response

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
                            )
                        )

        return incoming_messages

    # -----------------------------------------------------------------------
    # 4. Outbound WhatsApp Message Formatting
    # -----------------------------------------------------------------------

    def format_whatsapp_payload(self, response: NormalizedOutgoingResponse) -> dict[str, Any]:
        """Build Meta WhatsApp Cloud API JSON payload."""
        to_number = response.recipient_id.replace("+", "").strip()

        body_text = response.text[:1000]

        # If interactive actions exist (e.g. clarification options or confirmation buttons)
        if response.interactive_actions:
            # 1. Decision List Reply (for payment methods, address selection, alternative options)
            if response.conversation_state == "NEEDS_DECISION":
                header_text = (response.interactive_title or "Options")[:60]
                section_title = (response.interactive_title or "Available Options")[:24]
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
                        "header": {"type": "text", "text": header_text},
                        "body": {"text": body_text},
                        "footer": {"text": "GROCER Intent Assistant"},
                        "action": {
                            "button": response.interactive_button_text or "Choose Option",
                            "sections": [
                                {
                                    "title": section_title,
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
                        "body": {"text": body_text},
                        "action": {"buttons": buttons},
                    },
                }

        # 3. Standard Text Message
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": body_text},
        }

    # -----------------------------------------------------------------------
    # 5. Outbound Delivery
    # -----------------------------------------------------------------------

    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """Send formatted response via Meta WhatsApp Cloud API or record for test inspection."""
        payload = self.format_whatsapp_payload(response)

        if self.record_only:
            self.outbound_messages.append(payload)
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code in (200, 201):
                    logger.info("WhatsApp message delivered.")
                    return True
                logger.error("WhatsApp API returned HTTP %d.", res.status_code)
                return False
        except Exception as exc:
            logger.error("Failed to deliver WhatsApp message: %s", type(exc).__name__)
            return False


# Singleton instance
default_whatsapp_adapter = WhatsAppChannelAdapter()
