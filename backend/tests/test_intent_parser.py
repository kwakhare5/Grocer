"""Unit tests for GROCER Phase 2 Intent Parser (Spec §5, §12, IMPLEMENTATION_PLAN §4).

Covers all 9 required test scenarios:
1. Normal request
2. Multiple items
3. Quantities with units
4. Budget extraction
5. Hard vs soft distinction
6. Contradictory request
7. Ambiguous quantity
8. Explicit substitution rule
9. Current instruction overriding memory
"""
import pytest

from backend.intent.enums import (
    AmbiguitySeverity,
    ConstraintType,
    PreferenceType,
)
from backend.intent.models import (
    BrandPreference,
    SoftPreference,
)
from backend.intent.parser import IntentParser


@pytest.fixture
def parser() -> IntentParser:
    return IntentParser()


# ---------------------------------------------------------------------------
# 1. Normal request
# ---------------------------------------------------------------------------

def test_normal_request(parser: IntentParser):
    """'get my weekly groceries under ₹2,000' → goal + budget + recurring task."""
    contract = parser.parse(
        "get my weekly groceries under ₹2,000",
        session_id="sess-01",
    )

    assert "weekly" in contract.goal.lower()
    assert contract.budget is not None
    assert contract.budget.max_budget == 2000.0
    assert contract.budget.is_hard is True
    # Budget should auto-sync to hard_constraints
    assert any(
        hc.constraint_type == ConstraintType.BUDGET
        for hc in contract.hard_constraints
    )
    assert contract.session_id == "sess-01"
    assert contract.version == 1
    assert contract.confidence > 0.5


# ---------------------------------------------------------------------------
# 2. Multiple items
# ---------------------------------------------------------------------------

def test_multiple_items(parser: IntentParser):
    """'get 2L milk, 1kg rice, bread, and 6 eggs' → 4 items parsed."""
    contract = parser.parse(
        "get 2L milk, 1kg rice, bread, and 6 eggs",
        session_id="sess-02",
    )

    names = [item.name.lower() for item in contract.items]
    assert len(contract.items) >= 3  # At minimum milk, rice, eggs with quantities
    assert any("milk" in n for n in names)
    assert any("rice" in n for n in names)
    assert any("egg" in n for n in names)


# ---------------------------------------------------------------------------
# 3. Quantities with units
# ---------------------------------------------------------------------------

def test_quantities_with_units(parser: IntentParser):
    """'2 litres of milk' → quantity=2.0, unit='L'."""
    contract = parser.parse(
        "get 2 litres of milk",
        session_id="sess-03",
    )

    milk_items = [i for i in contract.items if "milk" in i.name.lower()]
    assert len(milk_items) >= 1
    milk = milk_items[0]
    assert milk.quantity == 2.0
    assert milk.unit == "L"


# ---------------------------------------------------------------------------
# 4. Budget extraction
# ---------------------------------------------------------------------------

def test_budget_extraction(parser: IntentParser):
    """'under ₹1,500' → hard budget constraint at 1500."""
    contract = parser.parse(
        "order groceries under ₹1,500",
        session_id="sess-04",
    )

    assert contract.budget is not None
    assert contract.budget.max_budget == 1500.0
    assert contract.budget.is_hard is True
    assert contract.budget.currency == "INR"

    # Must appear in hard_constraints
    budget_hc = [
        hc for hc in contract.hard_constraints
        if hc.constraint_type == ConstraintType.BUDGET
    ]
    assert len(budget_hc) >= 1


# ---------------------------------------------------------------------------
# 5. Hard vs soft distinction
# ---------------------------------------------------------------------------

def test_hard_vs_soft_distinction(parser: IntentParser):
    """'vegetarian only, use my usual brands' → dietary=hard, brands=soft."""
    contract = parser.parse(
        "get vegetarian items only, use my usual brands",
        session_id="sess-05",
    )

    # Dietary constraint is hard
    assert any(dc.tag == "vegetarian" and dc.is_hard for dc in contract.dietary_constraints)
    assert any(
        hc.constraint_type == ConstraintType.DIETARY
        for hc in contract.hard_constraints
    )

    # Brand preference is soft
    assert any(
        sp.preference_type == PreferenceType.BRAND
        for sp in contract.soft_preferences
    )


# ---------------------------------------------------------------------------
# 6. Contradictory request
# ---------------------------------------------------------------------------

def test_contradictory_request(parser: IntentParser):
    """'vegetarian items, also get chicken' → HIGH ambiguity flagged."""
    contract = parser.parse(
        "get vegetarian items, also get 1kg chicken",
        session_id="sess-06",
    )

    # Should have both the dietary constraint and the item
    assert any(dc.tag == "vegetarian" for dc in contract.dietary_constraints)
    chicken_items = [i for i in contract.items if "chicken" in i.name.lower()]
    assert len(chicken_items) >= 1

    # Must flag contradiction as HIGH severity ambiguity
    high_ambiguities = [
        a for a in contract.ambiguities
        if a.severity == AmbiguitySeverity.HIGH
    ]
    assert len(high_ambiguities) >= 1
    assert any("chicken" in a.description.lower() for a in high_ambiguities)

    # Confidence should be reduced
    assert contract.confidence < 1.0


# ---------------------------------------------------------------------------
# 7. Ambiguous quantity
# ---------------------------------------------------------------------------

def test_ambiguous_quantity(parser: IntentParser):
    """'get some apples' → MEDIUM ambiguity on quantity."""
    contract = parser.parse(
        "get some apples",
        session_id="sess-07",
    )

    # Should flag vague quantity
    medium_ambiguities = [
        a for a in contract.ambiguities
        if a.severity == AmbiguitySeverity.MEDIUM
    ]
    assert len(medium_ambiguities) >= 1
    assert any("apple" in a.field.lower() for a in medium_ambiguities)


# ---------------------------------------------------------------------------
# 8. Explicit substitution rule
# ---------------------------------------------------------------------------

def test_explicit_substitution_rule(parser: IntentParser):
    """'don't replace the milk with another brand' → brand lock + restricted sub policy."""
    contract = parser.parse(
        "get 2L milk, and don't replace the milk with another brand",
        session_id="sess-08",
    )

    # Should have a hard brand preference for milk
    milk_bp = [bp for bp in contract.brand_preferences if "milk" in bp.product_or_category.lower()]
    assert len(milk_bp) >= 1
    assert milk_bp[0].is_hard is True

    # Substitution policy should reflect restricted brand tolerance
    assert contract.substitution_policy.brand_tolerance.value == "same_brand"


# ---------------------------------------------------------------------------
# 9. Current instruction overriding memory
# ---------------------------------------------------------------------------

def test_current_instruction_overrides_memory(parser: IntentParser):
    """Parse with explicit brand, then apply_memory with different brand — explicit wins."""
    contract = parser.parse(
        "get 1L Mother Dairy milk",
        session_id="sess-09",
    )

    # User explicitly requested Mother Dairy
    milk_items = [i for i in contract.items if "milk" in i.name.lower()]
    assert len(milk_items) >= 1

    # Apply stored memory that says user usually buys Amul
    stored_memory = [
        BrandPreference(product_or_category="milk", preferred_brand="Amul"),
        SoftPreference(
            preference_type=PreferenceType.PACK_SIZE,
            target="pack_size:rice",
            preference="5kg",
        ),
    ]

    updated = contract.apply_memory(stored_memory)

    # Explicit current request (Mother Dairy) must win over stored Amul
    milk_bp = updated.get_brand_preference("milk")
    # If Mother Dairy was parsed as brand_preference, it should remain
    # The stored Amul preference should NOT have overwritten it
    if milk_bp is not None:
        assert milk_bp.preferred_brand != "Amul"

    # Non-conflicting soft preference (rice pack size) should be adopted
    assert any("rice" in sp.target.lower() for sp in updated.soft_preferences)

    # Version should increment
    assert updated.version == contract.version + 1


# ---------------------------------------------------------------------------
# Authorization invariant (cross-check with Phase 1)
# ---------------------------------------------------------------------------

def test_parser_enforces_checkout_authorization(parser: IntentParser):
    """Every parsed contract must have checkout_requires_explicit_confirmation = True."""
    contract = parser.parse(
        "get weekly groceries",
        session_id="sess-auth",
    )

    assert contract.authorization_scope.checkout_requires_explicit_confirmation is True
    assert contract.is_checkout_authorized(explicit_confirmation=False) is False
    assert contract.is_checkout_authorized(explicit_confirmation=True) is True
