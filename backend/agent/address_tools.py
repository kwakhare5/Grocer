"""Saved address retrieval and delivery address migration tools."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from backend.config import settings
from backend.agent.formatters import _format_inr, clean_address, format_cart_receipt
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart, DeliveryAddress
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.address_tools")


def match_pending_address_choice(
    pending_addrs: list[dict[str, Any]],
    norm_text: str = "",
    interactive_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Resolve customer selection from a list of pending address choices without regex or fake keywords."""
    if interactive_id:
        clean_id = (
            interactive_id.removeprefix("addr_choice_")
            .removeprefix("select_address:")
            .removeprefix("addr_")
        )
        for a in pending_addrs:
            if (
                str(a.get("_choice_code")) == clean_id
                or str(a.get("address_id")) == clean_id
                or str(a.get("id")) == clean_id
                or str(a.get("_choice_index")) == clean_id
                or str(a.get("id")) == interactive_id
                or str(a.get("address_id")) == interactive_id
            ):
                return a

    norm_text = (norm_text or "").strip().casefold()
    if not norm_text:
        return None

    # Handle numeric references: "1", "option 2", "choice 3", "#1"
    num_match = re.search(r"\b(?:option|choice|number|no\.?|#)?\s*(\d+)\b", norm_text)
    choice_num = num_match.group(1) if num_match else None

    for a in pending_addrs:
        if choice_num and str(a.get("_choice_index")) == choice_num:
            return a
        cand_values = {
            str(a.get("_choice_code", "")).casefold(),
            str(a.get("label", "")).casefold(),
            str(a.get("clean_address", "")).casefold(),
            str(a.get("id", "")).casefold(),
            str(a.get("address_id", "")).casefold(),
        }
        cand_values.discard("")
        if norm_text in cand_values:
            return a

    # Token matching with negation handling
    tokens = [t for t in re.split(r"\W+", norm_text) if len(t) > 2]
    positive_tokens = []
    for i, t in enumerate(tokens):
        if i > 0 and tokens[i - 1] in ("not", "dont", "never"):
            continue
        positive_tokens.append(t)

    for token in positive_tokens:
        token_matches = [
            a for a in pending_addrs
            if token in str(a.get("clean_address", "")).casefold()
            or token in str(a.get("label", "")).casefold()
            or token in str(a.get("area", "")).casefold()
            or token in str(a.get("city", "")).casefold()
        ]
        if len(token_matches) == 1:
            return token_matches[0]

    return None


def match_explicit_address(
    addresses: list[dict[str, Any]],
    norm_text: str = "",
) -> Optional[dict[str, Any]]:
    """Match a delivery destination against the customer's actual saved addresses."""
    if not norm_text or not addresses:
        return None
    norm_text = norm_text.casefold()

    # Detect negation phrases to avoid picking negated addresses
    negated_matches = set()
    for neg_phrase in re.findall(
        r"\b(?:do\s+not|don't|not|never)\s+(?:send|deliver|ship)?\s*(?:to|at)?\s+([^,.;]+)",
        norm_text,
    ):
        negated_matches.add(neg_phrase.strip())

    candidates = []
    for a in addresses:
        lbl = str(a.get("label") or "").casefold()
        clean_addr = str(a.get("clean_address") or "").casefold()
        area = str(a.get("area") or "").casefold()
        street = str(a.get("street") or "").casefold()
        city = str(a.get("city") or "").casefold()

        # Check if this address is explicitly negated in the instruction
        is_negated = any(
            (lbl and lbl in neg) or (area and area in neg) or (clean_addr and clean_addr in neg)
            for neg in negated_matches
        )
        if is_negated:
            continue

        # 1. Exact label match or direct command: "deliver to home", "send to pune office", "use pune office"
        if lbl and (
            re.search(
                rf"\b(?:deliver|send|ship|bring|drop|switch|change|take|use)\s*(?:to|at)?\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b(?:to|at)\s+(?:my\s+)?{re.escape(lbl)}\b"
                rf"|\b{re.escape(lbl)}\s+(?:address|location|destination|office|home)\b",
                norm_text,
            )
            or norm_text == lbl
            or norm_text.startswith(f"{lbl} ")
        ):
            candidates.append(a)
            continue

        # 2. Area/city/street destination match grounded in this address
        location_tokens = {
            t for t in re.findall(r"[a-z0-9]{3,}", f"{area} {city} {street}")
            if t not in {
                "road", "flat", "floor", "near", "opposite", "lane", "house", "building",
                "street", "block", "sector", "phase", "cross", "main", "layout",
            }
        }
        if any(
            re.search(
                rf"\b(?:deliver|send|ship|bring|drop|switch|change|use)\s+(?:to|at|it to)\s+(?:my\s+|the\s+)?{re.escape(t)}\b"
                rf"|\b(?:to|at)\s+(?:my\s+|the\s+)?{re.escape(t)}\s+(?:address|location|area|house|flat|apartment|branch|office|home)\b"
                rf"|\b{re.escape(t)}\s+(?:address|location)\b",
                norm_text,
            )
            for t in location_tokens
        ):
            candidates.append(a)

    if candidates:
        return candidates[0]

    return None


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
                "latitude": getattr(a, "latitude", None),
                "longitude": getattr(a, "longitude", None),
                "is_serviceable": getattr(a, "is_serviceable", True),
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
