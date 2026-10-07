"""Swiggy MCP Tools registry for LLM Function Calling."""
from __future__ import annotations

import asyncio
import logging
import math
import re
from decimal import Decimal
from typing import Any, Optional

from backend.agent.approval import cart_fingerprint
from backend.agent.budget import is_explicit_extra
from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
    DeliveryAddress,
    CommerceOrderResult,
)
from backend.integrations.commerce.exceptions import (
    ItemOutOfStockError,
    OrderStateUnknownError,
    ProviderAuthError,
    ProviderRateLimitedError,
)

logger = logging.getLogger("grocer.agent.tools")

_HINDI_GROCERY_ALIASES = {
    "doodh": "milk", "anda": "egg", "ande": "egg", "aata": "atta",
    "chawal": "rice", "adrak": "ginger", "pyaz": "onion", "aloo": "potato",
    "dahi": "curd",
}
_HINDI_ALIAS_PATTERN = re.compile(
    rf"\b({'|'.join(_HINDI_GROCERY_ALIASES)})\b", re.IGNORECASE
)


def _format_inr(amount: float) -> str:
    """Format numeric price into clean ₹ string without trailing zero decimals."""
    return f"₹{int(amount)}" if amount.is_integer() else f"₹{amount:.2f}"


def _normalize_token(w: str) -> str:
    w = w.casefold()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and len(w) > 2 and not w.endswith("ss"):
        return w[:-1]
    return w


def _matches_requested_product(query: str, product: dict[str, Any]) -> bool:
    """Reject loose provider search hits that do not contain the requested product words."""
    raw_words = [_HINDI_GROCERY_ALIASES.get(w, w) for w in re.findall(r"[\w]+", query.casefold())
                 if w not in {"a", "an", "the", "of", "for"}]
    if not raw_words:
        return True
    name = " ".join(str(product.get(field) or "") for field in
                    ("brand", "product_name", "name", "pack_size")).casefold()
    name_tokens = {_normalize_token(t) for t in re.findall(r"[\w]+", name)}
    for rw in raw_words:
        norm_rw = _normalize_token(rw)
        if norm_rw in name or norm_rw in name_tokens or rw in name:
            continue
        return False
    return True


def clean_address(street: str, city: Optional[str] = None, label: Optional[str] = None) -> str:
    """Format address into the full human-readable destination (flat, building, area, city, state)."""
    del label
    if not street:
        return city or "Your Saved Location"

    # Remove user name prefixes like 'Customer Name:'
    text = re.sub(r"^[^:]+:\s*", "", street).strip()
    # Keep the postal code in the destination the customer reviews.
    text = re.sub(r",?\s*\bIndia\b\s*", "", text, flags=re.IGNORECASE).strip(" ,")

    # Deduplicate repeated comma-separated phrases while keeping ALL parts intact
    parts = [p.strip() for p in text.split(",") if p.strip()]
    seen: set[str] = set()
    cleaned_parts: list[str] = []
    for p in parts:
        p_low = p.casefold()
        if p_low not in seen and len(p) > 1:
            seen.add(p_low)
            cleaned_parts.append(p)

    res = ", ".join(cleaned_parts)
    if city and city.casefold() not in res.casefold():
        res = f"{res}, {city}" if res else city
    return res or street



def format_cart_receipt(
    cart: CommerceCart,
    delivery_location: str = "Home",
    allow_checkout_prompt: bool = True,
) -> str:
    """Deterministically format verified cart state into a clean WhatsApp receipt card."""
    if not cart.items:
        return "🛒 *Your Basket is empty.*"
    if cart.currency != "INR":
        return "⚠️ The provider basket is not priced in INR. Checkout is unavailable."

    clean_loc = clean_address(delivery_location)
    item_lines = [
        f"• {it.quantity}x {it.name} ({it.pack_size}) — {_format_inr(it.total_price)}"
        for it in cart.items
    ]
    items_block = "\n".join(item_lines)

    lines = [
        f"🛒 *Your Basket ({clean_loc})*",
        items_block,
        "",
    ]
    if not cart.billing_complete:
        lines.append("*Provider bill:* incomplete; fee breakdown and payable amount need verification")
    elif cart.bill_lines:
        lines.extend(
            f"*{line['label']}:* {_format_inr(float(line['value']))}"
            for line in cart.bill_lines
        )
    else:
        lines.append(f"*Subtotal:* {_format_inr(cart.item_total)}")
        delivery_text = "FREE (₹0)" if cart.delivery_fee == 0 else _format_inr(cart.delivery_fee)
        lines.append(f"*Delivery Fee:* {delivery_text}")
        packaging_and_handling = round(cart.packaging_fee + cart.handling_fee, 2)
        if packaging_and_handling:
            lines.append(f"*Packaging & Handling:* {_format_inr(packaging_and_handling)}")
        if cart.taxes:
            lines.append(f"*Taxes (GST):* {_format_inr(cart.taxes)}")
        if cart.discount:
            lines.append(f"*Discount:* -{_format_inr(cart.discount)}")
    lines.append(
        f"*Grand Total:* {_format_inr(cart.grand_total)}"
        if cart.grand_total > 0 else "*Grand Total:* unavailable"
    )
    if not cart.billing_complete:
        lines.append("⚠️ Provider bill is incomplete. Checkout is unavailable until it can be verified.")
    elif cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        diff = round(cart.min_order_threshold - cart.grand_total, 2)
        lines.append(f"⚠️ *Store Minimum Order:* {_format_inr(cart.min_order_threshold)} (Add {_format_inr(diff)} more to checkout)")
    lines.extend([
        "",
        f"📍 *Delivering to:* {clean_loc}",
    ])
    if not cart.billing_complete:
        lines.append("👉 Please wait while I verify the provider bill.")
    elif cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        lines.append("👉 Add items to reach the minimum order, or tell me what to add!")
    elif allow_checkout_prompt:
        lines.append("👉 Reply *Confirm* to place order, or tell me what to change!")
    return "\n".join(lines)


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
            try:
                provider_query = _HINDI_ALIAS_PATTERN.sub(
                    lambda match: _HINDI_GROCERY_ALIASES[match.group().casefold()], q
                )
                res = await self.search_products(provider_query, address_id)
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
                return {"query": q, "products": compact_prods}
            except Exception as exc:
                return {"query": q, "products": [], "error": str(exc)}

        batch_results: list[dict[str, Any]] = []
        for start in range(0, len(clean_queries), 3):
            if start:
                await asyncio.sleep(3)
            wave = await asyncio.gather(*[_search_one(q) for q in clean_queries[start:start + 3]])
            failed = (next((item for item in wave if item.get("error") == "RATE_LIMITED"), None)
                      or next((item for item in wave if item.get("error") == "AUTH_EXPIRED"), None)
                      or next((item for item in wave if item.get("error")), None))
            if failed:
                return {"success": False, "error": failed["error"], "retryable": False,
                        "retry_after_seconds": failed.get("retry_after_seconds")}
            batch_results.extend(wave)
        return {
            "success": True,
            "results": batch_results,
        }

    async def prepare_variant_choices(
        self, items: list[dict[str, Any]], address_id: str,
    ) -> dict[str, Any]:
        """Resolve every requested item to customer-visible SKU choices without writing the cart."""
        if not address_id or not isinstance(items, list) or not 1 <= len(items) <= 30:
            return {"success": False, "error": "INVALID_CART_PROPOSAL"}
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                return {"success": False, "error": "INVALID_CART_PROPOSAL"}
            query, quantity = item.get("query"), item.get("quantity", 1)
            if not isinstance(query, str) or not query.strip() or type(quantity) is not int or not 1 <= quantity <= 99:
                return {"success": False, "error": "INVALID_CART_PROPOSAL"}
            normalized.append({"query": query.strip(), "quantity": quantity,
                               "preferred_pack_size": str(item.get("preferred_pack_size") or "").strip()})

        search = await self.batch_search_products([item["query"] for item in normalized], address_id)
        if not search.get("success"):
            return search
        groups: list[dict[str, Any]] = []
        unavailable: list[str] = []
        restricted: list[str] = []
        for index, (item, result) in enumerate(zip(normalized, search["results"], strict=True), 1):
            if result.get("error"):
                return {"success": False, "error": result["error"],
                        "retry_after_seconds": result.get("retry_after_seconds")}
            options: list[dict[str, Any]] = []
            seen: set[str] = set()
            for product in result.get("products", []):
                if not _matches_requested_product(item["query"], product):
                    continue
                if is_restricted_medical_product(str(product.get("name") or ""),
                                                 str(product.get("category") or "")):
                    restricted.append(item["query"])
                    continue
                spin_id, sku_id = product.get("spin_id"), product.get("sku_id")
                if not isinstance(spin_id, str) or not spin_id or spin_id in seen or not isinstance(sku_id, str):
                    continue
                pack = str(product.get("pack_size") or "")
                preferred = item["preferred_pack_size"].casefold()
                if preferred and preferred not in (
                    pack + " " + str(product.get("name") or "")
                    + " " + str(product.get("product_name") or "")
                ).casefold():
                    continue
                price = product.get("price")
                if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price < 0:
                    continue
                seen.add(spin_id)
                options.append({"code": f"{index}{chr(64 + len(options) + 1)}",
                                "spin_id": spin_id, "sku_id": sku_id,
                                "name": str(product.get("name") or item["query"]),
                                "pack_size": pack, "price": float(price),
                                "max_quantity": product.get("max_quantity")})
            if options:
                groups.append({"query": item["query"], "quantity": item["quantity"],
                               "options": options[:6], "more_available": len(options) > 6})
            elif item["query"] not in restricted:
                unavailable.append(item["query"])
        return {"success": True, "needs_variant_choice": bool(groups), "groups": groups,
                "unavailable_items": unavailable, "restricted_items": list(dict.fromkeys(restricted))}

    async def get_saved_addresses(self, customer_id: str) -> dict[str, Any]:
        """Retrieve the user's saved delivery addresses from Swiggy."""
        try:
            addresses: list[DeliveryAddress] = await self.commerce.get_addresses(customer_id)
            formatted = [
                {
                    "address_id": a.id,
                    "label": a.label or a.street or "Saved Address",
                    "street": a.street,
                    "city": a.city,
                    "is_default": getattr(a, "is_default", False),
                    "clean_address": clean_address(a.street, a.city, label=a.label),
                }
                for a in addresses
            ]
            return {
                "success": True,
                "addresses": formatted,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("get_saved_addresses failed for customer=%s: %s", customer_id, exc)
            return {"success": False, "error": str(exc)}

    async def select_delivery_address(
        self, customer_id: str, address_id: str
    ) -> dict[str, Any]:
        """Validate and select an active delivery address from saved addresses."""
        if not address_id:
            return {"success": False, "error": "address_id is required."}
        try:
            addresses: list[DeliveryAddress] = await self.commerce.get_addresses(customer_id)
            matched = next((a for a in addresses if str(a.id) == str(address_id)), None)
            if not matched:
                return {
                    "success": False,
                    "error": f"Address ID '{address_id}' not found in user's saved addresses.",
                }
            clean_loc = clean_address(matched.street, matched.city, label=matched.label)
            res: dict[str, Any] = {
                "success": True,
                "address_id": matched.id,
                "label": matched.label or matched.street or "Selected Address",
                "street": matched.street,
                "city": matched.city,
                "clean_address": clean_loc,
            }
            # Check if active cart exists for this customer and migrate it to the new dark store
            try:
                cart: CommerceCart = await self.commerce.get_cart()
                if cart and cart.items:
                    migrate_updates = [
                        CartItemUpdate(spin_id=ci.spin_id, quantity=ci.quantity, sku_id=ci.sku_id)
                        for ci in cart.items if ci.quantity > 0
                    ]
                    try:
                        migrated = await self.commerce.update_cart(
                            items=migrate_updates, address_id=matched.id
                        )
                    except Exception as mig_exc:
                        logger.warning("Cart address migration failed: %s", type(mig_exc).__name__)
                        return {"success": False, "error": "ADDRESS_CHANGE_FAILED",
                                "message": "I couldn't move your basket to that address. Your previous destination remains selected."}
                    requested = {(item.spin_id, item.sku_id): item.quantity for item in migrate_updates}
                    received = {(item.spin_id, item.sku_id): item.quantity for item in migrated.items}
                    if requested != received or (migrated.address_id and migrated.address_id != matched.id):
                        return {"success": False, "error": "ADDRESS_CHANGE_FAILED",
                                "message": "I couldn't verify every item at that address. Please review your basket again."}
                    cart = migrated

                    res["has_active_cart"] = True
                    res["item_count"] = len(cart.items)
                    res["grand_total"] = cart.grand_total
                    receipt = format_cart_receipt(cart, delivery_location=clean_loc)
                    res["formatted_receipt"] = receipt
                    res["instruction"] = (
                        f"Delivery address successfully updated to {clean_loc}. "
                        f"The customer already has an active basket with {len(cart.items)} items (Grand Total: {_format_inr(cart.grand_total)}). "
                        f"You MUST immediately display the updated delivery address and the current cart receipt, and ask them to reply 'Confirm' to place the order. "
                        f"DO NOT ask 'What would you like to order today?'."
                    )
                else:
                    res["has_active_cart"] = False
                    res["instruction"] = (
                        f"Delivery address set to {clean_loc}. The basket is currently empty. "
                        f"Ask the customer what groceries they would like to order."
                    )
            except Exception as cart_exc:
                logger.warning("Failed to inspect cart in select_delivery_address: %s", type(cart_exc).__name__)
                return {"success": False, "error": "CART_UNAVAILABLE",
                        "message": "I couldn't verify your basket at the new address."}
            return res
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("select_delivery_address failed: %s", exc)
            return {"success": False, "error": str(exc)}

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
        if not isinstance(address_id, str) or not address_id or not isinstance(items, list) or not 1 <= len(items) <= 30:
            return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
        seen_spins: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
            spin = item.get("spin_id")
            sku = item.get("sku_id")
            quantity = item.get("quantity")
            if (not isinstance(spin, str) or not 1 <= len(spin) <= 128
                    or spin in seen_spins or type(quantity) is not int or not 0 <= quantity <= 99
                    or (sku is not None and (not isinstance(sku, str) or not 1 <= len(sku) <= 128))):
                return {"success": False, "error": "INVALID_CART_PROPOSAL", "retryable": False}
            seen_spins.add(spin)
        try:
            merged_by_spin: dict[str, CartItemUpdate] = {}
            try:
                existing_cart: CommerceCart = await self.commerce.get_cart()
                if existing_cart is None:
                    return {"success": False, "error": "CART_UNAVAILABLE", "retryable": False}
                if expected_cart_state is not None and {
                    "cart_id": existing_cart.cart_id,
                    "address_id": existing_cart.address_id,
                    "grand_total": existing_cart.grand_total,
                    "items": sorted(
                        ([ci.spin_id, ci.sku_id, ci.quantity] for ci in existing_cart.items),
                        key=lambda entry: entry[0],
                    ),
                } != expected_cart_state:
                    return {"success": False, "error": "CART_CHANGED", "retryable": False,
                            "message": "Your Swiggy basket changed. Please review it before adding these items."}
                if existing_cart and existing_cart.items:
                    for ci in existing_cart.items:
                        if ci.quantity > 0:
                            merged_by_spin[ci.spin_id] = CartItemUpdate(
                                spin_id=ci.spin_id,
                                quantity=ci.quantity,
                                sku_id=ci.sku_id,
                            )
            except ProviderAuthError:
                raise
            except Exception:
                return {"success": False, "error": "CART_UNAVAILABLE", "retryable": False,
                        "message": "I couldn't read the current basket, so I didn't change it."}

            if ingredient_budget_inr is not None:
                existing_spins = {item.spin_id for item in existing_cart.items}
                if any(item["quantity"] > 0 and item["spin_id"] not in existing_spins for item in items):
                    return {"success": False, "error": "SCOPED_BUDGET_USE_SEARCH", "retryable": False,
                            "message": "I need to search new items so I can keep the ingredient limit accurate."}

            for it in items:
                spin = str(it["spin_id"])
                qty = int(it["quantity"])
                sku = it.get("sku_id") or (merged_by_spin[spin].sku_id if spin in merged_by_spin else None)
                merged_by_spin[spin] = CartItemUpdate(
                    spin_id=spin,
                    quantity=qty,
                    sku_id=sku,
                )

            cart_updates = list(merged_by_spin.values())
            updated: CommerceCart = await self.commerce.update_cart(
                items=cart_updates, address_id=address_id
            )
            # Swiggy's cart response is not a substitute for a fresh provider read-back.
            try:
                verified = await self.commerce.get_cart(updated.cart_id)
            except Exception as exc:
                logger.warning("Cart read-back failed after provider write: %s", exc)
                return {"success": False, "error": "CART_WRITE_UNVERIFIED", "retryable": False,
                        "message": "Swiggy may have changed your basket, but I couldn't verify it. Please show your basket before trying again."}
            if ingredient_budget_inr is not None and sum(
                Decimal(str(item.total_price)) for item in verified.items
                if item.spin_id in (ingredient_spin_ids or [])
            ) > Decimal(str(ingredient_budget_inr)):
                if not await self._restore_cart(existing_cart, verified, address_id):
                    return {"success": False, "error": "BUDGET_ROLLBACK_UNVERIFIED", "retryable": False,
                            "message": "I couldn't verify the basket after a budget check. Please review it before ordering."}
                return {"success": False, "error": "INGREDIENT_BUDGET_EXCEEDED", "retryable": False,
                        "message": "That change exceeds your ingredient-price limit. I kept the previous basket."}
            actual_by_spin = {item.spin_id: item for item in verified.items}
            unresolved_items = []
            for requested in cart_updates:
                actual = actual_by_spin.get(requested.spin_id)
                actual_quantity = actual.quantity if actual else 0
                if (actual_quantity != requested.quantity
                        or (requested.quantity > 0 and requested.sku_id
                            and (actual is None or actual.sku_id != requested.sku_id))):
                    unresolved_items.append({
                        "spin_id": requested.spin_id,
                        "sku_id": requested.sku_id,
                        "requested_quantity": requested.quantity,
                        "actual_quantity": actual_quantity,
                        "actual_sku_id": actual.sku_id if actual else None,
                    })
            if unresolved_items:
                return {
                    "success": False,
                    "error": "CART_ITEMS_UNRESOLVED",
                    "retryable": False,
                    "cart_id": verified.cart_id,
                    "verified_fingerprint": cart_fingerprint(verified, address_id),
                    "unresolved_items": unresolved_items,
                    "formatted_receipt": format_cart_receipt(verified, delivery_location),
                    "message": "Swiggy changed or omitted an item. Please resolve each difference before approval.",
                }
            items_summary = [
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
                "formatted_delivery_fee": _format_inr(verified.delivery_fee) if verified.delivery_fee > 0 else "FREE (₹0)",
                "formatted_packaging_fee": _format_inr(verified.packaging_fee),
                "formatted_handling_fee": _format_inr(verified.handling_fee),
                "formatted_packaging_and_handling": _format_inr(packaging_and_handling),
                "formatted_taxes": _format_inr(verified.taxes),
                "formatted_total_fees": _format_inr(total_fees),
                "formatted_grand_total": _format_inr(verified.grand_total),
                "formatted_receipt": format_cart_receipt(verified, delivery_location),
            }
        except ItemOutOfStockError as exc:
            return {
                "success": False,
                "error": "ITEM_OUT_OF_STOCK",
                "spin_id": exc.spin_id,
                "available_quantity": exc.available_quantity,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("update_cart failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _restore_cart(self, before: CommerceCart, after: CommerceCart, address_id: str) -> bool:
        restore = [CartItemUpdate(spin_id=item.spin_id, sku_id=item.sku_id, quantity=item.quantity)
                   for item in before.items]
        before_spins = {item.spin_id for item in before.items}
        restore.extend(CartItemUpdate(spin_id=item.spin_id, sku_id=item.sku_id, quantity=0)
                       for item in after.items if item.spin_id not in before_spins)
        try:
            await self.commerce.update_cart(restore, address_id=address_id)
            restored = await self.commerce.get_cart()
        except Exception:
            return False
        before_items = sorted((item.spin_id, item.sku_id, item.quantity) for item in before.items)
        restored_items = sorted((item.spin_id, item.sku_id, item.quantity) for item in restored.items)
        return (before_items == restored_items
                and Decimal(str(before.grand_total)) == Decimal(str(restored.grand_total)))

    async def add_selected_variants(
        self, selected: list[dict[str, Any]], address_id: str, current_cart: CommerceCart,
        expected_cart_state: dict[str, Any], delivery_location: str = "Home",
        budget_cap_inr: float | None = None, ingredient_budget_inr: float | None = None,
        ingredient_extras_text: str = "", ingredient_spin_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Apply customer-chosen, freshly verified SKUs in one cart update."""
        existing_by_spin = {item.spin_id: item for item in current_cart.items}
        ingredient_ids = set(ingredient_spin_ids or [])
        ingredient_total = sum(
            (Decimal(str(item.total_price)) for item in current_cart.items if item.spin_id in ingredient_ids),
            Decimal(0),
        )
        predicted_total = Decimal(str(current_cart.grand_total))
        accepted: list[dict[str, Any]] = []
        blocked: list[str] = []
        for item in selected:
            option, query, quantity = item["option"], item["query"], item["quantity"]
            spin = option["spin_id"]
            if any(prior["spin_id"] == spin for prior in accepted):
                return {"success": False, "error": "DUPLICATE_SELECTED_PRODUCT",
                        "message": "The same product was selected twice. Please revise the choices."}
            max_quantity = option.get("max_quantity")
            if isinstance(max_quantity, int) and quantity > max_quantity:
                blocked.append(query)
                continue
            line_total = Decimal(str(option["price"])) * quantity
            previous = existing_by_spin.get(spin)
            previous_total = Decimal(str(previous.total_price)) if previous else Decimal(0)
            delta = line_total - previous_total
            is_ingredient = ingredient_budget_inr is not None and not is_explicit_extra(
                query, ingredient_extras_text,
            )
            proposed_ingredient_total = ingredient_total + (
                delta if spin in ingredient_ids else line_total
            ) if is_ingredient else ingredient_total
            if (budget_cap_inr is not None and predicted_total + delta > Decimal(str(budget_cap_inr))) or (
                ingredient_budget_inr is not None and is_ingredient
                and proposed_ingredient_total > Decimal(str(ingredient_budget_inr))
            ):
                blocked.append(query)
                continue
            accepted.append({"spin_id": spin, "sku_id": option["sku_id"], "quantity": quantity})
            predicted_total += delta
            ingredient_total = proposed_ingredient_total
            if is_ingredient:
                ingredient_ids.add(spin)
        if not accepted:
            return {"success": False, "error": "BUDGET_BLOCKED", "budget_blocked_items": blocked,
                    "message": "None of the selected items fit the stated limit. Your basket was not changed."}
        result = await self.update_cart(
            accepted, address_id, delivery_location,
            expected_cart_state=expected_cart_state,
        )
        if not result.get("success"):
            if result.get("error") == "CART_ITEMS_UNRESOLVED":
                by_spin = {item["option"]["spin_id"]: item["query"] for item in selected}
                unresolved = [by_spin.get(item["spin_id"], item["spin_id"])
                              for item in result.get("unresolved_items", [])]
                result["message"] = (
                    "Swiggy omitted or changed: " + ", ".join(unresolved)
                    + ". Please review the basket before ordering.\n\n"
                    + result.get("formatted_receipt", "")
                )
            return result
        actual_ingredient_total = sum(
            (Decimal(str(item["total_price"])) for item in result["items"]
             if item["spin_id"] in ingredient_ids), Decimal(0),
        )
        over_limit = (
            budget_cap_inr is not None
            and Decimal(str(result["grand_total"])) > Decimal(str(budget_cap_inr))
        ) or (
            ingredient_budget_inr is not None
            and actual_ingredient_total > Decimal(str(ingredient_budget_inr))
        )
        if over_limit:
            try:
                after = await self.commerce.get_cart()
                restored = await self._restore_cart(current_cart, after, address_id)
            except Exception:
                restored = False
            return {"success": False,
                    "error": "BUDGET_EXCEEDED" if restored else "BUDGET_ROLLBACK_UNVERIFIED",
                    "message": ("The live total changed and exceeded your limit. I restored your previous basket."
                                if restored else "The live total changed and I could not verify a rollback. Please review your basket."),
                    "budget_blocked_items": blocked}
        result["budget_blocked_items"] = blocked
        result["ingredient_spin_ids"] = list(ingredient_ids)
        result["added_items"] = [item["option"]["name"] for item in selected
                                 if item["query"] not in blocked]
        return result

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
        if not is_user_confirmed:
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "retryable": False,
                "message": (
                    "Order placement rejected: User has not provided explicit final confirmation. "
                    "You must ask the user to confirm the order summary and grand total first."
                ),
            }

        try:
            cart = await self.commerce.get_cart(cart_id)
        except Exception as exc:
            logger.warning("Checkout cart verification failed: %s", type(exc).__name__)
            return {"success": False, "error": "CART_UNAVAILABLE", "retryable": False,
                    "message": "I couldn't verify your basket. Please review it again before ordering."}
        if not cart or not math.isfinite(cart.grand_total) or cart.grand_total <= 0:
            return {"success": False, "error": "TOTAL_UNKNOWN", "retryable": False,
                    "message": "I couldn't verify the full payable total. No order was attempted."}
        if cart.currency != "INR":
            return {"success": False, "error": "CURRENCY_MISMATCH", "retryable": False,
                    "message": "The basket currency is not INR. No order was attempted."}
        if not cart.billing_complete:
            return {"success": False, "error": "BILL_INCOMPLETE", "retryable": False,
                    "message": "I couldn't verify every charge in the payable total. No order was attempted."}
        if cart_id and cart.cart_id and cart.cart_id != cart_id:
            return {"success": False, "error": "CART_CHANGED", "retryable": False,
                    "message": "Your basket changed. Please review the current basket again."}
        if address_id and cart.address_id and cart.address_id != address_id:
            return {"success": False, "error": "ADDRESS_CHANGED", "retryable": False,
                    "message": "The delivery address changed. Please review the current basket again."}
        if expected_cart_fingerprint and cart_fingerprint(cart, address_id) != expected_cart_fingerprint:
            return {"success": False, "error": "CART_CHANGED", "retryable": False,
                    "message": "Your basket or total changed. Please review it again."}
        if budget_inr is not None:
            if not math.isfinite(budget_inr) or budget_inr <= 0:
                return {"success": False, "error": "INVALID_BUDGET", "retryable": False,
                        "message": "I couldn't verify your spending limit. Please restate it."}
            if Decimal(str(cart.grand_total)) > Decimal(str(budget_inr)):
                overage = float(Decimal(str(cart.grand_total)) - Decimal(str(budget_inr)))
                return {
                    "success": False,
                    "error": "BUDGET_EXCEEDED",
                    "retryable": False,
                    "grand_total": cart.grand_total,
                    "budget_inr": budget_inr,
                    "message": (
                        f"Order placement blocked: Current grand total ₹{cart.grand_total:.0f} "
                        f"exceeds your budget of ₹{budget_inr:.0f} by ₹{overage:.0f}. "
                        "Please ask the user if they would like to remove an item or increase their budget."
                    ),
                }
        if not cart.items:
            return {"success": False, "error": "CART_EMPTY", "retryable": False,
                    "message": "Your basket is empty. No order was attempted."}
        medical_items = [
            item.name for item in cart.items
            if is_restricted_medical_product(item.name, item.category)
        ]
        if medical_items:
            return {
                "success": False, "error": "MEDICAL_PRODUCT_RESTRICTED", "retryable": False,
                "items": medical_items,
                "message": "Medical products cannot be ordered through this WhatsApp shopping flow.",
            }

        from backend.config import settings
        if settings.CHECKOUT_MODE == "live":
            try:
                options = await self.commerce.get_payment_options(cart_id, address_id)
            except ProviderAuthError:
                return {"success": False, "error": "AUTH_EXPIRED", "retryable": False,
                        "message": "Please reconnect Swiggy before choosing a payment option."}
            except Exception:
                logger.warning("Payment options could not be verified before checkout.")
                return {"success": False, "error": "PAYMENT_OPTIONS_UNAVAILABLE", "retryable": True,
                        "message": "I couldn't verify the current payment options. No order was attempted."}
            available = [option for option in options if option.id and option.is_available
                         and ((option.method == "UPI" and option.kind == "intent")
                              or option.method in ("Cash", "COD", "SwiggyPay"))]
            if not payment_option_id:
                return {"success": False, "error": "PAYMENT_CHOICE_REQUIRED", "retryable": False,
                        "payment_options": [option.model_dump() for option in available[:10]],
                        "message": "Please choose an available payment option before placing the order."}
            selected = next((option for option in options if option.id == payment_option_id
                             and option.kind == payment_option_kind and option.is_available), None)
            if selected is None or selected.method.casefold() != payment_method.casefold():
                return {"success": False, "error": "PAYMENT_OPTION_UNAVAILABLE", "retryable": False,
                        "message": "That payment option is no longer available. Please choose from the current options."}
            if selected.kind == "qr":
                return {"success": False, "error": "QR_ELIGIBILITY_UNVERIFIED", "retryable": False,
                        "message": "Scan-QR eligibility could not be verified for this basket. Please choose another available option."}

        try:
            result: CommerceOrderResult = await self.commerce.checkout(
                cart_id=cart_id,
                address_id=address_id,
                payment_method=payment_method,
                payment_option_kind=payment_option_kind,
                payment_option_id=payment_option_id,
                explicit_confirmation=True,
            )
            if result.status == "PAYMENT_PENDING" and not (
                result.order_id and result.paas_id and result.bridge_url
                and result.polling_interval_ms and result.polling_interval_ms > 0
                and result.max_time_to_poll_ms and result.max_time_to_poll_ms > 0
            ):
                return {
                    "success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False,
                    "order_id": result.order_id, "paas_id": result.paas_id,
                    "message": "Swiggy started a payment, but I couldn't verify the details needed to track it. Check Swiggy before trying again.",
                }
            return {
                "success": result.status not in ("ORDER_STATE_UNKNOWN", "FAILED"),
                "order_id": result.order_id,
                "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                "grand_total": result.grand_total,
                "formatted_grand_total": _format_inr(result.grand_total) if result.grand_total else None,
                "tracking_url": result.tracking_url,
                "delivery_address": result.delivery_address.street if result.delivery_address else "",
                "paas_id": result.paas_id,
                "polling_interval_ms": result.polling_interval_ms,
                "max_time_to_poll_ms": result.max_time_to_poll_ms,
                "bridge_url": result.bridge_url,
                "upi_intent_url": result.upi_intent_url,
                "is_qr_flow": result.is_qr_flow,
                "is_simulated": result.is_simulated,
                "message": result.message,
                "orders": [order.model_dump(mode="json") for order in result.orders],
                "success_count": result.success_count,
                "failure_count": result.failure_count,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except OrderStateUnknownError:
            return {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False,
                    "message": "I couldn't verify whether checkout completed. Please don't try again yet."}
        except Exception as exc:
            logger.warning("checkout outcome unverified after %s", type(exc).__name__)
            return {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False,
                    "message": "I couldn't verify whether checkout completed. Please don't try again yet."}

    async def track_order(self, order_id: str) -> dict[str, Any]:
        """Track the real-time delivery status and ETA of an existing order."""
        if not order_id:
            return {"success": False, "error": "order_id is required."}
        try:
            status = await self.commerce.track_order(order_id)
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
