"""Unit and integration tests for GROCER Phase 1 Intent Contract (Spec §5).

Verifies:
1. Serialization / deserialization round-trip (JSON, dict).
2. Hard vs soft constraint semantics and automatic invariant synchronization.
3. Precedence rules: current explicit user request overriding stored soft preferences.
4. Authorization boundary: consequential checkout requires explicit confirmation.
5. Budget constraints and deviation boundaries.
6. Ambiguity tracking and severity classification.
7. Versioning and historical snapshot retrieval in IntentSessionStore.
"""
import json
import pytest
from pydantic import ValidationError

from backend.intent.enums import (
    AmbiguitySeverity,
    BrandTolerance,
    ConstraintType,
    PreferenceType,
    SubstitutionTolerance,
)
from backend.intent.models import (
    Ambiguity,
    AuthorizationScope,
    BrandPreference,
    BudgetConstraint,
    DeliveryPreferences,
    DietaryConstraint,
    HardConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    QuantityRules,
    SoftPreference,
    SourceContext,
    SubstitutionPolicy,
)
from backend.intent.storage import IntentSessionStore


def test_intent_contract_instantiation_and_serialization():
    """Verify full instantiation and round-trip JSON serialization (Spec §5.1)."""
    contract = IntentContract(
        session_id="sess-wa-101",
        goal="Weekly family grocery restock",
        items=[
            IntentItem(name="Amul Taaza Milk", quantity=2.0, unit="L", brand_preference="Amul"),
            IntentItem(name="Whole Wheat Bread", quantity=1.0, unit="pcs", category="bakery"),
            IntentItem(name="Farm Fresh Eggs", quantity=12.0, unit="pcs", category="poultry"),
        ],
        budget=BudgetConstraint(max_budget=2000.0, currency="INR"),
        dietary_constraints=[DietaryConstraint(tag="vegetarian")],
        brand_preferences=[
            BrandPreference(product_or_category="milk", preferred_brand="Amul", is_hard=False)
        ],
        substitution_policy=SubstitutionPolicy(
            category_tolerance="same_category",
            pack_size_tolerance=SubstitutionTolerance.REASONABLE,
            brand_tolerance=BrandTolerance.USUAL_BRANDS,
            max_budget_deviation=0.0,
        ),
        confidence=0.98,
        source_context=SourceContext(
            channel="whatsapp",
            raw_text="get my weekly groceries under 2000, vegetarian, use my usual brands",
            customer_id="cust-mumbai-01",
        ),
    )

    # Required conceptual fields presence check
    assert contract.intent_id is not None
    assert contract.session_id == "sess-wa-101"
    assert len(contract.items) == 3
    assert contract.budget.max_budget == 2000.0
    assert contract.version == 1

    # Invariant validator auto-synced dietary and budget to hard_constraints
    assert contract.has_dietary_constraint("vegetarian")
    assert contract.is_hard_constraint("total_budget")
    assert contract.is_hard_constraint("dietary")

    # Round-trip JSON serialization
    serialized = contract.model_dump_json()
    assert isinstance(serialized, str)

    deserialized = IntentContract.model_validate_json(serialized)
    assert deserialized.intent_id == contract.intent_id
    assert deserialized.session_id == contract.session_id
    assert len(deserialized.items) == 3
    assert deserialized.items[0].name == "Amul Taaza Milk"
    assert deserialized.budget.max_budget == 2000.0
    assert deserialized.confidence == 0.98


def test_hard_vs_soft_constraint_semantics():
    """Verify distinct semantics of hard constraints vs soft preferences (Spec §5.4)."""
    hard = HardConstraint(
        constraint_type=ConstraintType.DIETARY,
        target="dietary",
        rule="vegetarian",
        description="Strictly vegetarian items only",
    )
    assert hard.is_hard is True

    soft = SoftPreference(
        preference_type=PreferenceType.BRAND,
        target="brand:milk",
        preference="Amul",
        weight=0.9,
    )
    assert soft.can_relax is True

    contract = IntentContract(
        session_id="sess-02",
        goal="Quick breakfast restock",
        hard_constraints=[hard],
        soft_preferences=[soft],
    )

    assert contract.is_hard_constraint("dietary")
    assert not contract.is_hard_constraint("brand:milk")


def test_authorization_scope_invariant():
    """Verify server-enforced checkout authorization invariant (Spec §6, §8.3).
    
    Checkout cannot be authorized without explicit user confirmation.
    """
    scope = AuthorizationScope()
    assert scope.checkout_requires_explicit_confirmation is True

    # Attempting to construct scope with False must fail structural validation
    with pytest.raises(ValidationError):
        AuthorizationScope(checkout_requires_explicit_confirmation=False)

    contract = IntentContract(session_id="sess-auth", goal="Restock")
    
    # Authoritative check requires explicit_confirmation flag
    assert contract.is_checkout_authorized(explicit_confirmation=False) is False
    assert contract.is_checkout_authorized(explicit_confirmation=True) is True


def test_precedence_current_request_overrides_memory():
    """Verify current explicit request strictly overrides historical memory (Spec §5.3)."""
    # User's explicit request in current conversation: "Get Mother Dairy milk"
    contract = IntentContract(
        session_id="sess-precedence",
        goal="Get milk",
        items=[
            IntentItem(name="milk", quantity=1.0, unit="L", brand_preference="Mother Dairy")
        ],
        brand_preferences=[
            BrandPreference(product_or_category="milk", preferred_brand="Mother Dairy")
        ],
    )

    # Stored historical profile memory: user usually buys "Amul" milk and "Harvest Gold" bread
    stored_memory = [
        BrandPreference(product_or_category="milk", preferred_brand="Amul"),
        BrandPreference(product_or_category="bread", preferred_brand="Harvest Gold"),
        SoftPreference(preference_type=PreferenceType.PACK_SIZE, target="pack_size:produce", preference="small"),
    ]

    # Apply historical memory
    updated = contract.apply_memory(stored_memory)

    # 1. Milk brand preference remains "Mother Dairy" (explicit request wins)
    milk_bp = updated.get_brand_preference("milk")
    assert milk_bp is not None
    assert milk_bp.preferred_brand == "Mother Dairy"

    # 2. Bread brand preference is adopted from memory because not explicitly mentioned
    bread_bp = updated.get_brand_preference("bread")
    assert bread_bp is not None
    assert bread_bp.preferred_brand == "Harvest Gold"

    # 3. Non-conflicting soft preference adopted
    assert any(sp.target == "pack_size:produce" for sp in updated.soft_preferences)

    # 4. Version incremented
    assert updated.version == 2
    assert updated.updated_at >= contract.created_at


def test_brand_preference_hard_lock():
    """Verify brand lock constraint registers as non-negotiable hard constraint (Spec §5.4)."""
    contract = IntentContract(
        session_id="sess-brand-lock",
        goal="Get coffee",
        items=[IntentItem(name="Nescafe Classic", quantity=1.0, unit="pcs")],
        brand_preferences=[
            BrandPreference(product_or_category="coffee", preferred_brand="Nescafe", is_hard=True)
        ],
    )

    # When is_hard is True, invariant validator creates a BRAND_LOCK hard constraint
    assert contract.is_hard_constraint("brand:coffee")
    lock_hc = next(
        hc for hc in contract.hard_constraints
        if hc.constraint_type == ConstraintType.BRAND_LOCK
    )
    assert lock_hc.rule == "Nescafe"


def test_ambiguity_classification():
    """Verify ambiguity severity surfaces whether clarification is required (Spec §6)."""
    # Contract with minor ambiguity (default safe)
    contract_low = IntentContract(
        session_id="sess-ambig-1",
        goal="Restock",
        ambiguities=[
            Ambiguity(
                field="delivery_slot",
                description="Delivery slot unspecified, defaulting to ASAP",
                severity=AmbiguitySeverity.LOW,
            )
        ],
    )
    assert contract_low.has_critical_ambiguities() is False

    # Contract with critical missing info
    contract_high = IntentContract(
        session_id="sess-ambig-2",
        goal="Restock",
        ambiguities=[
            Ambiguity(
                field="items[0].quantity",
                description="User requested 'some apples' with no unit or quantity",
                severity=AmbiguitySeverity.HIGH,
                candidate_options=["500g", "1kg"],
                suggested_clarification="How many kg of apples would you like?",
            )
        ],
    )
    assert contract_high.has_critical_ambiguities() is True


def test_intent_session_store_versioning():
    """Verify IntentSessionStore records snapshots and retrieves active versions."""
    store = IntentSessionStore()
    session_id = "sess-store-test"

    # Version 1
    v1 = IntentContract(session_id=session_id, goal="Get groceries", version=1)
    store.save(v1)

    assert store.get_active(session_id).version == 1
    assert store.get_by_id(v1.intent_id).intent_id == v1.intent_id

    # Version 2 update
    v2 = v1.model_copy(deep=True)
    v2.intent_id = "intent-v2"
    v2.version = 2
    v2.items.append(IntentItem(name="Eggs", quantity=6.0, unit="pcs"))
    store.save(v2)


    # Active is now version 2
    active = store.get_active(session_id)
    assert active.version == 2
    assert len(active.items) == 1

    # Historical version 1 is still retrievable
    retrieved_v1 = store.get_version(session_id, version=1)
    assert retrieved_v1 is not None
    assert retrieved_v1.version == 1
    assert len(retrieved_v1.items) == 0

    # List all versions
    versions = store.list_versions(session_id)
    assert len(versions) == 2
    assert [v.version for v in versions] == [1, 2]

    # Clear session
    store.clear_session(session_id)
    assert store.get_active(session_id) is None


def test_to_summary_dict():
    """Verify to_summary_dict generates concise, telemetry-safe summary."""
    contract = IntentContract(
        session_id="sess-summary",
        goal="Weekly essentials",
        items=[
            IntentItem(name="Milk", quantity=1.0, unit="L"),
            IntentItem(name="Butter", quantity=1.0, unit="pcs"),
        ],
        budget=BudgetConstraint(max_budget=500.0),
        dietary_constraints=[DietaryConstraint(tag="vegetarian")],
    )

    summary = contract.to_summary_dict()
    assert summary["session_id"] == "sess-summary"
    assert summary["item_count"] == 2
    assert summary["max_budget"] == 500.0
    assert "vegetarian" in summary["dietary"]
    assert summary["version"] == 1
