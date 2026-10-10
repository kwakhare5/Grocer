"""Engine tool execution dispatcher with checkout gating, address syncing, and error mapping."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from backend.agent.approval import cart_fingerprint
from backend.config import settings
from backend.integrations.commerce.exceptions import ProviderAuthError, ProviderRateLimitedError
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.tool_executor")


async def execute_engine_tool(
    engine: Any,
    name: str,
    args: dict[str, Any],
    *,
    customer_id: str,
    address_id: Optional[str],
    user_confirmed: Optional[bool] = None,
    current_cart: Optional[CommerceCart] = None,
) -> Any:
    """Dispatch a single function call to SwiggyAgentTools."""
    logger.info("Executing agent tool call: %s", name)
    if name == "get_saved_addresses":
        return await engine.tools.get_saved_addresses(customer_id)
    elif name == "select_delivery_address":
        engine.get_session(customer_id).pending_approval = None
        res = await engine.tools.select_delivery_address(customer_id, args.get("address_id", ""))
        if res.get("success") and res.get("address_id"):
            engine._customer_address[customer_id] = res["address_id"]
            engine._customer_address_label[customer_id] = (
                res.get("clean_address") or res.get("label") or "Selected Address"
            )
            engine._order_address_confirmed[customer_id] = True
        return res
    elif name == "get_go_to_items":
        addr = args.get("address_id") or address_id
        return await engine.tools.get_go_to_items(address_id=addr)
    elif name == "search_products":
        addr = args.get("address_id") or address_id
        return await engine.tools.search_products(args.get("query", ""), address_id=addr)
    elif name == "batch_search_products":
        addr = args.get("address_id") or address_id
        return await engine.tools.batch_search_products(args.get("queries", []), address_id=addr)
    elif name == "get_cart":
        loc = engine._customer_address_label.get(customer_id, "Home")
        return await engine.tools.get_cart(delivery_location=loc)
    elif name == "manage_basket":
        session = engine.get_session(customer_id)
        session.pending_approval = None
        loc = engine._customer_address_label.get(customer_id, "Home")
        result = await engine.tools.manage_basket(
            address_id=args.get("address_id") or address_id or "",
            add=args.get("add"),
            remove=args.get("remove"),
            set_quantity=args.get("set_quantity"),
            current_cart=current_cart,
            delivery_location=loc,
            budget_cap_inr=session.budget_inr,
            ingredient_budget_inr=session.ingredient_budget_inr,
            ingredient_extras_text=session.ingredient_extras_text or "",
            ingredient_spin_ids=session.ingredient_spin_ids,
        )
        if result.get("verified_fingerprint"):
            session.known_cart_fingerprint = result["verified_fingerprint"]
        if result.get("ingredient_spin_ids"):
            session.ingredient_spin_ids = result["ingredient_spin_ids"]
        return result
    elif name == "quick_add_items":
        session = engine.get_session(customer_id)
        session.pending_approval = None
        loc = engine._customer_address_label.get(customer_id, "Home")
        result = await engine.tools.quick_add_items(
            items=args.get("items", []),
            address_id=address_id or "",
            current_cart=current_cart,
            delivery_location=loc,
            budget_cap_inr=session.budget_inr,
            ingredient_budget_inr=session.ingredient_budget_inr,
            ingredient_extras_text=session.ingredient_extras_text or "",
            ingredient_spin_ids=session.ingredient_spin_ids,
        )
        if result.get("verified_fingerprint"):
            session.known_cart_fingerprint = result["verified_fingerprint"]
        if result.get("ingredient_spin_ids"):
            session.ingredient_spin_ids = result["ingredient_spin_ids"]
        return result
    elif name == "update_cart":
        session = engine.get_session(customer_id)
        session.pending_approval = None
        proposed = args.get("items", [])
        try:
            existing = await engine.commerce.get_cart()
        except ProviderAuthError:
            return {"success": False, "error": "AUTH_EXPIRED"}
        except ProviderRateLimitedError as exc:
            return {
                "success": False,
                "error": "RATE_LIMITED",
                "retry_after_seconds": exc.retry_after_seconds,
            }
        except Exception:
            return {"success": False, "error": "CART_UNAVAILABLE"}
        existing_by_spin = {item.spin_id: item for item in existing.items}
        if not isinstance(proposed, list) or any(
            not isinstance(item, dict) or type(item.get("quantity")) is not int
            for item in proposed
        ):
            return {"success": False, "error": "INVALID_CART_PROPOSAL"}
        if isinstance(proposed, list) and any(
            isinstance(item, dict)
            and item.get("quantity", 0) > 0
            and (
                item.get("spin_id") not in existing_by_spin
                or (
                    item.get("sku_id")
                    and item.get("sku_id") != existing_by_spin[item["spin_id"]].sku_id
                )
            )
            for item in proposed
        ):
            return {"success": False, "error": "VARIANT_SELECTION_REQUIRED"}
        addr = address_id
        loc = engine._customer_address_label.get(customer_id, "Home")
        result = await engine.tools.update_cart(
            proposed,
            address_id=addr or "",
            delivery_location=loc,
            ingredient_budget_inr=session.ingredient_budget_inr,
            ingredient_spin_ids=session.ingredient_spin_ids,
        )
        unresolved_by_spin = {
            item["spin_id"]: item for item in session.unresolved_items if item.get("spin_id")
        }
        if isinstance(proposed, list):
            for item in proposed:
                if isinstance(item, dict) and item.get("spin_id") and result.get("success"):
                    unresolved_by_spin.pop(str(item["spin_id"]), None)
        for item in result.get("unresolved_items", []):
            unresolved_by_spin[item["spin_id"]] = item
        session.unresolved_items = list(unresolved_by_spin.values())
        if result.get("verified_fingerprint"):
            session.known_cart_fingerprint = result["verified_fingerprint"]
        return result
    elif name == "clear_cart":
        result = await engine.tools.clear_cart()
        if result.get("success"):
            try:
                cart = await engine.commerce.get_cart()
            except Exception:
                cart = None
            if cart is None or cart.items:
                return {"success": False, "error": "CLEAR_UNVERIFIED"}
            engine.get_session(customer_id).unresolved_items.clear()
            engine.get_session(customer_id).known_cart_fingerprint = None
            engine.get_session(customer_id).external_cart_pending = False
            engine.get_session(customer_id).budget_inr = None
            engine.get_session(customer_id).ingredient_budget_inr = None
            engine.get_session(customer_id).ingredient_extras_text = None
            engine.get_session(customer_id).ingredient_spin_ids.clear()
            engine.reset_customer_order_address(customer_id)
        return result
    elif name == "checkout":
        sess = engine.get_session(customer_id)
        if sess.unresolved_items:
            return {
                "success": False,
                "error": "ITEMS_UNRESOLVED",
                "retryable": False,
                "message": "Please resolve each missing or reduced requested item before checkout.",
            }
        if sess.external_cart_pending:
            return {"success": False, "error": "EXTERNAL_CART_UNREVIEWED", "retryable": False}
        approval = sess.pending_approval
        if not user_confirmed or not approval or approval.expires_at <= time.time():
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "retryable": False,
                "message": "Please review the current basket and confirm it before checkout.",
            }
        checkout_address = args.get("address_id", "") or address_id or ""
        try:
            cart = await engine.commerce.get_cart(args.get("cart_id", ""))
        except Exception:
            return {
                "success": False,
                "error": "CART_UNAVAILABLE",
                "retryable": False,
                "message": "I couldn't verify your basket. Please review it again.",
            }
        if cart.address_id is None and checkout_address:
            cart.address_id = checkout_address
        if cart_fingerprint(cart, checkout_address) != approval.fingerprint:
            sess.pending_approval = None
            return {
                "success": False,
                "error": "CART_CHANGED",
                "retryable": False,
                "message": "Your basket or total changed. Please review it again.",
            }
        if sess.ingredient_budget_inr is not None:
            ingredient_total = sum(
                item.total_price for item in cart.items if item.spin_id in sess.ingredient_spin_ids
            )
            if ingredient_total > sess.ingredient_budget_inr:
                return {
                    "success": False,
                    "error": "INGREDIENT_BUDGET_EXCEEDED",
                    "retryable": False,
                    "message": "Recipe ingredients exceed the agreed price limit. Please review the basket.",
                }
        attempt_id = None
        if settings.CHECKOUT_MODE == "live":
            if engine.attempt_store is None:
                return {
                    "success": False,
                    "error": "DURABLE_ATTEMPT_REQUIRED",
                    "retryable": False,
                    "message": "Live checkout is unavailable until durable attempt tracking is ready.",
                }
            try:
                attempt_id = await engine.attempt_store.start(
                    customer_id,
                    cart.cart_id or "",
                    checkout_address,
                    approval.fingerprint,
                    cart.grand_total,
                )
            except Exception:
                logger.exception("Could not reserve durable checkout attempt.")
                return {"success": False, "error": "DURABLE_ATTEMPT_REQUIRED", "retryable": False}
            if attempt_id is None:
                return {
                    "success": False,
                    "error": "ATTEMPT_UNRESOLVED",
                    "retryable": False,
                    "message": "An earlier checkout or payment is unresolved. Further checkout is on hold.",
                }
        sess.pending_approval = None
        try:
            result = await engine.tools.checkout(
                cart_id=args.get("cart_id", ""),
                address_id=checkout_address,
                payment_method=sess.selected_payment_method or "UPI",
                payment_option_kind=sess.selected_payment_kind,
                payment_option_id=sess.selected_payment_id,
                is_user_confirmed=True,
                budget_inr=sess.budget_inr,
                expected_cart_fingerprint=approval.fingerprint,
            )
            if attempt_id is not None:
                await engine.attempt_store.finish(attempt_id, result)
            if result.get("error") in {
                "PAYMENT_CHOICE_REQUIRED",
                "PAYMENT_OPTION_UNAVAILABLE",
                "PAYMENT_OPTIONS_UNAVAILABLE",
                "QR_ELIGIBILITY_UNVERIFIED",
            }:
                sess.pending_approval = approval
            return result
        except Exception as exc:
            logger.exception("Checkout outcome could not be verified: %s", exc)
            fallback = {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False}
            if attempt_id is not None:
                try:
                    await engine.attempt_store.finish(attempt_id, fallback)
                except Exception as finish_exc:
                    logger.warning("Could not record attempt failure: %s", finish_exc)
            return fallback
    elif name == "track_order":
        return await engine.tools.track_order(args.get("order_id", ""))
    elif name == "check_replenishment":
        if getattr(engine, "replenishment_store", None) is None:
            return {"success": False, "message": "Household replenishment is not configured."}
        try:
            rep_store = engine.replenishment_store
            state = await rep_store._load(customer_id)
            if state is None:
                return {
                    "success": False,
                    "opted_in": False,
                    "message": "Household reminders are currently off. You can opt in anytime by asking to turn on grocery reminders.",
                }
            await rep_store._sync_orders(customer_id, engine.commerce)
            state = await rep_store._load(customer_id) or state
            due = rep_store._due_items(state)
            return {
                "success": True,
                "opted_in": True,
                "due_items": due,
                "message": (
                    f"Based on your past purchase intervals, you may be running low on: {', '.join(due[:5])}."
                    if due
                    else "All recurring essentials look well-stocked based on past delivery intervals."
                ),
            }
        except Exception as exc:
            logger.warning("check_replenishment failed for customer=%s: %s", customer_id, exc)
            return {"success": False, "error": str(exc), "message": "Could not check replenishment right now."}
    return {"error": f"Unknown tool: {name}"}
