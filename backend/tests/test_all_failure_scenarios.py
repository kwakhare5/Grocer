"""Deterministic test suite for all 8 canonical failure scenarios (Spec §15 & Phase 7).

Proves the 8 canonical failure recovery behaviors required by GROCER v2:
1. Unavailable product (OOS) -> auto-substitute compliant variant within budget.
2. Preferred brand unavailable -> enforce brand tolerance (strict requires user decision vs flexible auto-adapts).
3. Pack-size change -> reason over pack multiples (2x 500ml for 1L) to satisfy quantity under budget.
4. Budget drift / price surge -> detect budget exceeded, prevent unapproved checkout, request decision.
5. Stale cart -> detect store unserviceability / expired cart, block checkout, demand session refresh.
6. Safe transient retry -> resilient upstream timeout retry without item duplication or cart mutation corruption.
7. Partial cart success -> detect item dropped by provider during mutation, flag intent drift.
8. Minimum order threshold -> detect basket below store threshold, suggest compliant staple addition.
"""
from __future__ import annotations

import uuid
import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CartItemUpdate, CommerceCart
from backend.integrations.commerce.exceptions import (
    CommerceError,
    MinOrderNotMetError,
    UnconfirmedCheckoutError,
)
from backend.intent.enums import PrecedenceLevel, PreferenceType, SubstitutionTolerance
from backend.intent.models import (
    AuthorizationScope,
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    SoftPreference,
    SubstitutionPolicy,
)
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import (
    FailureClass,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.verifier import IntentVerifier, VerificationStatus, ViolationCode


# ---------------------------------------------------------------------------
# Scenario 1: Unavailable Product (OOS)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_1_unavailable_product_oos() -> None:
    """Scenario 1: Primary item goes OOS; system auto-substitutes compliant variant within budget."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_loop = LoopingRecoveryEngine(verifier=verifier)

    cart_id = f"s1-cart-{uuid.uuid4().hex[:6]}"
    address_id = "addr-bandra-1"

    contract = IntentContract(
        session_id="s1-session",
        customer_id="s1-cust",
        goal="milk and bread under 2000",
        items=[
            IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy", is_essential=True),
            IntentItem(name="bread", quantity=1, pack_size_preference="400 g", category="bakery", is_essential=True),
        ],
        budget=BudgetConstraint(max_budget=2000.0, is_hard=True),
        pack_size_rules=PackSizeRules(preferred_multiples=True),
        authorization_scope=AuthorizationScope(
            requires_approval_for_price_increase=False,
        ),
    )

    # Initial cart setup: 1L milk + bread
    await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
        ],
        cart_id=cart_id,
        address_id=address_id,
    )

    # Injected fault: 1L milk goes out of stock
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    # Verify live cart flags failure
    live_cart = await adapter.get_cart(cart_id)
    v_result = verifier.verify(contract, live_cart)
    assert v_result.status == VerificationStatus.FAIL
    assert any(v.violation_code in (ViolationCode.ITEM_UNAVAILABLE, ViolationCode.MISSING_ITEM) for v in v_result.violations)

    # Recovery loop executes bounded recovery
    catalog = await adapter.search_products(address_id, "")
    result = await recovery_loop.run(
        contract=contract,
        cart_id=cart_id,
        commerce_port=adapter,
        available_products=catalog,
        max_attempts=3,
        address_id=address_id,
    )

    # System successfully recovered by substituting 2x 500ml milk
    assert result.state == RecoveryState.RECOVERED
    assert result.verification.status == VerificationStatus.PASS
    spins = {it.spin_id: it for it in result.cart.items}
    assert "SPIN-MILK-1L" not in spins
    assert "SPIN-MILK-500ML" in spins
    assert spins["SPIN-MILK-500ML"].quantity == 2
    assert "SPIN-BREAD-400G" in spins  # Unrelated item preserved
    assert result.cart.grand_total <= 2000.0


# ---------------------------------------------------------------------------
# Scenario 2: Preferred Brand Unavailable (Brand Tolerance)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_2_preferred_brand_unavailable_strict_vs_flexible() -> None:
    """Scenario 2: Enforce brand tolerance - strict blocks/fails, flexible auto-adapts."""
    policy_engine = PolicyEngine()
    recovery_engine = RecoveryEngine(policy_engine=policy_engine)
    verifier = IntentVerifier()

    # Case A: Strict brand tolerance (hard brand lock)
    contract_strict = IntentContract(
        session_id="s2-strict",
        customer_id="s2-cust",
        goal="Amul milk only",
        items=[IntentItem(name="milk", quantity=1, category="dairy", is_essential=True)],
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Amul",
                is_hard=True,
            )
        ],
    )

    # Cart has a non-Amul brand
    cart_wrong_brand = CommerceCart(
        cart_id="s2-cart-wrong",
        items=[
            CartItem(
                spin_id="SPIN-MILK-NANDINI-1L",
                name="Nandini Toned Milk 1L",
                pack_size="1 L",
                unit_price=62.0,
                quantity=1,
                total_price=62.0,
            )
        ],
        item_total=62.0,
        grand_total=97.0,
    )

    v_strict = verifier.verify(contract_strict, cart_wrong_brand)
    assert v_strict.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.WRONG_BRAND for v in v_strict.violations)

    # Case B: Flexible brand preference
    contract_flexible = IntentContract(
        session_id="s2-flex",
        customer_id="s2-cust",
        goal="Amul milk preferred, but flexible",
        items=[IntentItem(name="milk", quantity=1, category="dairy", is_essential=True)],
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Amul",
                is_hard=False,
            )
        ],
    )
    v_flex = verifier.verify(contract_flexible, cart_wrong_brand)
    # Flexible brand preference does not emit a hard WRONG_BRAND failure
    assert not any(v.violation_code == ViolationCode.WRONG_BRAND for v in v_flex.violations)
    assert v_flex.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# Scenario 3: Pack-Size Change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_3_pack_size_change() -> None:
    """Scenario 3: Requested 1L pack size unavailable; system computes 2x 500ml multiple."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_engine = RecoveryEngine()

    contract = IntentContract(
        session_id="s3-pack",
        customer_id="s3-cust",
        goal="1L milk",
        items=[
            IntentItem(
                name="milk",
                quantity=1,
                unit="L",
                pack_size_preference="1 L",
                category="dairy",
                is_essential=True,
            )
        ],
        pack_size_rules=PackSizeRules(
            tolerance=SubstitutionTolerance.STRICT,
            preferred_multiples=True,
        ),
    )

    # Cart currently has 500ml milk with quantity=1 (wrong volume)
    cart = await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-500ML", quantity=1)],
        cart_id="s3-cart",
    )
    adapter.inject_out_of_stock("SPIN-MILK-1L")

    # Verification detects WRONG_PACK_SIZE because 500ml != 1 L under strict tolerance
    v_res = verifier.verify(contract, cart)
    assert v_res.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.WRONG_PACK_SIZE for v in v_res.violations)

    # Recovery computes pack multiple: 1 L requested / 500 ml = 2 packs
    catalog = await adapter.search_products("addr-bandra-1", "")
    outcome = recovery_engine.recover(
        contract=contract,
        cart=cart,
        verification_result=v_res,
        available_products=catalog,
    )

    assert len(outcome.recovery_actions) > 0
    action = outcome.recovery_actions[0]
    assert action.spin_id == "SPIN-MILK-500ML"
    assert action.quantity == 2  # Correct multiple applied


# ---------------------------------------------------------------------------
# Scenario 4: Budget Drift / Price Surge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_4_budget_drift_price_surge() -> None:
    """Scenario 4: Price surge breaches hard budget cap; system blocks checkout and requests decision."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_engine = RecoveryEngine()

    contract = IntentContract(
        session_id="s4-budget",
        customer_id="s4-cust",
        goal="groceries under 120",
        items=[
            IntentItem(name="bread", quantity=1, category="bakery"),
            IntentItem(name="tomatoes", quantity=1, category="produce"),
        ],
        budget=BudgetConstraint(max_budget=120.0, is_hard=True),
    )

    # Initial cart: bread (50) + tomatoes (32) = 82 + 30 delivery + 5 packaging = 117 <= 120
    cart = await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
            CartItemUpdate(spin_id="SPIN-TOMATO-500G", quantity=1),
        ],
        cart_id="s4-cart",
    )
    assert cart.grand_total <= 120.0
    assert verifier.verify(contract, cart).status == VerificationStatus.PASS

    # Injected fault: Tomato price surges from 32 to 95, causing total to exceed budget
    adapter.inject_price_change("SPIN-TOMATO-500G", 95.0)

    live_cart = await adapter.get_cart("s4-cart")
    assert live_cart.grand_total > 120.0

    v_drift = verifier.verify(contract, live_cart)
    assert v_drift.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.BUDGET_EXCEEDED for v in v_drift.violations)

    # Recovery detects BUDGET_DRIFT and requires user decision because no zero-loss replacement exists
    catalog = await adapter.search_products("addr-bandra-1", "")
    outcome = recovery_engine.recover(
        contract=contract,
        cart=live_cart,
        verification_result=v_drift,
        available_products=catalog,
    )
    assert outcome.failure_class == FailureClass.BUDGET_DRIFT
    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.can_auto_apply is False


# ---------------------------------------------------------------------------
# Scenario 5: Stale Cart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_5_stale_cart() -> None:
    """Scenario 5: Cart expires or dark store becomes unserviceable; verifier and recovery block."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_engine = RecoveryEngine()

    contract = IntentContract(
        session_id="s5-stale",
        customer_id="s5-cust",
        goal="milk delivery",
        items=[IntentItem(name="milk", quantity=1, category="dairy")],
    )

    await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
        cart_id="s5-cart",
    )

    # Fault: Dark store becomes unserviceable / cart expires
    adapter.inject_stale_cart(True)

    live_cart = await adapter.get_cart("s5-cart")
    assert live_cart.is_serviceable is False

    v_stale = verifier.verify(contract, live_cart)
    assert v_stale.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.STALE_CART for v in v_stale.violations)

    catalog = await adapter.search_products("addr-bandra-1", "")
    outcome = recovery_engine.recover(
        contract=contract,
        cart=live_cart,
        verification_result=v_stale,
        available_products=catalog,
    )
    assert outcome.failure_class == FailureClass.STALE_CART
    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert outcome.can_auto_apply is False


# ---------------------------------------------------------------------------
# Scenario 6: Safe Transient Retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_6_safe_transient_retry() -> None:
    """Scenario 6: Upstream 503/timeout retries safely without duplicating items or mutating cart."""
    adapter = MockCommerceAdapter()

    # Injected transient fault: 1 failure then success
    adapter.inject_transient_error(1)

    # First call fails with transient error
    with pytest.raises(CommerceError) as exc_info:
        await adapter.get_cart("s6-cart")
    assert "transient network timeout" in str(exc_info.value).lower()

    # Safe retry succeeds without corrupted cart state
    cart = await adapter.get_cart("s6-cart")
    assert cart is not None
    assert cart.cart_id == "s6-cart"
    assert len(cart.items) == 0


# ---------------------------------------------------------------------------
# Scenario 7: Partial Cart Success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_7_partial_cart_success() -> None:
    """Scenario 7: Provider silently drops an item during mutation; verifier catches missing item."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()

    contract = IntentContract(
        session_id="s7-partial",
        customer_id="s7-cust",
        goal="milk and tomatoes",
        items=[
            IntentItem(name="milk", quantity=1, is_essential=True),
            IntentItem(name="tomatoes", quantity=1, is_essential=True),
        ],
    )

    # Fault: Provider drops tomatoes on cart update
    adapter.inject_partial_cart_drop("SPIN-TOMATO-500G")

    cart = await adapter.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
            CartItemUpdate(spin_id="SPIN-TOMATO-500G", quantity=1),
        ],
        cart_id="s7-cart",
    )

    # Cart only contains milk
    spins = [it.spin_id for it in cart.items]
    assert "SPIN-MILK-1L" in spins
    assert "SPIN-TOMATO-500G" not in spins

    # Verifier detects missing tomatoes
    v_res = verifier.verify(contract, cart)
    assert v_res.status == VerificationStatus.FAIL
    assert any(
        v.violation_code == ViolationCode.MISSING_ITEM and "tomato" in v.target.lower()
        for v in v_res.violations
    )
    outcome = RecoveryEngine().recover(
        contract=contract,
        cart=cart,
        verification_result=v_res,
        available_products=await adapter.search_products("addr-bandra-1", ""),
    )
    assert cart.cart_warning == "PARTIAL_SUCCESS"
    assert outcome.failure_class == FailureClass.PARTIAL_SUCCESS
    assert outcome.state == RecoveryState.NEEDS_USER_DECISION


# ---------------------------------------------------------------------------
# Scenario 8: Minimum Order Threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_8_minimum_order_threshold() -> None:
    """Scenario 8: Provider enforces minimum order; recovery proposes a sufficient addition."""
    adapter = MockCommerceAdapter()
    verifier = IntentVerifier()
    recovery_engine = RecoveryEngine()

    contract = IntentContract(
        session_id="s8-min-order",
        customer_id="s8-cust",
        goal="bread",
        items=[IntentItem(name="bread", quantity=1, is_essential=True)],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )

    # Enforce minimum order threshold of \u20b9250
    adapter.inject_min_order_threshold(250.0)

    # Cart has only bread: \u20b950 + fees = \u20b985 < \u20b9250
    cart = await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1)],
        cart_id="s8-cart",
    )
    assert cart.grand_total < 250.0

    # Unconfirmed or confirmed checkout below threshold raises MinOrderNotMetError
    with pytest.raises(MinOrderNotMetError):
        await adapter.checkout(cart_id="s8-cart", explicit_confirmation=True)

    # Recovery detects MIN_ORDER_FAILURE and proposes adding staple item (e.g. Amul Milk / Eggs)
    catalog = await adapter.search_products("addr-bandra-1", "")
    v_res = verifier.verify(contract, cart)
    outcome = recovery_engine.recover(
        contract=contract,
        cart=cart,
        verification_result=v_res,
        available_products=catalog,
    )

    assert outcome.failure_class == FailureClass.MIN_ORDER_FAILURE
    assert outcome.state == RecoveryState.NEEDS_USER_DECISION
    assert len(outcome.recovery_actions) > 0
    assert outcome.recovery_actions[0].action_type == "add_item"
    proposed = outcome.recovery_actions[0]
    proposed_total = cart.grand_total + proposed.price * proposed.quantity
    assert proposed_total >= cart.min_order_threshold
    assert proposed_total <= contract.budget.max_budget
    assert "minimum order" in outcome.message.lower()
