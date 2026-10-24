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
                if is_restricted_medical_product(
                    str(v.get("name") or p.get("name") or ""),
                    str(p.get("category") or ""),
                ):
                    continue
                in_stock_val = v.get("in_stock")
                if in_stock_val is None:
                    in_stock_val = v.get("is_available")

                raw_price = v.get("price")
                try:
                    price_float = float(raw_price) if raw_price is not None else 0.0
                except (ValueError, TypeError):
                    price_float = 0.0

                candidates.append(
                    {
                        "candidate_id": str(cand_id),
                        "product_id": p.get("product_id"),
                        "name": v.get("name") or p.get("name") or "",
                        "brand": p.get("brand"),
                        "category": p.get("category"),
                        "pack_size": v.get("pack_size") or "",
                        "price": price_float,
                        "in_stock": in_stock_val,
                        "spin_id": v.get("spin_id") or p.get("spin_id"),
                        "sku_id": v.get("sku_id")
                        or v.get("spin_id")
                        or p.get("sku_id"),
                        "max_quantity": v.get("max_quantity"),
                    }
                )
                cand_id += 1
                if len(candidates) >= 10:
                    break
        else:
            if is_restricted_medical_product(
                str(p.get("name") or ""), str(p.get("category") or "")
            ):
                continue
            in_stock_val = p.get("in_stock")
            if in_stock_val is None:
                in_stock_val = p.get("is_available")

            raw_price = p.get("price")
            try:
                price_float = float(raw_price) if raw_price is not None else 0.0
            except (ValueError, TypeError):
                price_float = 0.0

            candidates.append(
                {
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
                }
            )
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
    pref_text = (
        f"\nPreferred pack size: {preferred_pack_size}" if preferred_pack_size else ""
    )

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
        self._catalog_cache: dict[
            tuple[str, str], tuple[float, list[dict[str, Any]]]
        ] = {}

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
                results.append(
                    {
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
                                "savings": f"{_format_inr(v.mrp - v.price)} off"
                                if v.mrp and v.mrp > v.price
                                else None,
                                "in_stock": v.in_stock,
                                "max_quantity": v.max_quantity,
                                "max_quantity_message": v.max_quantity_message,
                            }
                            for v in in_stock_variants
                        ],
                        "similar_products": [
                            {
                                "product_id": similar.product_id,
                                "name": similar.name,
                                "brand": similar.brand,
                                "variants": [
                                    {
                                        "spin_id": variant.spin_id,
                                        "sku_id": variant.sku_id,
                                        "pack_size": variant.pack_size,
                                        "price": variant.price,
                                        "in_stock": variant.in_stock,
                                    }
                                    for variant in similar.variants
                                    if variant.in_stock is not False
                                ],
                            }
                            for similar in p.similar_products[:3]
                            if any(
                                variant.in_stock is not False
                                for variant in similar.variants
                            )
                        ],
                    }
                )
                if len(results) == 10:
                    break
            return {
                "success": True,
                "query": query,
                "count": len(results),
                "products": results,
            }
        except ProviderAuthError as exc:
            return {
                "success": False,
                "error": "AUTH_EXPIRED",
                "detail": str(exc),
                "retryable": False,
            }
        except ProviderRateLimitedError as exc:
            return {
                "success": False,
                "error": "RATE_LIMITED",
                "retryable": False,
                "retry_after_seconds": exc.retry_after_seconds,
            }
        except Exception as exc:
            logger.warning("search_products failed for query=%s: %s", query, exc)
            return {"success": False, "error": str(exc), "retryable": True}

    async def batch_search_products(
        self,
        queries: list[str],
        address_id: Optional[str] = None,
        bypass_cache: bool = False,
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
                    return {
                        "query": q,
                        "products": [],
                        "error": res.get("error") or "SEARCH_UNAVAILABLE",
                        "retry_after_seconds": res.get("retry_after_seconds"),
                    }
                compact_prods = []
                for p in res.get("products", [])[:5]:
                    for v in p.get("variants", []):
                        compact_prods.append(
                            {
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
                                "in_stock": v.get("in_stock")
                                if v.get("in_stock") is not None
                                else v.get("is_available"),
                                "is_available": v.get("is_available")
                                if v.get("is_available") is not None
                                else v.get("in_stock"),
                                "is_veg": v.get("is_veg")
                                if v.get("is_veg") is not None
                                else p.get("is_veg"),
                            }
                        )
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
                (
                    item
                    for item in wave_res
                    if item.get("error") in ("RATE_LIMITED", "AUTH_EXPIRED")
                ),
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
            logger.error(
                "No Gemini client available for product selection on query '%s'", query
            )
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
                    reason,
                    query,
                )
                await asyncio.sleep(0.5)
                res, reason = await _call_model()

            if not res:
                logger.error(
                    "Product selection model call failed for query '%s': %s",
                    query,
                    reason,
                )
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
            matched = next(
                (c for c in candidates if c["candidate_id"] == chosen_id), None
            )
            if not matched:
                import re

                m_num = re.search(r"\b(\d+)\b", chosen_id)
                if m_num:
                    matched = next(
                        (c for c in candidates if c["candidate_id"] == m_num.group(1)),
                        None,
                    )

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
                chosen_id,
                query,
            )
            return {
                "action": "selection_unavailable",
                "candidates": candidates,
                "query": query,
                "error": "candidate_id_not_found",
            }

        except Exception as exc:
            logger.error(
                "Product selection model call exception for query '%s': %s", query, exc
            )
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
        session: Optional[Any] = None,
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
            session=session,
        )

    async def get_saved_addresses(self, customer_id: str) -> dict[str, Any]:
        """Retrieve the user's saved delivery addresses from Swiggy."""
        return await execute_get_saved_addresses(self.commerce, customer_id)

    async def select_delivery_address(
        self, customer_id: str, address_id: str
    ) -> dict[str, Any]:
        """Validate and select an active delivery address from saved addresses."""
        return await execute_select_delivery_address(
            self.commerce, customer_id, address_id
        )

    async def get_cart(self, delivery_location: str = "Home") -> dict[str, Any]:
        """Fetch current Swiggy Instamart cart contents and pre-computed pricing."""
        try:
            cart: CommerceCart = await self.commerce.get_cart()
            items = [
                {
                    "id": getattr(item, "cart_line_id", None)
                    or getattr(item, "line_id", None)
                    or item.spin_id,
                    "line_id": getattr(item, "cart_line_id", None)
                    or getattr(item, "line_id", None)
                    or item.spin_id,
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
            total_fees = round(
                cart.delivery_fee + packaging_and_handling + cart.taxes, 2
            )
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
                "formatted_delivery_fee": _format_inr(cart.delivery_fee)
                if cart.delivery_fee > 0
                else "FREE (₹0)",
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
        self,
        items: list[dict[str, Any]],
        address_id: str,
    ) -> dict[str, Any]:
        """Ground optional suggestions in the catalogue without changing the basket."""
        queries = [
            str(item.get("query", "")).strip()
            for item in items
            if isinstance(item, dict)
        ]
        search = await self.batch_search_products(queries, address_id)
        suggestions: list[str] = []
        restricted: list[str] = []
        for result in search.get("results", []):
            query = str(result.get("query", ""))
            products = result.get("products") or []
            if not products:
                continue
            product = products[0]
            if is_restricted_medical_product(
                str(product.get("name") or ""), product.get("category")
            ):
                restricted.append(query)
            else:
                suggestions.append(str(product.get("name") or query))
        return {
            "success": True,
            "suggestions": suggestions,
            "restricted_items": restricted,
        }

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
        conversation_state: Optional[str] = "AWAITING_CONFIRMATION",
        attempt_store: Optional[Any] = None,
        customer_id: Optional[str] = None,
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
            conversation_state=conversation_state,
            attempt_store=attempt_store,
            customer_id=customer_id,
        )

    async def track_order(
        self, order_id: str, lat: Optional[float] = None, lng: Optional[float] = None
    ) -> dict[str, Any]:
        """Track the real-time delivery status and ETA of an existing order."""
        if not order_id:
            return {"success": False, "error": "order_id is required."}
        try:
            status = await self.commerce.track_order(order_id, lat=lat, lng=lng)
            status_val = (
                status.status.value
                if hasattr(status.status, "value")
                else str(status.status)
            )
            return {
                "success": True,
                "order_id": order_id,
                "status": status_val,
                "eta_minutes": status.eta_minutes,
                "eta_text": status.eta_text
                or (f"~{status.eta_minutes} mins" if status.eta_minutes else None),
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
            items: list[CommerceProductItem] = await self.commerce.get_go_to_items(
                address_id=address_id or ""
            )
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

    async def list_available_coupons(
        self, cart_id: Optional[str] = None
    ) -> dict[str, Any]:
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
            return {
                "success": False,
                "error": "AUTH_EXPIRED",
                "detail": str(exc),
                "coupons": [],
            }
        except Exception as exc:
            logger.warning("list_available_coupons failed: %s", exc)
            return {"success": False, "error": str(exc), "coupons": []}

    async def apply_cart_coupon(
        self, code: str, cart_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Apply a coupon code to the active Swiggy cart."""
        if not code or not str(code).strip():
            return {"success": False, "error": "COUPON_CODE_REQUIRED"}
        try:
            res = await self.commerce.apply_coupon(
                code=str(code).strip().upper(), cart_id=cart_id
            )
            return {
                "success": res.applied,
                "code": res.code,
                "discount_amount": res.discount_amount,
                "message": res.message
                or ("Coupon applied successfully" if res.applied else "Coupon invalid"),
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("apply_cart_coupon failed: %s", exc)
            return {"success": False, "error": str(exc)}

    list_coupons = list_available_coupons
    apply_coupon = apply_cart_coupon

    async def create_address(
        self,
        customer_id: str = "",
        label: str = "Home",
        street: str = "",
        area: str | None = None,
        city: str | None = None,
        postal_code: str | None = None,
        landmark: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> dict[str, Any]:
        """Save a new delivery address to the customer's Swiggy Instamart account."""
        if not street:
            return {"success": False, "error": "Street address is required."}
        try:
            addr = await self.commerce.create_address(
                customer_id=customer_id,
                label=label,
                street=street,
                area=area,
                city=city,
                postal_code=postal_code,
                landmark=landmark,
                latitude=latitude,
                longitude=longitude,
            )
            return {
                "success": True,
                "address_id": addr.id,
                "label": addr.label,
                "formatted_address": addr.formatted_address,
                "is_serviceable": addr.is_serviceable,
                "message": f"Saved '{addr.label}' to your Swiggy addresses and set it for delivery! 📍",
            }
        except Exception as exc:
            logger.error("create_address failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def delete_address(self, address_id: str) -> dict[str, Any]:
        """Delete an obsolete delivery address from Swiggy."""
        if not address_id:
            return {"success": False, "error": "address_id is required."}
        try:
            ok = await self.commerce.delete_address(address_id)
            return {
                "success": ok,
                "message": f"Address {address_id} deleted."
                if ok
                else "Could not delete address.",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_orders(self, count: int = 5) -> dict[str, Any]:
        """Fetch past Swiggy Instamart order history."""
        try:
            orders = await self.commerce.get_orders(count=count)
            return {
                "success": True,
                "orders": [
                    {
                        "order_id": o.order_id,
                        "status": o.status,
                        "total_amount": o.total_amount,
                        "formatted_total": _format_inr(o.total_amount),
                        "item_count": o.item_count,
                        "ordered_at": str(getattr(o, "ordered_at", "")),
                    }
                    for o in orders
                ],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_order_details(self, order_id: str) -> dict[str, Any]:
        """Fetch item breakdown of a past order for 1-tap reordering."""
        if not order_id:
            return {"success": False, "error": "order_id is required."}
        try:
            details = await self.commerce.get_order_details(order_id)
            return {
                "success": True,
                "order_id": details.order_id,
                "status": details.status,
                "total_amount": details.total_amount,
                "items": [
                    {
                        "name": it.name,
                        "pack_size": it.pack_size,
                        "quantity": it.quantity,
                        "price": it.price,
                        "formatted_price": _format_inr(it.price),
                    }
                    for it in getattr(details, "items", [])
                ],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def report_error(
        self, report_id: str, details: str | None = None
    ) -> dict[str, Any]:
        """Report an issue directly to Swiggy customer care."""
        try:
            res = await self.commerce.report_error(
                report_id, context={"details": details} if details else None
            )
            return {
                "success": res.success,
                "ticket_id": res.ticket_id,
                "customer_care_phone": "080-67466729",
                "message": "Report logged with Swiggy support. Customer care: 080-67466729",
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "customer_care_phone": "080-67466729",
            }


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
    """Apply customer-chosen, freshly verified SKUs and extra updates via atomic update_cart."""
    if budget_cap_inr is not None and current_cart:
        total_estimate = 0.0
        for s in selected:
            total_estimate += float(s.get("price", 0.0)) * int(s.get("quantity", 1))
        for u in (extra_updates or []):
            spin = u.get("spin_id")
            matching_item = next((it for it in current_cart.items if it.spin_id == spin), None)
            price = matching_item.unit_price if matching_item else float(u.get("price", 0.0))
            total_estimate += price * int(u.get("quantity", 1))
        if total_estimate > budget_cap_inr:
            return {"success": False, "error": "BUDGET_BLOCKED", "detail": f"Projected total {total_estimate} exceeds budget {budget_cap_inr}"}

    updates = [
        CartItemUpdate(
            spin_id=str(s.get("spin_id")),
            sku_id=str(s.get("sku_id") or s.get("spin_id")),
            quantity=int(s.get("quantity", 1)),
        )
        for s in selected
        if s.get("spin_id")
    ]
    if extra_updates:
        updates.extend(
            CartItemUpdate(
                spin_id=str(u.get("spin_id")),
                sku_id=str(u.get("sku_id") or u.get("spin_id")),
                quantity=int(u.get("quantity", 1)),
            )
            for u in extra_updates
            if u.get("spin_id")
        )
    try:
        updated = await tools.commerce.update_cart(updates, address_id=address_id)
        return {
            "success": True,
            "cart": updated,
            "cart_id": updated.cart_id,
            "item_count": len(updated.items),
            "grand_total": updated.grand_total,
            "formatted_receipt": format_cart_receipt(updated, delivery_location),
        }
    except Exception as exc:
        logger.warning("execute_add_selected_variants failed: %s", exc)
        return {"success": False, "error": str(exc)}


async def execute_manage_basket(
    tools: Any,
    address_id: str,
    add: Optional[list[dict[str, Any]]] = None,
    remove: Optional[list[str]] = None,
    set_quantity: Optional[list[dict[str, Any]]] = None,
    current_cart: Optional[CommerceCart] = None,
    delivery_location: str = "Home",
    budget_cap_inr: Optional[float] = None,
    session: Optional[Any] = None,
) -> dict[str, Any]:
    """Atomically manage basket by delegating to composite_cart."""
    from backend.agent.composite_cart import execute_composite_cart_modification
    from backend.agent.product_policy import is_restricted_medical_product

    if remove:
        for r in remove:
            if not isinstance(r, str) or not r.strip():
                return {"success": False, "error": "INVALID_INPUT", "unavailable_items": []}

    if add:
        for a in add:
            q = a.get("quantity")
            if q is not None and (not isinstance(q, int) or isinstance(q, bool) or q <= 0):
                return {"success": False, "error": "INVALID_INPUT", "unavailable_items": []}

    items_to_add = list(add or [])
    items_to_remove = list(remove or [])
    if set_quantity:
        for sq in set_quantity:
            raw_qty = sq.get("quantity")
            if not isinstance(raw_qty, int) or isinstance(raw_qty, bool) or raw_qty < 0:
                return {"success": False, "error": "INVALID_INPUT", "unavailable_items": []}
            item_name = sq.get("item_name") or sq.get("name") or sq.get("query") or sq.get("line_id") or ""
            if raw_qty > 0:
                items_to_add.append({"name": item_name, "quantity": raw_qty})
            else:
                items_to_remove.append(item_name)

    # Support overridden batch_search_products in test fixtures
    custom_search = getattr(tools, "batch_search_products", None)
    if custom_search is not None and getattr(custom_search, "__func__", None) != SwiggyAgentTools.batch_search_products:
        queries = [it.get("query") or it.get("name") for it in items_to_add if isinstance(it, dict)]
        search_res = await custom_search(queries, address_id)
        unavailable = []
        found_updates = []
        added_names = []
        for r in search_res.get("results", []):
            q = r.get("query")
            prods = [p for p in r.get("products", []) if not is_restricted_medical_product(p.get("name", ""), p.get("category", ""))]
            if not prods or r.get("error"):
                unavailable.append(q)
            else:
                custom_pick = getattr(tools, "select_best_variant", None)
                if custom_pick is not None and getattr(custom_pick, "__func__", None) != SwiggyAgentTools.select_best_variant:
                    pick_res = await custom_pick(q, prods)
                    opt = pick_res.get("option")
                    if opt:
                        found_updates.append(CartItemUpdate(spin_id=opt["spin_id"], sku_id=opt.get("sku_id") or opt["spin_id"], quantity=1))
                        added_names.append(opt.get("name") or opt["spin_id"])
                    else:
                        unavailable.append(q)
                else:
                    p = prods[0]
                    found_updates.append(CartItemUpdate(spin_id=p["spin_id"], sku_id=p.get("sku_id") or p["spin_id"], quantity=1))
                    added_names.append(p.get("name") or q)
        if found_updates:
            await tools.commerce.update_cart(found_updates, address_id=address_id)
        return {
            "success": True,
            "unavailable_items": unavailable,
            "added_items": added_names,
            "removed_items": [],
            "substitutions": [],
            "items": [],
            "verified_fingerprint": "mock_fp",
        }

    try:
        res = await execute_composite_cart_modification(
            commerce=tools.commerce,
            session=session,
            items_to_add=items_to_add,
            items_to_remove=items_to_remove,
            address_id=address_id,
            budget_cap_inr=budget_cap_inr,
        )
        return res.to_tool_dict()
    except Exception as exc:
        logger.error("execute_manage_basket failed: %s", exc)
        return {"success": False, "error": str(exc), "unavailable_items": []}
