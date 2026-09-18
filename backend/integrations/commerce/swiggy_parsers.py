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
    CommerceOrderResult,
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    OrderBillLine,
    OrderDetails,
    OrderSummary,
    PaymentOption,
    TrackingLineItem,
    TrackingLocation,
)
from backend.integrations.commerce.swiggy_normalizers import (
    _optional_provider_bool,
    normalize_existing_order_status,
    normalize_order_status,
    parse_child_order,
    parse_order_items,
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
