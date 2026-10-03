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
)

logger = logging.getLogger("grocer.agent.tools")


def _format_inr(amount: float) -> str:
    """Format numeric price into clean ₹ string without trailing zero decimals."""
    return f"₹{int(amount)}" if amount.is_integer() else f"₹{amount:.2f}"


def _matches_requested_product(query: str, product: dict[str, Any]) -> bool:
    """Reject loose provider search hits that do not contain the requested product words."""
    words = [word for word in re.findall(r"[\w]+", query.casefold())
             if word not in {"a", "an", "the", "of", "for"}]
    name = " ".join(str(product.get(field) or "") for field in ("name", "pack_size")).casefold()
    return bool(words) and all(word in name for word in words)


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
        if len(clean_queries) > 30:
            return {"success": False, "error": "TOO_MANY_QUERIES", "retryable": False}

        semaphore = asyncio.Semaphore(3)

        async def _search_one(q: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    res = await self.search_products(q, address_id)
                    if not res.get("success"):
                        return {"query": q, "products": [], "error": res.get("error") or "SEARCH_UNAVAILABLE"}
                    prods = res.get("products", [])[:2]
                    compact_prods = []
                    for p in prods:
                        v = p.get("variants", [{}])[0] if p.get("variants") else {}
                        compact_prods.append({
                            "name": p.get("name"),
                            "category": p.get("category"),
                            "brand": p.get("brand"),
                            "spin_id": v.get("spin_id"),
                            "sku_id": v.get("sku_id"),
                            "pack_size": v.get("pack_size"),
                            "price": v.get("price"),
                            "formatted_price": v.get("formatted_price"),
                        })
                    return {"query": q, "products": compact_prods}
                except Exception as exc:
                    return {"query": q, "products": [], "error": str(exc)}

        batch_results = await asyncio.gather(*[_search_one(q) for q in clean_queries])
        return {
            "success": True,
            "results": batch_results,
        }

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
            # Use updated cart directly if populated to save network roundtrip, otherwise fallback to get_cart
            if updated.items or updated.grand_total > 0:
                verified = updated
            else:
                verified = await self.commerce.get_cart(updated.cart_id)
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

    async def quick_add_items(
        self,
        items: list[dict[str, Any]],
        address_id: str,
        budget_cap_inr: Optional[float] = None,
        delivery_location: str = "Home",
        ingredient_budget_inr: Optional[float] = None,
        ingredient_extras_text: str = "",
        ingredient_spin_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search products, resolve in-stock variants, respect budget, and update cart in a single atomic pass."""
        if not items or not address_id:
            return {"success": False, "error": "MISSING_ARGUMENTS"}

        added_descriptions: list[str] = []
        unavailable_items: list[str] = []
        restricted_items: list[str] = []
        budget_blocked_items: list[str] = []
        cart_updates: list[dict[str, Any]] = []
        query_by_spin: dict[str, str] = {}
        last_update_result: dict[str, Any] | None = None
        scoped_ids = list(ingredient_spin_ids or [])
        has_budget = budget_cap_inr is not None or ingredient_budget_inr is not None

        queries = [item.get("query", "").strip() for item in items if item.get("query")]
        search_res = await self.batch_search_products(queries, address_id)
        if not search_res.get("success"):
            return {"success": False, "error": search_res.get("error") or "SEARCH_UNAVAILABLE",
                    "retryable": bool(search_res.get("retryable", True)),
                    "message": "I couldn't check every requested item, so I left the basket unchanged."}
        search_errors = {
            item["query"]: item["error"]
            for item in search_res.get("results", [])
            if item.get("error")
        }
        if any(error == "AUTH_EXPIRED" for error in search_errors.values()):
            return {"success": False, "error": "AUTH_EXPIRED", "retryable": False}
        search_failed_items = list(search_errors)
        results_by_query = {
            item["query"]: item.get("products", [])
            for item in (search_res.get("results", []) if search_res.get("success") else [])
        }

        for it in items:
            q = it.get("query", "").strip()
            if q in search_errors:
                continue
            qty = max(1, int(it.get("quantity", 1)))
            pref_size = (it.get("preferred_pack_size") or "").lower()

            products = [product for product in results_by_query.get(q, [])
                        if _matches_requested_product(q, product)]
            selected_variant = None
            if pref_size:
                for p in products:
                    if pref_size in str(p.get("name", "")).lower() or pref_size in str(p.get("pack_size", "")).lower():
                        selected_variant = p
                        break
            if not selected_variant and products:
                selected_variant = products[0]

            if not selected_variant:
                unavailable_items.append(q)
                continue

            if is_restricted_medical_product(
                str(selected_variant.get("name") or ""),
                str(selected_variant.get("category") or ""),
            ):
                restricted_items.append(q)
                continue

            proposal = {
                "spin_id": selected_variant["spin_id"],
                "sku_id": selected_variant["sku_id"],
                "quantity": qty,
                "name": selected_variant["name"],
            }
            query_by_spin[proposal["spin_id"]] = q
            if has_budget:
                try:
                    before = await self.commerce.get_cart()
                except Exception:
                    return {"success": False, "error": "CART_UNAVAILABLE", "retryable": True,
                            "message": "I couldn't verify the basket before applying your budget."}
                if ingredient_budget_inr is not None and before.items and not scoped_ids:
                    return {"success": False, "error": "SCOPED_BUDGET_EXISTING_CART", "retryable": False,
                            "message": "Your basket already has items. Please clarify which existing items count as pizza ingredients."}
                if (budget_cap_inr is not None and before.items
                        and Decimal(str(before.grand_total)) > Decimal(str(budget_cap_inr))):
                    budget_blocked_items.append(q)
                    continue
                candidate = await self.update_cart([proposal], address_id, delivery_location)
                if not candidate.get("success"):
                    if candidate.get("error") == "CART_ITEMS_UNRESOLVED":
                        candidate["unavailable_items"] = [q]
                    return candidate
                is_ingredient = ingredient_budget_inr is not None and not is_explicit_extra(
                    q, ingredient_extras_text,
                )
                proposed_scope = set(scoped_ids)
                if is_ingredient:
                    proposed_scope.add(proposal["spin_id"])
                ingredient_total = sum(
                    Decimal(str(item["total_price"])) for item in candidate["items"]
                    if item["spin_id"] in proposed_scope
                )
                cap_exceeded = (
                    ingredient_total > Decimal(str(ingredient_budget_inr))
                    if ingredient_budget_inr is not None else
                    Decimal(str(candidate["grand_total"])) > Decimal(str(budget_cap_inr))
                )
                if cap_exceeded:
                    after = await self.commerce.get_cart()
                    if not await self._restore_cart(before, after, address_id):
                        return {"success": False, "error": "BUDGET_ROLLBACK_UNVERIFIED", "retryable": False,
                                "message": "The basket changed during a budget check. Please review it before ordering."}
                    budget_blocked_items.append(q)
                    continue
                if is_ingredient:
                    scoped_ids = list(proposed_scope)
                last_update_result = candidate
            cart_updates.append(proposal)
            added_descriptions.append(f"{qty}x {selected_variant['name']}")

        if not cart_updates:
            if search_failed_items and not unavailable_items and not restricted_items:
                return {
                    "success": False, "error": "SEARCH_UNAVAILABLE", "retryable": True,
                    "search_failed_items": search_failed_items,
                    "message": "I couldn't check those items right now. Please try again.",
                }
            return {
                "success": False,
                "error": "NO_ITEMS_AVAILABLE",
                "unavailable_items": unavailable_items,
                "restricted_items": restricted_items,
                "budget_blocked_items": budget_blocked_items,
                "search_failed_items": search_failed_items,
                "message": "No requested grocery item could be added."
            }

        update_result = last_update_result if has_budget else await self.update_cart(
            items=cart_updates, address_id=address_id, delivery_location=delivery_location,
        )

        if not update_result.get("success"):
            if update_result.get("error") == "CART_ITEMS_UNRESOLVED":
                missing = update_result.get("unresolved_items", [])
                update_result["unavailable_items"] = [
                    query_by_spin.get(item.get("spin_id"), str(item.get("spin_id")))
                    for item in missing if item.get("actual_quantity", 0) == 0
                ]
                update_result["reduced_items"] = [
                    f"{query_by_spin.get(item.get('spin_id'), item.get('spin_id'))} "
                    f"({item.get('actual_quantity', 0)} of {item.get('requested_quantity', 0)})"
                    for item in missing if item.get("actual_quantity", 0) > 0
                ]
            return update_result

        update_result["added_items"] = added_descriptions
        update_result["unavailable_items"] = unavailable_items
        update_result["restricted_items"] = restricted_items
        update_result["budget_blocked_items"] = budget_blocked_items
        update_result["search_failed_items"] = search_failed_items
        if ingredient_budget_inr is not None:
            update_result["ingredient_spin_ids"] = scoped_ids
            update_result["ingredient_item_total"] = sum(
                item["total_price"] for item in update_result["items"]
                if item["spin_id"] in scoped_ids
            )
        return update_result

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
