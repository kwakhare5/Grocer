"""LoopingRecoveryEngine — canonical bounded multi-turn recovery loop (Spec §10, §12, §20).

Executes the deterministic recovery sequence across live commerce state:
1. Fetch live cart from CommercePort (never trust stale local cart).
2. Verify live cart against full IntentContract.
3. If verification PASS: complete immediately with RECOVERED.
4. Generate candidate recovery outcome via deterministic recover().
5. If outcome is NEEDS_USER_DECISION, BLOCKED, or FAILED: stop and return.
6. Guard against repeating identical failed actions (infinite-loop prevention).
7. Apply authorized mutation or controlled non-mutating retry/refresh.
   - Preserves ALL unrelated cart items.
   - Non-mutating retries/refreshes never fake cart updates.
8. Re-fetch live cart from CommercePort after mutation.
9. Re-verify live cart against full IntentContract.
10. Return RECOVERED on PASS, or continue next iteration with fresh live cart verification.
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
    """Bounded, deterministic recovery loop orchestrator (Spec §10, §12)."""

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
        verifier: Optional[IntentVerifier] = None,
        attempt_number: int = 1,
    ) -> LoopingRecoveryResult:
        """Run the canonical multi-turn recovery loop up to max_attempts.

        Every recovery iteration executes the strict sequence:
        1. get_cart() — fetch live provider cart (never trust stale state)
        2. verifier.verify() — verify live cart against full IntentContract
        3. recover() — generate candidate recovery actions via deterministic policy
        4. apply authorized mutation or controlled non-mutating retry/refresh
        5. get_cart() again — fetch fresh provider cart after action
        6. verify again — re-verify live cart against full IntentContract
        7. either return success, return user decision/blocked/failed, or continue
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        effective_verifier = verifier or self._verifier
        all_notes: list[str] = []
        all_actions: list[RecoveryAction] = []
        attempted_action_signatures: set[str] = set()
        current_catalog = available_products
        last_outcome: Optional[RecoveryOutcome] = None

        for attempt in range(attempt_number, max_attempts + 1):
            # 1. Fetch live cart
            cart = await commerce_port.get_cart(cart_id)

            # 2. Verify against full intent
            verification = effective_verifier.verify(contract, cart)
            if verification.status == VerificationStatus.PASS:
                return LoopingRecoveryResult(
                    state=RecoveryState.RECOVERED,
                    cart=cart,
                    verification=verification,
                    outcome=last_outcome or RecoveryOutcome(
                        state=RecoveryState.RECOVERED,
                        failure_class=FailureClass.UNKNOWN,
                        message="Intent verified against live commerce state.",
                        attempt_number=attempt,
                        can_auto_apply=True,
                        remaining_violations=[],
                    ),
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            # 3. Generate candidate recovery outcome via deterministic recover()
            outcome = self._recovery.recover(
                contract=contract,
                cart=cart,
                verification_result=verification,
                available_products=current_catalog,
                attempt_number=attempt,
                max_attempts=max_attempts,
            )
            last_outcome = outcome

            # Terminal states: non-recoverable, user decision needed, or unauthorized
            if outcome.state != RecoveryState.RECOVERED or not outcome.can_auto_apply or not outcome.recovery_actions:
                return LoopingRecoveryResult(
                    state=outcome.state,
                    cart=cart,
                    verification=verification,
                    outcome=outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            # Infinite-loop guard: check if identical recovery actions repeated
            action_sig = ";".join(
                f"{a.action_type}:{a.spin_id}:{a.quantity}" for a in outcome.recovery_actions
            )
            if action_sig in attempted_action_signatures:
                loop_outcome = RecoveryOutcome(
                    state=RecoveryState.FAILED,
                    failure_class=outcome.failure_class,
                    message=f"Loop detected: identical recovery actions ({action_sig}) repeated",
                    attempt_number=attempt,
                    can_auto_apply=False,
                    remaining_violations=verification.violations,
                )
                return LoopingRecoveryResult(
                    state=RecoveryState.FAILED,
                    cart=cart,
                    verification=verification,
                    outcome=loop_outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )
            attempted_action_signatures.add(action_sig)

            # 4. Apply authorized mutation or controlled non-mutating retry/refresh
            mutation_actions = [
                a
                for a in outcome.recovery_actions
                if a.action_type in ("add_item", "replace_item", "remove_item", "adjust_quantity")
            ]
            non_mutation_actions = [
                a
                for a in outcome.recovery_actions
                if a.action_type in ("retry", "refresh_cart")
            ]

            if mutation_actions:
                updates = self._build_cart_updates(cart, outcome)
                if not updates:
                    outcome.state = RecoveryState.FAILED
                    outcome.can_auto_apply = False
                    outcome.message = "Recovery produced no executable cart mutation."
                    outcome.remaining_violations = verification.violations
                    return LoopingRecoveryResult(
                        state=RecoveryState.FAILED,
                        cart=cart,
                        verification=verification,
                        outcome=outcome,
                        attempts=attempt,
                        recovery_notes=all_notes,
                        actions_taken=all_actions,
                    )
                await commerce_port.update_cart(
                    items=updates, cart_id=cart_id, address_id=address_id
                )
            elif non_mutation_actions:
                # Controlled non-mutating provider operation: re-fetch / refresh
                # Do NOT fake retries through update_cart()!
                try:
                    current_catalog = await commerce_port.get_go_to_items(address_id or "")
                except Exception:
                    pass

            for a in outcome.recovery_actions:
                all_actions.append(a)
                all_notes.append(a.reason)

            # 5. Live cart re-fetch after mutation
            live_cart_after = await commerce_port.get_cart(cart_id)

            # 6. Full re-verification against intent
            reverification = effective_verifier.verify(contract, live_cart_after)

            # 7. Either return success, return user decision/blocked/failed, or continue
            if reverification.status == VerificationStatus.PASS:
                recovered_outcome = RecoveryOutcome(
                    state=RecoveryState.RECOVERED,
                    failure_class=outcome.failure_class,
                    recovery_actions=outcome.recovery_actions,
                    candidates_for_user=outcome.candidates_for_user,
                    message=f"Successfully recovered intent: {outcome.message}",
                    attempt_number=attempt,
                    can_auto_apply=True,
                    remaining_violations=[],
                )
                return LoopingRecoveryResult(
                    state=RecoveryState.RECOVERED,
                    cart=live_cart_after,
                    verification=reverification,
                    outcome=recovered_outcome,
                    attempts=attempt,
                    recovery_notes=all_notes,
                    actions_taken=all_actions,
                )

            # If reverification failed and this was not a non-mutation action, refresh catalog
            if not non_mutation_actions:
                try:
                    current_catalog = await commerce_port.get_go_to_items(address_id or "")
                except Exception:
                    pass

        # Reached max_attempts without PASS
        final_cart = await commerce_port.get_cart(cart_id)
        final_verification = effective_verifier.verify(contract, final_cart)
        return LoopingRecoveryResult(
            state=RecoveryState.FAILED,
            cart=final_cart,
            verification=final_verification,
            outcome=RecoveryOutcome(
                state=RecoveryState.FAILED,
                failure_class=last_outcome.failure_class if last_outcome else FailureClass.UNKNOWN,
                message=f"Recovery aborted: exceeded maximum attempts ({max_attempts})",
                attempt_number=max_attempts,
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
        """Delegate to canonical run() loop and adapt result to tuple (CommerceCart, VerificationResult, RecoveryOutcome)."""
        res = await self.run(
            contract=contract,
            cart_id=cart_id,
            commerce_port=commerce_port,
            available_products=available_products,
            max_attempts=max_attempts,
            address_id=address_id,
            verifier=verifier,
            attempt_number=attempt_number,
        )
        outcome = res.outcome or RecoveryOutcome(
            state=res.state,
            failure_class=FailureClass.UNKNOWN,
            message="Intent verified against live commerce state.",
            attempt_number=res.attempts,
            can_auto_apply=(res.state == RecoveryState.RECOVERED),
            remaining_violations=res.verification.violations,
        )
        return res.cart, res.verification, outcome

    @staticmethod
    def _build_cart_updates(cart: CommerceCart, outcome: RecoveryOutcome) -> list[CartItemUpdate]:
        """Materialize authorized replacement/addition/removal/quantity actions into cart updates."""
        mutation_actions = [
            a
            for a in outcome.recovery_actions
            if a.action_type in ("add_item", "replace_item", "remove_item", "adjust_quantity")
        ]
        removed_spins = {a.removes_spin_id for a in mutation_actions if a.removes_spin_id}
        removed_spins.update(
            a.spin_id for a in mutation_actions if a.action_type == "remove_item"
        )
        adjusted_quantities = {
            a.spin_id: a.quantity
            for a in mutation_actions
            if a.action_type == "adjust_quantity"
        }

        updates: list[CartItemUpdate] = []
        for item in cart.items:
            if item.spin_id not in removed_spins:
                qty = adjusted_quantities.get(item.spin_id, item.quantity)
                updates.append(CartItemUpdate(spin_id=item.spin_id, quantity=qty))

        for action in mutation_actions:
            if action.action_type in ("add_item", "replace_item"):
                updates.append(CartItemUpdate(spin_id=action.spin_id, quantity=action.quantity))

        return updates


__all__ = ["LoopingRecoveryEngine", "LoopingRecoveryResult"]
