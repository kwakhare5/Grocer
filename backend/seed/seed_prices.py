"""
Seed Price History — Task 3.5
Seeds the `price_history` table in TimescaleDB with 30 days of historical data
matching the demo scenario:
  - Tomatoes INS_006: spike from ₹19 → ₹48
  - Oil INS_003: dip from ₹130 → ₹98
  - Onions INS_007: slow rise from ₹35 → ₹42
  - Milk INS_001: stable at ₹28
"""

import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from backend.database.connection import AsyncSessionLocal, init_db
from backend.database.models import PriceHistory

# Realistic 10-point price histories matching frontend mock values
COMMODITIES_SEEDS = {
    "INS_006": {
        "name": "Tomatoes (500g)",
        "prices": [19, 21, 20, 22, 23, 25, 29, 35, 41, 48],
    },
    "INS_003": {
        "name": "Fortune Sunflower Oil 1L",
        "prices": [130, 128, 127, 125, 120, 115, 110, 105, 100, 98],
    },
    "INS_007": {
        "name": "Onions (1kg)",
        "prices": [35, 36, 38, 37, 39, 40, 41, 40, 42, 42],
    },
    "INS_001": {
        "name": "Amul Taza Milk 1L",
        "prices": [28, 28, 28, 28, 28, 28, 28, 28, 28, 28],
    }
}


async def seed_prices():
    print("Seeding price history data...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Clear existing price history
        await db.execute(text("DELETE FROM price_history;"))
        await db.commit()

        now = datetime.now(timezone.utc)
        records = []

        for item_id, data in COMMODITIES_SEEDS.items():
            name = data["name"]
            prices = data["prices"]
            n_points = len(prices)

            # We distribute these prices over the last 30 days (every 3 days)
            for i, price in enumerate(prices):
                days_ago = (n_points - 1 - i) * 3
                recorded_at = now - timedelta(days=days_ago)

                # Standard standard base calculations
                price_per_unit = float(price)

                records.append(
                    PriceHistory(
                        item_id=item_id,
                        item_name=name,
                        recorded_at=recorded_at,
                        price=float(price),
                        price_per_unit=price_per_unit,
                    )
                )

        db.add_all(records)
        await db.commit()
        print(f"Successfully seeded {len(records)} price history records!")


if __name__ == "__main__":
    asyncio.run(seed_prices())
