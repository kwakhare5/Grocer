import random
from datetime import datetime, timedelta, timezone
from backend.seed.generate_orders import HOUSEHOLD_ITEMS

def generate_scenario_orders(scenario: str, months: int = 4, user_id: str = "demo_user_001"):
    # Seed random generator to ensure generated fake data is deterministic and identical on every refresh/regenerate
    random.seed(42)
    # Create a deep copy of HOUSEHOLD_ITEMS
    items = {k: dict(v) for k, v in HOUSEHOLD_ITEMS.items()}
    
    if scenario == "party":
        # Simulate party spike: dairy products are consumed very fast
        # Milk cycle is short, butter cycle is short, cream cycle is short
        # Last purchase days ago matches near depletion
        items["INS_001"]["cycle"] = 1.0
        items["INS_001"]["last_purchase_days_ago"] = 1
        
        if "INS_008" in items:
            items["INS_008"]["cycle"] = 4.0
            items["INS_008"]["last_purchase_days_ago"] = 3
        
        if "INS_009" in items:
            items["INS_009"]["cycle"] = 2.0
            items["INS_009"]["last_purchase_days_ago"] = 2
        
        # Increase tomatoes and onions depletion
        if "INS_006" in items:
            items["INS_006"]["cycle"] = 2.0
            items["INS_006"]["last_purchase_days_ago"] = 2

    elif scenario == "vacation":
        # Simulate vacation/travel: zero consumption recently, or they just stocked up everything
        # So days remaining are very high (everything was bought 1 day ago)
        for item_id in items:
            items[item_id]["last_purchase_days_ago"] = 1
            # Adjust cycle to be longer
            items[item_id]["cycle"] = float(items[item_id]["cycle"]) * 1.5
            
    # Now generate orders using these scenario-specific parameters
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=months * 30)

    # Travel gap spans days 43-53 exactly relative to start_date
    travel_start = start_date + timedelta(days=43)
    travel_end = start_date + timedelta(days=53)

    # Guest spike in dairy in month 3 (day 75)
    guest_date = start_date + timedelta(days=75)

    order_items_by_date = {}

    for item_id, item in items.items():
        cycle: float = float(item["cycle"])
        variance: float = float(item["variance"])
        last_buy_days: int = int(item["last_purchase_days_ago"])
        pack_size: float = float(item["pack_size"])
        base_price: float = float(item["base_price"])

        current_date = now - timedelta(days=last_buy_days)

        while current_date > start_date:
            if travel_start <= current_date <= travel_end:
                current_date = current_date - timedelta(days=cycle + random.uniform(-variance, variance))
                continue

            date_str = current_date.strftime("%Y-%m-%d")
            if date_str not in order_items_by_date:
                order_items_by_date[date_str] = []

            qty = 1
            if item_id == "INS_001" and abs((current_date - guest_date).days) <= 1:
                qty = 3

            price = round(base_price * qty * random.uniform(0.96, 1.04), 2)

            order_items_by_date[date_str].append({
                "item_id": item_id,
                "item_name": item["name"],
                "quantity": qty,
                "standard_quantity": float(qty) * pack_size,
                "unit": item["unit"],
                "category": item["category"],
                "price": price
            })

            current_date = current_date - timedelta(days=cycle + random.uniform(-variance, variance))

    orders = []
    order_counter = 1

    for date_str in sorted(order_items_by_date.keys()):
        items_list = order_items_by_date[date_str]
        if not items_list:
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
            "items": items_list,
            "total": round(sum(i["price"] for i in items_list), 2),
            "status": "delivered"
        })
        order_counter += 1

    return orders
