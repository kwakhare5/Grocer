"""Tracking and order status handlers for GrocerOrchestrator (Spec Section 12, Phase 6).

Handles:
- Observing and advancing pending UPI/gateway payment status (without tight polling loops)
- Reading itemized order details from provider
- Reading live rider and ETA delivery status
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from backend.integrations.commerce.exceptions import CommerceError
from backend.intent.session import ConversationState
from backend.intent.stages import (
    _msg_failed,
    _msg_ordered,
    _msg_payment_pending,
)

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


async def handle_payment_status(
    orchestrator: GrocerOrchestrator, session_id: str
) -> OrchestratorTurnResult:
    """Observe and advance a pending payment without tight-loop polling."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    async with orchestrator._store.lock_for(session_id):
        session = orchestrator._store.get(session_id)
        if session is None:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("session not found"),
                events=["SESSION_NOT_FOUND"],
            )
        if (
            session.conversation_state != ConversationState.PAYMENT_PENDING
            or not session.payment_paas_id
        ):
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="There is no pending payment to check.",
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=session.payment_status,
                events=["NO_PENDING_PAYMENT"],
            )

        now = datetime.now(timezone.utc)
        if session.payment_poll_deadline and now >= session.payment_poll_deadline:
            events = ["PAYMENT_POLL_CAP_CONFIRM_ATTEMPTED"]
            session.payment_poll_deadline = None
            if not session.order_id:
                session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
                orchestrator._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                    user_message=(
                        "The payment polling window ended without enough provider "
                        "data to finalize. I will not retry checkout or claim success."
                    ),
                    order_total=session.order_total,
                    payment_status=session.payment_status,
                    events=events + ["PAYMENT_POLL_CAP_CONFIRM_UNKNOWN"],
                )
            try:
                with orchestrator._port.customer_scope(session.customer_id):
                    order = await orchestrator._port.confirm_order(
                        session.order_id,
                        session.payment_paas_id,
                    )
            except Exception:
                session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
                orchestrator._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                    user_message=(
                        "The payment finalization outcome is unknown. I will not "
                        "retry checkout or claim success."
                    ),
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=session.payment_status,
                    events=events + ["PAYMENT_POLL_CAP_CONFIRM_UNKNOWN"],
                )
            return orchestrator._apply_order_result(session, order, events)
        if session.payment_next_poll_at and now < session.payment_next_poll_at:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.PAYMENT_PENDING,
                user_message=_msg_payment_pending(session.order_id, session.payment_url),
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=session.payment_status,
                payment_url=session.payment_url,
                events=["PAYMENT_POLL_DEFERRED"],
            )

        with orchestrator._port.customer_scope(session.customer_id):
            payment = await orchestrator._port.check_payment_status(
                session.payment_paas_id,
                session.order_id,
            )
        session.payment_status = payment.normalized_status
        if payment.order_id:
            session.order_id = payment.order_id
        events = [f"PAYMENT_STATUS_{payment.normalized_status}"]

        if payment.normalized_status == "PAYMENT_PENDING":
            if session.payment_polling_interval_ms:
                session.payment_next_poll_at = now + timedelta(
                    milliseconds=session.payment_polling_interval_ms
                )
            orchestrator._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.PAYMENT_PENDING,
                user_message=_msg_payment_pending(session.order_id, session.payment_url),
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=payment.normalized_status,
                payment_url=session.payment_url,
                events=events,
            )
        if payment.normalized_status == "PAYMENT_FAILED":
            session.conversation_state = ConversationState.PAYMENT_FAILED
            orchestrator._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.PAYMENT_FAILED,
                user_message="Payment failed or was cancelled. No successful order is being reported.",
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=payment.normalized_status,
                events=events,
            )
        if payment.normalized_status != "PAYMENT_CONFIRMED" or not session.order_id:
            session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
            orchestrator._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                user_message="Payment or order status is unknown. I will not retry checkout or claim success.",
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=payment.normalized_status,
                events=events,
            )

        if payment.confirmed:
            session.conversation_state = ConversationState.ORDERED
            orchestrator._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.ORDERED,
                user_message=_msg_ordered(session.order_id, session.order_total),
                order_id=session.order_id,
                order_total=session.order_total,
                payment_status=payment.normalized_status,
                events=events + ["ORDER_CONFIRMED_BY_PAYMENT_STATUS"],
            )

        with orchestrator._port.customer_scope(session.customer_id):
            order = await orchestrator._port.confirm_order(
                session.order_id, session.payment_paas_id
            )
        return orchestrator._apply_order_result(session, order, events + ["ORDER_CONFIRM_ATTEMPTED"])


async def handle_order_details(
    orchestrator: GrocerOrchestrator, session_id: str
) -> OrchestratorTurnResult:
    """Read back provider order facts without synthesizing missing fields."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session = orchestrator._store.get(session_id)
    if session is None or not session.order_id:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=(
                session.conversation_state if session else ConversationState.FAILED
            ),
            user_message="I do not have an order ID for this session.",
            events=["ORDER_DETAILS_UNAVAILABLE"],
        )
    try:
        with orchestrator._port.customer_scope(session.customer_id):
            details = await orchestrator._port.get_order_details(session.order_id)
    except CommerceError:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message="Order details are unavailable from the commerce provider right now.",
            order_id=session.order_id,
            order_total=session.order_total,
            events=["ORDER_DETAILS_UNAVAILABLE"],
        )

    facts = [
        f"{item.quantity}× {item.name}"
        for item in details.items
        if item.removed is not True
    ]
    parts = [f"Order {details.order_id}"]
    if details.raw_status:
        parts.append(f"status: {details.raw_status}")
    if facts:
        parts.append("items: " + ", ".join(facts))
    if details.total_bill is not None:
        parts.append(f"total: ₹{details.total_bill:,.0f}")
    return OrchestratorTurnResult(
        session_id=session_id,
        conversation_state=session.conversation_state,
        user_message=". ".join(parts) + ".",
        order_id=details.order_id,
        order_total=details.total_bill,
        events=["ORDER_DETAILS_READ"],
    )


async def handle_delivery_status(
    orchestrator: GrocerOrchestrator, session_id: str
) -> OrchestratorTurnResult:
    """Prefer rich conversational tracking, with a coordinate-safe ETA fallback."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session = orchestrator._store.get(session_id)
    if session is None or not session.order_id or not session.address_id:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=(
                session.conversation_state if session else ConversationState.FAILED
            ),
            user_message="I do not have enough provider order data to check delivery.",
            events=["DELIVERY_STATUS_UNAVAILABLE"],
        )

    if (
        session.delivery_latitude is not None
        and session.delivery_longitude is not None
    ):
        try:
            with orchestrator._port.customer_scope(session.customer_id):
                tracking = await orchestrator._port.track_order(
                    session.order_id,
                    lat=session.delivery_latitude,
                    lng=session.delivery_longitude,
                )
        except Exception as exc:
            return orchestrator._provider_failure_result(session, exc, [])

        facts: list[str] = []
        if tracking.raw_status:
            facts.append(tracking.raw_status)
        if (
            tracking.status_message
            and tracking.status_message != tracking.raw_status
        ):
            facts.append(tracking.status_message)
        if tracking.sub_status_message:
            facts.append(tracking.sub_status_message)
        eta = tracking.eta_text
        if not eta and tracking.eta_minutes is not None:
            eta = f"ETA {tracking.eta_minutes} minutes"
        if eta:
            facts.append(eta)
        if tracking.store_name:
            store = tracking.store_name
            if tracking.store_address:
                store += f" ({tracking.store_address})"
            facts.append(f"Store: {store}")
        if tracking.delivery_address:
            label = (
                f"{tracking.delivery_address_label}: "
                if tracking.delivery_address_label
                else ""
            )
            facts.append(f"Delivery: {label}{tracking.delivery_address}")
        if tracking.rider_location:
            facts.append(
                "Rider location: "
                f"{tracking.rider_location.latitude:.5f}, "
                f"{tracking.rider_location.longitude:.5f}"
            )
        if tracking.items:
            facts.append(
                "Items: "
                + ", ".join(
                    f"{item.quantity}× {item.name}" for item in tracking.items
                )
            )
        if tracking.payment_message:
            payment = tracking.payment_message
            if tracking.payment_amount:
                payment += f" ({tracking.payment_amount})"
            facts.append(f"Payment: {payment}")
        message = (
            f"Order {tracking.order_id}: " + ". ".join(facts) + "."
            if facts
            else f"Order {tracking.order_id} has no new tracking status available."
        )
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message=message,
            order_id=tracking.order_id,
            order_total=session.order_total,
            events=["ORDER_TRACKING_READ"],
        )

    try:
        with orchestrator._port.customer_scope(session.customer_id):
            delivery = await orchestrator._port.get_delivery_status(
                session.order_id, session.address_id
            )
    except Exception as exc:
        return orchestrator._provider_failure_result(session, exc, [])

    facts = [delivery.status_text, delivery.eta_text]
    known = [fact for fact in facts if fact]
    fallback_note = (
        "Detailed rider tracking is unavailable because Swiggy has not returned "
        "delivery coordinates."
    )
    message = fallback_note
    if known:
        message += f" Order {delivery.order_id}: " + ". ".join(known) + "."
    else:
        message += f" Order {delivery.order_id} has no new delivery status available."
    return OrchestratorTurnResult(
        session_id=session_id,
        conversation_state=session.conversation_state,
        user_message=message,
        order_id=delivery.order_id,
        order_total=session.order_total,
        events=["ORDER_TRACKING_FALLBACK_DELIVERY_STATUS"],
    )
