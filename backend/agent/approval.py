"""Grocer — Checkout Approval & Cart Fingerprinting Engine.

Enforces:
1. Canonical SHA-256 cart fingerprinting over items and destination.
2. 10-minute approval TTL in PostgreSQL (grocer.approvals).
3. Small-Cart Fee Shock Protection integration (ADR 0009).
4. Strict integer paise money calculations; zero floating-point formatting.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.agent.customer_advocate import (
    extract_cart_to_pay_paise,
)
from backend.integrations.commerce.schemas import CartData, CartItem

logger = logging.getLogger("grocer.approval")

__all__ = [
    "ApprovalRecord",
    "compute_cart_fingerprint",
    "create_checkout_approval",
]


@dataclass
class ApprovalRecord:
    id: str
    user_id: str
    fingerprint: str
    to_pay_paise: int
    address_id: str
    snapshot: dict[str, Any]
    status: str
    expires_at: datetime


def compute_cart_fingerprint(
    items: list[CartItem | dict[str, Any]],
    to_pay_paise: int,
    address_id: str,
) -> str:
    """Compute canonical SHA-256 fingerprint for cart items, integer paise, and destination.

    Enforces ARCHITECTURE.md line 291: Canonical SHA-256 hash of basket items & paise.
    """
    normalized_items: list[tuple[str, int]] = []
    for it in items:
        if isinstance(it, CartItem):
            spin_id = it.spinId
            qty = it.quantity
        else:
            spin_id = str(it.get("spinId") or it.get("spin_id") or "")
            qty = int(it.get("quantity") or 1)
        normalized_items.append((spin_id, qty))

    # Sort deterministically by spinId
    normalized_items.sort(key=lambda x: x[0])
    items_repr = ",".join(f"{s}:{q}" for s, q in normalized_items)
    payload = f"{items_repr}|{to_pay_paise}|{address_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def create_checkout_approval(
    conn: Any,
    user_id: str,
    cart: CartData,
    address_id: str,
    ttl_minutes: int = 10,
) -> ApprovalRecord:
    """Create a 10-minute valid checkout approval record in PostgreSQL."""
    to_pay_paise = extract_cart_to_pay_paise(cart)
    fingerprint = compute_cart_fingerprint(cart.items, to_pay_paise, address_id)

    snapshot = {
        "items": [
            {
                "spinId": it.spinId,
                "itemName": it.itemName,
                "quantity": it.quantity,
                "price_paise": it.discounted_final_price_paise,
            }
            for it in cart.items
        ],
        "to_pay_paise": to_pay_paise,
        "address_id": address_id,
    }

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    row = await conn.fetchrow(
        """
        INSERT INTO grocer.approvals (
            user_id,
            fingerprint,
            to_pay_paise,
            address_id,
            snapshot,
            status,
            expires_at
        )
        VALUES ($1, $2, $3, $4, $5, 'shown', $6)
        RETURNING id, user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at;
        """,
        user_id,
        fingerprint,
        to_pay_paise,
        address_id,
        json.dumps(snapshot),
        expires_at,
    )

    return ApprovalRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        fingerprint=row["fingerprint"],
        to_pay_paise=int(row["to_pay_paise"]),
        address_id=row["address_id"],
        snapshot=json.loads(row["snapshot"]) if isinstance(row["snapshot"], str) else row["snapshot"],
        status=row["status"],
        expires_at=row["expires_at"],
    )
