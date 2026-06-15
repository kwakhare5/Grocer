"""
Orders API — returns past order history for a household.
Reads directly from the generated_orders.json seed file.
"""

from fastapi import APIRouter, HTTPException
import json
import os
from pathlib import Path

router = APIRouter(prefix="/api/orders", tags=["orders"])

ORDERS_FILE = Path(__file__).parent.parent.parent / "seed" / "generated_orders.json"


@router.get("/{user_id}")
async def get_orders(user_id: str, limit: int = 30):
    """
    Return the last N orders for a user, newest first.
    Reads from the seed/generated_orders.json file.
    """
    if not ORDERS_FILE.exists():
        return {"user_id": user_id, "orders": []}

    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            all_orders = json.load(f)
    except Exception:
        return {"user_id": user_id, "orders": []}

    # Filter by user_id, sort newest first, limit
    user_orders = [o for o in all_orders if o.get("user_id") == user_id]
    user_orders.sort(key=lambda o: o.get("placed_at", ""), reverse=True)
    user_orders = user_orders[:limit]

    return {
        "user_id": user_id,
        "total": len(user_orders),
        "orders": user_orders,
    }
