"""Unit tests for GROCER Phase 5 Recovery Engine (Spec §10, §16.2).

Covers 10 core scenarios:
 1. Single clear substitute available → auto-recover (RECOVERED)
 2. Two materially similar candidates with close scores → ask user (NEEDS_USER_DECISION)
 3. No candidates in category/catalog → BLOCKED
 4. Candidate violates hard dietary constraint → filtered out → BLOCKED
 5. Brand unavailable, alternative in alternative_brands list → auto-recover (RECOVERED)
 6. Budget drift — cheaper swap brings total under budget → RECOVERED
 7. Budget drift — no cheaper swap available → NEEDS_USER_DECISION
 8. Stale cart → always NEEDS_USER_DECISION
 9. Max attempts exceeded → FAILED
10. Clean cart (PASS verification) → RECOVERED with no actions
"""
from __future__ import annotations

import pytest

from backend.integrations.commerce.models import (
    CartItem,
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.intent.enums import BrandTolerance, SubstitutionTolerance
from backend.intent.models import (
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SubstitutionPolicy,
)
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import (
    FailureClass,
    RecoveryEngine,
    RecoveryState,
)
from backend.intent.verifier import (
    ConstraintViolation,
    VerificationResult,
    VerificationStatus,
    ViolationCode,
)


# ---------------------------------------------------------------------------
# Fixtures and Catalog Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> RecoveryEngine:
    return RecoveryEngine(policy_engine=PolicyEngine())


def _make_catalog() -> list[CommerceProductItem]:
    """Catalog with standard dairy and bakery items."""
    return [
        CommerceProductItem(
            product_id="prod-milk-amul",
            name="Amul Taaza Fresh Toned Milk",
            category="dairy",
            variants=[
                ProductVariant(
                    spin_id="SPIN-AMUL-1L",
                    name="Amul Taaza Milk 1L Pouch",
                    pack_size="1 L",
                    price=66.0,
                    mrp=68.0,
                    in_stock=True,
                ),
                ProductVariant(
                    spin_id="SPIN-AMUL-500ML",
                    name="Amul Taaza Milk 500ml Pouch",
                    pack_size="500 ml",
                    price=34.0,
                    mrp=35.0,
                    in_stock=True,
                ),
            ],
        ),
        CommerceProductItem(
            product_id="prod-milk-motherdairy",
            name="Mother Dairy Toned Milk",
            category="dairy",
            variants=[
                ProductVariant(
                    spin_id="SPIN-MD-1L",
                    name="Mother Dairy Milk 1L Pouch",
                    pack_size="1 L",
                    price=66.0,
                    mrp=68.0,
                    in_stock=True,
                ),
            ],
        ),
        CommerceProductItem(
            product_id="prod-bread-wheat",
            name="Whole Wheat Brown Bread",
            category="bakery",
            variants=[
                ProductVariant(
                    spin_id="SPIN-BREAD-400G",
                    name="Whole Wheat Bread 400g",
                    pack_size="400 g",
                    price=50.0,
                    mrp=55.0,
                    in_stock=True,
                ),
            ],
        ),
        CommerceProductItem(
            product_id="prod-chicken",
            name="Fresh Chicken Breast 500g",
            category="meat",
            variants=[
                ProductVariant(
                    spin_id="SPIN-CHICKEN-500G",
                    name="Fresh Chicken Breast 500g",
                    pack_size="500 g",
                    price=250.0,
                    mrp=280.0,
                    in_stock=True,
                ),
            ],
        ),
    ]


def _make_contract(**overrides) -> IntentContract:
    defaults = dict(
        session_id="test-recovery-session",
        goal="weekly restock",
        items=[
            IntentItem(name="milk", quantity=1, unit="L", pack_size_preference="1 L", category="dairy"),
        ],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True, max_deviation=0.0),
        substitution_policy=SubstitutionPolicy(
            allow_substitutions=True,
            brand_tolerance=BrandTolerance.USUAL_BRANDS,
        ),
    )
    defaults.update(overrides)
    return IntentContract(**defaults)


def _make_cart(
    items: list[CartItem] | None = None,
    grand_total: float = 66.0,
    is_serviceable: bool = True,
) -> CommerceCart:
    return CommerceCart(
        cart_id="cart-recov-1",
        items=items or [],
        item_total=grand_total,
        grand_total=grand_total,
        is_serviceable=is_serviceable,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_clear_substitute_auto_recovers(engine: RecoveryEngine) -> None:
    """When a single clear substitute matches the intent, auto-apply and return RECOVERED."""
    contract = _make_contract(
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Amul",
                alternative_brands=["Mother Dairy"],
            )
        ]
    )
    # Cart has no milk (MISSING_ITEM)
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="Essential item 'milk' missing",
                is_hard=True,
            )
        ],
        unresolved_items=["milk"],
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.RECOVERED
    assert outcome.failure_class == FailureClass.ITEM_UNAVAILABLE
    assert outcome.can_auto_apply is True
    assert len(outcome.recovery_actions) == 1
    assert "Amul" in outcome.recovery_actions[0].name


def test_two_close_candidates_needs_user_decision(engine: RecoveryEngine) -> None:
    """When multiple candidates are equally viable, return NEEDS_USER_DECISION with options."""
    # Contract has no brand preference for milk and flexible tolerance
    contract = _make_contract(
        items=[IntentItem(name="milk", quantity=1, unit="L", category="dairy")],
        brand_preferences=[],  # Neutral
    )
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="Milk is missing",
                is_hard=True,
            )
        ],
        unresolved_items=["milk"],
    )

    # Catalog with Amul 1L and Mother Dairy 1L at exact same price
    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert len(outcome.candidates_for_user) >= 2
    assert outcome.can_auto_apply is False


def test_no_candidate_in_category_blocked(engine: RecoveryEngine) -> None:
    """When no in-stock candidates exist in the requested category, return BLOCKED."""
    contract = _make_contract(
        items=[IntentItem(name="olive oil", quantity=1, unit="bottle", category="oils")],
    )
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="olive oil",
                detail="Essential item 'olive oil' missing",
                is_hard=True,
            )
        ],
        unresolved_items=["olive oil"],
    )

    catalog = _make_catalog()  # Only has dairy, bakery, meat
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.BLOCKED
    assert outcome.can_auto_apply is False


def test_candidate_violating_hard_dietary_filtered_out(engine: RecoveryEngine) -> None:
    """Candidates violating hard dietary constraint (e.g. meat in veg contract) are filtered out."""
    contract = _make_contract(
        dietary_constraints=[DietaryConstraint(tag="vegetarian", is_hard=True)],
        items=[IntentItem(name="chicken", quantity=1, unit="pack", category="meat")],
    )
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="chicken",
                detail="Chicken missing",
                is_hard=True,
            )
        ],
        unresolved_items=["chicken"],
    )

    # Chicken exists in catalog, but contract is strictly vegetarian
    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.BLOCKED
    assert outcome.can_auto_apply is False


def test_brand_unavailable_alternative_in_list_auto_recovers(engine: RecoveryEngine) -> None:
    """When preferred brand is unavailable, but an approved alternative exists, auto-recover."""
    contract = _make_contract(
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Nestle",  # Not in catalog
                alternative_brands=["Amul", "Mother Dairy"],
            )
        ]
    )
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="Milk missing",
                is_hard=True,
            )
        ],
        unresolved_items=["milk"],
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.RECOVERED
    assert outcome.can_auto_apply is True
    assert outcome.recovery_actions[0].spin_id.startswith("SPIN-AMUL")


def test_budget_drift_never_underfills_requested_quantity(engine: RecoveryEngine) -> None:
    """A nominally cheaper pack cannot be applied if exact quantity would exceed budget."""
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=50.0, is_hard=True, max_deviation=0.0)
    )
    # Cart has Amul 1L at ₹66, which is ₹16 over ₹50 budget
    current_item = CartItem(
        spin_id="SPIN-AMUL-1L",
        name="Amul Taaza Milk 1L Pouch",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    cart = _make_cart(items=[current_item], grand_total=66.0)

    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.BUDGET_EXCEEDED,
                target="total_budget",
                detail="Cart total ₹66 exceeds hard budget ₹50",
                is_hard=True,
            )
        ],
        budget_delta=16.0,
    )

    # 500 ml needs two packs to preserve 1 L, costing ₹68 and still exceeding budget.
    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.failure_class == FailureClass.BUDGET_DRIFT
    assert outcome.can_auto_apply is False
    assert outcome.recovery_actions == []


def test_missing_item_recovery_prices_all_required_packs_before_auto_apply(
    engine: RecoveryEngine,
) -> None:
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=50.0, is_hard=True, max_deviation=0.0)
    )
    cart = _make_cart(items=[], grand_total=0.0)
    verification = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="Milk missing",
                is_hard=True,
            )
        ],
        unresolved_items=["milk"],
    )
    catalog = [
        CommerceProductItem(
            product_id="milk",
            name="Amul Milk",
            category="dairy",
            variants=[
                ProductVariant(
                    spin_id="milk-500",
                    name="Amul Milk 500 ml",
                    pack_size="500 ml",
                    price=30.0,
                    mrp=30.0,
                )
            ],
        )
    ]

    outcome = engine.recover(contract, cart, verification, catalog)

    assert outcome.can_auto_apply is False
    assert outcome.recovery_actions == []


def test_budget_recovery_respects_hard_multiword_brand_lock(
    engine: RecoveryEngine,
) -> None:
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=70.0, is_hard=True, max_deviation=0.0),
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Mother Dairy",
                is_hard=True,
            )
        ],
    )
    current_item = CartItem(
        spin_id="SPIN-MD-1L",
        name="Mother Dairy Milk 1L Pouch",
        pack_size="1 L",
        unit_price=80.0,
        quantity=1,
        total_price=80.0,
        brand="Mother Dairy",
    )
    outcome = engine.recover(
        contract,
        _make_cart(items=[current_item], grand_total=80.0),
        VerificationResult(
            status=VerificationStatus.FAIL,
            violations=[
                ConstraintViolation(
                    violation_code=ViolationCode.BUDGET_EXCEEDED,
                    target="total_budget",
                    detail="Budget exceeded",
                    is_hard=True,
                )
            ],
            budget_delta=10.0,
        ),
        _make_catalog(),
    )

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.can_auto_apply is False


def test_budget_drift_no_swap_possible_needs_user_decision(engine: RecoveryEngine) -> None:
    """Cart over budget with no cheaper alternative must ask user to decide."""
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=30.0, is_hard=True, max_deviation=0.0)
    )
    # Cart has Whole Wheat Bread at ₹50, over budget by ₹20. Cheapest variant in catalog is ₹34.
    current_item = CartItem(
        spin_id="SPIN-BREAD-400G",
        name="Whole Wheat Bread 400g",
        pack_size="400 g",
        unit_price=50.0,
        quantity=1,
        total_price=50.0,
    )
    cart = _make_cart(items=[current_item], grand_total=50.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.BUDGET_EXCEEDED,
                target="total_budget",
                detail="Cart total ₹50 exceeds hard budget ₹30",
                is_hard=True,
            )
        ],
        budget_delta=20.0,
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.failure_class == FailureClass.BUDGET_DRIFT
    assert outcome.can_auto_apply is False


def test_stale_cart_always_needs_user_decision(engine: RecoveryEngine) -> None:
    """Stale or non-serviceable cart cannot be auto-repaired; must ask user."""
    contract = _make_contract()
    cart = _make_cart(is_serviceable=False)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.STALE_CART,
                target="cart",
                detail="Cart is stale",
                is_hard=True,
            )
        ],
        is_stale=True,
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.failure_class == FailureClass.STALE_CART
    assert outcome.can_auto_apply is False


def test_max_attempts_exceeded_fails(engine: RecoveryEngine) -> None:
    """Recovery must be bounded: exceeding max_attempts returns FAILED."""
    contract = _make_contract()
    cart = _make_cart(items=[])
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="Milk missing",
                is_hard=True,
            )
        ],
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog, attempt_number=4, max_attempts=3)

    assert outcome.state == RecoveryState.FAILED
    assert "exceeded maximum attempts" in outcome.message


def test_clean_cart_no_recovery_needed(engine: RecoveryEngine) -> None:
    """If cart already passes verification, recovery returns RECOVERED with zero actions."""
    contract = _make_contract()
    cart = _make_cart()
    v_res = VerificationResult(status=VerificationStatus.PASS)

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.RECOVERED
    assert outcome.recovery_actions == []
    assert outcome.can_auto_apply is True


def test_pack_size_multiples_auto_recovers(engine: RecoveryEngine) -> None:
    """When 1L is unavailable, 2x 500ml packs are automatically ordered if preferred_multiples is True."""
    contract = _make_contract(
        items=[
            IntentItem(name="milk", quantity=1, unit="L", pack_size_preference="1 L", category="dairy"),
        ],
        pack_size_rules=PackSizeRules(tolerance=SubstitutionTolerance.REASONABLE, preferred_multiples=True),
        brand_preferences=[
            BrandPreference(product_or_category="milk", preferred_brand="Amul"),
        ],
    )
    # Catalog where only 500ml is in stock (1L is OOS)
    catalog = [
        CommerceProductItem(
            product_id="prod-milk-amul",
            name="Amul Taaza Fresh Toned Milk",
            category="dairy",
            variants=[
                ProductVariant(
                    spin_id="SPIN-AMUL-500ML",
                    name="Amul Taaza Milk 500ml Pouch",
                    pack_size="500 ml",
                    price=34.0,
                    mrp=35.0,
                    in_stock=True,
                ),
            ],
        ),
    ]
    cart = _make_cart(items=[], grand_total=0.0)
    v_res = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.MISSING_ITEM,
                target="milk",
                detail="1L Milk missing",
                is_hard=True,
            )
        ],
        unresolved_items=["milk"],
    )

    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.RECOVERED
    assert outcome.can_auto_apply is True
    assert len(outcome.recovery_actions) == 1
    action = outcome.recovery_actions[0]
    assert action.spin_id == "SPIN-AMUL-500ML"
    assert action.quantity == 2  # 2x 500ml for 1L
    assert "2x" in action.reason


def test_min_order_threshold_needs_user_decision(engine: RecoveryEngine) -> None:
    """When cart is below minimum order threshold, engine suggests adding staple items."""
    contract = _make_contract(
        budget=BudgetConstraint(max_budget=500.0, is_hard=True)
    )
    # Cart has only milk at ₹66, which is below min_order_threshold of ₹99.0
    milk_item = CartItem(
        spin_id="SPIN-AMUL-1L",
        name="Amul Taaza Milk 1L Pouch",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    cart = CommerceCart(
        cart_id="cart-min-order",
        items=[milk_item],
        item_total=66.0,
        grand_total=66.0,
        is_serviceable=True,
        min_order_threshold=99.0,
    )
    v_res = VerificationResult(
        status=VerificationStatus.PASS,  # All intent items met, but basket threshold isn't
        violations=[],
    )

    catalog = _make_catalog()
    outcome = engine.recover(contract, cart, v_res, catalog)

    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.failure_class == FailureClass.MIN_ORDER_FAILURE
    assert len(outcome.candidates_for_user) >= 1
    assert "minimum order threshold" in outcome.message


def test_transient_error_safe_retry(engine: RecoveryEngine) -> None:
    """Transient errors generate a safe retry action per provider contract."""
    contract = _make_contract()
    cart = _make_cart()
    v_res = VerificationResult(status=VerificationStatus.FAIL)

    # Recovery with explicit transient error
    outcome = engine._handle_transient_error(attempt_number=1, max_attempts=3)

    assert outcome.state == RecoveryState.RECOVERED
    assert outcome.failure_class == FailureClass.TRANSIENT_ERROR
    assert outcome.can_auto_apply is True
    assert outcome.recovery_actions[0].action_type == "retry"


@pytest.mark.asyncio
async def test_execute_recovery_closed_loop(engine: RecoveryEngine) -> None:
    """Full closed-loop test: failure -> compute recovery -> update cart -> re-verify -> RECOVERED."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.intent.verifier import IntentVerifier

    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()

    contract = _make_contract(
        items=[
            IntentItem(name="milk", quantity=1, unit="L", pack_size_preference="1 L", category="dairy"),
            IntentItem(name="bread", quantity=1, unit="pcs", category="bakery"),
        ],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
        brand_preferences=[
            BrandPreference(product_or_category="milk", preferred_brand="Amul"),
        ],
    )

    # Initial state: only bread in cart, milk missing
    initial_cart = await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1)],
        cart_id="cart-closed-loop",
    )
    v_result = verifier.verify(contract, initial_cart)
    assert v_result.status == VerificationStatus.FAIL
    assert ViolationCode.MISSING_ITEM in v_result.violation_codes

    # Execute closed-loop recovery
    catalog = await adapter.search_products(address_id="addr-bandra-1", query="")
    updated_cart, final_v_result, outcome = await engine.execute_recovery(
        contract=contract,
        cart_id="cart-closed-loop",
        commerce_port=adapter,
        verifier=verifier,
        available_products=catalog,
        verification_result=v_result,
    )

    assert outcome.state == RecoveryState.RECOVERED
    assert final_v_result.status == VerificationStatus.PASS
    assert len(updated_cart.items) == 2
    item_names = [i.name for i in updated_cart.items]
    assert any("Amul" in name for name in item_names)
    assert any("Bread" in name for name in item_names)
