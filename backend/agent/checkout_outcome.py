"""Checkout outcome evaluation, status routing, and fail-closed response guards."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.formatters import format_cart_receipt
from backend.agent.guards import _claims_order_success, _explains_failure
from backend.channels.models import InteractiveAction
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.checkout_outcome")


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
    if pending_request_needs_retry:
        conv_state = "NEEDS_DECISION"

    if checkout_executed and checkout_result:
        if not checkout_result.get("success"):
            if checkout_result.get("error") == "CONFIRMATION_REQUIRED":
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
                actions = [
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
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
                if settings.CHECKOUT_MODE == "live":
                    final_text = (
                        f"Checkout could not be completed or verified: {error_msg}. "
                        "Please check the Swiggy order status before trying again."
                    )
                else:
                    disclaimer = "Your order has NOT been placed and your account has not been charged."
                    if _claims_order_success(final_text):
                        logger.warning("Fail-closed guard triggered: LLM falsely claimed order success on failed checkout (%s). Overriding response.", error_msg)
                        final_text = f"I could not complete your order: {error_msg}. {disclaimer} Please check your basket and try again."
                    elif not _explains_failure(final_text, checkout_result.get("error"), checkout_result.get("message")):
                        logger.warning("Fail-closed guard triggered: LLM failed to explain failure (%s). Overriding response.", error_msg)
                        final_text = f"I could not complete your order: {error_msg}. {disclaimer} Please check your basket and try again."
                    elif disclaimer not in final_text:
                        final_text = f"{final_text.rstrip()}\n\n{disclaimer}"
                conv_state = "FAILED"
        else:
            out_order_id = checkout_result.get("order_id")
            out_order_total = checkout_result.get("grand_total")
            out_bridge_url = checkout_result.get("bridge_url")
            upi_url = checkout_result.get("upi_intent_url")
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
                engine._order_address_confirmed.pop(customer_id, None)
                engine._customer_address.pop(customer_id, None)
                engine._customer_address_label.pop(customer_id, None)
                pay_link = out_bridge_url or upi_url
                link_present = False
                if out_bridge_url and out_bridge_url in final_text:
                    link_present = True
                if upi_url and upi_url in final_text:
                    link_present = True

                if _claims_order_success(final_text) or not final_text.strip():
                    logger.warning("PAYMENT_PENDING guard triggered: LLM claimed premature order placement or empty response. Overriding response.")
                    if pay_link:
                        final_text = f"Your order is ready! Please complete payment to place your order: {pay_link}"
                    else:
                        final_text = "Your order is ready! Please complete payment in your Swiggy app to place your order."
                else:
                    if pay_link and not link_present:
                        final_text += f"\n\n👉 Complete payment to place your order: {pay_link}"
                    elif not pay_link and not link_present:
                        final_text += "\n\nPlease complete payment in your Swiggy app to finalize your order."

            elif status == "ORDER_PLACED":
                conv_state = "ORDER_PLACED"
                engine._order_address_confirmed.pop(customer_id, None)
                engine._customer_address.pop(customer_id, None)
                engine._customer_address_label.pop(customer_id, None)
            else:
                conv_state = "READY"

    return conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url
