"""Phase 6 — GrocerOrchestrator end-to-end tests (Spec §20 Phase 6).

Tests the full conversational commerce loop using MockCommerceAdapter:
    parse → resolve products → build cart → verify → recover → confirm → checkout

All tests use deterministic mocks — no real commerce provider.
"""
from __future__ import annotations

import asyncio
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
        clarification_nonce=session.pending_clarification.nonce,
    )
    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_handle_choice_preserves_unrelated_items_and_quantity(
    orchestrator: GrocerOrchestrator,
    mock_adapter: MockCommerceAdapter,
    fresh_store: OrchestratorSessionStore,
) -> None:
    """handle_choice must preserve other basket items and respect intended quantity."""
    session_id, customer_id = new_session()
    cart_id = f"cart-{session_id}"

    # Pre-populate cart with bread (unrelated item)
    from backend.integrations.commerce.models import CartItemUpdate
    await mock_adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=2)],
        cart_id=cart_id,
    )

    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = cart_id

    from backend.intent.parser import IntentParser
    contract = IntentParser().parse("get me 2 packs of milk and 2 packs of bread", session_id=session_id)
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
                score=0.85,
            )
        ],
        clarification_question="Which milk would you prefer?",
        intended_quantity=2,
    )
    fresh_store.save(session)

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-MILK-500ML",
        clarification_nonce=session.pending_clarification.nonce,
    )

    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    live_cart = await mock_adapter.get_cart(cart_id)
    items_by_spin = {it.spin_id: it for it in live_cart.items}

    # Verify unrelated bread is PRESERVED with its quantity 2
    assert "SPIN-BREAD-400G" in items_by_spin
    assert items_by_spin["SPIN-BREAD-400G"].quantity == 2

    # Verify chosen milk is ADDED with intended quantity 2
    assert "SPIN-MILK-500ML" in items_by_spin
    assert items_by_spin["SPIN-MILK-500ML"].quantity == 2


@pytest.mark.asyncio
async def test_handle_choice_invalid_unlisted_rejected(
    orchestrator: GrocerOrchestrator,
    fresh_store: OrchestratorSessionStore,
) -> None:
    """handle_choice rejects spins not in pending_clarification.candidates."""
    session_id, customer_id = new_session()
    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = f"cart-{session_id}"

    from backend.intent.parser import IntentParser
    session.intent_contract = IntentParser().parse("get me milk", session_id=session_id)

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
        clarification_question="Which milk?",
    )
    fresh_store.save(session)

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-UNLISTED-RANDOM",
        clarification_nonce=session.pending_clarification.nonce,
    )

    # Must NOT transition to AWAITING_CONFIRMATION or crash; remains in NEEDS_DECISION
    assert result.conversation_state == ConversationState.NEEDS_DECISION
    assert "not one of the available options" in result.user_message


@pytest.mark.asyncio
async def test_handle_choice_rejects_stale_clarification_nonce(
    orchestrator: GrocerOrchestrator,
    fresh_store: OrchestratorSessionStore,
) -> None:
    session_id, customer_id = new_session()
    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = f"cart-{session_id}"

    from backend.intent.parser import IntentParser
    from backend.intent.recovery import RecoveryCandidate
    from backend.intent.session import PendingClarification

    session.intent_contract = IntentParser().parse(
        "get me milk", session_id=session_id
    )
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
        clarification_question="Which milk?",
    )
    current_nonce = session.pending_clarification.nonce
    fresh_store.save(session)

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-MILK-500ML",
        clarification_nonce="stale-clarification-nonce",
    )

    assert result.conversation_state == ConversationState.NEEDS_DECISION
    assert result.clarification_nonce == current_nonce
    assert result.events == ["STALE_CHOICE_REJECTED"]
    assert fresh_store.get(session_id).pending_clarification is not None


@pytest.mark.asyncio
async def test_handle_choice_violating_hard_constraint_handled_safely(
    orchestrator: GrocerOrchestrator,
    fresh_store: OrchestratorSessionStore,
) -> None:
    """If user choice violates a hard constraint (e.g. eggs chosen with vegetarian contract), do not silently accept."""
    session_id, customer_id = new_session()
    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = f"cart-{session_id}"

    from backend.intent.parser import IntentParser
    contract = IntentParser().parse("get me snacks, strictly vegetarian", session_id=session_id)
    session.intent_contract = contract

    from backend.intent.session import PendingClarification
    from backend.intent.recovery import RecoveryCandidate
    session.pending_clarification = PendingClarification(
        item_name="snacks",
        candidates=[
            RecoveryCandidate(
                spin_id="SPIN-EGGS-6",
                name="Farm Fresh Eggs (6 pcs)",
                pack_size="6 pcs",
                price=48.0,
                category="poultry",
                score=0.5,
            )
        ],
        clarification_question="Which snack?",
    )
    fresh_store.save(session)

    result = await orchestrator.handle_choice(
        session_id=session_id,
        chosen_spin_id="SPIN-EGGS-6",
        clarification_nonce=session.pending_clarification.nonce,
    )

    # Must NOT accept eggs for a vegetarian contract
    assert result.conversation_state in (ConversationState.NEEDS_DECISION, ConversationState.FAILED)
    assert result.requires_confirmation is False


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
        clarification_nonce="no-pending-decision",
    )
    assert result.conversation_state == ConversationState.READY
    assert "No pending decision" in result.user_message


@pytest.mark.asyncio
async def test_concurrent_choices_apply_at_most_one_cart_update(
    orchestrator: GrocerOrchestrator,
    mock_adapter: MockCommerceAdapter,
    fresh_store: OrchestratorSessionStore,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    session_id, customer_id = new_session()
    session = fresh_store.get_or_create(session_id, customer_id)
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.cart_id = f"cart-{session_id}"

    from backend.intent.parser import IntentParser
    from backend.intent.recovery import RecoveryCandidate
    from backend.intent.session import PendingClarification

    session.intent_contract = IntentParser().parse(
        "get me milk", session_id=session_id
    )
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
        clarification_question="Which milk?",
    )
    nonce = session.pending_clarification.nonce
    fresh_store.save(session)

    original_update_cart = mock_adapter.update_cart
    update_count = 0

    async def counted_update_cart(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal update_count
        update_count += 1
        await asyncio.sleep(0)
        return await original_update_cart(*args, **kwargs)

    monkeypatch.setattr(mock_adapter, "update_cart", counted_update_cart)

    results = await asyncio.gather(
        orchestrator.handle_choice(session_id, "SPIN-MILK-500ML", nonce),
        orchestrator.handle_choice(session_id, "SPIN-MILK-500ML", nonce),
    )

    assert update_count == 1
    assert sum("NO_PENDING_DECISION" in result.events for result in results) == 1
    assert fresh_store.get(session_id).pending_clarification is None


@pytest.mark.asyncio
async def test_checkout_safety_no_unconfirmed_checkout(
    orchestrator: GrocerOrchestrator, fresh_store: OrchestratorSessionStore
) -> None:
    """Checkout must strictly require AWAITING_CONFIRMATION state and cannot be bypassed."""
    session_id, customer_id = new_session()
    session = fresh_store.get_or_create(session_id, customer_id)

    # In READY state
    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(session_id=session_id)

    # In NEEDS_DECISION state
    session.conversation_state = ConversationState.NEEDS_DECISION
    fresh_store.save(session)
    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(session_id=session_id)

    # In FAILED state
    session.conversation_state = ConversationState.FAILED
    fresh_store.save(session)
    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(session_id=session_id)



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

async def _create_api_session(client, customer_id: str) -> tuple[str, dict[str, str]]:  # type: ignore[no-untyped-def]
    del customer_id
    response = await client.post("/api/intent/sessions", json={})
    assert response.status_code == 201
    body = response.json()
    return body["session_id"], {
        "X-Grocer-Session-Capability": body["session_capability"]
    }

@pytest.mark.asyncio
async def test_api_chat_endpoint(client) -> None:
    customer_id = str(uuid.uuid4())
    session_id, headers = await _create_api_session(client, customer_id)
    response = await client.post(
        "/api/intent/chat",
        json={
            "session_id": session_id,
            "message": "get me 1L milk",
        },
        headers=headers,
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
    customer_id = str(uuid.uuid4())
    session_id, headers = await _create_api_session(client, customer_id)
    # First create a session via chat
    await client.post(
        "/api/intent/chat",
        json={
            "session_id": session_id,
            "message": "get me bread",
        },
        headers=headers,
    )
    response = await client.get(f"/api/intent/sessions/{session_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["turn_count"] >= 1


# ---------------------------------------------------------------------------
# 18. API — POST /api/intent/sessions/{id}/confirm without explicit_confirmation → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_confirm_without_explicit_rejects(client) -> None:
    session_id, headers = await _create_api_session(client, str(uuid.uuid4()))
    response = await client.post(
        f"/api/intent/sessions/{session_id}/confirm",
        json={"explicit_confirmation": False, "payment_method": "UPI"},
        headers=headers,
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
    customer_id = str(uuid.uuid4())
    session_id, headers = await _create_api_session(client, customer_id)
    await client.post(
        "/api/intent/chat",
        json={"session_id": session_id, "message": "get milk"},
        headers=headers,
    )
    delete_resp = await client.delete(f"/api/intent/sessions/{session_id}", headers=headers)
    assert delete_resp.status_code == 200
    # Session should now be gone
    get_resp = await client.get(f"/api/intent/sessions/{session_id}", headers=headers)
    assert get_resp.status_code == 404
