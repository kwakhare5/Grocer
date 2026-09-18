"""Payment flow handlers for GrocerOrchestrator (Spec Section 12, Phase 6).

Handles:
- Presenting grouped payment options (UPI intent, UPI QR, COD, NetBanking)
- Resolving and validating user payment choices
- Updating customer payment preferences and transitioning to basket confirmation
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from backend.integrations.commerce.models import PaymentOption
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    PendingPaymentChoice,
)
from backend.intent.stages import (
    _group_payment_options,
    _msg_failed,
    _msg_payment_choice,
    match_payment_choice,
)

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


def payment_choice_result(
    orchestrator: GrocerOrchestrator,
    session: OrchestratorSession,
    options: list[PaymentOption],
    recovery_notes: list[str],
    events: list[str],
    *,
    pending: Optional[PendingPaymentChoice] = None,
) -> OrchestratorTurnResult:
    """Persist and render a live provider payment choice without preselecting."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    grouped = _group_payment_options(options)
    payment_choice = pending or PendingPaymentChoice(
        options=grouped,
        raw_options=options,
        recovery_notes=recovery_notes,
    )
    session.pending_confirmation = None
    session.pending_payment_choice = payment_choice
    session.conversation_state = ConversationState.NEEDS_DECISION
    orchestrator._store.save(session)
    return OrchestratorTurnResult(
        session_id=session.session_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        user_message=_msg_payment_choice(payment_choice.options),
        payment_options=payment_choice.options,
        payment_choice_nonce=payment_choice.nonce,
        events=events,
    )


async def handle_payment_choice(
    orchestrator: GrocerOrchestrator,
    session_id: str,
    payment_option_id: str,
    payment_choice_nonce: Optional[str],
) -> OrchestratorTurnResult:
    """Bind an exact live provider payment option before basket confirmation."""
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

        pending = session.pending_payment_choice
        if (
            session.conversation_state != ConversationState.NEEDS_DECISION
            or pending is None
        ):
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="There is no pending payment choice.",
                events=["NO_PENDING_PAYMENT_CHOICE"],
            )
        if payment_choice_nonce != pending.nonce:
            return orchestrator._payment_choice_result(
                session,
                pending.options,
                pending.recovery_notes,
                ["STALE_PAYMENT_CHOICE_REJECTED"],
                pending=pending,
            )

        all_candidates = list(pending.options) + list(getattr(pending, "raw_options", []))
        selected = match_payment_choice(payment_option_id, all_candidates)
        if selected is None:
            return orchestrator._payment_choice_result(
                session,
                pending.options,
                pending.recovery_notes,
                ["PAYMENT_CHOICE_REJECTED"],
                pending=pending,
            )

        orchestrator._customer_payment_preferences[session.customer_id] = selected.id or selected.method
        session.selected_payment_method = selected.method
        session.selected_payment_option_id = selected.id
        session.selected_payment_option_kind = selected.kind
        session.selected_payment_option_label = selected.label

        contract = session.intent_contract
        if contract is None:
            return orchestrator._handle_failed(
                session,
                "no active intent contract",
                ["PAYMENT_CHOICE_REJECTED"],
            )
        cart_id = session.cart_id or f"cart-{session_id}"
        try:
            with orchestrator._port.customer_scope(session.customer_id):
                cart = await orchestrator._port.get_cart(cart_id)
        except Exception as exc:
            return orchestrator._provider_failure_result(session, exc, [])

        return await orchestrator._make_awaiting_confirmation(
            session,
            contract,
            cart,
            pending.recovery_notes,
            [f"PAYMENT_OPTION_SELECTED id={payment_option_id}"],
            preferred_payment_option_id=payment_option_id,
        )
