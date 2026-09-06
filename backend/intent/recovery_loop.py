"""LoopingRecoveryEngine — bounded multi-turn recovery loop (Spec §10, §20 Phase 5/7).

Executes the deterministic 10-step recovery sequence across live commerce state:
1. Fetch live cart from CommercePort (never trust stale local cart).
2. Verify live cart against full IntentContract.
3. If verification PASS: complete immediately with RECOVERED (or no-op).
4. Check bounded limit (attempt <= max_attempts).
5. Compute RecoveryOutcome via RecoveryEngine (filter hard constraints, rank candidates).
6. If outcome is NEEDS_USER_DECISION, BLOCKED, or FAILED: stop and return.
7. If outcome can_auto_apply: apply authorized actions without deleting unrelated cart items.
   - Guard against repeating identical failed actions (infinite-loop prevention).
8. Fetch live cart again from CommercePort.
9. Verify again against full IntentContract.
10. Loop until clean pass, user decision required, or max attempts reached.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import IntentContract
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import (
    FailureClass,
    RecoveryAction,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus


class LoopingRecoveryResult(BaseModel):
    """Result of running LoopingRecoveryEngine."""
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    state: RecoveryState
    cart: CommerceCart
    verification: VerificationResult
    outcome: Optional[RecoveryOutcome] = None
    attempts: int = 1
    recovery_notes: list[str] = Field(default_factory=list)
    actions_taken: list[RecoveryAction] = Field(default_factory=list)


class LoopingRecoveryEngine(RecoveryEngine):
    """Bounded, deterministic recovery loop orchestrator (Spec §10)."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        verifier: Optional[IntentVerifier] = None,
        recovery_engine: Optional[RecoveryEngine] = None,
    ) -> None:
        super().__init__(policy_engine=policy_engine)
        self._policy = policy_engine or PolicyEngine()
        self._verifier = verifier or IntentVerifier()
        self._recovery = recovery_engine or self

    async def run(
        self,
        contract: IntentContract,
        cart_id: str,
        commerce_port: CommercePort,
        available_products: list[CommerceProductItem],
        *,
        max_attempts: int = 3,
        address_id: Optional[str] = None,
    ) -> LoopingRecoveryResult:
        """Run the multi-turn recovery loop up to max_attempts."""
        all_notes: list[str] = []
        all_actions: list[RecoveryAction] = []
        attempted_action_signatures: set[str] = set()

        for attempt in range(1, max_attempts + 1):
            # 1. Fetch live cart
            cart = await commerce_port.get_cart(cart_id)

            # 2. Verify against full intent
            verification = self._verifier.verify(contract, cart)

            # 3. If PASS, stop immediately
            if verification.status == VerificationStatus.PASS:
                return LoopingRecoveryResult(
                    state=RecoveryState.RECOVERED,
                    cart=cart,
                    verification=verification,
                    outcome=None,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            # 4. Generate candidate recovery outcome
            outcome = self._recovery.recover(
                contract=contract,
                cart=cart,
                verification_result=verification,
                available_products=available_products,
                attempt_number=attempt,
                max_attempts=max_attempts,
            )

            # 5. Non-auto-executable outcomes stop the loop
            if outcome.state != RecoveryState.RECOVERED or not outcome.can_auto_apply:
                return LoopingRecoveryResult(
                    state=outcome.state,
                    cart=cart,
                    verification=verification,
                    outcome=outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            if not outcome.recovery_actions:
                return LoopingRecoveryResult(
                    state=outcome.state,
                    cart=cart,
                    verification=verification,
                    outcome=outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            # 6. Infinite-loop guard: check if identical recovery actions repeated
            action_sig = ";".join(
                f"{a.action_type}:{a.spin_id}:{a.quantity}" for a in outcome.recovery_actions
            )
            if action_sig in attempted_action_signatures:
                return LoopingRecoveryResult(
                    state=RecoveryState.FAILED,
                    cart=cart,
                    verification=verification,
                    outcome=RecoveryOutcome(
                        state=RecoveryState.FAILED,
                        failure_class=outcome.failure_class,
                        message=f"Loop detected: identical recovery actions ({action_sig}) repeated",
                        attempt_number=attempt,
                        can_auto_apply=False,
                        remaining_violations=verification.violations,
                    ),
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )
            attempted_action_signatures.add(action_sig)

            # 7. Apply authorized actions while preserving ALL unrelated items
            mutation_actions = [
                a
                for a in outcome.recovery_actions
                if a.action_type in ("add_item", "replace_item", "remove_item", "adjust_quantity")
            ]

            if mutation_actions:
                updates: list[CartItemUpdate] = []
                removed_spins = {a.removes_spin_id for a in mutation_actions if a.removes_spin_id}
                removed_spins.update(
                    a.spin_id for a in mutation_actions if a.action_type == "remove_item"
                )
                adjusted_quantities = {
                    a.spin_id: a.quantity
                    for a in mutation_actions
                    if a.action_type == "adjust_quantity"
                }

                for item in cart.items:
                    if item.spin_id not in removed_spins:
                        qty = adjusted_quantities.get(item.spin_id, item.quantity)
                        updates.append(CartItemUpdate(spin_id=item.spin_id, quantity=qty))

                for action in mutation_actions:
                    if action.action_type in ("add_item", "replace_item"):
                        updates.append(CartItemUpdate(spin_id=action.spin_id, quantity=action.quantity))

                await commerce_port.update_cart(
                    items=updates, cart_id=cart_id, address_id=address_id
                )

            for a in outcome.recovery_actions:
                all_actions.append(a)
                all_notes.append(a.reason)

            # 8. Re-fetch live cart again to verify outcome
            cart = await commerce_port.get_cart(cart_id)
            new_verification = self._verifier.verify(contract, cart)
            if new_verification.status == VerificationStatus.PASS:
                return LoopingRecoveryResult(
                    state=RecoveryState.RECOVERED,
                    cart=cart,
                    verification=new_verification,
                    outcome=outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

        # Reached max_attempts without PASS
        final_cart = await commerce_port.get_cart(cart_id)
        final_verification = self._verifier.verify(contract, final_cart)
        return LoopingRecoveryResult(
            state=RecoveryState.FAILED,
            cart=final_cart,
            verification=final_verification,
            outcome=RecoveryOutcome(
                state=RecoveryState.FAILED,
                failure_class=FailureClass.UNKNOWN,
                message=f"Recovery aborted: exceeded maximum attempts ({max_attempts})",
                attempt_number=max_attempts + 1,
                can_auto_apply=False,
                remaining_violations=final_verification.violations,
            ),
            attempts=max_attempts,
            recovery_notes=all_notes,
            actions_taken=all_actions,
        )

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
        """Recover until the live cart satisfies intent or the loop is exhausted (HEAD compatibility)."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        current_catalog = available_products
        last_outcome: Optional[RecoveryOutcome] = None
        current_hint = verification_result

        for attempt in range(attempt_number, max_attempts + 1):
            cart = await commerce_port.get_cart(cart_id)

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


__all__ = ["LoopingRecoveryEngine", "LoopingRecoveryResult"]
