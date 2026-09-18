"""Clarification choice resolution for GrocerOrchestrator (Spec Section 10 & 12).

Handles:
- Presenting clarification questions and candidate options when recovery needs user decision
- Validating and resolving user-chosen spin_id with intent verification
- Handling basket change requests to return session to BUILDING state
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
)
from backend.intent.recovery import RecoveryCandidate, RecoveryEngine, RecoveryOutcome, RecoveryState
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    PendingClarification,
)
from backend.intent.stages import (
    _candidates_to_options,
    _msg_clarification,
    _msg_failed,
    _targeted_recovery_query,
)
from backend.intent.verifier import VerificationResult, VerificationStatus

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


def handle_needs_decision(
    orchestrator: GrocerOrchestrator,
    session: OrchestratorSession,
    cart: CommerceCart,
    verification: VerificationResult,
    outcome: RecoveryOutcome,
    events: list[str],
) -> OrchestratorTurnResult:
    """Format and set pending clarification for user decision."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    candidates = outcome.candidates_for_user or []
    options = _candidates_to_options(candidates)
    item_name = (
        verification.violations[0].target
        if verification.violations
        else "an item"
    )
    question = outcome.message or (
        f"Your usual {item_name} is unavailable. Which alternative would you prefer?"
    )
    removes_spin_id = None
    intended_quantity = 1
    if outcome.recovery_actions:
        top_act = outcome.recovery_actions[0]
        removes_spin_id = top_act.removes_spin_id
        intended_quantity = max(1, top_act.quantity)
    else:
        matched_cart_item = next(
            (ci for ci in cart.items if item_name.lower() in ci.name.lower() or ci.name.lower() in item_name.lower()),
            None,
        )
        if matched_cart_item:
            removes_spin_id = matched_cart_item.spin_id
            intended_quantity = matched_cart_item.quantity

    session.pending_clarification = PendingClarification(
        item_name=item_name,
        candidates=candidates,
        clarification_question=question,
        removes_spin_id=removes_spin_id,
        intended_quantity=intended_quantity,
    )
    session.conversation_state = ConversationState.NEEDS_DECISION
    orchestrator._store.save(session)
    return OrchestratorTurnResult(
        session_id=session.session_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        user_message=_msg_clarification(question, options),
        clarification_options=options,
        clarification_nonce=session.pending_clarification.nonce,
        events=events,
    )


async def handle_change_request(
    orchestrator: GrocerOrchestrator, session_id: str
) -> OrchestratorTurnResult:
    """Invalidate checkout approval and return the session to an editable state."""
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
        session.pending_confirmation = None
        session.pending_payment_choice = None
        session.conversation_state = ConversationState.BUILDING
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.BUILDING,
            user_message="Tell me what you want to change in the basket.",
            events=["CONFIRMATION_CANCELLED"],
        )


async def handle_choice_locked(
    orchestrator: GrocerOrchestrator,
    *,
    session_id: str,
    chosen_spin_id: str,
    clarification_nonce: str,
) -> OrchestratorTurnResult:
    """Resolve a pending clarification inside session lock."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session = orchestrator._store.get(session_id)
    if session is None:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed("session not found"),
            events=["SESSION_NOT_FOUND"],
        )

    if (
        session.conversation_state != ConversationState.NEEDS_DECISION
        or not session.pending_clarification
    ):
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message="No pending decision. Please send a new grocery request.",
            events=["NO_PENDING_DECISION"],
        )

    pending = session.pending_clarification
    if clarification_nonce != pending.nonce:
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message="That choice is stale. Please use the latest options.",
            clarification_options=_candidates_to_options(pending.candidates),
            clarification_nonce=pending.nonce,
            events=["STALE_CHOICE_REJECTED"],
        )
    matching_candidate = next(
        (c for c in pending.candidates if c.spin_id == chosen_spin_id),
        None,
    )
    if matching_candidate is None:
        options = _candidates_to_options(pending.candidates)
        events = list(session.events) + [f"INVALID_CHOICE spin_id={chosen_spin_id}"]
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=(
                f"'{chosen_spin_id}' is not one of the available options. Please choose from:\n"
                + _msg_clarification(pending.clarification_question, options)
            ),
            clarification_options=options,
            clarification_nonce=pending.nonce,
            events=events,
        )

    events: list[str] = [f"USER_CHOICE spin_id={chosen_spin_id}"]
    contract = session.intent_contract
    if contract is None:
        session.conversation_state = ConversationState.FAILED
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed("no active intent contract"),
            events=events,
        )

    effective_address = session.address_id or f"addr-{session.customer_id}"
    cart_id = session.cart_id or f"cart-{session_id}"
    session.cart_id = cart_id

    try:
        with orchestrator._port.customer_scope(session.customer_id):
            current_cart = await orchestrator._port.get_cart(cart_id)
    except Exception as exc:
        session.conversation_state = ConversationState.FAILED
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(f"could not fetch cart: {exc}"),
            events=events,
        )

    quantity = pending.intended_quantity
    intent_item = next(
        (
            item
            for item in contract.items
            if item.name.lower() in pending.item_name.lower()
            or pending.item_name.lower() in item.name.lower()
        ),
        None,
    )
    if intent_item and contract.pack_size_rules.preferred_multiples:
        engine = RecoveryEngine(policy_engine=orchestrator._policy)
        multiple = engine._calculate_pack_multiple(intent_item, matching_candidate.pack_size)
        if multiple > 0:
            quantity = multiple

    removes_spin_id = pending.removes_spin_id
    if not removes_spin_id:
        matched = next(
            (
                ci
                for ci in current_cart.items
                if pending.item_name.lower() in ci.name.lower()
                or ci.name.lower() in pending.item_name.lower()
            ),
            None,
        )
        if matched:
            removes_spin_id = matched.spin_id

    updates: list[CartItemUpdate] = []
    replaced = False
    chosen_sku_id = matching_candidate.sku_id
    if not chosen_sku_id:
        try:
            with orchestrator._port.customer_scope(session.customer_id):
                search_query = matching_candidate.name or pending.item_name
                prods = await orchestrator._port.search_products(effective_address, search_query)
                for p in prods:
                    for v in p.variants:
                        if v.spin_id == chosen_spin_id and v.sku_id:
                            chosen_sku_id = v.sku_id
                            break
                    if chosen_sku_id:
                        break
        except Exception:
            pass

    for ci in current_cart.items:
        if removes_spin_id and ci.spin_id == removes_spin_id:
            updates.append(CartItemUpdate(spin_id=chosen_spin_id, sku_id=chosen_sku_id, quantity=quantity))
            replaced = True
        else:
            updates.append(CartItemUpdate(spin_id=ci.spin_id, sku_id=ci.sku_id, quantity=ci.quantity))

    if not replaced:
        updates.append(CartItemUpdate(spin_id=chosen_spin_id, sku_id=chosen_sku_id, quantity=quantity))

    try:
        with orchestrator._port.customer_scope(session.customer_id):
            cart = await orchestrator._port.update_cart(
                items=updates,
                cart_id=cart_id,
                address_id=effective_address,
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

    events.append(f"CART_UPDATED cart_id={cart_id}")

    if intent_item and intent_item.resolved_meaning:
        intent_item.resolved_meaning.status = "EXACT"
        intent_item.resolved_meaning.spin_id = chosen_spin_id
        intent_item.resolved_meaning.provider_pack_description = matching_candidate.pack_size
        intent_item.resolved_meaning.cart_quantity = quantity
        intent_item.resolved_meaning.clarification_required = False
        intent_item.resolved_meaning.explanation = f"User explicitly chose {matching_candidate.name} ({matching_candidate.pack_size})"

    verification = orchestrator._verifier.verify(contract, cart)
    session.last_verification = {"status": verification.status.value}
    events.append(f"VERIFICATION_{verification.status.value.upper()}")

    if verification.status == VerificationStatus.PASS:
        session.pending_clarification = None
        return await orchestrator._make_awaiting_confirmation(
            session, contract, cart, [f"Applied your choice: {matching_candidate.name}."], events
        )

    events.append("CHOICE_VIOLATION_DETECTED")
    reason = (
        verification.violations[0].detail if verification.violations else "constraint violation"
    )

    try:
        with orchestrator._port.customer_scope(session.customer_id):
            available: list[CommerceProductItem] = await orchestrator._port.search_products(
                effective_address,
                _targeted_recovery_query(contract, verification),
            )
    except Exception as exc:
        return orchestrator._provider_failure_result(session, exc, events)

    engine = RecoveryEngine(policy_engine=orchestrator._policy)
    outcome = engine.recover(
        contract=contract,
        cart=cart,
        verification_result=verification,
        available_products=available,
        attempt_number=1,
        max_attempts=3,
    )

    if outcome.state == RecoveryState.NEEDS_USER_DECISION:
        new_candidates = outcome.candidates_for_user or []
        options = _candidates_to_options(new_candidates)
        session.pending_clarification = PendingClarification(
            item_name=(
                verification.violations[0].target
                if verification.violations
                else pending.item_name
            ),
            candidates=new_candidates,
            clarification_question=outcome.message,
            removes_spin_id=chosen_spin_id,
            intended_quantity=quantity,
        )
        session.conversation_state = ConversationState.NEEDS_DECISION
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=f"That choice causes an issue: {reason}. {outcome.message}",
            clarification_options=options,
            clarification_nonce=session.pending_clarification.nonce,
            events=events,
        )
    else:
        session.pending_clarification = None
        session.conversation_state = ConversationState.FAILED
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(f"Selected option cannot be used: {reason}"),
            events=events,
        )
