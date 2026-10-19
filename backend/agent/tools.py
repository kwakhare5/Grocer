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
from backend.agent.gemini import GeminiClient
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.basket_manager import execute_manage_basket
from backend.agent.cart_actions import (
    execute_add_selected_variants,
)
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
                        lat = getattr(addrs[0], "latitude", getattr(addrs[0], "lat", None))
                        lng = getattr(addrs[0], "longitude", getattr(addrs[0], "lng", None))
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
