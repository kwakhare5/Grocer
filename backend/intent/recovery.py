"""Recovery Engine — deterministic intent drift repair and candidate ranking (Spec §10).

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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RecoveryState(str, Enum):
    """Terminal or intermediate state of a recovery attempt (Spec §10.4)."""
    RECOVERED = "recovered"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLOCKED = "blocked"
    FAILED = "failed"


class FailureClass(str, Enum):
    """Normalized taxonomy of commerce intent failures (Spec §10.2)."""
    ITEM_UNAVAILABLE = "item_unavailable"
    BRAND_UNAVAILABLE = "brand_unavailable"
    PACK_SIZE_CHANGED = "pack_size_changed"
    BUDGET_DRIFT = "budget_drift"
    STALE_CART = "stale_cart"
    TRANSIENT_ERROR = "transient_error"
    PARTIAL_SUCCESS = "partial_success"
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
    name: str
    pack_size: str
    price: float
    category: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class RecoveryOutcome(BaseModel):
    """Result of a recovery pass with explicit instructions or user choices (Spec §10.1)."""
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
    """Deterministic recovery and candidate ranking engine (Spec §10)."""

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

        if failure_class in (FailureClass.ITEM_UNAVAILABLE, FailureClass.BRAND_UNAVAILABLE, FailureClass.PACK_SIZE_CHANGED):
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
    # Classification (Spec §10.1)
    # -----------------------------------------------------------------------

    def _classify(
        self, verification_result: VerificationResult, cart: Optional[CommerceCart] = None
    ) -> FailureClass:
        """Map VerificationResult violations and cart state to a FailureClass."""
        codes = verification_result.violation_codes

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
        """Handle safe provider retry after a transient error (Spec §10.2 item 6)."""
        action = RecoveryAction(
            action_type="retry",
            spin_id="system-retry",
            name="upstream_provider",
            quantity=1,
            price=0.0,
            reason="Safe transient retry per provider contract",
        )
        return RecoveryOutcome(
            state=RecoveryState.RECOVERED,
            failure_class=FailureClass.TRANSIENT_ERROR,
            recovery_actions=[action],
            message="Transient provider error detected; safely retrying action.",
            attempt_number=attempt_number,
            can_auto_apply=True,
        )

    def _handle_min_order_failure(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        available_products: list[CommerceProductItem],
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Handle minimum-order basket failure by suggesting staple addition (Spec §10.2 item 8)."""
        shortfall = cart.min_order_threshold - cart.grand_total
        max_budget = contract.budget.max_budget if contract.budget else float("inf")

        candidates: list[tuple[RecoveryCandidate, int]] = []
        for prod in available_products:
            for variant in prod.variants:
                if variant.in_stock and variant.price > 0:
                    required_quantity = max(1, math.ceil(shortfall / variant.price))
                    added_total = variant.price * required_quantity
                    new_total = cart.grand_total + added_total
                    if new_total <= max_budget:
                        score = round(
                            max(0.1, 1.0 - abs(added_total - shortfall) / 100.0),
                            2,
                        )
                        candidates.append(
                            (
                                RecoveryCandidate(
                                spin_id=variant.spin_id,
                                name=variant.name,
                                pack_size=variant.pack_size,
                                price=variant.price,
                                category=prod.category,
                                score=score,
                                reasons=[
                                    f"Adds {required_quantity} × ₹{variant.price:.0f} "
                                    f"to satisfy the ₹{cart.min_order_threshold:.0f} minimum"
                                ],
                                ),
                                required_quantity,
                            )
                        )

        candidates.sort(key=lambda entry: entry[0].score, reverse=True)
        if candidates:
            top, top_quantity = candidates[0]
            action = RecoveryAction(
                action_type="add_item",
                spin_id=top.spin_id,
                name=top.name,
                quantity=top_quantity,
                price=top.price,
                reason=f"Add staple item to meet min order threshold (₹{cart.min_order_threshold:.0f})",
            )
            return RecoveryOutcome(
                state=RecoveryState.NEEDS_USER_DECISION,
                failure_class=FailureClass.MIN_ORDER_FAILURE,
                recovery_actions=[action],
                candidates_for_user=[candidate for candidate, _ in candidates[:3]],
                message=(
                    f"Cart total (₹{cart.grand_total:.0f}) is below the "
                    f"₹{cart.min_order_threshold:.0f} minimum order threshold. "
                    f"Add {top_quantity} × {top.name} "
                    f"(₹{top.price * top_quantity:.0f}) to meet the threshold?"
                ),
                attempt_number=attempt_number,
                can_auto_apply=False,
            )

        return RecoveryOutcome(
            state=RecoveryState.BLOCKED,
            failure_class=FailureClass.MIN_ORDER_FAILURE,
            message=f"Cart total (₹{cart.grand_total:.0f}) is below minimum order threshold (₹{cart.min_order_threshold:.0f}) and no compliant items found within budget.",
            attempt_number=attempt_number,
            can_auto_apply=False,
        )

    def _handle_stale_cart(
        self,
        cart: CommerceCart,
        verification_result: VerificationResult,
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Handle stale cart or serviceability changes. Always requires human attention."""
        return RecoveryOutcome(
            state=RecoveryState.NEEDS_USER_DECISION,
            failure_class=FailureClass.STALE_CART,
            message="Cart is stale or store is not serviceable. Please refresh or update address.",
            attempt_number=attempt_number,
            can_auto_apply=False,
            remaining_violations=verification_result.violations,
        )

    def _handle_budget_drift(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        verification_result: VerificationResult,
        available_products: list[CommerceProductItem],
        attempt_number: int,
    ) -> RecoveryOutcome:
        """Attempt to swap an item for a cheaper variant to bring cart under budget."""
        max_budget = contract.budget.max_budget if contract.budget else float("inf")
        overrun = cart.grand_total - max_budget

        # Search for possible cheaper replacements among cart items
        best_swap: Optional[tuple[CartItem, ProductVariant, float]] = None

        for cart_item in cart.items:
            # Find candidate products matching this cart item
            query = cart_item.name.lower()
            matching_products = [
                p for p in available_products
                if any(word in p.name.lower() for word in query.split()[:2])
            ]
            for prod in matching_products:
                for variant in prod.variants:
                    if not variant.in_stock:
                        continue
                    if variant.spin_id == cart_item.spin_id:
                        continue
                    savings = (cart_item.unit_price - variant.price) * cart_item.quantity
                    if savings >= overrun:
                        if best_swap is None or savings < best_swap[2]:  # minimal required swap
                            best_swap = (cart_item, variant, savings)

        if best_swap:
            old_item, new_variant, savings = best_swap
            proposal = ActionProposal(
                action_type="substitute",
                target=old_item.name,
                details={
                    "item_name": new_variant.name,
                    "replacement": new_variant.name,
                    "price_delta": -savings,
                    "new_brand": new_variant.name.split()[0],
                },
                reason=f"Downsize/swap to bring total within ₹{max_budget:.0f} budget",
            )
            decision = self.policy_engine.evaluate(proposal, contract)
            action = RecoveryAction(
                action_type="replace_item",
                spin_id=new_variant.spin_id,
                name=new_variant.name,
                quantity=old_item.quantity,
                removes_spin_id=old_item.spin_id,
                price=new_variant.price,
                reason=proposal.reason,
            )
            if decision.autonomy_level == AutonomyLevel.AUTO_EXECUTE:
                return RecoveryOutcome(
                    state=RecoveryState.RECOVERED,
                    failure_class=FailureClass.BUDGET_DRIFT,
                    recovery_actions=[action],
                    message=f"Adjusted {old_item.name} to {new_variant.name} to stay within ₹{max_budget:.0f} budget.",
                    attempt_number=attempt_number,
                    can_auto_apply=True,
                )
            else:
                return RecoveryOutcome(
                    state=RecoveryState.NEEDS_USER_DECISION,
                    failure_class=FailureClass.BUDGET_DRIFT,
                    candidates_for_user=[
                        RecoveryCandidate(
                            spin_id=new_variant.spin_id,
                            name=new_variant.name,
                            pack_size=new_variant.pack_size,
                            price=new_variant.price,
                            category="budget_saver",
                            score=0.9,
                            reasons=[f"Saves ₹{savings:.0f} to meet budget"],
                        )
                    ],
                    message=f"Cart exceeds budget by ₹{overrun:.0f}. Would you like to swap {old_item.name} with {new_variant.name}?",
                    attempt_number=attempt_number,
                    can_auto_apply=False,
                )

        return RecoveryOutcome(
            state=RecoveryState.NEEDS_USER_DECISION,
            failure_class=FailureClass.BUDGET_DRIFT,
            message=f"Basket is ₹{overrun:.0f} over budget. Please adjust your items or budget limit.",
            attempt_number=attempt_number,
            can_auto_apply=False,
            remaining_violations=verification_result.violations,
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
        target_name = ""
        removes_spin_id: Optional[str] = None
        quantity = 1

        # Identify target item
        for v in verification_result.violations:
            if v.violation_code in (
                ViolationCode.ITEM_UNAVAILABLE,
                ViolationCode.MISSING_ITEM,
                ViolationCode.WRONG_BRAND,
                ViolationCode.WRONG_PACK_SIZE,
                ViolationCode.WRONG_QUANTITY,
                ViolationCode.DIETARY_VIOLATION,
            ):
                target_name = v.target
                break

        if not target_name and verification_result.unresolved_items:
            target_name = verification_result.unresolved_items[0]

        # Find matching intent item if exists
        intent_item = next(
            (item for item in contract.items if item.name.lower() in target_name.lower() or target_name.lower() in item.name.lower()),
            None,
        )
        if intent_item:
            quantity = int(intent_item.quantity)

        # Check if replacing an existing cart item
        matched_cart_item = next(
            (ci for ci in cart.items if ci.name.lower() == target_name.lower() or target_name.lower() in ci.name.lower()),
            None,
        )
        if matched_cart_item:
            removes_spin_id = matched_cart_item.spin_id
            quantity = matched_cart_item.quantity

        # 1. Generate candidate alternatives
        raw_candidates = self._find_candidates(target_name, intent_item, available_products)

        # 2. Filter by hard constraints & policy
        filtered_candidates = self._filter_by_hard_constraints(
            raw_candidates, target_name, contract, cart, removes_spin_id
        )

        if intent_item:
            requested_quantity = normalize_requested_quantity(
                intent_item.quantity,
                intent_item.unit,
                intent_item.name,
                quantity_is_explicit=intent_item.quantity_is_explicit,
                pack_size_preference=intent_item.pack_size_preference,
            )
            filtered_candidates = [
                (product, variant)
                for product, variant in filtered_candidates
                if requested_quantity is not None
                and required_pack_count(
                    requested_quantity,
                    normalize_pack_quantity(variant.pack_size),
                )
                is not None
                and (
                    not intent_item.brand_preference
                    or brand_identity_matches(
                        intent_item.brand_preference,
                        product.brand,
                        product.name,
                        variant.name,
                    )
                )
            ]

        if not filtered_candidates:
            return RecoveryOutcome(
                state=RecoveryState.BLOCKED,
                failure_class=failure_class,
                message=f"No compliant replacement found for '{target_name}' that satisfies all hard constraints",
                attempt_number=attempt_number,
                can_auto_apply=False,
                remaining_violations=verification_result.violations,
            )

        # 3. Score and rank candidates
        scored = [
            self._score_candidate(c, target_name, intent_item, contract)
            for c in filtered_candidates
        ]
        scored.sort(key=lambda c: c.score, reverse=True)

        top_candidate = scored[0]

        # 4. Check policy on top candidate
        old_pack = (
            matched_cart_item.pack_size
            if matched_cart_item and matched_cart_item.pack_size
            else (intent_item.pack_size_preference if intent_item and intent_item.pack_size_preference else "")
        )
        new_pack = top_candidate.pack_size or ""
        proposal = ActionProposal(
            action_type="substitute" if removes_spin_id else "add_item",
            target=target_name,
            details={
                "item_name": top_candidate.name,
                "replacement": top_candidate.name,
                "category": top_candidate.category,
                "price_delta": top_candidate.price - (matched_cart_item.unit_price if matched_cart_item else 0.0),
                "new_brand": self._extract_brand(top_candidate.name),
                "old_pack_size": old_pack,
                "new_pack_size": new_pack,
            },
            reason=f"Substitute for unavailable '{target_name}'",
        )
        policy_decision = self.policy_engine.evaluate(proposal, contract)

        # Check if top candidate is distinct from runner up or if ambiguity warrants user choice
        is_ambiguous = False
        target_lower = (intent_item.name if intent_item else target_name).lower()
        bp = contract.get_brand_preference(target_lower)
        if len(scored) > 1:
            score_diff = scored[0].score - scored[1].score
            top_brand = self._extract_brand(scored[0].name).lower()
            runner_brand = self._extract_brand(scored[1].name).lower()

            has_exact_match = (
                bp is not None and bp.preferred_brand.lower() in scored[0].name.lower()
                and intent_item is not None and intent_item.pack_size_preference is not None
                and intent_item.pack_size_preference.lower() in scored[0].pack_size.lower()
            )
            if not has_exact_match:
                if score_diff < 0.08:
                    is_ambiguous = True

        # Resolve pack count using the same physical semantics as selection and
        # verification. Invalid underfill/overfill candidates were filtered out.
        multiple = 1
        if intent_item:
            multiple = self._calculate_pack_multiple(intent_item, top_candidate.pack_size)
            if multiple < 1:
                return RecoveryOutcome(
                    state=RecoveryState.BLOCKED,
                    failure_class=failure_class,
                    message=f"No exact quantity-preserving replacement found for '{target_name}'",
                    attempt_number=attempt_number,
                    can_auto_apply=False,
                    remaining_violations=verification_result.violations,
                )
            quantity = multiple

        action_reason = (
            f"Supplied {multiple}x {top_candidate.pack_size} packs to fulfill requested {intent_item.name}"
            if multiple > 1 and intent_item
            else f"Replaced unavailable '{target_name}' with {top_candidate.name}"
        )

        action = RecoveryAction(
            action_type="replace_item" if removes_spin_id else "add_item",
            spin_id=top_candidate.spin_id,
            name=top_candidate.name,
            quantity=quantity,
            removes_spin_id=removes_spin_id,
            price=top_candidate.price,
            reason=action_reason,
        )

        if policy_decision.autonomy_level == AutonomyLevel.AUTO_EXECUTE and not is_ambiguous:
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=failure_class,
                recovery_actions=[action],
                message=f"Automatically replaced '{target_name}' with '{top_candidate.name}'.",
                attempt_number=attempt_number,
                can_auto_apply=True,
            )

        # Ambiguous or requires approval
        clarification_msg = (
            policy_decision.clarification_needed
            or f"'{target_name}' is unavailable. I found multiple options: {', '.join(c.name for c in scored[:2])}. Which should I choose?"
        )
        return RecoveryOutcome(
            state=RecoveryState.NEEDS_USER_DECISION,
            failure_class=failure_class,
            candidates_for_user=scored[:3],
            recovery_actions=[action],  # Recommended top action
            message=clarification_msg,
            attempt_number=attempt_number,
            can_auto_apply=False,
        )

    # -----------------------------------------------------------------------
    # Candidate Generation & Ranking (Spec §10.3)
    # -----------------------------------------------------------------------

    def _find_candidates(
        self,
        target_name: str,
        intent_item: Optional[IntentItem],
        available_products: list[CommerceProductItem],
    ) -> list[tuple[CommerceProductItem, ProductVariant]]:
        """Find in-stock product variants matching the target's category or name."""
        candidates: list[tuple[CommerceProductItem, ProductVariant]] = []
        requested_name = intent_item.name if intent_item else target_name
        requested_category = intent_item.category if intent_item else None

        for prod in available_products:
            if product_identity_matches(
                requested_name,
                prod.name,
                requested_category,
                prod.category,
            ):
                for variant in prod.variants:
                    if variant.in_stock and product_identity_matches(
                        requested_name,
                        variant.name,
                        requested_category,
                        prod.category,
                    ):
                        candidates.append((prod, variant))

        return candidates

    def _filter_by_hard_constraints(
        self,
        candidates: list[tuple[CommerceProductItem, ProductVariant]],
        target_name: str,
        contract: IntentContract,
        cart: CommerceCart,
        removes_spin_id: Optional[str] = None,
    ) -> list[tuple[CommerceProductItem, ProductVariant]]:
        """Filter candidate variants using PolicyEngine hard constraint checks."""
        valid: list[tuple[CommerceProductItem, ProductVariant]] = []

        old_price = 0.0
        if removes_spin_id:
            for item in cart.items:
                if item.spin_id == removes_spin_id:
                    old_price = item.total_price
                    break

        for prod, variant in candidates:
            price_delta = variant.price - old_price
            proposal = ActionProposal(
                action_type="substitute" if removes_spin_id else "add_item",
                target=target_name,
                details={
                    "item_name": variant.name,
                    "category": prod.category,
                    "new_brand": self._extract_brand(variant.name),
                    "price_delta": price_delta,
                    "current_total": cart.grand_total,
                },
                reason="Candidate viability check",
            )
            violations = self.policy_engine._check_hard_constraints(proposal, contract)
            if not violations:
                valid.append((prod, variant))

        return valid

    def _score_candidate(
        self,
        item_tuple: tuple[CommerceProductItem, ProductVariant],
        target_name: str,
        intent_item: Optional[IntentItem],
        contract: IntentContract,
    ) -> RecoveryCandidate:
        """Score candidate along 7 deterministic dimensions (Spec §10.3)."""
        prod, variant = item_tuple
        score = 0.4  # Base score for category/keyword relevance
        reasons: list[str] = ["Category/keyword match"]

        target_lower = (intent_item.name if intent_item else target_name).lower()
        bp = contract.get_brand_preference(target_lower)
        var_name_lower = variant.name.lower()

        # 1. Brand affinity scoring
        if bp:
            if bp.preferred_brand.lower() in var_name_lower:
                score += 0.45
                reasons.append(f"Preferred brand ({bp.preferred_brand}) match")
            else:
                alt_matched = False
                for idx, alt in enumerate(bp.alternative_brands):
                    if alt.lower() in var_name_lower:
                        bonus = max(0.15, 0.30 - (idx * 0.10))
                        score += bonus
                        reasons.append(f"Approved alternative brand ({alt}) match (priority #{idx+1})")
                        alt_matched = True
                        break
                if not alt_matched and contract.substitution_policy.brand_tolerance == BrandTolerance.USUAL_BRANDS:
                    score += 0.05
        else:
            # Check intent item brand_preference
            if intent_item and intent_item.brand_preference:
                if intent_item.brand_preference.lower() in var_name_lower:
                    score += 0.45
                    reasons.append(f"Specified brand ({intent_item.brand_preference}) match")

        # 2. Pack size similarity
        preferred_pack = intent_item.pack_size_preference if intent_item else None
        if preferred_pack:
            if preferred_pack.lower() in variant.pack_size.lower():
                score += 0.20
                reasons.append(f"Pack size ({preferred_pack}) exact match")
            elif contract.pack_size_rules.tolerance == SubstitutionTolerance.REASONABLE:
                score += 0.05
                reasons.append("Pack size within reasonable tolerance")

        # 3. Price impact
        if intent_item and intent_item.max_price and variant.price <= intent_item.max_price:
            score += 0.10
            reasons.append(f"Price ₹{variant.price:.0f} within item limit ₹{intent_item.max_price:.0f}")

        # Clamp between 0.0 and 1.0
        final_score = min(1.0, round(score, 2))

        return RecoveryCandidate(
            spin_id=variant.spin_id,
            name=variant.name,
            pack_size=variant.pack_size,
            price=variant.price,
            category=prod.category,
            score=final_score,
            reasons=reasons,
        )

    def _extract_brand(self, product_name: str) -> str:
        """Extract brand name heuristic (first token in Indian grocery catalog)."""
        tokens = product_name.strip().split()
        return tokens[0] if tokens else ""

    def _calculate_pack_multiple(self, intent_item: IntentItem, candidate_pack_size: str) -> int:
        """Return the exact quantity-preserving pack count, or zero if unsafe."""

        requested = normalize_requested_quantity(
            intent_item.quantity,
            intent_item.unit,
            intent_item.name,
            quantity_is_explicit=intent_item.quantity_is_explicit,
            pack_size_preference=intent_item.pack_size_preference,
        )
        if requested is None:
            return 0
        count = required_pack_count(
            requested,
            normalize_pack_quantity(candidate_pack_size),
        )
        return count or 0

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
        """Execute the complete closed recovery loop (Spec §10.1).

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


