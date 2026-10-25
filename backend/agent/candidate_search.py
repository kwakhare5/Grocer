"""Grocer v1.0 — Intelligent Candidate Search & Grounding Engine.

Fetches candidate items from Swiggy Instamart dark stores via SwiggyClient.
Extracts variant details, filters in-stock SKUs, and normalizes into CandidateItems
with strict integer paise currency math. Zero floating point currency formatting.
"""

from __future__ import annotations

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


def search_catalog(
    query: str,
    address_id: str | None = None,
    swiggy_client: SwiggyClient | None = None,
) -> list[CandidateItem]:
    """Search hyper-local Instamart dark store and return top in-stock candidate variations."""
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
                    )
                )

    # Return top 5 in-stock candidates
    return candidates[:5]
