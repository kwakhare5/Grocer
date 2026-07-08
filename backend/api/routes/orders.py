"""
Orders API — returns past order history for a household.
Reads directly from the PostgreSQL database using SQLAlchemy ORM.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.connection import get_db
from backend.database.models import Order, Household

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/{user_id}")
async def get_orders(user_id: str, limit: int = 30, db: AsyncSession = Depends(get_db)):
    """
    Return the last N orders for a user, newest first.
    Reads from the PostgreSQL Orders table.
    """
    stmt = (
        select(Order)
        .join(Household)
        .where(Household.user_id == user_id)
        .order_by(Order.placed_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    user_orders = [o.raw_data for o in orders if o.raw_data]

    return {
        "user_id": user_id,
        "total": len(user_orders),
        "orders": user_orders,
    }

