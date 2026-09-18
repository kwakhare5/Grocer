"""Regression coverage for fail-closed hard dietary verification."""

from __future__ import annotations

import pytest

from backend.integrations.commerce.models import CartItem, CommerceCart
from backend.intent.models import DietaryConstraint, IntentContract
from backend.intent.verifier import IntentVerifier, VerificationStatus, ViolationCode


def _cart_with(item_name: str, *, category: str | None = None) -> CommerceCart:
    return CommerceCart(
        cart_id="dietary-cart",
        items=[
            CartItem(
                spin_id="spin-item",
                name=item_name,
                pack_size="1 pack",
                unit_price=50,
                quantity=1,
                total_price=50,
                category=category,
            )
        ],
        item_total=50,
        grand_total=50,
    )


@pytest.mark.parametrize(
    "tag",
    [
        "vegetarian",
        "veg",
        "vegan",
        "halal",
        "kosher",
        "Jain",
        "gluten-free",
        "gluten free",
        "dairy-free",
        "dairy free",
        "egg-free",
        "eggless",
        "sugar-free",
        "sugar free",
    ],
)
def test_hard_dietary_constraint_fails_when_compliance_is_unverifiable(tag: str) -> None:
    contract = IntentContract(
        session_id="dietary-verification",
        goal="buy compliant groceries",
        dietary_constraints=[DietaryConstraint(tag=tag, is_hard=True)],
    )

    result = IntentVerifier().verify(contract, _cart_with("Plain Rice"))

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.DIETARY_UNVERIFIABLE in result.violation_codes
    assert any(
        violation.target == "Plain Rice" and tag.casefold() in violation.detail.casefold()
        for violation in result.violations
        if violation.violation_code == ViolationCode.DIETARY_UNVERIFIABLE
    )


@pytest.mark.parametrize(
    ("tag", "item_name", "category"),
    [
        ("vegetarian", "Chicken Breast", "poultry"),
        ("vegan", "Fresh Milk", "dairy"),
    ],
)
def test_known_dietary_contradictions_keep_specific_violation(
    tag: str, item_name: str, category: str
) -> None:
    contract = IntentContract(
        session_id="dietary-contradiction",
        goal="buy compliant groceries",
        dietary_constraints=[DietaryConstraint(tag=tag, is_hard=True)],
    )

    result = IntentVerifier().verify(
        contract,
        _cart_with(item_name, category=category),
    )

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.DIETARY_VIOLATION in result.violation_codes
    assert ViolationCode.DIETARY_UNVERIFIABLE not in result.violation_codes


def test_soft_dietary_preference_does_not_create_a_hard_failure() -> None:
    contract = IntentContract(
        session_id="dietary-soft-preference",
        goal="buy groceries",
        dietary_constraints=[DietaryConstraint(tag="vegan", is_hard=False)],
    )

    result = IntentVerifier().verify(contract, _cart_with("Plain Rice"))

    assert result.status == VerificationStatus.PASS
    assert ViolationCode.DIETARY_UNVERIFIABLE not in result.violation_codes
