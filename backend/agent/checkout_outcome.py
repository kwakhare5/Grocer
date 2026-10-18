"""Checkout outcome evaluation, status routing, and fail-closed response guards."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.formatters import _format_inr, format_cart_receipt
from backend.channels.models import InteractiveAction
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.checkout_outcome")


def order_message(result: dict[str, Any]) -> str:
    """Write customer message deterministically from checkout result."""
    order_id = result.get("order_id") or ""
    total = result.get("formatted_grand_total")
    if not total and result.get("grand_total") is not None:
        total = _format_inr(result["grand_total"])
    total_str = f" for {total}" if total else ""
    order_str = f" {order_id}" if order_id else ""
    status = result.get("status")

    if status == "ORDER_PLACED":
        tracking_url = result.get("tracking_url")
        track_str = f" Track your order here: {tracking_url}" if tracking_url else ""
        return f"Your order{order_str}{total_str} has been placed!{track_str}".strip()
    elif status == "PAYMENT_PENDING":
        pay_link = result.get("bridge_url") or result.get("upi_intent_url")
        if pay_link:
            return f"Your order{order_str}{total_str} is ready! Please complete payment to place your order: {pay_link}".strip()
        return f"Your order{order_str}{total_str} is ready! Please complete payment in your Swiggy app to place your order.".strip()
    return ""


def process_checkout_outcome(
    engine: Any,
    customer_id: str,
    *,
    checkout_executed: bool,
    checkout_result: Optional[dict[str, Any]],
    last_cart_receipt: Optional[str],
    current_cart: Optional[CommerceCart],
    addr_lbl: Optional[str],
    final_text: str,
    actions: list[InteractiveAction],
    pending_request_needs_retry: bool,
) -> tuple[str, str, list[InteractiveAction], Optional[str], Optional[float], Optional[str]]:
    """Evaluate checkout results and return (conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url)."""
    out_order_id: str | None = None
    out_order_total: float | None = None
    out_bridge_url: str | None = None
    conv_state = "READY"
    session = engine.get_session(customer_id) if hasattr(engine, "get_session") else None
    if pending_request_needs_retry:
        conv_state = "NEEDS_DECISION"

    if checkout_executed and checkout_result:
        if not checkout_result.get("success"):
            if checkout_result.get("error") == "CONFIRMATION_REQUIRED":
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
                token = ""
                if session and getattr(session, "pending_approval", None) and session.pending_approval.token:
                    token = session.pending_approval.token
                elif engine and current_cart and hasattr(engine, "_record_pending_approval"):
                    target_addr = (
                        (session.address_id if session else None)
                        or (current_cart.address_id if current_cart else None)
                        or addr_lbl
                        or ""
                    )
                    if engine._record_pending_approval(customer_id, current_cart, target_addr):
                        sess = engine.get_session(customer_id) if hasattr(engine, "get_session") else None
                        if sess and getattr(sess, "pending_approval", None):
                            token = sess.pending_approval.token or ""

                actions = []
                if token:
                    actions.append(InteractiveAction(action_type="button", id=f"confirm_order:{token}", title="Confirm Order"))
                actions.append(InteractiveAction(action_type="button", id="modify_cart", title="Change Items"))

                receipt_str = last_cart_receipt or (format_cart_receipt(current_cart, addr_lbl or "Home") if current_cart else "")
                final_text = (f"{receipt_str}\n\n👉 Reply *Confirm* to place order, or let me know if you'd like to change anything!").strip()
            elif (
                checkout_result.get("error") in ("ORDER_STATE_UNKNOWN", "ATTEMPT_UNRESOLVED")
                or checkout_result.get("status") == "ORDER_STATE_UNKNOWN"
            ):
                conv_state = "RECOVERING"
                final_text = (
                    "I couldn't verify whether checkout completed. "
                    "Please check the order status in Swiggy or contact support before trying again. "
                    "Further checkout is on hold until this is resolved."
                )
            elif checkout_result.get("error") == "PAYMENT_CHOICE_REQUIRED":
                available = checkout_result.get("payment_options") or []
                if available:
                    actions = [
                        InteractiveAction(
                            action_type="list_row",
                            id=f"payment_choice:{option['id']}",
                            title=str(option["label"])[:24],
                        )
                        for option in available[:10]
                    ]
                    final_text = "Please choose how you want to pay. I'll show the final basket again before placing an order."
                    conv_state = "NEEDS_PAYMENT"
                else:
                    final_text = "I couldn't verify an available payment option. Please try again later."
                    conv_state = "NEEDS_DECISION"
            else:
                error_msg = checkout_result.get("error") or checkout_result.get("message") or "Provider checkout error"
                base_text = (
                    f"Checkout could not be completed or verified: {error_msg}. "
                    "Please check the Swiggy order status before trying again."
                )
                extra = final_text.strip()
                final_text = f"{base_text}\n\n{extra}" if extra else base_text
                conv_state = "FAILED"
        else:
            out_order_id = checkout_result.get("order_id")
            out_order_total = checkout_result.get("grand_total")
            out_bridge_url = checkout_result.get("bridge_url")
            status = checkout_result.get("status")

            if status in ("REVIEW_COMPLETE", "REVIEW_SIMULATED") or checkout_result.get("is_simulated"):
                conv_state = "REVIEW_COMPLETE"
                out_order_id = None
                out_bridge_url = None
                final_text = "Review complete. No real order was placed and no payment was taken."
            elif status == "PARTIAL_ORDER":
                conv_state = "NEEDS_DECISION"
                final_text = (
                    f"Swiggy reported a partial order: {checkout_result.get('success_count', 0)} "
                    f"placed and {checkout_result.get('failure_count', 0)} failed. "
                    "Please check the order details before taking another action."
                )
            elif status == "PAYMENT_CONFIRMED":
                conv_state = "RECOVERING"
                final_text = (
                    "Swiggy confirmed payment, but I couldn't verify that every order was placed. "
                    "Please check the order details in Swiggy. Further checkout is on hold."
                )
            elif status == "PAYMENT_PENDING":
                conv_state = "AWAITING_PAYMENT"
                if session is not None:
                    session.reset_order_address()
                code_text = order_message(checkout_result)
                extra = final_text.strip()
                final_text = f"{code_text}\n\n{extra}" if extra else code_text
            elif status == "ORDER_PLACED":
                conv_state = "ORDER_PLACED"
                if session is not None:
                    session.reset_order_address()
                final_text = order_message(checkout_result)
            else:
                conv_state = "READY"

    return conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url
