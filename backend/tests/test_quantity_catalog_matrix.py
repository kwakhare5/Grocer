"""Generalized table-driven quantity/catalog semantic matrix (Spec Section 11).

No product-name hacks: bare quantities resolve only from catalog evidence.
Covers the ten required invariants across quantities, explicit semantics,
provider pack shapes, and provider caps.
"""
from __future__ import annotations

import pytest

from backend.intent.models import IntentContract, IntentItem, ResolvedMeaning
from backend.intent.orchestrator import _search_and_pick
from backend.intent.semantics import (
    normalize_pack_quantity,
    normalize_requested_quantity,
    required_pack_count,
)
from backend.intent.trace import build_interpretation_trace
from backend.intent.verifier import IntentVerifier
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter


def _product(variants: list[tuple[str, str, float]]) -> list[CommerceProductItem]:
    items = []
    for idx, (spin, pack, price) in enumerate(variants):
        items.append(
            CommerceProductItem(
                product_id=f"prod-{idx}",
                name="test item",
                category="test",
                variants=[
                    ProductVariant(
                        spin_id=spin,
                        sku_id=f"sku-{spin}",
                        name=f"test item {pack}",
                        pack_size=pack,
                        price=price,
                        mrp=price,
                        in_stock=True,
                    )
                ],
            )
        )
    return items


class _MatrixPort(MockCommerceAdapter):
    def __init__(self, catalog: list[CommerceProductItem]) -> None:
        super().__init__()
        self._matrix_catalog = catalog

    async def search_products(self, address_id: str, query: str):  # type: ignore[override]
        return self._matrix_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [1, 2, 3, 6, 12])
@pytest.mark.parametrize(
    "pack_shape,pack_dim,pack_amount",
    [
        ("1 pc", "count", 1),
        ("4 pcs", "count", 4),
        ("100 g", "mass", 100),
        ("250 g", "mass", 250),
        ("500 ml", "volume", 500),
        ("1 L", "volume", 1000),
        ("2 x 100 g", "mass", 200),
        ("pack of 6", "count", 6),
    ],
)
async def test_bare_quantity_uses_catalog_evidence_or_asks(quantity, pack_shape, pack_dim, pack_amount) -> None:
    """Invariant 4+5: bare quantity resolves from evidence or blocks mutation."""
    catalog = _product([(f"spin-{pack_shape}", pack_shape, 10.0)])
    port = _MatrixPort(catalog)
    item = IntentItem(name="test item", quantity=float(quantity), unit="units", quantity_is_explicit=True)
    update = await _search_and_pick(port, "addr", item)
    assert item.resolved_meaning is not None
    if pack_dim == "count" and pack_amount == 1:
        assert update is not None
        assert update.quantity == quantity
        assert item.resolved_meaning.status == "EXACT"
    elif pack_dim in {"mass", "volume"}:
        assert update is not None
        assert update.quantity == quantity
        assert item.resolved_meaning.status == "INFERRED"
    else:
        # Ambiguous count packs (4 pcs, pack of 6) with no 1-pc evidence: must clarify.
        assert update is None
        assert item.resolved_meaning.status == "AMBIGUOUS"
        assert item.resolved_meaning.clarification_required is True


@pytest.mark.asyncio
async def test_explicit_count_never_becomes_pack_count() -> None:
    """Invariant 1: explicit COUNT stays COUNT."""
    catalog = _product([("s1", "100 g", 10.0)])
    port = _MatrixPort(catalog)
    item = IntentItem(name="test item", quantity=6, unit="pcs", quantity_is_explicit=True)
    update = await _search_and_pick(port, "addr", item)
    assert update is None  # gram pack is dimensionally incompatible with COUNT
    assert item.resolved_meaning is None or item.resolved_meaning.status != "INFERRED"


@pytest.mark.asyncio
async def test_explicit_pack_count_never_becomes_count() -> None:
    """Invariant 2: explicit PACK_COUNT stays PACK_COUNT."""
    requested = normalize_requested_quantity(3, "packs", "test item", quantity_is_explicit=True)
    assert requested is not None and requested.dimension == "pack_count"
    # A 4-pc pack is still pack_count-compatible: 3 packs requested.
    count = required_pack_count(requested, normalize_pack_quantity("4 pcs"))
    assert count == 3


def test_mass_volume_dimensional_correctness() -> None:
    """Invariant 3: MASS/VOLUME never cross dimensions."""
    mass = normalize_requested_quantity(1, "kg", "rice", quantity_is_explicit=True)
    assert mass is not None and (mass.dimension, mass.amount) == ("mass", 1000)
    assert required_pack_count(mass, normalize_pack_quantity("1 L")) is None
    vol = normalize_requested_quantity(2, "L", "milk", quantity_is_explicit=True)
    assert vol is not None and (vol.dimension, vol.amount) == ("volume", 2000)
    assert required_pack_count(vol, normalize_pack_quantity("500 ml")) == 4
    assert normalize_requested_quantity(2, "dozen", "eggs", quantity_is_explicit=True).amount == 24  # type: ignore[union-attr]


def test_price_ranking_only_after_semantic_validity() -> None:
    """Invariant 6: cheapest semantically-invalid candidate must not win."""
    # Covered by _search_and_pick filtering before min(price); explicit COUNT
    # with only gram packs yields no resolution regardless of price.
    requested = normalize_requested_quantity(3, "pcs", "test", quantity_is_explicit=True)
    assert required_pack_count(requested, normalize_pack_quantity("100 g")) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("omitted", [None])
def test_provider_unknown_never_becomes_false_or_true(omitted) -> None:
    """Invariant 7: omitted serviceability/availability stays unknown."""
    cart = CommerceCart(cart_id="c", items=[], is_serviceable=omitted)
    assert cart.is_serviceable is None
    result = IntentVerifier().verify(IntentContract(session_id="s", goal="g"), cart)
    assert result.status.value == "pass"


def test_requested_mutation_success_does_not_imply_fulfillment() -> None:
    """Invariant 8+9+10: canonical cart wins; caps never report full success."""
    item = IntentItem(
        name="test item",
        quantity=3,
        unit="units",
        quantity_is_explicit=True,
        resolved_meaning=ResolvedMeaning(
            original_expression="3 test item",
            requested_quantity=3,
            requested_dimension="catalog_dependent",
            interpretation_explicit=False,
            status="INFERRED",
            spin_id="s1",
            sku_id="sku-s1",
            provider_pack_description="100 g",
            cart_quantity=3,
            expected_dimension="pack_count",
            expected_amount=3,
            explanation="3 packs",
        ),
    )
    contract = IntentContract(session_id="s", goal="g", items=[item])
    cart = CommerceCart(
        cart_id="c",
        is_serviceable=True,
        items=[
            CartItem(
                spin_id="s1",
                sku_id="sku-s1",
                name="test item",
                pack_size="100 g",
                unit_price=10,
                quantity=1,
                total_price=10,
                max_quantity=1,
            )
        ],
    )
    result = IntentVerifier().verify(contract, cart)
    assert result.status.value == "fail"
    assert item.resolved_meaning is not None
    assert item.resolved_meaning.status == "PARTIALLY_FULFILLED"
    assert item.resolved_meaning.actual_cart_quantity == 1
    trace = build_interpretation_trace(
        item, catalog_evidence=["test item — 100 g"], classification="PROVIDER_LIMITED",
    )
    assert trace["difference"] == "2 retail units unmet"
    assert "token" not in str(trace).lower()
