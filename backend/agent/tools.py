"""Swiggy MCP Tools registry for LLM Function Calling."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    CommerceCart,
    CommerceProductItem,
)
from backend.integrations.commerce.exceptions import (
    ProviderAuthError,
    ProviderRateLimitedError,
)

logger = logging.getLogger("grocer.agent.tools")

_CATALOG_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

from backend.agent.formatters import _format_inr, format_cart_receipt
from backend.agent.catalog_ranker import rank_and_select_best_variant
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.basket_manager import execute_manage_basket, execute_quick_add_items
from backend.agent.cart_actions import (
    execute_add_selected_variants,
    execute_restore_cart,
    execute_update_cart,
)
from backend.agent.address_tools import (
    execute_get_saved_addresses,
    execute_select_delivery_address,
)


class SwiggyAgentTools:
    """Wraps CommercePort into clean, high-signal tools for the LLM agent."""

    def __init__(self, commerce: CommercePort) -> None:
        self.commerce = commerce

    async def search_products(
        self, query: str, address_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Search products available on Swiggy Instamart for a given address."""
        if not address_id:
            return {
                "success": False,
                "error": "Address ID is required to search the local store catalogue.",
                "retryable": False,
            }
        try:
            products: list[CommerceProductItem] = await self.commerce.search_products(
                address_id=address_id, query=query
            )
            results = []
            for p in products:
                in_stock_variants = [v for v in p.variants if v.in_stock is not False]
                if not in_stock_variants:
                    continue
                results.append({
                    "product_id": p.product_id,
                    "brand": p.brand,
                    "name": p.name,
                    "category": getattr(p, "category", None),
                    "variants": [
                        {
                            "spin_id": v.spin_id,
                            "sku_id": v.sku_id,
                            "name": v.name,
                            "pack_size": v.pack_size,
                            "price": v.price,
                            "mrp": v.mrp,
                            "formatted_price": _format_inr(v.price),
                            "savings": f"{_format_inr(v.mrp - v.price)} off" if v.mrp and v.mrp > v.price else None,
                            "in_stock": v.in_stock,
                            "max_quantity": v.max_quantity,
                            "max_quantity_message": v.max_quantity_message,
                        }
                        for v in in_stock_variants
                    ],
                    "similar_products": [
                        {"product_id": similar.product_id, "name": similar.name,
                         "brand": similar.brand,
                         "variants": [{"spin_id": variant.spin_id, "sku_id": variant.sku_id,
                                       "pack_size": variant.pack_size, "price": variant.price,
                                       "in_stock": variant.in_stock}
                                      for variant in similar.variants if variant.in_stock is not False]}
                        for similar in p.similar_products[:3]
                        if any(variant.in_stock is not False for variant in similar.variants)
                    ],
                })
                if len(results) == 10:
                    break
            return {
                "success": True,
                "query": query,
                "count": len(results),
                "products": results,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc), "retryable": False}
        except ProviderRateLimitedError as exc:
            return {"success": False, "error": "RATE_LIMITED", "retryable": False,
                    "retry_after_seconds": exc.retry_after_seconds}
        except Exception as exc:
            logger.warning("search_products failed for query=%s: %s", query, exc)
            return {"success": False, "error": str(exc), "retryable": True}

    async def batch_search_products(
        self, queries: list[str], address_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Search multiple grocery items concurrently against Swiggy Instamart."""
        if not address_id:
            return {
                "success": False,
                "error": "Address ID is required to search the local store catalogue.",
                "retryable": False,
            }
        clean_queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        if not clean_queries:
            return {"success": False, "error": "No valid search queries provided."}
        if len(clean_queries) > 45:
            return {"success": False, "error": "TOO_MANY_QUERIES", "retryable": False}

        async def _search_one(q: str) -> dict[str, Any]:
            cache_key = (q.casefold().strip(), str(address_id or ""))
            now = time.time()
            if cache_key in _CATALOG_CACHE:
                cached_time, cached_items = _CATALOG_CACHE[cache_key]
                if now - cached_time < 300.0:
                    return {"query": q, "products": cached_items}

            try:
                res = await self.search_products(q, address_id)
                if not res.get("success"):
                    return {"query": q, "products": [], "error": res.get("error") or "SEARCH_UNAVAILABLE",
                            "retry_after_seconds": res.get("retry_after_seconds")}
                compact_prods = []
                for p in res.get("products", [])[:5]:
                    for v in p.get("variants", []):
                        compact_prods.append({
                            "name": v.get("name") or p.get("name"),
                            "product_name": p.get("name"),
                            "category": p.get("category"),
                            "brand": p.get("brand"),
                            "spin_id": v.get("spin_id"),
                            "sku_id": v.get("sku_id"),
                            "pack_size": v.get("pack_size"),
                            "price": v.get("price"),
                            "formatted_price": v.get("formatted_price"),
                            "max_quantity": v.get("max_quantity"),
                        })
                _CATALOG_CACHE[cache_key] = (now, compact_prods)
                return {"query": q, "products": compact_prods}
            except Exception as exc:
                return {"query": q, "products": [], "error": str(exc)}

        sem = asyncio.Semaphore(3)

        async def _bounded_search(q: str) -> dict[str, Any]:
            async with sem:
                return await _search_one(q)

        batch_results = await asyncio.gather(*[_bounded_search(q) for q in clean_queries])
        critical_failed = (next((item for item in batch_results if item.get("error") == "RATE_LIMITED"), None)
                           or next((item for item in batch_results if item.get("error") == "AUTH_EXPIRED"), None))
        if critical_failed:
            return {"success": False, "error": critical_failed["error"], "retryable": False,
                    "retry_after_seconds": critical_failed.get("retry_after_seconds")}
        return {
            "success": True,
            "results": list(batch_results),
        }

    def select_best_variant(
        self,
        query: str,
        products: list[dict[str, Any]],
        preferred_pack_size: str = "",
    ) -> Optional[dict[str, Any]]:
        """Deterministically score and pick the single best product variant."""
        return rank_and_select_best_variant(query, products, preferred_pack_size)

    async def manage_basket(
        self,
        address_id: str,
        add: Optional[list[dict[str, Any]]] = None,
        remove: Optional[list[str]] = None,
        set_quantity: Optional[list[dict[str, Any]]] = None,
        current_cart: Optional[CommerceCart] = None,
        delivery_location: str = "Home",
        budget_cap_inr: Optional[float] = None,
        ingredient_budget_inr: Optional[float] = None,
        ingredient_extras_text: str = "",
        ingredient_spin_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Atomically manage Swiggy Instamart basket: add items, remove items, or adjust quantities in a single turn."""
        return await execute_manage_basket(
            tools=self,
            address_id=address_id,
            add=add,
            remove=remove,
            set_quantity=set_quantity,
            current_cart=current_cart,
            delivery_location=delivery_location,
            budget_cap_inr=budget_cap_inr,
            ingredient_budget_inr=ingredient_budget_inr,
            ingredient_extras_text=ingredient_extras_text,
            ingredient_spin_ids=ingredient_spin_ids,
        )

    async def quick_add_items(
        self,
        items: list[dict[str, Any]],
        address_id: str,
        current_cart: Optional[CommerceCart] = None,
        delivery_location: str = "Home",
        budget_cap_inr: Optional[float] = None,
        ingredient_budget_inr: Optional[float] = None,
        ingredient_extras_text: str = "",
        ingredient_spin_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Automatically find and add the best matching in-stock grocery items to the cart."""
        return await execute_quick_add_items(
            tools=self,
            items=items,
            address_id=address_id,
            current_cart=current_cart,
            delivery_location=delivery_location,
            budget_cap_inr=budget_cap_inr,
            ingredient_budget_inr=ingredient_budget_inr,
            ingredient_extras_text=ingredient_extras_text,
            ingredient_spin_ids=ingredient_spin_ids,
        )


    async def get_saved_addresses(self, customer_id: str) -> dict[str, Any]:
        """Retrieve the user's saved delivery addresses from Swiggy."""
        return await execute_get_saved_addresses(self.commerce, customer_id)

    async def select_delivery_address(
        self, customer_id: str, address_id: str
    ) -> dict[str, Any]:
        """Validate and select an active delivery address from saved addresses."""
        return await execute_select_delivery_address(self.commerce, customer_id, address_id)

    async def get_cart(self, delivery_location: str = "Home") -> dict[str, Any]:
        """Fetch current Swiggy Instamart cart contents and pre-computed pricing."""
        try:
            cart: CommerceCart = await self.commerce.get_cart()
            items = [
                {
                    "spin_id": item.spin_id,
                    "sku_id": item.sku_id,
                    "name": item.name,
                    "pack_size": item.pack_size,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "formatted_price": _format_inr(item.total_price),
                }
                for item in cart.items
            ]
            packaging_and_handling = round(cart.packaging_fee + cart.handling_fee, 2)
            total_fees = round(cart.delivery_fee + packaging_and_handling + cart.taxes, 2)
            return {
                "success": True,
                "cart_id": cart.cart_id,
                "item_count": len(items),
                "items": items,
                "item_total": cart.item_total,
                "delivery_fee": cart.delivery_fee,
                "packaging_fee": cart.packaging_fee,
                "handling_fee": cart.handling_fee,
                "taxes": cart.taxes,
                "total_fees": total_fees,
                "discount": cart.discount,
                "grand_total": cart.grand_total,
                "is_serviceable": cart.is_serviceable,
                "min_order_threshold": cart.min_order_threshold,
                "address_warning": cart.address_warning,
                "formatted_item_total": _format_inr(cart.item_total),
                "formatted_delivery_fee": _format_inr(cart.delivery_fee) if cart.delivery_fee > 0 else "FREE (₹0)",
                "formatted_packaging_fee": _format_inr(cart.packaging_fee),
                "formatted_handling_fee": _format_inr(cart.handling_fee),
                "formatted_packaging_and_handling": _format_inr(packaging_and_handling),
                "formatted_taxes": _format_inr(cart.taxes),
                "formatted_total_fees": _format_inr(total_fees),
                "formatted_grand_total": _format_inr(cart.grand_total),
                "formatted_receipt": format_cart_receipt(cart, delivery_location),
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("get_cart failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def update_cart(
        self,
        items: list[dict[str, Any]],
        address_id: str,
        delivery_location: str = "Home",
        ingredient_budget_inr: Optional[float] = None,
        ingredient_spin_ids: list[str] | None = None,
        expected_cart_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update Swiggy Instamart cart by deterministically merging item updates with active cart items."""
        return await execute_update_cart(
            tools=self,
            items=items,
            address_id=address_id,
            delivery_location=delivery_location,
            ingredient_budget_inr=ingredient_budget_inr,
            ingredient_spin_ids=ingredient_spin_ids,
            expected_cart_state=expected_cart_state,
        )

    async def _restore_cart(self, before: CommerceCart, after: CommerceCart, address_id: str) -> bool:
        return await execute_restore_cart(self.commerce, before, after, address_id)

    async def add_selected_variants(
        self,
        selected: list[dict[str, Any]],
        address_id: str,
        current_cart: CommerceCart,
        expected_cart_state: dict[str, Any],
        delivery_location: str = "Home",
        budget_cap_inr: float | None = None,
        ingredient_budget_inr: float | None = None,
        ingredient_extras_text: str = "",
        ingredient_spin_ids: list[str] | None = None,
        extra_updates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Apply customer-chosen, freshly verified SKUs and extra updates in one atomic cart update."""
        return await execute_add_selected_variants(
            tools=self,
            selected=selected,
            address_id=address_id,
            current_cart=current_cart,
            expected_cart_state=expected_cart_state,
            delivery_location=delivery_location,
            budget_cap_inr=budget_cap_inr,
            ingredient_budget_inr=ingredient_budget_inr,
            ingredient_extras_text=ingredient_extras_text,
            ingredient_spin_ids=ingredient_spin_ids,
            extra_updates=extra_updates,
        )

    async def suggest_grocery_items(
        self, items: list[dict[str, Any]], address_id: str,
    ) -> dict[str, Any]:
        """Ground optional suggestions in the catalogue without changing the basket."""
        queries = [str(item.get("query", "")).strip() for item in items if isinstance(item, dict)]
        search = await self.batch_search_products(queries, address_id)
        suggestions: list[str] = []
        restricted: list[str] = []
        for result in search.get("results", []):
            query = str(result.get("query", ""))
            products = result.get("products") or []
            if not products:
                continue
            product = products[0]
            if is_restricted_medical_product(str(product.get("name") or ""), product.get("category")):
                restricted.append(query)
            else:
                suggestions.append(str(product.get("name") or query))
        return {"success": True, "suggestions": suggestions, "restricted_items": restricted}

    async def clear_cart(self) -> dict[str, Any]:
        """Empty the active Swiggy Instamart cart."""
        try:
            await self.commerce.clear_cart()
            return {"success": True, "message": "Cart cleared."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def checkout(
        self,
        cart_id: str = "",
        address_id: str = "",
        payment_method: str = "UPI",
        payment_option_kind: Optional[str] = None,
        payment_option_id: Optional[str] = None,
        is_user_confirmed: bool = False,
        budget_inr: Optional[float] = None,
        expected_cart_fingerprint: Optional[str] = None,
    ) -> dict[str, Any]:
        """Place the final order on Swiggy Instamart. STRICTLY server-side gated."""
        return await execute_gated_checkout(
            commerce=self.commerce,
            cart_id=cart_id,
            address_id=address_id,
            payment_method=payment_method,
            payment_option_kind=payment_option_kind,
            payment_option_id=payment_option_id,
            is_user_confirmed=is_user_confirmed,
            budget_inr=budget_inr,
            expected_cart_fingerprint=expected_cart_fingerprint,
        )

    async def track_order(self, order_id: str, lat: Optional[float] = None, lng: Optional[float] = None) -> dict[str, Any]:
        """Track the real-time delivery status and ETA of an existing order."""
        if not order_id:
            return {"success": False, "error": "order_id is required."}
        try:
            if lat is None or lng is None:
                try:
                    addrs = await self.commerce.get_addresses()
                    if addrs:
                        lat = addrs[0].lat
                        lng = addrs[0].lng
                except Exception:
                    pass
            status = await self.commerce.track_order(order_id, lat=lat, lng=lng)
            status_val = status.status.value if hasattr(status.status, "value") else str(status.status)
            return {
                "success": True,
                "order_id": order_id,
                "status": status_val,
                "eta_minutes": status.eta_minutes,
                "eta_text": status.eta_text or (f"~{status.eta_minutes} mins" if status.eta_minutes else None),
                "driver_name": status.driver_name,
                "driver_phone": status.driver_phone,
                "status_message": status.status_message,
            }
        except Exception as exc:
            logger.warning("track_order failed for order_id=%s: %s", order_id, exc)
            return {"success": False, "error": str(exc)}

    async def get_go_to_items(self, address_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch the customer's frequently ordered / usual items from Swiggy Instamart."""
        try:
            items: list[CommerceProductItem] = await self.commerce.get_go_to_items(address_id=address_id or "")
            formatted_products = []
            for item in items[:12]:
                in_stock_variants = [
                    {
                        "spin_id": v.spin_id,
                        "sku_id": v.sku_id or v.spin_id,
                        "name": v.name,
                        "pack_size": v.pack_size,
                        "price": v.price,
                        "formatted_price": _format_inr(v.price),
                        "mrp": v.mrp,
                    }
                    for v in item.variants
                    if v.in_stock
                ]
                if in_stock_variants:
                    formatted_products.append(
                        {
                            "product_id": item.product_id,
                            "name": item.name,
                            "brand": item.brand,
                            "variants": in_stock_variants,
                        }
                    )
            return {
                "success": True,
                "count": len(formatted_products),
                "products": formatted_products,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("get_go_to_items failed: %s", exc)
            return {"success": False, "error": str(exc)}
