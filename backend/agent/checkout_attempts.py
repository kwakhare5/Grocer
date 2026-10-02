"""Durable reservation for non-idempotent live checkout."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any


class PostgresCheckoutAttemptStore:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def start(
        self, customer_id: str, cart_id: str, address_id: str,
        fingerprint: str, total: float,
    ) -> str | None:
        attempt_id = str(uuid.uuid4())
        row = await self.pool.fetchval(
            """INSERT INTO grocer_internal.checkout_attempts
               (id, customer_id, cart_id, address_id, cart_fingerprint,
                approved_total, status)
               VALUES ($1, $2, $3, $4, $5, $6, 'IN_FLIGHT')
               ON CONFLICT DO NOTHING RETURNING id""",
            attempt_id, customer_id, cart_id, address_id, fingerprint, Decimal(str(total)),
        )
        return str(row) if row else None

    async def finish(self, attempt_id: str, result: dict[str, Any]) -> None:
        if not result.get("success"):
            state = "UNKNOWN" if (
                result.get("error") == "ORDER_STATE_UNKNOWN"
                or result.get("status") == "ORDER_STATE_UNKNOWN"
            ) else "FAILED"
        elif result.get("is_simulated") or result.get("status") == "REVIEW_COMPLETE":
            state = "REVIEW_COMPLETE"
        elif result.get("status") in ("PARTIAL", "PARTIAL_ORDER"):
            state = "PARTIAL"
        elif result.get("status") in ("PAYMENT_PENDING", "AWAITING_PAYMENT", "PAYMENT_CONFIRMED"):
            state = "PAYMENT_PENDING"
        else:
            state = "PLACED"
        safe_result = {
            key: result.get(key)
            for key in ("success", "error", "status", "order_id", "grand_total",
                        "success_count", "failure_count", "paas_id", "orders")
        }
        updated = await self.pool.execute(
            """UPDATE grocer_internal.checkout_attempts
               SET status = $2, provider_order_id = $3, result = $4::jsonb,
                   updated_at = now()
               WHERE id = $1 AND status = 'IN_FLIGHT'""",
            attempt_id, state, result.get("order_id"), json.dumps(safe_result),
        )
        if updated != "UPDATE 1":
            raise RuntimeError("Checkout attempt was not in flight.")
