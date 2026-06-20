# ARCHITECTURE.md — The Technical Blueprint

_This document is for HUMANS to read. The AI will only read this when explicitly commanded via `@ZOOM` or when investigating complex database/architecture tasks._

## 1. PROJECT OVERVIEW & BUSINESS LOGIC

### The Simple Version
Instamart Intelligence is an AI system that sits on top of Swiggy Instamart and watches how your household consumes groceries over time. It learns your patterns — how fast you go through milk, oil, atta, eggs — and sends you a WhatsApp message before you run out, asking if you want to reorder. One tap and it's done.

It's the difference between a grocery app and a grocery assistant.

### The Real-World Analogy
Imagine you had a full-time house manager — someone who lives with you, watches what leaves the kitchen shelf, and automatically handles restocking. Before your cooking oil runs out, they've already placed the Instamart order. Before you plan Sunday biryani, they've already checked what's in the pantry and added the missing ingredients to the cart.

That house manager is what this app pretends to be — except it's software that reads your Instamart order history instead of physically watching your shelves.

### Why Does This Matter for Swiggy?
**The existential problem:** Swiggy Instamart and Blinkit are identical products. Same 10-minute delivery. Same Amul milk. Same prices. Same interface. A user has zero reason to be loyal to either one — they open whichever app they remember first.

**The solution this project creates:** If Instamart has been learning your household's grocery patterns for 6 months, it knows things Blinkit cannot know:
- Your family uses 1L milk every 2.1 days.
- You buy 5kg atta every 17 days, not 16 or 18.
- You always buy eggs and bread together on Sunday mornings.
- Your oil consumption spikes in October-November (festive season cooking).
- You were away for 10 days in March (zero orders = travel detected).

If you switch to Blinkit, you lose all of that. You're starting from zero. That intelligence — that knowledge about your household — is the switching cost. That's Swiggy's moat against Blinkit. No other feature creates this kind of lock-in.

---

### The Five Core Features Explained

#### Consumption Modeling
**What it does in plain English:**
The system reads every Instamart order you've ever placed and builds a profile for each recurring item. It figures out: "This household buys 1L milk every 2.1 days on average. Sometimes 1.9 days, sometimes 2.4 days, but almost always within that range."

**How it works technically:**
- Pulls your complete order history from Swiggy's MCP (API).
- For each item that appears more than 3 times, it runs a time-series analysis using Facebook Prophet (an open-source forecasting library).
- Prophet handles weekly patterns (you buy more groceries on Sunday), seasonal patterns (more milk during festivals), and random noise.
- The output is a consumption model per item: average daily usage, typical purchase cycle, and a confidence score.

**Real example:**
```
Item: Fortune Sunflower Oil (1L)
Orders found: 14 purchases over 4 months
Average daily consumption: 68ml/day
Typical purchase cycle: 14.7 days
Last purchased: May 10 (1L bottle)
Estimated depletion: May 24-25
Confidence: 87%
```

**Why this is hard without AI:**
A human looking at 14 grocery orders would take 20 minutes to notice the pattern. The system does it for all 30-50 recurring items in your household in seconds, and updates the model every time you place a new order.

#### Predictive Restocking
**What it does in plain English:**
Once the system knows your consumption rates, it monitors all your items in the background. Two days before any item is predicted to run out, it sends you a WhatsApp message asking if you want to reorder. You reply YES. It builds the cart and places the order. You never open the app.

**How it works technically:**
- A background scheduler (APScheduler) runs every morning at 8am.
- It checks all consumption models for items where `estimated_depletion_date < NOW() + 2 days`.
- For matching items, it generates a friendly WhatsApp message using Claude API.
- The message is sent via Twilio's WhatsApp API.
- When you reply, a LangGraph agent parses your response and either places the order, modifies the cart, or dismisses the alert.
- The Swiggy Instamart MCP APIs handle the actual cart building and order placement.

**Real example WhatsApp flow:**
```
[8:02 AM from Instamart Intelligence]
🛒 Your household is likely running low on:

• Cooking oil (87% confident — last bought 14 days ago)
• Milk (76% confident — last bought 1.9 days ago)
• Atta (68% confident — last bought 16 days ago)

Reply YES to reorder all, or tell me which ones.

---

[You reply: "just the oil and milk"]

---

[Response within 10 seconds]
Got it! Adding Fortune Sunflower Oil 1L + Amul Milk 1L to cart.
Total: ₹158. Confirming order?

---

[You reply: yes]

---

✅ Order placed! Arriving in ~15 minutes. Order #INS_8821
```

**The anomaly handling:**
The system doesn't blindly predict — it watches for anomalies:
- **Travel detection**: No orders for 5+ days? You're probably traveling. Predictions are paused, not broken.
- **Guest spike**: You bought 3L milk instead of your usual 1L? Guests visited. This outlier is excluded from your baseline model so it doesn't inflate your daily average.
- **Dietary shift**: Your egg purchases dropped 80% over the last month? The system flags a possible dietary change and asks you to confirm before updating your model.

#### Recipe Intelligence
**What it does in plain English:**
You tell the app you're making Sunday biryani for 6. It figures out all the ingredients needed, cross-references against your estimated pantry (based on what you've bought and how fast you use it), and shows you exactly what's missing with a ready-to-order cart.

**How it works technically:**
- You type a recipe name (or paste one) into the app.
- Claude API parses the recipe and extracts all ingredients with quantities (e.g., "400g basmati rice, 300ml yogurt, 2 large onions, 1 tsp saffron...").
- The system checks your "estimated pantry state" — a calculated estimate of what you likely still have based on last purchase date and daily consumption rate.
- Items where your estimated remaining stock is less than what the recipe needs are flagged as "missing".
- Missing items are bundled into a single Instamart cart for one-tap ordering.

**Real example:**
```
Recipe: Dal Makhani for 4 people

Checking pantry...

You likely have:
✓ Black dal (urad) — ~300g estimated remaining
✓ Rajma — bought last week, ~200g left
✓ Butter — 100g pack bought 3 days ago
✓ Garlic, ginger, onions — staples stocked
✓ Cumin, coriander powder — bought in bulk 2 weeks ago

You probably need:
✗ Fresh cream (200ml) — not in recent orders
✗ Kasuri methi — not in recent orders
✗ Heavy cream or malai — not tracked

Missing ingredients cart: ₹120
[Order Missing Items →]
```

**Additional recipe features:**
- Pin recipes to specific dates ("Making biryani this Sunday") — system auto-schedules the missing ingredient check for 2 days before.
- Cuisine week planning: tell the system your weekly meal plan, it gives you a consolidated shopping list.
- Nutritional awareness: if your last 3 restock carts are dominated by processed food or packaged snacks, the system gently flags it.

#### Price Intelligence
**What it does in plain English:**
Certain groceries in India fluctuate wildly — tomatoes, onions, potatoes, cooking oil, atta. The app tracks the price of these volatile staples daily. When tomatoes suddenly cost 140% more than last month, it tells you. When prices dip, it tells you to stock up.

**How it works technically:**
- A daily price scraper calls Swiggy's `search_instamart_items` MCP for each volatile commodity.
- Prices are stored in TimescaleDB (a time-series database) — one row per item per day.
- Each day, the system calculates the current price vs the 30-day rolling average.
- If price > 30% above average: spike alert sent to household.
- If price > 20% below average: dip alert sent, suggesting stock-up.
- Substitution logic: during a tomato spike, the system suggests canned tomatoes or a recipe swap.

**Real example alerts:**
```
📈 Price Alert: Tomatoes
Current: ₹29/100g (+142% vs last month avg of ₹12)
This spike typically lasts 8-12 days based on past patterns.
Suggestion: Use canned tomatoes for this week's cooking,
or wait 7-8 days before restocking fresh.

---

📉 Price Dip: Fortune Sunflower Oil (1L)
Current: ₹98 (−23% vs 30-day avg of ₹127)
Good time to stock 2-3 bottles. Add to cart?
```

**Why this matters for Indian households specifically:**
India has extreme commodity price volatility driven by monsoon, harvest cycles, and supply chain shocks. Onions alone can go from ₹15/kg to ₹80/kg within 3 weeks. Most households absorb this silently. An app that warns you 1-2 days into a spike (before you naturally notice at the store) is genuinely useful.

#### Household Intelligence Profile
**What it does in plain English:**
Without you ever filling out a form, the system figures out what kind of household you are — solo, couple, family of 4, elderly couple — purely from your consumption patterns. It uses this to calibrate all its predictions.

**How it works technically:**
- Benchmarks for known household types are pre-defined (e.g., a family of 4 in India uses ~1L milk/day, ~300g atta/day, ~2-3 eggs/day).
- The system compares your observed consumption rates across multiple items to these benchmarks.
- Whichever benchmark profile your data most closely matches becomes your inferred household type.
- This inference is shown to you with a confidence score and you can correct it.

**Real example profile:**
```
Your Household Profile
━━━━━━━━━━━━━━━━━━━━━━
Inferred type: Family (3-4 members) — 84% confidence
Based on: Milk consumption (1.1L/day), Atta (280g/day), Eggs (2.3/day)

Tracked since: January 2025 (4 months)
Items modeled: 34 recurring items
Prediction accuracy (last 30 days): ±1.4 days avg error
Orders prevented from running out: 12

Anomalies recorded:
• Travel gap detected: March 15-24 (9 days)
• Guest visit detected: February 8 (3x milk spike)
```

### The Competitive Moat Explained
When you use regular Instamart, there's no switching cost. Every order is independent. Blinkit has your order history too. Neither app knows anything special about you.

When you use Instamart Intelligence for 3+ months, something changes:
- **Month 1:** The system has enough data to model your top 10 recurring items with ~60% confidence. Predictions are okay but not magical.
- **Month 3:** 30+ items modeled, 80%+ confidence on staples, anomalies detected and filtered, household composition accurate. The system is genuinely useful.
- **Month 6:** The system has seen you through one full seasonal cycle (summer, monsoon, winter). It knows your oil consumption spikes during Diwali cooking. It knows you order more fresh vegetables after New Year resolutions. It knows you were away for a week in March. This is irreplaceable data.

At month 6, if you switch to Blinkit, you start from zero. Blinkit cannot replicate 6 months of household-specific intelligence instantly. That knowledge is the moat — and it grows with every order.

**The metric that matters to Swiggy's product team:**
90-day retention of Instamart Intelligence users vs regular Instamart users.

### Business Impact Numbers
- **GMV impact:** "Proactive restocking eliminates the 'I'll get it later' behavior. A household that restocks oil when prompted (before it runs out) buys it on Instamart. A household that runs out might buy it at the kirana across the street. Recovering even 30% of those lost-to-kirana purchases represents meaningful incremental GMV."
- **Retention impact:** "Users with 3+ months of household intelligence modeled will not churn. Switching means losing their model. This creates a structural churn floor that no marketing spend can replicate."
- **Frequency impact:** "Currently, users visit Instamart when they remember to. With proactive alerts, visit frequency is driven by the AI. A household receiving 3-4 depletion alerts per week that converts 60% of those will double their order frequency."
- **Competitive impact:** "Blinkit cannot copy this feature in 3 months. The data moat compounds with time. Swiggy has first-mover advantage in Indian quick commerce intelligence."

---

## 2. SYSTEM ARCHITECTURE

### Technology Decisions
- **FastAPI (Python web framework):** All ML is Python. FastAPI is fast, modern, and has automatic API documentation. Every feature exposes itself as a FastAPI endpoint.
- **PostgreSQL + TimescaleDB:** PostgreSQL is the main database. TimescaleDB is a time-series extension that stores price history and consumption logs efficiently.
- **Facebook Prophet:** Designed for seasonal, messy business data with weekend spikes and outlier trends.
- **pgvector:** PostgreSQL extension that allows similarity searches of recipe ingredients semantically rather than by exact text matching.
- **LangGraph:** Orchestrates stateful agent nodes across multi-turn WhatsApp conversation graphs.
- **Claude API:** Extracts structured ingredients list, generates natural-sounding alert notifications, and parses WhatsApp replies.
- **Twilio WhatsApp API:** Seamlessly routes incoming and outgoing text interactions.
- **Next.js Dashboard:** Visualizes virtual pantry shelves, price tickers, and scenario timelines.
- **APScheduler:** Handles scheduled daily jobs (depletions check and price scrapes).

### Data Flow Diagram
```
YOUR INSTAMART ORDER HISTORY
          ↓
    [MCP Client pulls data]
          ↓
    [TimescaleDB stores it]  ←→  [Price History stored here too]
          ↓
    [Prophet ML builds consumption models]
          ↓
    [Daily scheduler checks depletion dates]
          ↓
    [LangGraph Agent decides what to alert]
          ↓
    [Claude API writes the natural language message]
          ↓
    [Twilio sends it to your WhatsApp]
          ↓
    [You reply YES/NO]
          ↓
    [Agent calls Instamart MCP to build cart + place order]
          ↓
    [Next.js dashboard shows everything visually]
```

### Project Structure
```
Instamart-Intelligence/
├── backend/
│   ├── main.py                        # FastAPI entry point — lifespan, CORS, GZip, router registration
│   ├── config.py                      # Pydantic Settings — DATABASE_URL, MCP_BASE_URL, Twilio, Groq, NVIDIA
│   ├── active_scenario.json           # Persists active demo scenario across server restarts
│   ├── database/
│   │   ├── connection.py              # Async engine, SessionLocal, init_db(), get_checkpointer()
│   │   ├── models.py                  # SQLAlchemy ORM models (6 tables)
│   │   └── migrations/                # Alembic migrations
│   ├── mcp/
│   │   ├── client.py                  # SwiggyMCPClient wrapper
│   │   └── mock_server.py             # Localhost mock MCP server (port 8001), /reload_mock_orders
│   ├── ml/
│   │   ├── consumption_model.py       # ConsumptionModeler — Prophet fitting + rebuild_all_models()
│   │   ├── anomaly_detector.py        # Travel gap / guest spike / dietary change detection
│   │   ├── household_profiler.py      # Infers solo/couple/family_small/family_large composition
│   │   └── confidence_scorer.py       # human_readable() confidence labels
│   ├── agents/
│   │   ├── restock_agent.py           # LangGraph stateful restock graph (6 stages)
│   │   ├── recipe_agent.py            # Recipe → ingredient extraction → pantry check → cart
│   │   └── price_agent.py             # Price tracking → spike/dip alerts → WhatsApp dispatch
│   ├── api/
│   │   ├── schemas.py                 # Pydantic request/response schemas
│   │   └── routes/
│   │       ├── household.py           # GET/POST profile, sync, rebuild-models, scenario switch
│   │       ├── predictions.py         # GET predictions with days_remaining + stock_fill_percent
│   │       ├── restock.py             # GET/POST depletion check (≤45% stock, ≤7 days), alert history
│   │       ├── recipes.py             # GET list; POST parse, pin
│   │       ├── prices.py              # GET /feed and /alerts — 10-day price history + signals
│   │       └── orders.py              # GET raw order history from seed JSON
│   ├── notifications/
│   │   ├── whatsapp.py                # POST /api/webhook/whatsapp — Twilio + JSON sandbox + LangGraph runner
│   │   └── scheduler.py               # APScheduler: 07:00 prices, 08:00 depletions, 02:00 Sun rebuild
│   ├── services/
│   │   └── sync_service.py            # fetch_and_sync_orders() — MCP → DB with batch dedup
│   ├── seed/
│   │   ├── catalog.py                 # 13-item CATALOG (INS_001–INS_013) + format_restock_alert_message()
│   │   ├── generate_orders.py         # Standard household order generator
│   │   ├── scenarios.py               # generate_scenario_orders() — standard / party / vacation
│   │   ├── seed_prices.py             # Backfills 30-day realistic price history into TimescaleDB
│   │   └── generated_orders.json      # Active seed data (auto-regenerated on scenario switch)
│   └── tests/                         # 16 tests — async SQLite in-memory, no Docker required
│       ├── conftest.py                # SQLite engine, MCP mocks, checkpointer mock, demo household
│       ├── test_db.py
│       ├── test_ml.py
│       ├── test_prices.py
│       ├── test_recipes.py
│       ├── test_webhook.py
│       └── test_checkpointer.py
├── frontend/
│   ├── app/
│   │   ├── globals.css                # CSS tokens, liquid wave + jar lid animations
│   │   ├── layout.tsx                 # Root layout — Header + ChatDrawer
│   │   ├── page.tsx                   # Dashboard — Virtual Pantry Shelf + Depletion Timeline + Scenario Panel
│   │   ├── household/page.tsx         # Household profile
│   │   ├── predictions/page.tsx       # Full prediction list with SWR
│   │   ├── recipes/page.tsx           # Recipe planner — parse + pin
│   │   └── price-alerts/page.tsx      # Commodity price feed — sparklines + signals
│   ├── components/
│   │   ├── ChatDrawer.tsx             # WhatsApp Sandbox Simulator — floating chat with suggestion chips
│   │   └── Header.tsx                 # Navigation header
│   └── lib/
│       └── api.ts                     # Axios client + TypeScript interfaces (householdApi, predictionsApi, recipesApi, pricesApi)
├── docs/
│   ├── specs/                         # Feature specs from @BRAINSTORM sessions
│   ├── adr/                           # Architecture Decision Records from @GRILL sessions
│   ├── builders_club_application.md
│   └── project_analysis_refinements.md
├── AUDIT.md                           # Production readiness audit — 100/100
├── CONTEXT.md                         # Domain glossary and architecture vocabulary
├── docker-compose.yml                 # Postgres + TimescaleDB container
├── alembic.ini
├── pytest.ini
├── pyrightconfig.json
├── requirements.txt
├── run_backend.py                     # Dev helper: starts backend + mock server
├── .env.example
└── README.md
```

### Step-by-Step Implementation & Reference Code

#### Step 1.1 — Environment Setup
```bash
# 1. Clone and init project
git clone https://github.com/kwakhare5/Instamart-Intelligence.git
cd Instamart-Intelligence
python -m venv venv && venv\Scripts\activate  # Windows

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start TimescaleDB via Docker
docker-compose up -d

# 4. Seed order history and price data
python -m backend.seed.generate_orders
python -m backend.seed.seed_prices

# 5. Start all three servers
# Terminal 1 — Mock MCP server (port 8001)
python -m uvicorn backend.mcp.mock_server:app --port 8001

# Terminal 2 — FastAPI backend (port 8000)
python -m uvicorn backend.main:app --port 8000

# Terminal 3 — Next.js frontend (port 3000)
cd frontend && npm install && npm run dev
```

Create a `.env` file in the root with:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/instamart_intelligence
MCP_BASE_URL=http://localhost:8001
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
ALERT_THRESHOLD_DAYS=7
MIN_CONFIDENCE=0.50
GROQ_API_KEY=your_key_here
NVIDIA_API_KEY=your_key_here
```

#### Step 1.2 — Mock Swiggy MCP Server (Localhost Dev)
```python
# backend/mcp/mock_server.py
from fastapi import FastAPI
from datetime import datetime, timedelta
import random, json

app = FastAPI()

MOCK_ORDERS = []  # populated by seed script

@app.get("/get_instamart_orders")
async def get_orders(user_id: str, limit: int = 50):
    return {"orders": MOCK_ORDERS[-limit:]}

@app.post("/search_instamart_items")
async def search_items(query: str):
    # Return mock items matching query
    return {"items": []}

@app.post("/update_instamart_cart")
async def update_cart(items: list):
    return {"cart_id": "mock_cart_123", "items": items}

@app.post("/place_instamart_order")
async def place_order(cart_id: str):
    return {"order_id": f"mock_order_{random.randint(1000,9999)}", "status": "placed"}
```

#### Step 1.3 — Seed Data Generator
```python
# backend/seed/generate_orders.py
import random
from datetime import datetime, timedelta

HOUSEHOLD_ITEMS = {
    "milk": {"item_id": "INS_001", "unit": "L", "family_daily": 1.0, "solo_daily": 0.25, "pack_sizes": [0.5, 1.0, 2.0], "price_per_unit": 28, "category": "dairy"},
    "atta": {"item_id": "INS_002", "unit": "kg", "family_daily": 0.3, "solo_daily": 0.07, "pack_sizes": [1, 2, 5, 10], "price_per_unit": 40, "category": "staples"},
    "cooking_oil": {"item_id": "INS_003", "unit": "L", "family_daily": 0.07, "solo_daily": 0.02, "pack_sizes": [1, 2, 5], "price_per_unit": 130, "category": "staples"},
    "rice": {"item_id": "INS_004", "unit": "kg", "family_daily": 0.2, "solo_daily": 0.05, "pack_sizes": [1, 2, 5, 10], "price_per_unit": 60, "category": "staples"},
    "eggs": {"item_id": "INS_005", "unit": "piece", "family_daily": 2.5, "solo_daily": 0.7, "pack_sizes": [6, 12, 30], "price_per_unit": 7, "category": "protein"}
}

def generate_orders(household_type: str, months: int = 4, user_id: str = "demo_user_001"):
    orders = []
    start_date = datetime.now() - timedelta(days=months * 30)
    inventory = {item: 0.0 for item in HOUSEHOLD_ITEMS}
    current_date = start_date
    while current_date < datetime.now():
        items_to_order = []
        for item, stock in inventory.items():
            daily_use = HOUSEHOLD_ITEMS[item][f"{household_type}_daily"]
            if stock <= daily_use * 2:
                pack = random.choice(HOUSEHOLD_ITEMS[item]["pack_sizes"])
                items_to_order.append({
                    "item_id": HOUSEHOLD_ITEMS[item]["item_id"],
                    "item_name": item,
                    "quantity": 1,
                    "pack_size": pack,
                    "price": pack * HOUSEHOLD_ITEMS[item]["price_per_unit"],
                    "category": HOUSEHOLD_ITEMS[item]["category"]
                })
                inventory[item] += pack
        if items_to_order:
            orders.append({
                "order_id": f"ORD_{len(orders):04d}",
                "user_id": user_id,
                "placed_at": current_date.isoformat(),
                "items": items_to_order,
                "total": sum(i["price"] for i in items_to_order)
            })
        for item in inventory:
            daily_use = HOUSEHOLD_ITEMS[item][f"{household_type}_daily"]
            noise = random.uniform(0.85, 1.15)
            inventory[item] = max(0, inventory[item] - daily_use * noise)
        current_date += timedelta(days=1)
    return orders
```

#### Step 1.4 — Consumption Model with Prophet
```python
# backend/ml/consumption_model.py
from prophet import Prophet
import pandas as pd
from datetime import datetime, timedelta

class ConsumptionModeler:
    def __init__(self, db_session):
        self.db = db_session

    async def build_model_for_item(self, household_id: str, item_id: str) -> dict:
        purchases = await self.db.fetch_all("""
            SELECT oi.standard_quantity, o.placed_at
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.household_id = $1 AND oi.item_id = $2
            ORDER BY o.placed_at ASC
        """, household_id, item_id)

        if len(purchases) < 3:
            return {"confidence": 0.0, "message": "insufficient_data"}

        df = pd.DataFrame([{"ds": p["placed_at"], "y": p["standard_quantity"]} for p in purchases])
        model = Prophet(seasonality_mode='multiplicative', yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False)
        model.fit(df)

        total_quantity = df["y"].sum()
        days_elapsed = (df["ds"].max() - df["ds"].min()).days
        avg_daily = total_quantity / max(days_elapsed, 1)
        last_purchase = purchases[-1]
        days_of_stock = last_purchase["standard_quantity"] / avg_daily
        depletion_date = last_purchase["placed_at"] + timedelta(days=days_of_stock)

        cycle_days_list = df["ds"].diff().dt.days.dropna().tolist()
        cycle_std = pd.Series(cycle_days_list).std()
        confidence = max(0.0, min(1.0, 1.0 - (cycle_std / 30)))

        return {
            "item_id": item_id,
            "avg_daily_consumption": avg_daily,
            "consumption_cycle_days": pd.Series(cycle_days_list).mean(),
            "last_purchase_date": last_purchase["placed_at"],
            "last_purchase_quantity": last_purchase["standard_quantity"],
            "estimated_depletion_date": depletion_date,
            "confidence_score": confidence,
            "data_points": len(purchases)
        }

    async def rebuild_all_models(self, household_id: str):
        """Rebuild consumption models for all recurring items"""
        items = await self.db.fetch_all("""
            SELECT DISTINCT oi.item_id, oi.item_name
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.household_id = $1
        """, household_id)

        results = []
        for item in items:
            model_data = await self.build_model_for_item(household_id, item["item_id"])
            if model_data.get("confidence", 0) > 0.3:
                await self.db.upsert("consumption_models", {
                    "household_id": household_id,
                    **model_data
                })
                results.append(model_data)
        return results
```

#### Step 2.1 — Anomaly Detector
```python
# backend/ml/anomaly_detector.py
class AnomalyDetector:
    def detect_travel(self, order_history: list, window_days: int = 7) -> dict:
        dates = sorted([o["placed_at"] for o in order_history])
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        long_gaps = [g for g in gaps if g >= 5]
        if long_gaps:
            return {"anomaly": "travel", "detected": True, "avg_travel_gap": sum(long_gaps) / len(long_gaps)}
        return {"anomaly": "travel", "detected": False}

    def detect_guests(self, item_id: str, recent_orders: list, baseline: float) -> dict:
        if not recent_orders:
            return {"anomaly": "guests", "detected": False}
        latest_qty = recent_orders[-1]["standard_quantity"]
        if latest_qty > baseline * 2.5:
            return {"anomaly": "guests", "detected": True, "spike_factor": latest_qty / baseline, "recommendation": "exclude_from_model"}
        return {"anomaly": "guests", "detected": False}
```

#### Step 2.2 — Alert Trigger Logic
```python
# backend/api/routes/restock.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=8, minute=0)
async def daily_depletion_check():
    ALERT_THRESHOLD_DAYS = 2
    households = await db.fetch_all("SELECT id, phone_number FROM households WHERE phone_number IS NOT NULL")
    for household in households:
        models = await db.fetch_all("""
            SELECT * FROM consumption_models
            WHERE household_id = $1 AND confidence_score > 0.5
            AND estimated_depletion_date BETWEEN NOW() AND NOW() + INTERVAL '$2 days'
        """, household["id"], ALERT_THRESHOLD_DAYS)
        if models:
            await send_restock_alert(household, models)
```

#### Step 2.3 — Household Profiler
```python
# backend/ml/household_profiler.py
class HouseholdProfiler:
    CONSUMPTION_BENCHMARKS = {
        "solo": {"milk_L_day": 0.25, "eggs_day": 0.7, "atta_kg_day": 0.07},
        "couple": {"milk_L_day": 0.5, "eggs_day": 1.5, "atta_kg_day": 0.15},
        "family_small": {"milk_L_day": 1.0, "eggs_day": 2.5, "atta_kg_day": 0.3},
        "family_large": {"milk_L_day": 2.0, "eggs_day": 5.0, "atta_kg_day": 0.6},
    }
    def infer_composition(self, consumption_models: list) -> dict:
        observed = {m["item_id"]: m["avg_daily_consumption"] for m in consumption_models}
        scores = {}
        for hh_type, benchmarks in self.CONSUMPTION_BENCHMARKS.items():
            score, count = 0, 0
            for metric, expected in benchmarks.items():
                item_id = self.metric_to_item_id(metric)
                if item_id in observed:
                    ratio = observed[item_id] / expected
                    score += max(0, 1 - abs(1 - ratio))
                    count += 1
            scores[hh_type] = score / max(count, 1)
        best_type = max(scores, key=scores.get)
        return {"composition": best_type, "confidence": scores[best_type], "scores": scores}
```

#### Step 3.1 — LangGraph Restock Agent
```python
# backend/agents/restock_agent.py
from langgraph.graph import StateGraph, END
from anthropic import Anthropic
from typing import TypedDict, List

class RestockState(TypedDict):
    household_id: str
    depleting_items: List[dict]
    user_message: str
    confirmed_items: List[dict]
    cart_id: str
    order_placed: bool
    response: str

# Build the graph
graph = StateGraph(RestockState)

async def analyze_items(state: RestockState):
    """Use Claude to generate a natural restock message"""
    client = Anthropic()

    items_text = "\n".join([
        f"- {item['item_name']}: {int(item['confidence']*100)}% likely low, "
        f"last bought {item['days_since_purchase']} days ago"
        for item in state["depleting_items"]
    ])

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""You are a smart household assistant for Instamart.

Items likely running low in this household:
{items_text}

Write a friendly, concise WhatsApp message (under 100 words) asking if they want to reorder.
Include confidence % for top 3 items. End with "Reply YES to reorder all."
Do not use excessive emojis."""
        }]
    )

    state["response"] = response.content[0].text
    return state

async def check_user_response(state: RestockState):
    """Parse user's WhatsApp reply"""
    msg = state["user_message"].strip().upper()

    if msg in ["YES", "Y", "REORDER", "ORDER ALL"]:
        state["confirmed_items"] = state["depleting_items"]
    elif msg == "NO":
        state["confirmed_items"] = []
    else:
        # Let Claude parse partial responses ("just the milk and oil")
        pass
    return state

async def build_cart(state: RestockState):
    """Call Instamart MCP to search and add items"""
    if not state["confirmed_items"]:
        state["response"] = "Got it! I'll check again in 2 days. 👍"
        return state

    cart_items = []
    for item in state["confirmed_items"]:
        search_result = await mcp_client.search_instamart_items(item["item_name"])
        best_match = search_result["items"][0]
        cart_items.append({
            "item_id": best_match["id"],
            "quantity": item["suggested_quantity"]
        })

    cart = await mcp_client.update_instamart_cart(cart_items)
    state["cart_id"] = cart["cart_id"]
    return state

async def confirm_and_place(state: RestockState):
    """Place the order"""
    if state.get("cart_id"):
        order = await mcp_client.place_instamart_order(state["cart_id"])
        state["order_placed"] = True
        state["response"] = f"✅ Order placed! Delivering in ~15 mins. Order #{order['order_id']}"
    return state

# Wire the graph
graph.add_node("analyze", analyze_items)
graph.add_node("check_response", check_user_response)
graph.add_node("build_cart", build_cart)
graph.add_node("confirm", confirm_and_place)

graph.set_entry_point("analyze")
graph.add_edge("analyze", END)
graph.add_edge("check_response", "build_cart")
graph.add_edge("build_cart", "confirm")
graph.add_edge("confirm", END)

restock_agent = graph.compile()
```

#### Step 3.2 — Unified Webhook Router & Checkpointer
```python
# backend/notifications/whatsapp.py
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.connection import get_db, get_checkpointer
from backend.database.models import Household, RestockAlert
from backend.agents.restock_agent import build_restock_graph

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    is_json = "application/json" in content_type
    phone, message = "", ""

    if is_json:
        payload = await request.json()
        phone = payload.get("phone", "").replace("whatsapp:", "")
        message = payload.get("message", "")
    else:
        form_data = await request.form()
        phone = form_data.get("From", "").replace("whatsapp:", "")
        message = form_data.get("Body", "")

    # Look up household by phone number
    stmt = select(Household).where(Household.phone_number == phone)
    res = await db.execute(stmt)
    hh = res.scalar_one_or_none()

    if not hh:
        reply = "Household not registered. Please register on the dashboard."
        return {"response_message": reply} if is_json else Response(content=f"<Response><Message>{reply}</Message></Response>", media_type="application/xml")

    # Fetch active depleting items from latest alert
    depleting_items = [{"item_name": "Fortune Sunflower Oil 1L", "confidence_score": 0.9, "days_remaining": 1.0}]

    # Run stateful LangGraph agent with Postgres checkpointer
    config = {"configurable": {"thread_id": phone}}
    async with await get_checkpointer() as cp:
        agent = build_restock_graph().compile(checkpointer=cp)
        result = await agent.ainvoke({
            "household_id": str(hh.id),
            "depleting_items": depleting_items,
            "stage": "parse_reply",
            "user_message": message,
            "confirmed_items": [],
            "response_message": ""
        }, config=config)
        reply_msg = result.get("response_message", "")

    return {"response_message": reply_msg} if is_json else Response(content=f"<Response><Message>{reply_msg}</Message></Response>", media_type="application/xml")
```

#### Step 3.3 — Next.js Dashboard Key Components
```tsx
// frontend/components/DepletionCard.tsx
interface DepletionCardProps {
  itemName: string;
  daysUntilDepletion: number;
  confidence: number;
  lastPurchaseDate: string;
  suggestedQuantity: number;
}
export function DepletionCard({ itemName, daysUntilDepletion, confidence }: DepletionCardProps) {
  const urgency = daysUntilDepletion <= 1 ? "red" : daysUntilDepletion <= 3 ? "orange" : "green";
  return (
    <div className={`card border-l-4 border-${urgency}-500`}>
      <h3>{itemName}</h3>
      <div className="days-counter">
        <span className="big-number">{daysUntilDepletion}</span>
        <span>days left</span>
      </div>
      <div className="confidence-bar">
        <div style={{ width: `${confidence * 100}%` }} />
        <span>{Math.round(confidence * 100)}% confidence</span>
      </div>
    </div>
  );
}
```
**Required Frontend Pages**:
- `/` — Overview: items depleting soon (sorted by urgency), household profile badge
- `/predictions` — Full timeline: all items with confidence bars + depletion dates
- `/recipes` — Pin weekly recipes, see what's missing from pantry
- `/price-alerts` — Commodity price charts, spike/dip alerts
- `/settings` — Household profile, notification preferences, privacy controls

#### Step 4.1 — Recipe Agent (LangGraph + Claude)
```python
# backend/agents/recipe_agent.py
from anthropic import Anthropic
import json

async def recipe_to_cart(recipe_name: str, servings: int, household_id: str) -> dict:
    """
    Given a recipe name, figure out what's missing from the pantry
    and generate a shopping cart.
    """
    client = Anthropic()

    # Step 1: Parse recipe ingredients with Claude
    ingredient_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"List all ingredients needed for {recipe_name} for {servings} people."
        }]
    )
    ingredients = json.loads(ingredient_response.content[0].text)

    # Step 2: Check estimated pantry state
    pantry = await get_estimated_pantry_state(household_id)

    # Step 3: Find what's missing
    missing_items = []
    for ingredient in ingredients:
        pantry_match = find_pantry_match(ingredient["name"], pantry)
        if not pantry_match or pantry_match["estimated_remaining"] < ingredient["quantity"]:
            missing_items.append({
                "name": ingredient["name"],
                "quantity_needed": ingredient["quantity"],
                "unit": ingredient["unit"],
                "in_pantry": pantry_match["estimated_remaining"] if pantry_match else 0
            })

    return {
        "recipe": recipe_name,
        "servings": servings,
        "missing_items": missing_items
    }
```

#### Step 4.2 — Price Tracker
```python
# backend/agents/price_agent.py
# Run daily via scheduler to track commodity prices

VOLATILE_ITEMS = ["tomatoes", "onions", "potatoes", "cooking_oil", "atta", "dal"]

async def track_commodity_prices():
    for item_name in VOLATILE_ITEMS:
        results = await mcp_client.search_instamart_items(item_name)
        if results["items"]:
            current_price = results["items"][0]["price_per_unit"]

            # Store in TimescaleDB
            await db.execute("""
                INSERT INTO price_history (item_id, item_name, recorded_at, price_per_unit)
                VALUES ($1, $2, NOW(), $3)
            """, results["items"][0]["id"], item_name, current_price)

            # Check vs 30-day average
            avg_price = await db.fetch_val("""
                SELECT AVG(price_per_unit) FROM price_history
                WHERE item_name = $1 AND recorded_at > NOW() - INTERVAL '30 days'
            """, item_name)

            if avg_price:
                change_pct = ((current_price - avg_price) / avg_price) * 100
                if change_pct > 30:
                    await create_price_alert(item_name, "spike", change_pct, current_price, avg_price)
                elif change_pct < -20:
                    await create_price_alert(item_name, "dip", change_pct, current_price, avg_price)
```

#### Step 4.3 — Demo Script (What to Record)
- **Scene 1: The Insight (0:00 - 0:45)**: Open dashboard → Show household profile: "4-person family · Mumbai · Tracked for 4 months". Scroll through timeline of color-coded cards.
- **Scene 2: The Prediction (0:45 - 1:30)**: Click Cooking Oil. Show "Last bought 1L on April 28, depletion May 13". Show 89% confidence bar and history tables.
- **Scene 3: The Alert (1:30 - 2:00)**: WhatsApp alert mockup: Cooking oil (89%), Milk (76%), Atta (71%). Reply YES, receive confirmation of order.
- **Scene 4: Price Intelligence (2:00 - 2:30)**: Price spike alerts for tomatoes (+140%). Suggest substitutions.
- **Scene 5: Recipe Intelligence (2:30 - 3:15)**: Type "Sunday Biryani for 6". Parse ingredients, pantry check, order missing.
- **Scene 6: The Pitch (3:15 - 3:30)**: Show retention statistics.

---

## 3. DATABASE SCHEMA

```sql
-- Households
CREATE TABLE households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    composition VARCHAR(50),        -- 'solo', 'couple', 'family_small', 'family_large'
    composition_confidence FLOAT,
    intelligence_consent BOOLEAN DEFAULT FALSE,
    notifications_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders (synced from Instamart MCP mock server)
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID REFERENCES households(id),   -- indexed
    instamart_order_id VARCHAR(255) UNIQUE,
    placed_at TIMESTAMPTZ NOT NULL,
    total_amount FLOAT,
    raw_data JSONB
);

-- Order line items
CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES orders(id),           -- indexed
    item_id VARCHAR(255) NOT NULL,                 -- indexed
    item_name VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    quantity INTEGER,
    unit VARCHAR(50),               -- 'L', 'kg', 'pack', 'piece'
    standard_quantity FLOAT,        -- normalized (e.g., 500ml → 0.5)
    price FLOAT
);

-- Consumption models (one per item per household)
CREATE TABLE consumption_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID REFERENCES households(id),   -- indexed
    item_id VARCHAR(255),
    item_name VARCHAR(500),
    category VARCHAR(100),
    avg_daily_consumption FLOAT,    -- in standard units per day
    consumption_cycle_days FLOAT,   -- avg days between purchases
    last_purchase_date TIMESTAMPTZ,
    last_purchase_quantity FLOAT,
    estimated_depletion_date TIMESTAMPTZ,
    confidence_score FLOAT,         -- 0.0 to 1.0
    data_points INTEGER,            -- number of orders used to compute
    is_anomaly_excluded BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(household_id, item_id)
);

-- Restock alerts
CREATE TABLE restock_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID REFERENCES households(id),   -- indexed
    item_ids JSONB,                 -- list of item_id strings
    message_sent TEXT,              -- the WhatsApp message text
    sent_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'sent', 'acted', 'dismissed'
    acted_at TIMESTAMPTZ,
    order_id_placed VARCHAR(255)    -- Instamart order ID once placed
);

-- Price history (TimescaleDB hypertable — partitioned by recorded_at)
CREATE TABLE price_history (
    item_id VARCHAR(255) NOT NULL,
    item_name VARCHAR(500),
    recorded_at TIMESTAMPTZ NOT NULL,
    price FLOAT,
    price_per_unit FLOAT,
    PRIMARY KEY (item_id, recorded_at)
);
SELECT create_hypertable('price_history', 'recorded_at');

-- Recipes
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID REFERENCES households(id),
    name VARCHAR(500),
    servings INTEGER,
    ingredients JSONB,              -- [{name, needed, status, estimated?, price?}]
    cuisine VARCHAR(100),
    pinned_for TIMESTAMPTZ,         -- which date it's planned for
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. API CONTRACTS & INTEGRATIONS

### Swiggy Instamart MCP APIs
- **`get_instamart_orders`**: Complete order history — every order placed, every item, quantities, prices, timestamps.
- **`search_instamart_items`**: Product listings matching a search query — item ID, name, price, available sizes.
- **`update_instamart_cart`**: Updated cart state with all items.
- **`get_instamart_cart`**: Current cart contents and total.
- **`place_instamart_order`**: Order confirmation with order ID and estimated delivery time.
- **`track_instamart_order`**: Real-time order status.

### Demo Strategy
- Seed data must not be mathematically uniform. Ensure it includes:
  - 10-day travel gap in month 2.
  - 3x milk spike outlier in month 3.
  - Realistic commodity price fluctuations.

---

## 5. HISTORICAL DECISIONS (ADRs)
- See architectural decisions in the domain context file.

---

## APPENDIX

### Swiggy Builders Club Application Template
```
Subject: Instamart Intelligence — Household AI to win the Blinkit war

Problem I'm solving:
Blinkit and Instamart are functionally identical. Swiggy cannot win on speed or price alone.
The only sustainable moat is intelligence.

What I built:
Instamart Intelligence uses Prophet time-series forecasting on order history to model each
household's consumption rates, predict depletion dates with confidence scores, and proactively
reorder via WhatsApp before items run out. Users who train the system for 3 months will never
switch to Blinkit — they'd lose their household intelligence.

Swiggy MCP APIs used:
- get_instamart_orders (order history ingestion)
- search_instamart_items (restock cart building)
- update_instamart_cart (auto-cart population)
- place_instamart_order (one-tap reorder)
- track_instamart_order (delivery confirmation)

Business impact:
- Switching cost: 3-6 months of household data = structural Blinkit lock-out
- GMV increase: Proactive restocking eliminates "I'll get it next time" behavior
- Frequency: Users order 40% more often when AI prompts them vs self-initiated

Technical proof of agent-building ability:
[Link to your memory palace / prompt engineering project on GitHub]

Built and working on localhost — demo video attached.
Happy to share codebase.

[Your name]
```

### Completion Checklist

#### Week 1
- [ ] Docker + TimescaleDB running locally
- [ ] Mock MCP server returning realistic data
- [ ] Seed script generating 4 months of order history
- [ ] Prophet consumption models building correctly for top 10 items
- [ ] Data pipeline: MCP → DB → Model running end-to-end

#### Week 2
- [ ] Depletion predictions accurate on seed data (±2 days)
- [ ] Anomaly detection handling travel gaps correctly
- [ ] Household profiler inferring family type correctly
- [ ] Alert trigger logic firing at correct thresholds
- [ ] Confidence scores displaying meaningfully

#### Week 3
- [ ] FastAPI endpoints for all core features
- [ ] WhatsApp webhook receiving and parsing replies
- [ ] LangGraph restock agent placing mock orders end-to-end
- [ ] Next.js dashboard showing depletion cards
- [ ] One-tap reorder flow working

#### Week 4
- [ ] Recipe-to-cart working for 5 test recipes
- [ ] Price tracker storing 30+ days of commodity data
- [ ] Demo seed data generating impressive accuracy numbers
- [ ] Demo video recorded (3-4 minutes)
- [ ] Builders Club application submitted

### Privacy & Consent
Add these before demo:
- Clear data deletion endpoint: `DELETE /api/household/{id}/data`
- Consent flag in `households` table: `intelligence_consent BOOLEAN`
- WhatsApp opt-out: reply "STOP" → sets `notifications_enabled = false`
- Privacy note in dashboard: "Your data never leaves Swiggy's infrastructure"

### Key Commands Reference
```bash
# Launch TimescaleDB
docker-compose up -d
# Run Mock MCP
python -m backend.mcp.mock_server
# Run API
uvicorn backend.main:app --reload
# Run nextjs
cd frontend && npm run dev
```
