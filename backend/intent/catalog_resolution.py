"""Resolve a desired basket against live catalogue facts without mutating a cart."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from backend.integrations.commerce.models import CommerceProductItem, ProductVariant
from backend.integrations.commerce.port import CommercePort
from backend.intent.semantics import (
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
)
from backend.intent.task_model import DesiredBasketItem


class CatalogResolutionKind(StrEnum):
    EXACT = "EXACT"
    AMBIGUOUS = "AMBIGUOUS"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CatalogCandidate:
    spin_id: str
    sku_id: str | None
    name: str
    pack_size: str
    price: float


@dataclass(frozen=True)
class CatalogResolution:
    requested_item: DesiredBasketItem
    kind: CatalogResolutionKind
    selected: CatalogCandidate | None = None
    candidates: tuple[CatalogCandidate, ...] = ()


class CatalogResolver:
    """Conservative, catalogue-grounded resolver for human grocery language.

    A result is exact only when live catalogue facts leave one compliant variant.
    Two plausible pack sizes are a user decision, not a ranking problem.
    """

    def __init__(self, port: CommercePort) -> None:
        self._port = port

    async def resolve_basket(
        self, address_id: str, items: list[DesiredBasketItem]
    ) -> list[CatalogResolution]:
        return list(
            await asyncio.gather(*(self.resolve_item(address_id, item) for item in items))
        )

    async def resolve_item(
        self, address_id: str, item: DesiredBasketItem
    ) -> CatalogResolution:
        products = await self._port.search_products(address_id, item.name)
        candidates = self._matching_candidates(products, item)
        if not candidates:
            return CatalogResolution(item, CatalogResolutionKind.UNAVAILABLE)

        exact_candidates = self._exact_quantity_candidates(candidates, item)
        if len(exact_candidates) == 1:
            return CatalogResolution(
                item, CatalogResolutionKind.EXACT, selected=exact_candidates[0]
            )

        # No stated physical amount means a single provider variation is safe;
        # multiple variations need a human choice rather than an inferred pack.
        if item.unit == "units" and len(candidates) == 1:
            return CatalogResolution(item, CatalogResolutionKind.EXACT, selected=candidates[0])

        options = exact_candidates or candidates
        return CatalogResolution(
            item, CatalogResolutionKind.AMBIGUOUS, candidates=tuple(options[:10])
        )

    def _matching_candidates(
        self, products: list[CommerceProductItem], item: DesiredBasketItem
    ) -> list[CatalogCandidate]:
        candidates: list[CatalogCandidate] = []
        for product in products:
            for variant in product.variants:
                if variant.in_stock is False:
                    continue
                if not (
                    product_identity_matches(item.name, product.name, candidate_category=product.category)
                    or product_identity_matches(item.name, variant.name, candidate_category=product.category)
                ):
                    continue
                if item.brand and item.brand.casefold() not in (
                    f"{product.brand or ''} {product.name} {variant.name}".casefold()
                ):
                    continue
                candidates.append(
                    CatalogCandidate(
                        spin_id=variant.spin_id,
                        sku_id=variant.sku_id,
                        name=variant.name,
                        pack_size=variant.pack_size,
                        price=variant.price,
                    )
                )
        return candidates

    def _exact_quantity_candidates(
        self, candidates: list[CatalogCandidate], item: DesiredBasketItem
    ) -> list[CatalogCandidate]:
        requested = normalize_requested_quantity(
            item.quantity,
            item.unit,
            item.name,
            quantity_is_explicit=item.quantity_is_explicit,
        )
        if requested is None or requested.dimension in {"catalog_dependent", "pack_count", "count"}:
            return []

        exact: list[CatalogCandidate] = []
        for candidate in candidates:
            pack = normalize_pack_quantity(candidate.pack_size)
            if pack is None or pack.dimension != requested.dimension:
                continue
            if abs(pack.amount - requested.amount) < 0.001:
                exact.append(candidate)
        return exact
