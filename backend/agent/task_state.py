"""Encrypted restart-safe customer task snapshots with 30-day retention."""
from __future__ import annotations

from typing import Any

from backend.integrations.commerce.token_vault import EncryptedPayloadCodec


class PostgresTaskStateStore:
    def __init__(self, pool: Any, encryption_key: str) -> None:
        self.pool = pool
        self.codec = EncryptedPayloadCodec(encryption_key)

    async def load(self, customer_id: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            """SELECT ciphertext FROM grocer_internal.task_state
               WHERE customer_id = $1 AND updated_at > now() - interval '30 days'""",
            customer_id,
        )
        return self.codec.decrypt(row["ciphertext"]) if row else None

    async def save(self, customer_id: str, state: dict[str, Any]) -> None:
        ciphertext = self.codec.encrypt(state)
        await self.pool.execute(
            """INSERT INTO grocer_internal.task_state
               (customer_id, ciphertext, updated_at) VALUES ($1, $2, now())
               ON CONFLICT (customer_id) DO UPDATE
               SET ciphertext = EXCLUDED.ciphertext, updated_at = now()""",
            customer_id, ciphertext,
        )

    async def delete(self, customer_id: str) -> None:
        await self.pool.execute(
            "DELETE FROM grocer_internal.task_state WHERE customer_id = $1", customer_id
        )

    async def delete_expired(self) -> None:
        await self.pool.execute(
            "DELETE FROM grocer_internal.task_state WHERE updated_at <= now() - interval '30 days'"
        )
