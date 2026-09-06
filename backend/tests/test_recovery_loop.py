from __future__ import annotations

import pytest

from backend.integrations.commerce.models import CartItemUpdate, CommerceCart
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import IntentContract
from backend.intent.recovery import FailureClass, RecoveryAction, RecoveryOutcome, RecoveryState
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.verifier import VerificationResult, VerificationStatus


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

    async def get_payment_options(self, cart_id=None):
        return []

    async def checkout(self, cart_id: str, payment_method="UPI", explicit_confirmation=False, address_id=None):
        raise AssertionError("checkout is not part of recovery-loop test")

    async def track_order(self, order_id: str):
        raise AssertionError("tracking is not part of recovery-loop test")


class SequenceVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, contract, cart):
        self.calls += 1
        if self.calls == 1:
            return VerificationResult(status=VerificationStatus.FAIL)
        return VerificationResult(status=VerificationStatus.PASS)


class TwoStepRecoveryEngine(LoopingRecoveryEngine):
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


@pytest.mark.asyncio
async def test_recovery_retries_after_failed_reverification() -> None:
    port = FakeCommercePort()
    verifier = SequenceVerifier()
    engine = TwoStepRecoveryEngine()
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
    assert engine.recover_calls == 1
    assert verifier.calls == 2
    assert port.update_calls == 1
    assert port.get_cart_calls == 1
    assert port.refresh_calls == 0
    assert cart.grand_total == 10.0
