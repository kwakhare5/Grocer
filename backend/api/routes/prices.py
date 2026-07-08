"""
Prices API — Task 3.5 (frontend hydration)
Exposes commodity price histories and AI intelligence alerts.

Endpoints:
  - GET /api/prices/feed   — lists the 10-day history and rolling stats for all commodities
  - GET /api/prices/alerts — returns active spike/dip alerts
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone

from backend.database.connection import get_db
from backend.database.models import PriceHistory
from backend.services.cache import cache_response

router = APIRouter(prefix='/api/prices', tags=['prices'])

# Match the IDs and names from catalog / generate_orders.py
COMMODITY_MAPPINGS = {
    "INS_006": {
        "id": "tomatoes",
        "name": "Tomatoes 500g",
        "unit": "per 500g",
        "suggestion": "Use canned tomatoes for this week. Spike typically lasts 8-12 days based on past patterns."
    },
    "INS_003": {
        "id": "oil",
        "name": "Fortune Sunflower Oil 1L",
        "unit": "per litre",
        "suggestion": "Good time to stock 2-3 bottles. Currently 23% below your 30-day average."
    },
    "INS_007": {
        "id": "onions",
        "name": "Onions 1kg",
        "unit": "per kg",
        "suggestion": "Onion prices are showing a slight upward watch trend. Purchase normal weekly quantities."
    },
    "INS_001": {
        "id": "milk",
        "name": "Amul Taza Milk 1L",
        "unit": "per litre",
        "suggestion": "Milk prices remain stable. Purchase on regular restock alerts."
    }
}


@router.get('/feed')
@cache_response(ttl=3600, key_prefix="price_feed")
async def get_price_feed(db: AsyncSession = Depends(get_db)):
    """
    Returns the daily price feed for the commodities:
    Tomato, Oil, Onion, Milk.
    Includes 10-day history and 30-day average comparison.
    """
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_10d = now - timedelta(days=10)

    # 1. Fetch 30-day average for each item
    avg_stmt = (
        select(PriceHistory.item_id, func.avg(PriceHistory.price).label("avg_price"))
        .where(PriceHistory.recorded_at >= cutoff_30d)
        .group_by(PriceHistory.item_id)
    )
    avg_res = await db.execute(avg_stmt)
    avg_map = {row.item_id: float(row.avg_price) for row in avg_res.all()}

    # 2. Fetch history for the last 10 days
    hist_stmt = (
        select(PriceHistory)
        .where(PriceHistory.recorded_at >= cutoff_10d)
        .order_by(PriceHistory.item_id, PriceHistory.recorded_at.asc())
    )
    hist_res = await db.execute(hist_stmt)
    all_history = hist_res.scalars().all()

    # Group history by item_id
    history_by_item = {}
    for h in all_history:
        if h.item_id not in history_by_item:
            history_by_item[h.item_id] = []
        
        # Format date for sparkline label (e.g. "May 15")
        day_str = h.recorded_at.strftime("%b %d")
        history_by_item[h.item_id].append({
            "day": day_str,
            "price": float(h.price)  # type: ignore
        })

    feed = []
    for item_id, meta in COMMODITY_MAPPINGS.items():
        history = history_by_item.get(item_id, [])
        current_price = history[-1]["price"] if history else 0.0
        avg_30d = avg_map.get(item_id, current_price or 1.0)

        # Calculate signal
        ratio = current_price / avg_30d if avg_30d else 1.0
        if ratio >= 1.3:
            signal = "SPIKE"
        elif ratio <= 0.85:
            signal = "DIP"
        elif ratio >= 1.05:
            signal = "WATCH"
        else:
            signal = "STABLE"

        feed.append({
            "id": meta["id"],
            "item_id": item_id,
            "name": meta["name"],
            "unit": meta["unit"],
            "current": current_price,
            "avg30d": round(avg_30d, 1),
            "signal": signal,
            "suggestion": meta["suggestion"] if signal in ["SPIKE", "DIP", "WATCH"] else None,
            "history": history
        })

    return feed


@router.get('/alerts')
@cache_response(ttl=3600, key_prefix="price_alerts")
async def get_price_alerts(db: AsyncSession = Depends(get_db)):
    """
    Returns only active price alerts (spikes or dips).
    """
    feed = await get_price_feed(db)
    alerts = [item for item in feed if item["signal"] in ["SPIKE", "DIP"]]
    return {"alerts": alerts}
