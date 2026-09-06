"""Bounded closed-loop recovery coordinator for intent-preserving commerce."""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import CartItemUpdate, CommerceCart, CommerceProductItem
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import IntentContract
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import RecoveryEngine, RecoveryOutcome, RecoveryState
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus


class LoopingRecoveryEngine(RecoveryEngine):
    """Run observe → recover → mutate → re-verify in a bounded loop."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        super().__init__(policy_engine=policy_engine)

    async def execute_recovery(
        self,
        contract: IntentContract,
        cart_id: str,
        commerce_port: CommercePort,
        verifier: IntentVerifier,
        available_products: list[CommerceProductItem],
        verification_result: VerificationResult,
        *,
        attempt_number: int = 1,
        max_attempts: int = 3,
        address_id: Optional[str] = None,
    ) -> tuple[CommerceCart, VerificationResult, RecoveryOutcome]:
        """Recover until the live cart satisfies intent or the loop is exhausted."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        current_catalog = available_products
        last_outcome: Optional[RecoveryOutcome] = None
        current_hint = verification_result

        for attempt in range(attempt_number, max_attempts + 1):
            cart = await commerce_port.get_cart(cart_id)

            # Never trust an old verification result over live provider state.
            current_verification = verifier.verify(contract, cart)
            if current_verification.status == VerificationStatus.PASS:
                return cart, current_verification, RecoveryOutcome(
                    state=RecoveryState.RECOVERED,
                    failure_class=last_outcome.failure_class if last_outcome else self._classify(current_verification, cart),
                    message="Intent verified against live commerce state.",
                    attempt_number=attempt,
                    can_auto_apply=True,
                    remaining_violations=[],
                )

            # On the first iteration the caller's verification is a useful snapshot;
            # live verification above remains authoritative for the actual decision.
            if attempt == attempt_number and current_hint.status != current_verification.status:
                current_hint = current_verification
            else:
                current_hint = current_verification

            outcome = self.recover(
                contract,
                cart,
                current_hint,
                current_catalog,
                attempt_number=attempt,
                max_attempts=max_attempts,
            )
            last_outcome = outcome

            if not outcome.can_auto_apply or not outcome.recovery_actions:
                return cart, current_hint, outcome

            updates = self._build_cart_updates(cart, outcome)
            if not updates:
                outcome.state = RecoveryState.FAILED
                outcome.can_auto_apply = False
                outcome.message = "Recovery produced no executable cart mutation."
                outcome.remaining_violations = current_hint.violations
                return cart, current_hint, outcome

            updated_cart = await commerce_port.update_cart(
                items=updates,
                cart_id=cart_id,
                address_id=address_id,
            )
            post_verification = verifier.verify(contract, updated_cart)

            if post_verification.status == VerificationStatus.PASS:
                outcome.state = RecoveryState.RECOVERED
                outcome.message = f"Successfully recovered intent: {outcome.message}"
                outcome.remaining_violations = []
                return updated_cart, post_verification, outcome

            outcome.remaining_violations = post_verification.violations
            current_hint = post_verification

            try:
                current_catalog = await commerce_port.get_go_to_items(address_id or "")
            except Exception:
                pass

        final_cart = await commerce_port.get_cart(cart_id)
        final_verification = verifier.verify(contract, final_cart)
        failure_class = last_outcome.failure_class if last_outcome else self._classify(final_verification, final_cart)
        return final_cart, final_verification, RecoveryOutcome(
            state=RecoveryState.FAILED,
            failure_class=failure_class,
            recovery_actions=[],
            message=f"Recovery exhausted after {max_attempts} attempt(s) without restoring the intent.",
            attempt_number=max_attempts,
            can_auto_apply=False,
            remaining_violations=final_verification.violations,
        )

    @staticmethod
    def _build_cart_updates(cart: CommerceCart, outcome: RecoveryOutcome) -> list[CartItemUpdate]:
        """Materialize authorized replacement/addition actions into a full cart update."""
        removed_spins = {
            action.removes_spin_id
            for action in outcome.recovery_actions
            if action.removes_spin_id
        }
        updates = [
            CartItemUpdate(spin_id=item.spin_id, quantity=item.quantity)
            for item in cart.items
            if item.spin_id not in removed_spins
        ]
        for action in outcome.recovery_actions:
            if action.action_type in {"add_item", "replace_item"}:
                updates.append(CartItemUpdate(spin_id=action.spin_id, quantity=action.quantity))
        return updates


__all__ = ["LoopingRecoveryEngine"]
