"""Grocer v1.0 — Intelligent Candidate Search & Grounding Engine.

Fetches candidate items from Swiggy Instamart dark stores via SwiggyClient.
Extracts variant details, filters in-stock SKUs, and normalizes into CandidateItems
with strict integer paise currency math. Zero floating point currency formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from backend.integrations.commerce.swiggy_client import SwiggyClient


class CandidateItem(BaseModel):
    """Normalized dark-store product variation candidate."""

    model_config = ConfigDict(extra="ignore")

    spin_id: str
    sku_id: str
    product_id: str
    display_name: str
    brand_name: str | None = None
    quantity_description: str
    mrp_paise: int
    offer_price_paise: int
    is_in_stock: bool
    veg_classifier: str | None = None
    max_quantity: int | None = None
    max_quantity_message: str | None = None


@dataclass
class CatalogSearch:
    """In-stock candidates plus the store's own alternative names."""

    candidates: list[CandidateItem] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


def _alternative_names(products: list[object], limit: int = 3) -> list[str]:
    names: list[str] = []
    for product in products:
        name = getattr(product, "displayName", None)
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def search_catalog_full(
    query: str,
    address_id: str | None = None,
    swiggy_client: SwiggyClient | None = None,
) -> CatalogSearch:
    """Search the live dark store and return in-stock candidates plus alternatives."""
    if swiggy_client is None:
        swiggy_client = SwiggyClient()

    search_data = swiggy_client.search_products(query=query, address_id=address_id)
    candidates: list[CandidateItem] = []

    for product in search_data.products:
        for variation in product.variations:
            if variation.isInStockAndAvailable:
                candidates.append(
                    CandidateItem(
                        spin_id=variation.spinId,
                        sku_id=variation.skuId,
                        product_id=product.productId,
                        display_name=variation.displayName,
                        brand_name=variation.brandName or product.brand,
                        quantity_description=variation.quantityDescription,
                        mrp_paise=variation.price.mrp_paise,
                        offer_price_paise=variation.price.offer_price_paise,
                        is_in_stock=True,
                        veg_classifier=variation.vegClassifier,
                        max_quantity=variation.maxQuantity,
                        max_quantity_message=variation.maxQuantityMessage,
                    )
                )

    return CatalogSearch(
        candidates=candidates[:5],
        alternatives=_alternative_names(search_data.similarProducts or []),
    )


def search_catalog(
    query: str,
    address_id: str | None = None,
    swiggy_client: SwiggyClient | None = None,
) -> list[CandidateItem]:
    """Return only the in-stock candidates (backwards-compatible wrapper)."""
    return search_catalog_full(query, address_id, swiggy_client).candidates
