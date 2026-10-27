"""Grocer v1.0 — Outbound Meta WhatsApp Cloud API Client.

Transmits messages, interactive reply buttons, and CTA URL buttons
to customer phones adhering to DESIGN.md.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("grocer.channels.whatsapp_client")


def build_text_payload(to_wa_id: str, text: str) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text},
    }


def build_buttons_payload(
    to_wa_id: str,
    body_text: str,
    buttons: list[tuple[str, str]],
) -> dict[str, Any]:
    meta_buttons = [
        {
            "type": "reply",
            "reply": {"id": btn_id, "title": title[:20]},
        }
        for btn_id, title in buttons[:3]
    ]

    interactive: dict[str, Any] = {
        "type": "button",
        "body": {"text": body_text[:1024]},
        "action": {"buttons": meta_buttons},
    }

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": interactive,
    }


def build_read_payload(message_id: str) -> dict[str, Any]:
    """Mark an inbound message read and show a typing bubble."""
    return {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }


def build_cta_payload(
    to_wa_id: str,
    body_text: str,
    button_text: str,
    url: str,
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError(f"Strict scheme violation: CTA URL must use 'https://', got '{url}'")

    interactive: dict[str, Any] = {
        "type": "cta_url",
        "body": {"text": body_text[:1024]},
        "action": {
            "name": "cta_url",
            "parameters": {
                "display_text": button_text[:20],
                "url": url,
            },
        },
    }

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": interactive,
    }


class WhatsAppClient:
    """Outbound client sending messages to Meta's WhatsApp Cloud API (v21.0)."""

    def __init__(
        self,
        phone_number_id: str | None = None,
        access_token: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.timeout_seconds = timeout_seconds
        self.endpoint_url = (
            f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"
        )

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _post_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deliver payload to the Meta Graph API."""
        # Clean recipient phone number (remove any leading '+')
        if "to" in payload:
            payload["to"] = payload["to"].lstrip("+").strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=self._get_headers(),
                )
                res.raise_for_status()
                data = res.json()
                logger.info("WhatsApp message delivered to %s: id=%s", payload.get("to"), data.get("messages", [{}])[0].get("id"))
                return data
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
            logger.warning("WhatsApp message delivery failed to %s: %s", payload.get("to"), exc)
            return {"status": "failed", "error": str(exc), "to": payload.get("to")}

    async def mark_read(self, message_id: str) -> dict[str, Any]:
        """Blue ticks plus a typing indicator; Meta clears it after ~25 seconds."""
        return await self._post_message(build_read_payload(message_id))

    async def send_text_message(
        self,
        to_wa_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a standard text message."""
        return await self._post_message(build_text_payload(to_wa_id, text))

    async def send_quick_reply_buttons(
        self,
        to_wa_id: str,
        body_text: str,
        buttons: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """Send an interactive message with up to 3 quick-reply buttons (DESIGN.md)."""
        return await self._post_message(
            build_buttons_payload(to_wa_id, body_text, buttons)
        )

    async def send_cta_url_button(
        self,
        to_wa_id: str,
        body_text: str,
        button_text: str,
        url: str,
    ) -> dict[str, Any]:
        """Send an interactive CTA URL button (opens Swiggy HTTPS bridgeUrl)."""
        return await self._post_message(
            build_cta_payload(to_wa_id, body_text, button_text, url)
        )
