"""Grocer v1.0 — Native Swiggy Instamart Commerce Adapter.

Handles JSON-RPC 2.0 communication with Swiggy Instamart dark stores (https://mcp.swiggy.com/im).
Calls the live authenticated endpoints with strictly typed Pydantic envelopes.
Fixture playback lives in the test suite, never in production code.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

import httpx

from backend.config import settings
from backend.integrations.commerce.schemas import (
    CartData,
    CheckoutData,
    ClearCartData,
    ConfirmOrderData,
    CreateAddressData,
    DeleteAddressData,
    DeliveryStatusData,
    GetAddressesData,
    ListCouponsData,
    OrderDetailsData,
    OrdersListData,
    PaymentOptionsData,
    PaymentStatusData,
    RecommendAddressData,
    ReportErrorData,
    SearchProductsData,
    ToolEnvelope,
    TrackOrderData,
)

T = TypeVar("T")


class SwiggyAuthExpiredError(Exception):
    """Raised when Swiggy returns 401 Unauthorized (5-day token expired, ADR 0010)."""


# Canonical Hinglish to English grocery translation dictionary
HINGLISH_TRANSLATIONS: dict[str, str] = {
    "doodh": "milk",
    "pyaz": "onion",
    "kanda": "onion",
    "atta": "atta",
    "cheeni": "sugar",
    "shakkar": "sugar",
    "dahi": "curd",
    "adrak": "ginger",
    "lasun": "garlic",
    "lahsun": "garlic",
    "chawal": "rice",
    "namak": "salt",
    "tel": "oil",
    "haldi": "turmeric",
    "mirch": "chili",
    "aloo": "potato",
    "batata": "potato",
}

# Common customer typos dictionary for dark-store search normalization
TYPO_CORRECTIONS: dict[str, str] = {
    "brd": "bread",
    "bred": "bread",
    "milkk": "milk",
    "mlk": "milk",
    "magi": "maggi",
    "maggie": "maggi",
    "biskit": "biscuit",
    "biskoot": "biscuit",
    "biscit": "biscuit",
    "potatos": "potato",
    "oninos": "onion",
}


def normalize_query(query: str) -> str:
    """Normalize user search query by correcting typos and translating Hinglish."""
    q = query.strip().lower()
    tokens = re.findall(r"\b\w+\b", q)
    normalized_tokens: list[str] = []
    for token in tokens:
        token = TYPO_CORRECTIONS.get(token, token)
        token = HINGLISH_TRANSLATIONS.get(token, token)
        normalized_tokens.append(token)
    return " ".join(normalized_tokens)


class SwiggyClient:
    """Live Swiggy Instamart MCP Client & Staging Contract Runner."""

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.base_url = base_url or settings.SWIGGY_MCP_BASE_URL
        self.auth_token = auth_token

    def search_products(
        self,
        query: str,
        address_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        offset: int = 0,
    ) -> SearchProductsData:
        """Search products in the hyper-local Instamart dark store."""
        args: dict[str, Any] = {"query": query, "offset": offset}
        if address_id:
            args["addressId"] = address_id
        elif latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude

        return self.call_remote_tool("search_products", args, SearchProductsData)

    def call_remote_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        model_cls: type[T],
    ) -> T:
        """Execute a live MCP tool call."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{self.base_url}/im", headers=headers, json=payload)
            if resp.status_code == 401:
                raise SwiggyAuthExpiredError("Swiggy OAuth token has expired (401)")
            resp.raise_for_status()
            data = resp.json()

            # Auth failures can arrive as HTTP 200 + JSON-RPC -32001.
            rpc_error = data.get("error") if isinstance(data, dict) else None
            if isinstance(rpc_error, dict) and rpc_error.get("code") == -32001:
                raise SwiggyAuthExpiredError("Swiggy OAuth session expired (JSON-RPC -32001)")

            # Handle native Swiggy MCP structuredContent
            if "result" in data and "structuredContent" in data["result"]:
                sc = data["result"]["structuredContent"]
                if sc:
                    return model_cls.model_validate(sc)

            # Handle JSON-RPC envelope with embedded JSON text
            if "result" in data and "content" in data["result"]:
                content = data["result"]["content"]
                if content and "text" in content[0]:
                    try:
                        envelope = ToolEnvelope[model_cls].model_validate(
                            json.loads(content[0]["text"])
                        )
                        if envelope.data is not None:
                            return envelope.data
                    except (json.JSONDecodeError, ValueError):
                        pass

            envelope = ToolEnvelope[model_cls].model_validate(data)
            if envelope.data is not None:
                return envelope.data
            raise ValueError(f"Empty data payload returned for tool {tool_name}")

    def get_cart(self, address_id: str | None = None) -> CartData:
        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        return self.call_remote_tool("get_cart", args, CartData)

    def update_cart(
        self,
        items: list[dict[str, Any]],
        address_id: str | None = None,
    ) -> CartData:
        args: dict[str, Any] = {"items": items}
        if address_id:
            args["selectedAddressId"] = address_id
        return self.call_remote_tool("update_cart", args, CartData)

    def clear_cart(self) -> ClearCartData:
        return self.call_remote_tool("clear_cart", {}, ClearCartData)

    def get_addresses(self, page: int = 1, page_size: int = 10) -> GetAddressesData:
        args = {"page": page, "pageSize": page_size}
        return self.call_remote_tool("get_addresses", args, GetAddressesData)

    def create_address(
        self,
        full_address: str,
        address_line: str,
        address_line2: str,
        city: str,
        postal_code: str,
        address_category: str = "HOME",
        user_name: str = "",
        user_phone: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        locality: str | None = None,
        address_tag: str | None = None,
    ) -> CreateAddressData:
        args: dict[str, Any] = {
            "fullAddress": full_address,
            "addressLine": address_line,
            "addressLine2": address_line2,
            "city": city,
            "postalCode": postal_code,
            "addressCategory": address_category,
            "userName": user_name,
            "userPhone": user_phone,
        }
        if latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude
        if locality:
            args["locality"] = locality
        if address_tag:
            args["addressTag"] = address_tag
        return self.call_remote_tool("create_address", args, CreateAddressData)

    def delete_address(self, address_id: str) -> DeleteAddressData:
        return self.call_remote_tool(
            "delete_address", {"addressId": address_id}, DeleteAddressData
        )

    def recommend_address(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        query: str | None = None,
    ) -> RecommendAddressData:
        args: dict[str, Any] = {}
        if latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude
        if query:
            args["query"] = query
        return self.call_remote_tool("recommend_address", args, RecommendAddressData)

    def your_go_to_items(self, address_id: str | None = None) -> SearchProductsData:
        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        return self.call_remote_tool("your_go_to_items", args, SearchProductsData)

    def get_orders(
        self,
        count: int = 10,
        order_type: str = "INSTAMART",
        active_only: bool = False,
    ) -> OrdersListData:
        args: dict[str, Any] = {
            "count": count,
            "orderType": order_type,
            "activeOnly": active_only,
        }
        return self.call_remote_tool("get_orders", args, OrdersListData)

    def checkout(
        self,
        payment_method: str = "UPI",
        address_id: str | None = None,
        intent_app: str | None = None,
    ) -> CheckoutData:
        args: dict[str, Any] = {"paymentMethod": payment_method}
        if address_id:
            args["addressId"] = address_id
        # Swiggy rejects UPI checkout without an intent app or a QR request.
        if payment_method.upper() == "UPI":
            if intent_app:
                args["intentApp"] = intent_app
            else:
                args["generateUPIQR"] = True
        return self.call_remote_tool("checkout", args, CheckoutData)

    def check_payment_status(
        self,
        paas_id: str | None = None,
        order_id: str | None = None,
    ) -> PaymentStatusData:
        args: dict[str, Any] = {}
        if paas_id:
            args["paasId"] = paas_id
        if order_id:
            args["orderId"] = order_id
        return self.call_remote_tool("check_payment_status", args, PaymentStatusData)

    def track_order(self, order_id: str, lat: float, lng: float) -> TrackOrderData:
        return self.call_remote_tool(
            "track_order", {"orderId": order_id, "lat": lat, "lng": lng}, TrackOrderData
        )

    def get_order_details(self, order_id: str) -> OrderDetailsData:
        return self.call_remote_tool("get_order_details", {"orderId": order_id}, OrderDetailsData)

    def confirm_order(self, order_id: str, paas_id: str | None = None) -> ConfirmOrderData:
        args: dict[str, Any] = {"orderId": order_id}
        if paas_id:
            args["paasId"] = paas_id
        return self.call_remote_tool("confirm_order", args, ConfirmOrderData)

    def list_coupons(self, address_id: str | None = None) -> ListCouponsData:
        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        return self.call_remote_tool("list_coupons", args, ListCouponsData)

    def apply_coupon(self, coupon_code: str) -> CartData:
        return self.call_remote_tool("apply_coupon", {"couponCode": coupon_code}, CartData)

    def get_delivery_status(self, order_id: str) -> DeliveryStatusData:
        return self.call_remote_tool("get_delivery_status", {"orderId": order_id}, DeliveryStatusData)

    def get_payment_options(self, address_id: str | None = None) -> PaymentOptionsData:
        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        return self.call_remote_tool("get_payment_options", args, PaymentOptionsData)

    def report_error(
        self,
        tool: str,
        error_message: str,
        flow_description: str | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> ReportErrorData:
        args: dict[str, Any] = {"tool": tool, "errorMessage": error_message}
        if flow_description:
            args["flowDescription"] = flow_description
        if tool_context:
            args["toolContext"] = tool_context
        return self.call_remote_tool("report_error", args, ReportErrorData)
