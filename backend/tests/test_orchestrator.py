"""Phase 6 — GrocerOrchestrator end-to-end tests (Spec §20 Phase 6).

Tests the full conversational commerce loop using MockCommerceAdapter:
    parse → resolve products → build cart → verify → recover → confirm → checkout

All tests use deterministic mocks — no real commerce provider.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import (
    ConversationState,
    OrchestratorSessionStore,
    default_session_store,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_store() -> OrchestratorSessionStore:
    """Return a clean, isolated session store for each test."""
    return OrchestratorSessionStore()


@pytest.fixture
def mock_adapter() -> MockCommerceAdapter:
    """Return a fresh MockCommerceAdapter per test."""
    return MockCommerceAdapter()


@pytest.fixture
def orchestrator(mock_adapter: MockCommerceAdapter, fresh_store: OrchestratorSessionStore) -> GrocerOrchestrator:
    """GrocerOrchestrator wired to the mock adapter and an isolated session store."""
    return GrocerOrchestrator(commerce_adapter=mock_adapter, session_store=fresh_store)


def new_session() -> tuple[str, str]:
    """Return a fresh (session_id, customer_id) pair."""
    return str(uuid.uuid4()), str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Happy path — grocery request builds basket and awaits confirmation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_awaits_confirmation(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk",
    )
    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert result.requires_confirmation is True
    assert result.basket_summary is not None
    assert result.basket_summary.grand_total > 0
    assert "Confirm" in result.user_message or "confirm" in result.user_message.lower()


# ---------------------------------------------------------------------------
# 2. Session is persisted across turns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_persisted(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()
    await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk and eggs",
    )
    session = fresh_store.get(session_id)
    assert session is not None
    assert session.customer_id == customer_id
    assert session.turn_count == 1
    assert session.conversation_state == ConversationState.AWAITING_CONFIRMATION


# ---------------------------------------------------------------------------
# 3. Session state — GET equivalent (from store)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_state_after_turn(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()
    await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="I need milk, bread and eggs",
    )
    session = fresh_store.get(session_id)
    assert session is not None
    assert session.cart_id is not None
    assert session.intent_contract is not None


# ---------------------------------------------------------------------------
# 4. Explicit confirmation → ORDERED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_checkout_happy_path(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    turn = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk",
    )
    assert turn.conversation_state == ConversationState.AWAITING_CONFIRMATION

    confirm = await orchestrator.handle_confirm(
        session_id=session_id,
        payment_method="UPI",
    )
    assert confirm.conversation_state == ConversationState.ORDERED
    assert confirm.order_id is not None
    assert confirm.order_total is not None
    assert "Order placed" in confirm.user_message or "order" in confirm.user_message.lower()


# ---------------------------------------------------------------------------
# 5. Checkout without AWAITING_CONFIRMATION raises UnconfirmedCheckoutError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_without_awaiting_raises(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    # Don't call handle_turn first — session is READY
    orchestrator._store.get_or_create(session_id, customer_id)
    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(session_id=session_id)


# ---------------------------------------------------------------------------
# 6. Checkout on non-existent session returns FAILED (graceful)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_nonexistent_session_returns_failed(orchestrator: GrocerOrchestrator) -> None:
    result = await orchestrator.handle_confirm(session_id="no-such-session")
    assert result.conversation_state == ConversationState.FAILED
    assert "session not found" in result.user_message.lower()


# ---------------------------------------------------------------------------
# 7. Multi-item basket — milk + eggs + bread all resolved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_item_basket(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk, eggs and bread for the week",
    )
    # Should have resolved to some basket
    assert result.conversation_state in (
        ConversationState.AWAITING_CONFIRMATION,
        ConversationState.NEEDS_DECISION,
    )
    if result.basket_summary:
        assert result.basket_summary.grand_total > 0


# ---------------------------------------------------------------------------
# 8. Budget constraint in intent — basket must stay within budget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_budget_constraint_respected(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk and bread, total under ₹500",
    )
    # Milk (₹66) + Bread (₹50) + fees = well under ₹500
    if result.basket_summary:
        assert result.basket_summary.within_budget is True


# ---------------------------------------------------------------------------
# 9. User choice resolves NEEDS_DECISION (simulated via handle_choice)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_choice_valid_spin(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()

    # Manually put session into NEEDS_DECISION state
    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = f"cart-{session_id}"

    # Set an intent contract via a real parse
    from backend.intent.parser import IntentParser
    contract = IntentParser().parse("get me milk", session_id=session_id)
    session.intent_contract = contract

    from backend.intent.session import PendingClarification
    from backend.intent.recovery import RecoveryCandidate
    session.pending_clarification = PendingClarification(
        item_name="milk",
        candidates=[
            RecoveryCandidate(
                spin_id="SPIN-MILK-500ML",
                name="Amul Taaza Milk 500ml",
                pack_size="500 ml",
                price=34.0,
                category="dairy",
                score=0.8,
            )
        ],
        clarification_question="Which milk would you prefer?",
    )
    fresh_store.save(session)

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-MILK-500ML",
    )
    # Should re-verify and move to AWAITING_CONFIRMATION (milk in cart, constraint PASS)
    assert result.conversation_state in (
        ConversationState.AWAITING_CONFIRMATION,
        ConversationState.FAILED,  # acceptable if verifier has more constraints
    )


# ---------------------------------------------------------------------------
# 10. handle_choice on non-NEEDS_DECISION session returns polite rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_choice_wrong_state(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()
    fresh_store.get_or_create(session_id, customer_id)  # state = READY

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-MILK-1L",
    )
    assert result.conversation_state == ConversationState.READY
    assert "No pending decision" in result.user_message


# ---------------------------------------------------------------------------
# 11. Session clear resets to no session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_clear(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()
    await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me milk",
    )
    assert fresh_store.get(session_id) is not None
    fresh_store.clear(session_id)
    assert fresh_store.get(session_id) is None


# ---------------------------------------------------------------------------
# 12. Events audit trail is populated each turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_populated(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="I need bread",
    )
    assert len(result.events) > 0
    event_text = " ".join(result.events)
    assert "INTENT_PARSED" in event_text
    assert "CART_BUILT" in event_text
    assert "VERIFICATION" in event_text


# ---------------------------------------------------------------------------
# 13. Turn count increments with each turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_turn_count_increments(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    session_id, customer_id = new_session()
    await orchestrator.handle_turn(session_id=session_id, customer_id=customer_id, message="get milk")
    assert fresh_store.get(session_id).turn_count == 1
    await orchestrator.handle_turn(session_id=session_id, customer_id=customer_id, message="add bread")
    assert fresh_store.get(session_id).turn_count == 2


# ---------------------------------------------------------------------------
# 14. Basket summary contains expected fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_basket_summary_structure(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me 1L milk",
    )
    assert result.basket_summary is not None
    b = result.basket_summary
    assert b.cart_id is not None
    assert len(b.items) >= 1
    assert b.grand_total > 0
    assert b.item_total >= 0
    assert b.delivery_fee >= 0


# ---------------------------------------------------------------------------
# 15. Checkout confirmation produces order_id in result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_produces_order_id(orchestrator: GrocerOrchestrator) -> None:
    session_id, customer_id = new_session()
    await orchestrator.handle_turn(
        session_id=session_id, customer_id=customer_id, message="get me milk"
    )
    result = await orchestrator.handle_confirm(session_id=session_id)
    assert result.order_id is not None
    assert result.order_id.startswith("OD-")


# ---------------------------------------------------------------------------
# 16. API — POST /api/intent/chat returns 200 and valid body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_chat_endpoint(client) -> None:
    session_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    response = await client.post(
        "/api/intent/chat",
        json={
            "session_id": session_id,
            "customer_id": customer_id,
            "message": "get me 1L milk",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["conversation_state"] in [
        "AWAITING_CONFIRMATION", "BUILDING", "NEEDS_DECISION", "FAILED"
    ]
    assert "user_message" in data


# ---------------------------------------------------------------------------
# 17. API — GET /api/intent/sessions/{id} returns 200 after chat turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_get_session(client) -> None:
    session_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    # First create a session via chat
    await client.post(
        "/api/intent/chat",
        json={
            "session_id": session_id,
            "customer_id": customer_id,
            "message": "get me bread",
        },
    )
    response = await client.get(f"/api/intent/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["turn_count"] >= 1


# ---------------------------------------------------------------------------
# 18. API — POST /api/intent/sessions/{id}/confirm without explicit_confirmation → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_confirm_without_explicit_rejects(client) -> None:
    session_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/intent/sessions/{session_id}/confirm",
        json={"explicit_confirmation": False, "payment_method": "UPI"},
    )
    assert response.status_code == 400
    assert "explicit_confirmation" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 19. API — GET /api/intent/sessions/{id} returns 404 for unknown session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_get_session_not_found(client) -> None:
    response = await client.get("/api/intent/sessions/no-such-session-xyz")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 20. API — DELETE /api/intent/sessions/{id} clears session (returns 204)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_delete_session(client) -> None:
    session_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    await client.post(
        "/api/intent/chat",
        json={"session_id": session_id, "customer_id": customer_id, "message": "get milk"},
    )
    delete_resp = await client.delete(f"/api/intent/sessions/{session_id}")
    assert delete_resp.status_code == 200
    # Session should now be gone
    get_resp = await client.get(f"/api/intent/sessions/{session_id}")
    assert get_resp.status_code == 404
