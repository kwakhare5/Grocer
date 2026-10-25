"""Grocer v1.0 — Inbound WhatsApp Payload Parser & Stale Latch."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

STALE_MESSAGE_THRESHOLD_SECONDS = 900  # 15 minutes


@dataclass(frozen=True)
class InboundMessage:
    wa_message_id: str
    sender_wa_id: str
    timestamp: int
    message_type: str
    text: str | None = None
    button_id: str | None = None
    button_title: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def is_stale(self) -> bool:
        """Check if message timestamp is older than the 15-minute threshold."""
        return (time.time() - self.timestamp) > STALE_MESSAGE_THRESHOLD_SECONDS


def parse_webhook_payload(payload: dict[str, Any]) -> tuple[str, list[InboundMessage]]:
    """Parse Meta WhatsApp Cloud API webhook JSON payload.

    Returns:
        tuple of (payload_kind, list of parsed messages)
        payload_kind can be "status", "messages", or "empty".
    """
    entries = payload.get("entry", [])
    if not entries:
        return "empty", []

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})

            # 1. Delivery Receipts (statuses) -> Fast ACK and ignore
            if value.get("statuses"):
                return "status", []

            # 2. Inbound Customer Messages
            raw_messages = value.get("messages", [])
            if raw_messages:
                parsed_list: list[InboundMessage] = []
                for msg in raw_messages:
                    wa_message_id = msg.get("id", "")
                    sender_wa_id = msg.get("from", "")
                    timestamp = int(msg.get("timestamp", time.time()))
                    raw_type = msg.get("type", "unknown")

                    text_val: str | None = None
                    btn_id: str | None = None
                    btn_title: str | None = None
                    lat: float | None = None
                    lon: float | None = None

                    if raw_type == "text":
                        text_val = msg.get("text", {}).get("body", "")
                        msg_type = "text"
                    elif raw_type == "interactive":
                        msg_type = "button_reply"
                        interactive = msg.get("interactive", {})
                        sub_type = interactive.get("type", "")
                        if sub_type in ("button_reply", "list_reply"):
                            reply_obj = interactive.get(sub_type, {})
                            btn_id = reply_obj.get("id")
                            btn_title = reply_obj.get("title")
                    elif raw_type == "location":
                        msg_type = "location"
                        loc = msg.get("location", {})
                        lat = loc.get("latitude")
                        lon = loc.get("longitude")
                    else:
                        msg_type = "unsupported"

                    parsed_list.append(
                        InboundMessage(
                            wa_message_id=wa_message_id,
                            sender_wa_id=sender_wa_id,
                            timestamp=timestamp,
                            message_type=msg_type,
                            text=text_val,
                            button_id=btn_id,
                            button_title=btn_title,
                            latitude=lat,
                            longitude=lon,
                            raw_payload=msg,
                        )
                    )
                return "messages", parsed_list

    return "empty", []
