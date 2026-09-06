"""Forensic test proving hard budget constraints are strictly non-negotiable.

Proves:
1. hard budget = X CANNOT result in an autonomous final cart total > X.
2. When staying within budget is impossible, the system asks the user (NEEDS_DECISION)
   rather than silently exceeding the cap.
3. Consequential checkout is strictly rejected if budget is violated.
"""
from __future__ import annotations

import uuid
import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.models import BudgetConstraint, IntentContract, IntentItem
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import FailureClass, RecoveryEngine, RecoveryState
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.session import ConversationState, OrchestratorSessionStore
from backend.intent.verifier import IntentVerifier, VerificationStatus, ViolationCode


@pytest.mark.asyncio
async def test_hard_budget_cannot_result_in_autonomous_cart_overrun() -> None:
    """Proof 1: Hard budget = X cannot result in an autonomous cart total > X.
    
    When an item price surges, if an autonomous substitution is made, the resulting
    cart total must remain <= max_budget.
    """
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_loop = LoopingRecoveryEngine(verifier=verifier)

    budget_cap = 200.0
    contract = IntentContract(
        session_id="test-budget-invar",
        customer_id="cust-budget",
        goal="milk and bread under 200",
        items=[
            IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy", is_essential=True),
            IntentItem(name="bread", quantity=1, pack_size_preference="400 g", category="bakery", is_essential=True),
        ],
        budget=BudgetConstraint(max_budget=budget_cap, is_hard=True, max_deviation=0.0),
    )

    cart_id = "cart-budget-1"
    # Initial: 1L milk (66) + bread (50) + delivery (30) + packaging (5) = 151 <= 200
    await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
        ],
        cart_id=cart_id,
    )

    # Injected fault: 1L milk goes OOS -> recovery will substitute 2x 500ml milk (2 * 34 = 68)
    # Total becomes: 68 + 50 + 35 = 153 <= 200
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    catalog = await adapter.search_products("addr-1", "")
    result = await recovery_loop.run(
        contract=contract,
        cart_id=cart_id,
        commerce_port=adapter,
        available_products=catalog,
    )

    # Autonomous recovery completed
    assert result.state == RecoveryState.RECOVERED
    assert result.cart.grand_total <= budget_cap, (
        f"Autonomous cart total {result.cart.grand_total} strictly exceeded hard budget {budget_cap}!"
    )
    # Full verification must be PASS
    assert result.verification.status == VerificationStatus.PASS


@pytest.mark.asyncio
async def test_impossible_budget_strictly_requests_decision_without_checkout() -> None:
    """Proof 2: If staying within budget is impossible, system asks the user (NEEDS_DECISION)
    rather than silently exceeding the cap.
    """
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = f"budget-orch-{uuid.uuid4().hex[:6]}"
    customer_id = f"cust-budget-{uuid.uuid4().hex[:6]}"

    # User establishes strict hard budget of \u20b9120
    turn1 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get bread and tomatoes under 120",
    )
    assert turn1.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert turn1.basket_summary.grand_total <= 120.0

    # Injected fault: Tomato price surges from 32 to 95.
    # New cart total: 50 (bread) + 95 (tomatoes) + 35 (fees) = 180 > 120.
    # No cheaper tomato variant exists in the catalog.
    adapter.inject_price_change("SPIN-TOMATO-500G", 95.0)

    # Turn 2: User queries status / continues replenishment
    turn2 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="check my basket",
    )

    # Strict compliance: system CANNOT auto-apply and CANNOT proceed to checkout
    assert turn2.conversation_state == ConversationState.NEEDS_DECISION, (
        f"Expected NEEDS_DECISION on budget breach, got {turn2.conversation_state}!"
    )
    assert turn2.requires_confirmation is False, "Cannot request checkout confirmation for a breached budget!"
    assert turn2.order_id is None, "Autonomous order must NOT be placed on breached budget!"
    assert "budget" in turn2.user_message.lower() or "overrun" in turn2.user_message.lower()

    # And even if an explicit confirmation is attempted, handle_confirm strictly blocks checkout
    with pytest.raises(UnconfirmedCheckoutError):
        # Session is in NEEDS_DECISION, so unconfirmed checkout error is raised
        await orchestrator.handle_confirm(session_id=session_id)


@pytest.mark.asyncio
async def test_checkout_gate_strictly_rejects_budget_breach() -> None:
    """Proof 3: IntentVerifier and checkout gate strictly reject checkout when budget is exceeded."""
    verifier = IntentVerifier()
    contract = IntentContract(
        session_id="test-gate",
        customer_id="cust-gate",
        goal="budget gate test",
        items=[IntentItem(name="tomatoes", quantity=1)],
        budget=BudgetConstraint(max_budget=50.0, is_hard=True),
    )

    # Cart with grand_total \u20b975 > \u20b950
    from backend.integrations.commerce.models import CommerceCart, CartItem
    cart_over_budget = CommerceCart(
        cart_id="cart-over",
        items=[
            CartItem(
                spin_id="SPIN-TOMATO-1KG",
                name="Tomatoes 1kg",
                pack_size="1 kg",
                unit_price=60.0,
                quantity=1,
                total_price=60.0,
            )
        ],
        item_total=60.0,
        grand_total=75.0,
    )

    # Verification must fail with BUDGET_EXCEEDED
    v_res = verifier.verify(contract, cart_over_budget)
    assert v_res.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.BUDGET_EXCEEDED for v in v_res.violations)

    # verify_checkout must reject checkout even if explicit_confirmation is True
    v_checkout = verifier.verify_checkout(contract, cart_over_budget, explicit_confirmation=True)
    assert v_checkout.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.BUDGET_EXCEEDED for v in v_checkout.violations)
