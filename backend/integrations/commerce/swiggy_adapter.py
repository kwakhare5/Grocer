"""Swiggy Instamart MCP commerce adapter.

Authoritative integration with Swiggy Instamart MCP server following official
Swiggy Builders Club specifications. Strictly enforces:
- Token secrecy and zero-credential leakage
- Explicit confirmation requirement before checkout
- Non-idempotent checkout error recovery (no blind retries on 5xx/timeout)
- Multi-store order and UPI PENDING_PAYMENT handling
- Exact schema fidelity for get_addresses, search_products, update_cart, get_cart, get_payment_options, checkout, and track_order
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Optional

import httpx

from backend.integrations.commerce.exceptions import (
    CommerceError,
    OrderStateUnknownError,
    ProviderAuthError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.models import (
    AddressRecommendation,
    CartItemUpdate,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    Coupon,
    CouponApplyResult,
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    ErrorReportResult,
    OrderDetails,
    OrderSummary,
    PaymentOption,
    PaymentStatusResult,
)
from backend.integrations.commerce.port import CommercePort, SWIGGY_CUSTOMER_CARE_PHONE
from backend.integrations.commerce.swiggy_client import SwiggyMcpClient
from backend.integrations.commerce.catalog_parsers import parse_coupons, parse_swiggy_products
from backend.integrations.commerce.cart_parsers import build_commerce_cart
from backend.integrations.commerce.order_parsers import (
    build_checkout_order_result,
    normalize_order_status,
    normalize_payment_status,
    parse_delivery_addresses,
    parse_delivery_status_response,
    parse_delivery_tracking_response,
    parse_order_details_response,
    parse_orders_summary,
    parse_payment_options,
)

logger = logging.getLogger("grocer.integrations.swiggy")


class SwiggyMCPAdapter(CommercePort):
    """Authoritative production adapter for Swiggy Instamart MCP server."""

    def __init__(
        self,
        base_url: str = "https://mcp.swiggy.com/im",
        auth_token: Optional[str] = None,
        timeout: float = 15.0,
        token_resolver: Optional[Callable[[str], Optional[str] | Awaitable[Optional[str]]]] = None,
        owner_customer_id: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self.timeout = timeout
        self._token_resolver = token_resolver
        self._owner_customer_id = owner_customer_id
        self._customer_context: ContextVar[Optional[str]] = ContextVar(
            f"swiggy_customer_{id(self)}", default=None
        )
        self._client = SwiggyMcpClient(
            base_url=self.base_url,
            timeout=self.timeout,
            auth_token=self._auth_token,
            token_resolver=self._token_resolver,
            owner_customer_id=self._owner_customer_id,
        )

    @contextmanager
    def customer_scope(self, customer_id: str) -> Iterator[None]:
        token = self._customer_context.set(customer_id)
        try:
            yield
        finally:
            self._customer_context.reset(token)

    def __repr__(self) -> str:
        # Strict zero-credential leakage in logs and repr strings
        has_token = bool(self._auth_token or self._token_resolver)
        token_masked = "***" if has_token else "none"
        return f"SwiggyMCPAdapter(endpoint={self.base_url}, token={token_masked})"

    def __str__(self) -> str:
        return repr(self)

    def _resolve_token(self, customer_id: Optional[str] = None) -> Optional[str]:
        effective_customer = customer_id or self._customer_context.get()
        return self._client.resolve_token(effective_customer)

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        customer_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Execute JSON-RPC 2.0 tool call against Swiggy Instamart MCP endpoint."""
        effective_customer = customer_id or self._customer_context.get()
        return await self._client.call_tool(tool_name, arguments, customer_id=effective_customer, timeout=timeout)

    def _parse_error_if_failed(self, response_data: dict[str, Any]) -> None:
        """Classify errors from Swiggy envelope per official error taxonomy."""
        self._client.parse_error_if_failed(response_data)

    async def get_addresses(
        self, customer_id: str, page: int = 1, page_size: int = 10
    ) -> list[DeliveryAddress]:
        """Fetch saved delivery addresses per official get_addresses schema."""
        args = {"page": page, "pageSize": page_size} if page > 1 or page_size != 10 else {}
        res = await self._call_mcp_tool("get_addresses", args, customer_id=customer_id)
        self._parse_error_if_failed(res)
        return parse_delivery_addresses(res.get("data", {}))

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        """Fetch staple items via your_go_to_items tool."""
        res = await self._call_mcp_tool("your_go_to_items", {"addressId": address_id})
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_items = data.get("products", data) if isinstance(data, dict) else data
        return parse_swiggy_products(raw_items)

    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        """Search products available at delivery address via search_products tool."""
        if not query.strip():
            raise CommerceError(
                "Product search requires a non-empty query.",
                provider="swiggy",
                code="MISSING_SEARCH_QUERY",
            )
        res = await self._call_mcp_tool(
            "search_products",
            {"addressId": address_id, "query": query},
        )
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_items = data.get("products", data) if isinstance(data, dict) else data
        products = parse_swiggy_products(raw_items)

        if isinstance(data, dict) and "similarProducts" in data:
            similar_raw = data.get("similarProducts", [])
            similar = parse_swiggy_products(similar_raw)
            if products and similar:
                products[0].similar_products = similar

        return products

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        """Fetch current Instamart cart per official get_cart schema."""
        del cart_id
        res = await self._call_mcp_tool("get_cart", {})
        self._parse_error_if_failed(res)
        return build_commerce_cart(res.get("data", {}))

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
            if not it.sku_id:
                raise CommerceError(
                    "Cart update requires a catalog SKU ID for every item.",
                    provider="swiggy",
                    code="MISSING_SKU",
                )
            payload_items.append({"spinId": it.spin_id, "quantity": it.quantity, "skuId": it.sku_id})

        args: dict[str, Any] = {
            "selectedAddressId": effective_address,
            "items": payload_items,
        }
        res = await self._call_mcp_tool("update_cart", args)
        self._parse_error_if_failed(res)

        data = res.get("data", {})
        if isinstance(data, dict) and (data.get("items") or data.get("cartId")):
            canonical_cart = build_commerce_cart(data, cart_id=cart_id)
        else:
            canonical_cart = await self.get_cart()
        reduced_quantity_items = data.get("reducedQuantityItems", []) if isinstance(data, dict) else []
        if not canonical_cart.address_id and effective_address:
            canonical_cart.address_id = effective_address
        if isinstance(reduced_quantity_items, list):
            canonical_cart.reduced_quantity_items = [
                item for item in reduced_quantity_items if isinstance(item, dict)
            ]
        return canonical_cart

    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        """Clear all items from active cart via clear_cart tool."""
        res = await self._call_mcp_tool("clear_cart", {})
        self._parse_error_if_failed(res)
        return True

    async def get_payment_options(
        self, cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> list[PaymentOption]:
        """Fetch live available payment methods via get_payment_options tool."""
        del cart_id, address_id
        res = await self._call_mcp_tool("get_payment_options", {})
        self._parse_error_if_failed(res)
        return parse_payment_options(res.get("data", {}))

    async def checkout(
        self,
        cart_id: str,
        payment_method: str = "UPI",
        explicit_confirmation: bool = False,
        address_id: Optional[str] = None,
        payment_option_id: Optional[str] = None,
        payment_option_kind: Optional[str] = None,
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
        if payment_option_kind == "intent":
            if not payment_option_id:
                raise CommerceError(
                    "UPI intent checkout requires the selected provider option ID.",
                    provider="swiggy",
                    code="MISSING_PAYMENT_OPTION",
                )
            args["intentApp"] = payment_option_id
        elif payment_option_kind == "qr":
            args["generateUPIQR"] = True
        elif payment_method.upper() == "UPI":
            args["generateUPIQR"] = True

        from backend.config import settings
        if settings.CHECKOUT_MODE == "review":
            logger.info(
                "CHECKOUT_MODE=review active: suppressing live Swiggy MCP checkout and returning simulated order."
            )
            try:
                current_cart = await self.get_cart(cart_id)
            except ProviderAuthError:
                raise
            except Exception as exc:
                logger.warning("Could not fetch cart for review simulation: %s", exc)
                raise CommerceError(f"Cannot checkout: unable to verify cart {cart_id}", provider="swiggy")
            cart_items = current_cart.items if current_cart else []
            total_amt = current_cart.grand_total if current_cart else 0.0

            return CommerceOrderResult(
                order_id=f"sim_rev_{int(time.time())}",
                cart_id=cart_id,
                status="REVIEW_COMPLETE",
                raw_status="REVIEW_SIMULATED",
                items=cart_items,
                grand_total=total_amt,
                payment_method=payment_method,
                is_simulated=True,
                message="[REVIEW MODE] Order simulated safely. No financial charge was made.",
                provider_message="Review mode simulated checkout successful.",
            )

        try:
            res = await self._call_mcp_tool("checkout", args)
            self._parse_error_if_failed(res)
        except (UpstreamTimeoutError, httpx.TimeoutException) as exc:
            logger.warning("Checkout upstream timeout/5xx. Checking order state before acting: %s", exc)
            await asyncio.sleep(2)
            recovered_order = await self._probe_order_status_after_failure(effective_address, cart_id)
            if recovered_order:
                return recovered_order
            raise OrderStateUnknownError(
                f"Checkout status uncertain due to upstream timeout: {exc}. "
                "Do not retry blindly without verifying order state."
            )

        return build_checkout_order_result(
            res.get("data", {}), res, cart_id, effective_address, payment_method
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
                correlated = None
                for order in orders:
                    if not isinstance(order, dict) or not order.get("orderId"):
                        continue
                    delivery = order.get("deliveryAddress")
                    ord_addr = (
                        str(delivery.get("id"))
                        if isinstance(delivery, dict) and delivery.get("id") is not None
                        else str(order.get("addressId") or "")
                    )
                    ord_cart = str(order.get("cartId", ""))
                    if ord_cart:
                        if ord_cart != cart_id:
                            continue
                    else:
                        # Require address match and non-historical order state to prevent claiming old orders
                        if not ord_addr or ord_addr != address_id:
                            continue
                        raw_st = str(order.get("currentStatus") or order.get("status") or "").upper()
                        if raw_st in ("DELIVERED", "COMPLETED", "CANCELLED", "REFUNDED", "FAILED", "RETURNED"):
                            continue
                    correlated = order
                    break

                if correlated:
                    order_id = correlated.get("orderId")
                    raw_status = correlated.get("currentStatus") or correlated.get("status")
                    order_total = correlated.get("totalAmount") or correlated.get("orderTotal")
                    return CommerceOrderResult(
                        order_id=str(order_id) if order_id else None,
                        cart_id=cart_id,
                        status=normalize_order_status(
                            str(raw_status).upper() if raw_status is not None else None,
                        ),
                        raw_status=str(raw_status) if raw_status is not None else None,
                        payment_method=str(correlated.get("paymentMethod") or ""),
                        grand_total=(
                            float(order_total)
                            if order_total is not None
                            else None
                        ),
                        delivery_address=DeliveryAddress(id=address_id),
                    )
        except Exception as exc:
            logger.warning("Failed to probe order status: %s", exc)
        return None

    async def check_payment_status(
        self, paas_id: str, order_id: Optional[str] = None
    ) -> PaymentStatusResult:
        """Check UPI or gateway payment status for an initiated checkout."""
        args: dict[str, Any] = {"paasId": paas_id}
        if order_id:
            args["orderId"] = order_id
        res = await self._call_mcp_tool("check_payment_status", args, timeout=25.0)
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
            normalized = normalize_payment_status(raw_status)
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
        """Finalize order confirmation once upstream payment succeeds."""
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
            normalized = normalize_order_status(
                str(order_status).upper() if order_status is not None else None,
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
        )

    async def get_orders(
        self, count: int = 10, active_only: bool = False
    ) -> list[OrderSummary]:
        """List past or active Instamart orders."""
        args: dict[str, Any] = {
            "count": max(1, min(count, 20)),
        }
        if active_only:
            args["activeOnly"] = True
        res = await self._call_mcp_tool("get_orders", args)
        self._parse_error_if_failed(res)
        return parse_orders_summary(res.get("data", {}))

    async def get_order_details(self, order_id: str) -> OrderDetails:
        """Fetch itemized bill and line items for an order."""
        res = await self._call_mcp_tool("get_order_details", {"orderId": order_id})
        self._parse_error_if_failed(res)
        return parse_order_details_response(res.get("data", {}))

    async def get_delivery_status(
        self, order_id: str, address_id: Optional[str] = None
    ) -> DeliveryStatusResult:
        """Fetch basic delivery ETA and cancellation status."""
        args: dict[str, Any] = {"orderId": order_id}
        if address_id:
            args["addressId"] = address_id
        res = await self._call_mcp_tool("get_delivery_status", args)
        self._parse_error_if_failed(res)
        return parse_delivery_status_response(res.get("data", {}))

    async def track_order(
        self, order_id: str, lat: Optional[float] = None, lng: Optional[float] = None
    ) -> DeliveryTrackingStatus:
        """Fetch real-time delivery tracking status and ETA per official track_order schema."""
        args: dict[str, Any] = {"orderId": order_id}
        if lat is not None and lng is not None:
            args["lat"] = lat
            args["lng"] = lng
        res = await self._call_mcp_tool("track_order", args)
        self._parse_error_if_failed(res)
        return parse_delivery_tracking_response(res.get("data", {}), order_id)

    async def create_address(
        self,
        customer_id: str,
        label: str,
        street: str,
        area: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        phone_number: Optional[str] = None,
        landmark: Optional[str] = None,
        address_tag: Optional[str] = None,
    ) -> DeliveryAddress:
        """Create a new saved delivery address."""
        args: dict[str, Any] = {
            "addressLine": street,
            "label": label,
        }
        if area:
            args["area"] = area
        if city:
            args["city"] = city
        if postal_code:
            args["pincode"] = postal_code
        if latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude
        if phone_number:
            args["phoneNumber"] = phone_number
        if landmark:
            args["landmark"] = landmark
        if address_tag:
            args["addressTag"] = address_tag
        res = await self._call_mcp_tool("create_address", args, customer_id=customer_id)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        addrs = parse_delivery_addresses([data] if isinstance(data, dict) and "addresses" not in data else data)
        if addrs:
            return addrs[0]
        return DeliveryAddress(
            id=str(data.get("id") or data.get("addressId") or "created"),
            label=label,
            street=street,
            area=area,
            city=city,
            postal_code=postal_code,
            latitude=latitude,
            longitude=longitude,
            phone_number=phone_number,
            landmark=landmark,
            address_tag=address_tag,
        )

    async def delete_address(self, address_id: str) -> bool:
        """Delete a saved delivery address."""
        res = await self._call_mcp_tool("delete_address", {"addressId": address_id})
        self._parse_error_if_failed(res)
        return True

    async def list_coupons(self, cart_id: Optional[str] = None) -> list[Coupon]:
        """Fetch available coupons for current active cart."""
        del cart_id
        res = await self._call_mcp_tool("list_coupons", {})
        self._parse_error_if_failed(res)
        return parse_coupons(res.get("data", {}))

    async def apply_coupon(
        self, code: str, cart_id: Optional[str] = None
    ) -> CouponApplyResult:
        """Apply a coupon code to the active cart."""
        del cart_id
        res = await self._call_mcp_tool("apply_coupon", {"couponCode": code})
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        discount = float(data.get("discountAmount", data.get("discount", 0.0)))
        return CouponApplyResult(
            applied=bool(data.get("applied", True)),
            code=code,
            discount_amount=discount,
            message=data.get("message"),
        )

    async def recommend_address(
        self, latitude: Optional[float] = None, longitude: Optional[float] = None
    ) -> AddressRecommendation:
        """Recommend best delivery address based on location or order history."""
        args: dict[str, Any] = {}
        if latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude
        res = await self._call_mcp_tool("recommend_address", args)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        addr_data = data.get("address")
        matched = parse_delivery_addresses([addr_data])[0] if isinstance(addr_data, dict) else None
        return AddressRecommendation(
            recommended_address_id=data.get("recommendedAddressId") or data.get("addressId"),
            confidence=float(data["confidence"]) if data.get("confidence") is not None else None,
            reason=data.get("reason"),
            matched_address=matched,
        )

    async def report_error(
        self, report_id: str, context: Optional[dict[str, Any]] = None
    ) -> ErrorReportResult:
        """Submit diagnostic context for a provider error."""
        args: dict[str, Any] = {"reportId": report_id, "context": context or {}}
        res = await self._call_mcp_tool("report_error", args)
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        return ErrorReportResult(
            report_id=report_id,
            status=str(data.get("status") or "received"),
            message=data.get("message"),
        )
