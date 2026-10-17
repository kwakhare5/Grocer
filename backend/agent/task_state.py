"""Encrypted restart-safe customer task snapshots with 30-day retention."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import struct
from typing import Any, AsyncIterator

from backend.integrations.commerce.token_vault import EncryptedPayloadCodec


def customer_advisory_lock_key(customer_id: str) -> int:
    """Derive a deterministic 64-bit signed integer for pg_advisory_xact_lock."""
    digest = hashlib.sha256(customer_id.encode("utf-8")).digest()
    return struct.unpack(">q", digest[:8])[0]


class PostgresTaskStateStore:
    def __init__(self, pool: Any, encryption_key: str) -> None:
        self.pool = pool
        self.codec = EncryptedPayloadCodec(encryption_key)

    @asynccontextmanager
    async def transaction_lock(self, customer_id: str) -> AsyncIterator[Any]:
        """Acquire a Postgres session advisory lock ensuring single-turn serialization across all nodes."""
        if not self.pool:
            yield None
            return
        lock_key = customer_advisory_lock_key(customer_id)
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_lock($1)", lock_key)
            try:
                yield conn
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)

    customer_lock = transaction_lock

    async def load(self, customer_id: str, conn: Any = None) -> dict[str, Any] | None:
        executor = conn or self.pool
        row = await executor.fetchrow(
            """SELECT ciphertext FROM grocer_internal.task_state
               WHERE customer_id = $1 AND updated_at > now() - interval '30 days'""",
            customer_id,
        )
        return self.codec.decrypt(row["ciphertext"]) if row else None

    async def save(self, customer_id: str, state: dict[str, Any], conn: Any = None) -> None:
        ciphertext = self.codec.encrypt(state)
        executor = conn or self.pool
        await executor.execute(
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
