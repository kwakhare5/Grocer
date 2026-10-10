"""Swiggy Instamart product catalog and search response parsers."""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.models import (
    CommerceProductItem,
    ProductVariant,
)


def _optional_provider_bool(value: Any) -> Optional[bool]:
    """Preserve True/False when returned by provider, return None when omitted."""
    return value if isinstance(value, bool) else None


def parse_swiggy_products(raw_items: Any) -> list[CommerceProductItem]:
    """Parse official SearchProduct and variation schemas."""
    products: list[CommerceProductItem] = []
    if not isinstance(raw_items, list):
        return products

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        product_id = item.get("productId") or item.get("id")
        display_name = item.get("displayName") or item.get("name")
        if not product_id or not display_name:
            continue
        product_id = str(product_id)
        display_name = str(display_name)
        brand = item.get("brand") or item.get("brandName")
        category = str(item.get("category") or "")

        raw_variations = item.get("variations") or item.get("variants") or []
        variants: list[ProductVariant] = []

        for v in raw_variations:
            if not isinstance(v, dict):
                continue
            spin_id = v.get("spinId") or v.get("spin_id")
            if not spin_id:
                continue
            sku_id = v.get("skuId") or v.get("sku_id")
            var_name = v.get("displayName") or v.get("name") or display_name
            pack_size = (
                v.get("quantityDescription")
                or v.get("packSize")
                or v.get("pack_size")
                or ""
            )

            # Official price structure is { mrp: number, offerPrice: number }
            price_obj = v.get("price")
            if isinstance(price_obj, dict):
                if "offerPrice" not in price_obj and "mrp" not in price_obj:
                    continue
                offer_price = float(price_obj.get("offerPrice", price_obj.get("mrp", 0.0)))
                mrp = float(price_obj.get("mrp", offer_price))
            else:
                if "price" not in v:
                    continue
                offer_price = float(v.get("price", 0.0))
                mrp = float(v.get("mrp", offer_price))

            stock_value = v.get(
                "isInStockAndAvailable", v.get("inStock", item.get("inStock"))
            )
            in_stock = _optional_provider_bool(stock_value)
            image_url = v.get("imageUrl") or item.get("imageUrl")

            variants.append(
                ProductVariant(
                    spin_id=spin_id,
                    sku_id=sku_id,
                    name=var_name,
                    pack_size=pack_size,
                    price=offer_price,
                    offer_price=offer_price,
                    mrp=mrp,
                    in_stock=in_stock,
                    image_url=image_url,
                    max_quantity=v.get("maxQuantity"),
                    max_quantity_message=v.get("maxQuantityMessage"),
                )
            )

        if not variants:
            continue
        products.append(
            CommerceProductItem(
                product_id=product_id,
                name=display_name,
                category=category,
                brand=brand,
                variants=variants,
                image_url=item.get("imageUrl"),
            )
        )
    return products
