"""Gated server-side checkout execution for Swiggy Instamart orders."""
from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Optional

from backend.agent.approval import cart_fingerprint
from backend.agent.formatters import _format_inr
from backend.agent.product_policy import is_restricted_medical_product
from backend.config import settings
from backend.integrations.commerce.exceptions import (
    AddressNotServiceableError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    OrderStateUnknownError,
    ProviderAuthError,
)
from backend.integrations.commerce.models import CommerceOrderResult
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.checkout")


async def execute_gated_checkout(
    commerce: CommercePort,
    cart_id: str = "",
    address_id: str = "",
    payment_method: str = "UPI",
    payment_option_kind: Optional[str] = None,
    payment_option_id: Optional[str] = None,
    is_user_confirmed: bool = False,
    budget_inr: Optional[float] = None,
    expected_cart_fingerprint: Optional[str] = None,
    conversation_state: Optional[str] = "AWAITING_CONFIRMATION",
    attempt_store: Optional[Any] = None,
    customer_id: Optional[str] = None,
) -> dict[str, Any]:
    """Place the final order on Swiggy Instamart. STRICTLY server-side gated."""
    # Lock 1: Must be in AWAITING_CONFIRMATION state
    if conversation_state is not None and conversation_state != "AWAITING_CONFIRMATION":
        return {
            "success": False,
            "error": "STATE_NOT_CONFIRMING",
            "retryable": False,
            "message": "Order placement blocked: Session must be in AWAITING_CONFIRMATION before checkout can execute.",
        }

    # Lock 2: Explicit dual confirmation check
    if not is_user_confirmed:
        return {
            "success": False,
            "error": "CONFIRMATION_REQUIRED",
            "retryable": False,
            "message": (
                "Order placement rejected: User has not provided explicit final confirmation. "
                "You must ask the user to confirm the order summary and grand total first."
            ),
        }

    try:
        cart = await commerce.get_cart(cart_id)
    except Exception as exc:
        logger.warning("Checkout cart verification failed: %s", type(exc).__name__)
        return {
            "success": False,
            "error": "CART_UNAVAILABLE",
            "retryable": False,
            "message": "I couldn't verify your basket. Please review it again before ordering.",
        }

    if not cart:
        return {
            "success": False,
            "error": "CART_UNAVAILABLE",
            "retryable": False,
            "message": "I couldn't verify your basket. Please review it again before ordering.",
        }
    if getattr(cart, "is_serviceable", True) is False:
        return {
            "success": False,
            "error": "ADDRESS_NOT_SERVICEABLE",
            "retryable": False,
            "message": "Swiggy Instamart is currently unable to deliver to this address (store may be closed or unserviceable).",
        }
    if not math.isfinite(cart.grand_total) or cart.grand_total <= 0:
        return {
            "success": False,
            "error": "TOTAL_UNKNOWN",
            "retryable": False,
            "message": "I couldn't verify the full payable total. No order was attempted.",
        }
    if cart.currency != "INR":
        return {
            "success": False,
            "error": "CURRENCY_MISMATCH",
            "retryable": False,
            "message": "The basket currency is not INR. No order was attempted.",
        }
    if not cart.billing_complete:
        return {
            "success": False,
            "error": "BILL_INCOMPLETE",
            "retryable": False,
            "message": "I couldn't verify every charge in the payable total. No order was attempted.",
        }
    if cart_id and cart.cart_id and cart.cart_id != cart_id:
        return {
            "success": False,
            "error": "CART_CHANGED",
            "retryable": False,
            "message": "Your basket changed. Please review the current basket again.",
        }
    if address_id and cart.address_id and cart.address_id != address_id:
        return {
            "success": False,
            "error": "ADDRESS_CHANGED",
            "retryable": False,
            "message": "The delivery address changed. Please review the current basket again.",
        }

    # Lock 4: Live cart fingerprint match (zero price drift or OOS silent changes)
    current_fingerprint = cart_fingerprint(cart, address_id)
    if expected_cart_fingerprint and current_fingerprint != expected_cart_fingerprint:
        return {
            "success": False,
            "error": "CART_CHANGED",
            "retryable": False,
            "message": "Your basket or total changed. Please review it again.",
        }

    # Lock 3: Grand total <= budget_limit check
    if budget_inr is not None:
        if not math.isfinite(budget_inr) or budget_inr <= 0:
            return {
                "success": False,
                "error": "INVALID_BUDGET",
                "retryable": False,
                "message": "I couldn't verify your spending limit. Please restate it.",
            }
        if Decimal(str(cart.grand_total)) > Decimal(str(budget_inr)):
            overage = float(Decimal(str(cart.grand_total)) - Decimal(str(budget_inr)))
            return {
                "success": False,
                "error": "BUDGET_EXCEEDED",
                "retryable": False,
                "grand_total": cart.grand_total,
                "budget_inr": budget_inr,
                "message": (
                    f"Order placement blocked: Current grand total ₹{cart.grand_total:.0f} "
                    f"exceeds your budget of ₹{budget_inr:.0f} by ₹{overage:.0f}. "
                    "Please ask the user if they would like to remove an item or increase their budget."
                ),
            }

    if not cart.items:
        return {
            "success": False,
            "error": "CART_EMPTY",
            "retryable": False,
            "message": "Your basket is empty. No order was attempted.",
        }

    # Lock 5: Zero restricted medical products in basket
    medical_items = [
        item.name
        for item in cart.items
        if is_restricted_medical_product(item.name, item.category)
    ]
    if medical_items:
        return {
            "success": False,
            "error": "MEDICAL_PRODUCT_RESTRICTED",
            "retryable": False,
            "items": medical_items,
            "message": "Medical products cannot be ordered through this WhatsApp shopping flow.",
        }

    # Hold tracking: check for unresolved checkout attempt
    attempt_id: Optional[str] = None
    if attempt_store is not None and customer_id:
        try:
            attempt_id = await attempt_store.start(
                customer_id=customer_id,
                cart_id=cart.cart_id or cart_id,
                address_id=address_id,
                fingerprint=expected_cart_fingerprint or current_fingerprint,
                total=cart.grand_total,
            )
        except Exception as exc:
            logger.exception("Could not reserve durable checkout attempt: %s", exc)
            return {
                "success": False,
                "error": "DURABLE_ATTEMPT_REQUIRED",
                "retryable": False,
                "message": "Live checkout is unavailable until durable attempt tracking is ready.",
            }
        if attempt_id is None:
            return {
                "success": False,
                "error": "ATTEMPT_UNRESOLVED",
                "retryable": False,
                "message": "An earlier checkout or payment is unresolved. Further checkout is on hold.",
            }

    if settings.CHECKOUT_MODE == "live":
        try:
            options = await commerce.get_payment_options(cart_id, address_id)
        except ProviderAuthError:
            err_res = {
                "success": False,
                "error": "AUTH_EXPIRED",
                "retryable": False,
                "message": "Please reconnect Swiggy before choosing a payment option.",
            }
            if attempt_store is not None and attempt_id:
                await attempt_store.finish(attempt_id, err_res)
            return err_res
        except Exception:
            logger.warning("Payment options could not be verified before checkout.")
            err_res = {
                "success": False,
                "error": "PAYMENT_OPTIONS_UNAVAILABLE",
                "retryable": True,
                "message": "I couldn't verify the current payment options. No order was attempted.",
            }
            if attempt_store is not None and attempt_id:
                await attempt_store.finish(attempt_id, err_res)
            return err_res

        available = [
            option
            for option in options
            if option.id
            and option.is_available
            and (
                (option.method == "UPI" and option.kind == "intent")
                or option.method in ("Cash", "COD", "SwiggyPay")
            )
        ]
        if not payment_option_id:
            err_res = {
                "success": False,
                "error": "PAYMENT_CHOICE_REQUIRED",
                "retryable": False,
                "payment_options": [option.model_dump() for option in available[:10]],
                "message": "Please choose an available payment option before placing the order.",
            }
            if attempt_store is not None and attempt_id:
                await attempt_store.finish(attempt_id, err_res)
            return err_res

        selected = next(
            (
                option
                for option in options
                if option.id == payment_option_id
                and option.kind == payment_option_kind
                and option.is_available
            ),
            None,
        )
        if selected is None or selected.method.casefold() != payment_method.casefold():
            err_res = {
                "success": False,
                "error": "PAYMENT_OPTION_UNAVAILABLE",
                "retryable": False,
                "message": "That payment option is no longer available. Please choose from the current options.",
            }
            if attempt_store is not None and attempt_id:
                await attempt_store.finish(attempt_id, err_res)
            return err_res

    try:
        result: CommerceOrderResult = await commerce.checkout(
            cart_id=cart_id,
            address_id=address_id,
            payment_method=payment_method,
            payment_option_kind=payment_option_kind,
            payment_option_id=payment_option_id,
            explicit_confirmation=True,
        )
        polling_ms = result.polling_interval_ms or 15000
        max_poll_ms = result.max_time_to_poll_ms or 600000

        # Construct 1-tap mobile UPI deep link (upi://pay) if not provided by backend payload
        upi_intent = result.upi_intent_url
        if not upi_intent and result.order_id and result.grand_total:
            upi_intent = (
                f"upi://pay?pa=swiggy@icici&pn=SwiggyInstamart"
                f"&am={result.grand_total:.2f}&tr={result.order_id}&cu=INR"
            )

        if result.status == "PAYMENT_PENDING" and not (
            result.order_id
            and result.paas_id
            and (result.bridge_url or result.qr_code_url or upi_intent)
        ):
            err_res = {
                "success": False,
                "error": "ORDER_STATE_UNKNOWN",
                "retryable": False,
                "order_id": result.order_id,
                "paas_id": result.paas_id,
                "message": "Swiggy started a payment, but I couldn't verify the details needed to track it. Check Swiggy before trying again.",
            }
            if attempt_store is not None and attempt_id:
                await attempt_store.finish(attempt_id, err_res)
            return err_res

        out = {
            "success": result.status not in ("ORDER_STATE_UNKNOWN", "FAILED"),
            "order_id": result.order_id,
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "grand_total": result.grand_total,
            "formatted_grand_total": _format_inr(result.grand_total) if result.grand_total else None,
            "tracking_url": result.tracking_url,
            "delivery_address": result.delivery_address.street if result.delivery_address else "",
            "paas_id": result.paas_id,
            "polling_interval_ms": polling_ms,
            "max_time_to_poll_ms": max_poll_ms,
            "bridge_url": result.bridge_url,
            "upi_intent_url": upi_intent,
            "qr_code_url": result.qr_code_url,
            "is_qr_flow": result.is_qr_flow,
            "is_simulated": result.is_simulated,
            "message": result.message,
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, out)
        return out
    except ProviderAuthError as exc:
        err_res = {"success": False, "error": "AUTH_EXPIRED", "detail": str(exc)}
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
    except ItemOutOfStockError as exc:
        err_res = {
            "success": False,
            "error": "ITEM_OUT_OF_STOCK",
            "retryable": True,
            "spin_id": getattr(exc, "spin_id", None),
            "message": "One of the items in your basket just went out of stock on Swiggy Instamart.",
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
    except AddressNotServiceableError:
        err_res = {
            "success": False,
            "error": "ADDRESS_NOT_SERVICEABLE",
            "retryable": False,
            "message": "Swiggy Instamart is currently unable to deliver to this address (store may be closed or unserviceable).",
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
    except MinOrderNotMetError as exc:
        err_res = {
            "success": False,
            "error": "MIN_ORDER_NOT_MET",
            "retryable": False,
            "message": str(exc),
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
    except OrderStateUnknownError:
        err_res = {
            "success": False,
            "error": "ORDER_STATE_UNKNOWN",
            "retryable": False,
            "message": "I couldn't verify whether checkout completed. Please don't try again yet.",
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
    except Exception as exc:
        logger.warning("checkout outcome unverified after %s", type(exc).__name__)
        err_res = {
            "success": False,
            "error": "ORDER_STATE_UNKNOWN",
            "retryable": False,
            "message": "I couldn't verify whether checkout completed. Please don't try again yet.",
        }
        if attempt_store is not None and attempt_id:
            await attempt_store.finish(attempt_id, err_res)
        return err_res
