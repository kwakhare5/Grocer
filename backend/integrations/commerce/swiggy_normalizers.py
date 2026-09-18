"""Payload parsers and status normalizers for Swiggy Instamart MCP API responses."""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    OrderChildResult,
    OrderLineItem,
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


def build_commerce_cart(data: dict[str, Any], cart_id: Optional[str] = None) -> CommerceCart:
    """Construct CommerceCart domain model from Swiggy InstamartCart schema."""
    raw_items = data.get("items", [])
    cart_items: list[CartItem] = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        spin_id = raw.get("spinId") or raw.get("spin_id")
        sku_id = raw.get("skuId") or raw.get("sku_id")
        name = raw.get("itemName") or raw.get("name")
        if not spin_id or not name or "quantity" not in raw:
            continue
        if "discountedFinalPrice" not in raw and "price" not in raw:
            continue
        pack_size = raw.get("itemVariant") or raw.get("packSize") or ""
        unit_price = float(raw.get("discountedFinalPrice", raw.get("price", 0.0)))
        mrp = float(raw.get("mrp", unit_price))
        quantity = int(raw["quantity"])
        total_price = unit_price * quantity
        stock_value = raw.get("isInStockAndAvailable")
        is_available = _optional_provider_bool(stock_value)

        cart_items.append(
            CartItem(
                spin_id=spin_id,
                sku_id=sku_id,
                product_id=raw.get("productId"),
                category=raw.get("category"),
                brand=raw.get("brand") or raw.get("brandName"),
                name=name,
                pack_size=pack_size,
                unit_price=unit_price,
                mrp=mrp,
                quantity=quantity,
                total_price=total_price,
                is_available=is_available,
                max_quantity=raw.get("maxQuantity"),
                max_quantity_message=raw.get("maxQuantityMessage"),
            )
        )

    # Parse bill breakdown
    bill_breakdown = data.get("billBreakdown", {})
    line_items = bill_breakdown.get("lineItems", [])
    item_total = 0.0
    delivery_fee = 0.0
    packaging_fee = 0.0
    discount = 0.0

    for line in line_items:
        label = line.get("label", "").lower()
        val_str = str(line.get("value", "0")).replace("₹", "").replace(",", "").strip()
        try:
            val = float(val_str)
        except ValueError:
            val = 0.0

        if "item" in label:
            item_total = val
        elif "delivery" in label:
            delivery_fee = val
        elif "packaging" in label:
            packaging_fee = val
        elif "discount" in label:
            discount = abs(val)

    # Fallback to direct bill or subtotal if lineItems was absent
    if item_total == 0.0:
        legacy_bill = data.get("bill", {})
        item_total = float(legacy_bill.get("itemTotal", data.get("subtotal", sum(ci.total_price for ci in cart_items))))
        delivery_fee = float(legacy_bill.get("deliveryFee", data.get("deliveryFee", 0.0)))
        packaging_fee = float(legacy_bill.get("packagingFee", data.get("packagingFee", 0.0)))
        discount = float(legacy_bill.get("discount", 0.0))

    grand_total = 0.0
    to_pay = bill_breakdown.get("toPay", {})
    if to_pay and "value" in to_pay:
        try:
            grand_total = float(str(to_pay["value"]).replace("₹", "").replace(",", "").strip())
        except ValueError:
            grand_total = 0.0

    if grand_total == 0.0:
        tot_str = str(data.get("cartTotalAmount", data.get("total", "0"))).replace("₹", "").replace(",", "").strip()
        try:
            grand_total = float(tot_str)
        except ValueError:
            grand_total = item_total + delivery_fee + packaging_fee - discount

    is_serviceable = _optional_provider_bool(data.get("serviceable"))
    if data.get("addressWarning") or data.get("unserviceableItems"):
        is_serviceable = False

    return CommerceCart(
        cart_id=str(data["cartId"]) if data.get("cartId") is not None else None,
        address_id=data.get("selectedAddress"),
        items=cart_items,
        item_total=item_total,
        delivery_fee=delivery_fee,
        packaging_fee=packaging_fee,
        discount=discount,
        grand_total=grand_total,
        is_serviceable=is_serviceable,
        min_order_threshold=(
            float(data["minimumOrderAmount"])
            if data.get("minimumOrderAmount") is not None
            else 0.0
        ),
        cart_absent=_optional_provider_bool(data.get("cartAbsent")),
        reduced_quantity_items=(
            [item for item in data.get("reducedQuantityItems", []) if isinstance(item, dict)]
            if isinstance(data.get("reducedQuantityItems", []), list)
            else []
        ),
        address_warning=data.get("addressWarning"),
        available_payment_methods=data.get("availablePaymentMethods", []),
    )


def normalize_payment_status(raw_status: Any) -> str:
    """Normalize Swiggy payment status string into canonical states."""
    status = str(raw_status or "").strip().upper()
    if status in {"FAILED", "FAILURE", "CANCELLED", "CANCELED", "EXPIRED", "REFUNDED", "REFUND_INITIATED", "UNSUCCESSFUL", "UNPAID"}:
        return "PAYMENT_FAILED"
    if status in {"SUCCESS", "PAID", "COMPLETED", "CAPTURED"}:
        return "PAYMENT_CONFIRMED"
    if status in {"PENDING", "PROCESSING", "INITIATED", "PENDING_PAYMENT"}:
        return "PAYMENT_PENDING"
    return "PAYMENT_UNKNOWN"


def normalize_order_status(
    raw_status: Optional[str],
    *,
    order_count: int,
    success_count: int,
    failure_count: int,
    all_succeeded: bool,
) -> str:
    """Normalize order status according to line counts and outcomes."""
    status = (raw_status or "").strip().upper()
    if status in {"PENDING_PAYMENT", "PAYMENT_PENDING"}:
        return "PAYMENT_PENDING"
    if (failure_count > 0 and success_count > 0) or status in {
        "PARTIAL",
        "PARTIAL_ORDER",
        "PARTIALLY_PLACED",
    }:
        return "PARTIAL_ORDER"
    if (
        (failure_count > 0 and success_count == 0)
        or status in {"FAILED", "FAILURE", "UNSUCCESSFUL", "CANCELLED", "CANCELED", "EXPIRED"}
    ):
        return "FAILED"
    if status in {
        "CONFIRMED",
        "ORDER_PLACED",
        "PLACED",
        "SUCCESS",
        "SUCCEEDED",
        "COMPLETED",
        "PAYMENT_CONFIRMED",
    }:
        return "ORDER_PLACED"
    if order_count > 0 and all_succeeded and success_count == order_count:
        return "ORDER_PLACED"
    return "ORDER_STATE_UNKNOWN"


def parse_child_order(raw: dict[str, Any]) -> OrderChildResult:
    """Parse single child order payload in multi-order or split-order baskets."""
    raw_status_value = raw.get("status")
    raw_status = str(raw_status_value).upper() if raw_status_value is not None else None
    explicit_success = raw.get("success")
    success = explicit_success if isinstance(explicit_success, bool) else None
    raw_error = raw.get("error")
    if isinstance(raw_error, dict):
        child_error = raw_error.get("message") or raw_error.get("code")
    else:
        child_error = raw_error
    normalized = normalize_order_status(
        raw_status,
        order_count=1,
        success_count=1 if success is True else 0,
        failure_count=1 if success is False else 0,
        all_succeeded=success is True,
    )
    if child_error is not None and normalized == "ORDER_STATE_UNKNOWN":
        normalized = "FAILED"
    if success is None:
        if normalized == "ORDER_PLACED":
            success = True
        elif normalized == "FAILED":
            success = False
    return OrderChildResult(
        order_id=str(raw["orderId"]) if raw.get("orderId") else None,
        status=normalized,
        raw_status=raw_status,
        success=success,
        grand_total=float(raw["orderTotal"]) if raw.get("orderTotal") is not None else None,
        error=str(child_error) if child_error is not None else None,
    )


def parse_order_items(raw_items: Any) -> list[OrderLineItem]:
    """Parse list of items inside an existing order."""
    items: list[OrderLineItem] = []
    if not isinstance(raw_items, list):
        return items
    for raw in raw_items:
        if not isinstance(raw, dict) or not raw.get("name") or "quantity" not in raw:
            continue
        items.append(
            OrderLineItem(
                name=str(raw["name"]),
                quantity=int(raw["quantity"]),
                item_id=(str(raw["itemId"]) if raw.get("itemId") is not None else None),
                final_price=(
                    float(raw["finalPrice"])
                    if raw.get("finalPrice") is not None
                    else None
                ),
                removed=(bool(raw["removed"]) if "removed" in raw else None),
            )
        )
    return items


def normalize_existing_order_status(raw_status: Any) -> str:
    """Normalize tracked order lifecycle status."""
    status = str(raw_status or "").upper()
    if "CANCEL" in status:
        return "CANCELLED"
    if any(token in status for token in ("OUT_FOR_DELIVERY", "DISPATCH")):
        return "OUT_FOR_DELIVERY"
    if status == "DELIVERED":
        return "DELIVERED"
    if any(token in status for token in ("PACK", "PREPAR")):
        return "PACKING"
    return normalize_order_status(
        status or None,
        order_count=0,
        success_count=0,
        failure_count=0,
        all_succeeded=False,
    )
