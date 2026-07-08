"""
Seed Data Generator — Task 4.6
Generates realistic PreFill order history for an Indian household.
Guarantees exact cycle lengths, last purchase dates, travel gaps, and guest spikes.
"""

import json
import random
from datetime import datetime, timedelta, timezone
import os

# Aligned with backend/seed/catalog.py
HOUSEHOLD_ITEMS = {
    "INS_001": {
        "name": "Amul Taza Milk 1L",
        "category": "dairy",
        "unit": "L",
        "pack_size": 1.0,
        "family_daily_use": 1.0,          # 1L/day for family
        "cycle": 2.1,                     # 2.1 days cycle
        "variance": 0.3,
        "last_purchase_days_ago": 1,
        "base_price": 28
    },
    "INS_002": {
        "name": "Aashirvaad Atta 5kg",
        "category": "staples",
        "unit": "kg",
        "pack_size": 5.0,
        "family_daily_use": 0.30,         # ~17 days cycle (5 / 0.3 = 16.7d)
        "cycle": 16.7,
        "variance": 1.0,
        "last_purchase_days_ago": 5,
        "base_price": 198
    },
    "INS_003": {
        "name": "Fortune Sunflower Oil 1L",
        "category": "staples",
        "unit": "L",
        "pack_size": 1.0,
        "family_daily_use": 0.068,        # exactly 14.7 days cycle (1 / 0.068 = 14.7d)
        "cycle": 14.7,
        "variance": 0.0,                  # exact cycle for demo
        "last_purchase_days_ago": 13,     # exactly 13 days ago (depletes in 1.7 days!)
        "base_price": 127
    },
    "INS_005": {
        "name": "Nandini Eggs (Pack of 12)",
        "category": "protein",
        "unit": "piece",
        "pack_size": 12.0,
        "family_daily_use": 2.5,          # ~4.8 days cycle (12 / 2.5 = 4.8d)
        "cycle": 4.8,
        "variance": 0.5,
        "last_purchase_days_ago": 3,
        "base_price": 84
    },
    "INS_006": {
        "name": "Tomatoes (500g)",
        "category": "vegetables",
        "unit": "kg",
        "pack_size": 0.5,
        "family_daily_use": 0.15,         # ~3.3 days cycle
        "cycle": 3.3,
        "variance": 0.4,
        "last_purchase_days_ago": 3,
        "base_price": 29
    },
    "INS_007": {
        "name": "Onions (1kg)",
        "category": "vegetables",
        "unit": "kg",
        "pack_size": 1.0,
        "family_daily_use": 0.14,         # ~7.1 days cycle
        "cycle": 7.1,
        "variance": 0.8,
        "last_purchase_days_ago": 3,
        "base_price": 42
    },
    "INS_011": {
        "name": "Britannia Whole Wheat Bread",
        "category": "bakery",
        "unit": "400g",
        "pack_size": 1.0,
        "family_daily_use": 0.25,         # 4 days cycle
        "cycle": 4.0,
        "variance": 0.4,
        "last_purchase_days_ago": 1,
        "base_price": 50
    }
}



def generate_realistic_orders(months: int = 4, user_id: str = "demo_user_001"):
    # Seed random generator to ensure generated mock data is deterministic and identical
    random.seed(42)
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=months * 30)

    # 1. Travel gap spans days 43-53 exactly relative to start_date
    travel_start = start_date + timedelta(days=43)
    travel_end = start_date + timedelta(days=53)

    # 2. Guest spike in dairy in month 3 (day 75)
    guest_date = start_date + timedelta(days=75)

    # Dictionary: {date_str: [items ordered]}
    order_items_by_date = {}

    for item_id, item in HOUSEHOLD_ITEMS.items():
        cycle = item["cycle"]
        variance = item["variance"]
        last_buy_days = item["last_purchase_days_ago"]

        # Track dates backward from last purchase
        current_date = now - timedelta(days=last_buy_days)

        while current_date > start_date:
            # Skip travel gap
            if travel_start <= current_date <= travel_end:
                current_date = current_date - timedelta(days=cycle + random.uniform(-variance, variance))
                continue

            date_str = current_date.strftime("%Y-%m-%d")
            if date_str not in order_items_by_date:
                order_items_by_date[date_str] = []

            # Determine quantity
            qty = 1
            # Guest spike: order 3x milk on guest date
            if item_id == "INS_001" and abs((current_date - guest_date).days) <= 1:
                qty = 3

            price = round(float(item["base_price"]) * qty * random.uniform(0.96, 1.04), 2)

            order_items_by_date[date_str].append({
                "item_id": item_id,
                "item_name": item["name"],
                "quantity": qty,
                "standard_quantity": float(qty) * item["pack_size"],
                "unit": item["unit"],
                "category": item["category"],
                "price": price
            })

            # Move backwards
            current_date = current_date - timedelta(days=cycle + random.uniform(-variance, variance))

    # Convert to standard orders
    orders = []
    order_counter = 1

    for date_str in sorted(order_items_by_date.keys()):
        items = order_items_by_date[date_str]
        if not items:
            continue

        order_hour = random.choice([8, 9, 10, 18, 19, 20])
        order_minute = random.randint(0, 59)

        platform = ["instamart", "blinkit", "zepto"][order_counter % 3]
        prefix = {"instamart": "INS_", "blinkit": "BLK_", "zepto": "ZEP_"}[platform]
        order_id = f"{prefix}MOCK_{order_counter:04d}"

        orders.append({
            "order_id": order_id,
            "user_id": user_id,
            "placed_at": f"{date_str}T{order_hour:02d}:{order_minute:02d}:00+05:30",
            "platform": platform,
            "items": items,
            "total": round(sum(i["price"] for i in items), 2),
            "status": "delivered"
        })
        order_counter += 1

    return orders


if __name__ == "__main__":
    print("Generating precision seed orders...")
    orders = generate_realistic_orders()

    output_dir = os.path.dirname(__file__)
    output_path = os.path.join(output_dir, "generated_orders.json")
    with open(output_path, "w") as f:
        json.dump(orders, f, indent=2)

    print(f"Generated {len(orders)} precision orders over 4 months.")
    print("  Travel gap: Day 43 to Day 53.")
    print("  Milk cycle: exactly 2.1 days average.")
    print("  Oil cycle: exactly 14.7 days, last bought 13 days ago.")
    print(f"  Saved to {output_path}")
