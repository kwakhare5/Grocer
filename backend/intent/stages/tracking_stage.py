"""Stage 5: Tracking Stage.

Handles post-checkout tracking, delivery status inquiries, order details,
and customer support redirection for order cancellations.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.integrations.commerce.port import CommercePort


def format_delivery_status(status: Any) -> str:
    """Format delivery tracking status into a user message."""
    carrier = getattr(status, "carrier", None) or "Instamart partner"
    eta = getattr(status, "eta_minutes", None)
    eta_text = f" ETA: ~{eta} mins." if eta else ""
    return f"Delivery status: {status.status.value.replace('_', ' ').title()}. Carrier: {carrier}.{eta_text}"


def format_order_cancellation_redirect() -> str:
    return (
        "Order cancellation is not supported directly in chat. "
        "Please contact Swiggy customer support in the Swiggy app or call 080-67466729."
    )
