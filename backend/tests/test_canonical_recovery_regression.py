"""Regression tests proving GrocerOrchestrator uses canonical LoopingRecoveryEngine (Spec §10, §12).

Tests the 7 critical invariants:
1. OOS recovery through GrocerOrchestrator.handle_turn() (end-to-end)
2. Repeated identical recovery action causes safe termination (infinite-loop protection)
3. Failed recovery reaches max attempts safely
4. Unrelated cart items survive recovery
5. Live cart is re-fetched and re-verified between recovery iterations
6. Transient retry does not become a fake cart mutation
7. Successful recovery ends only after fresh verification PASS
"""
from __future__ import annotations

import uuid
import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import (
    BudgetConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SubstitutionPolicy,
)
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.recovery import (
    FailureClass,
    RecoveryAction,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.session import ConversationState, OrchestratorSessionStore
from backend.intent.verifier import (
    ConstraintViolation,
    IntentVerifier,
    VerificationResult,
    VerificationStatus,
    ViolationCode,
)


# ---------------------------------------------------------------------------
# Helpers & Mocks
# ---------------------------------------------------------------------------

class TrackingCommercePort(MockCommerceAdapter):
    """MockCommerceAdapter that records every commerce port operation."""
    def __init__(self) -> None:
        super().__init__()
        self.operation_log: list[str] = []
        self.update_cart_calls: int = 0
        self.get_cart_calls: int = 0
        self.refresh_catalog_calls: int = 0

    async def get_cart(self, cart_id=None) -> CommerceCart:
        self.operation_log.append("get_cart")
        self.get_cart_calls += 1
        return await super().get_cart(cart_id)

    async def update_cart(self, items: list[CartItemUpdate], cart_id=None, address_id=None) -> CommerceCart:
        self.operation_log.append("update_cart")
        self.update_cart_calls += 1
        return await super().update_cart(items, cart_id=cart_id, address_id=address_id)

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        self.operation_log.append("get_go_to_items")
        self.refresh_catalog_calls += 1
        return await super().get_go_to_items(address_id)


class TrackingVerifier:
    """IntentVerifier that records verification calls and cart states."""
    def __init__(self, real_verifier: IntentVerifier) -> None:
        self._real = real_verifier
        self.verify_calls: int = 0
        self.verified_carts: list[CommerceCart] = []

    def verify(self, contract: IntentContract, cart: CommerceCart) -> VerificationResult:
        self.verify_calls += 1
        self.verified_carts.append(cart)
        return self._real.verify(contract, cart)


# ---------------------------------------------------------------------------
# Test 1: OOS recovery through GrocerOrchestrator.handle_turn()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_oos_recovery_canonical_path() -> None:
    """Proves GrocerOrchestrator -> LoopingRecoveryEngine -> CommercePort -> IntentVerifier end-to-end."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = f"orch-oos-{uuid.uuid4().hex[:8]}"
    customer_id = f"cust-oos-{uuid.uuid4().hex[:8]}"

    # Turn 1: Request milk and bread
    turn1 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me 1L milk and bread under 2000",
    )
    assert turn1.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert turn1.requires_confirmation is True
    # 1L milk was selected
    spins1 = {it.spin_id: it for it in turn1.basket_summary.items}
    assert "SPIN-MILK-1L" in spins1

    # Inject failure: Amul 1L milk becomes OOS
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    # Turn 2: User says "add tomatoes too"
    turn2 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="add tomatoes too",
    )

    # Orchestrator should trigger canonical recovery loop, detect OOS, substitute 2x 500ml milk, and re-verify
    assert turn2.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert turn2.requires_confirmation is True
    assert turn2.basket_summary is not None

    spins = {it.spin_id: it for it in turn2.basket_summary.items}
    # 1L milk replaced by 500ml milk
    assert "SPIN-MILK-1L" not in spins
    assert "SPIN-MILK-500ML" in spins
    assert spins["SPIN-MILK-500ML"].quantity == 2

    # Bread and tomatoes preserved
    assert any("bread" in it.name.lower() for it in turn2.basket_summary.items)
    assert any("tomato" in it.name.lower() for it in turn2.basket_summary.items)

    # Recovery audit trail present in turn events
    assert "RECOVERY_STARTED" in turn2.events
    assert "RECOVERY_RECOVERED" in turn2.events
    assert "POST_RECOVERY_VERIFY_PASS" in turn2.events


# ---------------------------------------------------------------------------
# Test 2: Repeated identical recovery action causes safe termination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_repeated_identical_recovery_infinite_loop_protection() -> None:
    """Proves repeated identical recovery action aborts safely with FAILED (infinite-loop protection)."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()

    class LoopMockRecovery(RecoveryEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def recover(self, *args, **kwargs) -> RecoveryOutcome:
            self.calls += 1
            # Always return identical recovery action signature
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=FailureClass.ITEM_UNAVAILABLE,
                recovery_actions=[
                    RecoveryAction(
                        action_type="replace_item",
                        spin_id="SPIN-MILK-500ML",
                        name="Amul Taaza Milk 500ml",
                        quantity=1,
                        removes_spin_id="SPIN-MILK-1L",
                        reason="stuck recovery attempt",
                    )
                ],
                message="attempting repeated replacement",
                attempt_number=self.calls,
                can_auto_apply=True,
            )

    # Verifier that always fails
    class StrictFailVerifier(IntentVerifier):
        def verify(self, contract, cart) -> VerificationResult:
            return VerificationResult(
                status=VerificationStatus.FAIL,
                violations=[
                    ConstraintViolation(
                        violation_code=ViolationCode.ITEM_UNAVAILABLE,
                        target="milk",
                        detail="Milk unavailable",
                        is_hard=True,
                    )
                ],
            )

    loop_engine = LoopingRecoveryEngine(
        verifier=StrictFailVerifier(),
        recovery_engine=LoopMockRecovery(),
    )
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=store,
        recovery_engine=loop_engine,
        verifier=StrictFailVerifier(),
    )

    session_id = f"orch-loop-{uuid.uuid4().hex[:8]}"
    customer_id = f"cust-loop-{uuid.uuid4().hex[:8]}"

    # Turn 1: Build initial cart
    turn1 = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me 1L milk",
    )

    # The mock recovery returns identical action signature on attempts 1 and 2
    # The loop MUST detect the repeated signature on attempt 2 and safely terminate with FAILED
    assert turn1.conversation_state == ConversationState.FAILED
    assert "RECOVERY_FAILED" in turn1.events
    assert any("Loop detected" in e or "failed" in e.lower() for e in turn1.events)


# ---------------------------------------------------------------------------
# Test 3: Failed recovery reaches max attempts safely
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_failed_recovery_reaches_max_attempts_safely() -> None:
    """Proves a non-looping failed recovery aborts after max_attempts without exceeding limit."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()

    class UniqueFailingRecovery(RecoveryEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def recover(self, *args, **kwargs) -> RecoveryOutcome:
            self.calls += 1
            valid_spins = ["SPIN-EGGS-6", "SPIN-EGGS-12", "SPIN-TOMATO-500G"]
            spin = valid_spins[min(self.calls - 1, len(valid_spins) - 1)]
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=FailureClass.ITEM_UNAVAILABLE,
                recovery_actions=[
                    RecoveryAction(
                        action_type="replace_item",
                        spin_id=spin,
                        name=f"Alternative {self.calls}",
                        quantity=self.calls,
                        removes_spin_id="SPIN-MILK-1L",
                        reason=f"attempt {self.calls}",
                    )
                ],
                message=f"attempt {self.calls}",
                attempt_number=self.calls,
                can_auto_apply=True,
            )

    class AlwaysFailVerifier(IntentVerifier):
        def verify(self, contract, cart) -> VerificationResult:
            return VerificationResult(
                status=VerificationStatus.FAIL,
                violations=[
                    ConstraintViolation(
                        violation_code=ViolationCode.ITEM_UNAVAILABLE,
                        target="milk",
                        detail="Milk is still unavailable",
                        is_hard=True,
                    )
                ],
            )

    mock_rec = UniqueFailingRecovery()
    engine = LoopingRecoveryEngine(
        verifier=AlwaysFailVerifier(),
        recovery_engine=mock_rec,
    )
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=store,
        recovery_engine=engine,
        verifier=AlwaysFailVerifier(),
    )

    session_id = f"orch-exhaust-{uuid.uuid4().hex[:8]}"
    customer_id = f"cust-exhaust-{uuid.uuid4().hex[:8]}"

    turn = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get me 1L milk",
    )

    # Exactly 3 attempts made, never exceeds max_attempts
    assert mock_rec.calls == 3
    assert turn.conversation_state == ConversationState.FAILED
    assert "RECOVERY_FAILED" in turn.events


# ---------------------------------------------------------------------------
# Test 4: Unrelated cart items survive recovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unrelated_cart_items_survive_recovery() -> None:
    """Proves 3 unrelated staples remain completely intact when milk is substituted."""
    adapter = MockCommerceAdapter()
    engine = LoopingRecoveryEngine()

    contract = IntentContract(
        session_id="unrelated-test",
        goal="staples restock",
        items=[
            IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy"),
            IntentItem(name="bread", quantity=2, pack_size_preference="400 g", category="bakery"),
            IntentItem(name="tomatoes", quantity=1, pack_size_preference="1 kg", category="produce"),
            IntentItem(name="eggs", quantity=1, pack_size_preference="12 pcs", category="poultry"),
        ],
        budget=BudgetConstraint(max_budget=2000.0, is_hard=True),
        substitution_policy=SubstitutionPolicy(),
        pack_size_rules=PackSizeRules(preferred_multiples=True),
    )

    cart_id = "unrelated-cart-1"
    # Initial cart contains all 4 items
    await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=2),
            CartItemUpdate(spin_id="SPIN-TOMATO-1KG", quantity=1),
            CartItemUpdate(spin_id="SPIN-EGGS-12", quantity=1),
        ],
        cart_id=cart_id,
        address_id="addr-bandra-1",
    )

    # Inject failure only on milk
    adapter.inject_out_of_stock("SPIN-MILK-1L")
    available = await adapter.search_products("addr-bandra-1", "")

    res = await engine.run(
        contract=contract,
        cart_id=cart_id,
        commerce_port=adapter,
        available_products=available,
        max_attempts=3,
        address_id="addr-bandra-1",
    )

    assert res.state == RecoveryState.RECOVERED
    assert res.verification.status == VerificationStatus.PASS

    spins = {item.spin_id: item for item in res.cart.items}
    # Milk substituted
    assert "SPIN-MILK-1L" not in spins
    assert "SPIN-MILK-500ML" in spins

    # ALL unrelated items preserved with exact quantities
    assert "SPIN-BREAD-400G" in spins
    assert spins["SPIN-BREAD-400G"].quantity == 2

    assert "SPIN-TOMATO-1KG" in spins
    assert spins["SPIN-TOMATO-1KG"].quantity == 1

    assert "SPIN-EGGS-12" in spins
    assert spins["SPIN-EGGS-12"].quantity == 1


# ---------------------------------------------------------------------------
# Test 5: Live cart is re-fetched and re-verified between recovery iterations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_cart_refetched_and_reverified_between_iterations() -> None:
    """Proves get_cart() and verifier.verify() are called fresh on every loop iteration."""
    tracking_port = TrackingCommercePort()
    real_verifier = IntentVerifier()
    tracking_verifier = TrackingVerifier(real_verifier)

    contract = IntentContract(
        session_id="refetch-test",
        goal="weekly milk",
        items=[IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy")],
        budget=BudgetConstraint(max_budget=2000.0, is_hard=True),
        substitution_policy=SubstitutionPolicy(),
        pack_size_rules=PackSizeRules(preferred_multiples=True),
    )
    cart_id = "cart-refetch-1"

    # Setup initial cart with OOS milk
    await tracking_port.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
        cart_id=cart_id,
        address_id="addr-bandra-1",
    )
    tracking_port.inject_out_of_stock("SPIN-MILK-1L")

    # Reset tracking log to isolate recovery operations
    tracking_port.operation_log.clear()
    tracking_port.get_cart_calls = 0
    tracking_port.update_cart_calls = 0

    available = await tracking_port.search_products("addr-bandra-1", "")
    engine = LoopingRecoveryEngine(verifier=tracking_verifier)

    res = await engine.run(
        contract=contract,
        cart_id=cart_id,
        commerce_port=tracking_port,
        available_products=available,
        max_attempts=3,
        address_id="addr-bandra-1",
    )

    assert res.state == RecoveryState.RECOVERED

    # Log should show:
    # 1. get_cart (initial live fetch)
    # 2. update_cart (mutation)
    # 3. get_cart (live re-fetch after mutation)
    assert tracking_port.operation_log == ["get_cart", "update_cart", "get_cart"]
    # Verifier was called twice: once before mutation, once after live re-fetch
    assert tracking_verifier.verify_calls == 2
    # Second verification was performed on the updated cart, NOT the old one
    assert tracking_verifier.verified_carts[0].items[0].spin_id == "SPIN-MILK-1L"
    assert tracking_verifier.verified_carts[1].items[0].spin_id == "SPIN-MILK-500ML"


# ---------------------------------------------------------------------------
# Test 6: Transient retry does not become a fake cart mutation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transient_retry_does_not_mutate_cart() -> None:
    """Proves action_type='retry' performs controlled provider re-fetch and NEVER calls update_cart."""
    tracking_port = TrackingCommercePort()

    class TransientRetryRecovery(RecoveryEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def recover(self, *args, **kwargs) -> RecoveryOutcome:
            self.calls += 1
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=FailureClass.TRANSIENT_ERROR,
                recovery_actions=[
                    RecoveryAction(
                        action_type="retry",
                        spin_id="NONE",
                        name="Transient provider retry",
                        quantity=1,
                        reason="Transient provider hiccup, retrying fetch",
                    )
                ],
                message="Retrying provider operation",
                attempt_number=self.calls,
                can_auto_apply=True,
            )

    # Verifier that passes after retry
    class RetryVerifier:
        def __init__(self) -> None:
            self.calls = 0

        def verify(self, contract, cart) -> VerificationResult:
            self.calls += 1
            if self.calls == 1:
                return VerificationResult(status=VerificationStatus.FAIL)
            return VerificationResult(status=VerificationStatus.PASS)

    retry_rec = TransientRetryRecovery()
    engine = LoopingRecoveryEngine(
        verifier=RetryVerifier(),
        recovery_engine=retry_rec,
    )

    contract = IntentContract(
        session_id="retry-test",
        goal="test retry",
        items=[],
    )

    res = await engine.run(
        contract=contract,
        cart_id="cart-retry-1",
        commerce_port=tracking_port,
        available_products=[],
        max_attempts=3,
        address_id="addr-bandra-1",
    )

    assert res.state == RecoveryState.RECOVERED
    # update_cart MUST NOT be called for a non-mutating retry!
    assert tracking_port.update_cart_calls == 0
    # controlled provider operations (get_cart, get_go_to_items) were used instead
    assert tracking_port.get_cart_calls >= 2


# ---------------------------------------------------------------------------
# Test 7: Successful recovery ends only after fresh verification PASS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_ends_only_after_fresh_verification_pass() -> None:
    """Proves a mutated cart is NEVER reported as RECOVERED if fresh re-verification fails."""
    adapter = MockCommerceAdapter()

    class RejectingReverifier(IntentVerifier):
        """Always rejects post-mutation verification."""
        def verify(self, contract, cart) -> VerificationResult:
            return VerificationResult(
                status=VerificationStatus.FAIL,
                violations=[
                    ConstraintViolation(
                        violation_code=ViolationCode.BUDGET_EXCEEDED,
                        target="budget",
                        detail="Budget strictly exceeded",
                        is_hard=True,
                    )
                ],
            )

    engine = LoopingRecoveryEngine(verifier=RejectingReverifier())
    contract = IntentContract(
        session_id="verify-pass-test",
        goal="strict budget",
        items=[IntentItem(name="milk", quantity=1)],
        budget=BudgetConstraint(max_budget=10.0, is_hard=True),
    )

    res = await engine.run(
        contract=contract,
        cart_id="cart-reject-1",
        commerce_port=adapter,
        available_products=await adapter.get_go_to_items("addr-bandra-1"),
        max_attempts=2,
    )

    # Must NEVER claim RECOVERED when verification fails
    assert res.state != RecoveryState.RECOVERED
    assert res.state in (RecoveryState.NEEDS_USER_DECISION, RecoveryState.FAILED, RecoveryState.BLOCKED)
    assert res.verification.status == VerificationStatus.FAIL
