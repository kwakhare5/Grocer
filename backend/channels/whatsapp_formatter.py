"""WhatsApp outbound message payload formatting, buttons, lists, and chunking."""
from __future__ import annotations

from typing import Any

from backend.channels.models import NormalizedOutgoingResponse


def mask_recipient(phone: str) -> str:
    """Mask phone number for logging privacy."""
    clean = str(phone or "").strip()
    if len(clean) <= 6:
        return "***"
    return f"{clean[:3]}****{clean[-4:]}"


def format_whatsapp_payload(response: NormalizedOutgoingResponse) -> dict[str, Any]:
    """Build Meta WhatsApp Cloud API JSON payload."""
    to_number = response.recipient_id.replace("+", "").strip()

    # If interactive actions exist (Meta limits interactive bodies to 1024 chars)
    if response.interactive_actions:
        if len(response.text) > 1024:
            cutoff = response.text[:1020].rfind("\n")
            if cutoff == -1 or cutoff < 800:
                cutoff = response.text[:1020].rfind(" ")
            body_text = (response.text[:cutoff].rstrip() + "...") if cutoff > 0 else response.text[:1024]
        else:
            body_text = response.text

        # 1. Quick Reply Buttons (max 3 buttons for confirmation, payment verification, or short binary decisions)
        if response.conversation_state == "AWAITING_PAYMENT":
            reply_actions = [a for a in response.interactive_actions if getattr(a, "action_type", "button") in ("button", "reply")]
            if not reply_actions:
                oid = response.order_id or "order"
                reply_actions = [
                    InteractiveAction(action_type="button", id=f"check_payment:{oid}", title="Check Payment"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": action.id,
                        "title": action.title[:20],  # Meta max 20 chars
                    },
                }
                for action in reply_actions[:3]
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

        reply_actions = [a for a in response.interactive_actions if getattr(a, "action_type", "button") in ("button", "reply")]
        has_list_actions = any(getattr(a, "action_type", "button") in ("list_item", "list_row") for a in response.interactive_actions)

        if reply_actions and (not has_list_actions) and len(response.interactive_actions) <= 3:
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": action.id,
                        "title": action.title[:20],  # Meta max 20 chars
                    },
                }
                for action in reply_actions[:3]
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

        # 2. Decision List Reply (for addresses, multi-item choices, or >3 options)
        else:
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
                        "button": (response.interactive_button_text or "Choose Option")[:20],
                        "sections": [
                            {
                                "title": section_title,
                                "rows": rows[:10],  # Meta allows max 10 rows
                            }
                        ],
                    },
                },
            }

    # 3. Standard Text Message (up to 4096 characters)
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": response.text[:4096]},
    }


def build_message_payloads(response: NormalizedOutgoingResponse) -> list[dict[str, Any]]:
    """Construct ordered text chunks followed by actions, without truncating a receipt."""
    to_number = response.recipient_id.replace("+", "").strip()
    if len(response.text) <= 4096 and (
        not response.interactive_actions or len(response.text) <= 1000
    ):
        return [format_whatsapp_payload(response)]

    payloads: list[dict[str, Any]] = []
    remaining = response.text
    while remaining:
        cut = min(len(remaining), 4096)
        if cut < len(remaining):
            newline = remaining.rfind("\n", 0, cut + 1)
            if newline > cut // 2:
                cut = newline + 1
        payloads.append({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": remaining[:cut]},
        })
        remaining = remaining[cut:]
    if response.interactive_actions:
        short_prompt_resp = NormalizedOutgoingResponse(
            recipient_id=response.recipient_id,
            channel=response.channel,
            text="Please review the details above and choose an option:",
            conversation_state=response.conversation_state,
            interactive_actions=response.interactive_actions,
            interactive_title=response.interactive_title,
            interactive_button_text=response.interactive_button_text,
        )
        payloads.append(format_whatsapp_payload(short_prompt_resp))
    return payloads
