# Instamart Intelligence — Implementation Plan
## With model recommendations for every task

---

## MODEL LEGEND

| Tag | Model | Use it for |
|-----|-------|------------|
| 🟣 OPUS | Claude Opus | Complex agent graphs, high-stakes writing |
| 🟢 SONNET | Claude Sonnet | Everyday coding workhorse (80% of tasks) |
| 🟡 FLASH | Gemini 3 Flash | Boilerplate, config, quick fixes |
| 🔴 GPH | Gemini 3.1 Pro High | ML code, debugging, reading full codebase |
| ⚫ GPL | Gemini 3.1 Pro Low | Medium logic, data viz, second opinion |

**Core rule:** Opus only 3 times total (restock agent, recipe agent, pitch application). GPH for anything ML or debugging. Sonnet for everything else with real logic. Flash for anything you could copy-paste from docs.

---

---

# PRE-WEEK: SETUP
## 2-3 hours — do this before writing any application code

---

### Task 0.1 — Folder Structure 🟡 FLASH

Create the full directory tree first. Empty folders are fine.

```bash
mkdir instamart-intelligence && cd instamart-intelligence

mkdir -p backend/{database/migrations,mcp,ml,agents,api/routes,notifications,seed,tests}
mkdir -p frontend/{app/{household,predictions,recipes,price-alerts},components,lib}

touch backend/main.py backend/config.py
touch .env.example docker-compose.yml README.md
```

**Done when:** `tree instamart-intelligence` shows all folders cleanly.

---

### Task 0.2 — Docker Compose for TimescaleDB 🟡 FLASH

```yaml
# docker-compose.yml
version: '3.8'
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: instamart_db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: instamart_intelligence
    volumes:
      - timescale_data:/var/lib/postgresql/data
volumes:
  timescale_data:
```

```bash
docker-compose up -d
docker ps   # verify container is running

psql -h localhost -U postgres -d instamart_intelligence   # verify connection
```

**Done when:** psql connects successfully.

---

### Task 0.3 — Python Dependencies 🟡 FLASH

```bash
python -m venv venv
source venv/bin/activate

pip install fastapi==0.110.0 \
    uvicorn[standard]==0.27.0 \
    sqlalchemy[asyncio]==2.0.28 \
    asyncpg==0.29.0 \
    alembic==1.13.1 \
    prophet==1.1.5 \
    pandas==2.2.0 \
    numpy==1.26.4 \
    scikit-learn==1.4.0 \
    langgraph==0.0.62 \
    langchain-anthropic==0.1.6 \
    anthropic==0.21.0 \
    twilio==8.13.0 \
    apscheduler==3.10.4 \
    pgvector==0.2.5 \
    python-dotenv==1.0.1 \
    httpx==0.26.0 \
    pydantic==2.6.3

pip freeze > requirements.txt
```

**Verify:** `python -c "import prophet, langgraph, anthropic"` runs without errors.

---

### Task 0.4 — Environment Variables 🟡 FLASH

```bash
# .env.example (commit this to git)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/instamart_intelligence
MCP_BASE_URL=http://localhost:3001
ANTHROPIC_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=+14155238886

# Copy and fill in real values
cp .env.example .env

# Never commit .env
echo ".env" >> .gitignore
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
```

---

### Task 0.5 — Git Init 🟡 FLASH

```bash
git init
git add .
git commit -m "Project structure and environment setup"
# Push to GitHub now — proves you started (useful for Swiggy application)
```

**End of pre-week:** You have a repo, a running database, and a working Python environment. Nothing else.

---

---

# WEEK 1: DATA PIPELINE
## Goal: Order history flowing into DB → Consumption models building

---

## DAY 1 (Monday)

---

### Task 1.1 — Database Schema 🟢 SONNET

Ask Sonnet to write all SQLAlchemy models in one go. Give it the full schema from the project docs as context.

```python
# backend/database/models.py

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid

class Base(DeclarativeBase):
    pass

class Household(Base):
    __tablename__ = "households"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(20))
    composition = Column(String(50))           # solo, couple, family_small, family_large
    composition_confidence = Column(Float)
    intelligence_consent = Column(Boolean, default=False)
    notifications_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True))

class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"))
    instamart_order_id = Column(String(255), unique=True)
    placed_at = Column(DateTime(timezone=True), nullable=False)
    total_amount = Column(Float)
    raw_data = Column(JSONB)

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    item_id = Column(String(255), nullable=False)
    item_name = Column(String(500), nullable=False)
    category = Column(String(100))
    quantity = Column(Integer)
    unit = Column(String(50))
    standard_quantity = Column(Float)
    price = Column(Float)

class ConsumptionModel(Base):
    __tablename__ = "consumption_models"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"))
    item_id = Column(String(255))
    item_name = Column(String(500))
    category = Column(String(100))
    avg_daily_consumption = Column(Float)
    consumption_cycle_days = Column(Float)
    last_purchase_date = Column(DateTime(timezone=True))
    last_purchase_quantity = Column(Float)
    estimated_depletion_date = Column(DateTime(timezone=True))
    confidence_score = Column(Float)
    data_points = Column(Integer)
    updated_at = Column(DateTime(timezone=True))

class RestockAlert(Base):
    __tablename__ = "restock_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"))
    item_ids = Column(JSONB)
    message_sent = Column(String)
    sent_at = Column(DateTime(timezone=True))
    status = Column(String(50), default='pending')
    acted_at = Column(DateTime(timezone=True))
    order_id_placed = Column(String(255))

class PriceHistory(Base):
    __tablename__ = "price_history"
    item_id = Column(String(255), primary_key=True)
    item_name = Column(String(500))
    recorded_at = Column(DateTime(timezone=True), primary_key=True)
    price = Column(Float)
    price_per_unit = Column(Float)

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"))
    name = Column(String(500))
    servings = Column(Integer)
    ingredients = Column(JSONB)
    cuisine = Column(String(100))
    pinned_for = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
```

**After writing models, run Alembic:**
```bash
cd backend
alembic init migrations
# Edit alembic.ini → set sqlalchemy.url to your DATABASE_URL
# Edit migrations/env.py → import Base and all models
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# Enable TimescaleDB hypertable for price_history
psql -h localhost -U postgres -d instamart_intelligence \
  -c "SELECT create_hypertable('price_history', 'recorded_at', if_not_exists => TRUE);"

# Enable pgvector
psql -h localhost -U postgres -d instamart_intelligence \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Done when:** `alembic current` shows latest revision. All tables exist in DB.

---

### Task 1.2 — Database Connection Setup 🟢 SONNET

```python
# backend/database/connection.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    from backend.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

### Task 1.3 — Config Module 🟡 FLASH

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    MCP_BASE_URL: str = "http://localhost:3001"
    ANTHROPIC_API_KEY: str
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    ALERT_THRESHOLD_DAYS: int = 2
    MIN_CONFIDENCE: float = 0.50

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## DAY 1 (Monday) — continued

### Task 1.4 — Mock MCP Server 🟢 SONNET

This runs on port 3001 and pretends to be Swiggy's real API. You'll swap it for the real MCP when Swiggy grants production access.

```python
# backend/mcp/mock_server.py
from fastapi import FastAPI
from pydantic import BaseModel
import json, os, uuid, random
from datetime import datetime

app = FastAPI(title="Mock Swiggy Instamart MCP")

MOCK_ORDERS = []
MOCK_CART = {"items": [], "cart_id": None}

@app.on_event("startup")
async def load_seed_data():
    global MOCK_ORDERS
    seed_file = "backend/seed/generated_orders.json"
    if os.path.exists(seed_file):
        with open(seed_file) as f:
            MOCK_ORDERS = json.load(f)
        print(f"Loaded {len(MOCK_ORDERS)} mock orders")

@app.get("/get_instamart_orders")
async def get_orders(user_id: str = "demo_user_001", limit: int = 100):
    return {"success": True, "user_id": user_id,
            "total_orders": len(MOCK_ORDERS), "orders": MOCK_ORDERS[-limit:]}

@app.post("/search_instamart_items")
async def search_items(body: dict):
    query = body.get("query", "").lower()
    MOCK_CATALOG = [
        {"id": "INS_001", "name": "Amul Taza Milk 1L", "price": 28, "price_per_unit": 28, "unit": "L", "category": "dairy"},
        {"id": "INS_002", "name": "Aashirvaad Atta 5kg", "price": 198, "price_per_unit": 39.6, "unit": "kg", "category": "staples"},
        {"id": "INS_003", "name": "Fortune Sunflower Oil 1L", "price": 127, "price_per_unit": 127, "unit": "L", "category": "staples"},
        {"id": "INS_004", "name": "India Gate Basmati Rice 5kg", "price": 310, "price_per_unit": 62, "unit": "kg", "category": "staples"},
        {"id": "INS_005", "name": "Nandini Eggs Pack of 12", "price": 84, "price_per_unit": 7, "unit": "piece", "category": "protein"},
        {"id": "INS_006", "name": "Tomatoes 500g", "price": 29, "price_per_unit": 58, "unit": "kg", "category": "vegetables"},
        {"id": "INS_007", "name": "Onions 1kg", "price": 42, "price_per_unit": 42, "unit": "kg", "category": "vegetables"},
        {"id": "INS_008", "name": "Amul Butter 500g", "price": 270, "price_per_unit": 540, "unit": "kg", "category": "dairy"},
        {"id": "INS_009", "name": "Amul Fresh Cream 200ml", "price": 55, "price_per_unit": 275, "unit": "L", "category": "dairy"},
        {"id": "INS_010", "name": "Tata Salt 1kg", "price": 28, "price_per_unit": 28, "unit": "kg", "category": "staples"},
    ]
    results = [i for i in MOCK_CATALOG if query in i["name"].lower() or query in i["category"]]
    return {"items": results if results else MOCK_CATALOG[:3]}

class CartUpdate(BaseModel):
    items: list

@app.post("/update_instamart_cart")
async def update_cart(body: CartUpdate):
    MOCK_CART["cart_id"] = f"CART_{str(uuid.uuid4())[:8]}"
    MOCK_CART["items"] = body.items
    total = sum(i.get("price", 50) * i.get("quantity", 1) for i in body.items)
    return {"success": True, "cart_id": MOCK_CART["cart_id"], "items": body.items, "total": total}

@app.get("/get_instamart_cart")
async def get_cart():
    return {"success": True, **MOCK_CART}

class PlaceOrder(BaseModel):
    cart_id: str

@app.post("/place_instamart_order")
async def place_order(body: PlaceOrder):
    order_id = f"INS_{random.randint(10000, 99999)}"
    return {"success": True, "order_id": order_id, "status": "placed",
            "estimated_delivery_minutes": random.randint(12, 20),
            "placed_at": datetime.now().isoformat()}

@app.get("/track_instamart_order/{order_id}")
async def track_order(order_id: str):
    return {"order_id": order_id, "status": "out_for_delivery", "eta": "10-15 minutes"}
```

Run: `uvicorn backend.mcp.mock_server:app --port 3001 --reload`

**Done when:** `curl http://localhost:3001/get_instamart_orders` returns JSON.

---

## DAY 2 (Tuesday)

### Task 1.5 — Seed Data Generator 🟢 SONNET

> This is the most important non-ML task. Give Sonnet the full HOUSEHOLD_ITEMS dict and ask it to produce a generator with: weekly order clustering, ±15% quantity noise, a 10-day travel gap at day 45, a 3x milk spike at day 75, and realistic Sunday/evening ordering preference.

```python
# backend/seed/generate_orders.py
"""
Run: python -m backend.seed.generate_orders
Generates 4 months of realistic Indian household order history.
"""
import json, random
from datetime import datetime, timedelta

HOUSEHOLD_ITEMS = {
    "INS_001": {"name": "Amul Taza Milk 1L", "category": "dairy",
                "unit": "L", "pack_size": 1.0, "family_daily_use": 1.0, "base_price": 28},
    "INS_002": {"name": "Aashirvaad Atta 5kg", "category": "staples",
                "unit": "kg", "pack_size": 5.0, "family_daily_use": 0.30, "base_price": 198},
    "INS_003": {"name": "Fortune Sunflower Oil 1L", "category": "staples",
                "unit": "L", "pack_size": 1.0, "family_daily_use": 0.068, "base_price": 127},
    "INS_004": {"name": "India Gate Basmati Rice 5kg", "category": "staples",
                "unit": "kg", "pack_size": 5.0, "family_daily_use": 0.25, "base_price": 310},
    "INS_005": {"name": "Nandini Eggs Pack of 12", "category": "protein",
                "unit": "piece", "pack_size": 12.0, "family_daily_use": 2.5, "base_price": 84},
    "INS_006": {"name": "Tomatoes 500g", "category": "vegetables",
                "unit": "kg", "pack_size": 0.5, "family_daily_use": 0.15, "base_price": 20},
    "INS_007": {"name": "Onions 1kg", "category": "vegetables",
                "unit": "kg", "pack_size": 1.0, "family_daily_use": 0.10, "base_price": 35},
    "INS_008": {"name": "Amul Butter 500g", "category": "dairy",
                "unit": "kg", "pack_size": 0.5, "family_daily_use": 0.025, "base_price": 270},
    "INS_009": {"name": "Tata Salt 1kg", "category": "staples",
                "unit": "kg", "pack_size": 1.0, "family_daily_use": 0.008, "base_price": 28},
    "INS_010": {"name": "Britannia Bread Large", "category": "bakery",
                "unit": "piece", "pack_size": 1.0, "family_daily_use": 0.25, "base_price": 55},
}

def generate_realistic_orders(months=4):
    start = datetime.now() - timedelta(days=months * 30)
    end = datetime.now() - timedelta(days=1)
    travel_start = start + timedelta(days=45)
    travel_end = travel_start + timedelta(days=10)
    guest_date = start + timedelta(days=75)

    inventory = {iid: item["pack_size"] for iid, item in HOUSEHOLD_ITEMS.items()}
    pending = {}
    current = start

    while current < end:
        is_traveling = travel_start <= current <= travel_end
        for iid, item in HOUSEHOLD_ITEMS.items():
            daily = item["family_daily_use"]
            if abs((current - guest_date).days) < 2 and iid == "INS_001":
                daily *= 3.0
            if not is_traveling:
                inventory[iid] = max(0, inventory[iid] - daily * random.uniform(0.85, 1.15))
            if inventory[iid] <= daily * 2 and not is_traveling:
                delay = random.randint(0, 2)
                reorder_date = (current + timedelta(days=delay)).strftime("%Y-%m-%d")
                packs = max(1, round(item["pack_size"] * random.uniform(0.8, 1.2)))
                pending.setdefault(reorder_date, []).append({
                    "item_id": iid, "item_name": item["name"],
                    "quantity": packs, "standard_quantity": packs * item["pack_size"],
                    "unit": item["unit"], "category": item["category"],
                    "price": round(item["base_price"] * packs * random.uniform(0.95, 1.05), 2)
                })
                inventory[iid] += packs * item["pack_size"]
        current += timedelta(days=1)

    orders = []
    for i, date_str in enumerate(sorted(pending)):
        items = pending[date_str]
        hour = random.choice([9, 10, 11, 18, 19, 20, 21])
        orders.append({
            "order_id": f"INS_MOCK_{i+1:04d}", "user_id": "demo_user_001",
            "placed_at": f"{date_str}T{hour:02d}:{random.randint(0,59):02d}:00+05:30",
            "items": items, "total": round(sum(x["price"] for x in items), 2),
            "status": "delivered"
        })
    return orders

if __name__ == "__main__":
    orders = generate_realistic_orders(months=4)
    with open("backend/seed/generated_orders.json", "w") as f:
        json.dump(orders, f, indent=2)
    print(f"Generated {len(orders)} orders")
    print(f"Date range: {orders[0]['placed_at'][:10]} to {orders[-1]['placed_at'][:10]}")
```

Run: `python -m backend.seed.generate_orders`

**Done when:** `generated_orders.json` has 60-100 orders and spans 4 months.

---

## DAY 2-3 (Tue-Wed)

### Task 1.6 — Order Sync Service 🟢 SONNET

```python
# backend/api/routes/household.py
from fastapi import APIRouter
import httpx
from datetime import datetime

router = APIRouter(prefix="/api/household", tags=["household"])

async def sync_orders(household_id: str, user_id: str, db) -> int:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.MCP_BASE_URL}/get_instamart_orders",
            params={"user_id": user_id, "limit": 200}
        )
    data = resp.json()
    synced = 0
    for raw in data["orders"]:
        existing = await db.execute(
            "SELECT id FROM orders WHERE instamart_order_id = $1", raw["order_id"]
        )
        if existing.scalar():
            continue
        order_id = await db.execute("""
            INSERT INTO orders (household_id, instamart_order_id, placed_at, total_amount, raw_data)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, household_id, raw["order_id"],
            datetime.fromisoformat(raw["placed_at"]), raw["total"], raw)

        for item in raw["items"]:
            await db.execute("""
                INSERT INTO order_items
                  (order_id, item_id, item_name, category, quantity, unit, standard_quantity, price)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """, order_id, item["item_id"], item["item_name"], item.get("category"),
                item["quantity"], item.get("unit"), item.get("standard_quantity", item["quantity"]),
                item.get("price"))
        synced += 1
    return synced

@router.post("/{user_id}/sync")
async def sync_household_orders(user_id: str, db=Depends(get_db)):
    hh = await get_or_create_household(user_id, db)
    count = await sync_orders(str(hh["id"]), user_id, db)
    return {"message": f"Synced {count} new orders", "household_id": str(hh["id"])}
```

**Done when:** `POST /api/household/demo_user_001/sync` returns synced count.

---

## DAY 3-4 (Wed-Thu)

### Task 1.7 — Prophet Consumption Model Builder 🔴 GPH

> Use Gemini Pro (high thinking) for this. It involves time-series math, confidence calculation, and edge case handling. Give it the full task: "Build a Prophet-based consumption modeler. For each item, pull purchase history from the DB, fit Prophet, derive avg daily consumption, cycle days, depletion date, and a confidence score based on purchase regularity and data points."

```python
# backend/ml/consumption_model.py
from prophet import Prophet
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ConsumptionModeler:
    MIN_DATA_POINTS = 3
    MIN_CONFIDENCE = 0.30

    async def build_model_for_item(self, household_id: str, item_id: str,
                                    item_name: str, db) -> dict | None:
        purchases = await db.fetch_all("""
            SELECT oi.standard_quantity, o.placed_at
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
            WHERE o.household_id = $1 AND oi.item_id = $2
            ORDER BY o.placed_at ASC
        """, household_id, item_id)

        if len(purchases) < self.MIN_DATA_POINTS:
            return None

        df = pd.DataFrame({
            "ds": pd.to_datetime([p["placed_at"] for p in purchases]),
            "y":  [p["standard_quantity"] for p in purchases]
        })

        try:
            import logging as log
            log.getLogger('prophet').setLevel(log.WARNING)
            log.getLogger('cmdstanpy').setLevel(log.WARNING)
            model = Prophet(
                seasonality_mode='multiplicative',
                yearly_seasonality=False,
                weekly_seasonality=(len(purchases) >= 10),
                daily_seasonality=False,
                interval_width=0.80
            )
            model.fit(df)
        except Exception as e:
            logger.error(f"Prophet failed for {item_name}: {e}")
            return None

        total_qty = df["y"].sum()
        days_elapsed = max((df["ds"].max() - df["ds"].min()).days, 1)
        avg_daily = total_qty / days_elapsed

        time_diffs = df["ds"].diff().dt.days.dropna()
        cycle_days = float(time_diffs.mean())

        last = purchases[-1]
        last_date = last["placed_at"]
        last_qty  = last["standard_quantity"]
        depletion = last_date + timedelta(days=last_qty / avg_daily) if avg_daily > 0 else None

        cycle_std = float(time_diffs.std()) if len(time_diffs) > 1 else 30
        regularity = max(0, 1 - (cycle_std / 14))
        data_score = min(1.0, len(purchases) / 20)
        confidence = (regularity * 0.6) + (data_score * 0.4)

        if confidence < self.MIN_CONFIDENCE:
            return None

        return {
            "household_id": household_id, "item_id": item_id, "item_name": item_name,
            "avg_daily_consumption": round(avg_daily, 4),
            "consumption_cycle_days": round(cycle_days, 1),
            "last_purchase_date": last_date, "last_purchase_quantity": last_qty,
            "estimated_depletion_date": depletion,
            "confidence_score": round(confidence, 3),
            "data_points": len(purchases), "updated_at": datetime.now()
        }

    async def rebuild_all_models(self, household_id: str, db) -> dict:
        items = await db.fetch_all("""
            SELECT DISTINCT oi.item_id, oi.item_name, COUNT(*) as cnt
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
            WHERE o.household_id = $1
            GROUP BY oi.item_id, oi.item_name
            HAVING COUNT(*) >= 3
            ORDER BY cnt DESC
        """, household_id)

        results = {"built": 0, "skipped": 0, "errors": 0}
        for item in items:
            try:
                data = await self.build_model_for_item(
                    household_id, item["item_id"], item["item_name"], db
                )
                if data:
                    await db.execute("""
                        INSERT INTO consumption_models
                          (household_id, item_id, item_name, avg_daily_consumption,
                           consumption_cycle_days, last_purchase_date, last_purchase_quantity,
                           estimated_depletion_date, confidence_score, data_points, updated_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                        ON CONFLICT (household_id, item_id) DO UPDATE SET
                          avg_daily_consumption = EXCLUDED.avg_daily_consumption,
                          confidence_score = EXCLUDED.confidence_score,
                          estimated_depletion_date = EXCLUDED.estimated_depletion_date,
                          updated_at = NOW()
                    """, *list(data.values()))
                    results["built"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                logger.error(f"Error building model for {item['item_name']}: {e}")
                results["errors"] += 1
        return results
```

**Done when:** `POST /api/household/demo_user_001/rebuild-models` returns `{"built": 8+, "errors": 0}` and `consumption_models` table has rows with `confidence_score > 0.5`.

---

## DAY 4-5 (Thu-Fri)

### Task 1.8 — FastAPI Main App 🟡 FLASH

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import household, predictions, restock, recipes
from backend.database.connection import init_db

app = FastAPI(title="Instamart Intelligence API", version="1.0.0")

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

app.include_router(household.router)
app.include_router(predictions.router)
app.include_router(restock.router)
app.include_router(recipes.router)

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
```

Run: `uvicorn backend.main:app --port 8000 --reload`

---

### Week 1 End — State Check

```bash
# Run these in order to verify everything works
curl -X POST http://localhost:8000/api/household/demo_user_001/sync
# Expected: {"message": "Synced 87 new orders", ...}

curl -X POST http://localhost:8000/api/household/demo_user_001/rebuild-models
# Expected: {"built": 8, "skipped": 2, "errors": 0}
```

**Week 1 checklist:**
- [ ] TimescaleDB running, all tables created
- [ ] Seed data generated (60-100 realistic orders)
- [ ] Mock MCP server on port 3001 returning seed data
- [ ] Order sync working (data flows MCP → DB)
- [ ] Consumption models built for 8+ items
- [ ] FastAPI on port 8000, `/health` returns 200

---

---

# WEEK 2: PREDICTION ENGINE
## Goal: Accurate forecasts + anomaly handling + alert triggers

---

## DAY 6 (Monday)

### Task 2.1 — Anomaly Detector 🔴 GPH

> Use Gemini Pro (high thinking) again. Three detection algorithms — travel gaps, guest spikes, dietary shifts — each with different logic. Ask it to write all three as a single class with clear docstrings, and to handle the edge cases: what if there are only 2 orders? What if gap is exactly 5 days?

```python
# backend/ml/anomaly_detector.py
from datetime import datetime
from collections import defaultdict

class AnomalyDetector:

    def detect_travel(self, order_dates: list[datetime]) -> dict:
        """Gaps of 5+ days between consecutive orders = likely travel."""
        if len(order_dates) < 2:
            return {"detected": False, "type": "travel"}
        sorted_dates = sorted(order_dates)
        gaps = []
        for i in range(1, len(sorted_dates)):
            gap = (sorted_dates[i] - sorted_dates[i-1]).days
            if gap >= 5:
                gaps.append({"start": sorted_dates[i-1], "end": sorted_dates[i], "duration_days": gap})
        if not gaps:
            return {"detected": False, "type": "travel"}
        return {"detected": True, "type": "travel", "gaps": gaps,
                "total_travel_days": sum(g["duration_days"] for g in gaps)}

    def detect_guest_visit(self, purchase_history: list, baseline_qty: float) -> dict:
        """Single order quantity >2.5x baseline = guests visited. Exclude from model."""
        spikes = []
        for p in purchase_history:
            ratio = p["standard_quantity"] / max(baseline_qty, 0.001)
            if ratio >= 2.5:
                spikes.append({"date": p["placed_at"], "quantity": p["standard_quantity"],
                               "spike_factor": round(ratio, 1)})
        if spikes:
            return {"detected": True, "type": "guest_visit",
                    "events": spikes, "action": "exclude_from_model"}
        return {"detected": False, "type": "guest_visit"}

    def detect_dietary_change(self, category_monthly_counts: dict) -> dict:
        """Category purchase count drops >60% in most recent month vs prior average."""
        changes = []
        for cat, counts in category_monthly_counts.items():
            if len(counts) < 3:
                continue
            prior_avg = sum(counts[:-1]) / len(counts[:-1])
            recent = counts[-1]
            if prior_avg == 0:
                continue
            drop_pct = ((prior_avg - recent) / prior_avg) * 100
            if drop_pct > 60:
                changes.append({"category": cat, "drop_pct": round(drop_pct, 1),
                                 "prior_avg": round(prior_avg, 1), "recent": recent})
        return {"detected": bool(changes), "type": "dietary_change",
                "changes": changes, "action": "confirm_with_user" if changes else None}
```

---

## DAY 7 (Tuesday)

### Task 2.2 — Confidence Scorer 🟢 SONNET

> Straight implementation of the formula: regularity score × 0.6 + data score × 0.4. Simple enough for Sonnet.

```python
# backend/ml/confidence_scorer.py
import pandas as pd

class ConfidenceScorer:

    def score(self, purchase_dates: list, data_points: int) -> float:
        if data_points < 3:
            return 0.0
        dates = pd.to_datetime(sorted(purchase_dates))
        diffs = dates.diff().dt.days.dropna()
        if len(diffs) < 2:
            return 0.3
        std = float(diffs.std())
        regularity = max(0.0, 1.0 - (std / 14.0))
        data_score = min(1.0, data_points / 20.0)
        return round((regularity * 0.6) + (data_score * 0.4), 3)

    def human_readable(self, score: float) -> str:
        if score >= 0.80: return "Very high"
        if score >= 0.65: return "High"
        if score >= 0.50: return "Moderate"
        if score >= 0.30: return "Low"
        return "Insufficient data"
```

---

### Task 2.3 — Alert Trigger Logic 🟢 SONNET

```python
# backend/api/routes/restock.py
from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/api/restock", tags=["restock"])

async def check_depletions_for_household(household_id: str, db) -> list:
    """Items with confidence >= 50% depleting within ALERT_THRESHOLD_DAYS."""
    depleting = await db.fetch_all("""
        SELECT cm.*,
               EXTRACT(EPOCH FROM (cm.estimated_depletion_date - NOW()))/86400 as days_remaining
        FROM consumption_models cm
        WHERE cm.household_id = $1
          AND cm.confidence_score >= $2
          AND cm.estimated_depletion_date IS NOT NULL
          AND cm.estimated_depletion_date BETWEEN NOW()
              AND NOW() + INTERVAL '2 days'
        ORDER BY cm.estimated_depletion_date ASC
    """, household_id, settings.MIN_CONFIDENCE)

    # Don't re-alert items alerted in last 24h
    recently = await db.fetch_all("""
        SELECT DISTINCT unnest(item_ids::text[]) as item_id
        FROM restock_alerts
        WHERE household_id = $1
          AND sent_at > NOW() - INTERVAL '24 hours'
          AND status IN ('sent', 'acted')
    """, household_id)

    recent_ids = {r["item_id"] for r in recently}
    return [d for d in depleting if d["item_id"] not in recent_ids]

@router.post("/check-now")
async def manual_check(household_id: str, db=Depends(get_db)):
    items = await check_depletions_for_household(household_id, db)
    if items:
        hh = await db.fetch_one("SELECT * FROM households WHERE id = $1", household_id)
        await send_depletion_alert(hh, items, db)
    return {"alerts_triggered": len(items), "items": [i["item_name"] for i in items]}
```

---

## DAY 7-8 (Tue-Wed)

### Task 2.4 — Household Profiler 🟢 SONNET

```python
# backend/ml/household_profiler.py

BENCHMARKS = {
    "solo":         {"INS_001": 0.25, "INS_002": 0.07, "INS_005": 0.70, "INS_003": 0.020},
    "couple":       {"INS_001": 0.50, "INS_002": 0.15, "INS_005": 1.50, "INS_003": 0.040},
    "family_small": {"INS_001": 1.00, "INS_002": 0.30, "INS_005": 2.50, "INS_003": 0.068},
    "family_large": {"INS_001": 2.00, "INS_002": 0.60, "INS_005": 5.00, "INS_003": 0.130},
}

DISPLAY = {
    "solo": "Solo (1 person)", "couple": "Couple (2 people)",
    "family_small": "Family (3-4 people)", "family_large": "Large Family (5+)"
}

async def infer_composition(household_id: str, db) -> dict:
    models = await db.fetch_all(
        "SELECT item_id, avg_daily_consumption FROM consumption_models WHERE household_id = $1",
        household_id
    )
    observed = {m["item_id"]: m["avg_daily_consumption"] for m in models}
    scores = {}
    for hh_type, bench in BENCHMARKS.items():
        parts = []
        for item_id, expected in bench.items():
            if item_id in observed and expected > 0:
                ratio = observed[item_id] / expected
                parts.append(max(0, 1 - abs(1 - ratio)))
        scores[hh_type] = sum(parts) / max(len(parts), 1)
    best = max(scores, key=scores.get)
    return {"composition": best, "display_name": DISPLAY[best],
            "confidence": round(scores[best], 2), "all_scores": scores}
```

---

## DAY 8-9 (Wed-Thu)

### Task 2.5 — LangGraph Restock Agent 🟣 OPUS

> **Use Claude Opus 4 here.** This is the most complex piece of code in the entire project. It's a stateful multi-turn agent with 5 nodes, conditional edges, Claude API calls, and MCP tool calls inside the graph. Opus reasons about all the state transitions correctly where Sonnet sometimes misses edge cases.
>
> Prompt Opus with: "Build a LangGraph StateGraph for a grocery restock agent. States: household_id, depleting_items, stage (alert/awaiting_reply/building_cart/done), user_message, confirmed_items, cart_id, cart_total, order_id, response_message. Nodes: generate_alert_message (call Claude API), parse_user_reply (handle YES/NO/partial with Claude), build_cart (call Instamart MCP search + update_cart), place_order (call MCP place_instamart_order). Wire conditional edges: parse_reply → build_cart if confirmed_items else done. build_cart → place_order if cart_id. Add full error handling."

```python
# backend/agents/restock_agent.py
from langgraph.graph import StateGraph, END
from anthropic import Anthropic
from typing import TypedDict, Optional
import httpx, json

anthropic = Anthropic()

class RestockState(TypedDict):
    household_id: str
    depleting_items: list
    stage: str
    user_message: Optional[str]
    confirmed_items: list
    cart_id: Optional[str]
    cart_total: Optional[float]
    order_id: Optional[str]
    response_message: str
    error: Optional[str]

async def generate_alert_message(state: RestockState) -> RestockState:
    items_text = "\n".join([
        f"- {i['item_name']}: {int(i['confidence_score']*100)}% likely low "
        f"({round(i.get('days_remaining', 1), 1)} days remaining)"
        for i in state["depleting_items"]
    ])
    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=300,
        messages=[{"role": "user", "content":
            f"You are a smart household assistant for Swiggy Instamart.\n\n"
            f"Items likely running low:\n{items_text}\n\n"
            f"Write a WhatsApp message under 80 words. List top 3 items with confidence %. "
            f"Be friendly but brief. Max 2 emojis. End with: "
            f"'Reply YES to reorder all, or tell me which ones.' "
            f"Mention this is based on their purchase pattern. Write ONLY the message."}]
    )
    state["response_message"] = response.content[0].text
    state["stage"] = "awaiting_reply"
    return state

async def parse_user_reply(state: RestockState) -> RestockState:
    msg = (state.get("user_message") or "").strip().upper()
    if msg in ["YES","Y","REORDER","ORDER ALL","OK","OKAY","YES PLEASE"]:
        state["confirmed_items"] = state["depleting_items"]
        state["stage"] = "building_cart"
        return state
    if msg in ["NO","NOPE","CANCEL","SKIP","NOT NOW","LATER"]:
        state["confirmed_items"] = []
        state["response_message"] = "Got it! I'll check again tomorrow. 👍"
        state["stage"] = "done"
        return state
    # Partial response — use Claude to parse
    items_list = "\n".join([f"- {i['item_name']}" for i in state["depleting_items"]])
    resp = anthropic.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=200,
        messages=[{"role": "user", "content":
            f"User was asked to reorder these items:\n{items_list}\n\n"
            f"Their reply: \"{state['user_message']}\"\n\n"
            f"Return a JSON array of item names they want. Empty array if none. "
            f"Full list if they said 'all'. ONLY the JSON array."}]
    )
    try:
        wanted = json.loads(resp.content[0].text)
        state["confirmed_items"] = [
            i for i in state["depleting_items"]
            if any(w.lower() in i["item_name"].lower() for w in wanted)
        ]
        state["stage"] = "building_cart" if state["confirmed_items"] else "done"
    except:
        state["response_message"] = "Sorry, I didn't catch that. Reply YES to reorder all, or NO to skip."
        state["stage"] = "awaiting_reply"
    return state

async def build_cart(state: RestockState) -> RestockState:
    if not state["confirmed_items"]:
        state["response_message"] = "Nothing to order — I'll check again tomorrow!"
        state["stage"] = "done"
        return state
    cart_items = []
    async with httpx.AsyncClient() as client:
        for item in state["confirmed_items"]:
            r = await client.post(f"{settings.MCP_BASE_URL}/search_instamart_items",
                                   json={"query": item["item_name"]})
            results = r.json().get("items", [])
            if results:
                m = results[0]
                cart_items.append({"item_id": m["id"], "item_name": m["name"],
                                   "quantity": 1, "price": m["price"]})
        cart = await client.post(f"{settings.MCP_BASE_URL}/update_instamart_cart",
                                  json={"items": cart_items})
        cdata = cart.json()
    state["cart_id"] = cdata["cart_id"]
    state["cart_total"] = cdata.get("total", 0)
    names = [i["item_name"] for i in cart_items]
    state["response_message"] = (
        f"Cart ready: {', '.join(names[:3])}{'...' if len(names) > 3 else ''}. "
        f"Total: ₹{state['cart_total']:.0f}. Reply CONFIRM to place order."
    )
    state["stage"] = "awaiting_confirm"
    return state

async def place_order(state: RestockState) -> RestockState:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{settings.MCP_BASE_URL}/place_instamart_order",
                               json={"cart_id": state["cart_id"]})
        data = r.json()
    if data.get("success"):
        state["order_id"] = data["order_id"]
        eta = data.get("estimated_delivery_minutes", 15)
        state["response_message"] = f"✅ Order placed! Arriving in ~{eta} mins. Order #{state['order_id']}"
    else:
        state["error"] = "Order placement failed"
        state["response_message"] = "⚠️ Couldn't place order. Please try directly on Instamart."
    state["stage"] = "done"
    return state

# Build the graph
graph = StateGraph(RestockState)
graph.add_node("generate_alert", generate_alert_message)
graph.add_node("parse_reply", parse_user_reply)
graph.add_node("build_cart", build_cart)
graph.add_node("place_order", place_order)

graph.set_entry_point("generate_alert")
graph.add_edge("generate_alert", END)
graph.add_edge("parse_reply", "build_cart")
graph.add_conditional_edges("build_cart",
    lambda s: "place_order" if s.get("cart_id") else END)
graph.add_edge("place_order", END)

restock_agent = graph.compile()
```

**Done when:** You can call `restock_agent.ainvoke({...})` with test data and it returns a natural WhatsApp message.

---

## DAY 9-10 (Thu-Fri)

### Task 2.6 — Scheduler Setup 🟡 FLASH

```python
# backend/notifications/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(daily_depletion_check_all, 'cron', hour=8, minute=0)
    scheduler.add_job(track_commodity_prices,    'cron', hour=7, minute=0)
    scheduler.add_job(rebuild_all_models_job,    'cron', day_of_week='sun', hour=2)
    scheduler.start()
```

---

### Task 2.7 — Week 2 Integration Test 🔴 GPH

> If anything is broken or the predictions look wrong, paste your full `consumption_model.py` and `anomaly_detector.py` to Gemini Pro High and ask it to debug. Its long context window handles reading both files plus your DB output simultaneously.

```bash
curl http://localhost:8000/api/predictions/demo_user_001
# Should return 5+ items with days_remaining and confidence_score

curl -X POST "http://localhost:8000/api/restock/check-now?household_id=demo_user_001"
# Should show which items triggered alerts
```

**Week 2 checklist:**
- [ ] Predictions endpoint returning real data with varied confidence scores
- [ ] Anomaly detector correctly identifying the travel gap in seed data
- [ ] Household profiler returning "family_small" for demo data
- [ ] LangGraph agent generating a natural-sounding message
- [ ] Scheduler running without errors

---

---

# WEEK 3: INTERFACE & NOTIFICATIONS
## Goal: WhatsApp working end-to-end + Next.js dashboard live

---

## DAY 11-12 (Mon-Tue)

### Task 3.1 — Twilio WhatsApp Setup 🟡 FLASH

Setup steps (no code needed, just config):
1. Sign up at twilio.com — free $15 credit
2. Messaging → Try it out → Send a WhatsApp message
3. Follow sandbox setup: send "join [word]" from your WhatsApp to +1-415-523-8886
4. Save your `ACCOUNT_SID` and `AUTH_TOKEN` in `.env`
5. Install ngrok: `ngrok http 8000` → copy the `https://xxxx.ngrok.io` URL

---

### Task 3.2 — WhatsApp Webhook 🟢 SONNET

```python
# backend/notifications/whatsapp.py
from fastapi import APIRouter, Form, Response
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os

router = APIRouter(prefix="/webhook", tags=["webhooks"])
twilio = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
FROM = f"whatsapp:{os.getenv('TWILIO_WHATSAPP_FROM')}"

async def send_whatsapp(to: str, message: str):
    twilio.messages.create(from_=FROM, body=message, to=f"whatsapp:{to}")

@router.post("/whatsapp")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    phone = From.replace("whatsapp:", "")
    hh = await db.fetch_one("SELECT * FROM households WHERE phone_number = $1", phone)

    if not hh:
        r = MessagingResponse()
        r.message("Hi! Please set up your account at the Instamart Intelligence app first.")
        return Response(content=str(r), media_type="application/xml")

    if Body.strip().upper() == "STOP":
        await db.execute(
            "UPDATE households SET notifications_enabled = FALSE WHERE id = $1", hh["id"]
        )
        r = MessagingResponse()
        r.message("Unsubscribed from alerts. Reply START to re-enable.")
        return Response(content=str(r), media_type="application/xml")

    pending = await db.fetch_one("""
        SELECT * FROM restock_alerts WHERE household_id = $1
        AND status = 'sent' ORDER BY sent_at DESC LIMIT 1
    """, hh["id"])

    depleting = await get_items_from_alert(pending) if pending else []
    result = await restock_agent.ainvoke({
        "household_id": str(hh["id"]), "depleting_items": depleting,
        "stage": "parse_reply", "user_message": Body,
        "confirmed_items": [], "response_message": ""
    })

    if result.get("order_id") and pending:
        await db.execute(
            "UPDATE restock_alerts SET status='acted', acted_at=NOW(), order_id_placed=$1 WHERE id=$2",
            result["order_id"], pending["id"]
        )

    r = MessagingResponse()
    r.message(result["response_message"])
    return Response(content=str(r), media_type="application/xml")
```

In Twilio dashboard → Sandbox settings → set Webhook URL to: `https://xxxx.ngrok.io/webhook/whatsapp`

**Done when:** Sending "YES" to your sandbox number triggers a cart build and order confirmation.

---

## DAY 12-14 (Tue-Thu)

### Task 3.3 — Next.js Init 🟡 FLASH

```bash
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend
npm install recharts lucide-react axios date-fns
```

---

### Task 3.4 — Dashboard Depletion Cards 🟢 SONNET

> Give Sonnet a clear component spec: card shows item name, days remaining (big number), confidence bar (0-100%), urgency color (red <1 day, orange <3 days, green 3+), and a one-tap reorder button. Use Tailwind.

```tsx
// frontend/components/DepletionCard.tsx
interface DepletionCardProps {
  itemName: string
  daysRemaining: number
  confidence: number
  category: string
  onReorder: () => void
}

export function DepletionCard({ itemName, daysRemaining, confidence, onReorder }: DepletionCardProps) {
  const urgency = daysRemaining <= 1 ? 'border-red-500 bg-red-50'
                : daysRemaining <= 3 ? 'border-orange-400 bg-orange-50'
                : 'border-green-400 bg-green-50'

  return (
    <div className={`rounded-xl border-l-4 p-4 ${urgency}`}>
      <h3 className="font-medium text-gray-900 text-sm">{itemName}</h3>
      <div className="mt-2 flex items-end gap-1">
        <span className="text-4xl font-light text-gray-800">{Math.max(0, Math.round(daysRemaining))}</span>
        <span className="text-sm text-gray-500 mb-1">days left</span>
      </div>
      <div className="mt-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Confidence</span>
          <span>{Math.round(confidence * 100)}%</span>
        </div>
        <div className="h-1.5 bg-gray-200 rounded-full">
          <div className="h-1.5 bg-gray-600 rounded-full" style={{width: `${confidence * 100}%`}} />
        </div>
      </div>
      <button onClick={onReorder}
        className="mt-3 w-full text-sm py-1.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors">
        Reorder →
      </button>
    </div>
  )
}
```

---

### Task 3.5 — Price Chart Component ⚫ GPL

> Use Gemini Pro Low for data visualization code. Give it: "Build a Recharts LineChart for commodity price history. X-axis is date, Y-axis is price per unit. Show a dashed red line for the 30-day average. Highlight the last 7 days if price is >30% above average."

---

### Task 3.6 — All FastAPI Prediction Endpoints 🟢 SONNET

```python
# backend/api/routes/predictions.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

@router.get("/{household_id}")
async def get_predictions(household_id: str, db=Depends(get_db)):
    models = await db.fetch_all("""
        SELECT *,
            EXTRACT(EPOCH FROM (estimated_depletion_date - NOW()))/86400 as days_remaining
        FROM consumption_models
        WHERE household_id = $1 AND confidence_score >= 0.4
        ORDER BY estimated_depletion_date ASC NULLS LAST
    """, household_id)

    hh = await db.fetch_one("SELECT * FROM households WHERE id = $1", household_id)
    total_models = len(models)

    critical  = [m for m in models if m["days_remaining"] and m["days_remaining"] <= 1]
    soon      = [m for m in models if m["days_remaining"] and 1 < m["days_remaining"] <= 3]
    upcoming  = [m for m in models if m["days_remaining"] and 3 < m["days_remaining"] <= 7]

    return {
        "household": {
            "id": str(hh["id"]), "composition": hh["composition"],
            "items_modeled": total_models
        },
        "summary": {"critical": len(critical), "soon": len(soon), "upcoming": len(upcoming)},
        "depleting_soon": [dict(m) for m in (critical + soon + upcoming)[:10]],
        "all_models": [dict(m) for m in models]
    }
```

---

### Task 3.7 — Dashboard Pages 🟢 SONNET

Build four pages in this order:
1. `/` — Home: household profile card + depletion cards sorted by urgency
2. `/predictions` — Full timeline: all items, confidence bars, historical accuracy table
3. `/recipes` — Recipe search input, pantry check results, missing items cart
4. `/price-alerts` — Commodity charts, spike/dip alerts, substitution suggestions

> Prompt Sonnet with the page layout description + the API response shape. Ask it to build the full page including the fetch call, loading state, and error state.

---

### Task 3.8 — CSS Polish 🟡 FLASH

Any Tailwind tweaks, spacing fixes, color adjustments. Use Flash for quick iteration here.

---

### Week 3 End — State Check

```bash
# Full end-to-end flow
# 1. Send a WhatsApp to your Twilio sandbox number
# 2. Reply YES
# 3. Expect cart confirmation back in WhatsApp
# 4. Open http://localhost:3000 — should show real depletion cards
```

**Week 3 checklist:**
- [ ] WhatsApp webhook receiving messages and replying
- [ ] YES → cart build → order placed → confirmation message sent
- [ ] Dashboard home showing depletion cards with real data
- [ ] All 4 pages rendering without errors
- [ ] API endpoints returning correct data for all dashboard pages

---

---

# WEEK 4: RECIPE + PRICE + DEMO
## Goal: All features complete, demo data perfect, video recorded, application submitted

---

## DAY 15-16 (Mon-Tue)

### Task 4.1 — Recipe LangGraph Agent 🟣 OPUS

> **Use Opus again.** Same reasoning as the restock agent — it's a stateful multi-turn flow. Nodes: parse_recipe_ingredients (Claude API call, JSON output), check_pantry_state (DB query against consumption_models), identify_missing (comparison logic), search_items (MCP calls), build_missing_cart (MCP update_cart). Opus handles the multi-step state correctly.
>
> Prompt: "Build a LangGraph agent that takes a recipe name and servings as input. Step 1: Call Claude API to parse all ingredients as structured JSON (name, quantity, unit). Step 2: Query consumption_models to estimate pantry state. Step 3: Compare ingredients vs pantry, identify what's missing. Step 4: Search Instamart MCP for each missing item. Step 5: Build a cart with missing items. Return both have_items and need_items lists."

```python
# backend/agents/recipe_agent.py
# (Full implementation — have Opus write it based on the prompt above)
# Key function signature:

async def recipe_to_cart(recipe_name: str, servings: int, household_id: str) -> dict:
    """
    Returns:
    {
        "recipe": str,
        "servings": int,
        "you_have": [{"name": str, "quantity": num, "unit": str}],
        "you_need": [{"name": str, "quantity": num, "unit": str}],
        "cart_items": [...],
        "estimated_cost": float,
        "ready_to_cook": bool
    }
    """
```

---

### Task 4.2 — Claude API Recipe Ingredient Parser 🟢 SONNET

This is the prompt engineering inside the recipe agent — the Claude API call that extracts ingredients. Sonnet is good enough for prompt tuning.

```python
response = anthropic.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    messages=[{"role": "user", "content":
        f"""List all ingredients for "{recipe_name}" for {servings} people.
Use standard Indian grocery app names (e.g. "basmati rice" not "long-grain rice").

Return ONLY a JSON array, no other text:
[{{"name": "basmati rice", "quantity": 400, "unit": "g", "optional": false}}]

Units must be: g, kg, ml, L, piece, tbsp, tsp"""}]
)
ingredients = json.loads(response.content[0].text)
```

Test on: dal makhani, biryani, palak paneer, chhole, aloo paratha. Fix prompt if JSON parsing fails.

---

### Task 4.3 — Pantry State Estimator ⚫ GPL

> Use Gemini Pro Low for this — it's a calculation problem, not a reasoning problem.
>
> Prompt: "Given a list of consumption_model rows (item_name, last_purchase_date, last_purchase_quantity, avg_daily_consumption), write a function that returns estimated remaining quantity per item as of right now. Handle the case where estimated_remaining < 0 (return 0). Also write a fuzzy matching function that takes an ingredient name and matches it to the closest pantry item name."

---

## DAY 16-17 (Tue-Wed)

### Task 4.4 — Recipe API Endpoint 🟢 SONNET

```python
# backend/api/routes/recipes.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

@router.post("/parse")
async def parse_recipe(body: dict, db=Depends(get_db)):
    recipe_name   = body["recipe"]
    servings      = body.get("servings", 4)
    household_id  = body["household_id"]
    result = await recipe_to_cart(recipe_name, servings, household_id)
    return result

@router.post("/pin")
async def pin_recipe(body: dict, db=Depends(get_db)):
    # Save recipe to DB with pinned_for date
    # Scheduler will check for missing ingredients 2 days before
    pass
```

---

### Task 4.5 — Commodity Price Tracker 🟢 SONNET

```python
# backend/agents/price_agent.py

VOLATILE_COMMODITIES = [
    ("INS_006", "tomatoes"), ("INS_007", "onions"),
    ("INS_003", "sunflower oil"), ("INS_002", "atta"),
    ("INS_004", "rice basmati"),
]

async def track_and_alert(db):
    for item_id, query in VOLATILE_COMMODITIES:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{settings.MCP_BASE_URL}/search_instamart_items",
                                   json={"query": query})
            items = r.json().get("items", [])
        if not items:
            continue

        current = items[0]["price_per_unit"]
        await db.execute(
            "INSERT INTO price_history (item_id, item_name, recorded_at, price_per_unit) VALUES ($1,$2,NOW(),$3)",
            item_id, items[0]["name"], current
        )

        avg = await db.fetch_val("""
            SELECT AVG(price_per_unit) FROM price_history
            WHERE item_id = $1 AND recorded_at > NOW() - INTERVAL '30 days'
        """, item_id)

        if avg:
            pct = ((current - avg) / avg) * 100
            if abs(pct) > 25:
                await notify_all_households_price_alert(
                    items[0]["name"],
                    "spike" if pct > 0 else "dip",
                    pct, current, avg, db
                )
```

---

## DAY 17-18 (Wed-Thu)

### Task 4.6 — Demo Seed Data (Make It Impressive) 🔴 GPH

> Use Gemini 3.1 Pro High for this. Paste your existing `generate_orders.py` and ask it to: "Modify the seed data generator so that: (1) Milk has exactly 2.1-day average cycle with ±0.3 days variance. (2) Oil has exactly 14.7-day cycle. (3) Last oil purchase was exactly 13 days ago so it shows as depleting NOW in the demo. (4) Add 30 days of price_history rows for tomatoes showing a clear spike in the last 7 days (+140%). (5) Make the travel gap span days 43-53 exactly so anomaly detection fires clearly. Return the full modified script."

Also run prediction accuracy verification:
```bash
python -m backend.tests.verify_prediction_accuracy
# Target: avg error < 2 days across all modeled items
```

### Task 4.7 — Final Integration Debugging 🔴 GPH

> If anything is broken across the full pipeline, paste ALL relevant files to Gemini 3.1 Pro High in one go. Its long context window handles reading your entire codebase simultaneously and spots the integration issues Sonnet misses when it only sees one file.

---

## DAY 19 (Friday)

### Task 4.8 — Demo Video Recording

Before recording, run this checklist:
```bash
# Restart all services fresh
docker-compose restart
uvicorn backend.mcp.mock_server:app --port 3001
uvicorn backend.main:app --port 8000

# Load fresh demo data
python -m backend.seed.generate_orders
python -m backend.seed.load_price_history   # separate script for tomato spike data

# Sync and rebuild
curl -X POST http://localhost:8000/api/household/demo_user_001/sync
curl -X POST http://localhost:8000/api/household/demo_user_001/rebuild-models

# Verify predictions look right
curl http://localhost:8000/api/predictions/demo_user_001
```

**Record in this order (3-4 minutes):**

| Scene | Duration | What to show |
|-------|----------|--------------|
| 1. The intelligence | 0:00–0:45 | Dashboard home: "4-person family · 34 items modeled". Household profile card. Scroll depletion timeline. |
| 2. The prediction | 0:45–1:30 | Click cooking oil card. Show "68ml/day, 87% confidence, depleting May 24." Show last 5 predictions vs actual dates — within ±1.2 days avg. |
| 3. The WhatsApp | 1:30–2:00 | Show phone. Receive alert message. Type YES. Order confirmation arrives. This is the money shot. |
| 4. Price intelligence | 2:00–2:30 | Show tomato price chart with spike. "Up 140% — prices fall in ~7 days based on pattern. Consider canned tomatoes." |
| 5. Recipe-to-cart | 2:30–3:15 | Type "Sunday biryani for 6". Watch ingredient parse. "You have: rice ✓, spices ✓. Need: cream, saffron — ₹180." Tap order. |
| 6. The moat | 3:15–3:30 | "Users with 90+ days of history: 0% churn. Switching to Blinkit means starting from zero." |

---

### Task 4.9 — Swiggy Builders Club Application 🟣 OPUS

> **Use Opus for this.** It's high-stakes persuasive writing. Give Opus: (1) the application framing tips from your project docs, (2) the full list of MCP APIs you used, (3) the business impact numbers, (4) your demo video link, (5) your GitHub link. Ask it to write the full application email in the format: Problem → Solution → MCP APIs used → Business Impact → Technical Proof → CTA.

**Application structure:**
```
Subject: Instamart Intelligence — Household AI to win the Blinkit war

1. The problem you solve (2-3 sentences on Blinkit competitive threat)
2. What you built (consumption modeling, depletion prediction, WhatsApp reorder)
3. Exact MCP API names used
4. Business impact in numbers (GMV, retention, churn)
5. Technical proof (link to GitHub + memory palace project)
6. CTA: "Built working localhost prototype — demo video attached"
```

---

### Task 4.10 — README + Docs 🟢 SONNET

```bash
# README should cover:
# - What the project is (2 sentences)
# - Architecture diagram (text-based is fine)
# - Setup instructions (copy from this doc)
# - How to run the demo
# - Week-by-week what was built
```

---

---

# QUICK REFERENCE

## Run all services

```bash
# Terminal 1
docker-compose up

# Terminal 2
uvicorn backend.mcp.mock_server:app --port 3001 --reload

# Terminal 3
uvicorn backend.main:app --port 8000 --reload

# Terminal 4
cd frontend && npm run dev

# Terminal 5 (for Twilio webhook)
ngrok http 8000
```

## Test the full pipeline

```bash
curl -X POST http://localhost:8000/api/household/demo_user_001/sync
curl -X POST http://localhost:8000/api/household/demo_user_001/rebuild-models
curl http://localhost:8000/api/predictions/demo_user_001
curl -X POST "http://localhost:8000/api/restock/check-now?household_id=demo_user_001"
curl -X POST "http://localhost:8000/api/recipes/parse" \
  -H "Content-Type: application/json" \
  -d '{"recipe":"dal makhani","servings":4,"household_id":"demo_user_001"}'
```

## Debug queries

```sql
-- Check consumption models
SELECT item_name, avg_daily_consumption, confidence_score,
       estimated_depletion_date,
       EXTRACT(EPOCH FROM (estimated_depletion_date - NOW()))/86400 as days_left
FROM consumption_models
WHERE household_id = (SELECT id FROM households WHERE user_id = 'demo_user_001')
ORDER BY estimated_depletion_date;

-- Check order frequency per item
SELECT item_name, COUNT(*) as orders
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN households h ON h.id = o.household_id
WHERE h.user_id = 'demo_user_001'
GROUP BY item_name ORDER BY orders DESC;
```

## Model usage summary

| # | Task | Model |
|---|------|-------|
| 1 | All folder/config/boilerplate | 🟡 Gemini 3 Flash |
| 2 | DB models, API routes, React components | 🟢 Claude Sonnet |
| 3 | Prophet ML model builder | 🔴 Gemini 3.1 Pro High |
| 4 | Anomaly detector | 🔴 Gemini 3.1 Pro High |
| 5 | **Restock LangGraph agent** | 🟣 **Claude Opus** |
| 6 | Confidence scorer, household profiler | 🟢 Claude Sonnet |
| 7 | WhatsApp webhook + Twilio | 🟢 Claude Sonnet |
| 8 | Price chart (Recharts) | ⚫ Gemini 3.1 Pro Low |
| 9 | Pantry state estimator | ⚫ Gemini 3.1 Pro Low |
| 10 | **Recipe LangGraph agent** | 🟣 **Claude Opus** |
| 11 | Recipe ingredient parser (prompt eng) | 🟢 Claude Sonnet |
| 12 | Price tracker + commodity alerts | 🟢 Claude Sonnet |
| 13 | Demo seed data (make numbers impressive) | 🔴 Gemini 3.1 Pro High |
| 14 | Full codebase debugging | 🔴 Gemini 3.1 Pro High |
| 15 | **Swiggy Builders Club application** | 🟣 **Claude Opus** |
| 16 | README + docs | 🟢 Claude Sonnet |
