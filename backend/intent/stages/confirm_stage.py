"""Stage 4: Confirmation Stage.

Handles receipt calculation with mathematical fee transparency, clean delivery address badges,
cryptographic token validation, and final order confirmation.
"""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import DeliveryAddress
from backend.intent.session import BasketSummary


from backend.intent.formatters import (
    format_clarification as _msg_clarification,
    format_confirmation_receipt as _msg_confirmation_basket,
    format_display_address as _display_address,
    format_failed as _msg_failed,
    format_ordered as _msg_ordered,
    format_payment_pending as _msg_payment_pending,
)

__all__ = [
    "_msg_confirmation_basket",
    "_display_address",
    "_msg_clarification",
    "_msg_failed",
    "_msg_ordered",
    "_msg_payment_pending",
]

