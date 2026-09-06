"""Intent Verifier — deterministic commerce-state-vs-intent comparison (Spec §9).

Answers the question: "Does the live cart still represent what the user intended?"

Architecture:
    IntentVerifier.verify(contract, cart)                → VerificationResult
    IntentVerifier.verify_checkout(contract, cart, ...)  → VerificationResult

Rules:
    - Zero LLM dependency; every check is deterministic.
    - Hard constraint violations always produce VerificationStatus.FAIL.
    - Soft preference deviations are recorded but may still produce PASS.
    - verify_checkout always fails without explicit_confirmation=True (Spec §8.3, §17.1).
    - Re-usable: called after cart mutations, after recovery, and before checkout.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.models import CommerceCart
from backend.intent.enums import ConstraintType, PreferenceType
from backend.intent.models import IntentContract


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    """Top-level result of a verification pass."""
    PASS = "pass"
    FAIL = "fail"


class ViolationCode(str, Enum):
    """Machine-readable codes for hard-constraint violations (Spec §9.2)."""
    BUDGET_EXCEEDED = "budget_exceeded"
    DIETARY_VIOLATION = "dietary_violation"
    MISSING_ITEM = "missing_item"
    WRONG_BRAND = "wrong_brand"
    WRONG_QUANTITY = "wrong_quantity"
    WRONG_PACK_SIZE = "wrong_pack_size"
    ITEM_UNAVAILABLE = "item_unavailable"
    STALE_CART = "stale_cart"
    UNAUTHORIZED_CHECKOUT = "unauthorized_checkout"


# ---------------------------------------------------------------------------
# Output models (Spec §9.2)
# ---------------------------------------------------------------------------

class ConstraintViolation(BaseModel):
    """A hard-constraint violation detected during verification."""
    model_config = ConfigDict(extra="ignore")

    violation_code: ViolationCode
    target: str = Field(..., description="Item or constraint that was violated")
    detail: str = Field(..., description="Human-readable explanation")
    is_hard: bool = Field(default=True)


class PreferenceDeviation(BaseModel):
    """A soft-preference deviation — recorded but does not force FAIL alone."""
    model_config = ConfigDict(extra="ignore")

    preference_type: PreferenceType
    target: str = Field(..., description="Item or attribute that deviated")
    expected: str = Field(..., description="What the user preferred")
    actual: str = Field(..., description="What was found in the cart")


class VerificationResult(BaseModel):
    """Full output of a verification pass (Spec §9.2)."""
    model_config = ConfigDict(extra="ignore")

    status: VerificationStatus
    violations: list[ConstraintViolation] = Field(default_factory=list)
    deviations: list[PreferenceDeviation] = Field(default_factory=list)
    unresolved_items: list[str] = Field(
        default_factory=list,
        description="Intent item names that could not be matched to any cart item",
    )
    budget_delta: float = Field(
        default=0.0,
        description="grand_total - max_budget; negative means under budget",
    )
    is_stale: bool = Field(default=False)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    recovery_hints: list[str] = Field(
        default_factory=list,
        description="Suggested recovery action descriptions for the Recovery Engine",
    )

    @property
    def has_hard_violations(self) -> bool:
        return any(v.is_hard for v in self.violations)

    @property
    def violation_codes(self) -> list[ViolationCode]:
        return [v.violation_code for v in self.violations]


# ---------------------------------------------------------------------------
# Keyword sets for dietary checking
# ---------------------------------------------------------------------------

_NON_VEG_KEYWORDS: frozenset[str] = frozenset({
    "chicken", "mutton", "lamb", "goat", "pork", "beef", "veal",
    "fish", "tuna", "salmon", "prawn", "shrimp", "crab", "lobster",
    "squid", "clam", "oyster", "seafood", "meat", "poultry",
    "egg", "eggs",
})

_NON_VEG_CATEGORIES: frozenset[str] = frozenset({
    "poultry", "meat", "seafood", "fish", "non-veg",
})

_VEGAN_EXCLUDED_KEYWORDS: frozenset[str] = frozenset({
    "milk", "butter", "ghee", "paneer", "curd", "yogurt", "cream",
    "cheese", "honey", "whey",
})


# ---------------------------------------------------------------------------
# IntentVerifier
# ---------------------------------------------------------------------------

class IntentVerifier:
    """Deterministic engine that compares live commerce state to IntentContract.

    All checks are deterministic — no LLM calls, no probabilistic logic.
    Hard violations always produce FAIL. Soft deviations are accumulated
    and reported, but only produce FAIL if they are also hard.
    """

    def verify(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        *,
        stale: bool = False,
    ) -> VerificationResult:
        """Compare cart state to intent contract.

        Args:
            contract: The active IntentContract governing this session.
            cart:     The current CommerceCart from the commerce provider.
            stale:    Caller-supplied flag indicating the cart is known stale.

        Returns:
            VerificationResult with PASS or FAIL status and full violation detail.
        """
        violations: list[ConstraintViolation] = []
        deviations: list[PreferenceDeviation] = []
        unresolved: list[str] = []
        recovery_hints: list[str] = []

        # 1. Stale cart check
        stale_violations = self._check_stale(cart, stale)
        violations.extend(stale_violations)
        if stale_violations:
            recovery_hints.append("Refresh cart state before proceeding")

        # 1b. Item availability check (in-cart OOS items)
        availability_violations = self._check_item_availability(cart)
        violations.extend(availability_violations)
        if availability_violations:
            recovery_hints.append("Replace or remove out-of-stock items from the basket")

        # 2. Budget check

        budget_delta, budget_violations = self._check_budget(contract, cart)
        violations.extend(budget_violations)
        if budget_violations:
            recovery_hints.append(
                f"Basket exceeds budget by ₹{budget_delta:.0f}; remove or substitute items"
            )

        # 3. Dietary constraints
        diet_violations = self._check_dietary(contract, cart)
        violations.extend(diet_violations)
        if diet_violations:
            targets = ", ".join(v.target for v in diet_violations)
            recovery_hints.append(f"Remove items violating dietary constraints: {targets}")

        # 4. Missing essential items
        missing, item_deviations = self._check_missing_items(contract, cart)
        unresolved.extend(missing)
        deviations.extend(item_deviations)
        if missing:
            for item_name in missing:
                violations.append(ConstraintViolation(
                    violation_code=ViolationCode.MISSING_ITEM,
                    target=item_name,
                    detail=f"Essential item '{item_name}' is not present in the cart",
                    is_hard=True,
                ))
                recovery_hints.append(f"Search for and add '{item_name}' to the cart")

        # 5. Quantity checks
        qty_violations = self._check_quantities(contract, cart)
        violations.extend(qty_violations)

        # 6. Brand checks
        brand_violations, brand_deviations = self._check_brand(contract, cart)
        violations.extend(brand_violations)
        deviations.extend(brand_deviations)
        if brand_violations:
            for v in brand_violations:
                recovery_hints.append(
                    f"Replace '{v.target}' with the required brand"
                )

        # 7. Pack size checks
        pack_violations, pack_deviations = self._check_pack_size(contract, cart)
        violations.extend(pack_violations)
        deviations.extend(pack_deviations)

        # Determine final status
        has_hard_fail = any(v.is_hard for v in violations)
        status = VerificationStatus.FAIL if has_hard_fail else VerificationStatus.PASS

        # Confidence drops with each unresolved item
        confidence = max(0.0, 1.0 - 0.1 * len(unresolved) - 0.05 * len(deviations))

        return VerificationResult(
            status=status,
            violations=violations,
            deviations=deviations,
            unresolved_items=unresolved,
            budget_delta=budget_delta,
            is_stale=stale or bool(stale_violations),
            confidence=round(confidence, 2),
            recovery_hints=recovery_hints,
        )

    def verify_checkout(
        self,
        contract: IntentContract,
        cart: CommerceCart,
        explicit_confirmation: bool = False,
    ) -> VerificationResult:
        """Full verification pass with checkout authorization gate (Spec §8.3, §17.1).

        Always fails without explicit_confirmation=True regardless of cart state.
        Runs the full verify() pass and then applies the authorization check.
        """
        result = self.verify(contract, cart)

        if not explicit_confirmation:
            auth_violation = ConstraintViolation(
                violation_code=ViolationCode.UNAUTHORIZED_CHECKOUT,
                target="checkout",
                detail="Checkout requires explicit user confirmation (Spec §8.3)",
                is_hard=True,
            )
            result.violations.append(auth_violation)
            result.status = VerificationStatus.FAIL
            result.recovery_hints.append("Request explicit checkout confirmation from the user")

        return result

    # -----------------------------------------------------------------------
    # Private deterministic check methods
    # -----------------------------------------------------------------------

    def _check_stale(
        self, cart: CommerceCart, stale_flag: bool
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        if stale_flag or not cart.is_serviceable:
            violations.append(ConstraintViolation(
                violation_code=ViolationCode.STALE_CART,
                target="cart",
                detail="Cart is stale or no longer serviceable; state must be refreshed",
                is_hard=True,
            ))
        return violations

    def _check_item_availability(
        self, cart: CommerceCart
    ) -> list[ConstraintViolation]:
        """Check for items in active cart that have become out-of-stock or unserviceable."""
        violations: list[ConstraintViolation] = []
        for item in cart.items:
            if getattr(item, "is_available", True) is False:
                violations.append(
                    ConstraintViolation(
                        violation_code=ViolationCode.ITEM_UNAVAILABLE,
                        target=item.name,
                        detail=f"Item '{item.name}' in cart is out of stock or unavailable",
                        is_hard=True,
                    )
                )
        return violations

    def _check_budget(
        self, contract: IntentContract, cart: CommerceCart
    ) -> tuple[float, list[ConstraintViolation]]:
        """Return (budget_delta, violations).

        budget_delta = grand_total - max_budget (negative = under budget).
        """
        if not contract.budget or contract.budget.max_budget is None:
            return 0.0, []

        max_budget = contract.budget.max_budget
        delta = round(cart.grand_total - max_budget, 2)

        if delta <= 0:
            return delta, []

        # Over budget — check deviation tolerance
        if not contract.budget.is_hard:
            # Soft budget — record as deviation, not hard violation
            return delta, []

        # Hard budget
        max_dev = contract.budget.max_deviation
        if delta > max_dev:
            return delta, [ConstraintViolation(
                violation_code=ViolationCode.BUDGET_EXCEEDED,
                target="total_budget",
                detail=(
                    f"Cart total ₹{cart.grand_total:.0f} exceeds hard budget "
                    f"₹{max_budget:.0f} by ₹{delta:.0f} "
                    f"(allowed deviation: ₹{max_dev:.0f})"
                ),
                is_hard=True,
            )]

        # Within deviation — soft overage
        return delta, []

    def _check_dietary(
        self, contract: IntentContract, cart: CommerceCart
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        if not contract.dietary_constraints:
            return violations

        hard_tags = {d.tag.lower() for d in contract.dietary_constraints if d.is_hard}

        for item in cart.items:
            item_name_lower = item.name.lower()
            tokens = set(re.findall(r"[a-z]+", item_name_lower))

            if "vegetarian" in hard_tags or "veg" in hard_tags:
                if tokens & _NON_VEG_KEYWORDS:
                    violations.append(ConstraintViolation(
                        violation_code=ViolationCode.DIETARY_VIOLATION,
                        target=item.name,
                        detail=(
                            f"'{item.name}' appears to violate vegetarian dietary constraint"
                        ),
                        is_hard=True,
                    ))

            if "vegan" in hard_tags:
                if (tokens & _NON_VEG_KEYWORDS) or (tokens & _VEGAN_EXCLUDED_KEYWORDS):
                    violations.append(ConstraintViolation(
                        violation_code=ViolationCode.DIETARY_VIOLATION,
                        target=item.name,
                        detail=(
                            f"'{item.name}' appears to violate vegan dietary constraint"
                        ),
                        is_hard=True,
                    ))

        return violations

    def _check_missing_items(
        self, contract: IntentContract, cart: CommerceCart
    ) -> tuple[list[str], list[PreferenceDeviation]]:
        """Return (missing_item_names, deviations_for_non_essential_missing)."""
        missing: list[str] = []
        deviations: list[PreferenceDeviation] = []
        cart_names_lower = [
            ci.name.lower()
            for ci in cart.items
            if getattr(ci, "is_available", True) is not False
        ]

        for intent_item in contract.items:
            query = intent_item.name.lower()
            matched = any(query in cname or cname.startswith(query[:4]) for cname in cart_names_lower)
            if not matched:
                if intent_item.is_essential:
                    missing.append(intent_item.name)

                else:
                    deviations.append(PreferenceDeviation(
                        preference_type=PreferenceType.PRODUCT_VARIANT,
                        target=intent_item.name,
                        expected="present in cart",
                        actual="not found",
                    ))

        return missing, deviations

    def _check_quantities(
        self, contract: IntentContract, cart: CommerceCart
    ) -> list[ConstraintViolation]:
        """Check that cart quantities satisfy intent quantity rules."""
        violations: list[ConstraintViolation] = []

        for intent_item in contract.items:
            query = intent_item.name.lower()
            matched_cart_items = [
                ci for ci in cart.items
                if query in ci.name.lower() or ci.name.lower().startswith(query[:4])
            ]
            if not matched_cart_items:
                continue  # Already handled by _check_missing_items

            # Sum quantities across matched variants
            total_quantity = sum(ci.quantity for ci in matched_cart_items)
            required = intent_item.quantity

            # Only flag as violation if contract has EXACT_QUANTITY constraint for this item
            has_exact_constraint = any(
                hc.constraint_type == ConstraintType.EXACT_QUANTITY
                and intent_item.name.lower() in hc.target.lower()
                for hc in contract.hard_constraints
            )

            if has_exact_constraint and total_quantity != required:
                violations.append(ConstraintViolation(
                    violation_code=ViolationCode.WRONG_QUANTITY,
                    target=intent_item.name,
                    detail=(
                        f"'{intent_item.name}' requires exactly {required:.0f} "
                        f"{intent_item.unit} but cart has {total_quantity}"
                    ),
                    is_hard=True,
                ))

        return violations

    def _check_brand(
        self, contract: IntentContract, cart: CommerceCart
    ) -> tuple[list[ConstraintViolation], list[PreferenceDeviation]]:
        """Check hard brand locks and soft brand preferences."""
        violations: list[ConstraintViolation] = []
        deviations: list[PreferenceDeviation] = []

        for bp in contract.brand_preferences:
            product_lower = bp.product_or_category.lower()
            matched_items = [
                ci for ci in cart.items
                if product_lower in ci.name.lower()
            ]
            if not matched_items:
                continue

            preferred = bp.preferred_brand.lower()
            alternatives = [b.lower() for b in bp.alternative_brands]

            for cart_item in matched_items:
                item_name_lower = cart_item.name.lower()
                brand_matched = preferred in item_name_lower or any(
                    alt in item_name_lower for alt in alternatives
                )

                if not brand_matched:
                    if bp.is_hard:
                        violations.append(ConstraintViolation(
                            violation_code=ViolationCode.WRONG_BRAND,
                            target=cart_item.name,
                            detail=(
                                f"'{cart_item.name}' does not match hard brand lock "
                                f"'{bp.preferred_brand}' for '{bp.product_or_category}'"
                            ),
                            is_hard=True,
                        ))
                    else:
                        deviations.append(PreferenceDeviation(
                            preference_type=PreferenceType.BRAND,
                            target=cart_item.name,
                            expected=bp.preferred_brand,
                            actual=cart_item.name,
                        ))

        return violations, deviations

    def _check_pack_size(
        self, contract: IntentContract, cart: CommerceCart
    ) -> tuple[list[ConstraintViolation], list[PreferenceDeviation]]:
        """Check pack size preference against cart items."""
        violations: list[ConstraintViolation] = []
        deviations: list[PreferenceDeviation] = []

        for intent_item in contract.items:
            if not intent_item.pack_size_preference:
                continue

            query = intent_item.name.lower()
            preferred_size = intent_item.pack_size_preference.lower()
            matched_items = [
                ci for ci in cart.items
                if query in ci.name.lower() or ci.name.lower().startswith(query[:4])
            ]
            if not matched_items:
                continue

            pack_size_rule = contract.pack_size_rules
            from backend.intent.enums import SubstitutionTolerance

            for cart_item in matched_items:
                actual_size = cart_item.pack_size.lower()
                if preferred_size not in actual_size and actual_size not in preferred_size:
                    if pack_size_rule.tolerance == SubstitutionTolerance.STRICT:
                        violations.append(ConstraintViolation(
                            violation_code=ViolationCode.WRONG_PACK_SIZE,
                            target=cart_item.name,
                            detail=(
                                f"'{cart_item.name}' pack size '{cart_item.pack_size}' "
                                f"does not match required '{intent_item.pack_size_preference}' "
                                f"(strict tolerance)"
                            ),
                            is_hard=True,
                        ))
                    else:
                        deviations.append(PreferenceDeviation(
                            preference_type=PreferenceType.PACK_SIZE,
                            target=cart_item.name,
                            expected=intent_item.pack_size_preference,
                            actual=cart_item.pack_size,
                        ))

        return violations, deviations
