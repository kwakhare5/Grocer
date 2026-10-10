"""Multi-item basket management, batch search handling, and auto-add orchestration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.catalog_ranker import _matches_item_name, _matches_requested_product
from backend.agent.formatters import format_cart_receipt
from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.basket_manager")


async def execute_manage_basket(
    tools: Any,
    address_id: str,
    add: Optional[list[dict[str, Any]]] = None,
    remove: Optional[list[str]] = None,
    set_quantity: Optional[list[dict[str, Any]]] = None,
    current_cart: Optional[CommerceCart] = None,
    delivery_location: str = "Home",
    budget_cap_inr: Optional[float] = None,
    ingredient_budget_inr: Optional[float] = None,
    ingredient_extras_text: str = "",
    ingredient_spin_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Atomically manage Swiggy Instamart basket: add items, remove items, or adjust quantities in a single turn."""
    if not address_id:
        return {"success": False, "error": "ADDRESS_REQUIRED"}

    if current_cart is None:
        try:
            current_cart = await tools.commerce.get_cart()
        except ProviderAuthError as exc:
            return {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        except Exception:
            current_cart = CommerceCart(
                cart_id="new_cart",
                items=[],
                item_total=0.0,
                grand_total=0.0,
                address_id=address_id,
                is_serviceable=True,
            )

    expected_cart_state = {
        "cart_id": current_cart.cart_id,
        "address_id": current_cart.address_id,
        "grand_total": current_cart.grand_total,
        "items": sorted(([it.spin_id, it.sku_id, it.quantity] for it in current_cart.items), key=lambda e: e[0]),
    }

    extra_updates: list[dict[str, Any]] = []
    removed_items: list[str] = []
    modified_items: list[str] = []
    unavailable_items: list[str] = []
    restricted_items: list[str] = []

    # 1. Process Removals
    if remove and isinstance(remove, list):
        for rem in remove:
            if not isinstance(rem, str) or not rem.strip():
                continue
            rem_clean = rem.strip()
            matched_any = False
            for ci in current_cart.items:
                if _matches_item_name(rem_clean, ci.name):
                    extra_updates.append({
                        "spin_id": ci.spin_id,
                        "sku_id": ci.sku_id,
                        "quantity": 0,
                    })
                    removed_items.append(ci.name)
                    matched_any = True
            if not matched_any:
                removed_items.append(rem_clean)

    # 2. Process Quantity Adjustments
    if set_quantity and isinstance(set_quantity, list):
        for sq in set_quantity:
            if not isinstance(sq, dict):
                continue
            q_text = str(sq.get("query") or "").strip()
            t_qty = sq.get("quantity")
            if not q_text or type(t_qty) is not int or not 0 <= t_qty <= 99:
                continue
            for ci in current_cart.items:
                if _matches_item_name(q_text, ci.name):
                    extra_updates.append({
                        "spin_id": ci.spin_id,
                        "sku_id": ci.sku_id,
                        "quantity": t_qty,
                    })
                    modified_items.append(f"{ci.name} -> {t_qty}")

    # 3. Process Additions
    selected_for_add: list[dict[str, Any]] = []
    if add and isinstance(add, list) and 1 <= len(add) <= 30:
        normalized_add = []
        for item in add:
            if not isinstance(item, dict):
                continue
            query, quantity = item.get("query"), item.get("quantity", 1)
            if not isinstance(query, str) or not query.strip() or type(quantity) is not int or not 1 <= quantity <= 99:
                continue
            normalized_add.append({
                "query": query.strip(),
                "quantity": quantity,
                "preferred_pack_size": str(item.get("preferred_pack_size") or "").strip(),
            })

        if normalized_add:
            search = await tools.batch_search_products([it["query"] for it in normalized_add], address_id)
            if not search.get("success"):
                return search

            for item, result in zip(normalized_add, search["results"], strict=True):
                if result.get("error"):
                    err_str = str(result.get("error"))
                    if err_str in ("RATE_LIMITED", "AUTH_EXPIRED", "SERVICE_UNAVAILABLE"):
                        return {
                            "success": False,
                            "error": result["error"],
                            "retry_after_seconds": result.get("retry_after_seconds"),
                        }
                    unavailable_items.append(item["query"])
                    continue

                raw_prods = result.get("products", [])
                has_medical = any(
                    is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or ""))
                    for p in raw_prods
                )
                if has_medical and not any(
                    _matches_requested_product(item["query"], p)
                    and not is_restricted_medical_product(str(p.get("name") or ""), str(p.get("category") or ""))
                    for p in raw_prods
                ):
                    restricted_items.append(item["query"])
                    continue

                best = tools.select_best_variant(item["query"], raw_prods, item["preferred_pack_size"])
                if best:
                    selected_for_add.append({
                        "option": best,
                        "query": item["query"],
                        "quantity": item["quantity"],
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
            ingredient_budget_inr=ingredient_budget_inr,
            ingredient_extras_text=ingredient_extras_text,
            ingredient_spin_ids=ingredient_spin_ids,
            extra_updates=extra_updates,
        )
        if not mutation.get("success"):
            return mutation
        mutation["added_items"] = [s["option"]["name"] for s in selected_for_add]
        mutation["removed_items"] = removed_items
        mutation["modified_items"] = modified_items
        mutation["unavailable_items"] = unavailable_items
        mutation["restricted_items"] = list(dict.fromkeys(restricted_items))
        return mutation

    # Nothing changed
    receipt = format_cart_receipt(current_cart, delivery_location)
    return {
        "success": True,
        "cart": current_cart,
        "cart_id": current_cart.cart_id,
        "item_count": len(current_cart.items),
        "items": [
            {
                "spin_id": item.spin_id,
                "sku_id": item.sku_id,
                "name": item.name,
                "quantity": item.quantity,
                "total_price": item.total_price,
            }
            for item in current_cart.items
        ],
        "grand_total": current_cart.grand_total,
        "formatted_receipt": receipt,
        "added_items": [],
        "removed_items": removed_items,
        "modified_items": modified_items,
        "unavailable_items": unavailable_items,
        "restricted_items": list(dict.fromkeys(restricted_items)),
    }


async def execute_quick_add_items(
    tools: Any,
    items: list[dict[str, Any]],
    address_id: str,
    current_cart: Optional[CommerceCart] = None,
    delivery_location: str = "Home",
    budget_cap_inr: Optional[float] = None,
    ingredient_budget_inr: Optional[float] = None,
    ingredient_extras_text: str = "",
    ingredient_spin_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Automatically find and add the best matching in-stock grocery items to the cart."""
    return await execute_manage_basket(
        tools=tools,
        address_id=address_id,
        add=items,
        current_cart=current_cart,
        delivery_location=delivery_location,
        budget_cap_inr=budget_cap_inr,
        ingredient_budget_inr=ingredient_budget_inr,
        ingredient_extras_text=ingredient_extras_text,
        ingredient_spin_ids=ingredient_spin_ids,
    )
