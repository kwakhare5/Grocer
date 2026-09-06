"""Intent Chat API — Phase 6 Agent Orchestration endpoints (Spec §12, §20).

Endpoints:
    POST   /api/intent/chat                    — main conversational turn
    POST   /api/intent/sessions/{id}/choice    — resolve pending NEEDS_DECISION
    POST   /api/intent/sessions/{id}/confirm   — explicit checkout confirmation
    GET    /api/intent/sessions/{id}           — inspect session state
    DELETE /api/intent/sessions/{id}           — clear/reset session

Safety invariants (Spec §17):
    - Checkout is rejected unless session is in AWAITING_CONFIRMATION state.
    - explicit_confirmation must be True in the request body.
    - Backend verifies the cart against intent before executing checkout.
    - No autonomous checkout without explicit human confirmation.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Response, status

from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import ConversationState, default_session_store
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.api.schemas import (
    IntentChatRequest,
    IntentChatResponse,
    IntentChoiceRequest,
    IntentConfirmRequest,
    IntentSessionStateResponse,
    BasketSummarySchema,
    BasketItemSchema,
    ClarificationOptionSchema,
)

router = APIRouter(prefix="/api/intent", tags=["intent"])

# Module-level orchestrator (stateless; sessions live in default_session_store)
_orchestrator = GrocerOrchestrator()


def _turn_to_response(result: OrchestratorTurnResult) -> IntentChatResponse:
    """Map OrchestratorTurnResult → IntentChatResponse."""
    basket = None
    if result.basket_summary:
        b = result.basket_summary
        basket = BasketSummarySchema(
            cart_id=b.cart_id,
            items=[
                BasketItemSchema(
                    spin_id=it.spin_id,
                    name=it.name,
                    pack_size=it.pack_size,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    line_total=it.line_total,
                    substituted=it.substituted,
                )
                for it in b.items
            ],
            item_total=b.item_total,
            delivery_fee=b.delivery_fee,
            grand_total=b.grand_total,
            budget=b.budget,
            within_budget=b.within_budget,
            recovery_notes=b.recovery_notes,
        )

    clarification_options = None
    if result.clarification_options:
        clarification_options = [
            ClarificationOptionSchema(
                index=opt.index,
                spin_id=opt.spin_id,
                name=opt.name,
                pack_size=opt.pack_size,
                price=opt.price,
                score=opt.score,
            )
            for opt in result.clarification_options
        ]

    return IntentChatResponse(
        session_id=result.session_id,
        conversation_state=result.conversation_state.value,
        user_message=result.user_message,
        basket_summary=basket,
        clarification_options=clarification_options,
        requires_confirmation=result.requires_confirmation,
        order_id=result.order_id,
        order_total=result.order_total,
        events=result.events,
    )


# ---------------------------------------------------------------------------
# POST /api/intent/chat — main conversational turn
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=IntentChatResponse)
async def intent_chat(payload: IntentChatRequest) -> IntentChatResponse:
    """Process one WhatsApp conversational turn through the full commerce loop.

    Parses intent, resolves products, builds cart, verifies, recovers if needed.
    Returns basket summary and state — does NOT execute checkout.
    """
    result = await _orchestrator.handle_turn(
        session_id=payload.session_id,
        customer_id=payload.customer_id,
        message=payload.message,
        address_id=payload.address_id,
    )
    return _turn_to_response(result)


# ---------------------------------------------------------------------------
# POST /api/intent/sessions/{session_id}/choice — resolve clarification
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/choice", response_model=IntentChatResponse)
async def intent_choice(
    session_id: str,
    payload: IntentChoiceRequest,
) -> IntentChatResponse:
    """Resolve a pending NEEDS_DECISION turn with the user's chosen product.

    The chosen_spin_id must be one of the options returned in the
    previous IntentChatResponse.clarification_options.
    """
    result = await _orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id=payload.chosen_spin_id,
    )
    return _turn_to_response(result)


# ---------------------------------------------------------------------------
# POST /api/intent/sessions/{session_id}/confirm — checkout confirmation
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/confirm", response_model=IntentChatResponse)
async def intent_confirm(
    session_id: str,
    payload: IntentConfirmRequest,
) -> IntentChatResponse:
    """Execute checkout with explicit user confirmation (Spec §8.3).

    CRITICAL INVARIANT: explicit_confirmation must be True.
    Returns 400 if:
        - explicit_confirmation is False.
        - session is not in AWAITING_CONFIRMATION state.
        - pre-checkout verification fails.
    """
    if not payload.explicit_confirmation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout requires explicit_confirmation=true.",
        )
    try:
        result = await _orchestrator.handle_confirm(
            session_id=session_id,
            payment_method=payload.payment_method,
            address_id=payload.address_id,
        )
    except UnconfirmedCheckoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _turn_to_response(result)


# ---------------------------------------------------------------------------
# GET /api/intent/sessions/{session_id} — session state inspection
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=IntentSessionStateResponse)
async def get_session(session_id: str) -> IntentSessionStateResponse:
    """Return current session state for the given session_id.

    Returns 404 if session has not been created yet.
    """
    session = default_session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id!r} not found.",
        )
    return IntentSessionStateResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        conversation_state=session.conversation_state.value,
        cart_id=session.cart_id,
        turn_count=session.turn_count,
        has_pending_clarification=session.pending_clarification is not None,
        order_id=session.order_id,
        order_total=session.order_total,
        events=session.events,
    )


# ---------------------------------------------------------------------------
# DELETE /api/intent/sessions/{session_id} — reset session
# ---------------------------------------------------------------------------

@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict:
    """Clear and reset a session. Useful for starting a fresh shopping task."""
    default_session_store.clear(session_id)
    return {"cleared": True, "session_id": session_id}
