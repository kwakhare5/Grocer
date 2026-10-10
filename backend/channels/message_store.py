"""PostgreSQL inbox and outbox for signed WhatsApp messages.

Interrupted turns receive an uncertainty notice; their agent work is never replayed.
"""
from __future__ import annotations

import json
from typing import Any

from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse


def _uncertain_turn_response(payload: dict[str, Any]) -> NormalizedOutgoingResponse:
    message = NormalizedIncomingMessage.model_validate(payload)
    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=ChannelType.WHATSAPP,
        text=("I couldn't verify what happened to your last request. "
              "Please review your current basket before making more changes or placing an order. "
              "Reply 'show cart' and I'll check it."),
        conversation_state="READY",
        events=["UNCERTAIN_ACTION"],
    )


class PostgresMessageStore:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    @staticmethod
    async def _complete_uncertain(connection: Any, inbound_id: int, payload: Any) -> None:
        response = _uncertain_turn_response(json.loads(payload) if isinstance(payload, str) else payload)
        await connection.execute(
            "UPDATE grocer_internal.inbound_messages SET status='PROCESSED', processed_at=now() WHERE id=$1",
            inbound_id,
        )
        await connection.execute(
            """INSERT INTO grocer_internal.outbound_messages (inbound_id, customer_id, payload)
               SELECT id, customer_id, $2::jsonb FROM grocer_internal.inbound_messages WHERE id=$1""",
            inbound_id, response.model_dump_json(),
        )

    async def enqueue_many(self, messages: list[NormalizedIncomingMessage]) -> int:
        inserted = 0
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for message in messages:
                    result = await connection.execute(
                        """INSERT INTO grocer_internal.inbound_messages
                           (message_id, customer_id, payload)
                           VALUES ($1, $2, $3::jsonb)
                           ON CONFLICT (message_id) DO NOTHING""",
                        message.message_id, message.customer_id,
                        message.model_dump_json(),
                    )
                    inserted += result == "INSERT 0 1"
        return inserted

    async def claim_next(self) -> tuple[int, NormalizedIncomingMessage] | None:
        row = await self.pool.fetchrow(
            """WITH candidate AS (
                   SELECT i.id FROM grocer_internal.inbound_messages i
                   WHERE i.status = 'PENDING'
                     AND NOT EXISTS (
                       SELECT 1 FROM grocer_internal.inbound_messages earlier
                       WHERE earlier.customer_id = i.customer_id AND earlier.id < i.id
                         AND earlier.status IN ('PENDING', 'PROCESSING', 'NEEDS_REVIEW'))
                     AND NOT EXISTS (
                       SELECT 1 FROM grocer_internal.outbound_messages o
                       WHERE o.customer_id = i.customer_id
                         AND o.status IN ('QUEUED', 'SENDING'))
                     AND NOT EXISTS (
                       SELECT 1 FROM grocer_internal.privacy_deletions d
                       WHERE d.customer_id = i.customer_id)
                   ORDER BY i.id LIMIT 1 FOR UPDATE SKIP LOCKED
               )
               UPDATE grocer_internal.inbound_messages i
               SET status = 'PROCESSING', claimed_at = now()
               FROM candidate WHERE i.id = candidate.id
               RETURNING i.id, i.payload"""
        )
        if row is None:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return row["id"], NormalizedIncomingMessage.model_validate(payload)

    async def absorb_subsequent_pending(self, customer_id: str) -> list[NormalizedIncomingMessage]:
        """Claim and absorb newly arrived pending messages for the active customer to debounce bursts."""
        rows = await self.pool.fetch(
            """WITH absorbed AS (
                   SELECT id FROM grocer_internal.inbound_messages
                   WHERE customer_id = $1 AND status = 'PENDING'
                   ORDER BY id ASC
                   FOR UPDATE SKIP LOCKED
               )
               UPDATE grocer_internal.inbound_messages i
               SET status = 'PROCESSED', processed_at = now()
               FROM absorbed WHERE i.id = absorbed.id
               RETURNING i.id, i.payload""",
            customer_id,
        )
        absorbed_messages: list[NormalizedIncomingMessage] = []
        for r in rows:
            p = r["payload"]
            if isinstance(p, str):
                p = json.loads(p)
            absorbed_messages.append(NormalizedIncomingMessage.model_validate(p))
        return absorbed_messages

    async def stage_response(self, inbound_id: int, response: NormalizedOutgoingResponse) -> None:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """UPDATE grocer_internal.inbound_messages
                       SET status = 'PROCESSED', processed_at = now()
                       WHERE id = $1 AND status = 'PROCESSING'
                       RETURNING customer_id""",
                    inbound_id,
                )
                if row is None:
                    raise RuntimeError("Inbound message is not being processed.")
                await connection.execute(
                    """INSERT INTO grocer_internal.outbound_messages
                       (inbound_id, customer_id, payload) VALUES ($1, $2, $3::jsonb)""",
                    inbound_id, row["customer_id"], response.model_dump_json(),
                )

    async def mark_processing_failed(self, inbound_id: int) -> None:
        """Surface an uncertain action without rerunning it or blocking later input."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """SELECT payload FROM grocer_internal.inbound_messages
                       WHERE id = $1 AND status = 'PROCESSING' FOR UPDATE""",
                    inbound_id,
                )
                if row is None:
                    return
                await self._complete_uncertain(connection, inbound_id, row["payload"])

    async def heartbeat_processing(self, inbound_id: int) -> None:
        await self.pool.execute(
            "UPDATE grocer_internal.inbound_messages SET claimed_at=now() WHERE id=$1 AND status='PROCESSING'",
            inbound_id,
        )

    async def recover_stale_processing(self) -> int:
        """Resolve abandoned claims after their worker lease expires."""
        recovered = 0
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                rows = await connection.fetch(
                    """SELECT id, payload FROM grocer_internal.inbound_messages
                       WHERE status='PROCESSING' AND claimed_at < now()-interval '5 minutes'
                       ORDER BY claimed_at LIMIT 20 FOR UPDATE SKIP LOCKED"""
                )
                for row in rows:
                    await self._complete_uncertain(connection, row["id"], row["payload"])
                    recovered += 1
        return recovered

    async def claim_outbound(self) -> tuple[int, str, NormalizedOutgoingResponse] | None:
        row = await self.pool.fetchrow(
            """WITH candidate AS (
                   SELECT o.id FROM grocer_internal.outbound_messages o
                   WHERE o.status = 'QUEUED'
                     AND NOT EXISTS (
                       SELECT 1 FROM grocer_internal.outbound_messages earlier
                       WHERE earlier.customer_id = o.customer_id AND earlier.id < o.id
                         AND earlier.status IN ('QUEUED', 'SENDING')
                     )
                   ORDER BY o.id LIMIT 1 FOR UPDATE SKIP LOCKED
               )
               UPDATE grocer_internal.outbound_messages o
               SET status = 'SENDING', sending_started_at = now()
               FROM candidate WHERE o.id = candidate.id
               RETURNING o.id, o.customer_id, o.payload"""
        )
        if row is None:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return row["id"], row["customer_id"], NormalizedOutgoingResponse.model_validate(payload)

    async def mark_outbound(self, outbound_id: int, delivered: bool) -> None:
        await self.pool.execute(
            """UPDATE grocer_internal.outbound_messages
               SET status = $2, sent_at = CASE WHEN $2 = 'SENT' THEN now() ELSE NULL END
               WHERE id = $1 AND status = 'SENDING'""",
            outbound_id, "SENT" if delivered else "UNKNOWN",
        )

    async def recover_stale_outbound(self) -> int:
        """Record an abandoned Meta send as uncertain; never resend it blindly."""
        result = await self.pool.execute(
            """UPDATE grocer_internal.outbound_messages SET status='UNKNOWN'
               WHERE status='SENDING' AND sending_started_at < now()-interval '2 minutes'"""
        )
        return int(result.removeprefix("UPDATE "))

    async def counts(self) -> dict[str, int]:
        row = await self.pool.fetchrow(
            """SELECT
                 (SELECT count(*) FROM grocer_internal.inbound_messages
                   WHERE status IN ('PROCESSING', 'NEEDS_REVIEW')) AS unsettled_inbound,
                 (SELECT count(*) FROM grocer_internal.outbound_messages
                   WHERE status IN ('SENDING', 'UNKNOWN')) AS unsettled_outbound"""
        )
        return {key: int(row[key]) for key in ("unsettled_inbound", "unsettled_outbound")}

    async def response_for_message(self, message_id: str) -> tuple[str, NormalizedOutgoingResponse] | None:
        row = await self.pool.fetchrow(
            """SELECT o.status, o.payload FROM grocer_internal.inbound_messages i
               JOIN grocer_internal.outbound_messages o ON o.inbound_id=i.id
               WHERE i.message_id=$1""",
            message_id,
        )
        if row is None:
            return None
        payload = row["payload"]
        return row["status"], NormalizedOutgoingResponse.model_validate(
            json.loads(payload) if isinstance(payload, str) else payload
        )

    async def purge_customer(self, customer_id: str) -> None:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT id FROM grocer_internal.inbound_messages WHERE customer_id = $1 FOR UPDATE", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.outbound_messages WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.inbound_messages WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.connect_tickets WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.task_state WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.replenishment WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.oauth_tokens WHERE customer_id = $1", customer_id
                )
                await connection.execute(
                    """DELETE FROM grocer_internal.checkout_attempts
                       WHERE customer_id = $1 AND status NOT IN
                       ('IN_FLIGHT', 'UNKNOWN', 'PAYMENT_PENDING', 'PARTIAL')""",
                    customer_id,
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.privacy_deletions WHERE customer_id = $1", customer_id
                )

    async def request_deletion(self, customer_id: str) -> None:
        await self.pool.execute(
            """INSERT INTO grocer_internal.privacy_deletions (customer_id)
               VALUES ($1) ON CONFLICT (customer_id) DO NOTHING""",
            customer_id,
        )

    async def process_deletions(self, engine: Any) -> None:
        from backend.integrations.commerce.token_vault import default_token_vault

        rows = await self.pool.fetch(
            """SELECT d.customer_id FROM grocer_internal.privacy_deletions d
               WHERE NOT EXISTS (
                   SELECT 1 FROM grocer_internal.outbound_messages o
                   WHERE o.customer_id = d.customer_id AND o.status = 'QUEUED')
                 AND NOT EXISTS (
                   SELECT 1 FROM grocer_internal.inbound_messages i
                   WHERE i.customer_id = d.customer_id AND i.status = 'PROCESSING'
                     AND i.received_at > now() - interval '5 minutes')
               LIMIT 10"""
        )
        for row in rows:
            await default_token_vault.revoke_token_durable(row["customer_id"])
            await engine.forget_customer(row["customer_id"])
            await self.purge_customer(row["customer_id"])

    async def delete_expired(self) -> None:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """DELETE FROM grocer_internal.outbound_messages
                       WHERE status IN ('SENT', 'UNKNOWN') AND created_at <= now() - interval '30 days'"""
                )
                await connection.execute(
                    """DELETE FROM grocer_internal.inbound_messages i
                       WHERE i.status IN ('PROCESSED', 'NEEDS_REVIEW')
                         AND i.received_at <= now() - interval '30 days'
                         AND NOT EXISTS (SELECT 1 FROM grocer_internal.outbound_messages o
                                         WHERE o.inbound_id = i.id)"""
                )
                await connection.execute(
                    "DELETE FROM grocer_internal.connect_tickets WHERE expires_at <= now()"
                )
