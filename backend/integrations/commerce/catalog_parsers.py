"""Swiggy Instamart product catalog parser."""
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

            price_obj = v.get("price")
            if isinstance(price_obj, dict):
                if "offerPrice" not in price_obj and "mrp" not in price_obj:
                    continue
                offer_price = float(price_obj.get("offerPrice", price_obj.get("mrp", 0.0)))
                mrp = float(price_obj.get("mrp", offer_price))
            else:
                raw_price = v.get("price", v.get("offerPrice", v.get("mrp", 0.0)))
                offer_price = float(raw_price) if raw_price is not None else 0.0
                mrp = float(v.get("mrp", offer_price))

            inventory = v.get("inventory", {})
            if isinstance(inventory, dict):
                is_available = _optional_provider_bool(
                    inventory.get("inStock", inventory.get("isInStock"))
                )
                max_allowed = inventory.get("maxAllowedQuantity")
            else:
                is_available = _optional_provider_bool(v.get("inStock", v.get("isInStock")))
                max_allowed = v.get("maxAllowedQuantity")

            meta = v.get("meta", {})
            if not isinstance(meta, dict):
                meta = {}
            veg_val = meta.get("isVeg", meta.get("veg"))
            is_veg = _optional_provider_bool(veg_val)

            variants.append(
                ProductVariant(
                    spin_id=str(spin_id),
                    sku_id=str(sku_id) if sku_id else None,
                    name=str(var_name),
                    pack_size=str(pack_size),
                    price=offer_price,
                    mrp=mrp,
                    in_stock=is_available,
                    is_available=is_available,
                    is_veg=is_veg,
                    max_quantity=(int(max_allowed) if max_allowed is not None else None),
                )
            )

        if not variants:
            continue

        products.append(
            CommerceProductItem(
                product_id=product_id,
                name=display_name,
                brand=str(brand) if brand else None,
                category=category,
                variants=variants,
            )
        )

    return products


__all__ = ["_optional_provider_bool", "parse_swiggy_products"]
