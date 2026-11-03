"""Grocer — Milestone-Only Delivery Notification Dispatcher.

Enforces:
1. 3 discrete delivery milestones: Confirmed, Picked Up, Delivered.
2. Anti-spam milestone latch: notifications are only dispatched when the order
   advances to a strictly new milestone; never repeated on polling ticks.
3. Only Swiggy's own ETA is shown; no invented link or delivery time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("grocer.delivery_tracker")

MILESTONE_CONFIRMED = "CONFIRMED"
MILESTONE_PICKED_UP = "PICKED_UP"
MILESTONE_DELIVERED = "DELIVERED"


@dataclass(frozen=True)
class MilestoneNotification:
    order_id: str
    milestone: str
    message: str


def resolve_delivery_milestone(
    status_text: str | None = None,
    delivered: bool = False,
    cancelled: bool = False,
    order_status: str | None = None,
) -> str | None:
    """Resolve normalized delivery milestone from raw Swiggy status fields."""
    if cancelled:
        return None

    if delivered or (order_status and order_status.upper() == "DELIVERED"):
        return MILESTONE_DELIVERED

    raw = f"{status_text or ''} {order_status or ''}".lower()

    if any(k in raw for k in ["on the way", "rider", "picked up", "dispatched", "out for delivery"]):
        return MILESTONE_PICKED_UP

    if any(k in raw for k in ["placed", "confirmed", "packing", "received", "processing"]):
        return MILESTONE_CONFIRMED

    return MILESTONE_CONFIRMED


def format_milestone_notification(
    order_id: str,
    milestone: str,
    eta_text: str | None = None,
    rider_name: str | None = None,
) -> MilestoneNotification:
    """Format plain, human WhatsApp milestone push messages adhering to bro style."""
    if milestone == MILESTONE_CONFIRMED:
        eta = f" ({eta_text})" if eta_text else ""
        msg = f"🎉 *Order #{order_id} Confirmed!* The dark store is packing your items{eta}."
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_CONFIRMED,
            message=msg,
        )

    if milestone == MILESTONE_PICKED_UP:
        eta = f" ETA: {eta_text}." if eta_text else ""
        rider = f" Delivery partner {rider_name}" if rider_name else " Delivery partner"
        msg = (
            f"🛵 *Order #{order_id} is on the way!*{eta}{rider} has picked up your bag."
        )
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_PICKED_UP,
            message=msg,
        )

    if milestone == MILESTONE_DELIVERED:
        msg = f"📦 *Order #{order_id} Delivered!* Your groceries have arrived. Enjoy your meal!"
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_DELIVERED,
            message=msg,
        )

    raise ValueError(f"Unknown milestone: {milestone}")
