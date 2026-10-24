"""Background payment status poller for Swiggy Instamart UPI orders.

Polls payment status every 15 seconds up to 10 minutes, verifies terminal completion,
persists order transitions in Postgres, and delivers WhatsApp notifications.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from backend.channels.models import ChannelType, InteractiveAction, NormalizedOutgoingResponse
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.channels.poller")

DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_MAX_POLL_SECONDS = 600  # 10 minutes


class PaymentPoller:
    """Crash-proof background poller tracking Swiggy UPI payments until confirmation or expiry."""

    def __init__(
        self,
        commerce: CommercePort,
        store: Optional[Any] = None,
        engine: Optional[Any] = None,
        interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS,
    ) -> None:
        self.commerce = commerce
        self.store = store
        self.engine = engine
        self.interval_seconds = interval_seconds
        self.max_poll_seconds = max_poll_seconds
        self._active_tasks: dict[str, asyncio.Task[Any]] = {}

    def start_polling(
        self,
        customer_id: str,
        order_id: str,
        paas_id: str,
        recipient_id: Optional[str] = None,
        custom_interval: Optional[int] = None,
        custom_max_duration: Optional[int] = None,
    ) -> asyncio.Task[Any]:
        """Spawn asynchronous poller for an in-flight checkout attempt."""
        task_key = f"{customer_id}:{order_id}"
        existing = self._active_tasks.get(task_key)
        if existing and not existing.done():
            logger.info("Poller already active for %s; reusing task.", task_key)
            return existing

        task = asyncio.create_task(
            self._poll_loop(
                customer_id=customer_id,
                order_id=order_id,
                paas_id=paas_id,
                recipient_id=recipient_id or customer_id,
                interval=custom_interval or self.interval_seconds,
                max_duration=custom_max_duration or self.max_poll_seconds,
            )
        )
        self._active_tasks[task_key] = task
        return task

    async def _poll_loop(
        self,
        customer_id: str,
        order_id: str,
        paas_id: str,
        recipient_id: str,
        interval: int,
        max_duration: int,
    ) -> bool:
        start_time = time.time()
        logger.info(
            "Starting payment poller for customer=%s order=%s paas=%s (interval=%ds, max=%ds)",
            customer_id, order_id, paas_id, interval, max_duration,
        )

        # In review simulation mode, verify immediately without waiting
        is_review_mode = order_id.startswith("sim_rev_") or getattr(self.commerce, "is_simulated", False)
        if is_review_mode and interval > 1:
            interval = 1

        while (time.time() - start_time) < max_duration:
            await asyncio.sleep(interval)
            try:
                status_res = await self.commerce.check_payment_status(paas_id=paas_id, order_id=order_id)
                norm_status = getattr(status_res, "normalized_status", None)
                is_success = (
                    norm_status == "PAYMENT_CONFIRMED"
                    or getattr(status_res, "is_terminal_success", False)
                    or getattr(status_res, "confirmed", False)
                )
                is_failure = (
                    norm_status == "PAYMENT_FAILED"
                    or getattr(status_res, "is_terminal_failure", False)
                )

                if is_success:
                    logger.info("Payment confirmed by Swiggy for order=%s customer=%s", order_id, customer_id)
                    await self._record_order_outcome(customer_id, order_id, "PLACED")
                    if self.engine:
                        sess = self.engine.get_session(customer_id)
                        if sess:
                            sess.conversation_state = "ORDER_PLACED"
                            sess.pending_approval = None

                    msg = NormalizedOutgoingResponse(
                        recipient_id=recipient_id,
                        channel=ChannelType.WHATSAPP,
                        text=(
                            f"🎉 *Payment Received!*\n\n"
                            f"Your Swiggy Instamart Order #{order_id} is confirmed and packing at your local store. 🚀\n\n"
                            "You can track live delivery updates in your Swiggy app."
                        ),
                        conversation_state="ORDER_PLACED",
                        order_id=order_id,
                    )
                    await default_whatsapp_adapter.send_response(msg)
                    return True

                elif is_failure:
                    logger.warning("Payment failed for order=%s customer=%s", order_id, customer_id)
                    await self._record_order_outcome(customer_id, order_id, "PAYMENT_FAILED")
                    msg = NormalizedOutgoingResponse(
                        recipient_id=recipient_id,
                        channel=ChannelType.WHATSAPP,
                        text=(
                            f"⚠️ *Payment Not Completed*\n\n"
                            f"The payment for Order #{order_id} was not completed on UPI. "
                            "Your basket is still saved. Tap below to review your items or try again."
                        ),
                        interactive_actions=[
                            InteractiveAction(action_type="button", id="modify_cart", title="Review Cart"),
                        ],
                        conversation_state="NEEDS_DECISION",
                        order_id=order_id,
                    )
                    await default_whatsapp_adapter.send_response(msg)
                    return False

            except Exception as exc:
                logger.warning("Poller probe error for order=%s: %s", order_id, exc)

        # 10-minute timeout / expiry
        logger.info("Payment window expired for order=%s customer=%s", order_id, customer_id)
        await self._record_order_outcome(customer_id, order_id, "PAYMENT_FAILED")
        msg = NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=ChannelType.WHATSAPP,
            text=(
                f"⏰ *Payment Window Expired*\n\n"
                f"The 10-minute payment window for Order #{order_id} has expired. "
                "Your basket is safely preserved. Tap below whenever you are ready to review or place your order!"
            ),
            interactive_actions=[
                InteractiveAction(action_type="button", id="modify_cart", title="Review Cart"),
            ],
            conversation_state="READY",
            order_id=order_id,
        )
        await default_whatsapp_adapter.send_response(msg)
        return False

    async def check_on_demand(
        self,
        customer_id: str,
        order_id: str,
        paas_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> NormalizedOutgoingResponse:
        """Immediate payment status probe triggered when customer taps 'Check Payment'."""
        eff_paas = paas_id or order_id
        try:
            status_res = await self.commerce.check_payment_status(paas_id=eff_paas, order_id=order_id)
            norm_status = getattr(status_res, "normalized_status", None)
            is_success = (
                norm_status == "PAYMENT_CONFIRMED"
                or getattr(status_res, "is_terminal_success", False)
                or getattr(status_res, "confirmed", False)
            )
            if is_success:
                await self._record_order_outcome(customer_id, order_id, "PLACED")
                if self.engine:
                    sess = self.engine.get_session(customer_id)
                    if sess:
                        sess.conversation_state = "ORDER_PLACED"
                return NormalizedOutgoingResponse(
                    recipient_id=recipient_id or customer_id,
                    channel=ChannelType.WHATSAPP,
                    text=(
                        f"🎉 *Payment Verified!*\n\n"
                        f"Your Swiggy Instamart Order #{order_id} is confirmed and packing at your local store. 🚀\n\n"
                        "You can track live delivery updates in your Swiggy app."
                    ),
                    conversation_state="ORDER_PLACED",
                    order_id=order_id,
                )
            elif norm_status == "PAYMENT_FAILED" or getattr(status_res, "is_terminal_failure", False):
                return NormalizedOutgoingResponse(
                    recipient_id=recipient_id or customer_id,
                    channel=ChannelType.WHATSAPP,
                    text=(
                        f"⚠️ *Payment Not Received*\n\n"
                        f"Swiggy has not received payment for Order #{order_id}. "
                        "Please check your UPI app or tap below to review your items."
                    ),
                    interactive_actions=[
                        InteractiveAction(action_type="button", id="modify_cart", title="Review Cart"),
                    ],
                    conversation_state="NEEDS_DECISION",
                    order_id=order_id,
                )
        except Exception as exc:
            logger.warning("On-demand payment check error: %s", exc)

        return NormalizedOutgoingResponse(
            recipient_id=recipient_id or customer_id,
            channel=ChannelType.WHATSAPP,
            text=(
                f"⏳ *Payment Still Pending*\n\n"
                f"We are waiting for UPI confirmation for Order #{order_id}. "
                "Once you approve the payment in Google Pay / PhonePe, we will confirm it automatically within seconds!"
            ),
            interactive_actions=[
                InteractiveAction(action_type="button", id=f"check_payment:{order_id}", title="Check Payment"),
                InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            ],
            conversation_state="AWAITING_PAYMENT",
            order_id=order_id,
        )

    async def _record_order_outcome(self, customer_id: str, order_id: str, status: str) -> None:
        """Update checkout_attempts table in PostgreSQL."""
        pool = getattr(self.store, "pool", None)
        if pool is not None:
            try:
                await pool.execute(
                    """UPDATE grocer_internal.checkout_attempts
                       SET status = $1, updated_at = now()
                       WHERE (provider_order_id = $2 OR id = $2) AND customer_id = $3""",
                    status, order_id, customer_id,
                )
            except Exception as exc:
                logger.warning("Could not update checkout attempt status in Postgres: %s", exc)

    async def recover_pending_attempts(self) -> int:
        """Resume polling for in-flight checkout attempts after server restart."""
        pool = getattr(self.store, "pool", None)
        if pool is None:
            return 0
        try:
            rows = await pool.fetch(
                """SELECT id, customer_id, provider_order_id, result, created_at
                   FROM grocer_internal.checkout_attempts
                   WHERE status = 'PAYMENT_PENDING'
                     AND created_at > now() - interval '10 minutes'"""
            )
            count = 0
            for r in rows:
                cid = r["customer_id"]
                oid = r["provider_order_id"] or r["id"]
                res = r.get("result") or {}
                paas_id = res.get("paas_id") or oid
                recip = (res.get("recipient_id") if isinstance(res, dict) else None) or cid
                elapsed = (time.time() - r["created_at"].timestamp()) if r["created_at"] else 0
                remaining = max(10, int(self.max_poll_seconds - elapsed))
                self.start_polling(cid, oid, paas_id, recipient_id=recip, custom_max_duration=remaining)
                count += 1
            if count:
                logger.info("Recovered %d in-flight payment pollers from Postgres.", count)
            return count
        except Exception as exc:
            logger.warning("Could not recover pending payment attempts from Postgres: %s", exc)
            return 0
