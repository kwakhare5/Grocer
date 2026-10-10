"""Saved address retrieval and delivery address migration tools."""
from __future__ import annotations

import logging
from typing import Any

from backend.agent.formatters import _format_inr, clean_address, format_cart_receipt
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart, DeliveryAddress
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.address_tools")


async def execute_get_saved_addresses(commerce: CommercePort, customer_id: str) -> dict[str, Any]:
    """Retrieve the user's saved delivery addresses from Swiggy."""
    try:
        addresses: list[DeliveryAddress] = await commerce.get_addresses(customer_id)
        formatted = [
            {
                "address_id": a.id,
                "label": a.label or a.street or "Saved Address",
                "street": a.street,
                "city": a.city,
                "is_default": getattr(a, "is_default", False),
                "clean_address": clean_address(a.street, a.city, label=a.label, area=getattr(a, "area", None)),
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


async def execute_select_delivery_address(
    commerce: CommercePort, customer_id: str, address_id: str
) -> dict[str, Any]:
    """Validate and select an active delivery address from saved addresses."""
    if not address_id:
        return {"success": False, "error": "address_id is required."}
    try:
        addresses: list[DeliveryAddress] = await commerce.get_addresses(customer_id)
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
            cart: CommerceCart = await commerce.get_cart()
            if cart and cart.items:
                migrate_updates = [
                    CartItemUpdate(spin_id=ci.spin_id, quantity=ci.quantity, sku_id=ci.sku_id)
                    for ci in cart.items
                    if ci.quantity > 0
                ]
                try:
                    migrated = await commerce.update_cart(
                        items=migrate_updates, address_id=matched.id
                    )
                except Exception as mig_exc:
                    logger.warning("Cart address migration failed: %s", type(mig_exc).__name__)
                    return {
                        "success": False,
                        "error": "ADDRESS_CHANGE_FAILED",
                        "message": (
                            "I couldn't move your basket to that address. Your previous destination remains selected."
                        ),
                    }
                requested = {(item.spin_id, item.sku_id): item.quantity for item in migrate_updates}
                received = {(item.spin_id, item.sku_id): item.quantity for item in migrated.items}
                if requested != received or (migrated.address_id and migrated.address_id != matched.id):
                    return {
                        "success": False,
                        "error": "ADDRESS_CHANGE_FAILED",
                        "message": "I couldn't verify every item at that address. Please review your basket again.",
                    }
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
            return {
                "success": False,
                "error": "CART_UNAVAILABLE",
                "message": "I couldn't verify your basket at the new address.",
            }
        return res
    except ProviderAuthError as exc:
        return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
    except Exception as exc:
        logger.warning("select_delivery_address failed: %s", exc)
        return {"success": False, "error": str(exc)}
