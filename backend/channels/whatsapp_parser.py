"""Meta Cloud API webhook inbound message parser."""
from __future__ import annotations

from typing import Any

from backend.channels.models import (
    ChannelType,
    NormalizedIncomingMessage,
)


def parse_webhook_payload(payload: dict[str, Any]) -> list[NormalizedIncomingMessage]:
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

                elif msg_type in ("audio", "voice", "image", "document", "sticker", "video"):
                    text_body = "UNSUPPORTED_MEDIA"

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
