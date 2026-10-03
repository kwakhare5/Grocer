"""Durable reservation for non-idempotent live checkout."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

from backend.channels.models import ChannelType, NormalizedOutgoingResponse


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
            state = "PAYMENT_PENDING" if (
                result.get("order_id") and result.get("paas_id")
                and result.get("polling_interval_ms") and result.get("max_time_to_poll_ms")
            ) else "UNKNOWN"
        else:
            state = "PLACED"
        safe_result = {
            key: result.get(key)
            for key in ("success", "error", "status", "order_id", "grand_total",
                        "success_count", "failure_count", "paas_id", "orders",
                        "polling_interval_ms", "max_time_to_poll_ms")
        }
        updated = await self.pool.execute(
            """UPDATE grocer_internal.checkout_attempts
               SET status = $2, provider_order_id = $3, result = $4::jsonb,
                   next_payment_check_at = CASE WHEN $2 = 'PAYMENT_PENDING' THEN now() ELSE NULL END,
                   payment_deadline_at = CASE WHEN $2 = 'PAYMENT_PENDING'
                       THEN now() + make_interval(secs => ($5::double precision / 1000.0)) ELSE NULL END,
                   updated_at = now()
               WHERE id = $1 AND status = 'IN_FLIGHT'""",
            attempt_id, state, result.get("order_id"), json.dumps(safe_result),
            float(result.get("max_time_to_poll_ms") or 0),
        )
        if updated != "UPDATE 1":
            raise RuntimeError("Checkout attempt was not in flight.")

    async def reconcile_due_payment(self, commerce: Any) -> int:
        """Advance one durable UPI payment using the provider's status and poll window."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """SELECT a.id, a.customer_id, a.provider_order_id, a.result,
                              payment_deadline_at, next_payment_check_at
                       FROM grocer_internal.checkout_attempts a
                       WHERE a.status='PAYMENT_PENDING'
                         AND (a.next_payment_check_at IS NULL OR a.next_payment_check_at <= now())
                         AND EXISTS (
                           SELECT 1 FROM grocer_internal.outbound_messages o
                           WHERE o.customer_id=a.customer_id AND o.inbound_id IS NOT NULL
                             AND o.created_at >= a.created_at AND o.status IN ('SENT', 'UNKNOWN')
                         )
                       ORDER BY next_payment_check_at NULLS FIRST LIMIT 1
                       FOR UPDATE SKIP LOCKED"""
                )
                if row is None:
                    return 0
                result = row["result"]
                if isinstance(result, str):
                    result = json.loads(result)
                order_id = result.get("order_id")
                paas_id = result.get("paas_id")
                interval_ms = max(10000, int(result.get("polling_interval_ms") or 0))
                deadline = row["payment_deadline_at"]
                status = "UNKNOWN"
                notice = "I could not verify your payment outcome. Please check this order in Swiggy before trying again."
                payment_status = None
                if order_id and paas_id:
                    try:
                        with commerce.customer_scope(row["customer_id"]):
                            payment_status = await commerce.check_payment_status(paas_id, order_id)
                    except Exception:
                        if deadline is not None and await connection.fetchval("SELECT now() < $1", deadline):
                            await connection.execute(
                                """UPDATE grocer_internal.checkout_attempts
                                   SET next_payment_check_at=now()+make_interval(secs => $2::double precision),
                                       updated_at=now() WHERE id=$1""",
                                row["id"], interval_ms / 1000.0,
                            )
                            return 1
                    else:
                        raw = (payment_status.status or "").casefold()
                        if payment_status.terminal and payment_status.is_terminal_success:
                            if payment_status.confirmed:
                                status = "PLACED"
                            else:
                                try:
                                    with commerce.customer_scope(row["customer_id"]):
                                        confirmed = await commerce.confirm_order(order_id, paas_id)
                                    if confirmed.status == "ORDER_PLACED":
                                        status = "PLACED"
                                except Exception:
                                    pass
                            notice = (
                                f"Swiggy confirmed your order {order_id}. You can ask me to track it."
                                if status == "PLACED" else
                                f"Payment may have succeeded for order {order_id}, but I could not verify placement. "
                                "Please check Swiggy before trying again."
                            )
                        elif payment_status.terminal and payment_status.is_terminal_failure:
                            if raw in {"refund-initiated", "cancelled", "canceled"}:
                                notice = (f"Swiggy reported {raw} for order {order_id}. "
                                          "Please check the payment or refund status in Swiggy before trying again.")
                            else:
                                status = "PAYMENT_FAILED"
                                notice = (f"Swiggy reported {raw or 'payment failure'} for order {order_id}. "
                                          "The order was not confirmed. Please review your basket before retrying.")
                        elif not payment_status.terminal and deadline is not None:
                            if await connection.fetchval("SELECT now() < $1", deadline):
                                await connection.execute(
                                    """UPDATE grocer_internal.checkout_attempts
                                       SET next_payment_check_at=now()+make_interval(secs => $2::double precision),
                                           updated_at=now() WHERE id=$1""",
                                    row["id"], interval_ms / 1000.0,
                                )
                                return 1
                            try:
                                with commerce.customer_scope(row["customer_id"]):
                                    confirmed = await commerce.confirm_order(order_id, paas_id)
                                if confirmed.status == "ORDER_PLACED":
                                    status = "PLACED"
                                    notice = f"Swiggy confirmed your order {order_id}. You can ask me to track it."
                            except Exception:
                                pass
                await connection.execute(
                    """UPDATE grocer_internal.checkout_attempts
                       SET status=$2, next_payment_check_at=NULL, updated_at=now(),
                           result=jsonb_set(COALESCE(result, '{}'::jsonb), '{payment_status}', to_jsonb($3::text))
                       WHERE id=$1""",
                    row["id"], status, payment_status.status if payment_status else "unverified",
                )
                sender = await connection.fetchval(
                    """SELECT payload->>'sender_id' FROM grocer_internal.inbound_messages
                       WHERE customer_id=$1 ORDER BY id DESC LIMIT 1""",
                    row["customer_id"],
                )
                if sender:
                    response = NormalizedOutgoingResponse(
                        recipient_id=sender, channel=ChannelType.WHATSAPP,
                        text=notice, conversation_state="ORDER_PLACED" if status == "PLACED" else "NEEDS_DECISION",
                        order_id=order_id if status == "PLACED" else None,
                    )
                    await connection.execute(
                        """INSERT INTO grocer_internal.outbound_messages
                           (inbound_id, customer_id, payload, payment_attempt_id)
                           VALUES (NULL, $1, $2::jsonb, $3)
                           ON CONFLICT DO NOTHING""",
                        row["customer_id"], response.model_dump_json(), row["id"],
                    )
                return 1
