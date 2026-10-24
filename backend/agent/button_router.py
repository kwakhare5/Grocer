"""Deterministic WhatsApp interactive button and action router.

Executes button callbacks (confirm order, clear cart, check payment, change address)
in <50ms without calling any LLM.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.formatters import format_cart_receipt
from backend.agent.session import CustomerSession
from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.exceptions import (
    StoreClosedError,
    DarkStoreOfflineError,
    AddressNotServiceableError,
)

logger = logging.getLogger("grocer.agent.button_router")


async def handle_button_action(
    payload: str,
    session: CustomerSession,
    commerce: CommercePort,
    customer_id: str,
    recipient_id: str,
    channel: ChannelType = ChannelType.WHATSAPP,
    attempt_store: Optional[Any] = None,
) -> Optional[NormalizedOutgoingResponse]:
    """Route interactive button payloads deterministically.
    
    Returns NormalizedOutgoingResponse if the payload is a known button action,
    or None if it should be handled as normal conversational text.
    """
    if not payload:
        return None

    clean = payload.strip()

    # 1. 1-Tap Checkout Confirmation: "confirm_order:<token>"
    if clean.startswith("confirm_order:") or clean == "confirm_order":
        token = clean.removeprefix("confirm_order:").strip() if ":" in clean else ""
        logger.info("Button router: processing checkout confirmation token='%s'", token)

        approval = getattr(session, "pending_approval", None)
        try:
            current_cart = await commerce.get_cart()
        except (StoreClosedError, DarkStoreOfflineError) as exc:
            logger.warning("Store closed or offline on checkout confirmation: %s", exc)
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="The local Swiggy Instamart store is currently closed or offline. Please check back shortly! 🏪",
                conversation_state="ACTIVE",
            )
        except AddressNotServiceableError as exc:
            logger.warning("Address not serviceable on checkout confirmation: %s", exc)
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="Your delivery address is currently not serviceable by Swiggy. Please tap below to choose another address.",
                conversation_state="ACTIVE",
            )
        except Exception as exc:
            logger.warning("Error fetching cart on checkout confirmation: %s", exc)
            current_cart = None

        if not current_cart or not current_cart.items:
            session.pending_approval = None
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="Your basket is empty. Please add items before checking out.",
                conversation_state="ACTIVE",
            )

        checkout_address = session.address_id or current_cart.address_id or ""
        observed_fp = cart_fingerprint(current_cart, checkout_address)

        # If no approval, expired approval, or stale token: refresh summary with a new token
        current_time = time.time()
        is_approval_valid = (
            approval is not None
            and getattr(approval, "expires_at", 0) > current_time
            and getattr(approval, "fingerprint", None) == observed_fp
            and getattr(session, "known_cart_fingerprint", None) == observed_fp
            and (not token or getattr(approval, "token", "") == token)
        )

        if not is_approval_valid:
            logger.info("Button router: approval invalid or expired, issuing fresh confirmation")
            new_token = uuid.uuid4().hex[:8]
            session.pending_approval = PendingApproval(
                fingerprint=observed_fp or "",
                expires_at=current_time + 300,
                token=new_token,
            )
            session.known_cart_fingerprint = observed_fp
            receipt = format_cart_receipt(current_cart, session.address_label or "Home")
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="Your previous confirmation expired. Here is your current basket:\n\n" + receipt,
                conversation_state="NEEDS_CONFIRMATION",
                interactive_actions=[
                    InteractiveAction(action_type="button", id=f"confirm_order:{new_token}", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
            )

        # Execute gated checkout
        result = await execute_gated_checkout(
            commerce=commerce,
            cart_id=current_cart.cart_id or "",
            address_id=checkout_address,
            payment_method=getattr(session, "selected_payment_method", "UPI") or "UPI",
            payment_option_kind=getattr(session, "selected_payment_kind", None),
            payment_option_id=getattr(session, "selected_payment_id", None),
            is_user_confirmed=True,
            budget_inr=getattr(session, "budget_inr", None),
            expected_cart_fingerprint=approval.fingerprint,
            customer_id=customer_id,
            attempt_store=attempt_store,
        )
        session.pending_approval = None

        if result.get("success"):
            order_id = result.get("order_id")
            grand_total = result.get("grand_total")
            pay_url = result.get("upi_intent_url") or result.get("bridge_url")
            actions = []
            if pay_url:
                actions.append(
                    InteractiveAction(
                        action_type="url",
                        id=f"pay_order:{order_id or 'order'}",
                        title="Pay with UPI (1-Tap)",
                        url=pay_url,
                    )
                )
            actions.append(
                InteractiveAction(
                    action_type="button",
                    id=f"check_payment:{order_id or 'order'}",
                    title="Check Payment",
                )
            )
            status = result.get("status")
            msg_text = result.get("message")
            if not msg_text:
                if status == "PAYMENT_PENDING":
                    msg_text = f"Order {order_id} for ₹{grand_total} is ready for payment!\n\n👉 *Tap here to pay:* {pay_url}\n\nTap *Check Payment* once paid, or *Change Items*."
                else:
                    msg_text = f"Order placed successfully! Order ID: {order_id}"
            elif pay_url and pay_url not in msg_text:
                msg_text = f"{msg_text}\n\n👉 *Tap here to pay:* {pay_url}"
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text=msg_text,
                conversation_state="AWAITING_PAYMENT" if status == "PAYMENT_PENDING" else "ORDER_PLACED",
                order_id=order_id,
                order_total=grand_total,
                interactive_actions=actions,
            )
        else:
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text=result.get("message") or "Checkout could not be completed. Please try again.",
                conversation_state="RECOVERING" if result.get("error") == "ORDER_STATE_UNKNOWN" else "ACTIVE",
            )

    # 2. Check Payment Status: "check_payment:<order_id>"
    if clean.startswith("check_payment:") or clean == "check_payment":
        order_id = clean.removeprefix("check_payment:").strip() if ":" in clean else getattr(session, "active_order_id", None)
        logger.info("Button router: checking payment status for order='%s'", order_id)

        if not order_id:
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="No active order found to check payment for. Let me know if you want to start a new order!",
                conversation_state="IDLE",
            )

        try:
            # Check payment status directly first
            try:
                paas_id = getattr(session, "paas_id", None) or order_id
                pay_status = await commerce.check_payment_status(paas_id=paas_id, order_id=order_id)
                norm_status = getattr(pay_status, "normalized_status", "")
                if getattr(pay_status, "confirmed", False) or norm_status == "PAYMENT_CONFIRMED":
                    session.conversation_state = "ORDER_PLACED"
                    session.pending_approval = None
                    return NormalizedOutgoingResponse(
                        recipient_id=recipient_id,
                        channel=channel,
                        text=(
                            f"🎉 *Payment Received!*\n\n"
                            f"Your Swiggy Instamart Order #{order_id} is confirmed and packing at your local store. 🛵\n\n"
                            "You can track live delivery updates in your Swiggy app."
                        ),
                        conversation_state="ORDER_PLACED",
                        order_id=order_id,
                    )
            except Exception as pay_err:
                logger.info("Direct check_payment_status call skipped/failed: %s", pay_err)

            order_status = await commerce.get_delivery_status(order_id)
            raw_status = (
                getattr(order_status, "status_text", None)
                or getattr(order_status, "status", None)
                or ("Delivered" if getattr(order_status, "delivered", False) else "In Progress")
            )
            status_str = str(raw_status).upper()
            status_text = (
                f"*Order Status*: {status_str}\n"
                f"*Order ID*: {order_id}\n"
            )
            if status_str.casefold() in ("delivered", "completed"):
                status_text += "\nYour order has been delivered! Enjoy your groceries! 🛒"
            elif status_str.casefold() in ("placed", "confirmed", "in_transit", "packing", "rider_assigned"):
                status_text += "\nYour order is confirmed and on the way! 🛵"
            else:
                status_text += "\nPayment is still pending. Please complete the UPI payment on your phone."

            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text=status_text,
                conversation_state="AWAITING_PAYMENT" if "pending" in status_text.casefold() else "COMPLETED",
                order_id=order_id,
            )
        except Exception as exc:
            logger.error("Error checking order status: %s", exc)
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="Could not fetch live order status right now. Please try again in a few moments.",
                conversation_state="IDLE",
            )

    # 3. Clear Cart: 2-step confirmation
    if clean == "clear_cart" or clean == "start_fresh":
        logger.info("Button router: clear_cart requested, returning confirmation prompt")
        try:
            cart = await commerce.get_cart()
        except Exception:
            cart = None

        if not cart or not cart.items:
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="Your basket is already empty! What would you like to add? 🛒",
                conversation_state="IDLE",
            )

        token = uuid.uuid4().hex[:8]
        fp = cart_fingerprint(cart, session.address_id or cart.address_id or "") or ""
        session.pending_cart_clear = PendingApproval(fingerprint=fp, expires_at=time.time() + 300, token=token)

        return NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=channel,
            text="Are you sure you want to clear your entire basket? 🛒",
            conversation_state="AWAITING_CART_CLEAR_CONFIRMATION",
            interactive_actions=[
                InteractiveAction(action_type="button", id=f"clear_cart_confirm:{token}", title="Yes, Clear Basket"),
                InteractiveAction(action_type="button", id="clear_cart_cancel", title="Keep Basket"),
            ],
        )

    if clean.startswith("clear_cart_confirm"):
        incoming_token = clean.removeprefix("clear_cart_confirm:").strip() if ":" in clean else ""
        clear_approval = getattr(session, "pending_cart_clear", None)
        current_time = time.time()
        is_token_valid = (
            bool(incoming_token)
            and clear_approval is not None
            and getattr(clear_approval, "token", None) == incoming_token
            and getattr(clear_approval, "expires_at", 0) > current_time
        )
        if not is_token_valid:
            logger.warning("Invalid or expired clear_cart_confirm token: '%s'", incoming_token)
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="The confirmation to clear your cart has expired or changed. Your cart was not cleared.",
                conversation_state="ACTIVE",
            )

        # Check cart fingerprint matches the cart when clear was requested
        try:
            current_cart = await commerce.get_cart()
            observed_fingerprint = cart_fingerprint(current_cart, session.address_id or current_cart.address_id or "")
            if clear_approval.fingerprint != observed_fingerprint:
                logger.warning("Cart fingerprint mismatch on clear_cart_confirm")
                return NormalizedOutgoingResponse(
                    recipient_id=recipient_id,
                    channel=channel,
                    text="Your cart changed before you confirmed clearing it. The confirmation has expired to protect your items.",
                    conversation_state="ACTIVE",
                )
        except Exception as exc:
            logger.warning("Could not check cart fingerprint: %s", exc)

        logger.info("Button router: clear_cart_confirm executed with valid token and fingerprint")
        try:
            await commerce.clear_cart()
        except Exception as exc:
            logger.warning("Could not clear cart upstream: %s", exc)
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text="I couldn't verify what happened to your cart with Swiggy. Please review your current basket before making more changes.",
                conversation_state="RECOVERING",
            )

        session.pending_cart_clear = None
        session.pending_approval = None
        return NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=channel,
            text="Your cart has been cleared. What would you like to order today?",
            conversation_state="IDLE",
        )

    if clean == "clear_cart_cancel":
        session.pending_cart_clear = None
        return NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=channel,
            text="Kept your cart intact! Let me know what else you'd like to add or if you're ready to checkout.",
            conversation_state="ACTIVE",
            interactive_actions=[
                InteractiveAction(action_type="button", id="confirm_order", title="Review & Confirm"),
            ],
        )

    # 4. Modify Cart
    if clean == "modify_cart":
        session.pending_approval = None
        return NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=channel,
            text="Sure! Just tell me what items you want to add or remove (e.g., 'remove bread' or 'add 1L milk').",
            conversation_state="ACTIVE",
        )

    # 5. Change Delivery Address: "select_address:<address_id>"
    if clean.startswith("select_address:"):
        addr_id = clean.removeprefix("select_address:").strip()
        addrs = getattr(session, "saved_addresses", []) or []
        matching = [a for a in addrs if str(a.get("id")) == addr_id]
        if matching:
            session.address_id = addr_id
            session.order_address_confirmed = True
            try:
                await commerce.update_cart(address_id=addr_id)
            except Exception as sync_exc:
                logger.warning("Failed to sync commerce cart to selected address %s: %s", addr_id, sync_exc)
            addr_name = matching[0].get("label") or matching[0].get("street") or addr_id
            return NormalizedOutgoingResponse(
                recipient_id=recipient_id,
                channel=channel,
                text=f"Updated your delivery address to *{addr_name}*. Let's continue with your order!",
                conversation_state="ACTIVE",
            )

    return None
