"""Swiggy Instamart MCP commerce adapter (Spec §5.1, §28, & §38.9).

Authoritative integration with Swiggy Instamart MCP server following official
Swiggy Builders Club specifications. Strictly enforces:
- Token secrecy and zero-credential leakage
- Explicit confirmation requirement before checkout
- Non-idempotent checkout error recovery (no blind retries on 5xx/timeout)
- Multi-store order and UPI PENDING_PAYMENT handling
- Exact schema fidelity for get_addresses, search_products, update_cart, get_cart, get_payment_options, checkout, and track_order
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional
import httpx

from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    DeliveryAddress,
    CommerceProductItem,
    ProductVariant,
    CartItemUpdate,
    CartItem,
    CommerceCart,
    PaymentOption,
    CommerceOrderResult,
    DeliveryTrackingStatus,
    OrderChildResult,
    PaymentStatusResult,
    DeliveryStatusResult,
    OrderBillLine,
    OrderDetails,
    OrderLineItem,
    OrderSummary,
)
from backend.integrations.commerce.exceptions import (
    CommerceError,
    UnconfirmedCheckoutError,
    AddressNotServiceableError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    CartExpiredError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UpstreamTimeoutError,
    OrderStateUnknownError,
)

logger = logging.getLogger("grocer.integrations.swiggy")


class SwiggyMCPAdapter(CommercePort):
    """Authoritative production adapter for Swiggy Instamart MCP server."""

    def __init__(
        self,
        base_url: str = "https://mcp.swiggy.com/im",
        auth_token: Optional[str] = None,
        timeout: float = 15.0,
        token_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self.timeout = timeout
        self._token_resolver = token_resolver

    def __repr__(self) -> str:
        # Strict zero-credential leakage in logs and repr strings
        has_token = bool(self._auth_token or self._token_resolver)
        token_masked = "***" if has_token else "none"
        return f"SwiggyMCPAdapter(endpoint={self.base_url}, token={token_masked})"

    def __str__(self) -> str:
        return repr(self)

    def _resolve_token(self, customer_id: Optional[str] = None) -> Optional[str]:
        if self._token_resolver and customer_id:
            resolved = self._token_resolver(customer_id)
            if resolved:
                return resolved
        return self._auth_token

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        customer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute JSON-RPC 2.0 tool call against Swiggy Instamart MCP endpoint."""
        token = self._resolve_token(customer_id)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.base_url, json=payload, headers=headers)

                if resp.status_code == 401:
                    raise ProviderAuthError("Swiggy MCP session unauthenticated or token expired.")
                elif resp.status_code == 419:
                    raise ProviderSessionRevokedError("Swiggy MCP session revoked. Re-auth required.")
                elif resp.status_code == 504:
                    raise UpstreamTimeoutError("Swiggy MCP upstream gateway timed out.")
                elif resp.status_code >= 500:
                    raise UpstreamTimeoutError(f"Swiggy MCP upstream error: HTTP {resp.status_code}")
                elif resp.status_code >= 400:
                    err_msg = f"Swiggy MCP bad request: HTTP {resp.status_code}"
                    try:
                        err_data = resp.json()
                        if "error" in err_data:
                            self._parse_error_if_failed(err_data)
                    except Exception as parse_exc:
                        if isinstance(parse_exc, CommerceError):
                            raise parse_exc
                    raise CommerceError(err_msg)

                data = resp.json()

                # Check JSON-RPC protocol error
                if "error" in data and not data.get("result"):
                    rpc_err = data["error"]
                    code = rpc_err.get("code")
                    msg = rpc_err.get("message", "Unknown JSON-RPC error")
                    if code == -32001:
                        raise ProviderAuthError(msg)
                    self._parse_error_if_failed({"success": False, "error": rpc_err})
                    raise CommerceError(f"Swiggy MCP RPC error {code}: {msg}")

                result = data.get("result", data)
                # Official Swiggy MCP returns structuredContent inside result
                if isinstance(result, dict) and "structuredContent" in result and "data" not in result:
                    result["data"] = result["structuredContent"]
                return result

        except httpx.TimeoutException:
            raise UpstreamTimeoutError("Swiggy MCP request timed out.")
        except httpx.RequestError as exc:
            if isinstance(exc, (ProviderAuthError, UpstreamTimeoutError, CommerceError)):
                raise exc
            raise CommerceError(f"Swiggy MCP network connection failure: {exc}")

    def _parse_error_if_failed(self, response_data: dict[str, Any]) -> None:
        """Classify errors from Swiggy envelope per official error taxonomy."""
        if response_data.get("success") is False:
            err = response_data.get("error", {})
            msg = err.get("message", "Swiggy operation failed")
            msg_lower = msg.lower()

            if "out of stock" in msg_lower or "item_out_of_stock" in msg_lower:
                raise ItemOutOfStockError(spin_id="unknown")
            elif "not serviceable" in msg_lower or "address_not_serviceable" in msg_lower:
                raise AddressNotServiceableError(address_id="current")
            elif "minimum order" in msg_lower or "min order" in msg_lower or "min_order_not_met" in msg_lower:
                raise MinOrderNotMetError(current_total=0.0)
            elif "expired" in msg_lower or "abandoned" in msg_lower or "cart_expired" in msg_lower:
                raise CartExpiredError(cart_id="current")
            elif "unauthenticated" in msg_lower or "token_expired" in msg_lower:
                raise ProviderAuthError(msg)
            elif "session_revoked" in msg_lower:
                raise ProviderSessionRevokedError(msg)
            else:
                raise CommerceError(f"Swiggy error: {msg}")

    async def get_addresses(
        self, customer_id: str, page: int = 1, page_size: int = 10
    ) -> list[DeliveryAddress]:
        """Fetch saved delivery addresses per official get_addresses schema.

        Returns data.addresses[] without inventing fake defaults.
        """
        args = {"page": page, "pageSize": page_size} if page > 1 or page_size != 10 else {}
        res = await self._call_mcp_tool("get_addresses", args, customer_id=customer_id)
        self._parse_error_if_failed(res)

        data = res.get("data", {})
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
                        is_serviceable=(
                            bool(raw["serviceable"])
                            if "serviceable" in raw
                            else None
                        ),
                    )
                )
        return addresses

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        """Fetch staple items via your_go_to_items tool."""
        res = await self._call_mcp_tool("your_go_to_items", {"addressId": address_id})
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_items = data.get("products", data) if isinstance(data, dict) else data
        return self._parse_products(raw_items)

    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        """Search products available at delivery address via search_products tool."""
        res = await self._call_mcp_tool(
            "search_products",
            {"addressId": address_id, "query": query, "offset": 0},
        )
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_items = data.get("products", data) if isinstance(data, dict) else data
        products = self._parse_products(raw_items)

        # Parse optional similar products if present
        if isinstance(data, dict) and "similarProducts" in data:
            similar_raw = data.get("similarProducts", [])
            similar = self._parse_products(similar_raw)
            if products and similar:
                products[0].similar_products = similar

        return products

    def _parse_products(self, raw_items: Any) -> list[CommerceProductItem]:
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
                in_stock = bool(stock_value) if stock_value is not None else None
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

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        """Fetch current Instamart cart per official get_cart schema."""
        args: dict[str, Any] = {}
        if cart_id:
            args["cartId"] = cart_id
        res = await self._call_mcp_tool("get_cart", args)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        return self._build_commerce_cart(data, cart_id)

    async def update_cart(
        self,
        items: list[CartItemUpdate],
        cart_id: Optional[str] = None,
        address_id: Optional[str] = None,
    ) -> CommerceCart:
        """Update Instamart cart using selectedAddressId and item array."""
        if not address_id:
            raise CommerceError(
                "Cart update requires a provider address ID.",
                provider="swiggy",
                code="MISSING_ADDRESS",
            )
        effective_address = address_id
        payload_items = []
        for it in items:
            item_entry: dict[str, Any] = {"spinId": it.spin_id, "quantity": it.quantity}
            if it.sku_id:
                item_entry["skuId"] = it.sku_id
            payload_items.append(item_entry)

        args: dict[str, Any] = {
            "selectedAddressId": effective_address,
            "items": payload_items,
        }
        if cart_id:
            args["cartId"] = cart_id

        res = await self._call_mcp_tool("update_cart", args)
        self._parse_error_if_failed(res)

        data = res.get("data", {})
        # If update_cart returned full InstamartCart, build from it, else refresh via get_cart
        if isinstance(data, dict) and "items" in data:
            return self._build_commerce_cart(data, cart_id)
        return await self.get_cart(cart_id)

    def _build_commerce_cart(self, data: dict[str, Any], cart_id: Optional[str] = None) -> CommerceCart:
        """Construct CommerceCart domain model from InstamartCart schema."""
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
            is_available = bool(stock_value) if stock_value is not None else None

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

        is_serviceable = (
            bool(data["serviceable"]) if "serviceable" in data else None
        )
        if data.get("addressWarning") or data.get("unserviceableItems"):
            is_serviceable = False

        resolved_cart_id = cart_id or data.get("cartId")
        if not resolved_cart_id:
            raise CommerceError(
                "Provider cart response omitted cartId.",
                provider="swiggy",
                code="INVALID_PROVIDER_RESPONSE",
            )

        return CommerceCart(
            cart_id=str(resolved_cart_id),
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
            cart_absent=bool(data.get("cartAbsent", False)),
            address_warning=data.get("addressWarning"),
            available_payment_methods=data.get("availablePaymentMethods", []),
        )

    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        """Clear all items from active cart via clear_cart tool."""
        res = await self._call_mcp_tool("clear_cart", {})
        self._parse_error_if_failed(res)
        return True

    async def get_payment_options(self, cart_id: Optional[str] = None, address_id: Optional[str] = None) -> list[PaymentOption]:
        """Fetch live available payment methods via get_payment_options tool."""
        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        res = await self._call_mcp_tool("get_payment_options", args)
        self._parse_error_if_failed(res)

        data = res.get("data", {})
        options: list[PaymentOption] = []

        all_methods = data.get("allMethods", [])
        if isinstance(all_methods, list) and all_methods:
            for m in all_methods:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id")
                if not mid:
                    continue
                dname = m.get("displayName", mid)
                kind = m.get("kind")
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

        # Check cod entry
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

    async def checkout(
        self,
        cart_id: str,
        payment_method: str = "UPI",
        explicit_confirmation: bool = False,
        address_id: Optional[str] = None,
        intent_app: Optional[str] = None,
        generate_upi_qr: bool = False,
    ) -> CommerceOrderResult:
        """Place Instamart order with strict server-side confirmation and non-idempotent retry guard."""
        if not explicit_confirmation:
            raise UnconfirmedCheckoutError(
                "Checkout rejected: explicit confirmation is strictly required."
            )

        if not address_id:
            raise CommerceError(
                "Checkout requires a provider address ID.",
                provider="swiggy",
                code="MISSING_ADDRESS",
            )
        effective_address = address_id
        args: dict[str, Any] = {
            "addressId": effective_address,
            "paymentMethod": payment_method,
        }
        if intent_app:
            args["intentApp"] = intent_app
        if generate_upi_qr:
            args["generateUPIQR"] = True

        try:
            res = await self._call_mcp_tool("checkout", args)
            self._parse_error_if_failed(res)
        except (UpstreamTimeoutError, httpx.TimeoutException) as exc:
            # NON-IDEMPOTENT CHECKOUT SAFETY: Do NOT blindly retry checkout!
            # Verify if order was already created upstream before failing.
            logger.warning("Checkout upstream timeout/5xx. Checking order state before acting: %s", exc)
            recovered_order = await self._probe_order_status_after_failure(effective_address, cart_id)
            if recovered_order:
                return recovered_order
            raise OrderStateUnknownError(
                f"Checkout status uncertain due to upstream timeout: {exc}. "
                "Do not retry blindly without verifying order state."
            )

        data = res.get("data", {})

        raw_orders = data.get("orders", [])
        orders_list = raw_orders if isinstance(raw_orders, list) else []
        children = [self._parse_child_order(raw) for raw in orders_list if isinstance(raw, dict)]
        order_count = int(data.get("orderCount", len(children)))
        success_count = int(
            data.get("successCount", sum(child.success is True for child in children))
        )
        failure_count = int(
            data.get("failureCount", sum(child.success is False for child in children))
        )
        all_succeeded = bool(
            data.get(
                "allSucceeded",
                bool(order_count and success_count == order_count and failure_count == 0),
            )
        )
        primary_order_id = data.get("orderId") or next(
            (child.order_id for child in children if child.order_id), None
        )

        raw_status_value = data.get("status")
        raw_status = str(raw_status_value).upper() if raw_status_value is not None else None
        status = self._normalize_order_status(
            raw_status,
            order_count=order_count,
            success_count=success_count,
            failure_count=failure_count,
            all_succeeded=all_succeeded,
        )

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
        )

    async def _probe_order_status_after_failure(
        self, address_id: str, cart_id: str
    ) -> Optional[CommerceOrderResult]:
        """Safely probe get_orders tool following a checkout 5xx/timeout to avoid duplicate charges."""
        try:
            res = await self._call_mcp_tool("get_orders", {})
            data = res.get("data", {})
            orders = data.get("orders", []) if isinstance(data, dict) else []
            if orders and isinstance(orders, list):
                correlated = next(
                    (
                        order
                        for order in orders
                        if isinstance(order, dict)
                        and str(order.get("cartId", "")) == cart_id
                        and str(order.get("addressId", "")) == address_id
                    ),
                    None,
                )
                if correlated:
                    order_id = correlated.get("orderId")
                    raw_status = correlated.get("status")
                    return CommerceOrderResult(
                        order_id=str(order_id) if order_id else None,
                        cart_id=cart_id,
                        status=self._normalize_order_status(
                            str(raw_status).upper() if raw_status is not None else None,
                            order_count=1,
                            success_count=1 if order_id else 0,
                            failure_count=0,
                            all_succeeded=bool(order_id),
                        ),
                        raw_status=str(raw_status) if raw_status is not None else None,
                        payment_method=str(correlated.get("paymentMethod") or ""),
                        grand_total=(
                            float(correlated["orderTotal"])
                            if correlated.get("orderTotal") is not None
                            else None
                        ),
                        delivery_address=DeliveryAddress(id=address_id),
                        order_count=1,
                        success_count=1 if order_id else 0,
                        all_succeeded=bool(order_id),
                    )
        except Exception as exc:
            logger.warning("Failed to probe order status: %s", exc)
        return None

    async def check_payment_status(
        self, paas_id: str, order_id: Optional[str] = None
    ) -> PaymentStatusResult:
        args: dict[str, Any] = {"paasId": paas_id}
        if order_id:
            args["orderId"] = order_id
        res = await self._call_mcp_tool("check_payment_status", args)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_status = data.get("status")
        is_terminal_success = data.get("isTerminalSuccess") is True
        is_terminal_failure = data.get("isTerminalFailure") is True
        terminal = data.get("terminal") is True
        if is_terminal_success:
            normalized = "PAYMENT_CONFIRMED"
        elif is_terminal_failure:
            normalized = "PAYMENT_FAILED"
        elif terminal:
            normalized = "PAYMENT_UNKNOWN"
        else:
            normalized = self._normalize_payment_status(raw_status)
        return PaymentStatusResult(
            paas_id=str(data.get("paasId") or paas_id),
            order_id=data.get("orderId") or order_id,
            transaction_id=data.get("transactionId"),
            status=str(raw_status) if raw_status is not None else None,
            normalized_status=normalized,
            terminal=terminal,
            is_terminal_success=is_terminal_success,
            is_terminal_failure=is_terminal_failure,
            confirmed=bool(data.get("confirmed", False)),
            order_status=data.get("orderStatus"),
        )

    async def confirm_order(self, order_id: str, paas_id: str) -> CommerceOrderResult:
        res = await self._call_mcp_tool(
            "confirm_order", {"orderId": order_id, "paasId": paas_id}
        )
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        result_value = data.get("result")
        order_status = data.get("orderStatus")
        result_text = str(result_value).casefold() if result_value is not None else ""
        raw_status = str(result_value or order_status) if result_value or order_status else None
        if result_text == "success":
            normalized = "ORDER_PLACED"
        elif result_text == "failed":
            normalized = "FAILED"
        elif result_text == "pending":
            normalized = "PAYMENT_PENDING"
        else:
            normalized = self._normalize_order_status(
                str(order_status).upper() if order_status is not None else None,
                order_count=1,
                success_count=0,
                failure_count=0,
                all_succeeded=False,
            )
        return CommerceOrderResult(
            order_id=data.get("orderId") or order_id,
            cart_id=data.get("cartId"),
            status=normalized,
            raw_status=raw_status,
            payment_method=(
                str(data["paymentMethod"]) if data.get("paymentMethod") is not None else None
            ),
            grand_total=(
                float(data.get("grandTotal", data.get("orderTotal")))
                if data.get("grandTotal", data.get("orderTotal")) is not None
                else None
            ),
            paas_id=str(data.get("paasId") or paas_id),
            order_count=1,
            success_count=1 if normalized == "ORDER_PLACED" else 0,
            failure_count=1 if normalized == "FAILED" else 0,
            all_succeeded=normalized == "ORDER_PLACED",
        )

    @staticmethod
    def _normalize_payment_status(raw_status: Any) -> str:
        status = str(raw_status or "").upper()
        if any(token in status for token in ("SUCCESS", "PAID", "COMPLETED")):
            return "PAYMENT_CONFIRMED"
        if any(token in status for token in ("FAIL", "CANCEL", "EXPIRE", "REFUND")):
            return "PAYMENT_FAILED"
        if any(token in status for token in ("PENDING", "PROCESS", "INITIATED")):
            return "PAYMENT_PENDING"
        return "PAYMENT_UNKNOWN"

    @staticmethod
    def _normalize_order_status(
        raw_status: Optional[str],
        *,
        order_count: int,
        success_count: int,
        failure_count: int,
        all_succeeded: bool,
    ) -> str:
        status = raw_status or ""
        if "PENDING_PAYMENT" in status or status == "PAYMENT_PENDING":
            return "PAYMENT_PENDING"
        if (failure_count > 0 and success_count > 0) or "PARTIAL" in status:
            return "PARTIAL_ORDER"
        if (failure_count > 0 and success_count == 0) or "FAIL" in status:
            return "FAILED"
        if any(token in status for token in ("CONFIRM", "PLACED", "SUCCESS")):
            return "ORDER_PLACED"
        if order_count > 0 and all_succeeded and success_count == order_count:
            return "ORDER_PLACED"
        return "ORDER_STATE_UNKNOWN"

    def _parse_child_order(self, raw: dict[str, Any]) -> OrderChildResult:
        raw_status_value = raw.get("status")
        raw_status = str(raw_status_value).upper() if raw_status_value is not None else None
        explicit_success = raw.get("success")
        success = bool(explicit_success) if explicit_success is not None else None
        normalized = self._normalize_order_status(
            raw_status,
            order_count=1,
            success_count=1 if success is True else 0,
            failure_count=1 if success is False else 0,
            all_succeeded=success is True,
        )
        return OrderChildResult(
            order_id=str(raw["orderId"]) if raw.get("orderId") else None,
            status=normalized,
            raw_status=raw_status,
            success=success,
            grand_total=float(raw["orderTotal"]) if raw.get("orderTotal") is not None else None,
        )

    @staticmethod
    def _parse_order_items(raw_items: Any) -> list[OrderLineItem]:
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

    @classmethod
    def _normalize_existing_order_status(cls, raw_status: Any) -> str:
        status = str(raw_status or "").upper()
        if "CANCEL" in status:
            return "CANCELLED"
        if "DELIVER" in status:
            return "DELIVERED"
        if any(token in status for token in ("PACK", "PREPAR")):
            return "PACKING"
        if any(token in status for token in ("OUT_FOR_DELIVERY", "DISPATCH")):
            return "OUT_FOR_DELIVERY"
        return cls._normalize_order_status(
            status or None,
            order_count=0,
            success_count=0,
            failure_count=0,
            all_succeeded=False,
        )

    async def get_orders(
        self, count: int = 10, active_only: bool = False
    ) -> list[OrderSummary]:
        args: dict[str, Any] = {
            "count": max(1, min(count, 20)),
            "orderType": "INSTAMART",
        }
        if active_only:
            args["activeOnly"] = True
        res = await self._call_mcp_tool("get_orders", args)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
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
                    normalized_status=self._normalize_existing_order_status(raw_status),
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
                    items=self._parse_order_items(raw.get("items")),
                )
            )
        return orders

    async def get_order_details(self, order_id: str) -> OrderDetails:
        res = await self._call_mcp_tool("get_order_details", {"orderId": order_id})
        self._parse_error_if_failed(res)
        data = res.get("data", {})
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
            normalized_status=self._normalize_existing_order_status(raw_status),
            total_bill=(float(data["totalBill"]) if data.get("totalBill") is not None else None),
            has_refunds=(bool(data["hasRefunds"]) if "hasRefunds" in data else None),
            items=self._parse_order_items(data.get("items")),
            bill_lines=lines,
            grand_total_text=(str(bill["grandTotal"]) if bill.get("grandTotal") is not None else None),
        )

    async def get_delivery_status(
        self, order_id: str, address_id: str
    ) -> DeliveryStatusResult:
        res = await self._call_mcp_tool(
            "get_delivery_status", {"orderId": order_id, "addressId": address_id}
        )
        self._parse_error_if_failed(res)
        data = res.get("data", {})
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

    async def track_order(
        self, order_id: str, lat: Optional[float] = None, lng: Optional[float] = None
    ) -> DeliveryTrackingStatus:
        """Fetch real-time delivery tracking status and ETA per official track_order schema."""
        if lat is None or lng is None:
            raise CommerceError(
                "Tracking requires provider-returned delivery coordinates.",
                provider="swiggy",
                code="MISSING_TRACKING_COORDINATES",
            )
        args: dict[str, Any] = {"orderId": order_id, "lat": lat, "lng": lng}
        res = await self._call_mcp_tool("track_order", args)
        self._parse_error_if_failed(res)

        data = res.get("data", {})
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
        store_name = store_info.get("name") if isinstance(store_info, dict) else None

        return DeliveryTrackingStatus(
            order_id=order_id,
            status=status,
            raw_status=str(raw_status) if raw_status is not None else None,
            eta_minutes=eta_minutes,
            eta_text=eta_text,
            status_message=str(raw_status) if raw_status is not None else None,
            store_name=store_name,
            polling_interval_seconds=(
                int(data["pollingIntervalSeconds"])
                if data.get("pollingIntervalSeconds") is not None
                else None
            ),
        )
