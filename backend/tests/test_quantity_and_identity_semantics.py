"""Adversarial quantity and product-identity invariants for GROCER."""

from __future__ import annotations

import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CommerceCart
from backend.intent.models import IntentContract, IntentItem
from backend.intent.orchestrator import _search_and_pick
from backend.intent.semantics import (
    NormalizedQuantity,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
from backend.intent.verifier import IntentVerifier, ViolationCode


@pytest.mark.parametrize(
    ("quantity", "unit", "product", "expected"),
    [
        (1, "L", "milk", NormalizedQuantity("volume", 1000)),
        (1.5, "L", "milk", NormalizedQuantity("volume", 1500)),
        (2, "kg", "rice", NormalizedQuantity("mass", 2000)),
        (750, "g", "paneer", NormalizedQuantity("mass", 750)),
        (2, "dozen", "eggs", NormalizedQuantity("count", 24)),
        (12, "units", "eggs", NormalizedQuantity("count", 12)),
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
async def test_selection_converts_requested_egg_count_to_pack_count() -> None:
    adapter = MockCommerceAdapter()
    adapter.inject_out_of_stock("SPIN-EGGS-12")
    update = await _search_and_pick(
        adapter,
        "addr-bandra-1",
        IntentItem(name="eggs", quantity=12, unit="units", quantity_is_explicit=True),
    )

    assert update is not None
    assert update.spin_id == "SPIN-EGGS-6"
    assert update.quantity == 2


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
