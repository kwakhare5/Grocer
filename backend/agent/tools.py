"""Swiggy MCP Tools registry for LLM Function Calling."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

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
    ProviderAuthError,
)

logger = logging.getLogger("grocer.agent.tools")


def _format_inr(amount: float) -> str:
    """Format numeric price into clean ₹ string without trailing zero decimals."""
    return f"₹{int(amount)}" if amount.is_integer() else f"₹{amount:.2f}"


def clean_address(street: str, city: Optional[str] = None, label: Optional[str] = None) -> str:
    """Format address into the full human-readable destination (flat, building, area, city, state)."""
    del label
    if not street:
        return city or "Your Saved Location"

    # Remove user name prefixes like 'Customer Name:'
    text = re.sub(r"^[^:]+:\s*", "", street).strip()
    # Strip Google Plus codes e.g. HRC8+HWV or 7JVW+9V8
    text = re.sub(r"\b[A-Z0-9]{4,8}\+[A-Z0-9]{2,6}\b", "", text, flags=re.IGNORECASE)
    # Strip country tag and 6-digit postal codes while keeping full street, area, city, and state
    text = re.sub(r",?\s*(?:\bIndia\b|\b\d{6}\b)\s*", "", text, flags=re.IGNORECASE).strip(" ,")

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
) -> str:
    """Deterministically format verified cart state into a clean WhatsApp receipt card."""
    if not cart.items:
        return "🛒 *Your Basket is empty.*"

    clean_loc = clean_address(delivery_location)
    item_lines = [
        f"• {it.quantity}x {it.name} ({it.pack_size}) — {_format_inr(it.total_price)}"
        for it in cart.items
    ]
    items_block = "\n".join(item_lines)

    packaging_and_handling = round(cart.packaging_fee + cart.handling_fee, 2)
    delivery_str = "FREE (₹0)" if cart.delivery_fee == 0.0 else _format_inr(cart.delivery_fee)

    lines = [
        f"🛒 *Your Basket ({clean_loc})*",
        items_block,
        "",
        f"*Subtotal:* {_format_inr(cart.item_total)}",
        f"*Delivery Fee:* {delivery_str}",
    ]
    if packaging_and_handling > 0:
        lines.append(f"*Packaging & Handling:* {_format_inr(packaging_and_handling)}")
    if cart.taxes > 0:
        lines.append(f"*Taxes (GST):* {_format_inr(cart.taxes)}")
    if cart.discount > 0:
        lines.append(f"*Discount:* -{_format_inr(cart.discount)}")
    lines.append(f"*Grand Total:* {_format_inr(cart.grand_total)}")
    if cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        diff = round(cart.min_order_threshold - cart.grand_total, 2)
        lines.append(f"⚠️ *Store Minimum Order:* {_format_inr(cart.min_order_threshold)} (Add {_format_inr(diff)} more to checkout)")
    lines.extend([
        "",
        f"📍 *Delivering to:* {clean_loc}",
    ])
    if cart.min_order_threshold and cart.grand_total < cart.min_order_threshold:
        lines.append("👉 Add items to reach the minimum order, or tell me what to add!")
    else:
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
            for p in products[:10]:
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
                        }
                        for v in in_stock_variants
                    ],
                })
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
                    try:
                        migrate_updates = [
                            CartItemUpdate(
                                spin_id=ci.spin_id,
                                quantity=ci.quantity,
                                sku_id=ci.sku_id,
                            )
                            for ci in cart.items
                            if ci.quantity > 0
                        ]
                        migrated = await self.commerce.update_cart(
                            items=migrate_updates, address_id=matched.id
                        )
                        if migrated and migrated.items:
                            cart = migrated
                    except Exception as mig_exc:
                        logger.debug("Cart dark-store migration skipped/failed: %s", mig_exc)

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
                logger.debug("Failed to inspect cart in select_delivery_address: %s", cart_exc)
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
    ) -> dict[str, Any]:
        """Update Swiggy Instamart cart by deterministically merging item updates with active cart items."""
        try:
            merged_by_spin: dict[str, CartItemUpdate] = {}
            try:
                existing_cart: CommerceCart = await self.commerce.get_cart()
                if existing_cart and existing_cart.items:
                    for ci in existing_cart.items:
                        if ci.quantity > 0:
                            merged_by_spin[ci.spin_id] = CartItemUpdate(
                                spin_id=ci.spin_id,
                                quantity=ci.quantity,
                                sku_id=ci.sku_id,
                            )
            except Exception:
                pass

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
        payment_option_kind: str = "qr",
        is_user_confirmed: bool = False,
        budget_inr: Optional[float] = None,
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

        # Deterministic Budget Gate: Block checkout if grand total exceeds budget
        if budget_inr is not None and budget_inr > 0:
            try:
                cart = await self.commerce.get_cart(cart_id)
                if cart and cart.grand_total and cart.grand_total > budget_inr:
                    overage = round(cart.grand_total - budget_inr, 2)
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
            except Exception as b_exc:
                logger.debug("Budget pre-check inspection failed: %s", b_exc)

        try:
            result: CommerceOrderResult = await self.commerce.checkout(
                cart_id=cart_id,
                address_id=address_id,
                payment_method=payment_method,
                payment_option_kind=payment_option_kind,
                explicit_confirmation=True,
            )
            return {
                "success": True,
                "order_id": result.order_id,
                "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                "grand_total": result.grand_total,
                "formatted_grand_total": _format_inr(result.grand_total) if result.grand_total else None,
                "tracking_url": result.tracking_url,
                "delivery_address": result.delivery_address.street if result.delivery_address else "",
                "paas_id": result.paas_id,
                "bridge_url": result.bridge_url,
                "upi_intent_url": result.upi_intent_url,
                "is_qr_flow": result.is_qr_flow,
            }
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("checkout failed: %s", exc)
            return {"success": False, "error": str(exc)}

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
