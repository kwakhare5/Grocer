"""Bounded closed-loop recovery coordinator for Intent commerce.

This module keeps candidate generation/policy decisions in RecoveryEngine and adds
one missing responsibility: repeatedly observe, recover, mutate, and re-verify until
the intent is restored or the bounded attempt budget is exhausted.
"""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import CartItemUpdate, CommerceCart, CommerceProductItem
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import IntentContract
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import RecoveryEngine, RecoveryOutcome, RecoveryState
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus


class LoopingRecoveryEngine(RecoveryEngine):
    """RecoveryEngine with a bounded verify-after-mutation loop.

    The inherited ``recover`` method remains the deterministic decision engine.
    This class only owns orchestration of repeated recovery attempts.
    """

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
        """Run bounded recovery until PASS, user decision, block, or exhaustion."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        current_verification = verification_result
        current_catalog = available_products
        last_outcome: Optional[RecoveryOutcome] = None

        for attempt in range(attempt_number, max_attempts + 1):
            cart = await commerce_port.get_cart(cart_id)

            # The live cart is authoritative at every iteration. A PASS ends recovery.
            if current_verification.status == VerificationStatus.PASS:
                return cart, current_verification, RecoveryOutcome(
                    state=RecoveryState.RECOVERED,
                    failure_class=last_outcome.failure_class if last_outcome else self._classify(current_verification, cart),
                    recovery_actions=[],
                    message="Intent verified after recovery.",
                    attempt_number=attempt,
                    can_auto_apply=True,
                    remaining_violations=[],
                )

            outcome = self.recover(
                contract,
                cart,
                current_verification,
                current_catalog,
                attempt_number=attempt,
                max_attempts=max_attempts,
            )
            last_outcome = outcome

            # Human decision / blocked / already-terminal paths stop immediately.
            if not outcome.can_auto_apply or not outcome.recovery_actions:
                return cart, current_verification, outcome

            updates = self._build_cart_updates(cart, outcome)
            updated_cart = await commerce_port.update_cart(
                items=updates,
                cart_id=cart_id,
                address_id=address_id,
            )

            # Every autonomous mutation must be re-verified against the same contract.
            current_verification = verifier.verify(contract, updated_cart)
            if current_verification.status == VerificationStatus.PASS:
                outcome.state = RecoveryState.RECOVERED
                outcome.message = f"Successfully recovered intent: {outcome.message}"
                outcome.remaining_violations = []
                return updated_cart, current_verification, outcome

            outcome.remaining_violations = current_verification.violations

            # Refresh the catalog before the next attempt so recovery does not keep
            # making decisions against a stale candidate set when the provider allows it.
            try:
                current_catalog = await commerce_port.get_go_to_items(address_id or "")
            except Exception:
                # Keep the last known catalog; deterministic recovery will decide whether
                # another attempt is still safe.
                pass

        # We mutated and re-verified on every permitted attempt, but intent still fails.
        final_cart = await commerce_port.get_cart(cart_id)
        final_verification = verifier.verify(contract, final_cart)
        failure_class = last_outcome.failure_class if last_outcome else self._classify(final_verification, final_cart)
        return final_cart, final_verification, RecoveryOutcome(
            state=RecoveryState.FAILED,
            failure_class=failure_class,
            recovery_actions=last_outcome.recovery_actions if last_outcome else [],
            message=f"Recovery exhausted after {max_attempts} attempt(s) without restoring the intent.",
            attempt_number=max_attempts,
            can_auto_apply=False,
            remaining_violations=final_verification.violations,
        )

    @staticmethod
    def _build_cart_updates(cart: CommerceCart, outcome: RecoveryOutcome) -> list[CartItemUpdate]:
        """Materialize authorized recovery actions into a complete cart update."""
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
                updates.append(
                    CartItemUpdate(spin_id=action.spin_id, quantity=action.quantity)
                )
        return updates


__all__ = ["LoopingRecoveryEngine"]
