"""External cart drift detector and bounded fee tolerance guard."""
from __future__ import annotations

from typing import Any, Optional

from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.formatters import format_cart_receipt
from backend.channels.models import NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.integrations.commerce.models import CommerceCart


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
    if session.known_cart_fingerprint:
        observed_fingerprint = (
            cart_fingerprint(current_cart, current_cart.address_id or session.address_id or "")
            if current_cart
            else None
        )
        if observed_fingerprint != session.known_cart_fingerprint:
            # Bounded price tolerance: minor fee fluctuations (<= ₹10) proceed smoothly
            is_minor_fluctuation = False
            if current_cart and session.pending_approval:
                old_total = getattr(session, "known_cart_total", None)
                if old_total is not None:
                    delta = abs(current_cart.grand_total - old_total)
                    within_budget = session.budget_inr is None or current_cart.grand_total <= session.budget_inr
                    if delta <= 10.0 and within_budget:
                        is_minor_fluctuation = True
                        session.known_cart_fingerprint = observed_fingerprint
                        session.known_cart_total = current_cart.grand_total
                        session.pending_approval = PendingApproval(
                            fingerprint=observed_fingerprint,
                            expires_at=session.pending_approval.expires_at,
                            token=session.pending_approval.token,
                        )

            if not is_minor_fluctuation:
                session.external_cart_pending = True
                session.pending_approval = None
                session.selected_payment_id = None

    if session.external_cart_pending:
        confirmed = user_confirmed
        if not confirmed and current_cart and message.text.strip():
            if confirmation_check is not None:
                ctx = "The Swiggy cart changed outside this chat. Did the customer confirm using the changes?"
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
                session.known_cart_total = current_cart.grand_total
                session.external_cart_pending = False
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I’ve included the Swiggy cart changes. Please tell me what to change next.\n\n"
                    + format_cart_receipt(
                        current_cart, session.address_label or "Saved Address", allow_checkout_prompt=False
                    ),
                    conversation_state="NEEDS_DECISION",
                )

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
            text="The Swiggy cart changed outside this chat. Reply *use changes* to include it, "
            "or tell me how you want to restore the basket.\n\n"
            + receipt,
            conversation_state="NEEDS_DECISION",
        )

    return None
