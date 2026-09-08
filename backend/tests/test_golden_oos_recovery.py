"""Golden Out-Of-Stock (OOS) Recovery Scenario (Spec §10, §15, §20).

Validates the flagship proof loop:
User request:
    "get my weekly groceries under ₹2000, vegetarian, use my usual brands"

End-to-End Cycle:
1. Parse conversational request → structured IntentContract.
2. Build initial basket via CommercePort (Amul milk, bread, tomatoes).
3. Deterministic verification: initial basket passes (status PASS, within ₹2000 budget, vegetarian).
4. Inject deterministic simulated commerce failure: Amul 1L milk goes out of stock.
5. Re-fetch live commerce state → IntentVerifier flags violation (ITEM_UNAVAILABLE).
6. LoopingRecoveryEngine executes bounded recovery:
   - Identifies broken intent item (milk).
   - Evaluates policy & candidate alternatives in catalog.
   - Selects compliant replacement (Amul 500ml milk with 2x pack multiple).
   - Mutates commerce cart while strictly preserving unrelated items (bread, tomatoes).
   - Re-fetches live cart from CommercePort.
   - Re-verifies FULL intent: vegetarian constraint satisfied, total <= ₹2000, items present.
7. Verification PASS → session transitions to AWAITING_CONFIRMATION with recovery notes.
8. Server-side explicit confirmation gate enforces that checkout CANNOT happen automatically.
9. Explicit user confirmation executes consequential checkout → ORDERED.
"""
from __future__ import annotations

import uuid
import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.enums import PrecedenceLevel, PreferenceType
from backend.intent.models import (
    BudgetConstraint,
    DietaryConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SoftPreference,
    SubstitutionPolicy,
)
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.recovery import RecoveryState
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.session import ConversationState, OrchestratorSessionStore
from backend.intent.verifier import IntentVerifier, VerificationStatus, ViolationCode


@pytest.mark.asyncio
async def test_golden_oos_recovery_scenario() -> None:
    """The complete verified golden end-to-end recovery proof."""
    # 0. Setup isolated components
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    verifier = IntentVerifier()
    recovery_loop = LoopingRecoveryEngine(verifier=verifier)

    session_id = f"golden-{uuid.uuid4().hex[:8]}"
    customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    cart_id = f"cart-{session_id}"
    address_id = "addr-bandra-1"

    # 1. Establish Intent Contract
    # Goal: "get my weekly groceries under ₹2000, vegetarian, use my usual brands"
    contract = IntentContract(
        session_id=session_id,
        customer_id=customer_id,
        goal="weekly groceries under ₹2000, vegetarian, use usual brands",
        items=[
            IntentItem(name="milk", quantity=1, unit="L", pack_size_preference="1 L", category="dairy", is_essential=True),
            IntentItem(name="bread", quantity=1, unit="pcs", pack_size_preference="400 g", category="bakery", is_essential=True),
            IntentItem(name="tomatoes", quantity=1, unit="kg", pack_size_preference="1 kg", category="produce", is_essential=True),
        ],
        budget=BudgetConstraint(max_budget=2000.0, is_hard=True, max_deviation=0.0),
        dietary_constraints=[
            DietaryConstraint(tag="vegetarian", is_hard=True, detail="Strictly vegetarian grocery restock")
        ],
        pack_size_rules=PackSizeRules(preferred_multiples=True),
        soft_preferences=[
            SoftPreference(
                preference_type=PreferenceType.BRAND,
                target="milk",
                preference="Amul",
            )


        ],
        substitution_policy=SubstitutionPolicy(),
    )

    # 2. Build initial basket via CommercePort
    initial_cart = await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),       # Amul 1L milk: ₹66
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),     # Bread 400g: ₹50
            CartItemUpdate(spin_id="SPIN-TOMATO-1KG", quantity=1),     # Tomatoes 1kg: ₹60
        ],
        cart_id=cart_id,
        address_id=address_id,
    )

    # Total: ₹176 + ₹30 delivery + ₹5 packing = ₹211 <= ₹2000
    assert initial_cart.grand_total <= 2000.0
    assert len(initial_cart.items) == 3

    # 3. Deterministic Verification: initial basket PASS
    initial_v = verifier.verify(contract, initial_cart)
    assert initial_v.status == VerificationStatus.PASS
    assert len(initial_v.violations) == 0

    # 4. Inject deterministic simulated commerce failure: Amul 1L milk goes out of stock!
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    # 5. Live cart fetched → IntentVerifier detects failure
    live_cart = await adapter.get_cart(cart_id)
    drift_v = verifier.verify(contract, live_cart)
    assert drift_v.status == VerificationStatus.FAIL
    assert any(
        v.violation_code in (ViolationCode.ITEM_UNAVAILABLE, ViolationCode.MISSING_ITEM)
        for v in drift_v.violations
    )

    # 6. LoopingRecoveryEngine executes bounded recovery
    available_catalog = await adapter.search_products(address_id, "")
    recovery_result = await recovery_loop.run(
        contract=contract,
        cart_id=cart_id,
        commerce_port=adapter,
        available_products=available_catalog,
        max_attempts=3,
        address_id=address_id,
    )

    # 7. Verify recovery outcome
    assert recovery_result.state == RecoveryState.RECOVERED
    assert recovery_result.verification.status == VerificationStatus.PASS
    assert recovery_result.attempts <= 3

    # Ensure unrelated items (bread, tomatoes) are STRICTLY preserved
    recovered_spins = {item.spin_id: item for item in recovery_result.cart.items}
    assert "SPIN-BREAD-400G" in recovered_spins
    assert "SPIN-TOMATO-1KG" in recovered_spins

    # Ensure unavailable 1L milk was replaced
    assert "SPIN-MILK-1L" not in recovered_spins

    # Ensure replacement (Amul 500ml with multiple 2) is present
    assert "SPIN-MILK-500ML" in recovered_spins
    assert recovered_spins["SPIN-MILK-500ML"].quantity == 2

    # Verify vegetarian constraint and budget constraints hold on recovered cart
    assert recovery_result.cart.grand_total <= contract.budget.max_budget
    assert len(recovery_result.verification.violations) == 0

    # 8. Explicit confirmation gate check:
    # Server-side checkout MUST fail if explicit_confirmation is False
    with pytest.raises(UnconfirmedCheckoutError):
        await adapter.checkout(
            cart_id=cart_id,
            payment_method="UPI",
            explicit_confirmation=False,
            address_id=address_id,
        )

    # 9. Consequential Checkout with explicit confirmation
    order = await adapter.checkout(
        cart_id=cart_id,
        payment_method="UPI",
        explicit_confirmation=True,
        address_id=address_id,
    )

    assert order.status == "ORDER_PLACED"
    assert order.order_id.startswith("OD-")
    assert order.grand_total == recovery_result.cart.grand_total
    assert len(order.items) == 3


@pytest.mark.asyncio
async def test_golden_orchestrator_turn_with_oos_recovery() -> None:
    """Conversational GrocerOrchestrator turn-by-turn with OOS recovery and explicit checkout."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = f"golden-orch-{uuid.uuid4().hex[:8]}"
    customer_id = f"cust-orch-{uuid.uuid4().hex[:8]}"

    # Turn 1: user requests milk and bread
    turn1 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me 1L milk and bread under 2000",
    )
    assert turn1.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert turn1.requires_confirmation is True

    # Now inject OOS on 1L milk
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    # Turn 2: User says "add tomatoes too"
    turn2 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="add tomatoes too",
    )
    assert turn2.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert turn2.requires_confirmation is True
    assert turn2.basket_summary is not None

    names = [it.name.lower() for it in turn2.basket_summary.items]
    assert any("bread" in n for n in names)
    assert any("tomato" in n for n in names)
    assert any("milk" in n for n in names)

    # Confirm checkout
    confirm_res = await orchestrator.handle_confirm(session_id=session_id)
    assert confirm_res.conversation_state == ConversationState.ORDERED
    assert confirm_res.order_id is not None

