from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json
import os
import uuid
import random
from backend.seed.catalog import CATALOG as MOCK_CATALOG

app = FastAPI(title="Mock Swiggy Instamart MCP")

# In-memory store for mock orders — loaded from seed data file
MOCK_ORDERS = []
MOCK_CART = {"items": [], "cart_id": None}

@app.on_event("startup")
async def load_seed_data():
    global MOCK_ORDERS
    seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
    if os.path.exists(seed_file):
        with open(seed_file) as f:
            MOCK_ORDERS = json.load(f)
        print(f"Loaded {len(MOCK_ORDERS)} mock orders")
    else:
        print(f"Seed file not found at {seed_file}. Please run generate_orders.py first.")

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
    results = [item for item in MOCK_CATALOG if query in item["name"].lower() or query in item.get("category", "").lower()]
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
    return {
        "success": True,
        "order_id": order_id,
        "cart_id": body.cart_id,
        "status": "placed",
        "estimated_delivery_minutes": random.randint(12, 20),
        "placed_at": datetime.now().isoformat()
    }

@app.get("/track_instamart_order/{order_id}")
async def track_order(order_id: str):
    return {
        "order_id": order_id,
        "status": "out_for_delivery",
        "estimated_arrival": "10-15 minutes"
    }
