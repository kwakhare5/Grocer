"""Order confirmation and checkout execution for GrocerOrchestrator (Spec Section 12, Phase 6).

Handles:
- Transition to AWAITING_CONFIRMATION with immutable basket fingerprint snapshot
- Server-side gated checkout execution with lock acquisition and pre-checkout verification
- Normalizing and applying provider order results to session
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from backend.config import settings
from backend.integrations.commerce.exceptions import (
    OrderStateUnknownError,
    UnconfirmedCheckoutError,
)
from backend.integrations.commerce.models import (
    CommerceOrderResult,
    PaymentOption,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.intent.models import IntentContract
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    confirmation_fingerprint,
    create_confirmation_snapshot,
)
from backend.intent.stages import (
    _build_basket_summary,
    _msg_confirmation_basket,
    _msg_failed,
    _msg_ordered,
    _msg_payment_pending,
    _payment_option_key,
)
from backend.intent.verifier import VerificationStatus

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


def apply_order_result(
    orchestrator: GrocerOrchestrator,
    session: OrchestratorSession,
    order: CommerceOrderResult,
    events: list[str],
) -> OrchestratorTurnResult:
    """Map a normalized provider result without collapsing uncertain states."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session.order_id = order.order_id
    session.order_total = order.grand_total
    session.payment_status = order.status
    session.payment_paas_id = order.paas_id
    session.payment_transaction_id = order.transaction_id
    session.payment_url = order.bridge_url or order.upi_intent_url
    session.payment_polling_interval_ms = order.polling_interval_ms
    session.payment_max_time_ms = order.max_time_to_poll_ms
    now = datetime.now(timezone.utc)
    session.payment_next_poll_at = (
        now + timedelta(milliseconds=order.polling_interval_ms)
        if order.polling_interval_ms
        else None
    )
    session.payment_poll_deadline = (
        now + timedelta(milliseconds=order.max_time_to_poll_ms)
        if order.max_time_to_poll_ms
        else None
    )
    if order.delivery_address is not None:
        session.delivery_latitude = order.delivery_address.latitude
        session.delivery_longitude = order.delivery_address.longitude
    session.child_orders = [child.model_dump(mode="json") for child in order.orders]

    if order.status == "PAYMENT_PENDING":
        session.conversation_state = ConversationState.PAYMENT_PENDING
        message = _msg_payment_pending(order.order_id, session.payment_url)
        events.append("PAYMENT_PENDING")
    elif order.status == "PARTIAL_ORDER":
        session.conversation_state = ConversationState.PARTIAL_ORDER
        failed_children = [
            f"{child.order_id or 'unknown store'}: {child.error}"
            for child in order.orders
            if child.status == "FAILED" and child.error
        ]
        detail = f" Failed: {'; '.join(failed_children)}." if failed_children else ""
        message = (
            "Only part of the order was placed. Review the individual order results before continuing."
            + detail
        )
        events.append("CHECKOUT_PARTIAL")
    elif order.status == "REVIEW_COMPLETE":
        session.conversation_state = ConversationState.REVIEW_COMPLETE
        message = order.provider_message or (
            "Your basket passed the final review. This submission environment did not place "
            "or charge a Swiggy order."
        )
        events.append("REVIEW_CHECKOUT_COMPLETED")
    elif order.status == "ORDER_PLACED" and order.order_id:
        session.conversation_state = ConversationState.ORDERED
        message = order.provider_message or _msg_ordered(order.order_id, order.grand_total)
        events.append(f"CHECKOUT_SUCCEEDED order_id={order.order_id}")
    elif order.status == "FAILED":
        session.conversation_state = ConversationState.PAYMENT_FAILED
        message = "Checkout failed. No successful order is being reported."
        events.append("CHECKOUT_FAILED")
    else:
        session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
        message = "The checkout outcome is unknown. I will not retry or claim that an order was placed."
        events.append("CHECKOUT_STATE_UNKNOWN")

    orchestrator._store.save(session)
    return OrchestratorTurnResult(
        session_id=session.session_id,
        conversation_state=session.conversation_state,
        user_message=message,
        order_id=order.order_id,
        order_total=order.grand_total,
        payment_status=session.payment_status,
        payment_url=session.payment_url,
        child_orders=order.orders,
        events=events,
    )


async def make_awaiting_confirmation(
    orchestrator: GrocerOrchestrator,
    session: OrchestratorSession,
    contract: IntentContract,
    cart: Any,
    recovery_notes: list[str],
    events: list[str],
    *,
    preferred_payment_method: Optional[str] = None,
    preferred_payment_option_id: Optional[str] = None,
) -> OrchestratorTurnResult:
    """Transition to AWAITING_CONFIRMATION and return the full result."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    if not cart or not getattr(cart, "items", None) or getattr(cart, "grand_total", 0.0) <= 0:
        session.conversation_state = ConversationState.BUILDING
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.BUILDING,
            user_message="Your basket is currently empty. What would you like to add?",
            events=events + ["EMPTY_CART_CONFIRMATION_BLOCKED"],
        )

    address_id = session.address_id or cart.address_id
    try:
        with orchestrator._port.customer_scope(session.customer_id):
            payment_options = [
                option
                for option in await orchestrator._port.get_payment_options(
                    cart_id=cart.cart_id,
                    address_id=address_id,
                )
                if option.is_available
            ]
    except Exception as exc:
        return orchestrator._provider_failure_result(session, exc, events)

    if not payment_options:
        session.pending_payment_choice = None
        return orchestrator._handle_failed(
            session,
            "no payment option is currently available",
            events + ["PAYMENT_OPTIONS_UNAVAILABLE"],
        )

    if preferred_payment_option_id is None and preferred_payment_method is None:
        if session.selected_payment_option_id:
            preferred_payment_option_id = session.selected_payment_option_id
        elif session.selected_payment_method:
            preferred_payment_method = session.selected_payment_method
        elif session.customer_id in orchestrator._customer_payment_preferences:
            preferred_payment_option_id = orchestrator._customer_payment_preferences[session.customer_id]

    selected: Optional[PaymentOption] = None
    if preferred_payment_option_id is not None:
        selected = next(
            (
                option
                for option in payment_options
                if _payment_option_key(option) == preferred_payment_option_id
                or (option.id and option.id.casefold() == preferred_payment_option_id.casefold())
                or option.method.casefold() == preferred_payment_option_id.casefold()
            ),
            None,
        )
        if selected is None:
            return orchestrator._payment_choice_result(
                session,
                payment_options,
                recovery_notes,
                events + ["PAYMENT_METHOD_UNAVAILABLE"],
            )
    elif preferred_payment_method is not None:
        requested = preferred_payment_method.casefold()
        matching = [
            option
            for option in payment_options
            if option.method.casefold() == requested
            or (option.id is not None and option.id.casefold() == requested)
            or requested in option.label.casefold()
        ]
        if len(matching) == 1:
            selected = matching[0]
        elif len(matching) > 1:
            selected = matching[0]
        else:
            return orchestrator._payment_choice_result(
                session,
                payment_options,
                recovery_notes,
                events + ["PAYMENT_METHOD_UNAVAILABLE"],
            )
    elif len(payment_options) == 1:
        selected = payment_options[0]
    else:
        return orchestrator._payment_choice_result(
            session,
            payment_options,
            recovery_notes,
            events + ["PAYMENT_CHOICE_REQUIRED"],
        )

    assert selected is not None

    session.selected_payment_method = selected.method
    session.selected_payment_option_id = selected.id
    session.selected_payment_option_kind = selected.kind
    session.selected_payment_option_label = selected.label
    orchestrator._customer_payment_preferences[session.customer_id] = selected.id or selected.method

    snapshot = create_confirmation_snapshot(
        cart,
        contract,
        address_id,
        selected.method,
        selected.id,
        selected.kind,
    )
    session.pending_payment_choice = None
    session.pending_confirmation = snapshot
    session.conversation_state = ConversationState.AWAITING_CONFIRMATION
    orchestrator._store.save(session)

    basket = _build_basket_summary(
        cart,
        contract,
        recovery_notes,
        confirmation_nonce=snapshot.nonce,
        confirmation_expires_at=snapshot.expires_at,
        payment_options=payment_options,
        address_display=session.address_display,
        selected_payment_method=selected.method,
        selected_payment_option_id=selected.id,
        selected_payment_option_kind=selected.kind,
        selected_payment_option_label=selected.label,
    )
    msg = _msg_confirmation_basket(basket)

    events.append("AWAITING_CONFIRMATION")
    return OrchestratorTurnResult(
        session_id=session.session_id,
        conversation_state=ConversationState.AWAITING_CONFIRMATION,
        user_message=msg,
        basket_summary=basket,
        requires_confirmation=True,
        events=events,
    )


async def handle_confirm_locked(
    orchestrator: GrocerOrchestrator,
    *,
    session_id: str,
    payment_method: str,
    address_id: Optional[str],
    confirmation_nonce: Optional[str],
) -> OrchestratorTurnResult:
    """Execute checkout inside session lock after validating explicit confirmation."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session = orchestrator._store.get(session_id)
    if session is None:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed("session not found"),
            events=["SESSION_NOT_FOUND"],
        )

    if session.conversation_state == ConversationState.ORDERED and session.order_id:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.ORDERED,
            user_message=_msg_ordered(session.order_id, session.order_total),
            order_id=session.order_id,
            order_total=session.order_total,
            events=["CHECKOUT_ALREADY_COMPLETED"],
        )

    if session.conversation_state != ConversationState.AWAITING_CONFIRMATION:
        raise UnconfirmedCheckoutError(
            f"Checkout requires session in AWAITING_CONFIRMATION state, "
            f"current: {session.conversation_state.value}"
        )

    contract = session.intent_contract
    pending = session.pending_confirmation
    if contract is None or pending is None:
        raise UnconfirmedCheckoutError("Checkout requires a current basket approval")
    if confirmation_nonce != pending.nonce or pending.consumed_at is not None or pending.is_expired:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.AWAITING_CONFIRMATION,
            user_message="That confirmation is stale or invalid. Please review the current basket.",
            requires_confirmation=True,
            events=["CONFIRMATION_REJECTED"],
        )
    cart_id = session.cart_id or f"cart-{session_id}"
    effective_address = address_id or session.address_id or f"addr-{session.customer_id}"
    events: list[str] = ["CHECKOUT_INITIATED"]

    try:
        with orchestrator._port.customer_scope(session.customer_id):
            cart = await orchestrator._port.get_cart(cart_id)
    except Exception as exc:
        session.conversation_state = ConversationState.FAILED
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(f"cart fetch failed: {exc}"),
            events=events,
        )

    if not cart or not getattr(cart, "items", None) or getattr(cart, "grand_total", 0.0) <= 0:
        session.conversation_state = ConversationState.BUILDING
        orchestrator._store.save(session)
        raise UnconfirmedCheckoutError("Cannot checkout an empty basket.")

    current_fingerprint = confirmation_fingerprint(
        cart,
        contract,
        effective_address,
        pending.payment_method,
        pending.payment_option_id,
        pending.payment_option_kind,
    )
    if current_fingerprint != pending.fingerprint:
        return await orchestrator._make_awaiting_confirmation(
            session,
            contract,
            cart,
            ["The basket changed after it was shown; please review it again."],
            events + ["CONFIRMATION_INVALIDATED_BASKET_CHANGED"],
        )

    if payment_method != pending.payment_method:
        return await orchestrator._make_awaiting_confirmation(
            session,
            contract,
            cart,
            ["Payment method changed; review the basket and payment choice again."],
            events + ["CONFIRMATION_INVALIDATED_PAYMENT_CHANGED"],
            preferred_payment_method=payment_method,
        )

    if contract is not None:
        pre_check = orchestrator._verifier.verify_checkout(
            contract=contract,
            cart=cart,
            explicit_confirmation=True,
        )
        events.append(f"PRE_CHECKOUT_VERIFY_{pre_check.status.value.upper()}")
        if pre_check.status != VerificationStatus.PASS:
            session.pending_confirmation = None
            session.conversation_state = ConversationState.FAILED
            reason = (
                pre_check.violations[0].detail
                if pre_check.violations
                else "pre-checkout verification failed"
            )
            orchestrator._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(reason),
                events=events,
            )

    pending.consumed_at = datetime.now(timezone.utc)
    orchestrator._store.save(session)

    review_checkout = (
        settings.CHECKOUT_MODE == "review"
        and isinstance(orchestrator._port, SwiggyMCPAdapter)
    )
    
    try:
        if review_checkout:
            order = CommerceOrderResult(
                status="REVIEW_COMPLETE",
                raw_status="review_complete",
                success=True,
                grand_total=cart.grand_total,
                provider_message=(
                    "Your basket passed the final review. This submission environment did not "
                    "place or charge a Swiggy order."
                ),
            )
            events.append("REVIEW_CHECKOUT_COMPLETED")
        else:
            with orchestrator._port.customer_scope(session.customer_id):
                order = await orchestrator._port.checkout(
                    cart_id=cart_id,
                    payment_method=pending.payment_method,
                    explicit_confirmation=True,
                    address_id=effective_address,
                    payment_option_id=pending.payment_option_id,
                    payment_option_kind=pending.payment_option_kind,
                )
    except UnconfirmedCheckoutError:
        raise
    except OrderStateUnknownError:
        session.pending_confirmation = None
        session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
            user_message="The checkout outcome is unknown. I will not retry or claim that an order was placed.",
            events=events + ["CHECKOUT_STATE_UNKNOWN"],
        )
    except Exception as exc:
        session.conversation_state = ConversationState.FAILED
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(str(exc)),
            events=events,
        )

    session.pending_confirmation = None
    return orchestrator._apply_order_result(session, order, events)
