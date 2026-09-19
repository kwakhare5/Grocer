"""Swiggy Instamart MCP commerce adapter (Spec Section 5.1, Section 28, & Section 38.9).

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
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Optional

import httpx

from backend.integrations.commerce.exceptions import (
    CommerceError,
    OrderStateUnknownError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    OrderChildResult,
    OrderDetails,
    OrderLineItem,
    OrderSummary,
    PaymentOption,
    PaymentStatusResult,
)
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.swiggy_client import SwiggyMcpClient
from backend.integrations.commerce.swiggy_parsers import (
    build_checkout_order_result,
    build_commerce_cart,
    normalize_existing_order_status,
    normalize_order_status,
    normalize_payment_status,
    parse_child_order,
    parse_delivery_addresses,
    parse_delivery_status_response,
    parse_delivery_tracking_response,
    parse_order_details_response,
    parse_order_items,
    parse_orders_summary,
    parse_payment_options,
    parse_swiggy_products,
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
    ) -> dict[str, Any]:
        """Execute JSON-RPC 2.0 tool call against Swiggy Instamart MCP endpoint."""
        effective_customer = customer_id or self._customer_context.get()
        return await self._client.call_tool(tool_name, arguments, customer_id=effective_customer)

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
        return self._parse_products(raw_items)

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
            {"addressId": address_id, "query": query, "offset": 0},
        )
        self._parse_error_if_failed(res)
        data = res.get("data", {})
        raw_items = data.get("products", data) if isinstance(data, dict) else data
        products = self._parse_products(raw_items)

        if isinstance(data, dict) and "similarProducts" in data:
            similar_raw = data.get("similarProducts", [])
            similar = self._parse_products(similar_raw)
            if products and similar:
                products[0].similar_products = similar

        return products

    def _parse_products(self, raw_items: Any) -> list[CommerceProductItem]:
        """Parse official SearchProduct and variation schemas."""
        return parse_swiggy_products(raw_items)

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        """Fetch current Instamart cart per official get_cart schema."""
        del cart_id
        res = await self._call_mcp_tool("get_cart", {})
        self._parse_error_if_failed(res)
        return self._build_commerce_cart(res.get("data", {}))

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
        for it in items:
            if not it.sku_id:
                try:
                    current_cart_state = await self.get_cart()
                    matched = next((ci for ci in current_cart_state.items if ci.spin_id == it.spin_id and ci.sku_id), None)
                    if matched:
                        it.sku_id = matched.sku_id
                except Exception:
                    pass

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
        reduced_quantity_items = data.get("reducedQuantityItems", []) if isinstance(data, dict) else []
        canonical_cart = await self.get_cart()
        if isinstance(reduced_quantity_items, list):
            canonical_cart.reduced_quantity_items = [
                item for item in reduced_quantity_items if isinstance(item, dict)
            ]
        return canonical_cart

    def _build_commerce_cart(self, data: dict[str, Any], cart_id: Optional[str] = None) -> CommerceCart:
        """Construct CommerceCart domain model from InstamartCart schema."""
        return build_commerce_cart(data, cart_id)

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
            raise CommerceError(
                "UPI checkout requires an exact intent-app or QR selection.",
                provider="swiggy",
                code="AMBIGUOUS_PAYMENT_OPTION",
            )

        try:
            res = await self._call_mcp_tool("checkout", args)
            self._parse_error_if_failed(res)
        except (UpstreamTimeoutError, httpx.TimeoutException) as exc:
            logger.warning("Checkout upstream timeout/5xx. Checking order state before acting: %s", exc)
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
        """Check UPI or gateway payment status for an initiated checkout."""
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
        return normalize_payment_status(raw_status)

    @staticmethod
    def _normalize_order_status(
        raw_status: Optional[str],
        *,
        order_count: int,
        success_count: int,
        failure_count: int,
        all_succeeded: bool,
    ) -> str:
        return normalize_order_status(
            raw_status,
            order_count=order_count,
            success_count=success_count,
            failure_count=failure_count,
            all_succeeded=all_succeeded,
        )

    def _parse_child_order(self, raw: dict[str, Any]) -> OrderChildResult:
        return parse_child_order(raw)

    @staticmethod
    def _parse_order_items(raw_items: Any) -> list[OrderLineItem]:
        return parse_order_items(raw_items)

    @classmethod
    def _normalize_existing_order_status(cls, raw_status: Any) -> str:
        return normalize_existing_order_status(raw_status)

    async def get_orders(
        self, count: int = 10, active_only: bool = False
    ) -> list[OrderSummary]:
        """List past or active Instamart orders."""
        args: dict[str, Any] = {
            "count": max(1, min(count, 20)),
            "orderType": "INSTAMART",
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
        self, order_id: str, address_id: str
    ) -> DeliveryStatusResult:
        """Fetch basic delivery ETA and cancellation status."""
        res = await self._call_mcp_tool(
            "get_delivery_status", {"orderId": order_id, "addressId": address_id}
        )
        self._parse_error_if_failed(res)
        return parse_delivery_status_response(res.get("data", {}))

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
        return parse_delivery_tracking_response(res.get("data", {}), order_id)
