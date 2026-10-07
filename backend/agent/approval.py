"""Fingerprint the exact provider basket a customer is asked to approve."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal

from backend.integrations.commerce.models import CommerceCart


@dataclass(frozen=True)
class PendingApproval:
    fingerprint: str
    expires_at: float


def cart_fingerprint(cart: CommerceCart, address_id: str) -> str | None:
    if (not cart.items or not cart.billing_complete or cart.currency != "INR"
            or not address_id or cart.address_id != address_id
            or not math.isfinite(cart.grand_total) or cart.grand_total <= 0):
        return None
    payload = {
        "cart_id": cart.cart_id,
        "address_id": address_id,
        "provider_address_id": cart.address_id,
        "payable_inr": str(Decimal(str(cart.grand_total))),
        "currency": cart.currency,
        "bill_lines": cart.bill_lines,
        "items": sorted(
            (item.spin_id, item.sku_id, item.quantity, str(Decimal(str(item.total_price))))
            for item in cart.items
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
