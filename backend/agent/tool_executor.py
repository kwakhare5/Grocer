"""Engine tool execution dispatcher with checkout gating, address syncing, and error mapping."""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional, TypeVar

from backend.agent.approval import cart_fingerprint
from backend.agent.session_manager import record_pending_cart_clear
from backend.config import settings
from backend.integrations.commerce.exceptions import ProviderAuthError, ProviderRateLimitedError
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.tool_executor")

T = TypeVar("T")


async def execute_tool_calls(
    calls: list[dict[str, Any]], execute: Callable[[dict[str, Any]], Awaitable[T]]
) -> list[T]:
    """Execute tool calls sequentially in model order without race conditions."""
    results: list[T] = []
    for call in calls:
        try:
            results.append(await execute(call))
        except Exception as exc:
            tool_name = call.get("name", "unknown")
            logger.warning("Tool execution error for %s: %s", tool_name, exc)
            results.append({  # type: ignore[arg-type]
                "success": False,
                "error": "TOOL_EXECUTION_ERROR",
                "tool": tool_name,
                "message": f"Tool {tool_name} failed: {exc}",
            })
    return results


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
    session = engine.get_session(customer_id)
    if name == "get_saved_addresses":
        return await engine.tools.get_saved_addresses(customer_id)
    elif name == "select_delivery_address":
        session.pending_approval = None
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
        )
        if result.get("verified_fingerprint"):
            session.known_cart_fingerprint = result["verified_fingerprint"]
        return result
    elif name == "clear_cart":
        session = engine.get_session(customer_id)
        try:
            cart = await engine.commerce.get_cart()
        except Exception:
            cart = None
        address_id = (
            engine._customer_address.get(customer_id)
            or (session.address_id if session else None)
            or (cart.address_id if cart else None)
            or ""
        )
        if cart and not cart.address_id and address_id:
            cart.address_id = address_id
        if cart and cart.items and session:
            record_pending_cart_clear(session, cart, address_id)
        return {"success": False, "error": "CLEAR_CONFIRMATION_REQUIRED"}
    elif name == "checkout":
        sess = engine.get_session(customer_id)
        confirmed_by_user = bool(user_confirmed)
        approval = sess.pending_approval
        if sess.unresolved_items:
            if confirmed_by_user and approval and approval.expires_at > time.time():
                sess.unresolved_items.clear()
            else:
                return {
                    "success": False,
                    "error": "ITEMS_UNRESOLVED",
                    "retryable": False,
                    "message": "Please resolve each missing or reduced requested item before checkout.",
                }
        if sess.external_cart_pending:
            return {"success": False, "error": "EXTERNAL_CART_UNREVIEWED", "retryable": False}
        if not confirmed_by_user or not approval or approval.expires_at <= time.time():
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
            if not result.get("success"):
                sess.pending_approval = approval
            else:
                sess.pending_approval = None
            return result
        except Exception as exc:
            logger.exception("Checkout outcome could not be verified: %s", exc)
            fallback = {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": True}
            sess.pending_approval = approval
            if attempt_id is not None:
                try:
                    await engine.attempt_store.finish(attempt_id, fallback)
                except Exception as finish_exc:
                    logger.warning("Could not record attempt failure: %s", finish_exc)
            return fallback
    elif name == "track_order":
        return await engine.tools.track_order(args.get("order_id", ""))
    elif name == "set_budget":
        amount = args.get("amount_inr")
        if not isinstance(amount, (int, float)) or amount <= 0:
            return {"success": False, "error": "Invalid budget amount"}
        session.budget_inr = float(amount)
        return {"success": True, "budget_inr": amount, "message": f"Budget set to ₹{amount}"}
    return {"error": f"Unknown tool: {name}"}
