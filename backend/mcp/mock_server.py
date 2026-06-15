from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from contextlib import asynccontextmanager
import json
import os
import uuid
import random
from backend.seed.catalog import CATALOG as MOCK_CATALOG

# In-memory store for mock orders — loaded from seed data file
MOCK_ORDERS = []
MOCK_CART = {"items": [], "cart_id": None}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global MOCK_ORDERS
    seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
    if os.path.exists(seed_file):
        with open(seed_file) as f:
            MOCK_ORDERS = json.load(f)
        print(f"Loaded {len(MOCK_ORDERS)} mock orders")
    else:
        print(f"Seed file not found at {seed_file}. Please run generate_orders.py first.")
    yield

app = FastAPI(title="Mock Swiggy Instamart MCP", lifespan=lifespan)

@app.get("/get_instamart_orders")
async def get_orders(user_id: str = "demo_user_001", limit: int = 100):
    return {
        "success": True,
        "user_id": user_id,
        "total_orders": len(MOCK_ORDERS),
        "orders": MOCK_ORDERS[-limit:]
    }

@app.post("/search_instamart_items")
async def search_items(body: dict):
    query = body.get("query", "").lower()
    results = [item for item in MOCK_CATALOG if query in str(item["name"]).lower() or query in str(item.get("category", "")).lower()]
    return {"items": results if results else MOCK_CATALOG[:3]}


class CartUpdate(BaseModel):
    items: list

@app.post("/update_instamart_cart")
async def update_cart(body: CartUpdate):
    MOCK_CART["cart_id"] = f"CART_{str(uuid.uuid4())[:8]}"
    MOCK_CART["items"] = body.items
    total = sum(item.get("price", 50) * item.get("quantity", 1) for item in body.items)
    return {"success": True, "cart_id": MOCK_CART["cart_id"], "items": body.items, "total": total}

@app.get("/get_instamart_cart")
async def get_cart():
    return {"success": True, **MOCK_CART}

class PlaceOrder(BaseModel):
    cart_id: str

@app.post("/place_instamart_order")
async def place_order(body: PlaceOrder):
    order_id = f"INS_{random.randint(10000, 99999)}"
    
    # Look up items in the mock cart
    items = []
    total = 0.0
    
    # Standard pack sizes mapping
    pack_sizes = {
        "INS_001": 1.0,
        "INS_002": 5.0,
        "INS_003": 1.0,
        "INS_004": 5.0,
        "INS_005": 12.0,
        "INS_006": 0.5,
        "INS_007": 1.0,
        "INS_008": 0.5,
        "INS_009": 1.0,
        "INS_010": 1.0,
        "INS_011": 1.0,
        "INS_012": 1.0,
    }
    
    # In-memory store for mock orders — loaded from seed data file
    global MOCK_ORDERS, MOCK_CART
    if MOCK_CART.get("cart_id") == body.cart_id:
        for item in (MOCK_CART.get("items") or []):
            item_id = item.get("item_id")
            # Lookup in CATALOG to get canonical details
            cat_item = next((c for c in MOCK_CATALOG if c["id"] == item_id), None)
            price = cat_item["price"] if cat_item else item.get("price", 50.0)
            name = cat_item["name"] if cat_item else item.get("item_name", item_id)
            unit = cat_item["unit"] if cat_item else "unit"
            category = cat_item["category"] if cat_item else "General"
            qty = item.get("quantity", 1)
            pack_size = pack_sizes.get(item_id, 1.0)
            
            items.append({
                "item_id": item_id,
                "item_name": name,
                "quantity": qty,
                "standard_quantity": float(qty) * pack_size,
                "unit": unit,
                "category": category,
                "price": price
            })
            total += price * qty
            
    if not items:
        # Fallback in case of empty/expired cart
        items = [{
            "item_id": "INS_001",
            "item_name": "Amul Taza Milk 1L",
            "quantity": 1,
            "standard_quantity": 1.0,
            "unit": "L",
            "category": "dairy",
            "price": 28.0
        }]
        total = 28.0
        
    new_order = {
        "order_id": order_id,
        "user_id": "demo_user_001",
        "placed_at": datetime.now().isoformat(),
        "items": items,
        "total": total,
        "status": "placed"
    }
    
    # Add to in-memory orders
    MOCK_ORDERS.append(new_order)
    
    # Persist the orders list to the JSON seed file to sync permanently
    try:
        seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
        with open(seed_file, "w") as f:
            json.dump(MOCK_ORDERS, f, indent=2)
        print(f"Mock server appended new order {order_id} and updated generated_orders.json")
    except Exception as e:
        print(f"Mock server failed to write generated_orders.json: {e}")
        
    return {
        "success": True,
        "order_id": order_id,
        "cart_id": body.cart_id,
        "status": "placed",
        "estimated_delivery_minutes": random.randint(12, 20),
        "placed_at": new_order["placed_at"]
    }

@app.get("/track_instamart_order/{order_id}")
async def track_order(order_id: str):
    return {
        "order_id": order_id,
        "status": "out_for_delivery",
        "estimated_arrival": "10-15 minutes"
    }

@app.post("/reload_mock_orders")
async def reload_mock_orders():
    global MOCK_ORDERS
    seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
    if os.path.exists(seed_file):
        try:
            with open(seed_file) as f:
                MOCK_ORDERS = json.load(f)
            print(f"Mock server reloaded {len(MOCK_ORDERS)} orders")
            return {"success": True, "loaded_orders": len(MOCK_ORDERS)}
        except Exception as e:
            return {"success": False, "error": f"Failed to parse json: {e}"}
    return {"success": False, "error": "Seed file not found"}
