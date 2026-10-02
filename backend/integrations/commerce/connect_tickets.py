"""Single-use account connection tickets issued only for verified WhatsApp senders."""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

from backend.integrations.commerce.token_vault import opaque_state_hash


class ConnectTickets:
    def __init__(self) -> None:
        self._pool: Any | None = None
        self._memory: dict[bytes, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def configure_postgres(self, pool: Any) -> None:
        self._pool = pool
        self._memory.clear()

    async def issue(self, customer_id: str) -> str:
        if not customer_id:
            raise ValueError("Verified customer identity is required.")
        ticket = secrets.token_urlsafe(32)
        ticket_hash = opaque_state_hash(ticket)
        expires_at = time.time() + 600
        if self._pool is not None:
            await self._pool.execute(
                """INSERT INTO grocer_internal.connect_tickets
                   (ticket_hash, customer_id, expires_at)
                   VALUES ($1, $2, to_timestamp($3))""",
                ticket_hash, customer_id, expires_at,
            )
        else:
            with self._lock:
                self._memory = {
                    key: value for key, value in self._memory.items()
                    if value[1] > time.time()
                }
                self._memory[ticket_hash] = (customer_id, expires_at)
        return ticket

    async def consume(self, ticket: str) -> str | None:
        if not ticket or len(ticket) > 256:
            return None
        ticket_hash = opaque_state_hash(ticket)
        if self._pool is not None:
            row = await self._pool.fetchrow(
                """DELETE FROM grocer_internal.connect_tickets
                   WHERE ticket_hash = $1 AND expires_at > NOW()
                   RETURNING customer_id""",
                ticket_hash,
            )
            return str(row["customer_id"]) if row else None
        with self._lock:
            entry = self._memory.pop(ticket_hash, None)
        return entry[0] if entry and entry[1] > time.time() else None


default_connect_tickets = ConnectTickets()
