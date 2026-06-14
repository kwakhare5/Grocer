"""
Sync Service — responsible for fetching orders from the MCP server
and persisting them to the database.

Why a service layer?
  - Keeps the route handler thin (HTTP concerns only).
  - Makes the sync logic independently testable without needing FastAPI.
  - Allows future swapping of the MCP transport without touching routes.
"""

import logging
import httpx
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Order, OrderItem
from backend.config import settings

logger = logging.getLogger(__name__)


def _normalize_quantity(quantity, unit: str, standard_quantity=None) -> float:
    """Safely coerce external quantity values to float. Defaults to 1.0 on bad input."""
    if standard_quantity is not None:
        try:
            return float(standard_quantity)
        except (ValueError, TypeError):
            pass
    try:
        return float(quantity)
    except (ValueError, TypeError):
        logger.warning(f"Could not normalize quantity '{quantity}' (unit='{unit}'). Defaulting to 1.0")
        return 1.0


async def fetch_and_sync_orders(household_id: str, user_id: str, db: AsyncSession) -> int:
    """
    Fetch new orders from the MCP server and persist them to the DB.

    Returns:
        int: Number of new orders inserted (already-synced orders are skipped).

    Raises:
        HTTPException: If the MCP server is unreachable or returns an error.
    """
    from fastapi import HTTPException

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        try:
            response = await client.get(
                f'{settings.MCP_BASE_URL}/get_instamart_orders',
                params={"user_id": user_id, "limit": 200}
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=503, detail="MCP server timed out. Please try again.")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to fetch from MCP: {str(e)}")

    orders_synced = 0
    raw_orders = data.get("orders", [])

    # Batch check: load all existing order IDs in one query to avoid N+1
    instamart_ids = [o["order_id"] for o in raw_orders]
    if instamart_ids:
        existing_result = await db.execute(
            select(Order.instamart_order_id).where(Order.instamart_order_id.in_(instamart_ids))
        )
        already_synced = {row[0] for row in existing_result.all()}
    else:
        already_synced = set()

    for raw_order in raw_orders:
        if raw_order["order_id"] in already_synced:
            continue  # Skip orders already in DB

        new_order = Order(
            household_id=household_id,
            instamart_order_id=raw_order["order_id"],
            placed_at=datetime.fromisoformat(raw_order["placed_at"]),
            total_amount=raw_order.get("total"),
            raw_data=raw_order
        )
        db.add(new_order)
        await db.flush()  # Get the new order's ID before committing

        for item in raw_order.get("items", []):
            std_qty = _normalize_quantity(
                item.get("quantity"),
                item.get("unit", ""),
                item.get("standard_quantity")
            )
            new_item = OrderItem(
                order_id=new_order.id,
                item_id=item["item_id"],
                item_name=item["item_name"],
                category=item.get("category"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                standard_quantity=std_qty,
                price=item.get("price")
            )
            db.add(new_item)

        orders_synced += 1

    await db.commit()
    return orders_synced
