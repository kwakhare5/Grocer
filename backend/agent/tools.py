"""Swiggy MCP Tools registry for LLM Function Calling."""
from __future__ import annotations
from decimal import Decimal
from backend.agent.approval import cart_fingerprint
from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.exceptions import (
    CartExpiredError,
    ItemOutOfStockError,
)
from backend.integrations.commerce.models import (
    CartItemUpdate,
)

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

from backend.agent.formatters import _format_inr, format_cart_receipt
from backend.agent.gemini import GeminiClient
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.address_tools import (
    execute_get_saved_addresses,
    execute_select_delivery_address,
)
from backend.config import settings


class AddedItem(str):
    """Product name string preserving candidate pick reason, query, and dictionary access."""
    name: str
    reason: str
    query: str

    def __new__(cls, name: str, reason: str = "", query: str = ""):
        obj = super().__new__(cls, name)
        obj.name = name
        obj.reason = reason
        obj.query = query
        return obj

    def get(self, key: str, default: Any = None) -> Any:
        if key == "name":
            return self.name
        if key == "reason":
            return self.reason
        if key == "query":
            return self.query
        return default

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key == "name":
                return self.name
            if key == "reason":
                return self.reason
            if key == "query":
                return self.query
        return super().__getitem__(key)


PRODUCT_SELECTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "action": {
            "type": "STRING",
            "enum": ["pick", "ask"],
            "description": "'pick' to select a candidate ID, or 'ask' if clarification is needed from the customer.",
        },
        "candidate_id": {
            "type": "STRING",
            "description": "The candidate ID (e.g. '1', '2', ...) chosen when action is 'pick'.",
        },
        "question": {
            "type": "STRING",
            "description": "The concise clarification question to ask the customer when action is 'ask'.",
        },
        "reason": {
            "type": "STRING",
            "description": "Short explanation for why this item was picked or why clarification is needed.",
        },
    },
    "required": ["action", "reason"],
}


def _extract_candidates(raw_prods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    cand_id = 1
    for p in raw_prods:
        variants = p.get("variants")
        if variants and isinstance(variants, list):
            for v in variants:
                if not isinstance(v, dict):
                    continue
                if is_restricted_medical_product(str(v.get("name") or p.get("name") or ""), str(p.get("category") or "")):
                    continue
                in_stock_val = v.get("in_stock")
                if in_stock_val is None:
                    in_stock_val = v.get("is_available")

                raw_price = v.get("price")
                try:
                    price_float = float(raw_price) if raw_price is not None else 0.0
                except (ValueError, TypeError):
                    price_float = 0.0

                candidates.append({
                    "candidate_id": str(cand_id),
                    "product_id": p.get("product_id"),
                    "name": v.get("name") or p.get("name") or "",
                    "brand": p.get("brand"),
                    "category": p.get("category"),
                    "pack_size": v.get("pack_size") or "",
                    "price": price_float,
                    "in_stock": in_stock_val,
                    "spin_id": v.get("spin_id") or p.get("spin_id"),
                    "sku_id": v.get("sku_id") or v.get("spin_id") or p.get("sku_id"),
                    "max_quantity": v.get("max_quantity"),
                })
                cand_id += 1
                if len(candidates) >= 10:
                    break
        else:
            if is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or "")):
                continue
            in_stock_val = p.get("in_stock")
            if in_stock_val is None:
                in_stock_val = p.get("is_available")

            raw_price = p.get("price")
            try:
                price_float = float(raw_price) if raw_price is not None else 0.0
            except (ValueError, TypeError):
                price_float = 0.0

            candidates.append({
                "candidate_id": str(cand_id),
                "product_id": p.get("product_id"),
                "name": p.get("name") or "",
                "brand": p.get("brand"),
                "category": p.get("category"),
                "pack_size": p.get("pack_size") or "",
                "price": price_float,
                "in_stock": in_stock_val,
                "spin_id": p.get("spin_id"),
                "sku_id": p.get("sku_id") or p.get("spin_id"),
                "max_quantity": p.get("max_quantity"),
            })
            cand_id += 1
        if len(candidates) >= 10:
            break
    return candidates


def _build_product_selection_prompt(
    query: str,
    candidates: list[dict[str, Any]],
    preferred_pack_size: str = "",
) -> str:
    cand_lines = []
    for c in candidates:
        stock_val = c.get("in_stock")
        if stock_val is True:
            stock_info = " | Status: In Stock"
        else:
            stock_info = ""  # unknown stock is None, shown only when known True
        brand_str = f" | Brand: {c['brand']}" if c.get("brand") else ""
        pack_str = f" | Pack: {c['pack_size']}" if c.get("pack_size") else ""
        price_str = f" | Price: ₹{c['price']}" if c.get("price") is not None else ""
        cand_lines.append(
            f"ID: {c['candidate_id']} | Name: {c['name']}{brand_str}{pack_str}{price_str}{stock_info}"
        )
    candidates_text = "\n".join(cand_lines)
    pref_text = f"\nPreferred pack size: {preferred_pack_size}" if preferred_pack_size else ""

    return (
        "You are selecting the best matching grocery product candidate for a customer's request.\n\n"
        f"Customer request: '{query}'{pref_text}\n\n"
        f"Available product candidates:\n{candidates_text}\n\n"
        "Principles:\n"
        "1. Clear request: Pick the single best candidate that fulfills what the customer asked for.\n"
        "2. Ask a question only when:\n"
        "   - The requested size, weight, or count does not exist in the candidates.\n"
        "   - The top candidates represent completely different kinds of products or purposes.\n"
        "3. Never ask simply because multiple brands exist: Pick the best matching brand and option.\n"
        "4. Respect the requested size and count: Honor the exact size, weight, or count specified by the customer. "
        "Prefer the standard single unit over multi-packs or bundled quantities unless the customer explicitly asked for a count.\n\n"
        "Return structured output:\n"
        "- If picking: action='pick', candidate_id='<id>', reason='<short explanation>'\n"
        "- If asking: action='ask', question='<concise question>', reason='<short explanation>'"
    )


class SwiggyAgentTools:
    """Wraps CommercePort into clean, high-signal tools for the LLM agent."""

    def __init__(
        self,
        commerce: CommercePort,
        gemini_client: Optional[GeminiClient] = None,
    ) -> None:
        self.commerce = commerce
        self.gemini_client = gemini_client
        self._catalog_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

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
        self, queries: list[str], address_id: Optional[str] = None, bypass_cache: bool = False
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
            if not bypass_cache and cache_key in self._catalog_cache:
                cached_time, cached_items = self._catalog_cache[cache_key]
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
                            "in_stock": v.get("in_stock") if v.get("in_stock") is not None else v.get("is_available"),
                            "is_available": v.get("is_available") if v.get("is_available") is not None else v.get("in_stock"),
                            "is_veg": v.get("is_veg") if v.get("is_veg") is not None else p.get("is_veg"),
                        })
                self._catalog_cache[cache_key] = (now, compact_prods)
                return {"query": q, "products": compact_prods}
            except Exception as exc:
                return {"query": q, "products": [], "error": str(exc)}

        batch_results = []
        for i in range(0, len(clean_queries), 3):
            wave = clean_queries[i : i + 3]
            wave_res = await asyncio.gather(*[_search_one(q) for q in wave])
            batch_results.extend(wave_res)
            critical = next(
                (item for item in wave_res if item.get("error") in ("RATE_LIMITED", "AUTH_EXPIRED")),
                None,
            )
            if critical:
                return {
                    "success": False,
                    "error": critical["error"],
                    "retryable": False,
                    "retry_after_seconds": critical.get("retry_after_seconds"),
                }
        return {
            "success": True,
            "results": list(batch_results),
        }

    async def select_best_variant(
        self,
        query: str,
        products: list[dict[str, Any]],
        preferred_pack_size: str = "",
    ) -> Optional[dict[str, Any]]:
        """Select product variant using SMALL_CHECK_MODEL, returning pick or ask with reason."""
        raw_candidates = _extract_candidates(products)
        if not raw_candidates:
            return None

        # Candidates whose in_stock is exactly False are removed before the model sees them. None (unknown) stays.
        candidates = [c for c in raw_candidates if c.get("in_stock") is not False]
        if not candidates:
            # If all candidates are False, say it is out of stock.
            return {
                "action": "out_of_stock",
                "query": query,
                "reason": f"{query} is out of stock",
                "candidates": [],
            }

        # Renumber candidates 1..N for prompt clarity
        for idx, c in enumerate(candidates, 1):
            c["candidate_id"] = str(idx)

        client = self.gemini_client
        if client is None:
            api_key = getattr(settings, "GEMINI_API_KEY", None) or ""
            if api_key:
                client = GeminiClient(api_key=api_key)

        if client is None:
            logger.error("No Gemini client available for product selection on query '%s'", query)
            return {
                "action": "selection_unavailable",
                "candidates": candidates,
                "query": query,
                "error": "no_gemini_client",
            }

        prompt = _build_product_selection_prompt(query, candidates, preferred_pack_size)
        model_name = settings.GEMINI_SMALL_CHECK_MODEL
        MODEL_TIMEOUT = 6.0

        async def _call_model() -> tuple[Optional[dict[str, Any]], Optional[str]]:
            try:
                return await asyncio.wait_for(
                    client.generate_structured_with_reason(
                        model=model_name,
                        prompt=prompt,
                        response_schema=PRODUCT_SELECTION_SCHEMA,
                    ),
                    timeout=MODEL_TIMEOUT,
                )
            except (asyncio.TimeoutError, TimeoutError):
                return None, "timeout"
            except Exception as exc:
                return None, str(exc)

        try:
            res, reason = await _call_model()
            is_transient = (
                not res
                and reason
                and (
                    "429" in str(reason).lower()
                    or "timeout" in str(reason).lower()
                    or "quota" in str(reason).lower()
                )
            )
            if is_transient:
                logger.warning(
                    "Product selection model transient error (%s) for query '%s', retrying once after wait",
                    reason, query,
                )
                await asyncio.sleep(0.5)
                res, reason = await _call_model()

            if not res:
                logger.error("Product selection model call failed for query '%s': %s", query, reason)
                return {
                    "action": "selection_unavailable",
                    "candidates": candidates,
                    "query": query,
                    "error": reason or "model_no_result",
                }

            action = str(res.get("action") or "").strip().lower()
            reason_text = str(res.get("reason") or "").strip()

            if action == "ask":
                question = str(res.get("question") or "").strip()
                return {
                    "action": "ask",
                    "question": question or f"Which option would you like for {query}?",
                    "reason": reason_text,
                    "candidates": candidates,
                    "query": query,
                }

            chosen_id = str(res.get("candidate_id") or "").strip()
            matched = next((c for c in candidates if c["candidate_id"] == chosen_id), None)
            if not matched:
                import re
                m_num = re.search(r"\b(\d+)\b", chosen_id)
                if m_num:
                    matched = next((c for c in candidates if c["candidate_id"] == m_num.group(1)), None)

            if matched:
                return {
                    "action": "pick",
                    "candidate_id": matched["candidate_id"],
                    "option": matched,
                    "spin_id": matched["spin_id"],
                    "sku_id": matched["sku_id"],
                    "name": matched["name"],
                    "pack_size": matched["pack_size"],
                    "price": matched["price"],
                    "reason": reason_text,
                }

            logger.error(
                "Product selection model candidate_id '%s' not found in candidates for query '%s'",
                chosen_id, query,
            )
            return {
                "action": "selection_unavailable",
                "candidates": candidates,
                "query": query,
                "error": "candidate_id_not_found",
            }

        except Exception as exc:
            logger.error("Product selection model call exception for query '%s': %s", query, exc)
            return {
                "action": "selection_unavailable",
                "candidates": candidates,
                "query": query,
                "error": str(exc),
            }

    async def manage_basket(
        self,
        address_id: str,
        add: Optional[list[dict[str, Any]]] = None,
        remove: Optional[list[str]] = None,
        set_quantity: Optional[list[dict[str, Any]]] = None,
        current_cart: Optional[CommerceCart] = None,
        delivery_location: str = "Home",
        budget_cap_inr: Optional[float] = None,
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
                    "id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or item.spin_id,
                    "line_id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or item.spin_id,
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

    async def add_selected_variants(
        self,
        selected: list[dict[str, Any]],
        address_id: str,
        current_cart: CommerceCart,
        expected_cart_state: dict[str, Any],
        delivery_location: str = "Home",
        budget_cap_inr: float | None = None,
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
            verified = await self.commerce.get_cart()
            item_count = len(verified.items) if verified and verified.items else 0
            return {
                "success": True,
                "message": "Cart cleared.",
                "item_count": item_count,
            }
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
                    if v.in_stock is not False
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

    async def list_available_coupons(self, cart_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch list of available discount coupons from Swiggy for the active cart."""
        try:
            coupons = await self.commerce.list_coupons(cart_id=cart_id)
            return {
                "success": True,
                "coupons": [
                    {
                        "code": c.code,
                        "description": c.description,
                        "discount_amount": c.discount_amount,
                        "min_cart_value": c.min_cart_value,
                        "is_applicable": c.is_applicable,
                        "terms": c.terms,
                    }
                    for c in coupons
                ],
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc), "coupons": []}
        except Exception as exc:
            logger.warning("list_available_coupons failed: %s", exc)
            return {"success": False, "error": str(exc), "coupons": []}

    async def apply_cart_coupon(self, code: str, cart_id: Optional[str] = None) -> dict[str, Any]:
        """Apply a coupon code to the active Swiggy cart."""
        if not code or not str(code).strip():
            return {"success": False, "error": "COUPON_CODE_REQUIRED"}
        try:
            res = await self.commerce.apply_coupon(code=str(code).strip().upper(), cart_id=cart_id)
            return {
                "success": res.applied,
                "code": res.code,
                "discount_amount": res.discount_amount,
                "message": res.message or ("Coupon applied successfully" if res.applied else "Coupon invalid"),
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("apply_cart_coupon failed: %s", exc)
            return {"success": False, "error": str(exc)}


# --- Merged Cart & Basket Orchestration ---

async def execute_restore_cart(
    commerce: CommercePort, before: CommerceCart, after: CommerceCart, address_id: str
) -> bool:
    """Restore previous cart state on budget or mutation failures without failing on fee shifts."""
    restore = [
        CartItemUpdate(
            spin_id=item.spin_id,
            sku_id=item.sku_id or getattr(item, "sku_id", None) or item.spin_id,
            quantity=item.quantity,
        )
        for item in before.items
    ]
    before_spins = {item.spin_id for item in before.items}
    restore.extend(
        CartItemUpdate(
            spin_id=item.spin_id,
            sku_id=item.sku_id or getattr(item, "sku_id", None) or item.spin_id,
            quantity=0,
        )
        for item in after.items
        if item.spin_id not in before_spins
    )
    try:
        await commerce.update_cart(restore, address_id=address_id)
        restored = await commerce.get_cart()
    except Exception as exc:
        logger.warning("execute_restore_cart failed during cart update/get: %s", exc)
        return False

    before_items = sorted((item.spin_id, item.quantity) for item in before.items)
    restored_items = sorted((item.spin_id, item.quantity) for item in restored.items)
    # Verification check matches item identities and quantities, ignoring dynamic delivery/surge fee shifts
    return before_items == restored_items


async def _write_cart_items(
    tools: Any,
    items: list[dict[str, Any]],
    address_id: str,
    delivery_location: str = "Home",
    expected_cart_state: dict[str, Any] | None = None,
    item_reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Internal helper to write merged item updates directly to Swiggy Instamart cart."""
    if not isinstance(address_id, str) or not address_id or not isinstance(items, list) or not 1 <= len(items) <= 30:
        return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
    seen_spins: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
        spin = item.get("spin_id")
        sku = item.get("sku_id")
        quantity = item.get("quantity")
        if (
            not isinstance(spin, str)
            or not 1 <= len(spin) <= 128
            or spin in seen_spins
            or type(quantity) is not int
            or not 0 <= quantity <= 99
            or (sku is not None and (not isinstance(sku, str) or not 1 <= len(sku) <= 128))
        ):
            return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
        seen_spins.add(spin)
    try:
        merged_by_spin: dict[str, CartItemUpdate] = {}
        try:
            existing_cart: CommerceCart = await tools.commerce.get_cart()
            if existing_cart is None:
                return {"success": False, "error": "CART_UNAVAILABLE", "retryable": False}
            if expected_cart_state is not None:
                existing_state = {
                    "cart_id": existing_cart.cart_id,
                    "address_id": existing_cart.address_id or expected_cart_state.get("address_id"),
                    "grand_total": existing_cart.grand_total,
                    "items": sorted(
                        ([ci.spin_id, ci.sku_id, ci.quantity] for ci in existing_cart.items),
                        key=lambda entry: (entry[0], entry[1] or ""),
                    ),
                }
                if existing_state != expected_cart_state:
                    return {
                        "success": False,
                        "error": "CART_CHANGED",
                        "retryable": False,
                        "message": "Your Swiggy basket changed. Please review it before adding these items.",
                    }
            if existing_cart and existing_cart.items:
                for ci in existing_cart.items:
                    if ci.quantity > 0:
                        merged_by_spin[ci.spin_id] = CartItemUpdate(
                            spin_id=ci.spin_id,
                            quantity=ci.quantity,
                            sku_id=ci.sku_id or ci.spin_id,
                        )
        except ProviderAuthError:
            raise
        except Exception:
            return {
                "success": False,
                "error": "CART_UNAVAILABLE",
                "retryable": False,
                "message": "I couldn't read the current basket, so I didn't change it.",
            }

        for it in items:
            spin = str(it["spin_id"])
            qty = int(it["quantity"])
            existing_sku = merged_by_spin[spin].sku_id if spin in merged_by_spin else None
            sku = it.get("sku_id") or existing_sku or spin
            merged_by_spin[spin] = CartItemUpdate(
                spin_id=spin,
                quantity=qty,
                sku_id=sku,
            )

        cart_updates = list(merged_by_spin.values())
        updated: CommerceCart = await tools.commerce.update_cart(
            items=cart_updates, address_id=address_id
        )
        try:
            verified = await tools.commerce.get_cart(updated.cart_id)
        except Exception as exc:
            logger.warning("Cart read-back failed after provider write: %s", exc)
            return {
                "success": False,
                "error": "CART_WRITE_UNVERIFIED",
                "retryable": False,
                "message": "Swiggy may have changed your basket, but I couldn't verify it. Please show your basket before trying again.",
            }
        actual_by_spin = {item.spin_id: item for item in verified.items}
        unresolved_items = []
        for requested in cart_updates:
            actual = actual_by_spin.get(requested.spin_id)
            actual_quantity = actual.quantity if actual else 0
            if (
                actual_quantity != requested.quantity
                or (
                    requested.quantity > 0
                    and requested.sku_id
                    and (actual is None or (actual.sku_id and actual.sku_id != requested.sku_id))
                )
            ):
                unresolved_items.append({
                    "spin_id": requested.spin_id,
                    "sku_id": requested.sku_id,
                    "requested_quantity": requested.quantity,
                    "actual_quantity": actual_quantity,
                    "actual_sku_id": actual.sku_id if actual else None,
                })
        if item_reasons:
            for it in verified.items:
                r = item_reasons.get(it.spin_id) or item_reasons.get(it.name)
                if r:
                    it.reason = r

        if unresolved_items:
            return {
                "success": False,
                "error": "CART_ITEMS_UNRESOLVED",
                "retryable": False,
                "cart_id": verified.cart_id,
                "verified_fingerprint": cart_fingerprint(verified, address_id),
                "unresolved_items": unresolved_items,
                "formatted_receipt": format_cart_receipt(verified, delivery_location, item_reasons=item_reasons),
                "message": "Swiggy changed or omitted an item. Please resolve each difference before approval.",
            }
        items_summary = [
            {
                "id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or getattr(item, "id", None) or item.spin_id,
                "line_id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or getattr(item, "id", None) or item.spin_id,
                "spin_id": item.spin_id,
                "sku_id": item.sku_id,
                "name": item.name,
                "pack_size": item.pack_size,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "formatted_price": _format_inr(item.total_price),
            }
            for item in verified.items
        ]
        packaging_and_handling = round(verified.packaging_fee + verified.handling_fee, 2)
        total_fees = round(verified.delivery_fee + packaging_and_handling + verified.taxes, 2)
        return {
            "success": True,
            "cart_id": verified.cart_id,
            "verified_fingerprint": cart_fingerprint(verified, address_id),
            "item_count": len(items_summary),
            "items": items_summary,
            "item_total": verified.item_total,
            "delivery_fee": verified.delivery_fee,
            "packaging_fee": verified.packaging_fee,
            "handling_fee": verified.handling_fee,
            "taxes": verified.taxes,
            "total_fees": total_fees,
            "discount": verified.discount,
            "grand_total": verified.grand_total,
            "is_serviceable": verified.is_serviceable,
            "min_order_threshold": verified.min_order_threshold,
            "address_warning": verified.address_warning,
            "formatted_item_total": _format_inr(verified.item_total),
            "formatted_delivery_fee": (
                _format_inr(verified.delivery_fee) if verified.delivery_fee > 0 else "FREE (₹0)"
            ),
            "formatted_packaging_fee": _format_inr(verified.packaging_fee),
            "formatted_handling_fee": _format_inr(verified.handling_fee),
            "formatted_packaging_and_handling": _format_inr(packaging_and_handling),
            "formatted_taxes": _format_inr(verified.taxes),
            "formatted_total_fees": _format_inr(total_fees),
            "formatted_grand_total": _format_inr(verified.grand_total),
            "formatted_receipt": format_cart_receipt(verified, delivery_location, item_reasons=item_reasons),
        }
    except CartExpiredError:
        logger.warning("Cart expired during _write_cart_items.")
        return {
            "success": False,
            "error": "CART_EXPIRED",
            "retryable": True,
            "message": "Your Swiggy basket session expired. Please tell me what you'd like to add fresh.",
        }
    except ItemOutOfStockError as exc:
        return {
            "success": False,
            "error": "ITEM_OUT_OF_STOCK",
            "available_quantity": exc.available_quantity,
        }
    except ProviderAuthError as exc:
        return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
    except Exception as exc:
        logger.warning("_write_cart_items failed: %s", exc)
        return {
            "success": False,
            "error": "CART_UPDATE_FAILED",
            "message": "We could not update your Swiggy basket right now. Please try again.",
            "detail": str(exc),
        }


async def execute_add_selected_variants(
    tools: Any,
    selected: list[dict[str, Any]],
    address_id: str,
    current_cart: CommerceCart,
    expected_cart_state: dict[str, Any],
    delivery_location: str = "Home",
    budget_cap_inr: float | None = None,
    extra_updates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply customer-chosen, freshly verified SKUs and extra updates in one atomic cart update."""
    existing_by_spin = {item.spin_id: item for item in current_cart.items}
    predicted_total = Decimal(str(current_cart.grand_total))
    accepted: list[dict[str, Any]] = []
    blocked: list[str] = []
    merged_selected: dict[str, dict[str, Any]] = {}
    for item in selected:
        spin = item["option"]["spin_id"]
        if spin in merged_selected:
            merged_selected[spin]["quantity"] += item["quantity"]
        else:
            merged_selected[spin] = dict(item)

    for spin, item in merged_selected.items():
        option, query, quantity = item["option"], item["query"], item["quantity"]
        previous = existing_by_spin.get(spin)
        prev_qty = previous.quantity if previous else 0
        final_quantity = prev_qty + quantity

        max_quantity = option.get("max_quantity")
        if isinstance(max_quantity, int) and final_quantity > max_quantity:
            blocked.append(query)
            continue

        unit_price = Decimal(str(option["price"]))
        delta = unit_price * quantity

        if budget_cap_inr is not None and predicted_total + delta > Decimal(str(budget_cap_inr)):
            blocked.append(query)
            continue
        accepted.append({
            "spin_id": spin,
            "sku_id": option.get("sku_id") or (previous.sku_id if previous else None) or spin,
            "quantity": final_quantity,
        })
        predicted_total += delta

    accepted_spins = {item["spin_id"] for item in accepted}
    if extra_updates:
        for u in extra_updates:
            spin = u["spin_id"]
            sku = u.get("sku_id")
            qty = u["quantity"]
            previous = existing_by_spin.get(spin)
            previous_total = Decimal(str(previous.total_price)) if previous else Decimal(0)
            unit_p = Decimal(str(previous.unit_price)) if previous else Decimal(0)
            new_line_total = unit_p * qty
            delta = new_line_total - previous_total

            if spin in accepted_spins:
                # Update existing entry rather than silently ignoring it
                for acc in accepted:
                    if acc["spin_id"] == spin:
                        acc["quantity"] = qty
                        break
            else:
                # Upfront budget cap enforcement on set_quantity updates
                if budget_cap_inr is not None and predicted_total + delta > Decimal(str(budget_cap_inr)):
                    blocked.append(u.get("name") or spin)
                    continue
                predicted_total += delta
                accepted.append({
                    "spin_id": spin,
                    "sku_id": sku or (previous.sku_id if previous else None) or spin,
                    "quantity": qty,
                })
                accepted_spins.add(spin)

    if not accepted:
        return {
            "success": False,
            "error": "BUDGET_BLOCKED",
            "budget_blocked_items": blocked,
            "message": "None of the selected items fit the stated limit. Your basket was not changed.",
        }
    reasons_map: dict[str, str] = {}
    for item in selected:
        r = item.get("reason")
        if r and isinstance(item.get("option"), dict):
            spin = item["option"].get("spin_id")
            name = item["option"].get("name")
            if spin:
                reasons_map[spin] = r
            if name:
                reasons_map[name] = r

    result = await _write_cart_items(
        tools,
        accepted,
        address_id,
        delivery_location,
        expected_cart_state=expected_cart_state,
        item_reasons=reasons_map,
    )
    if not result.get("success"):
        if result.get("error") == "CART_ITEMS_UNRESOLVED":
            by_spin = {item["option"]["spin_id"]: item["query"] for item in selected}
            if extra_updates:
                for u in extra_updates:
                    by_spin.setdefault(u.get("spin_id"), u.get("name") or "item")
            unresolved = [
                by_spin.get(item["spin_id"], "item") for item in result.get("unresolved_items", [])
            ]
            result["message"] = (
                "Swiggy omitted or changed: "
                + ", ".join(unresolved)
                + ". Please review the basket before ordering.\n\n"
                + result.get("formatted_receipt", "")
            )
        return result

    over_limit = (
        budget_cap_inr is not None
        and Decimal(str(result["grand_total"])) > Decimal(str(budget_cap_inr))
    )
    if over_limit:
        try:
            after = await tools.commerce.get_cart()
            restored = await execute_restore_cart(tools.commerce, current_cart, after, address_id)
        except Exception:
            restored = False
        return {
            "success": False,
            "error": "BUDGET_EXCEEDED" if restored else "BUDGET_ROLLBACK_UNVERIFIED",
            "message": (
                "The live total changed and exceeded your limit. I restored your previous basket."
                if restored
                else "The live total changed and I could not verify a rollback. Please review your basket."
            ),
            "budget_blocked_items": blocked,
        }
    result["budget_blocked_items"] = blocked
    result["added_items"] = [item["option"]["name"] for item in selected if item["query"] not in blocked]
    return result


async def execute_manage_basket(

    tools: Any,

    address_id: str,

    add: Optional[list[dict[str, Any]]] = None,

    remove: Optional[list[str]] = None,

    set_quantity: Optional[list[dict[str, Any]]] = None,

    current_cart: Optional[CommerceCart] = None,

    delivery_location: str = "Home",

    budget_cap_inr: Optional[float] = None,

) -> dict[str, Any]:

    """Atomically manage Swiggy Instamart basket: add items, remove items, or adjust quantities in a single turn."""

    if not address_id:

        return {"success": False, "error": "ADDRESS_REQUIRED"}



    if current_cart is None:

        try:

            current_cart = await tools.commerce.get_cart()

        except ProviderAuthError as exc:

            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}

        except Exception as exc:

            logger.warning(f"Failed to fetch cart: {exc}")

            return {

                "success": False,

                "error": "CART_UNAVAILABLE",

                "message": "Could not retrieve your current basket from Swiggy Instamart.",

            }



    expected_cart_state = {

        "cart_id": current_cart.cart_id,

        "address_id": current_cart.address_id,

        "grand_total": current_cart.grand_total,

        "items": sorted(

            ([it.spin_id, it.sku_id, it.quantity] for it in current_cart.items),

            key=lambda e: (e[0], e[1] or ""),

        ),

    }



    cart_items_by_id: dict[str, Any] = {}

    for ci in current_cart.items:

        lid = getattr(ci, "cart_line_id", None) or getattr(ci, "line_id", None) or ci.spin_id

        cart_items_by_id[lid] = ci



    # Validation: line IDs in remove and set_quantity must exist in live cart

    if remove and isinstance(remove, list):

        for rem in remove:

            rem_str = str(rem).strip() if rem is not None else ""

            if not rem_str:

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": "Empty or invalid item ID provided for removal.",

                }

            if rem_str not in cart_items_by_id:

                return {

                    "success": False,

                    "error": "INVALID_LINE_ID",

                    "message": f"Cart line ID '{rem_str}' does not exist in the active basket.",

                }



    if set_quantity and isinstance(set_quantity, list):

        for sq in set_quantity:

            if not isinstance(sq, dict):

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": "Each quantity adjustment must be an object with line_id and quantity.",

                }

            q_id = str(sq.get("line_id") or "").strip()

            if not q_id or q_id not in cart_items_by_id:

                return {

                    "success": False,

                    "error": "INVALID_LINE_ID",

                    "message": f"Cart line ID '{q_id}' does not exist in the active basket.",

                }

            raw_qty = sq.get("quantity")

            try:

                t_qty = int(raw_qty) if raw_qty is not None else -1

            except (ValueError, TypeError):

                t_qty = -1

            if not 0 <= t_qty <= 99:

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": f"Invalid quantity '{raw_qty}' for item '{q_id}'. Quantity must be between 0 and 99.",

                }



    extra_updates: list[dict[str, Any]] = []

    removed_items: list[str] = []

    modified_items: list[str] = []

    unavailable_items: list[str] = []

    restricted_items: list[str] = []

    clarifications_needed: list[dict[str, Any]] = []

    selection_unavailable_items: list[dict[str, Any]] = []

    from backend.agent.tools import AddedItem



    # 1. Process Removals

    if remove and isinstance(remove, list):

        for rem in remove:

            rem_clean = str(rem).strip()

            ci = cart_items_by_id.get(rem_clean)

            if ci:

                extra_updates.append({

                    "spin_id": ci.spin_id,

                    "sku_id": ci.sku_id,

                    "quantity": 0,

                })

                removed_items.append(ci.name)



    # 2. Process Quantity Adjustments

    if set_quantity and isinstance(set_quantity, list):

        for sq in set_quantity:

            q_id = str(sq.get("line_id") or "").strip()

            try:

                t_qty = int(sq.get("quantity", 0))

            except (ValueError, TypeError):

                continue

            ci = cart_items_by_id.get(q_id)

            if ci:

                extra_updates.append({

                    "spin_id": ci.spin_id,

                    "sku_id": ci.sku_id,

                    "quantity": t_qty,

                })

                modified_items.append(f"{ci.name} -> {t_qty}")



    # 3. Process Additions

    selected_for_add: list[dict[str, Any]] = []

    if add and isinstance(add, list):

        if len(add) > 30:

            return {

                "success": False,

                "error": "TOO_MANY_ITEMS",

                "message": "Cannot add more than 30 items in a single request.",

            }

        normalized_add = []

        for item in add:

            if not isinstance(item, dict):

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": "Each item to add must be an object with query and quantity.",

                }

            raw_query = item.get("query")

            if not isinstance(raw_query, str) or not raw_query.strip():

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": "Each item to add must contain a non-empty 'query' string.",

                }

            raw_quantity = item.get("quantity", 1)

            try:

                quantity = int(raw_quantity)

            except (ValueError, TypeError):

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": f"Invalid quantity '{raw_quantity}' for item '{raw_query}'. Must be an integer 1-99.",

                }

            if not 1 <= quantity <= 99:

                return {

                    "success": False,

                    "error": "INVALID_INPUT",

                    "message": f"Quantity for '{raw_query}' must be between 1 and 99.",

                }



            normalized_add.append({

                "query": raw_query.strip(),

                "quantity": quantity,

                "preferred_pack_size": str(item.get("preferred_pack_size") or "").strip(),

            })



        if normalized_add:

            search = await tools.batch_search_products([it["query"] for it in normalized_add], address_id)

            if not search.get("success"):

                return search



            search_results = search.get("results") or []

            for idx, item in enumerate(normalized_add):

                if idx >= len(search_results):

                    unavailable_items.append(item["query"])

                    continue

                result = search_results[idx]

                if result.get("error"):

                    err_str = str(result.get("error")).upper()

                    if err_str in ("RATE_LIMITED", "AUTH_EXPIRED", "SERVICE_UNAVAILABLE", "STORE_CLOSED", "ADDRESS_NOT_SERVICEABLE"):

                        return {

                            "success": False,

                            "error": result["error"],

                            "retry_after_seconds": result.get("retry_after_seconds"),

                        }

                    if "STORE" in err_str or "CLOSED" in err_str or "UNSERVICEABLE" in err_str:

                        return {

                            "success": False,

                            "error": "ADDRESS_NOT_SERVICEABLE",

                            "message": "The local Swiggy Instamart store is currently closed or unserviceable for this address.",

                        }

                    unavailable_items.append(item["query"])

                    continue



                raw_prods = result.get("products", [])

                has_medical = any(

                    is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or ""))

                    for p in raw_prods

                )

                non_medical = [

                    p for p in raw_prods

                    if not is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or ""))

                ]

                if has_medical and not non_medical:

                    restricted_items.append(item["query"])

                    continue



                # Direct model variant selection grounded in live Swiggy dark store candidates

                best = await tools.select_best_variant(item["query"], non_medical, item["preferred_pack_size"])

                if not best:

                    unavailable_items.append(item["query"])

                elif best.get("action") == "out_of_stock":

                    unavailable_items.append(item["query"])

                elif best.get("action") == "pick" and best.get("option"):

                    selected_for_add.append({

                        "option": best["option"],

                        "query": item["query"],

                        "quantity": item["quantity"],

                        "reason": best.get("reason", ""),

                    })

                elif best.get("action") == "ask":

                    clarifications_needed.append({

                        "query": item["query"],

                        "question": best.get("question"),

                        "reason": best.get("reason"),

                        "candidates": best.get("candidates", []),

                    })

                elif best.get("action") == "selection_unavailable":

                    selection_unavailable_items.append({

                        "query": item["query"],

                        "candidates": best.get("candidates", []),

                        "error": best.get("error"),

                    })

                else:

                    unavailable_items.append(item["query"])



    # If there are additions OR extra updates:

    if selected_for_add or extra_updates:

        mutation = await tools.add_selected_variants(

            selected=selected_for_add,

            address_id=address_id,

            current_cart=current_cart,

            expected_cart_state=expected_cart_state,

            delivery_location=delivery_location,

            budget_cap_inr=budget_cap_inr,

            extra_updates=extra_updates,

        )

        if not mutation.get("success"):

            return mutation

        verified_spins = {item.get("spin_id") for item in mutation.get("items", [])}

        mutation["added_items"] = [

            AddedItem(s["option"]["name"], reason=s.get("reason", ""), query=s.get("query", ""))

            for s in selected_for_add

            if s["option"].get("spin_id") in verified_spins

        ]

        mutation["removed_items"] = removed_items

        mutation["modified_items"] = modified_items

        mutation["unavailable_items"] = unavailable_items

        mutation["restricted_items"] = list(dict.fromkeys(restricted_items))

        if selection_unavailable_items:

            mutation["selection_unavailable"] = True

            mutation["selection_unavailable_items"] = selection_unavailable_items

        if clarifications_needed:

            mutation["clarifications_needed"] = clarifications_needed

            mutation["questions"] = [c["question"] for c in clarifications_needed if c.get("question")]

            mutation["candidates_for_clarification"] = {

                c["query"]: c.get("candidates", []) for c in clarifications_needed

            }

        return mutation



    # Nothing changed

    receipt = format_cart_receipt(current_cart, delivery_location)

    items_summary = [

        {

            "id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or getattr(item, "id", None) or item.spin_id,

            "line_id": getattr(item, "cart_line_id", None) or getattr(item, "line_id", None) or getattr(item, "id", None) or item.spin_id,

            "spin_id": item.spin_id,

            "sku_id": item.sku_id,

            "name": item.name,

            "pack_size": item.pack_size,

            "quantity": item.quantity,

            "unit_price": item.unit_price,

            "total_price": item.total_price,

            "formatted_price": _format_inr(item.total_price),

        }

        for item in current_cart.items

    ]

    packaging_and_handling = round(current_cart.packaging_fee + current_cart.handling_fee, 2)

    total_fees = round(current_cart.delivery_fee + packaging_and_handling + current_cart.taxes, 2)

    res = {

        "success": True,

        "cart_id": current_cart.cart_id,

        "verified_fingerprint": cart_fingerprint(current_cart, address_id),

        "item_count": len(items_summary),

        "items": items_summary,

        "item_total": current_cart.item_total,

        "delivery_fee": current_cart.delivery_fee,

        "packaging_fee": current_cart.packaging_fee,

        "handling_fee": current_cart.handling_fee,

        "taxes": current_cart.taxes,

        "total_fees": total_fees,

        "discount": current_cart.discount,

        "grand_total": current_cart.grand_total,

        "is_serviceable": current_cart.is_serviceable,

        "min_order_threshold": current_cart.min_order_threshold,

        "address_warning": current_cart.address_warning,

        "formatted_item_total": _format_inr(current_cart.item_total),

        "formatted_delivery_fee": (

            _format_inr(current_cart.delivery_fee) if current_cart.delivery_fee > 0 else "FREE (₹0)"

        ),

        "formatted_packaging_fee": _format_inr(current_cart.packaging_fee),

        "formatted_handling_fee": _format_inr(current_cart.handling_fee),

        "formatted_packaging_and_handling": _format_inr(packaging_and_handling),

        "formatted_taxes": _format_inr(current_cart.taxes),

        "formatted_total_fees": _format_inr(total_fees),

        "formatted_grand_total": _format_inr(current_cart.grand_total),

        "formatted_receipt": receipt,

        "added_items": [],

        "removed_items": removed_items,

        "modified_items": modified_items,

        "unavailable_items": unavailable_items,

        "restricted_items": list(dict.fromkeys(restricted_items)),

        "budget_blocked_items": [],

    }

    if selection_unavailable_items:

        res["selection_unavailable"] = True

        res["selection_unavailable_items"] = selection_unavailable_items

    if clarifications_needed:

        res["clarifications_needed"] = clarifications_needed

        res["questions"] = [c["question"] for c in clarifications_needed if c.get("question")]

        res["candidates_for_clarification"] = {

            c["query"]: c.get("candidates", []) for c in clarifications_needed

        }

    return res

