"""Provider quantity-cap recovery regressions using the canonical cart outcome."""
from __future__ import annotations

from backend.integrations.commerce.models import CartItem, CommerceCart, CommerceProductItem, ProductVariant
from backend.intent.models import IntentContract, IntentItem, ResolvedMeaning
from backend.intent.recovery import FailureClass, RecoveryEngine, RecoveryState
from backend.intent.verifier import ConstraintViolation, VerificationResult, VerificationStatus, ViolationCode


def test_provider_quantity_limit_uses_uncapped_targeted_variant_with_sku() -> None:
    item = IntentItem(
        name="plain snack",
        quantity=3,
        unit="units",
        quantity_is_explicit=True,
        resolved_meaning=ResolvedMeaning(
            original_expression="3 plain snack",
            requested_quantity=3,
            requested_dimension="catalog_dependent",
            interpretation_explicit=False,
            status="PARTIALLY_FULFILLED",
            spin_id="capped-spin",
            sku_id="capped-sku",
            provider_pack_description="100 g",
            cart_quantity=3,
            expected_dimension="pack_count",
            expected_amount=3,
            actual_cart_quantity=1,
            explanation="Treating this as three retail packs.",
        ),
    )
    contract = IntentContract(session_id="cap", goal="groceries", items=[item])
    cart = CommerceCart(
        cart_id="cart",
        items=[
            CartItem(
                spin_id="capped-spin",
                sku_id="capped-sku",
                name="Plain snack",
                pack_size="100 g",
                unit_price=18,
                quantity=1,
                total_price=18,
                is_available=True,
                max_quantity=1,
            )
        ],
    )
    catalog = [
        CommerceProductItem(
            product_id="snack",
            name="Plain snack",
            category="snacks",
            variants=[
                ProductVariant(
                    spin_id="capped-spin",
                    sku_id="capped-sku",
                    name="Plain snack 100 g",
                    pack_size="100 g",
                    price=18,
                    mrp=20,
                    in_stock=True,
                    max_quantity=1,
                ),
                ProductVariant(
                    spin_id="uncapped-spin",
                    sku_id="uncapped-sku",
                    name="Plain snack 100 g alternate",
                    pack_size="100 g",
                    price=20,
                    mrp=22,
                    in_stock=True,
                ),
            ],
        )
    ]
    verification = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.WRONG_QUANTITY,
                target="plain snack",
                detail="canonical cart accepted 1 of 3",
                is_hard=True,
            )
        ],
    )

    outcome = RecoveryEngine().recover(contract, cart, verification, catalog)

    assert outcome.failure_class == FailureClass.PROVIDER_QUANTITY_LIMIT
    assert outcome.state in {RecoveryState.RECOVERED, RecoveryState.NEEDS_USER_DECISION}
    assert outcome.recovery_actions[0].spin_id == "uncapped-spin"
    assert outcome.recovery_actions[0].sku_id == "uncapped-sku"
    assert outcome.recovery_actions[0].quantity == 3
