"""Address selection handlers for GrocerOrchestrator (Spec Section 11 & 12).

Handles:
- Routing to address selection if address is unconfirmed
- Resolving user address selections and transitioning to payment selection
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from backend.intent.models import IntentContract
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    PendingAddressChoice,
    PendingPaymentChoice,
)
from backend.intent.stages import (
    AddressStageManager,
    _detect_removal_request,
    _detect_swap_request,
    _display_address,
    _group_payment_options,
    _msg_payment_choice,
    default_address_manager,
)

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


async def advance_after_cart_built(
    orchestrator: GrocerOrchestrator,
    session: OrchestratorSession,
    contract: IntentContract,
    cart: Any,
    recovery_notes: list[str],
    events: list[str],
) -> OrchestratorTurnResult:
    """Route to address selection (Turn 2) if address unconfirmed on Swiggy, else confirmation."""
    from backend.intent.orchestrator import OrchestratorTurnResult
    from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter

    if not cart or not getattr(cart, "items", None) or getattr(cart, "grand_total", 0.0) <= 0:
        session.conversation_state = ConversationState.BUILDING
        orchestrator._store.save(session)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.BUILDING,
            user_message="Your basket is currently empty. What would you like to add?",
            events=events + ["EMPTY_CART_ADVANCE_BLOCKED"],
        )

    is_swiggy = isinstance(orchestrator._port, SwiggyMCPAdapter)

    if is_swiggy and not session.address_confirmed:
        try:
            addresses = await orchestrator._port.get_addresses(session.customer_id)
        except Exception as exc:
            return orchestrator._provider_failure_result(session, exc, events)

        if addresses:
            session.pending_address_choice = PendingAddressChoice(
                addresses=addresses,
                request_message=contract.goal or "grocery order",
            )
            session.conversation_state = ConversationState.NEEDS_DECISION
            events.append("NEEDS_ADDRESS_SELECTION")
            orchestrator._store.save(session)

            basket_lines = ["🛒 *Added to your basket:*", ""]
            for it in cart.items:
                basket_lines.append(f"• {it.quantity} × {it.name} ({it.pack_size}) — ₹{it.total_price:,.0f}")
            basket_lines.append("")
            basket_lines.append(f"Subtotal: ₹{cart.item_total:,.0f}")
            basket_prefix = "\n".join(basket_lines)

            prompt_msg = AddressStageManager.format_address_prompt(
                addresses, basket_prefix=basket_prefix
            )
            return OrchestratorTurnResult(
                session_id=session.session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message=prompt_msg,
                address_options=addresses,
                events=events,
            )

    return await orchestrator._make_awaiting_confirmation(
        session, contract, cart, recovery_notes, events
    )


async def handle_address_choice(
    orchestrator: GrocerOrchestrator,
    session_id: str,
    address_id: str,
) -> OrchestratorTurnResult:
    """Handle delivery address selection (Turn 2: Address -> Turn 3: Payment)."""
    from backend.intent.orchestrator import OrchestratorTurnResult

    session = orchestrator._store.get(session_id)
    if not session or not session.pending_address_choice:
        return await orchestrator.handle_turn(
            session_id=session_id,
            customer_id=session.customer_id if session else "default",
            message=address_id,
        )

    events: list[str] = list(session.events)
    pending = session.pending_address_choice
    addresses = pending.addresses

    selected = AddressStageManager.match_address_choice(address_id, addresses)
    if not selected:
        temp_contract = orchestrator._parser.parse(address_id, session_id=session.session_id)
        if (
            temp_contract.items
            or _detect_swap_request(address_id)
            or _detect_removal_request(address_id)
        ):
            session.pending_address_choice = None
            orchestrator._store.save(session)
            return await orchestrator.handle_turn(
                session_id=session_id,
                customer_id=session.customer_id,
                message=address_id,
            )
        prompt_msg = AddressStageManager.format_address_prompt(
            addresses,
            basket_prefix="📍 Please choose a delivery address from your saved list:",
        )
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=f"I couldn't match '{address_id}' to a saved address.\n\n{prompt_msg}",
            address_options=addresses,
            events=events + ["ADDRESS_CHOICE_UNMATCHED"],
        )

    session.address_id = selected.id
    session.address_display = _display_address(selected)
    session.address_confirmed = True
    session.pending_address_choice = None
    default_address_manager.save_address(session.customer_id, selected.id)
    events.append(f"ADDRESS_SELECTED id={selected.id}")

    cart_id = session.cart_id
    try:
        with orchestrator._port.customer_scope(session.customer_id):
            raw_options = await orchestrator._port.get_payment_options(
                cart_id=cart_id,
                address_id=selected.id,
            )
            payment_options = [o for o in raw_options if o.is_available]
    except Exception as exc:
        return orchestrator._provider_failure_result(session, exc, events)

    if not payment_options:
        return orchestrator._handle_failed(session, "no payment options available", events)

    grouped = _group_payment_options(payment_options)

    if len(grouped) == 1:
        contract = session.intent_contract or IntentContract(session_id=session_id, goal="grocery order")
        try:
            cart = await orchestrator._port.get_cart(cart_id)
        except Exception as exc:
            return orchestrator._provider_failure_result(session, exc, events)
        return await orchestrator._make_awaiting_confirmation(
            session, contract, cart, [], events,
            preferred_payment_option_id=grouped[0].id,
            preferred_payment_method=grouped[0].method,
        )

    session.pending_payment_choice = PendingPaymentChoice(
        options=grouped,
        raw_options=payment_options,
        recovery_notes=[],
    )
    session.conversation_state = ConversationState.NEEDS_DECISION
    orchestrator._store.save(session)
    events.append("PAYMENT_CHOICE_REQUIRED")

    user_msg = _msg_payment_choice(grouped, address_display=session.address_display)
    return OrchestratorTurnResult(
        session_id=session.session_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        user_message=user_msg,
        payment_options=grouped,
        payment_choice_nonce=session.pending_payment_choice.nonce,
        events=events,
    )
