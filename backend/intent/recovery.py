"""Recovery Engine — deterministic intent drift repair and candidate ranking (Spec Section 10).

When the live commerce state no longer satisfies the user's intent, find the safest
valid path back to the intent or ask the human when no safe path is known.

Architecture:
    VerificationResult + CommerceCart + available_products + IntentContract
    → RecoveryEngine.recover() → RecoveryOutcome

Principles:
    - Zero LLM dependency; candidate generation, filtering, and ranking are deterministic.
    - PolicyEngine is used to gate each candidate action before auto-execution.
    - Bounded recovery: strictly aborts with FAILED when attempt_number > max_attempts.
    - Terminal states: RECOVERED, NEEDS_USER_DECISION, BLOCKED, FAILED.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.models import (
    CartItem,
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent.enums import BrandTolerance, ConstraintType, SubstitutionTolerance
from backend.intent.models import BrandPreference, IntentContract, IntentItem
from backend.intent.policy import (
    ActionProposal,
    AutonomyLevel,
    PolicyDecision,
    PolicyEngine,
)
from backend.intent.verifier import (
    ConstraintViolation,
    IntentVerifier,
    VerificationResult,
    VerificationStatus,
    ViolationCode,
)
from backend.intent.semantics import (
    brand_identity_matches,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
from backend.intent.recovery_candidates import (
    calculate_pack_multiple,
    extract_brand,
    filter_by_hard_constraints,
    find_candidates,
    score_candidate,
)
from backend.intent.recovery_strategies import (
    handle_budget_drift,
    handle_item_or_brand_unavailable,
    handle_min_order_failure,
    handle_stale_cart,
    handle_transient_error,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RecoveryState(str, Enum):
    """Terminal or intermediate state of a recovery attempt (Spec Section 10.4)."""
    RECOVERED = "recovered"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLOCKED = "blocked"
    FAILED = "failed"


class FailureClass(str, Enum):
    """Normalized taxonomy of commerce intent failures (Spec Section 10.2)."""
    ITEM_UNAVAILABLE = "item_unavailable"
    BRAND_UNAVAILABLE = "brand_unavailable"
    PACK_SIZE_CHANGED = "pack_size_changed"
    BUDGET_DRIFT = "budget_drift"
    STALE_CART = "stale_cart"
    TRANSIENT_ERROR = "transient_error"
    PARTIAL_SUCCESS = "partial_success"
    PROVIDER_QUANTITY_LIMIT = "provider_quantity_limit"
    MIN_ORDER_FAILURE = "min_order_failure"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

class RecoveryAction(BaseModel):
    """Concrete cart instruction to repair intent drift."""
    model_config = ConfigDict(extra="ignore")

    action_type: Literal["add_item", "replace_item", "remove_item", "adjust_quantity", "refresh_cart", "retry"]
    spin_id: str = Field(..., description="Target SKU spin_id to add or adjust")
    sku_id: Optional[str] = Field(default=None, description="Provider SKU ID for a cart mutation")
    name: str = Field(..., description="Product or variant name")
    quantity: int = Field(default=1, ge=0)
    removes_spin_id: Optional[str] = Field(
        default=None,
        description="If replacing, the spin_id of the existing cart item to remove",
    )
    price: float = Field(default=0.0, ge=0.0)
    reason: str = Field(..., description="Explanation of why this action resolves the failure")


class RecoveryCandidate(BaseModel):
    """A scored alternative product variant considered during recovery."""
    model_config = ConfigDict(extra="ignore")

    spin_id: str
    sku_id: Optional[str] = None
    name: str
    pack_size: str
    price: float
    category: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class RecoveryOutcome(BaseModel):
    """Result of a recovery pass with explicit instructions or user choices (Spec Section 10.1)."""
    model_config = ConfigDict(extra="ignore")

    state: RecoveryState
    failure_class: FailureClass
    recovery_actions: list[RecoveryAction] = Field(default_factory=list)
    candidates_for_user: list[RecoveryCandidate] = Field(default_factory=list)
    message: str = Field(..., description="User-facing explanation of recovery status")
    attempt_number: int = Field(default=1, ge=1)
    can_auto_apply: bool = Field(
        default=False,
        description="True if actions are fully authorized by policy to auto-execute",
    )
    remaining_violations: list[ConstraintViolation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recovery Engine
# ---------------------------------------------------------------------------

class RecoveryEngine:
    """Deterministic recovery and candidate ranking engine (Spec Section 10)."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def recover(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        verification_result: VerificationResult,
        available_products: list[CommerceProductItem],
        *,
        attempt_number: int = 1,
        max_attempts: int = 3,
    ) -> RecoveryOutcome:
        """Execute the deterministic recovery loop.

        Args:
            contract: Active intent contract.
            cart: Current commerce cart state.
            verification_result: Output from IntentVerifier.
            available_products: Catalog items available at current dark store/address.
            attempt_number: Current cycle count (1-indexed).
            max_attempts: Maximum permitted recovery iterations.

        Returns:
            RecoveryOutcome with state, actions, or clarification candidates.
        """
        # 1. Check bounded limit
        if attempt_number > max_attempts:
            return RecoveryOutcome(
                state=RecoveryState.FAILED,
                failure_class=FailureClass.UNKNOWN,
                message=f"Recovery aborted: exceeded maximum attempts ({max_attempts})",
                attempt_number=attempt_number,
                can_auto_apply=False,
                remaining_violations=verification_result.violations,
            )

        # 2. If already valid, check if min_order_threshold is satisfied
        if verification_result.status == VerificationStatus.PASS:
            if cart and cart.items and cart.grand_total < cart.min_order_threshold:
                return self._handle_min_order_failure(contract, cart, available_products, attempt_number)
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=FailureClass.UNKNOWN,
                message="Cart already satisfies intent contract",
                attempt_number=attempt_number,
                can_auto_apply=True,
                remaining_violations=[],
            )

        # 3. Classify primary failure
        failure_class = self._classify(verification_result, cart)

        # 4. Dispatch to specialized class handler
        if failure_class == FailureClass.TRANSIENT_ERROR:
            return self._handle_transient_error(attempt_number, max_attempts)

        if failure_class == FailureClass.MIN_ORDER_FAILURE:
            return self._handle_min_order_failure(contract, cart, available_products, attempt_number)

        if failure_class == FailureClass.STALE_CART:
            return self._handle_stale_cart(cart, verification_result, attempt_number)

        if failure_class == FailureClass.BUDGET_DRIFT:
            return self._handle_budget_drift(
                contract, cart, verification_result, available_products, attempt_number
            )

        if failure_class in (
            FailureClass.ITEM_UNAVAILABLE,
            FailureClass.BRAND_UNAVAILABLE,
            FailureClass.PACK_SIZE_CHANGED,
            FailureClass.PARTIAL_SUCCESS,
            FailureClass.PROVIDER_QUANTITY_LIMIT,
        ):
            return self._handle_item_or_brand_unavailable(
                contract, cart, verification_result, available_products, failure_class, attempt_number
            )

        # Default fallback for unhandled or compound failures
        return RecoveryOutcome(
            state=RecoveryState.NEEDS_USER_DECISION,
            failure_class=failure_class,
            message="Intent drift detected requiring your decision",
            attempt_number=attempt_number,
            can_auto_apply=False,
            remaining_violations=verification_result.violations,
        )

    # -----------------------------------------------------------------------
    # Classification (Spec Section 10.1)
    # -----------------------------------------------------------------------

    def _classify(
        self, verification_result: VerificationResult, cart: Optional[CommerceCart] = None
    ) -> FailureClass:
        """Map VerificationResult violations and cart state to a FailureClass."""
        codes = verification_result.violation_codes

        if cart and (
            cart.reduced_quantity_items
            or any(
                item.max_quantity is not None and item.quantity >= item.max_quantity
                for item in cart.items
            )
        ):
            return FailureClass.PROVIDER_QUANTITY_LIMIT
        if cart and cart.cart_warning == "PARTIAL_SUCCESS":
            return FailureClass.PARTIAL_SUCCESS
        if ViolationCode.STALE_CART in codes:
            return FailureClass.STALE_CART
        if ViolationCode.BUDGET_EXCEEDED in codes:
            return FailureClass.BUDGET_DRIFT
        if ViolationCode.MISSING_ITEM in codes or ViolationCode.ITEM_UNAVAILABLE in codes:
            return FailureClass.ITEM_UNAVAILABLE
        if ViolationCode.WRONG_BRAND in codes:
            return FailureClass.BRAND_UNAVAILABLE
        if (
            ViolationCode.WRONG_PACK_SIZE in codes
            or ViolationCode.WRONG_QUANTITY in codes
        ):
            return FailureClass.PACK_SIZE_CHANGED
        if ViolationCode.DIETARY_VIOLATION in codes:
            return FailureClass.ITEM_UNAVAILABLE
        if cart and cart.items and cart.grand_total < cart.min_order_threshold:
            return FailureClass.MIN_ORDER_FAILURE

        return FailureClass.UNKNOWN

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------

    def _handle_transient_error(
        self, attempt_number: int, max_attempts: int
    ) -> RecoveryOutcome:
        """Handle safe provider retry after a transient error (Spec Section 10.2 item 6)."""
        return handle_transient_error(attempt_number, max_attempts)

    def _handle_min_order_failure(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        available_products: list[CommerceProductItem],
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Handle minimum-order basket failure by suggesting staple addition (Spec Section 10.2 item 8)."""
        return handle_min_order_failure(contract, cart, available_products, attempt_number)

    def _handle_stale_cart(
        self,
        cart: CommerceCart,
        verification_result: VerificationResult,
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Handle stale cart or serviceability changes. Always requires human attention."""
        return handle_stale_cart(cart, verification_result, attempt_number)

    def _handle_budget_drift(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        verification_result: VerificationResult,
        available_products: list[CommerceProductItem],
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Attempt to swap an item for a cheaper variant to bring cart under budget."""
        return handle_budget_drift(
            self.policy_engine, contract, cart, verification_result, available_products, attempt_number
        )

    def _handle_item_or_brand_unavailable(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        verification_result: VerificationResult,
        available_products: list[CommerceProductItem],
        failure_class: FailureClass,
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Generate, filter, rank candidates for missing/unavailable item."""
        return handle_item_or_brand_unavailable(
            self.policy_engine,
            contract,
            cart,
            verification_result,
            available_products,
            failure_class,
            attempt_number,
        )

    # -----------------------------------------------------------------------
    # Candidate Generation & Ranking (Spec Section 10.3)
    # -----------------------------------------------------------------------

    def _find_candidates(
        self,
        target_name: str,
        intent_item: Optional[IntentItem],
        available_products: list[CommerceProductItem],
    ) -> list[tuple[CommerceProductItem, ProductVariant]]:
        """Find in-stock product variants matching the target's category or name."""
        return find_candidates(target_name, intent_item, available_products)

    def _filter_by_hard_constraints(
        self,
        candidates: list[tuple[CommerceProductItem, ProductVariant]],
        target_name: str,
        contract: IntentContract,
        cart: CommerceCart,
        removes_spin_id: Optional[str] = None,
        intent_item: Optional[IntentItem] = None,
    ) -> list[tuple[CommerceProductItem, ProductVariant]]:
        """Filter candidate variants using PolicyEngine hard constraint checks."""
        return filter_by_hard_constraints(
            candidates,
            target_name,
            contract,
            cart,
            self.policy_engine,
            removes_spin_id,
            intent_item,
        )

    def _score_candidate(
        self,
        item_tuple: tuple[CommerceProductItem, ProductVariant],
        target_name: str,
        intent_item: Optional[IntentItem],
        contract: IntentContract,
    ) -> RecoveryCandidate:
        """Score candidate along 7 deterministic dimensions (Spec Section 10.3)."""
        prod, variant = item_tuple
        final_score, reasons = score_candidate(item_tuple, target_name, intent_item, contract)
        return RecoveryCandidate(
            spin_id=variant.spin_id,
            sku_id=variant.sku_id,
            name=variant.name,
            pack_size=variant.pack_size,
            price=variant.price,
            category=prod.category,
            score=final_score,
            reasons=reasons,
        )

    def _extract_brand(self, product_name: str) -> str:
        """Extract brand name heuristic (first token in Indian grocery catalog)."""
        return extract_brand(product_name)

    def _calculate_pack_multiple(self, intent_item: IntentItem, candidate_pack_size: str) -> int:
        """Return the exact quantity-preserving pack count, or zero if unsafe."""
        return calculate_pack_multiple(intent_item, candidate_pack_size)

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
        """Execute the complete closed recovery loop (Spec Section 10.1).

        Loop:
            Observe failure
            → Recover / compute candidate actions
            → If can_auto_apply: apply actions to CommercePort
            → Verify again
            → Return updated cart and verified outcome
        """
        cart = await commerce_port.get_cart(cart_id)
        outcome = self.recover(
            contract,
            cart,
            verification_result,
            available_products,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
        )

        if not outcome.can_auto_apply or not outcome.recovery_actions:
            return cart, verification_result, outcome

        # Apply actions to commerce cart
        mutation_actions = [
            a for a in outcome.recovery_actions
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

            updated_cart = await commerce_port.update_cart(
                items=updates, cart_id=cart_id, address_id=address_id
            )
        else:
            # Non-mutating recovery action (retry or refresh_cart): controlled live re-fetch
            updated_cart = await commerce_port.get_cart(cart_id)

        # Verify again!
        new_v_result = verifier.verify(contract, updated_cart)
        if new_v_result.status == VerificationStatus.PASS:
            outcome.state = RecoveryState.RECOVERED
            outcome.message = f"Successfully recovered intent: {outcome.message}"
        else:
            outcome.remaining_violations = new_v_result.violations

        return updated_cart, new_v_result, outcome


