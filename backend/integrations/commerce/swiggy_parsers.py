"""Swiggy MCP response parsers and payload normalizers.

Decoupled pure parsing logic for:
- Saved delivery addresses
- Live payment options
- Checkout order results
- Order summaries and details
- Delivery status and live tracking payloads
"""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.exceptions import CommerceError
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    OrderBillLine,
    OrderChildResult,
    OrderDetails,
    OrderLineItem,
    OrderSummary,
    PaymentOption,
    ProductVariant,
    TrackingLineItem,
    TrackingLocation,
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


def parse_delivery_addresses(data: Any) -> list[DeliveryAddress]:
    """Parse official get_addresses response without inventing fake defaults."""
    raw_list = data.get("addresses", data) if isinstance(data, dict) else data

    addresses: list[DeliveryAddress] = []
    if isinstance(raw_list, list):
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            addr_id = str(raw.get("id", ""))
            if not addr_id:
                continue

            label = (
                raw.get("addressCategory")
                or raw.get("addressTag")
                or raw.get("label")
                or ""
            )
            street = (
                raw.get("addressLine")
                or raw.get("formattedAddress")
                or raw.get("street")
                or ""
            )
            city = raw.get("city")
            postal_code = None
            if "pincode" in raw:
                postal_code = str(raw["pincode"])
            elif "postal_code" in raw:
                postal_code = str(raw["postal_code"])

            addresses.append(
                DeliveryAddress(
                    id=addr_id,
                    label=label,
                    street=street,
                    city=city,
                    postal_code=postal_code,
                    phone_number=raw.get("phoneNumber"),
                    address_category=raw.get("addressCategory"),
                    address_tag=raw.get("addressTag"),
                    is_serviceable=_optional_provider_bool(raw.get("serviceable")),
                )
            )
    return addresses


def parse_payment_options(data: dict[str, Any]) -> list[PaymentOption]:
    """Parse live available payment options from get_payment_options response."""
    options: list[PaymentOption] = []

    platform_kinds: dict[str, str] = {}
    platforms = data.get("platforms")
    if isinstance(platforms, dict):
        for platform_name, inferred_kind in (("mobile", "intent"), ("desktop", "qr")):
            platform = platforms.get(platform_name)
            methods = platform.get("methods", []) if isinstance(platform, dict) else []
            for method in methods if isinstance(methods, list) else []:
                if not isinstance(method, dict) or not method.get("id"):
                    continue
                method_id = str(method["id"])
                raw_kind = method.get("kind")
                kind = (
                    str(raw_kind).casefold()
                    if raw_kind is not None
                    else inferred_kind
                )
                if kind not in ("intent", "qr"):
                    continue
                existing = platform_kinds.get(method_id)
                platform_kinds[method_id] = kind if existing in (None, kind) else ""

    all_methods = data.get("allMethods", [])
    if isinstance(all_methods, list) and all_methods:
        for m in all_methods:
            if not isinstance(m, dict):
                continue
            mid = m.get("id")
            if not mid:
                continue
            dname = m.get("displayName", mid)
            raw_kind = m.get("kind")
            kind = (
                str(raw_kind).casefold()
                if raw_kind is not None
                else platform_kinds.get(str(mid))
            )
            if kind not in ("intent", "qr"):
                kind = None
            is_upi = "upi" in mid.lower() or "upi" in dname.lower() or kind in ("intent", "qr")
            lowered = f"{mid} {dname}".lower()
            if is_upi:
                method_cat = "UPI"
            elif "cash" in lowered or "cod" in lowered:
                method_cat = "Cash"
            elif "swiggy" in lowered and "pay" in lowered:
                method_cat = "SwiggyPay"
            else:
                method_cat = str(m.get("paymentMethod") or m.get("group") or mid)

            options.append(
                PaymentOption(
                    method=method_cat,
                    label=dname,
                    is_available=bool(m.get("enabled", True)),
                    id=mid,
                    kind=kind,
                )
            )

    cod_entry = data.get("cod", {})
    if isinstance(cod_entry, dict) and cod_entry.get("available"):
        options.append(
            PaymentOption(
                method=str(cod_entry.get("paymentMethod") or "Cash"),
                label=cod_entry.get("displayName") or "Cash",
                is_available=True,
                id=cod_entry.get("id"),
            )
        )

    return options


def build_checkout_order_result(
    data: dict[str, Any],
    res: dict[str, Any],
    cart_id: str,
    effective_address: str,
    payment_method: str,
) -> CommerceOrderResult:
    """Construct CommerceOrderResult from Swiggy checkout tool response."""
    raw_orders = data.get("orders", [])
    orders_list = raw_orders if isinstance(raw_orders, list) else []
    children = [parse_child_order(raw) for raw in orders_list if isinstance(raw, dict)]
    if children:
        order_count = len(children)
        success_count = sum(child.status == "ORDER_PLACED" for child in children)
        failure_count = sum(child.status == "FAILED" for child in children)
        all_succeeded = bool(
            order_count
            and success_count == order_count
            and failure_count == 0
        )
    else:
        order_count = int(data.get("orderCount", 0))
        success_count = int(data.get("successCount", 0))
        failure_count = int(data.get("failureCount", 0))
        reported_all_succeeded = data.get("allSucceeded")
        all_succeeded = (
            reported_all_succeeded
            if isinstance(reported_all_succeeded, bool)
            else bool(
                order_count
                and success_count == order_count
                and failure_count == 0
            )
        )
    primary_order_id = data.get("orderId") or next(
        (child.order_id for child in children if child.order_id), None
    )

    raw_status_value = data.get("status")
    raw_status = str(raw_status_value).upper() if raw_status_value is not None else None
    top_level_status = normalize_order_status(
        raw_status,
        order_count=order_count,
        success_count=success_count,
        failure_count=failure_count,
        all_succeeded=all_succeeded,
    )
    if children:
        if all_succeeded:
            status = "ORDER_PLACED"
        elif failure_count == order_count:
            status = "FAILED"
        elif success_count > 0:
            status = "PARTIAL_ORDER"
        elif top_level_status == "PAYMENT_PENDING" and failure_count == 0:
            status = "PAYMENT_PENDING"
        else:
            status = "ORDER_STATE_UNKNOWN"
    else:
        status = top_level_status
    if status == "ORDER_PLACED" and not primary_order_id:
        status = "ORDER_STATE_UNKNOWN"

    raw_grand_total = data.get("cartTotal", data.get("grandTotal"))
    grand_total = float(raw_grand_total) if raw_grand_total is not None else None
    delivery_addr = data.get("deliveryAddress")

    return CommerceOrderResult(
        order_id=primary_order_id,
        cart_id=cart_id,
        status=status,
        raw_status=raw_status,
        items=[],
        payment_method=payment_method,
        grand_total=grand_total,
        delivery_address=DeliveryAddress(
            id=effective_address,
            label=data.get("deliveryLabel") or "Address",
            street=delivery_addr if isinstance(delivery_addr, str) else "",
        ),
        tracking_url=data.get("trackingUrl"),
        orders=children,
        order_count=order_count,
        success_count=success_count,
        failure_count=failure_count,
        all_succeeded=all_succeeded,
        paas_id=data.get("paasId"),
        transaction_id=data.get("transactionId"),
        bridge_url=data.get("bridgeUrl"),
        upi_intent_url=data.get("upiIntentUrl"),
        is_qr_flow=bool(data.get("isQrFlow", False)),
        polling_interval_ms=data.get("pollingIntervalInMs"),
        max_time_to_poll_ms=data.get("maxTimeToPollForInMs"),
        provider_message=(
            str(data["message"])
            if data.get("message") is not None
            else (str(res["message"]) if res.get("message") is not None else None)
        ),
    )


def parse_orders_summary(data: dict[str, Any]) -> list[OrderSummary]:
    """Parse list of orders from get_orders tool response."""
    raw_orders = data.get("orders", []) if isinstance(data, dict) else []
    orders: list[OrderSummary] = []
    for raw in raw_orders if isinstance(raw_orders, list) else []:
        if not isinstance(raw, dict) or not raw.get("orderId"):
            continue
        raw_status = raw.get("currentStatus") or raw.get("status")
        delivery = raw.get("deliveryAddress")
        orders.append(
            OrderSummary(
                order_id=str(raw["orderId"]),
                raw_status=(str(raw_status) if raw_status is not None else None),
                normalized_status=normalize_existing_order_status(raw_status),
                created_at=raw.get("createdAt"),
                updated_at=raw.get("updatedAt"),
                estimated_delivery_time=raw.get("estimatedDeliveryTime"),
                item_count=(int(raw["itemCount"]) if raw.get("itemCount") is not None else None),
                total_amount=(float(raw["totalAmount"]) if raw.get("totalAmount") is not None else None),
                payment_method=raw.get("paymentMethod"),
                payment_status=raw.get("paymentStatus"),
                refund_status=raw.get("refundStatus"),
                order_type=raw.get("orderType"),
                is_active=(bool(raw["isActive"]) if "isActive" in raw else None),
                status_message=raw.get("statusMessage"),
                store_name=raw.get("storeName"),
                address_id=(
                    str(delivery["id"])
                    if isinstance(delivery, dict) and delivery.get("id") is not None
                    else None
                ),
                items=parse_order_items(raw.get("items")),
            )
        )
    return orders


def parse_order_details_response(data: dict[str, Any]) -> OrderDetails:
    """Parse order details from get_order_details tool response."""
    if not isinstance(data, dict) or not data.get("orderId"):
        raise CommerceError(
            "Provider order-details response omitted orderId.",
            provider="swiggy",
            code="INVALID_PROVIDER_RESPONSE",
        )
    raw_status = data.get("status")
    bill = data.get("bill") if isinstance(data.get("bill"), dict) else {}
    raw_lines = bill.get("lineItems", [])
    lines = [
        OrderBillLine(name=str(line["name"]), amount=str(line["amount"]))
        for line in raw_lines
        if isinstance(line, dict) and line.get("name") and line.get("amount") is not None
    ] if isinstance(raw_lines, list) else []
    return OrderDetails(
        order_id=str(data["orderId"]),
        raw_status=str(raw_status) if raw_status is not None else None,
        normalized_status=normalize_existing_order_status(raw_status),
        total_bill=(float(data["totalBill"]) if data.get("totalBill") is not None else None),
        has_refunds=(bool(data["hasRefunds"]) if "hasRefunds" in data else None),
        items=parse_order_items(data.get("items")),
        bill_lines=lines,
        grand_total_text=(str(bill["grandTotal"]) if bill.get("grandTotal") is not None else None),
    )


def parse_delivery_status_response(data: dict[str, Any]) -> DeliveryStatusResult:
    """Parse delivery status from get_delivery_status tool response."""
    if not isinstance(data, dict) or not data.get("orderId"):
        raise CommerceError(
            "Provider delivery-status response omitted orderId.",
            provider="swiggy",
            code="INVALID_PROVIDER_RESPONSE",
        )
    return DeliveryStatusResult(
        order_id=str(data["orderId"]),
        delivery_by_ms=(int(data["deliveryBy"]) if data.get("deliveryBy") is not None else None),
        server_now_ms=(int(data["serverNow"]) if data.get("serverNow") is not None else None),
        eta_text=data.get("etaText"),
        cancelled=(bool(data["cancelled"]) if "cancelled" in data else None),
        delivered=(bool(data["delivered"]) if "delivered" in data else None),
        status_text=data.get("statusText"),
        poll_interval_sec=(
            int(data["pollIntervalSec"])
            if data.get("pollIntervalSec") is not None
            else None
        ),
    )


def _parse_location(raw: Any) -> Optional[TrackingLocation]:
    if not isinstance(raw, dict):
        return None
    latitude = raw.get("latitude")
    longitude = raw.get("longitude")
    if latitude is None or longitude is None:
        return None
    return TrackingLocation(latitude=float(latitude), longitude=float(longitude))


def parse_delivery_tracking_response(data: dict[str, Any], order_id: str) -> DeliveryTrackingStatus:
    """Parse real-time delivery tracking status and ETA per official track_order schema."""
    status_info = data.get("status", {})
    status_msg = ""
    raw_status = None
    eta_minutes = None
    eta_text = None

    if isinstance(status_info, dict):
        raw_status = status_info.get("statusMessage")
        status_msg = str(raw_status or "").upper()
        eta_value = status_info.get("etaMinutes")
        eta_minutes = int(eta_value) if eta_value is not None else None
        eta_text = status_info.get("etaText")
    elif isinstance(status_info, str):
        raw_status = status_info
        status_msg = status_info.upper()

    if "CANCEL" in status_msg:
        status = "CANCELLED"
    elif "DELIVERED" in status_msg:
        status = "DELIVERED"
    elif "OUT" in status_msg or "DISPATCH" in status_msg:
        status = "OUT_FOR_DELIVERY"
    elif "PACK" in status_msg or "PREPAR" in status_msg:
        status = "PACKING"
    elif "RIDER" in status_msg and ("ASSIGN" in status_msg or "FOUND" in status_msg):
        status = "RIDER_ASSIGNED"
    elif "CONFIRM" in status_msg or "PLACED" in status_msg:
        status = "ORDER_PLACED"
    else:
        status = "UNKNOWN"

    store_info = data.get("storeInfo", {})
    delivery_info = data.get("deliveryInfo", {})
    payment_info = data.get("paymentInfo", {})
    map_info = data.get("mapInfo", {})

    raw_items = data.get("items", [])
    items = [
        TrackingLineItem(
            name=str(item["name"]),
            quantity=int(item["quantity"]),
            price=(str(item["price"]) if item.get("price") is not None else None),
        )
        for item in raw_items
        if isinstance(item, dict) and item.get("name") and item.get("quantity") is not None
    ] if isinstance(raw_items, list) else []

    return DeliveryTrackingStatus(
        order_id=str(data.get("orderId") or order_id),
        status=status,
        raw_status=str(raw_status) if raw_status is not None else None,
        sub_status_message=(
            str(status_info["subStatusMessage"])
            if isinstance(status_info, dict)
            and status_info.get("subStatusMessage") is not None
            else None
        ),
        eta_minutes=eta_minutes,
        eta_text=eta_text,
        order_title=(
            str(data["orderTitle"]) if data.get("orderTitle") is not None else None
        ),
        order_subtitle=(
            str(data["orderSubtitle"])
            if data.get("orderSubtitle") is not None
            else None
        ),
        status_message=str(raw_status) if raw_status is not None else None,
        store_name=(
            str(store_info["name"])
            if isinstance(store_info, dict) and store_info.get("name") is not None
            else None
        ),
        store_address=(
            str(store_info["address"])
            if isinstance(store_info, dict) and store_info.get("address") is not None
            else None
        ),
        delivery_address_label=(
            str(delivery_info["addressLabel"])
            if isinstance(delivery_info, dict)
            and delivery_info.get("addressLabel") is not None
            else None
        ),
        delivery_address=(
            str(delivery_info["fullAddress"])
            if isinstance(delivery_info, dict)
            and delivery_info.get("fullAddress") is not None
            else None
        ),
        items=items,
        item_count=(int(data["itemCount"]) if data.get("itemCount") is not None else None),
        placed_at=(str(data["placedAt"]) if data.get("placedAt") is not None else None),
        payment_message=(
            str(payment_info["message"])
            if isinstance(payment_info, dict) and payment_info.get("message") is not None
            else None
        ),
        payment_amount=(
            str(payment_info["amount"])
            if isinstance(payment_info, dict) and payment_info.get("amount") is not None
            else None
        ),
        store_location=_parse_location(map_info.get("storeLocation")) if isinstance(map_info, dict) else None,
        store_annotation=(
            str(map_info["storeAnnotation"])
            if isinstance(map_info, dict) and map_info.get("storeAnnotation") is not None
            else None
        ),
        delivery_location=_parse_location(map_info.get("deliveryLocation")) if isinstance(map_info, dict) else None,
        delivery_annotation=(
            str(map_info["deliveryAnnotation"])
            if isinstance(map_info, dict)
            and map_info.get("deliveryAnnotation") is not None
            else None
        ),
        rider_location=_parse_location(map_info.get("riderLocation")) if isinstance(map_info, dict) else None,
        polling_interval_seconds=(
            int(data["pollingIntervalSeconds"])
            if data.get("pollingIntervalSeconds") is not None
            else None
        ),
    )
