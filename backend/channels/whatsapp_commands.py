"""Grocer — deterministic text commands that run before commerce."""

from __future__ import annotations

from typing import Any

from backend.channels.link_tokens import login_url, verify_link_token


async def handle_text_command(
    conn: Any,
    msg: Any,
    user_id: Any,
    inbound_id: Any,
    wa_client: Any,
) -> dict[str, Any] | None:
    """Handle media, connect codes and privacy commands; None means continue."""
    if msg.message_type == "unsupported":
        raw_type = str((msg.raw_payload or {}).get("type") or "").lower()
        if raw_type == "reaction":
            return {"status": "ignored_reaction", "wa_message_id": msg.wa_message_id}
        await conn.execute(
            "UPDATE grocer.inbound_messages SET status = 'unsupported_message' "
            "WHERE id = $1;",
            inbound_id,
        )
        await wa_client.send_text_message(
            to_wa_id=msg.sender_wa_id,
            text=(
                "I can only read text and location pins right now. "
                "Please type what you need."
            ),
        )
        return {"status": "unsupported_message", "wa_message_id": msg.wa_message_id}

    if msg.text and msg.text.strip().lower().startswith("connect "):
        code = msg.text.strip().split(None, 1)[1].strip()
        typed_wa_id = verify_link_token(code)
        if typed_wa_id is None:
            await conn.execute(
                "UPDATE grocer.inbound_messages SET status = 'connect_invalid' "
                "WHERE id = $1;",
                inbound_id,
            )
            await wa_client.send_text_message(
                to_wa_id=msg.sender_wa_id,
                text=(
                    "That connect code is invalid or expired. "
                    "Enter your number on the website again for a fresh one."
                ),
            )
            return {"status": "connect_invalid"}

        if typed_wa_id != msg.sender_wa_id:
            await conn.execute(
                "UPDATE grocer.inbound_messages SET status = 'connect_mismatch' "
                "WHERE id = $1;",
                inbound_id,
            )
            await wa_client.send_text_message(
                to_wa_id=msg.sender_wa_id,
                text=(
                    "That code belongs to a different number. "
                    "Message me from the number you entered on the website."
                ),
            )
            return {"status": "connect_mismatch"}

        await conn.execute(
            "UPDATE grocer.inbound_messages SET status = 'connect_confirmed' "
            "WHERE id = $1;",
            inbound_id,
        )
        await wa_client.send_cta_url_button(
            to_wa_id=msg.sender_wa_id,
            body_text=(
                "*Number confirmed.* Tap below to sign in to Swiggy. "
                "I'll be ready in your chat when you're back."
            ),
            button_text="Connect Swiggy",
            url=login_url(msg.sender_wa_id),
        )
        return {"status": "connect_confirmed"}

    if msg.text and msg.text.strip().lower() == "delete my data":
        from backend.agent.dpdp import handle_delete_my_data

        cmd_res = await handle_delete_my_data(conn, str(user_id))
        if cmd_res is not None:
            if cmd_res.get("message"):
                await wa_client.send_text_message(
                    to_wa_id=msg.sender_wa_id,
                    text=cmd_res["message"],
                )
            return cmd_res

    return None
