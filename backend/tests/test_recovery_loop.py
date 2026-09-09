"""Unit and integration tests for LoopingRecoveryEngine (Spec §10, Task 5).

Covers:
1. recovery retries after failed reverification
2. canonical intent API surface, choice rejection, and explicit confirmation
3. no-op / already valid cart -> RECOVERED without mutations
4. one successful recovery -> RECOVERED with verified cart
5. unrelated cart items preserved across substitutions
6. repeated failure until max attempts -> FAILED
7. user decision required -> stops loop in NEEDS_USER_DECISION
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import (
    AuthorizationScope,
    BudgetConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SubstitutionPolicy,
)
from backend.intent.recovery import (
    FailureClass,
    RecoveryAction,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus


class FakeCommercePort(CommercePort):
    def __init__(self) -> None:
        self.get_cart_calls = 0
        self.update_calls = 0
        self.refresh_calls = 0
        self.cart = CommerceCart(
            cart_id="cart-1",
            items=[],
            item_total=0.0,
            grand_total=0.0,
            is_serviceable=True,
        )

    async def get_addresses(self, customer_id: str):
        return []

    async def get_go_to_items(self, address_id: str):
        self.refresh_calls += 1
        return []

    async def search_products(self, address_id: str, query: str):
        return []

    async def get_cart(self, cart_id=None):
        self.get_cart_calls += 1
        return self.cart

    async def update_cart(self, items: list[CartItemUpdate], cart_id=None, address_id=None):
        self.update_calls += 1
        self.cart = CommerceCart(
            cart_id="cart-1",
            items=[],
            item_total=10.0 * self.update_calls,
            grand_total=10.0 * self.update_calls,
            is_serviceable=True,
        )
        return self.cart

    async def clear_cart(self, cart_id=None):
        return True

    async def get_payment_options(self, cart_id=None, address_id=None):
        return []

    async def checkout(self, cart_id: str, payment_method="UPI", explicit_confirmation=False, address_id=None):
        raise AssertionError("checkout is not part of recovery-loop test")

    async def check_payment_status(self, paas_id: str, order_id=None):
        raise AssertionError("payment is not part of recovery-loop test")

    async def confirm_order(self, order_id: str, paas_id: str):
        raise AssertionError("payment is not part of recovery-loop test")

    async def get_orders(self, count: int = 10, active_only: bool = False):
        raise AssertionError("orders are not part of recovery-loop test")

    async def get_order_details(self, order_id: str):
        raise AssertionError("orders are not part of recovery-loop test")

    async def get_delivery_status(self, order_id: str, address_id: str):
        raise AssertionError("tracking is not part of recovery-loop test")

    async def track_order(self, order_id: str, lat=None, lng=None):
        raise AssertionError("tracking is not part of recovery-loop test")


class TwoAttemptRecoveryVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, contract, cart):
        self.calls += 1
        # Intent is only satisfied when second recovery attempt mutates cart to grand_total >= 20.0
        if cart.grand_total >= 20.0:
            return VerificationResult(status=VerificationStatus.PASS)
        return VerificationResult(status=VerificationStatus.FAIL)


class CountingRecoveryEngine(LoopingRecoveryEngine):
    def __init__(self) -> None:
        super().__init__()
        self.recover_calls = 0

    def recover(self, *args, **kwargs):
        self.recover_calls += 1
        return RecoveryOutcome(
            state=RecoveryState.RECOVERED,
            failure_class=FailureClass.ITEM_UNAVAILABLE,
            recovery_actions=[
                RecoveryAction(
                    action_type="add_item",
                    spin_id=f"replacement-{self.recover_calls}",
                    name=f"Replacement {self.recover_calls}",
                    quantity=1,
                    price=10.0,
                    reason="test recovery",
                )
            ],
            message=f"attempt {self.recover_calls}",
            attempt_number=self.recover_calls,
            can_auto_apply=True,
        )


class AuthFailureAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.get_cart_calls = 0

    async def get_cart(self, cart_id=None):  # type: ignore[no-untyped-def]
        self.get_cart_calls += 1
        raise ProviderAuthError("reauthentication required")


@pytest.mark.asyncio
async def test_recovery_does_not_retry_provider_auth_failure() -> None:
    adapter = AuthFailureAdapter()
    result = await LoopingRecoveryEngine().run(
        contract=IntentContract(
            session_id="auth-failure",
            goal="test auth failure",
            items=[],
        ),
        cart_id="cart",
        commerce_port=adapter,
        available_products=[],
        max_attempts=3,
    )

    assert result.state == RecoveryState.FAILED
    assert result.attempts == 1
    assert adapter.get_cart_calls == 1


@pytest.mark.asyncio
async def test_recovery_retries_after_failed_reverification() -> None:
    port = FakeCommercePort()
    verifier = TwoAttemptRecoveryVerifier()
    engine = CountingRecoveryEngine()
    contract = IntentContract(
        session_id="session-1",
        goal="weekly restock",
        items=[],
    )

    initial = VerificationResult(status=VerificationStatus.FAIL)
    cart, result, outcome = await engine.execute_recovery(
        contract=contract,
        cart_id="cart-1",
        commerce_port=port,
        verifier=verifier,
        available_products=[],
        verification_result=initial,
        max_attempts=3,
    )

    assert outcome.state == RecoveryState.RECOVERED
    assert result.status == VerificationStatus.PASS
    assert engine.recover_calls == 2
    assert verifier.calls == 4
    assert port.update_calls == 2
    assert port.get_cart_calls == 4
    assert port.refresh_calls == 1
    assert cart.grand_total == 20.0


@pytest.mark.asyncio
async def test_intent_api_exposes_canonical_chat_surface(client: AsyncClient) -> None:
    created = await client.post("/api/intent/sessions", json={})
    credentials = created.json()
    headers = {
        "X-Grocer-Session-Capability": credentials["session_capability"]
    }
    response = await client.post(
        "/api/intent/chat",
        json={
            "session_id": credentials["session_id"],
            "message": "buy 1L milk",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == credentials["session_id"]
    assert body["conversation_state"].lower() in {"awaiting_confirmation", "failed", "needs_decision"}
    assert isinstance(body["events"], list)


@pytest.mark.asyncio
async def test_intent_api_rejects_unoffered_choice(client: AsyncClient) -> None:
    response = await client.post(
        "/api/intent/sessions/missing-choice-session/choice",
        json={
            "chosen_spin_id": "SPIN-NOT-OFFERED",
            "clarification_nonce": "missing-choice-nonce",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_intent_api_requires_explicit_confirmation(client: AsyncClient) -> None:
    created = await client.post("/api/intent/sessions", json={})
    credentials = created.json()
    response = await client.post(
        f"/api/intent/sessions/{credentials['session_id']}/confirm",
        json={"explicit_confirmation": False, "payment_method": "UPI"},
        headers={
            "X-Grocer-Session-Capability": credentials["session_capability"]
        },
    )

    assert response.status_code == 400


def _make_contract(items: list[IntentItem], max_budget: float = 2000.0) -> IntentContract:
    return IntentContract(
        session_id="loop-test-session",
        goal="weekly groceries",
        items=items,
        budget=BudgetConstraint(max_budget=max_budget, is_hard=True, max_deviation=0.0),
        pack_size_rules=PackSizeRules(preferred_multiples=True),
        substitution_policy=SubstitutionPolicy(),
    )


@pytest.mark.asyncio
async def test_loop_no_op_valid_cart() -> None:
    """If the cart already satisfies the intent contract, loop returns RECOVERED immediately."""
    adapter = MockCommerceAdapter()
    engine = LoopingRecoveryEngine()

    contract = _make_contract([
        IntentItem(name="milk", quantity=1, pack_size_preference="1 L"),
    ])
    await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
        cart_id="test-loop-1",
    )
    available = await adapter.get_go_to_items("addr-bandra-1")

    result = await engine.run(
        contract=contract,
        cart_id="test-loop-1",
        commerce_port=adapter,
        available_products=available,
        max_attempts=3,
    )

    assert result.state == RecoveryState.RECOVERED
    assert result.attempts == 1
    assert result.verification.status == VerificationStatus.PASS
    assert len(result.actions_taken) == 0


@pytest.mark.asyncio
async def test_loop_single_successful_recovery_and_preserves_unrelated() -> None:
    """When an item becomes unavailable, loop replaces it and preserves other items."""
    adapter = MockCommerceAdapter()
    engine = LoopingRecoveryEngine()

    contract = _make_contract([
        IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy"),
        IntentItem(name="bread", quantity=1, pack_size_preference="400 g", category="bakery"),
    ])
    contract.authorization_scope = AuthorizationScope(
        requires_approval_for_price_increase=False,
    )

    # Initial cart has 1L milk and bread
    await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
        ],
        cart_id="test-loop-2",
    )

    # Inject failure: 1L milk goes OOS
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    available = await adapter.search_products("addr-bandra-1", "")

    result = await engine.run(
        contract=contract,
        cart_id="test-loop-2",
        commerce_port=adapter,
        available_products=available,
        max_attempts=3,
    )

    # Recovery should succeed with 500ml milk (2x) or alternative
    assert result.state == RecoveryState.RECOVERED
    assert result.verification.status == VerificationStatus.PASS

    # Check that bread is strictly preserved in the final cart!
    final_spins = [item.spin_id for item in result.cart.items]
    assert "SPIN-BREAD-400G" in final_spins
    # And 1L milk is replaced
    assert "SPIN-MILK-1L" not in final_spins


@pytest.mark.asyncio
async def test_loop_repeated_failure_until_max_attempts() -> None:
    """When no compliant substitute can be found, loop aborts after max_attempts."""
    adapter = MockCommerceAdapter()
    engine = LoopingRecoveryEngine()

    contract = _make_contract([
        IntentItem(name="dragonfruit", quantity=1, is_essential=True, category="exotic"),
    ])
    # Empty cart or cart with no dragonfruit
    await adapter.update_cart(items=[], cart_id="test-loop-3")

    available = await adapter.search_products("addr-bandra-1", "")

    result = await engine.run(
        contract=contract,
        cart_id="test-loop-3",
        commerce_port=adapter,
        available_products=available,
        max_attempts=3,
    )

    assert result.state in (RecoveryState.FAILED, RecoveryState.BLOCKED)
    assert result.verification.status == VerificationStatus.FAIL


@pytest.mark.asyncio
async def test_loop_user_decision_required() -> None:
    """When ambiguity exists, loop halts in NEEDS_USER_DECISION without guessing."""
    adapter = MockCommerceAdapter()
    engine = LoopingRecoveryEngine()

    # Stale cart always requires user decision
    contract = _make_contract([
        IntentItem(name="milk", quantity=1),
    ])
    await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
        cart_id="test-loop-4",
    )
    adapter.inject_stale_cart(True)

    available = await adapter.search_products("addr-bandra-1", "")

    result = await engine.run(
        contract=contract,
        cart_id="test-loop-4",
        commerce_port=adapter,
        available_products=available,
        max_attempts=3,
    )

    assert result.state == RecoveryState.NEEDS_USER_DECISION
    assert result.outcome is not None
    assert result.outcome.failure_class == FailureClass.STALE_CART
