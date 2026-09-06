"""Intent Chat API — the canonical GROCER conversational commerce surface."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import (
    BasketItemSchema,
    BasketSummarySchema,
    ClarificationOptionSchema,
    IntentChatRequest,
    IntentChatResponse,
    IntentChoiceRequest,
    IntentConfirmRequest,
    IntentSessionStateResponse,
)
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import default_session_store

router = APIRouter(prefix="/api/intent", tags=["intent"])
_orchestrator = GrocerOrchestrator()


def _turn_to_response(result: OrchestratorTurnResult) -> IntentChatResponse:
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


@router.post("/chat", response_model=IntentChatResponse)
async def intent_chat(payload: IntentChatRequest) -> IntentChatResponse:
    """Process one WhatsApp conversational turn without executing checkout."""
    result = await _orchestrator.handle_turn(
        session_id=payload.session_id,
        customer_id=payload.customer_id,
        message=payload.message,
        address_id=payload.address_id,
    )
    return _turn_to_response(result)


@router.post("/sessions/{session_id}/choice", response_model=IntentChatResponse)
async def intent_choice(
    session_id: str,
    payload: IntentChoiceRequest,
) -> IntentChatResponse:
    """Accept only a candidate that was actually offered for this session."""
    session = default_session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    pending = session.pending_clarification
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No pending product choice for this session.",
        )
    allowed = {candidate.spin_id for candidate in pending.candidates}
    if payload.chosen_spin_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chosen_spin_id is not one of the offered alternatives.",
        )

    result = await _orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id=payload.chosen_spin_id,
    )
    return _turn_to_response(result)


@router.post("/sessions/{session_id}/confirm", response_model=IntentChatResponse)
async def intent_confirm(
    session_id: str,
    payload: IntentConfirmRequest,
) -> IntentChatResponse:
    """Execute checkout only after explicit confirmation and pre-check verification."""
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _turn_to_response(result)


@router.get("/sessions/{session_id}", response_model=IntentSessionStateResponse)
async def get_session(session_id: str) -> IntentSessionStateResponse:
    """Return current state for a conversational commerce session."""
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


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict:
    """Clear a session so the next turn starts a fresh commerce task."""
    default_session_store.clear(session_id)
    return {"cleared": True, "session_id": session_id}
