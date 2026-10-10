"""Cart updates, variant additions, budget rollbacks, and line quantity adjustments."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from backend.agent.approval import cart_fingerprint
from backend.agent.budget import is_explicit_extra
from backend.agent.formatters import _format_inr, format_cart_receipt
from backend.integrations.commerce.exceptions import (
    CartExpiredError,
    ItemOutOfStockError,
    ProviderAuthError,
)
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.cart_actions")


async def execute_restore_cart(
    commerce: CommercePort, before: CommerceCart, after: CommerceCart, address_id: str
) -> bool:
    """Restore previous cart state on budget or mutation failures."""
    restore = [
        CartItemUpdate(spin_id=item.spin_id, sku_id=item.sku_id, quantity=item.quantity)
        for item in before.items
    ]
    before_spins = {item.spin_id for item in before.items}
    restore.extend(
        CartItemUpdate(spin_id=item.spin_id, sku_id=item.sku_id, quantity=0)
        for item in after.items
        if item.spin_id not in before_spins
    )
    try:
        await commerce.update_cart(restore, address_id=address_id)
        restored = await commerce.get_cart()
    except Exception:
        return False
    before_items = sorted((item.spin_id, item.sku_id, item.quantity) for item in before.items)
    restored_items = sorted((item.spin_id, item.sku_id, item.quantity) for item in restored.items)
    return (
        before_items == restored_items
        and Decimal(str(before.grand_total)) == Decimal(str(restored.grand_total))
    )


async def execute_update_cart(
    tools: Any,
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
            if expected_cart_state is not None and {
                "cart_id": existing_cart.cart_id,
                "address_id": existing_cart.address_id,
                "grand_total": existing_cart.grand_total,
                "items": sorted(
                    ([ci.spin_id, ci.sku_id, ci.quantity] for ci in existing_cart.items),
                    key=lambda entry: entry[0],
                ),
            } != expected_cart_state:
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
                            sku_id=ci.sku_id,
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

        if ingredient_budget_inr is not None:
            existing_spins = {item.spin_id for item in existing_cart.items}
            if any(item["quantity"] > 0 and item["spin_id"] not in existing_spins for item in items):
                return {
                    "success": False,
                    "error": "SCOPED_BUDGET_USE_SEARCH",
                    "retryable": False,
                    "message": "I need to search new items so I can keep the ingredient limit accurate.",
                }

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
        if ingredient_budget_inr is not None and sum(
            Decimal(str(item.total_price))
            for item in verified.items
            if item.spin_id in (ingredient_spin_ids or [])
        ) > Decimal(str(ingredient_budget_inr)):
            if not await execute_restore_cart(tools.commerce, existing_cart, verified, address_id):
                return {
                    "success": False,
                    "error": "BUDGET_ROLLBACK_UNVERIFIED",
                    "retryable": False,
                    "message": "I couldn't verify the basket after a budget check. Please review it before ordering.",
                }
            return {
                "success": False,
                "error": "INGREDIENT_BUDGET_EXCEEDED",
                "retryable": False,
                "message": "That change exceeds your ingredient-price limit. I kept the previous basket.",
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
                    and (actual is None or actual.sku_id != requested.sku_id)
                )
            ):
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
            "formatted_delivery_fee": (
                _format_inr(verified.delivery_fee) if verified.delivery_fee > 0 else "FREE (₹0)"
            ),
            "formatted_packaging_fee": _format_inr(verified.packaging_fee),
            "formatted_handling_fee": _format_inr(verified.handling_fee),
            "formatted_packaging_and_handling": _format_inr(packaging_and_handling),
            "formatted_taxes": _format_inr(verified.taxes),
            "formatted_total_fees": _format_inr(total_fees),
            "formatted_grand_total": _format_inr(verified.grand_total),
            "formatted_receipt": format_cart_receipt(verified, delivery_location),
        }
    except CartExpiredError:
        logger.warning("Cart expired during update_cart.")
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
        logger.warning("update_cart failed: %s", exc)
        return {"success": False, "error": str(exc)}


async def execute_add_selected_variants(
    tools: Any,
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
        existing_accepted = next((prior for prior in accepted if prior["spin_id"] == spin), None)
        if existing_accepted:
            existing_accepted["quantity"] += quantity
            continue
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
        proposed_ingredient_total = (
            ingredient_total + (delta if spin in ingredient_ids else line_total)
            if is_ingredient
            else ingredient_total
        )
        if (budget_cap_inr is not None and predicted_total + delta > Decimal(str(budget_cap_inr))) or (
            ingredient_budget_inr is not None
            and is_ingredient
            and proposed_ingredient_total > Decimal(str(ingredient_budget_inr))
        ):
            blocked.append(query)
            continue
        accepted.append({"spin_id": spin, "sku_id": option["sku_id"], "quantity": quantity})
        predicted_total += delta
        ingredient_total = proposed_ingredient_total
        if is_ingredient:
            ingredient_ids.add(spin)
    if extra_updates:
        for u in extra_updates:
            spin = u["spin_id"]
            sku = u.get("sku_id")
            qty = u["quantity"]
            if not any(prior["spin_id"] == spin for prior in accepted):
                previous = existing_by_spin.get(spin)
                previous_total = Decimal(str(previous.total_price)) if previous else Decimal(0)
                unit_p = Decimal(str(previous.unit_price)) if previous else Decimal(0)
                new_line_total = unit_p * qty
                delta = new_line_total - previous_total
                predicted_total += delta
                accepted.append({
                    "spin_id": spin,
                    "sku_id": sku or (previous.sku_id if previous else None),
                    "quantity": qty,
                })
    if not accepted:
        return {
            "success": False,
            "error": "BUDGET_BLOCKED",
            "budget_blocked_items": blocked,
            "message": "None of the selected items fit the stated limit. Your basket was not changed.",
        }
    result = await tools.update_cart(
        accepted,
        address_id,
        delivery_location,
        expected_cart_state=expected_cart_state,
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
    actual_ingredient_total = sum(
        (Decimal(str(item["total_price"])) for item in result["items"] if item["spin_id"] in ingredient_ids),
        Decimal(0),
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
    result["ingredient_spin_ids"] = list(ingredient_ids)
    result["added_items"] = [item["option"]["name"] for item in selected if item["query"] not in blocked]
    return result
