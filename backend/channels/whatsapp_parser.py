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

                media_id = None
                media_type = None
                media_mime_type = None
                media_caption = None

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

                elif msg_type in ("audio", "voice"):
                    audio_obj = msg.get(msg_type, {}) or msg.get("audio", {})
                    media_id = audio_obj.get("id")
                    media_type = "audio"
                    media_mime_type = audio_obj.get("mime_type", "audio/ogg")
                    text_body = "[VOICE_NOTE]"

                elif msg_type == "image":
                    img_obj = msg.get("image", {})
                    media_id = img_obj.get("id")
                    media_type = "image"
                    media_mime_type = img_obj.get("mime_type", "image/jpeg")
                    media_caption = img_obj.get("caption", "").strip()
                    text_body = f"[GROCERY_PHOTO] {media_caption}".strip() if media_caption else "[GROCERY_PHOTO]"

                elif msg_type == "location":
                    loc_obj = msg.get("location", {})
                    lat = loc_obj.get("latitude")
                    lng = loc_obj.get("longitude")
                    name = loc_obj.get("name") or ""
                    addr = loc_obj.get("address") or ""
                    loc_desc = f"{name}, {addr}".strip(" ,") if (name or addr) else f"GPS Pin ({lat}, {lng})"
                    text_body = f"[LOCATION_PIN] {loc_desc} (lat: {lat}, lng: {lng})"

                elif msg_type in ("document", "sticker", "video"):
                    text_body = "UNSUPPORTED_MEDIA"

                if text_body or interactive_id or media_id:
                    incoming_messages.append(
                        NormalizedIncomingMessage(
                            sender_id=sender_phone,
                            channel=ChannelType.WHATSAPP,
                            text=text_body,
                            message_id=msg_id,
                            interactive_type=interactive_type,
                            interactive_id=interactive_id,
                            media_id=media_id,
                            media_type=media_type,
                            media_mime_type=media_mime_type,
                            media_caption=media_caption,
                        )
                    )

    return incoming_messages
