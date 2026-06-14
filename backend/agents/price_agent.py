"""
Price Intelligence Agent — Task 4.5
Monitors volatile commodity price trends, updates history,
and dispatches dip/spike alerts via WhatsApp notifications and RestockAlert logs.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.config import settings
from backend.mcp.client import mcp_client
from backend.database.models import PriceHistory, Household, RestockAlert
from backend.notifications.whatsapp import send_whatsapp_message

logger = logging.getLogger(__name__)

# Volatile commodities map: (Catalog item ID, search query, threshold for spike, threshold for dip)
VOLATILE_COMMODITIES: List[Tuple[str, str, float, float]] = [
    ("INS_006", "tomatoes", 25.0, -10.0),       # Tomato spike threshold +25%, dip -10%
    ("INS_007", "onions", 25.0, -10.0),         # Onion spike threshold +25%, dip -10%
    ("INS_003", "sunflower oil", 15.0, -10.0),   # Oil spike threshold +15%, dip -10%
    ("INS_002", "atta", 15.0, -10.0),            # Atta spike threshold +15%, dip -10%
    ("INS_001", "milk", 10.0, -5.0),             # Milk spike threshold +10%, dip -5%
]

SUGGESTIONS = {
    "tomatoes": "Use canned tomatoes or tomato puree for this week. Spikes typically last 8-12 days based on past patterns.",
    "onions": "Onion prices are showing a upward watch trend. Purchase normal weekly quantities and avoid stockpiling.",
    "sunflower oil": "Good time to stock 2-3 bottles. Currently significantly below your 30-day average.",
    "atta": "Atta price dipped. Consider stocking up a 5kg bag.",
    "milk": "Milk prices are showing minor fluctuations. Purchase on normal schedule."
}


async def track_and_alert_prices(db: AsyncSession) -> dict:
    """
    Core function for the Price Intelligence Agent.
    1. Queries current prices of volatile commodities from mock MCP catalog.
    2. Logs the prices into the TimescaleDB price_history hypertable.
    3. Analyzes prices against 30-day rolling averages.
    4. Triggers restock/price alerts and sends WhatsApp messages for spikes/dips.
    """
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    alerts_triggered = []
    prices_recorded = 0

    logger.info("[PriceAgent] Initiating commodity price tracking...")

    for item_id, query, spike_thresh, dip_thresh in VOLATILE_COMMODITIES:
        try:
            # 1. Fetch current price from Swiggy Instamart mock catalog
            res = await mcp_client.search_instamart_items(query)
            items = res.get("items", [])
            if not items:
                logger.warning(f"[PriceAgent] No items found in catalog for search query: '{query}'")
                continue
            
            # Match strictly by item_id if available, otherwise fallback to first result
            best_match = None
            for item in items:
                if item.get("id") == item_id:
                    best_match = item
                    break
            if not best_match:
                best_match = items[0]

            current_price = float(best_match["price"])
            price_per_unit = float(best_match.get("price_per_unit", current_price))
            item_name = best_match["name"]

            # 2. Log entry in price_history
            ph_entry = PriceHistory(
                item_id=best_match["id"],
                item_name=item_name,
                recorded_at=now,
                price=current_price,
                price_per_unit=price_per_unit
            )
            db.add(ph_entry)
            prices_recorded += 1

            # 3. Query rolling 30-day average price
            stmt_avg = (
                select(func.avg(PriceHistory.price_per_unit))
                .where(PriceHistory.item_id == best_match["id"])
                .where(PriceHistory.recorded_at >= cutoff_30d)
            )
            res_avg = await db.execute(stmt_avg)
            avg_price_row = res_avg.scalar()

            if avg_price_row is not None:
                avg_price = float(avg_price_row)
                pct_change = ((price_per_unit - avg_price) / avg_price) * 100.0
                
                # Check for significant spike or dip
                is_spike = pct_change >= spike_thresh
                is_dip = pct_change <= dip_thresh

                if is_spike or is_dip:
                    signal = "SPIKE" if is_spike else "DIP"
                    logger.info(f"[PriceAgent] Price alert detected for {item_name}: {pct_change:+.1f}% vs 30d avg")

                    # Construct message
                    direction = "📈 Price Alert" if is_spike else "📉 Price Dip"
                    action_word = "spike" if is_spike else "dip"
                    change_sign = "+" if pct_change > 0 else ""
                    
                    suggestion = SUGGESTIONS.get(query, "Purchase as needed.")
                    if is_dip and query == "sunflower oil":
                        suggestion = "Good time to stock 2-3 bottles. Currently significantly below your 30-day average."
                    
                    alert_msg = f"{direction}: *{item_name}*\n" \
                                f"Current price: ₹{price_per_unit:.2f}/unit ({change_sign}{pct_change:.1f}% vs 30-day average of ₹{avg_price:.2f}).\n" \
                                f"Recommendation: {suggestion}"

                    # 4. Dispatch alert to opted-in households
                    stmt_hh = select(Household).where(Household.notifications_enabled == True)
                    res_hh = await db.execute(stmt_hh)
                    households = res_hh.scalars().all()

                    for hh in households:
                        # Log RestockAlert
                        alert_record = RestockAlert(
                            household_id=hh.id,
                            item_ids=[best_match["id"]],
                            message_sent=alert_msg,
                            sent_at=now,
                            status="sent"
                        )
                        db.add(alert_record)

                        # Send WhatsApp message if phone is set
                        if hh.phone_number:
                            await send_whatsapp_message(hh.phone_number, alert_msg)
                    
                    alerts_triggered.append({
                        "item_name": item_name,
                        "signal": signal,
                        "change_pct": round(pct_change, 1),
                        "current_price": price_per_unit,
                        "avg_price": round(avg_price, 2)
                    })
        except Exception as e:
            logger.error(f"[PriceAgent] Error tracking price for {item_id}: {e}")

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[PriceAgent] Database commit failed: {e}")

    return {
        "prices_recorded": prices_recorded,
        "alerts_triggered": alerts_triggered
    }
