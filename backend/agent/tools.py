"""Swiggy MCP Tools registry for Gemini Function Calling."""
from __future__ import annotations

import logging
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
    CommerceError,
    ItemOutOfStockError,
    ProviderAuthError,
)

logger = logging.getLogger("grocer.agent.tools")


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
            }
        try:
            products: list[CommerceProductItem] = await self.commerce.search_products(
                address_id=address_id, query=query
            )
            results = []
            for p in products[:8]:
                in_stock_variants = [v for v in p.variants if v.in_stock is not False]
                if not in_stock_variants:
                    continue
                results.append({
                    "product_id": p.product_id,
                    "brand": p.brand,
                    "name": p.name,
                    "variants": [
                        {
                            "spin_id": v.spin_id,
                            "sku_id": v.sku_id,
                            "name": v.name,
                            "pack_size": v.pack_size,
                            "price": v.price,
                            "mrp": v.mrp,
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
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception as exc:
            logger.warning("search_products failed for query=%s: %s", query, exc)
            return {"success": False, "error": str(exc)}

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

    async def get_cart(self) -> dict[str, Any]:
        """Fetch current Swiggy Instamart cart contents and pricing."""
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
                }
                for item in cart.items
            ]
            return {
                "success": True,
                "cart_id": cart.cart_id,
                "items": items,
                "item_total": cart.item_total,
                "delivery_fee": cart.delivery_fee,
                "packaging_fee": cart.packaging_fee,
                "discount": cart.discount,
                "grand_total": cart.grand_total,
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
    ) -> dict[str, Any]:
        """Update Swiggy Instamart cart with a list of item updates."""
        try:
            cart_updates = [
                CartItemUpdate(
                    spin_id=it["spin_id"],
                    quantity=int(it["quantity"]),
                    sku_id=it.get("sku_id"),
                )
                for it in items
            ]
            updated: CommerceCart = await self.commerce.update_cart(
                items=cart_updates, address_id=address_id
            )
            verified: CommerceCart = await self.commerce.get_cart(updated.cart_id)
            items_summary = [
                {
                    "spin_id": item.spin_id,
                    "name": item.name,
                    "pack_size": item.pack_size,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                }
                for item in verified.items
            ]
            return {
                "success": True,
                "cart_id": verified.cart_id,
                "items": items_summary,
                "item_total": verified.item_total,
                "delivery_fee": verified.delivery_fee,
                "packaging_fee": verified.packaging_fee,
                "discount": verified.discount,
                "grand_total": verified.grand_total,
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
        cart_id: str,
        address_id: str,
        payment_method: str = "UPI",
        payment_option_kind: str = "qr",
        is_user_confirmed: bool = False,
    ) -> dict[str, Any]:
        """Place the final order on Swiggy Instamart. STRICTLY server-side gated."""
        if not is_user_confirmed:
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "message": (
                    "Order placement rejected: User has not provided explicit final confirmation. "
                    "You must ask the user to confirm the order summary and grand total first."
                ),
            }
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


GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "get_saved_addresses",
        "description": "Fetch saved delivery addresses for the user from Swiggy Instamart. Call this first if you don't know the address_id.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_products",
        "description": "Search products in the live Swiggy Instamart store catalogue for the selected delivery address. Returns in-stock variants, pack sizes, prices, spin_id, and sku_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Item name to search for (e.g. 'dairy milk', 'eggs', 'bread', 'amul milk').",
                },
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID.",
                },
            },
            "required": ["query", "address_id"],
        },
    },
    {
        "name": "get_cart",
        "description": "Fetch the current items, item total, delivery fee, and grand total from the user's active Swiggy Instamart cart.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_cart",
        "description": "Add, modify, or set items in the Swiggy Instamart cart. Pass the spin_id, sku_id, and desired quantity.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to update in the cart.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "spin_id": {"type": "string", "description": "The variant's spin_id from search results."},
                            "sku_id": {"type": "string", "description": "The variant's sku_id from search results."},
                            "quantity": {"type": "integer", "description": "Quantity to set in the cart."},
                            "name": {"type": "string", "description": "Human-readable item name."},
                        },
                        "required": ["spin_id", "quantity"],
                    },
                },
                "address_id": {
                    "type": "string",
                    "description": "The user's delivery address ID.",
                },
            },
            "required": ["items", "address_id"],
        },
    },
    {
        "name": "clear_cart",
        "description": "Empty all items from the active Swiggy Instamart cart.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "checkout",
        "description": (
            "Place the final order on Swiggy Instamart. For UPI, generates a dynamic payment link/QR code. "
            "ONLY call this tool after the user has explicitly confirmed the order summary and grand total."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {"type": "string", "description": "Active cart ID."},
                "address_id": {"type": "string", "description": "Selected delivery address ID."},
                "payment_method": {
                    "type": "string",
                    "description": "Payment method: 'UPI' or 'cash_on_delivery'. Defaults to 'UPI'.",
                },
                "payment_option_kind": {
                    "type": "string",
                    "description": "UPI option kind: 'qr' to generate dynamic UPI QR payment link. Defaults to 'qr'.",
                },
                "is_user_confirmed": {
                    "type": "boolean",
                    "description": "Must be true. Indicates the user gave explicit confirmation to place the order.",
                },
                "grand_total": {"type": "number", "description": "Verified grand total in rupees."},
            },
            "required": ["cart_id", "address_id", "is_user_confirmed"],
        },
    },
]
