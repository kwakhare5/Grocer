"""Grocer v1.0 — Native Swiggy Instamart Commerce Adapter.

Handles JSON-RPC 2.0 communication with Swiggy Instamart dark stores (https://mcp.swiggy.com/im).
Uses real dark-store staging fixtures or live authenticated endpoints.
Zero fake mocks; strictly typed Pydantic envelopes.
"""

from __future__ import annotations

import difflib
import json
import re
from typing import Any, TypeVar

import httpx

from backend.config import settings
from backend.integrations.commerce.schemas import (
    CartData,
    ClearCartData,
    CreateAddressData,
    DeleteAddressData,
    GetAddressesData,
    OrdersListData,
    RecommendAddressData,
    SearchProduct,
    SearchProductsData,
    ToolEnvelope,
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
    # Strip punctuation
    tokens = re.findall(r"\b\w+\b", q)
    normalized_tokens: list[str] = []
    for token in tokens:
        # Check typos
        token = TYPO_CORRECTIONS.get(token, token)
        # Check Hinglish
        token = HINGLISH_TRANSLATIONS.get(token, token)
        normalized_tokens.append(token)
    return " ".join(normalized_tokens)


class SwiggyClient:
    """Live Swiggy Instamart MCP Client."""

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
        catalog_data: SearchProductsData | None = None,
    ) -> None:
        self.base_url = base_url or settings.SWIGGY_MCP_BASE_URL
        self.auth_token = auth_token
        self.catalog_data = catalog_data

    def search_products(
        self,
        query: str,
        address_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        offset: int = 0,
    ) -> SearchProductsData:
        """Search products in the hyper-local Instamart dark store.

        If catalog_data fixture is provided, performs grounded multi-attribute search.
        Otherwise calls Swiggy MCP JSON-RPC 2.0 endpoint.
        """
        if self.catalog_data is not None:
            return self._search_local_catalog(query)

        args: dict[str, Any] = {"query": query, "offset": offset}
        if address_id:
            args["addressId"] = address_id
        elif latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude

        return self.call_remote_tool("search_products", args, SearchProductsData)

    def _search_local_catalog(self, query: str) -> SearchProductsData:
        """Search against committed staging dark-store catalog fixture."""
        if self.catalog_data is None:
            raise ValueError(
                "Local catalog search requested but catalog_data fixture is None"
            )
        norm_q = normalize_query(query)
        q_tokens = norm_q.split()

        matching_products: list[SearchProduct] = []

        for prod in self.catalog_data.products:
            prod_name = prod.displayName.lower()
            prod_brand = (prod.brand or "").lower()
            matched = False

            # Check if any token matches product or variation
            for token in q_tokens:
                if (
                    token in prod_name
                    or token in prod_brand
                    or any(token in v.displayName.lower() for v in prod.variations)
                    or any(
                        token in (v.brandName or "").lower() for v in prod.variations
                    )
                ):
                    matched = True
                    break

            # Also check fuzzy matching for brand/product names
            if not matched:
                for candidate_text in [prod_name, prod_brand] + [
                    v.displayName.lower() for v in prod.variations
                ]:
                    ratio = difflib.SequenceMatcher(
                        None, norm_q, candidate_text
                    ).ratio()
                    if ratio > 0.6:
                        matched = True
                        break

            if matched:
                matching_products.append(prod)

        return SearchProductsData(
            nextOffset="0",
            products=matching_products,
            similarProducts=[],
        )

    def call_remote_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        model_cls: type[T],
    ) -> T:
        """Execute JSON-RPC 2.0 tools/call to Swiggy MCP server."""
        headers = {
            "Content-Type": "application/json",
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

            # Handle JSON-RPC envelope or direct tool envelope
            if "result" in data and "content" in data["result"]:
                content = data["result"]["content"]
                if content and "text" in content[0]:
                    envelope = ToolEnvelope[model_cls].model_validate(
                        json.loads(content[0]["text"])
                    )
                    if envelope.data is not None:
                        return envelope.data

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
            args["addressId"] = address_id
        return self.call_remote_tool("update_cart", args, CartData)

    def clear_cart(self) -> ClearCartData:
        return self.call_remote_tool("clear_cart", {}, ClearCartData)

    def get_addresses(self, page: int = 1, page_size: int = 10) -> GetAddressesData:
        args = {"page": page, "pageSize": page_size}
        return self.call_remote_tool("get_addresses", args, GetAddressesData)

    def create_address(
        self,
        address_line: str,
        latitude: float,
        longitude: float,
        tag: str = "Home",
    ) -> CreateAddressData:
        args = {
            "addressLine": address_line,
            "latitude": latitude,
            "longitude": longitude,
            "addressTag": tag,
        }
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

    def get_orders(self, offset: int = 0, limit: int = 10) -> OrdersListData:
        args = {"offset": offset, "limit": limit}
        return self.call_remote_tool("get_orders", args, OrdersListData)
