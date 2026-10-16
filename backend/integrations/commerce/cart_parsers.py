"""Swiggy Instamart cart and bill breakdown parser."""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.catalog_parsers import _optional_provider_bool
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
)


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
    handling_fee = 0.0
    taxes = 0.0
    discount = 0.0
    parsed_bill_lines = []

    for line in line_items:
        raw_label = line.get("label", "").strip()
        label = raw_label.lower()
        val_str = str(line.get("value", "0")).replace("₹", "").replace(",", "").strip()
        try:
            val = float(val_str)
        except ValueError:
            val = 0.0

        parsed_bill_lines.append({"label": raw_label, "value": val})

        if "item" in label or "subtotal" in label:
            item_total = val
        elif "delivery" in label:
            delivery_fee = val
        elif "package" in label or "packing" in label:
            packaging_fee = val
        elif "handling" in label or "convenience" in label or "platform" in label or "surge" in label or "rain" in label:
            handling_fee += val
        elif "tax" in label or "gst" in label:
            taxes = val
        elif "discount" in label or "coupon" in label:
            discount = abs(val)

    grand_total = 0.0
    to_pay = bill_breakdown.get("toPay") or data.get("toPay") or {}
    if isinstance(to_pay, dict) and "value" in to_pay:
        try:
            grand_total = float(str(to_pay["value"]).replace("₹", "").replace(",", "").strip())
        except ValueError:
            grand_total = 0.0
    elif isinstance(to_pay, (int, float)):
        grand_total = float(to_pay)
    else:
        grand_total = float(data.get("grandTotal", 0.0))

    if grand_total == 0.0 and (data.get("cartTotalAmount") is not None or data.get("total") is not None):
        tot_str = str(data.get("cartTotalAmount", data.get("total"))).replace("₹", "").replace(",", "").strip()
        try:
            grand_total = float(tot_str)
        except ValueError:
            grand_total = 0.0

    if not item_total and cart_items:
        item_total = sum(i.total_price for i in cart_items)

    computed_sum = round(item_total + delivery_fee + packaging_fee + handling_fee + taxes - discount, 2)
    grand_total = round(grand_total, 2)
    diff = round(grand_total - computed_sum, 2)

    cart_warning = data.get("cartWarning")
    to_pay_currency = to_pay.get("currency") if isinstance(to_pay, dict) else None
    currency = str(data.get("currency") or to_pay_currency or "INR").upper()
    if currency != "INR":
        cart_warning = "Provider cart currency is not INR."
    if grand_total <= 0:
        cart_warning = "Provider payable total is unavailable."
    elif abs(diff) > 0.01:
        cart_warning = "Provider bill lines do not explain the payable total."

    is_serviceable = _optional_provider_bool(data.get("serviceable"))
    if data.get("addressWarning") or data.get("unserviceableItems"):
        is_serviceable = False

    return CommerceCart(
        cart_id=str(data["cartId"]) if data.get("cartId") is not None else None,
        address_id=(
            (data.get("selectedAddress", {}).get("id") or data.get("selectedAddress", {}).get("addressId"))
            if isinstance(data.get("selectedAddress"), dict)
            else (data.get("selectedAddress") or data.get("selectedAddressId") or data.get("addressId"))
        ),
        items=cart_items,
        item_total=item_total,
        delivery_fee=delivery_fee,
        packaging_fee=packaging_fee,
        handling_fee=handling_fee,
        taxes=taxes,
        discount=discount,
        grand_total=grand_total,
        currency=currency,
        billing_complete=currency == "INR" and grand_total > 0 and abs(diff) <= 0.01,
        bill_lines=parsed_bill_lines,
        cart_warning=cart_warning,
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


__all__ = ["_optional_provider_bool", "build_commerce_cart"]
