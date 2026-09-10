"""Unit tests for GROCER Phase 4 Intent Verifier (Spec Section 9, Section 16.2, Section 17).

Covers 12 test scenarios:
 1.  Exact cart pass — PASS, zero violations
 2.  Budget exceeded — FAIL, BUDGET_EXCEEDED
 3.  Budget within soft deviation — PASS (no hard violation)
 4.  Missing essential item — FAIL, MISSING_ITEM
 5.  Wrong quantity with EXACT_QUANTITY constraint — FAIL, WRONG_QUANTITY
 6.  Hard brand lock violated — FAIL, WRONG_BRAND
 7.  Soft brand preference deviated — PASS with deviation recorded
 8.  Wrong pack size (strict tolerance) — FAIL, WRONG_PACK_SIZE
 9.  Stale cart flag — FAIL, STALE_CART
10.  Dietary constraint violated by cart item — FAIL, DIETARY_VIOLATION
11.  Checkout without explicit confirmation — FAIL, UNAUTHORIZED_CHECKOUT
12.  All clean after simulated recovery — PASS with no violations
"""
from __future__ import annotations

import pytest

from backend.integrations.commerce.models import CartItem, CommerceCart
from backend.intent.enums import (
    ConstraintType,
    SubstitutionTolerance,
)
from backend.intent.models import (
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    HardConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SubstitutionPolicy,
)
from backend.intent.verifier import (
    IntentVerifier,
    VerificationStatus,
    ViolationCode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_contract(**overrides) -> IntentContract:
    """Build a minimal IntentContract with optional overrides."""
    defaults: dict = dict(
        session_id="test-session-p4",
        goal="weekly grocery restock",
        items=[
            IntentItem(name="milk", quantity=1, unit="L"),
            IntentItem(name="bread", quantity=1, unit="pcs"),
        ],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True, max_deviation=0.0),
    )
    defaults.update(overrides)
    return IntentContract(**defaults)


def _make_cart(
    items: list[CartItem] | None = None,
    grand_total: float = 116.0,
    is_serviceable: bool = True,
) -> CommerceCart:
    """Build a minimal CommerceCart."""
    return CommerceCart(
        cart_id="test-cart-p4",
        items=items or [],
        item_total=grand_total,
        grand_total=grand_total,
        is_serviceable=is_serviceable,
    )


def _milk_item(name: str = "Amul Taaza Milk 1L Pouch", qty: int = 1, price: float = 66.0) -> CartItem:
    return CartItem(
        spin_id="SPIN-MILK-1L",
        name=name,
        pack_size="1 L",
        unit_price=price,
        quantity=qty,
        total_price=round(price * qty, 2),
    )


def _bread_item(qty: int = 1) -> CartItem:
    return CartItem(
        spin_id="SPIN-BREAD-400G",
        name="Whole Wheat Bread 400g",
        pack_size="400 g",
        unit_price=50.0,
        quantity=qty,
        total_price=50.0 * qty,
    )


@pytest.fixture
def verifier() -> IntentVerifier:
    return IntentVerifier()


# ---------------------------------------------------------------------------
# Test 1 — Exact cart pass
# ---------------------------------------------------------------------------

def test_exact_cart_pass(verifier: IntentVerifier) -> None:
    """A cart satisfying every intent item and constraint should PASS."""
    contract = _make_contract()
    cart = _make_cart(
        items=[_milk_item(), _bread_item()],
        grand_total=116.0,
    )
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.PASS
    assert result.violations == []
    assert result.unresolved_items == []
    assert result.budget_delta < 0  # Under budget


# ---------------------------------------------------------------------------
# Test 2 — Budget exceeded (hard, zero deviation)
# ---------------------------------------------------------------------------

def test_budget_exceeded_hard(verifier: IntentVerifier) -> None:
    """Grand total over hard budget with zero deviation → FAIL BUDGET_EXCEEDED."""
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=100.0, is_hard=True, max_deviation=0.0),
    )
    cart = _make_cart(grand_total=150.0, items=[_milk_item(), _bread_item()])
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.BUDGET_EXCEEDED in result.violation_codes
    assert result.budget_delta == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Test 3 — Budget slightly over but within allowed deviation → PASS
# ---------------------------------------------------------------------------

def test_budget_within_soft_deviation(verifier: IntentVerifier) -> None:
    """Grand total over budget but within max_deviation should not be a hard violation."""
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=110.0, is_hard=True, max_deviation=50.0),
    )
    # 116 is 6 over 110, well within 50 deviation
    cart = _make_cart(grand_total=116.0, items=[_milk_item(), _bread_item()])
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.PASS
    assert ViolationCode.BUDGET_EXCEEDED not in result.violation_codes


# ---------------------------------------------------------------------------
# Test 4 — Missing essential item
# ---------------------------------------------------------------------------

def test_missing_essential_item(verifier: IntentVerifier) -> None:
    """Cart missing an essential intent item → FAIL MISSING_ITEM."""
    contract = _make_contract()
    # Only milk in cart, bread is missing
    cart = _make_cart(items=[_milk_item()], grand_total=66.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.MISSING_ITEM in result.violation_codes
    assert any("bread" in item.lower() for item in result.unresolved_items)


# ---------------------------------------------------------------------------
# Test 5 — Wrong quantity with EXACT_QUANTITY constraint
# ---------------------------------------------------------------------------

def test_wrong_quantity_exact_constraint(verifier: IntentVerifier) -> None:
    """Cart with wrong quantity when EXACT_QUANTITY constraint exists → FAIL WRONG_QUANTITY."""
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=2, unit="L")],
        hard_constraints=[
            HardConstraint(
                constraint_type=ConstraintType.EXACT_QUANTITY,
                target="item:milk",
                rule="== 2",
                description="Exactly 2 units of milk required",
            )
        ],
    )
    # Only 1 milk in cart instead of required 2
    cart = _make_cart(items=[_milk_item(qty=1)], grand_total=66.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.WRONG_QUANTITY in result.violation_codes


# ---------------------------------------------------------------------------
# Test 6 — Hard brand lock violated
# ---------------------------------------------------------------------------

def test_hard_brand_lock_violated(verifier: IntentVerifier) -> None:
    """Cart with wrong brand when a hard brand lock is set → FAIL WRONG_BRAND."""
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=1, unit="L")],
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Mother Dairy",
                is_hard=True,
            )
        ],
    )
    # Cart has Amul, but Mother Dairy is hard-locked
    cart = _make_cart(items=[_milk_item(name="Amul Taaza Milk 1L Pouch")], grand_total=66.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.WRONG_BRAND in result.violation_codes
    hard_violations = [v for v in result.violations if v.violation_code == ViolationCode.WRONG_BRAND]
    assert all(v.is_hard for v in hard_violations)


# ---------------------------------------------------------------------------
# Test 7 — Soft brand preference deviated → PASS with deviation
# ---------------------------------------------------------------------------

def test_soft_brand_deviation_is_not_failure(verifier: IntentVerifier) -> None:
    """Cart with non-preferred soft brand → PASS with deviation recorded (no hard violation)."""
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=1, unit="L")],
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Mother Dairy",
                is_hard=False,  # soft preference
            )
        ],
    )
    # Amul instead of Mother Dairy — a soft deviation
    cart = _make_cart(items=[_milk_item(name="Amul Taaza Milk 1L Pouch"), _bread_item()], grand_total=116.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.PASS
    assert ViolationCode.WRONG_BRAND not in result.violation_codes
    assert len(result.deviations) >= 1


# ---------------------------------------------------------------------------
# Test 8 — Wrong pack size (strict tolerance)
# ---------------------------------------------------------------------------

def test_wrong_pack_size_strict_tolerance(verifier: IntentVerifier) -> None:
    """Cart item with wrong pack size under STRICT tolerance → FAIL WRONG_PACK_SIZE."""
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=1, unit="L", pack_size_preference="500 ml")],
        pack_size_rules=PackSizeRules(tolerance=SubstitutionTolerance.STRICT),
    )
    # Cart has 1L but 500ml is strictly required
    cart = _make_cart(items=[_milk_item(), _bread_item()], grand_total=116.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.WRONG_PACK_SIZE in result.violation_codes


# ---------------------------------------------------------------------------
# Test 9 — Stale cart flag
# ---------------------------------------------------------------------------

def test_stale_cart_flag(verifier: IntentVerifier) -> None:
    """Caller-supplied stale=True → FAIL STALE_CART."""
    contract = _make_contract()
    cart = _make_cart(items=[_milk_item(), _bread_item()], grand_total=116.0)
    result = verifier.verify(contract, cart, stale=True)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.STALE_CART in result.violation_codes
    assert result.is_stale is True


def test_non_serviceable_cart_is_stale(verifier: IntentVerifier) -> None:
    """CommerceCart with is_serviceable=False → FAIL STALE_CART."""
    contract = _make_contract()
    cart = _make_cart(
        items=[_milk_item(), _bread_item()],
        grand_total=116.0,
        is_serviceable=False,
    )
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.STALE_CART in result.violation_codes


# ---------------------------------------------------------------------------
# Test 10 — Dietary constraint violated by cart item
# ---------------------------------------------------------------------------

def test_dietary_violation_non_veg_in_veg_contract(verifier: IntentVerifier) -> None:
    """Cart contains a non-veg item under a vegetarian hard constraint → FAIL DIETARY_VIOLATION."""
    contract = _make_contract(
        dietary_constraints=[DietaryConstraint(tag="vegetarian", is_hard=True)],
    )
    non_veg_item = CartItem(
        spin_id="SPIN-CHICKEN-1",
        name="Farm Fresh Chicken Breast 500g",
        pack_size="500 g",
        unit_price=250.0,
        quantity=1,
        total_price=250.0,
    )
    cart = _make_cart(items=[_milk_item(), non_veg_item], grand_total=316.0)
    result = verifier.verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.DIETARY_VIOLATION in result.violation_codes
    diet_violations = [v for v in result.violations if v.violation_code == ViolationCode.DIETARY_VIOLATION]
    assert all(v.is_hard for v in diet_violations)


# ---------------------------------------------------------------------------
# Test 11 — Checkout without explicit confirmation
# ---------------------------------------------------------------------------

def test_checkout_without_confirmation_fails(verifier: IntentVerifier) -> None:
    """verify_checkout with explicit_confirmation=False always → FAIL UNAUTHORIZED_CHECKOUT."""
    contract = _make_contract()
    cart = _make_cart(items=[_milk_item(), _bread_item()], grand_total=116.0)
    result = verifier.verify_checkout(contract, cart, explicit_confirmation=False)

    assert result.status == VerificationStatus.FAIL
    assert ViolationCode.UNAUTHORIZED_CHECKOUT in result.violation_codes


def test_checkout_with_explicit_confirmation_passes(verifier: IntentVerifier) -> None:
    """verify_checkout with explicit_confirmation=True on a clean cart → PASS."""
    contract = _make_contract()
    cart = _make_cart(items=[_milk_item(), _bread_item()], grand_total=116.0)
    result = verifier.verify_checkout(contract, cart, explicit_confirmation=True)

    assert result.status == VerificationStatus.PASS
    assert ViolationCode.UNAUTHORIZED_CHECKOUT not in result.violation_codes


# ---------------------------------------------------------------------------
# Test 12 — Re-verify after simulated recovery → PASS
# ---------------------------------------------------------------------------

def test_reverify_after_recovery_passes(verifier: IntentVerifier) -> None:
    """After a simulated recovery that replaces missing items, re-verification should PASS."""
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=1, unit="L")],
        budget=BudgetConstraint(max_budget=200.0, is_hard=True, max_deviation=0.0),
    )
    # Simulate: first verify (milk missing)
    empty_cart = _make_cart(items=[], grand_total=0.0)
    first_result = verifier.verify(contract, empty_cart)
    assert first_result.status == VerificationStatus.FAIL
    assert ViolationCode.MISSING_ITEM in first_result.violation_codes

    # Simulate: recovery added milk → re-verify
    recovered_cart = _make_cart(items=[_milk_item()], grand_total=66.0)
    second_result = verifier.verify(contract, recovered_cart)
    assert second_result.status == VerificationStatus.PASS
    assert second_result.violations == []
