"""Intent Chat API — the canonical GROCER conversational commerce surface."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from backend.api.schemas import (
    BasketItemSchema,
    BasketSummarySchema,
    ClarificationOptionSchema,
    IntentChatRequest,
    IntentChatResponse,
    IntentChoiceRequest,
    IntentConfirmRequest,
    IntentSessionStateResponse,
    IntentSessionCreateRequest,
    IntentSessionCreateResponse,
)
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import default_session_store
from backend.intent.storage import default_intent_store

router = APIRouter(prefix="/api/intent", tags=["intent"])
_orchestrator = GrocerOrchestrator()


def _authorized_session(session_id: str, capability: str | None):
    session = default_session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if not default_session_store.verify_capability(session_id, capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid session capability.",
        )
    return session


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
            packaging_fee=b.packaging_fee,
            discount=b.discount,
            grand_total=b.grand_total,
            address_id=b.address_id,
            budget=b.budget,
            within_budget=b.within_budget,
            recovery_notes=b.recovery_notes,
            payment_options=[option.model_dump() for option in b.payment_options],
            selected_payment_method=b.selected_payment_method,
            selected_payment_option_id=b.selected_payment_option_id,
            confirmation_nonce=b.confirmation_nonce,
            confirmation_expires_at=b.confirmation_expires_at,
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
        clarification_nonce=result.clarification_nonce,
        requires_confirmation=result.requires_confirmation,
        order_id=result.order_id,
        order_total=result.order_total,
        payment_status=result.payment_status,
        payment_url=result.payment_url,
        child_orders=result.child_orders,
        events=result.events,
    )


@router.post(
    "/sessions",
    response_model=IntentSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_intent_session(
    _payload: IntentSessionCreateRequest,
) -> IntentSessionCreateResponse:
    """Create one opaque browser session and return its bearer capability once."""
    session, capability = default_session_store.create_capability_session()
    return IntentSessionCreateResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        session_capability=capability,
    )


@router.post("/chat", response_model=IntentChatResponse)
async def intent_chat(
    payload: IntentChatRequest,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Process one WhatsApp conversational turn without executing checkout."""
    session = _authorized_session(payload.session_id, session_capability)
    result = await _orchestrator.handle_turn(
        session_id=payload.session_id,
        customer_id=session.customer_id,
        message=payload.message,
        address_id=payload.address_id,
    )
    return _turn_to_response(result)


@router.post("/sessions/{session_id}/payment-status", response_model=IntentChatResponse)
async def intent_payment_status(
    session_id: str,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Observe one provider payment transition without polling in a request loop."""
    _authorized_session(session_id, session_capability)
    result = await _orchestrator.handle_payment_status(session_id)
    return _turn_to_response(result)


@router.get("/sessions/{session_id}/order-details", response_model=IntentChatResponse)
async def intent_order_details(
    session_id: str,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Return only order facts currently available from the commerce provider."""
    _authorized_session(session_id, session_capability)
    return _turn_to_response(await _orchestrator.handle_order_details(session_id))


@router.get("/sessions/{session_id}/delivery-status", response_model=IntentChatResponse)
async def intent_delivery_status(
    session_id: str,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Return one provider delivery observation without starting a poll loop."""
    _authorized_session(session_id, session_capability)
    return _turn_to_response(await _orchestrator.handle_delivery_status(session_id))


@router.post("/sessions/{session_id}/choice", response_model=IntentChatResponse)
async def intent_choice(
    session_id: str,
    payload: IntentChoiceRequest,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Accept only a candidate that was actually offered for this session."""
    session = _authorized_session(session_id, session_capability)
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
    if payload.clarification_nonce != pending.nonce:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The product choice is stale.",
        )

    result = await _orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id=payload.chosen_spin_id,
        clarification_nonce=payload.clarification_nonce,
    )
    return _turn_to_response(result)


@router.post("/sessions/{session_id}/confirm", response_model=IntentChatResponse)
async def intent_confirm(
    session_id: str,
    payload: IntentConfirmRequest,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentChatResponse:
    """Execute checkout only after explicit confirmation and pre-check verification."""
    _authorized_session(session_id, session_capability)
    if not payload.explicit_confirmation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout requires explicit_confirmation=true.",
        )
    if not payload.confirmation_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout requires the current confirmation_nonce.",
        )
    try:
        result = await _orchestrator.handle_confirm(
            session_id=session_id,
            payment_method=payload.payment_method,
            address_id=payload.address_id,
            explicit_confirmation=payload.explicit_confirmation,
            confirmation_nonce=payload.confirmation_nonce,
        )
    except UnconfirmedCheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _turn_to_response(result)


@router.get("/sessions/{session_id}", response_model=IntentSessionStateResponse)
async def get_session(
    session_id: str,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> IntentSessionStateResponse:
    """Return current state for a conversational commerce session."""
    session = _authorized_session(session_id, session_capability)
    return IntentSessionStateResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        conversation_state=session.conversation_state.value,
        cart_id=session.cart_id,
        turn_count=session.turn_count,
        has_pending_clarification=session.pending_clarification is not None,
        order_id=session.order_id,
        order_total=session.order_total,
        payment_status=session.payment_status,
        payment_url=session.payment_url,
        events=session.events,
    )


@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str,
    session_capability: str | None = Header(
        None, alias="X-Grocer-Session-Capability"
    ),
) -> dict:
    """Clear a session so the next turn starts a fresh commerce task."""
    _authorized_session(session_id, session_capability)
    default_session_store.clear(session_id)
    default_intent_store.clear_session(session_id)
    return {"cleared": True, "session_id": session_id}
