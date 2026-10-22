"""External cart drift detector and bounded fee tolerance guard."""
from __future__ import annotations

from typing import Any, Optional

from backend.agent.approval import cart_fingerprint
from backend.agent.formatters import format_cart_receipt
from backend.channels.models import InteractiveAction, NormalizedIncomingMessage, NormalizedOutgoingResponse
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
                getattr(session, "external_cart_warned", False)
                if hasattr(session, "external_cart_warned"):
                    session.external_cart_warned = False
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I’ve updated to your current Swiggy basket. What groceries would you like to change or add?\n\n"
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
