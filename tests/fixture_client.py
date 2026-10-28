"""Fixture-backed Swiggy client for contract tests. Never imported by backend code."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any, TypeVar

from backend.integrations.commerce.schemas import (
    CartData,
    CartItem,
    CheckoutData,
    ClearCartData,
    SearchProduct,
    SearchProductsData,
    ToolEnvelope,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient, normalize_query

T = TypeVar("T")


class FixtureSwiggyClient(SwiggyClient):
    """Replays committed Swiggy responses and simulates the staging cart."""

    def __init__(
        self,
        fixtures_dir: Path | None = None,
        catalog_data: SearchProductsData | None = None,
        base_url: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        super().__init__(base_url=base_url, auth_token=auth_token)
        self.fixtures_dir = fixtures_dir
        self.catalog_data = catalog_data
        self._staging_cart: CartData | None = None
        self._cleared_cart = False
        self.last_update_items: list[dict[str, Any]] = []
        self.last_checkout_args: dict[str, Any] = {}

    def search_products(
        self,
        query: str,
        address_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        offset: int = 0,
    ) -> SearchProductsData:
        if self.catalog_data is not None:
            return self._search_local_catalog(query)
        return super().search_products(
            query=query,
            address_id=address_id,
            latitude=latitude,
            longitude=longitude,
            offset=offset,
        )

    def _search_local_catalog(self, query: str) -> SearchProductsData:
        if self.catalog_data is None:
            raise ValueError("catalog_data is required for local catalog search")
        norm_q = normalize_query(query)
        q_tokens = norm_q.split()

        matching_products: list[SearchProduct] = []
        for prod in self.catalog_data.products:
            prod_name = prod.displayName.lower()
            prod_brand = (prod.brand or "").lower()
            matched = False

            for token in q_tokens:
                if (
                    token in prod_name
                    or token in prod_brand
                    or any(token in v.displayName.lower() for v in prod.variations)
                    or any(
                        token in (v.brandName or "").lower()
                        for v in prod.variations
                    )
                ):
                    matched = True
                    break

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
        if self.fixtures_dir is None:
            raise ValueError("fixtures_dir is required for fixture tool calls")
        fixture_file = self.fixtures_dir / f"{tool_name}.json"
        if not fixture_file.exists():
            raise FileNotFoundError(
                f"Fixture {tool_name}.json not found in {self.fixtures_dir}"
            )

        raw_data = json.loads(fixture_file.read_text(encoding="utf-8"))
        envelope = ToolEnvelope[model_cls].model_validate(raw_data)
        if envelope.data is None:
            raise ValueError(f"Empty data in fixture {tool_name}.json")
        return envelope.data

    def get_cart(self, address_id: str | None = None) -> CartData:
        if self._cleared_cart:
            return CartData(
                cartId="cart_empty",
                cartTotalAmount="0.00",
                items=[],
                billBreakdown={
                    "lineItems": [{"label": "Item Total", "value": "₹0.00"}],
                    "toPay": {"label": "To Pay", "value": "₹0.00"},
                },
            )
        if self._staging_cart is not None:
            return self._staging_cart

        args: dict[str, Any] = {}
        if address_id:
            args["addressId"] = address_id
        cart = self.call_remote_tool("get_cart", args, CartData)
        if self._staging_cart is None:
            self._staging_cart = cart
        return cart

    def update_cart(
        self,
        items: list[dict[str, Any]],
        address_id: str | None = None,
    ) -> CartData:
        self.last_update_items = items
        self._cleared_cart = False

        cart_items: list[CartItem] = []
        removed_items: list[CartItem] = []
        total_paise = 0

        for it in items:
            spin_id = it.get("spinId", "")
            qty = it.get("quantity", 1)
            price = float(it.get("price", 50.0))
            if "eggs_6" in spin_id:
                removed_items.append(
                    CartItem(
                        spinId=spin_id,
                        skuId=f"sku_{spin_id}",
                        productId=f"prod_{spin_id}",
                        itemName=it.get("itemName", spin_id),
                        quantity=qty,
                        isInStockAndAvailable=False,
                        mrp=price,
                        discountedFinalPrice=price,
                    )
                )
            else:
                cart_items.append(
                    CartItem(
                        spinId=spin_id,
                        skuId=f"sku_{spin_id}",
                        productId=f"prod_{spin_id}",
                        itemName=it.get("itemName", spin_id),
                        quantity=qty,
                        isInStockAndAvailable=True,
                        mrp=price,
                        discountedFinalPrice=price,
                    )
                )
                total_paise += round(price * qty * 100)

        total_rs = f"{total_paise // 100}.{total_paise % 100:02d}"
        to_pay_paise = total_paise + 500
        to_pay_rs = f"{to_pay_paise // 100}.{to_pay_paise % 100:02d}"
        self._staging_cart = CartData(
            cartId="cart_staging_live",
            cartTotalAmount=total_rs,
            items=cart_items,
            billBreakdown={
                "lineItems": [
                    {"label": "Item Total", "value": f"₹{total_rs}"},
                    {"label": "Handling Charge", "value": "₹5.00"},
                ],
                "toPay": {"label": "To Pay", "value": f"₹{to_pay_rs}"},
            },
            removedOutOfStockItems=removed_items,
        )
        return self._staging_cart

    def clear_cart(self) -> ClearCartData:
        self._cleared_cart = True
        self._staging_cart = None
        return self.call_remote_tool("clear_cart", {}, ClearCartData)

    def apply_coupon(self, coupon_code: str) -> CartData:
        if not coupon_code:
            self._staging_cart = None
            return self.get_cart()
        cart = self.call_remote_tool("apply_coupon", {"couponCode": coupon_code}, CartData)
        self._staging_cart = cart
        return cart

    def checkout(
        self,
        payment_method: str = "UPI",
        address_id: str | None = None,
        intent_app: str | None = None,
    ) -> CheckoutData:
        args: dict[str, Any] = {"paymentMethod": payment_method}
        if address_id:
            args["addressId"] = address_id
        if payment_method.upper() == "UPI":
            if intent_app:
                args["intentApp"] = intent_app
            else:
                args["generateUPIQR"] = True
        self.last_checkout_args = args
        return self.call_remote_tool("checkout", args, CheckoutData)
