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
        """Deliver payload to Meta Graph API, safely catching network issues in test/offline environments."""
        # Clean recipient phone number (remove any leading '+')
        if "to" in payload:
            payload["to"] = payload["to"].lstrip("+").strip()

        # Offline / Test fallback when credentials are placeholder or offline
        if not self.access_token or self.access_token.startswith("mock_") or settings.ENVIRONMENT == "test":
            logger.info("WhatsApp outbound delivery mocked in %s environment for %s", settings.ENVIRONMENT, payload.get("to"))
            return {"status": "mock_delivered", "payload": payload}

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

    async def send_text_message(
        self,
        to_wa_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a standard text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": text},
        }
        return await self._post_message(payload)

    async def send_quick_reply_buttons(
        self,
        to_wa_id: str,
        body_text: str,
        buttons: list[tuple[str, str]],
        header_text: str | None = None,
        footer_text: str | None = None,
    ) -> dict[str, Any]:
        """Send an interactive message with up to 3 quick-reply buttons (DESIGN.md)."""
        meta_buttons = []
        for btn_id, title in buttons[:3]:
            meta_buttons.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": btn_id,
                        "title": title[:20],  # Meta 20-char button title limit
                    },
                }
            )

        interactive: dict[str, Any] = {
            "type": "button",
            "body": {"text": body_text[:1024]},
            "action": {"buttons": meta_buttons},
        }

        if header_text:
            interactive["header"] = {"type": "text", "text": header_text[:60]}
        if footer_text:
            interactive["footer"] = {"text": footer_text[:60]}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._post_message(payload)

    async def send_cta_url_button(
        self,
        to_wa_id: str,
        body_text: str,
        button_text: str,
        url: str,
        header_text: str | None = None,
        footer_text: str | None = None,
    ) -> dict[str, Any]:
        """Send an interactive CTA URL button (opens Swiggy HTTPS bridgeUrl)."""
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

        if header_text:
            interactive["header"] = {"type": "text", "text": header_text[:60]}
        if footer_text:
            interactive["footer"] = {"text": footer_text[:60]}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._post_message(payload)
