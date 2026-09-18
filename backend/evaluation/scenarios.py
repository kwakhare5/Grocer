"""Canonical test scenarios for the GROCER v2 evaluation framework (Spec §15, §16, §20).

Provides reproducible scenario configurations for the 8 canonical failure cases
plus standard replenishment baselines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate
from backend.intent.enums import SubstitutionTolerance
from backend.intent.models import (
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
)
from backend.intent.recovery import FailureClass, RecoveryState


@dataclass
class ScenarioDefinition:
    """Specification of an evaluation scenario with reproducible faults."""
    id: str
    name: str
    description: str
    build_contract: Callable[[str], IntentContract]
    initial_items: list[CartItemUpdate]
    inject_fault: Callable[[MockCommerceAdapter, str], None]
    expected_failure_class: FailureClass
    expected_recovery_state: RecoveryState
    expected_auto_applied: bool


def _build_s1_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="milk and bread under 2000",
        items=[
            IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy", is_essential=True),
            IntentItem(name="bread", quantity=1, pack_size_preference="400 g", category="bakery", is_essential=True),
        ],
        budget=BudgetConstraint(max_budget=2000.0, is_hard=True),
        pack_size_rules=PackSizeRules(preferred_multiples=True),
    )


def _build_s2_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="Amul milk only with hard brand lock",
        items=[IntentItem(name="milk", quantity=1, pack_size_preference="1 L", category="dairy", is_essential=True)],
        brand_preferences=[
            BrandPreference(
                product_or_category="milk",
                preferred_brand="Amul",
                is_hard=True,
            )
        ],
        pack_size_rules=PackSizeRules(
            tolerance=SubstitutionTolerance.STRICT,
            preferred_multiples=False,
        ),
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def _build_s3_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
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
            tolerance=SubstitutionTolerance.REASONABLE,
            preferred_multiples=True,
        ),
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def _build_s4_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="groceries under 120",
        items=[
            IntentItem(name="bread", quantity=1, category="bakery"),
            IntentItem(name="tomatoes", quantity=1, category="produce"),
        ],
        budget=BudgetConstraint(max_budget=120.0, is_hard=True),
    )


def _build_s5_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="milk delivery",
        items=[IntentItem(name="milk", quantity=1, category="dairy")],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def _build_s6_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="milk delivery with transient resilience",
        items=[IntentItem(name="milk", quantity=1, category="dairy")],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def _build_s7_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="milk and tomatoes complete basket",
        items=[
            IntentItem(name="milk", quantity=1, is_essential=True),
            IntentItem(name="tomatoes", quantity=1, is_essential=True),
        ],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def _build_s8_contract(session_id: str) -> IntentContract:
    return IntentContract(
        session_id=session_id,
        customer_id=f"cust-{session_id}",
        goal="bread with minimum order threshold",
        items=[IntentItem(name="bread", quantity=1, is_essential=True)],
        budget=BudgetConstraint(max_budget=500.0, is_hard=True),
    )


def get_canonical_scenarios() -> list[ScenarioDefinition]:
    """Return the 8 canonical evaluation scenarios mapping to Master Spec §15."""
    return [
        ScenarioDefinition(
            id="SCN-01",
            name="Unavailable Product (OOS)",
            description="Primary 1L milk SKU goes OOS; auto-substitutes 2x 500ml milk within budget.",
            build_contract=_build_s1_contract,
            initial_items=[
                CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1),
                CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
            ],
            inject_fault=lambda adapter, cart_id: adapter.inject_out_of_stock("SPIN-MILK-1L"),
            expected_failure_class=FailureClass.ITEM_UNAVAILABLE,
            expected_recovery_state=RecoveryState.RECOVERED,
            expected_auto_applied=True,
        ),
        ScenarioDefinition(
            id="SCN-02",
            name="Preferred Brand Unavailable (Strict Lock)",
            description="User has hard brand lock on Amul; non-compliant brand requires user decision.",
            build_contract=_build_s2_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
            inject_fault=lambda adapter, cart_id: (
                adapter.inject_brand_mismatch(cart_id, "SPIN-MILK-1L", "Nandini Toned Milk 1L"),
                adapter.inject_out_of_stock("SPIN-MILK-1L"),
            ),
            expected_failure_class=FailureClass.BRAND_UNAVAILABLE,
            expected_recovery_state=RecoveryState.NEEDS_USER_DECISION,
            expected_auto_applied=False,
        ),
        ScenarioDefinition(
            id="SCN-03",
            name="Pack Size Change",
            description="1L pack unavailable; system computes pack multiple (2x 500ml) to satisfy volume.",
            build_contract=_build_s3_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
            inject_fault=lambda adapter, cart_id: adapter.inject_out_of_stock("SPIN-MILK-1L"),
            expected_failure_class=FailureClass.ITEM_UNAVAILABLE,
            expected_recovery_state=RecoveryState.RECOVERED,
            expected_auto_applied=True,
        ),
        ScenarioDefinition(
            id="SCN-04",
            name="Budget Drift / Price Surge",
            description="Tomato price surges, breaching hard budget cap; system blocks checkout.",
            build_contract=_build_s4_contract,
            initial_items=[
                CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
                CartItemUpdate(spin_id="SPIN-TOMATO-500G", quantity=1),
            ],
            inject_fault=lambda adapter, cart_id: adapter.inject_price_change("SPIN-TOMATO-500G", 95.0),
            expected_failure_class=FailureClass.BUDGET_DRIFT,
            expected_recovery_state=RecoveryState.NEEDS_USER_DECISION,
            expected_auto_applied=False,
        ),
        ScenarioDefinition(
            id="SCN-05",
            name="Stale Cart / Store Unserviceable",
            description="Dark store becomes unserviceable; blocks checkout and demands session refresh.",
            build_contract=_build_s5_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
            inject_fault=lambda adapter, cart_id: adapter.inject_stale_cart(True),
            expected_failure_class=FailureClass.STALE_CART,
            expected_recovery_state=RecoveryState.NEEDS_USER_DECISION,
            expected_auto_applied=False,
        ),
        ScenarioDefinition(
            id="SCN-06",
            name="Safe Transient Retry",
            description="Transient 503/timeout error on provider call retries safely without item corruption.",
            build_contract=_build_s6_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
            inject_fault=lambda adapter, cart_id: adapter.inject_transient_error(1),
            expected_failure_class=FailureClass.TRANSIENT_ERROR,
            expected_recovery_state=RecoveryState.RECOVERED,
            expected_auto_applied=True,
        ),
        ScenarioDefinition(
            id="SCN-07",
            name="Partial Cart Success",
            description="Provider drops tomato SKU during mutation; verifier catches missing item.",
            build_contract=_build_s7_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
            inject_fault=lambda adapter, cart_id: adapter.inject_partial_cart_drop("SPIN-TOMATO-500G"),
            expected_failure_class=FailureClass.ITEM_UNAVAILABLE,
            expected_recovery_state=RecoveryState.NEEDS_USER_DECISION,
            expected_auto_applied=False,
        ),
        ScenarioDefinition(
            id="SCN-08",
            name="Minimum Order Threshold",
            description="Basket below store minimum order threshold; recovery proposes staple addition.",
            build_contract=_build_s8_contract,
            initial_items=[CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1)],
            inject_fault=lambda adapter, cart_id: adapter.inject_min_order_threshold(250.0),
            expected_failure_class=FailureClass.MIN_ORDER_FAILURE,
            expected_recovery_state=RecoveryState.NEEDS_USER_DECISION,
            expected_auto_applied=False,
        ),
    ]
