"""Approval, confirmation checking, cart drift detection, and fingerprinting."""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

from backend.agent.config import BRAIN_FALLBACK_MODEL, SMALL_CHECK_MODEL
from backend.agent.formatters import format_cart_receipt
from backend.channels.models import InteractiveAction, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.approval")


@dataclass(frozen=True)
class PendingApproval:
    fingerprint: str
    expires_at: float
    token: str = ""


def _normalize_money(val: Any) -> str:
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return "0.00"


def cart_fingerprint(cart: CommerceCart, address_id: str) -> str | None:
    """Deterministically fingerprint the exact provider basket a customer is asked to approve."""
    target_address = address_id or cart.address_id or ""
    if (
        not cart.items
        or not cart.billing_complete
        or (cart.currency or "").strip().upper() != "INR"
        or not target_address
        or (cart.address_id and cart.address_id != target_address)
        or not math.isfinite(cart.grand_total)
        or cart.grand_total <= 0
    ):
        return None
    payload = {
        "cart_id": cart.cart_id,
        "address_id": target_address,
        "provider_address_id": target_address,
        "payable_inr": _normalize_money(cart.grand_total),
        "currency": (cart.currency or "").strip().upper(),
        "bill_lines": sorted(
            [
                {
                    "name": str(line.get("name") or line.get("label", "")).strip().casefold(),
                    "amount": _normalize_money(line.get("amount") if line.get("amount") is not None else line.get("value", 0.0)),
                }
                for line in cart.bill_lines
            ],
            key=lambda x: (x["name"], x["amount"]),
        )
        if cart.bill_lines
        else [],
        "items": sorted(
            (item.spin_id, item.sku_id or "", item.quantity, _normalize_money(item.total_price))
            for item in cart.items
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


CONFIRMATION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "confirmation": {
            "type": "STRING",
            "enum": ["yes", "no", "unclear"],
            "description": "Whether the customer confirmed this exact order.",
        },
    },
    "required": ["confirmation"],
}


async def is_confirmed(
    client_or_text: Any = None,
    text_or_context: str = "",
    context: str = "",
    *,
    client: Any = None,
    interactive_id: Optional[str] = None,
) -> bool:
    """Judge if customer confirmed this exact order via small check model structured output.

    Returns True only when the customer tapped confirm or model answers 'yes'.
    """
    if interactive_id in ("confirm_order", "btn_confirm", "order_confirm", "checkout_confirm"):
        return True

    if isinstance(client_or_text, str):
        target_client = client
        message_text = client_or_text
        short_context = text_or_context or context
    else:
        target_client = client or client_or_text
        message_text = text_or_context
        short_context = context

    if not target_client or not getattr(target_client, "api_key", None) or not message_text.strip():
        return False

    sanitized_message = message_text.strip().replace("```", "").replace("\r", "")
    sanitized_context = short_context.strip().replace("```", "")

    prompt = (
        f"Customer message:\n\"{sanitized_message}\"\n\n"
        f"Order context:\n\"{sanitized_context}\"\n\n"
        "Did the customer explicitly confirm and approve placing this exact order? "
        "Answer with 'yes' if they explicitly approved (including in Hindi/Hinglish like 'haan bhej do', 'chalo order kar do', 'kar de'), "
        "'no' if they rejected or wanted changes, "
        "or 'unclear' if it is ambiguous, a question, or not an explicit confirmation."
    )

    models_to_try = [SMALL_CHECK_MODEL, BRAIN_FALLBACK_MODEL]
    for model_name in models_to_try:
        try:
            res = await target_client.generate_structured(
                model=model_name,
                prompt=prompt,
                response_schema=CONFIRMATION_SCHEMA,
            )
            if isinstance(res, dict):
                val = str(res.get("confirmation", "")).strip().casefold()
                return val == "yes"
            return False
        except Exception as exc:
            logger.warning("Confirmation check failed with model %s: %r", model_name, exc)
            continue

    return False


check_confirmation = is_confirmed


async def check_cart_drift(
    session: Any,
    current_cart: Optional[CommerceCart],
    norm_text: str,
    user_confirmed: bool,
    message: NormalizedIncomingMessage,
    confirmation_check: Any = None,
    client: Any = None,
) -> Optional[NormalizedOutgoingResponse]:
    """Detect external changes to Swiggy cart and enforce bounded price tolerance."""
    observed_fingerprint = (
        cart_fingerprint(current_cart, current_cart.address_id or session.address_id or "")
        if current_cart
        else None
    )
    if (
        (session.known_cart_fingerprint and observed_fingerprint != session.known_cart_fingerprint)
        or (session.pending_approval is not None and not session.known_cart_fingerprint)
    ):
        session.external_cart_pending = True
        session.pending_approval = None
        session.selected_payment_id = None

    if session.external_cart_pending:
        confirmed = user_confirmed or (message.interactive_id in ("keep_external", "use_changes"))
        if not confirmed and current_cart and message.text.strip():
            if norm_text in ("use changes", "keep changes", "keep items", "use external", "keep swiggy items"):
                confirmed = True
            elif confirmation_check is not None:
                ctx = "The Swiggy cart changed outside this chat. Did the customer confirm keeping the changes?"
                if hasattr(confirmation_check, "is_confirmed"):
                    confirmed = await confirmation_check.is_confirmed(client, message.text, context=ctx)
                elif callable(confirmation_check):
                    try:
                        confirmed = await confirmation_check(client, message.text, context=ctx)
                    except TypeError:
                        confirmed = await confirmation_check(message.text, ctx)
                elif isinstance(confirmation_check, bool):
                    confirmed = confirmation_check

        if confirmed and current_cart:
            observed_fingerprint = cart_fingerprint(
                current_cart, current_cart.address_id or session.address_id or ""
            )
            if observed_fingerprint:
                session.known_cart_fingerprint = observed_fingerprint
                session.external_cart_pending = False
                if hasattr(session, "external_cart_warned"):
                    session.external_cart_warned = False
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I've updated to your current Swiggy basket. What groceries would you like to change or add?\n\n"
                    + format_cart_receipt(
                        current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
                    ),
                    conversation_state="NEEDS_DECISION",
                )

        if message.interactive_id == "restore_grocer":
            session.external_cart_pending = False
            if hasattr(session, "external_cart_warned"):
                session.external_cart_warned = False
            return None

        # If user was already warned on previous turn and types a command, unblock them
        if getattr(session, "external_cart_warned", False) and message.text.strip():
            session.external_cart_pending = False
            session.external_cart_warned = False
            return None

        if hasattr(session, "external_cart_warned"):
            session.external_cart_warned = True

        receipt = (
            format_cart_receipt(
                current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
            )
            if current_cart
            else "I couldn't read the current Swiggy basket."
        )
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text="The Swiggy cart changed outside this chat. You can keep the Swiggy items, "
            "or tell me what to change in your basket.\n\n"
            + receipt,
            conversation_state="NEEDS_DECISION",
            interactive_actions=[
                InteractiveAction(id="keep_external", title="Keep Swiggy items"),
                InteractiveAction(id="restore_grocer", title="Clear & start over"),
            ],
        )

    return None
