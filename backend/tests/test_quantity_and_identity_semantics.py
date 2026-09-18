"""Adversarial quantity and product-identity invariants for GROCER."""

from __future__ import annotations

import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.intent.models import IntentContract, IntentItem
from backend.intent.models import ResolvedMeaning
from backend.intent.orchestrator import _search_and_pick, _targeted_recovery_query
from backend.intent.recovery import RecoveryEngine, RecoveryState
from backend.intent.semantics import (
    NormalizedQuantity,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
from backend.intent.verifier import (
    ConstraintViolation,
    IntentVerifier,
    VerificationResult,
    VerificationStatus,
    ViolationCode,
)


@pytest.mark.parametrize(
    ("quantity", "unit", "product", "expected"),
    [
        (1, "L", "milk", NormalizedQuantity("volume", 1000)),
        (1.5, "L", "milk", NormalizedQuantity("volume", 1500)),
        (2, "kg", "rice", NormalizedQuantity("mass", 2000)),
        (750, "g", "paneer", NormalizedQuantity("mass", 750)),
        (2, "dozen", "eggs", NormalizedQuantity("count", 24)),
        (12, "units", "eggs", NormalizedQuantity("catalog_dependent", 12)),
        (6, "pieces", "apples", NormalizedQuantity("count", 6)),
        (4, "units", "bananas", NormalizedQuantity("catalog_dependent", 4)),
        (3, "packs", "biscuits", NormalizedQuantity("pack_count", 3)),
    ],
)
def test_requested_quantity_normalizes_to_base_dimension(
    quantity: float,
    unit: str,
    product: str,
    expected: NormalizedQuantity,
) -> None:
    assert normalize_requested_quantity(quantity, unit, product) == expected


@pytest.mark.parametrize(
    ("pack", "expected"),
    [
        ("500 ml", NormalizedQuantity("volume", 500)),
        ("1.5 L", NormalizedQuantity("volume", 1500)),
        ("2 x 500 ml", NormalizedQuantity("volume", 1000)),
        ("250g", NormalizedQuantity("mass", 250)),
        ("6 pcs", NormalizedQuantity("count", 6)),
        ("pack of 12 eggs", NormalizedQuantity("count", 12)),
    ],
)
def test_provider_pack_size_normalizes_without_special_cases(
    pack: str, expected: NormalizedQuantity
) -> None:
    assert normalize_pack_quantity(pack) == expected


def test_required_pack_count_rejects_underfill_and_unapproved_overfill() -> None:
    requested = NormalizedQuantity("volume", 1000)

    assert required_pack_count(requested, NormalizedQuantity("volume", 500)) == 2
    assert required_pack_count(requested, NormalizedQuantity("volume", 750)) is None
    assert required_pack_count(requested, NormalizedQuantity("mass", 500)) is None


@pytest.mark.parametrize(
    ("requested", "provider_pack", "expected"),
    [
        (NormalizedQuantity("count", 6), NormalizedQuantity("count", 6), 1),
        (NormalizedQuantity("count", 6), NormalizedQuantity("count", 1), 6),
        (NormalizedQuantity("pack_count", 3), NormalizedQuantity("count", 6), 3),
        (NormalizedQuantity("count", 4), NormalizedQuantity("count", 3), None),
    ],
)
def test_individual_and_pack_counts_convert_without_silent_quantity_drift(
    requested: NormalizedQuantity,
    provider_pack: NormalizedQuantity,
    expected: int | None,
) -> None:
    assert required_pack_count(requested, provider_pack) == expected


class _CatalogSearchPort:
    def __init__(self, pack_size: str, product_name: str = "Fresh Bananas") -> None:
        self._results = [
            CommerceProductItem(
                product_id="product",
                name=product_name,
                category="produce",
                variants=[
                    ProductVariant(
                        spin_id="spin-product",
                        name=product_name,
                        pack_size=pack_size,
                        price=30,
                        mrp=30,
                    )
                ],
            )
        ]

    async def search_products(
        self, address_id: str, query: str
    ) -> list[CommerceProductItem]:
        return self._results


class _MultiVariantCatalogSearchPort:
    def __init__(self, pack_sizes: list[str], product_name: str) -> None:
        self._results = [
            CommerceProductItem(
                product_id="product",
                name=product_name,
                category="generic",
                variants=[
                    ProductVariant(
                        spin_id=f"spin-{index}",
                        sku_id=f"sku-{index}",
                        name=f"{product_name} {pack_size}",
                        pack_size=pack_size,
                        price=float(index + 1),
                        mrp=float(index + 1),
                        in_stock=True,
                    )
                    for index, pack_size in enumerate(pack_sizes)
                ],
            )
        ]

    async def search_products(
        self, address_id: str, query: str
    ) -> list[CommerceProductItem]:
        return self._results


@pytest.mark.asyncio
async def test_bare_quantity_infers_retail_sku_units_from_mass_catalog_evidence() -> None:
    item = IntentItem(name="plain snack", quantity=3, unit="units", quantity_is_explicit=True)

    update = await _search_and_pick(
        _MultiVariantCatalogSearchPort(["100 g", "250 g"], "Plain snack"),  # type: ignore[arg-type]
        "address",
        item,
    )

    assert update is not None
    assert update.quantity == 3
    assert item.resolved_meaning is not None
    assert item.resolved_meaning.status == "INFERRED"
    assert item.resolved_meaning.provider_pack_description == "100 g"


@pytest.mark.asyncio
async def test_bare_quantity_uses_individual_sku_when_catalog_offers_one() -> None:
    item = IntentItem(name="generic produce", quantity=3, unit="units", quantity_is_explicit=True)

    update = await _search_and_pick(
        _MultiVariantCatalogSearchPort(["1 pc", "4 pcs"], "Generic produce"),  # type: ignore[arg-type]
        "address",
        item,
    )

    assert update is not None
    assert update.spin_id == "spin-0"
    assert update.quantity == 3
    assert item.resolved_meaning is not None
    assert item.resolved_meaning.status == "EXACT"


@pytest.mark.asyncio
async def test_bare_quantity_requires_clarification_for_count_pack_only_catalog() -> None:
    item = IntentItem(name="generic produce", quantity=3, unit="units", quantity_is_explicit=True)

    update = await _search_and_pick(
        _MultiVariantCatalogSearchPort(["4 pcs", "6 pcs"], "Generic produce"),  # type: ignore[arg-type]
        "address",
        item,
    )

    assert update is None
    assert item.resolved_meaning is not None
    assert item.resolved_meaning.status == "AMBIGUOUS"
    assert item.resolved_meaning.clarification_required is True


def test_verifier_uses_resolved_meaning_and_canonical_cart_quantity() -> None:
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
            status="INFERRED",
            spin_id="spin-snack",
            provider_pack_description="100 g",
            cart_quantity=3,
            expected_dimension="pack_count",
            expected_amount=3,
            explanation="Treating this as three retail packs.",
        ),
    )
    contract = IntentContract(session_id="resolved-meaning", goal="groceries", items=[item])
    cart = CommerceCart(
        cart_id="cart",
        is_serviceable=True,
        items=[
            CartItem(
                spin_id="spin-snack",
                name="Plain snack",
                pack_size="100 g",
                unit_price=18,
                quantity=1,
                total_price=18,
                is_available=True,
            )
        ],
    )

    result = IntentVerifier().verify(contract, cart)

    assert result.status == VerificationStatus.FAIL
    assert item.resolved_meaning is not None
    assert item.resolved_meaning.actual_cart_quantity == 1
    assert item.resolved_meaning.status == "PARTIALLY_FULFILLED"


def test_targeted_recovery_query_uses_the_failed_intent_item() -> None:
    contract = IntentContract(
        session_id="targeted-query",
        goal="groceries",
        items=[IntentItem(name="plain snack"), IntentItem(name="shampoo")],
    )
    verification = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.WRONG_QUANTITY,
                target="shampoo",
                detail="canonical cart shortfall",
                is_hard=True,
            )
        ],
    )

    assert _targeted_recovery_query(contract, verification) == "shampoo"


@pytest.mark.parametrize(
    ("item", "provider_pack", "provider_name", "expected_quantity"),
    [
        (
            IntentItem(
                name="bananas",
                quantity=6,
                unit="pieces",
                quantity_is_explicit=True,
                category="produce",
            ),
            "6 pieces",
            "Fresh Bananas",
            1,
        ),
        (
            IntentItem(
                name="bananas",
                quantity=6,
                unit="units",
                quantity_is_explicit=True,
                category="produce",
            ),
            "1 piece",
            "Fresh Bananas",
            6,
        ),
        (
            IntentItem(
                name="biscuits",
                quantity=3,
                unit="packs",
                quantity_is_explicit=True,
                category="produce",
            ),
            "6 pieces",
            "Tea Biscuits",
            3,
        ),
    ],
)
@pytest.mark.asyncio
async def test_selection_distinguishes_individual_counts_from_pack_counts(
    item: IntentItem,
    provider_pack: str,
    provider_name: str,
    expected_quantity: int,
) -> None:
    update = await _search_and_pick(
        _CatalogSearchPort(provider_pack, provider_name),  # type: ignore[arg-type]
        "address",
        item,
    )

    assert update is not None
    assert update.quantity == expected_quantity


@pytest.mark.asyncio
async def test_selection_rejects_non_divisible_individual_count() -> None:
    update = await _search_and_pick(
        _CatalogSearchPort("3 pieces"),  # type: ignore[arg-type]
        "address",
        IntentItem(
            name="bananas",
            quantity=4,
            unit="units",
            quantity_is_explicit=True,
            category="produce",
        ),
    )

    assert update is None


@pytest.mark.parametrize(
    ("requested", "candidate", "matches"),
    [
        ("milk", "Amul Taaza Fresh Toned Milk", True),
        ("milk", "Amul Milk Powder", False),
        ("milk", "Chocolate Milkshake", False),
        ("rice", "India Gate Basmati Rice", True),
        ("rice", "Organic Rice Flour", False),
        ("bread", "Whole Wheat Bread", True),
        ("bread", "Bread Crumbs", False),
        ("butter", "Salted Dairy Butter", True),
        ("butter", "Crunchy Peanut Butter", False),
    ],
)
def test_product_identity_uses_tokens_and_derivative_exclusions(
    requested: str, candidate: str, matches: bool
) -> None:
    assert product_identity_matches(requested, candidate) is matches


@pytest.mark.asyncio
async def test_selection_preserves_explicit_physical_quantity_before_price() -> None:
    adapter = MockCommerceAdapter()
    update = await _search_and_pick(
        adapter,
        "addr-bandra-1",
        IntentItem(name="milk", quantity=1.5, unit="L", quantity_is_explicit=True),
    )

    assert update is not None
    assert update.spin_id == "SPIN-MILK-500ML"
    assert update.quantity == 3


@pytest.mark.asyncio
async def test_selection_uses_cheapest_semantically_complete_option() -> None:
    adapter = MockCommerceAdapter()
    update = await _search_and_pick(
        adapter,
        "addr-bandra-1",
        IntentItem(name="milk", quantity=2, unit="L", quantity_is_explicit=True),
    )

    assert update is not None
    assert update.spin_id == "SPIN-MILK-1L"
    assert update.quantity == 2


@pytest.mark.asyncio
async def test_selection_requires_clarification_for_bare_count_pack_only_eggs() -> None:
    adapter = MockCommerceAdapter()
    adapter.inject_out_of_stock("SPIN-EGGS-12")
    update = await _search_and_pick(
        adapter,
        "addr-bandra-1",
        IntentItem(name="eggs", quantity=12, unit="units", quantity_is_explicit=True),
    )

    assert update is None


@pytest.mark.asyncio
async def test_selection_never_silently_replaces_explicit_brand() -> None:
    adapter = MockCommerceAdapter()
    update = await _search_and_pick(
        adapter,
        "addr-bandra-1",
        IntentItem(
            name="milk",
            quantity=1,
            unit="L",
            brand_preference="Mother Dairy",
            quantity_is_explicit=True,
        ),
    )

    assert update is None


@pytest.mark.parametrize("cart_name", ["Amul Milk Powder", "Chocolate Milkshake"])
def test_verifier_rejects_wrong_product_identity(cart_name: str) -> None:
    contract = IntentContract(
        session_id="identity-test",
        goal="buy milk",
        items=[IntentItem(name="milk", quantity=1, unit="L", quantity_is_explicit=True)],
    )
    cart = CommerceCart(
        cart_id="cart",
        items=[
            CartItem(
                spin_id="wrong",
                name=cart_name,
                pack_size="1 L",
                unit_price=50,
                quantity=1,
                total_price=50,
            )
        ],
        item_total=50,
        grand_total=50,
    )

    result = IntentVerifier().verify(contract, cart)

    assert ViolationCode.MISSING_ITEM in result.violation_codes


def test_verifier_checks_total_physical_quantity_without_exact_constraint() -> None:
    contract = IntentContract(
        session_id="quantity-test",
        goal="buy milk",
        items=[IntentItem(name="milk", quantity=1, unit="L", quantity_is_explicit=True)],
    )
    cart = CommerceCart(
        cart_id="cart",
        items=[
            CartItem(
                spin_id="underfill",
                name="Amul Fresh Milk",
                pack_size="500 ml",
                unit_price=34,
                quantity=1,
                total_price=34,
            )
        ],
        item_total=34,
        grand_total=34,
    )

    result = IntentVerifier().verify(contract, cart)

    assert ViolationCode.WRONG_QUANTITY in result.violation_codes


def test_verifier_rejects_non_divisible_individual_count() -> None:
    contract = IntentContract(
        session_id="count-verifier-test",
        goal="buy four bananas",
        items=[
            IntentItem(
                name="bananas",
                quantity=4,
                unit="units",
                quantity_is_explicit=True,
                category="produce",
            )
        ],
    )
    cart = CommerceCart(
        cart_id="cart",
        items=[
            CartItem(
                spin_id="spin-bananas",
                name="Fresh Bananas",
                pack_size="3 pieces",
                unit_price=30,
                quantity=1,
                total_price=30,
                category="produce",
            )
        ],
        item_total=30,
        grand_total=30,
    )

    result = IntentVerifier().verify(contract, cart)

    assert ViolationCode.WRONG_QUANTITY in result.violation_codes


def test_recovery_blocks_non_divisible_individual_count() -> None:
    contract = IntentContract(
        session_id="count-recovery-test",
        goal="buy four bananas",
        items=[
            IntentItem(
                name="bananas",
                quantity=4,
                unit="units",
                quantity_is_explicit=True,
                category="produce",
            )
        ],
    )
    cart = CommerceCart(cart_id="cart")
    verification = VerificationResult(
        status=VerificationStatus.FAIL,
        violations=[
            ConstraintViolation(
                violation_code=ViolationCode.WRONG_QUANTITY,
                target="bananas",
                detail="Four bananas cannot be filled exactly",
            )
        ],
        unresolved_items=["bananas"],
    )
    catalog = [
        CommerceProductItem(
            product_id="product-bananas",
            name="Fresh Bananas",
            category="produce",
            variants=[
                ProductVariant(
                    spin_id="spin-bananas",
                    name="Fresh Bananas",
                    pack_size="3 pieces",
                    price=30,
                    mrp=30,
                )
            ],
        )
    ]

    outcome = RecoveryEngine().recover(contract, cart, verification, catalog)

    assert outcome.state == RecoveryState.BLOCKED
    assert outcome.recovery_actions == []
