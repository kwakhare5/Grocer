"""Everything one webhook turn carries: the customer, the cart client, the DB
connection and the dialogue history. Passed to the per-capability handlers so
they need no closure over the webhook handler's locals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class TurnContext:
    conn: Any
    user_id: Any
    wa_id: str
    text: str
    client: Any
    wa_client: Any
    address_id: str | None
    history: list[dict[str, Any]]
    session_row: Any = None

    async def reply(self, customer_reply: Any) -> None:
        if customer_reply.buttons:
            await self.wa_client.send_quick_reply_buttons(
                to_wa_id=self.wa_id,
                body_text=customer_reply.text,
                buttons=customer_reply.buttons,
            )
        else:
            await self.wa_client.send_text_message(
                to_wa_id=self.wa_id, text=customer_reply.text
            )

    async def remember(self, reply_text: str) -> None:
        self.history.append({"role": "user", "text": self.text})
        self.history.append({"role": "assistant", "text": reply_text})
        await self.conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, history, last_active_at)
            VALUES ($1, $2::jsonb, now())
            ON CONFLICT (user_id) DO UPDATE SET history = $2::jsonb, last_active_at = now();
            """,
            self.user_id,
            json.dumps(self.history[-12:]),
        )
