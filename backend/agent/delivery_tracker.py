"""Grocer v1.0 — Milestone-Only Delivery Notification Dispatcher.

Enforces:
1. 3 discrete delivery milestones: Confirmed, Picked Up, Delivered.
2. Anti-spam milestone latch: notifications are only dispatched when the order
   advances to a strictly new milestone; never repeated on polling ticks.
3. Real-time GPS map link included on Picked Up milestone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("grocer.delivery_tracker")

MILESTONE_CONFIRMED = "CONFIRMED"
MILESTONE_PICKED_UP = "PICKED_UP"
MILESTONE_DELIVERED = "DELIVERED"

VALID_MILESTONES = (MILESTONE_CONFIRMED, MILESTONE_PICKED_UP, MILESTONE_DELIVERED)


@dataclass(frozen=True)
class MilestoneNotification:
    order_id: str
    milestone: str
    message: str
    map_url: str | None = None


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


def should_send_milestone_push(
    last_milestone: str | None,
    new_milestone: str,
) -> bool:
    """Anti-spam guardrail: strictly push only when milestone state advances."""
    if last_milestone == new_milestone:
        return False

    order_hierarchy = {
        None: 0,
        MILESTONE_CONFIRMED: 1,
        MILESTONE_PICKED_UP: 2,
        MILESTONE_DELIVERED: 3,
    }

    last_rank = order_hierarchy.get(last_milestone, 0)
    new_rank = order_hierarchy.get(new_milestone, 0)

    return new_rank > last_rank


def format_milestone_notification(
    order_id: str,
    milestone: str,
    eta_text: str | None = None,
    live_map_url: str | None = None,
    rider_name: str | None = None,
) -> MilestoneNotification:
    """Format plain, human WhatsApp milestone push messages adhering to bro style."""
    if live_map_url is None:
        live_map_url = f"https://swiggy.com/track/{order_id}"

    if milestone == MILESTONE_CONFIRMED:
        eta = f" ({eta_text})" if eta_text else " (10-15 mins)"
        msg = f"🎉 *Order #{order_id} Confirmed!* The dark store is packing your items{eta}."
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_CONFIRMED,
            message=msg,
            map_url=None,
        )

    if milestone == MILESTONE_PICKED_UP:
        eta = f" ETA: {eta_text}." if eta_text else ""
        rider = f" Delivery partner {rider_name}" if rider_name else " Delivery partner"
        msg = (
            f"🛵 *Order #{order_id} is on the way!*{eta}{rider} has picked up your bag.\n"
            f"Track live: {live_map_url}"
        )
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_PICKED_UP,
            message=msg,
            map_url=live_map_url,
        )

    if milestone == MILESTONE_DELIVERED:
        msg = f"📦 *Order #{order_id} Delivered!* Your groceries have arrived. Enjoy your meal!"
        return MilestoneNotification(
            order_id=order_id,
            milestone=MILESTONE_DELIVERED,
            message=msg,
            map_url=None,
        )

    raise ValueError(f"Unknown milestone: {milestone}")
