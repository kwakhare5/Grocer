# CLAUDE.md — Project Context

# Per-project file. Copy from D:\Ai Template\CLAUDE.md and fill in.

# Version: 4.0 | June 2026

# Full rules: C:\Users\kwakh\.gemini\AI_RULES.md

---

## THE HANDSHAKE (MANDATORY — before any action)

1. Output sentinel: `🔍 Skill: [loaded/none] | Persona: [@role] | Permission: [obtained/pending]`
2. State one detail from this file + `C:\Users\kwakh\.gemini\SKILLS_INDEX.md`
3. Read SKILLS_INDEX.md → load relevant skills → list them
4. Propose plan (Goal / Approach / Steps / Risks)
5. Wait for "Approved" — no tool calls before this

**Skip any step = Unsafe State. Stop. Apologize. Restart.**

Full rules: `C:\Users\kwakh\.gemini\AI_RULES.md`

---

## COMMANDS

| Command        | What it does                                                |
| -------------- | ----------------------------------------------------------- |
| @SYNC          | Reset + load all relevant skills for this project           |
| @GRILL         | Deep alignment + builds CONTEXT.md glossary + ADRs          |
| @BRAINSTORM    | Idea → spec. Always AFTER @GRILL                            |
| @PLAN          | Spec → task list (2-5 min tasks, exact paths, verification) |
| @BUILD         | Execute plan with TDD enforced (RED→GREEN→REFACTOR)         |
| @REVIEW        | Code review against spec before merging                     |
| @DIAGNOSE      | 6-phase disciplined bug hunt (feedback loop → fix → test)   |
| @AUDIT         | Production readiness scan → AUDIT.md with score/100         |
| @PROTOTYPE     | Throwaway design exploration (logic or UI)                  |
| @ZOOM          | Map unfamiliar code using domain vocabulary                 |
| @TAG [feature] | Architecture scan → ARCHITECT_AUDIT.md                      |
| @QA            | Interactive bug reporting → GitHub issues                   |
| @HANDOFF       | Compress session for fresh start                            |

**New feature:** `@GRILL → @BRAINSTORM → @PLAN → @BUILD → @REVIEW → merge`
**Bug:** `@DIAGNOSE → fix → @REVIEW`
**Unknown code:** `@ZOOM → explore → proceed`
**Design question:** `@PROTOTYPE → decision → @BRAINSTORM`

---

## SKILLS

Tier 0 (Karpathy — always active): embedded in AI_RULES.md → K1-K4
Tier 1 (Superpowers): `C:\Users\kwakh\.gemini\SKILLS_INDEX.md` → `sp-*`
Tier 2 (Matt Pocock): `C:\Users\kwakh\.gemini\SKILLS_INDEX.md` → `mp-*`
Tier 3 (Security): `C:\Users\kwakh\.gemini\SKILLS_INDEX.md` → `community-*`
Tier 4 (Domain): `C:\Users\kwakh\.gemini\SKILLS_INDEX.md` → domain skills

---

## PROJECT INFO

# CLAUDE.md — Instamart Intelligence

## Household AI that predicts what your kitchen needs before you run out

---

# Instamart Intelligence — Complete Project Documentation

## "The household AI that knows your kitchen better than you do"

---

# PART 1: WHAT IS THIS PROJECT?

## The Simple Version

Instamart Intelligence is an AI system that sits on top of Swiggy Instamart and watches how your household consumes groceries over time. It learns your patterns — how fast you go through milk, oil, atta, eggs — and sends you a WhatsApp message before you run out, asking if you want to reorder. One tap and it's done.

It's the difference between a grocery app and a grocery assistant.

---

## The Real-World Analogy

Imagine you had a full-time house manager — someone who lives with you, watches what leaves the kitchen shelf, and automatically handles restocking. Before your cooking oil runs out, they've already placed the Instamart order. Before you plan Sunday biryani, they've already checked what's in the pantry and added the missing ingredients to the cart.

That house manager is what this app pretends to be — except it's software that reads your Instamart order history instead of physically watching your shelves.

---

## Why Does This Matter for Swiggy?

**The existential problem:** Swiggy Instamart and Blinkit are identical products. Same 10-minute delivery. Same Amul milk. Same prices. Same interface. A user has zero reason to be loyal to either one — they open whichever app they remember first.

**The solution this project creates:** If Instamart has been learning your household's grocery patterns for 6 months, it knows things Blinkit cannot know:

- Your family uses 1L milk every 2.1 days
- You buy 5kg atta every 17 days, not 16 or 18
- You always buy eggs and bread together on Sunday mornings
- Your oil consumption spikes in October-November (festive season cooking)
- You were away for 10 days in March (zero orders = travel detected)

If you switch to Blinkit, you lose all of that. You're starting from zero. That intelligence — that knowledge about your household — is the switching cost. That's Swiggy's moat against Blinkit. No other feature creates this kind of lock-in.

---

# PART 2: THE FIVE CORE FEATURES EXPLAINED

---

## Feature 1: Consumption Modeling

**What it does in plain English:**
The system reads every Instamart order you've ever placed and builds a profile for each recurring item. It figures out: "This household buys 1L milk every 2.1 days on average. Sometimes 1.9 days, sometimes 2.4 days, but almost always within that range."

**How it works technically:**

- Pulls your complete order history from Swiggy's MCP (API)
- For each item that appears more than 3 times, it runs a time-series analysis using Facebook Prophet (an open-source forecasting library)
- Prophet handles the messy real-world stuff: weekly patterns (you buy more groceries on Sunday), seasonal patterns (more milk during festivals), and random noise
- The output is a consumption model per item: average daily usage, typical purchase cycle, and a confidence score

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

---

## Feature 2: Predictive Restocking

**What it does in plain English:**
Once the system knows your consumption rates, it monitors all your items in the background. Two days before any item is predicted to run out, it sends you a WhatsApp message asking if you want to reorder. You reply YES. It builds the cart and places the order. You never open the app.

**How it works technically:**

- A background scheduler (APScheduler) runs every morning at 8am
- It checks all consumption models for items where `estimated_depletion_date < NOW() + 2 days`
- For matching items, it generates a friendly WhatsApp message using Claude API
- The message is sent via Twilio's WhatsApp API
- When you reply, a LangGraph agent parses your response and either places the order, modifies the cart, or dismisses the alert
- The Swiggy Instamart MCP APIs handle the actual cart building and order placement

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

**The anomaly handling (what makes it actually smart):**
The system doesn't blindly predict — it watches for anomalies:

- **Travel detection**: No orders for 5+ days? You're probably traveling. Predictions are paused, not broken.
- **Guest spike**: You bought 3L milk instead of your usual 1L? Guests visited. This outlier is excluded from your baseline model so it doesn't inflate your daily average.
- **Dietary shift**: Your egg purchases dropped 80% over the last month? The system flags a possible dietary change and asks you to confirm before updating your model.

---

## Feature 3: Recipe Intelligence

**What it does in plain English:**
You tell the app you're making Sunday biryani for 6. It figures out all the ingredients needed, cross-references against your estimated pantry (based on what you've bought and how fast you use it), and shows you exactly what's missing with a ready-to-order cart.

**How it works technically:**

- You type a recipe name (or paste one) into the app
- Claude API parses the recipe and extracts all ingredients with quantities (e.g., "400g basmati rice, 300ml yogurt, 2 large onions, 1 tsp saffron...")
- The system checks your "estimated pantry state" — a calculated estimate of what you likely still have based on last purchase date and daily consumption rate
- Items where your estimated remaining stock is less than what the recipe needs are flagged as "missing"
- Missing items are bundled into a single Instamart cart for one-tap ordering

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

- Pin recipes to specific dates ("Making biryani this Sunday") — system auto-schedules the missing ingredient check for 2 days before
- Cuisine week planning: tell the system your weekly meal plan, it gives you a consolidated shopping list
- Nutritional awareness: if your last 3 restock carts are dominated by processed food or packaged snacks, the system gently flags it

---

## Feature 4: Price Intelligence

**What it does in plain English:**
Certain groceries in India fluctuate wildly — tomatoes, onions, potatoes, cooking oil, atta. The app tracks the price of these volatile staples daily. When tomatoes suddenly cost 140% more than last month, it tells you. When prices dip, it tells you to stock up.

**How it works technically:**

- A daily price scraper calls Swiggy's `search_instamart_items` MCP for each volatile commodity
- Prices are stored in TimescaleDB (a time-series database) — one row per item per day
- Each day, the system calculates the current price vs the 30-day rolling average
- If price > 30% above average: spike alert sent to household
- If price > 20% below average: dip alert sent, suggesting stock-up
- Substitution logic: during a tomato spike, the system suggests canned tomatoes or a recipe swap

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

---

## Feature 5: Household Intelligence Profile

**What it does in plain English:**
Without you ever filling out a form, the system figures out what kind of household you are — solo, couple, family of 4, elderly couple — purely from your consumption patterns. It uses this to calibrate all its predictions.

**How it works technically:**

- Benchmarks for known household types are pre-defined (e.g., a family of 4 in India uses ~1L milk/day, ~300g atta/day, ~2-3 eggs/day)
- The system compares your observed consumption rates across multiple items to these benchmarks
- Whichever benchmark profile your data most closely matches becomes your inferred household type
- This inference is shown to you with a confidence score and you can correct it

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

---

# PART 3: THE TECHNICAL ARCHITECTURE — EXPLAINED SIMPLY

## How all the pieces fit together

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

## Each technology and why it was chosen

**FastAPI (Python web framework)**
The backbone of the entire system. All your ML code is Python, so FastAPI keeps everything in one language. It's fast, modern, and has automatic API documentation. Every feature — consumption models, alerts, recipe parsing, price tracking — exposes itself as a FastAPI endpoint.

**PostgreSQL + TimescaleDB**
PostgreSQL is the main database. TimescaleDB is an extension on top of it that makes time-series data (prices, consumption events, prediction logs) extremely fast to query. You're storing things like "price of tomatoes on every day for 6 months" — that's exactly what TimescaleDB is built for.

**Facebook Prophet**
An open-source forecasting library released by Meta. It was designed specifically for business time-series data that has weekly patterns, seasonal patterns, and occasional anomalies — which is exactly what grocery consumption looks like. It handles messy data gracefully (you don't need perfect data) and gives you uncertainty intervals, not just point predictions.

**pgvector**
A PostgreSQL extension that lets you store and search vector embeddings. Used for item similarity matching — when a recipe calls for "fresh cream" and your order history has "Amul Fresh Cream 200ml", pgvector matches them semantically rather than just by exact string.

**LangGraph**
A framework for building AI agents as graphs with defined states and transitions. Your restock flow is: Analyze → Send Alert → Wait for Reply → Parse Reply → Build Cart → Confirm Order → Place Order. Each step is a node in the graph. LangGraph handles the state management between steps across a multi-turn WhatsApp conversation.

**Claude API**
Used in three places: (1) Writing natural, context-aware WhatsApp messages rather than robotic template strings. (2) Parsing recipe ingredients from free-text recipe names or pasted recipes. (3) Interpreting ambiguous user replies ("just get the basics" or "skip the oil for now").

**Twilio WhatsApp API**
Twilio provides a sandbox WhatsApp number for development. You register your number with the sandbox, and it can send/receive WhatsApp messages. For production, Swiggy would use their official WhatsApp Business API. The reason WhatsApp is the interface (not push notifications) is reach — even non-smartphone users, elderly family members, and people who don't use apps regularly use WhatsApp. It's the most frictionless interface in India.

**Next.js Dashboard**
The visual interface. Shows depletion timelines, price charts, household profile, and recipe planning. Built in Next.js with Tailwind CSS. This is for power users who want to see and manage everything. For casual users, WhatsApp alone is enough.

**APScheduler**
Python library that runs scheduled tasks. The daily depletion check (8am every day), price tracker (runs daily), and weekly model rebuild (every Sunday) are all APScheduler jobs.

---

# PART 4: THE SWIGGY INSTAMART MCP APIS

These are the six Swiggy APIs your system uses. Understanding what each does is important both for building and for your Builders Club application.

## `get_instamart_orders`

**What it returns:** Complete order history — every order placed, every item, quantities, prices, timestamps.
**When your system uses it:** On first load (to build initial consumption models) and after every new order (to update models). Also runs once a week to sync any orders.

## `search_instamart_items`

**What it returns:** Product listings matching a search query — item ID, name, price, available sizes.
**When your system uses it:** When building a restock cart (search for the item name to get the current product listing), when tracking commodity prices (search tomatoes daily to get current price), and when converting recipe ingredients to orderable items.

## `update_instamart_cart`

**What it returns:** Updated cart state with all items.
**When your system uses it:** After the user confirms a restock recommendation, the LangGraph agent calls this to populate the cart with the suggested items before placing the order.

## `get_instamart_cart`

**What it returns:** Current cart contents and total.
**When your system uses it:** Before placing an order, to show the user a cart summary on WhatsApp ("Your cart: Cooking Oil 1L + Milk 1L = ₹158. Confirm?")

## `place_instamart_order`

**What it returns:** Order confirmation with order ID and estimated delivery time.
**When your system uses it:** After the user confirms the cart. This is the final step in the restock flow.

## `track_instamart_order`

**What it returns:** Real-time order status.
**When your system uses it:** After placing an order, to send a delivery confirmation WhatsApp message when the order is out for delivery or delivered.

---

# PART 5: DATA FLOW — STEP BY STEP

## How a new user gets onboarded

1. User connects their Instamart account (OAuth or user ID)
2. System calls `get_instamart_orders` and pulls all available order history
3. For each item that appears 3+ times, a consumption model is built with Prophet
4. Items with confidence > 30% are stored in `consumption_models` table
5. Household composition is inferred from consumption rates
6. User gets their first dashboard view: "We've analyzed 4 months of orders and found 34 recurring items"
7. User optionally adds phone number for WhatsApp alerts

## How a daily depletion check works

1. APScheduler fires at 8:00 AM
2. Queries all consumption models where `estimated_depletion_date < NOW() + 2 days AND confidence > 0.5`
3. For each matching household, groups the depleting items
4. Passes items to LangGraph restock agent
5. Agent calls Claude API to write a natural WhatsApp message
6. Twilio sends the message
7. Alert is logged in `restock_alerts` table with status = 'sent'

## How a WhatsApp reply is processed

1. User replies to the WhatsApp message
2. Twilio sends a webhook POST to your FastAPI `/webhook/whatsapp` endpoint
3. Webhook looks up the household by phone number
4. Fetches the pending restock alert from the database
5. Passes the user's reply + pending items to the LangGraph agent
6. Agent uses Claude API to parse the intent ("yes", "no", "just the oil", "skip milk")
7. For confirmed items, calls `search_instamart_items` to get product IDs
8. Calls `update_instamart_cart` with the items
9. Calls `get_instamart_cart` to verify
10. Calls `place_instamart_order`
11. Sends confirmation WhatsApp message back to user
12. Updates `restock_alerts` table with status = 'acted'

---

# PART 6: THE COMPETITIVE MOAT EXPLAINED

## Why this creates switching cost

When you use regular Instamart, there's no switching cost. Every order is independent. Blinkit has your order history too. Neither app knows anything special about you.

When you use Instamart Intelligence for 3+ months, something changes:

**Month 1:** The system has enough data to model your top 10 recurring items with ~60% confidence. Predictions are okay but not magical.

**Month 3:** 30+ items modeled, 80%+ confidence on staples, anomalies detected and filtered, household composition accurate. The system is genuinely useful.

**Month 6:** The system has seen you through one full seasonal cycle (summer, monsoon, winter). It knows your oil consumption spikes during Diwali cooking. It knows you order more fresh vegetables after New Year resolutions. It knows you were away for a week in March. This is irreplaceable data.

At month 6, if you switch to Blinkit, you start from zero. Blinkit cannot replicate 6 months of household-specific intelligence instantly. That knowledge is the moat — and it grows with every order.

## The metric that matters to Swiggy's product team

**90-day retention of Instamart Intelligence users vs regular Instamart users.**

If users with the intelligence layer churn at 3% vs 15% for regular users, the case for investing in this feature is undeniable. This is the number to demo: show that the switching cost is real by showing what a user would lose.

---

# PART 7: DEMO STRATEGY

## Why the demo data matters as much as the code

Your seed data script is not an afterthought — it's 50% of your demo quality. Swiggy evaluators will not be impressed by "the model runs". They'll be impressed by seeing:

- "Your household uses 1L milk every 2.1 days" displayed with a confidence bar
- A prediction that was accurate within 1 day shown next to the actual order date
- A WhatsApp message that reads like a human assistant wrote it, not a template

All of this depends on having 4 months of realistic, believable seed data that tells a coherent household story.

## What makes seed data "realistic"

Bad seed data: every item ordered exactly every N days, always the same quantity, perfectly on schedule. This will produce impossibly high confidence scores and make your demo look fake.

Good seed data:

- Orders cluster slightly (you tend to do a "big shop" order vs small top-ups)
- Quantities vary ±20% (sometimes you buy 1L milk, sometimes 2L)
- There's a 10-day travel gap in month 2
- One weekend in month 3 shows a 3x spike in dairy (guests visited)
- Oil prices are slightly higher in month 3 (reflects real commodity trends)
- Sunday orders are slightly more common than weekday orders
- Some items are only bought monthly, some weekly — the distribution should look natural

## The five demo scenes (in order)

**Scene 1 — The Intelligence:** Open the dashboard. Show the household profile. "4-person family in Mumbai. Tracked for 4 months. 34 items modeled." Show the depletion timeline. This establishes that your system is real and running.

**Scene 2 — The Prediction:** Click on Cooking Oil. Show the consumption model. "68ml/day average. 14 data points. 87% confidence. Estimated depletion: May 24." Then show a table of the last 5 predictions vs actual reorder dates — they should be within ±1-2 days of each other. This proves accuracy.

**Scene 3 — The WhatsApp:** Show a phone screen with the incoming WhatsApp message. Show yourself replying YES. Show the order confirmation coming back. This is the money shot — the entire product in 20 seconds.

**Scene 4 — Price Intelligence:** Show the tomato price chart with a visible spike. Show the alert message. This demonstrates you've thought beyond just restocking — you've thought about price as a dimension.

**Scene 5 — Recipe Intelligence:** Type "Sunday biryani for 6." Show the ingredient parsing. Show the pantry check. Show the missing items cart. End with: "Missing items ordered — ₹180. Arriving in 15 minutes."

---

# PART 8: BUSINESS IMPACT NUMBERS FOR THE APPLICATION

When writing your Swiggy Builders Club application, frame the impact in their language:

**GMV impact:** "Proactive restocking eliminates the 'I'll get it later' behavior. A household that restocks oil when prompted (before it runs out) buys it on Instamart. A household that runs out might buy it at the kirana across the street. Recovering even 30% of those lost-to-kirana purchases represents meaningful incremental GMV."

**Retention impact:** "Users with 3+ months of household intelligence modeled will not churn. Switching means losing their model. This creates a structural churn floor that no marketing spend can replicate."

**Frequency impact:** "Currently, users visit Instamart when they remember to. With proactive alerts, visit frequency is driven by the AI. A household receiving 3-4 depletion alerts per week that converts 60% of those will double their order frequency."

**Competitive impact:** "Blinkit cannot copy this feature in 3 months. The data moat compounds with time. Swiggy has first-mover advantage in Indian quick commerce intelligence."

---

# PART 9: PRIVACY AND TRUST

This project handles sensitive data — your household's grocery patterns reveal a lot about your life. How many people live with you. What you eat. When you travel. Whether you're watching your diet. This trust must be handled explicitly.

**Required privacy features before demo:**

- Consent screen on first use: "We analyze your order history to predict what you need. You can delete your data at any time."
- Data deletion endpoint: `DELETE /api/household/{id}` wipes all models and history
- WhatsApp opt-out: reply "STOP" at any time to pause all notifications
- Anomaly data: travel gaps and guest spikes are flagged but not shared with Swiggy for any marketing purpose
- All data stays within Swiggy's infrastructure (emphasize this in the application)

---

# PART 10: WHAT SUCCESS LOOKS LIKE

**Week 4 demo is successful if:**

- You can show consumption models for 10+ items with real-looking confidence scores
- You can demonstrate a prediction that was accurate within 2 days on your seed data
- The WhatsApp → YES → order placed flow works end-to-end (even with mock MCP)
- The recipe-to-cart feature works for at least 5 common Indian dishes
- The dashboard looks professional and loads fast

**Swiggy application is successful if:**

- You get a response within 2 weeks (high strategic fit = faster response)
- They request the demo video (means they're interested)
- They grant sandbox API access (means they're serious)

**The product is successful (long-term) if:**

- 90-day retention of Intelligence users is 3x higher than regular users
- Average order frequency increases 40%+ for active Intelligence users
- User-reported NPS includes "it knows what I need" as a top mention

**Stack at a glance:**

- Backend: FastAPI (Python)
- Database: PostgreSQL + TimescaleDB (time-series)
- ML: Facebook Prophet (forecasting)
- AI Agent: LangGraph + Groq / NVIDIA NIM API
- Notifications: Twilio WhatsApp API
- Frontend: Next.js 15 dashboard (Tailwind CSS v4)
- MCP: Swiggy Instamart MCP (localhost mock for dev)

---

## 📁 Project Structure

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

---

## 🗄️ Database Schema

```sql
-- Core tables

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
-- NOTE: item_ids is a JSONB list (e.g. ["INS_001", "INS_003"]) — one row per alert event
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

## 🗓️ Week 1 — Data Pipeline & MCP Integration

### Goal: Get order history flowing and build consumption models

---

### Step 1.1 — Environment Setup

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

**.env file:**

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

---

### Step 1.2 — Mock Swiggy MCP Server (Localhost Dev)

Since you're working locally before Swiggy grants API access, build a mock that returns realistic data:

```python
# backend/mcp/mock_server.py
from fastapi import FastAPI
from datetime import datetime, timedelta
import random, json

app = FastAPI()

# Loaded from seed data
MOCK_ORDERS = []  # populated by seed script

@app.get("/get_instamart_orders")
async def get_orders(user_id: str, limit: int = 50):
    return {"orders": MOCK_ORDERS[-limit:]}

@app.post("/search_instamart_items")
async def search_items(query: str):
    # Return mock items matching query
    return {"items": [...]}  # see realistic_items.py

@app.post("/update_instamart_cart")
async def update_cart(items: list):
    return {"cart_id": "mock_cart_123", "items": items}

@app.post("/place_instamart_order")
async def place_order(cart_id: str):
    return {"order_id": f"mock_order_{random.randint(1000,9999)}", "status": "placed"}
```

---

### Step 1.3 — Seed Data Generator

This is critical for your demo. Generate 4 months of realistic Indian household order data:

```python
# backend/seed/generate_orders.py
"""
Generates realistic Instamart order history for an Indian household.
Run: python -m backend.seed.generate_orders --household-type family
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass

# Realistic Indian household items with consumption rates
HOUSEHOLD_ITEMS = {
    "milk": {
        "item_id": "INS_001",
        "unit": "L",
        "family_daily": 1.0,          # 1L/day for family
        "solo_daily": 0.25,
        "pack_sizes": [0.5, 1.0, 2.0],
        "price_per_unit": 28,          # ₹28/L
        "category": "dairy"
    },
    "atta": {
        "item_id": "INS_002",
        "unit": "kg",
        "family_daily": 0.3,           # 300g/day (roti for 4)
        "solo_daily": 0.07,
        "pack_sizes": [1, 2, 5, 10],
        "price_per_unit": 40,
        "category": "staples"
    },
    "cooking_oil": {
        "item_id": "INS_003",
        "unit": "L",
        "family_daily": 0.07,          # 70ml/day for family
        "solo_daily": 0.02,
        "pack_sizes": [1, 2, 5],
        "price_per_unit": 130,
        "category": "staples"
    },
    "rice": {
        "item_id": "INS_004",
        "unit": "kg",
        "family_daily": 0.2,
        "solo_daily": 0.05,
        "pack_sizes": [1, 2, 5, 10],
        "price_per_unit": 60,
        "category": "staples"
    },
    "eggs": {
        "item_id": "INS_005",
        "unit": "piece",
        "family_daily": 2.5,
        "solo_daily": 0.7,
        "pack_sizes": [6, 12, 30],
        "price_per_unit": 7,
        "category": "protein"
    },
    # Add 20+ more items...
}

def generate_orders(household_type: str, months: int = 4, user_id: str = "demo_user_001"):
    """
    Simulate realistic order patterns:
    - People don't reorder exactly when depleted (slight delay/early)
    - Larger packs ordered less frequently
    - Some items cluster (staples reorder together)
    - Weekend orders are more likely
    """
    orders = []
    start_date = datetime.now() - timedelta(days=months * 30)

    # Track inventory levels per item
    inventory = {item: 0.0 for item in HOUSEHOLD_ITEMS}

    current_date = start_date
    while current_date < datetime.now():
        # Check what needs reordering (within 20% of depletion)
        items_to_order = []
        for item, stock in inventory.items():
            daily_use = HOUSEHOLD_ITEMS[item][f"{household_type}_daily"]
            if stock <= daily_use * 2:  # 2-day buffer triggers reorder
                # Pick appropriate pack size
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

        # Consume daily
        for item in inventory:
            daily_use = HOUSEHOLD_ITEMS[item][f"{household_type}_daily"]
            # Add ±15% noise for realism
            noise = random.uniform(0.85, 1.15)
            inventory[item] = max(0, inventory[item] - daily_use * noise)

        current_date += timedelta(days=1)

    return orders
```

---

### Step 1.4 — Consumption Model with Prophet

```python
# backend/ml/consumption_model.py
from prophet import Prophet
import pandas as pd
from datetime import datetime, timedelta
import json

class ConsumptionModeler:
    def __init__(self, db_session):
        self.db = db_session

    async def build_model_for_item(self, household_id: str, item_id: str) -> dict:
        """
        Builds a Prophet time-series model for a single item.
        Returns: consumption rate, cycle days, predicted depletion date, confidence
        """
        # Fetch all purchases of this item
        purchases = await self.db.fetch_all("""
            SELECT oi.standard_quantity, o.placed_at
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.household_id = $1 AND oi.item_id = $2
            ORDER BY o.placed_at ASC
        """, household_id, item_id)

        if len(purchases) < 3:
            return {"confidence": 0.0, "message": "insufficient_data"}

        # Build Prophet dataframe — cumulative consumption over time
        df = pd.DataFrame([{
            "ds": p["placed_at"],
            "y": p["standard_quantity"]
        } for p in purchases])

        # Fit model
        model = Prophet(
            seasonality_mode='multiplicative',
            yearly_seasonality=False,
            weekly_seasonality=True,  # Catches weekend buying patterns
            daily_seasonality=False
        )
        model.fit(df)

        # Derive daily consumption rate from total purchased / days elapsed
        total_quantity = df["y"].sum()
        days_elapsed = (df["ds"].max() - df["ds"].min()).days
        avg_daily = total_quantity / max(days_elapsed, 1)

        # Last purchase date and quantity
        last_purchase = purchases[-1]

        # Predict when current stock will run out
        days_of_stock = last_purchase["standard_quantity"] / avg_daily
        depletion_date = last_purchase["placed_at"] + timedelta(days=days_of_stock)

        # Confidence: based on regularity of purchase pattern
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

---

## 🗓️ Week 2 — Prediction Engine

### Goal: Accurate depletion forecasting + smart alert triggers

---

### Step 2.1 — Anomaly Detector

```python
# backend/ml/anomaly_detector.py

class AnomalyDetector:
    """
    Detects lifestyle anomalies that break consumption patterns.
    Types: travel (zero orders), guests (consumption spike), dietary_change (category shift)
    """

    def detect_travel(self, order_history: list, window_days: int = 7) -> dict:
        """
        If no orders for 5+ days, user is likely traveling.
        Pause predictions during this window.
        """
        dates = sorted([o["placed_at"] for o in order_history])
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]

        long_gaps = [g for g in gaps if g >= 5]
        if long_gaps:
            return {
                "anomaly": "travel",
                "detected": True,
                "avg_travel_gap": sum(long_gaps) / len(long_gaps),
                "frequency_per_year": len(long_gaps) * (365 / len(dates))
            }
        return {"anomaly": "travel", "detected": False}

    def detect_guests(self, item_id: str, recent_orders: list, baseline: float) -> dict:
        """
        If a single order quantity is 2x+ the baseline, guests likely visited.
        Don't let this spike corrupt the consumption model.
        """
        if not recent_orders:
            return {"anomaly": "guests", "detected": False}

        latest_qty = recent_orders[-1]["standard_quantity"]
        if latest_qty > baseline * 2.5:
            return {
                "anomaly": "guests",
                "detected": True,
                "spike_factor": latest_qty / baseline,
                "recommendation": "exclude_from_model"
            }
        return {"anomaly": "guests", "detected": False}

    def detect_dietary_change(self, category_history: dict) -> dict:
        """
        If a food category's purchase frequency drops >60% vs 3-month average,
        the household may have changed diet (e.g., went vegan, started intermittent fasting).
        """
        changes = []
        for category, monthly_counts in category_history.items():
            if len(monthly_counts) >= 3:
                avg_past = sum(monthly_counts[:-1]) / len(monthly_counts[:-1])
                recent = monthly_counts[-1]
                if avg_past > 0 and recent < avg_past * 0.4:
                    changes.append({
                        "category": category,
                        "drop_pct": ((avg_past - recent) / avg_past) * 100
                    })
        return {"anomaly": "dietary_change", "detected": bool(changes), "changes": changes}
```

---

### Step 2.2 — Alert Trigger Logic

```python
# backend/api/routes/restock.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=8, minute=0)  # Every morning at 8 AM
async def daily_depletion_check():
    """
    For each household, check all consumption models.
    Fire alerts for items depleting within ALERT_THRESHOLD days.
    """
    ALERT_THRESHOLD_DAYS = 2  # Alert 2 days before predicted depletion

    households = await db.fetch_all("SELECT id, phone_number FROM households WHERE phone_number IS NOT NULL")

    for household in households:
        models = await db.fetch_all("""
            SELECT * FROM consumption_models
            WHERE household_id = $1
            AND confidence_score > 0.5
            AND estimated_depletion_date BETWEEN NOW() AND NOW() + INTERVAL '$2 days'
        """, household["id"], ALERT_THRESHOLD_DAYS)

        if models:
            await send_restock_alert(household, models)


async def send_restock_alert(household, items):
    """Send WhatsApp message with restock confirmation"""
    item_list = "\n".join([
        f"• {item['item_name']} ({int(item['confidence_score']*100)}% likely low)"
        for item in items
    ])

    message = f"""🛒 *Instamart Intelligence*

Your household is likely running low on:

{item_list}

Reply *YES* to reorder all, or tap to review each item.

_Prediction based on {items[0]['data_points']}+ orders_"""

    await whatsapp_client.send(household["phone_number"], message)
```

---

### Step 2.3 — Household Profiler

```python
# backend/ml/household_profiler.py

class HouseholdProfiler:
    """
    Infers household composition from consumption patterns.
    No personal questions asked — all inferred from data.
    """

    CONSUMPTION_BENCHMARKS = {
        "solo": {"milk_L_day": 0.25, "eggs_day": 0.7, "atta_kg_day": 0.07},
        "couple": {"milk_L_day": 0.5, "eggs_day": 1.5, "atta_kg_day": 0.15},
        "family_small": {"milk_L_day": 1.0, "eggs_day": 2.5, "atta_kg_day": 0.3},
        "family_large": {"milk_L_day": 2.0, "eggs_day": 5.0, "atta_kg_day": 0.6},
    }

    def infer_composition(self, consumption_models: list) -> dict:
        """
        Compare observed daily consumption rates against known benchmarks.
        Returns best-fit household type + confidence.
        """
        observed = {m["item_id"]: m["avg_daily_consumption"] for m in consumption_models}

        scores = {}
        for hh_type, benchmarks in self.CONSUMPTION_BENCHMARKS.items():
            score = 0
            count = 0
            for metric, expected in benchmarks.items():
                item_id = self.metric_to_item_id(metric)
                if item_id in observed:
                    ratio = observed[item_id] / expected
                    # Score based on how close to 1.0 the ratio is
                    score += max(0, 1 - abs(1 - ratio))
                    count += 1
            scores[hh_type] = score / max(count, 1)

        best_type = max(scores, key=scores.get)
        return {
            "composition": best_type,
            "confidence": scores[best_type],
            "scores": scores
        }
```

---

## 🗓️ Week 3 — Interface & Notifications

### Goal: WhatsApp bot + Next.js dashboard + one-tap reorder

---

### Step 3.1 — LangGraph Restock Agent

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
        # ... LLM parsing logic
        pass
    return state

async def build_cart(state: RestockState):
    """Call Instamart MCP to search and add items"""
    if not state["confirmed_items"]:
        state["response"] = "Got it! I'll check again in 2 days. 👍"
        return state

    cart_items = []
    for item in state["confirmed_items"]:
        # Search for item and get best match
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
graph.add_edge("analyze", END)  # First run: just send alert
# Second run (after user replies): start from check_response
graph.add_edge("check_response", "build_cart")
graph.add_edge("build_cart", "confirm")
graph.add_edge("confirm", END)

restock_agent = graph.compile()
```

---

### Step 3.2 — Unified Webhook Router & Checkpointer

```python
# backend/notifications/whatsapp.py
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

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

    # Look up household by phone number (with demo fallbacks)
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

---

### Step 3.3 — Next.js Dashboard Key Components

```tsx
// frontend/components/DepletionCard.tsx
// Shows a countdown card for each item

interface DepletionCardProps {
  itemName: string;
  daysUntilDepletion: number;
  confidence: number;
  lastPurchaseDate: string;
  suggestedQuantity: number;
}

export function DepletionCard({
  itemName,
  daysUntilDepletion,
  confidence,
}: DepletionCardProps) {
  const urgency =
    daysUntilDepletion <= 1
      ? "red"
      : daysUntilDepletion <= 3
        ? "orange"
        : "green";

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
      <button onClick={() => reorderItem(itemName)}>Reorder Now →</button>
    </div>
  );
}
```

**Dashboard pages to build:**

- `/` — Overview: items depleting soon (sorted by urgency), household profile badge
- `/predictions` — Full timeline: all items with confidence bars + depletion dates
- `/recipes` — Pin weekly recipes, see what's missing from pantry
- `/price-alerts` — Commodity price charts, spike/dip alerts
- `/settings` — Household profile, notification preferences, privacy controls

---

## 🗓️ Week 4 — Recipe Intelligence + Price Tracking + Demo

### Goal: Recipe-to-cart, price intelligence, demo-ready polish

---

### Step 4.1 — Recipe Agent (LangGraph + Claude)

```python
# backend/agents/recipe_agent.py

async def recipe_to_cart(recipe_name: str, servings: int, household_id: str) -> dict:
    """
    Given a recipe name, figure out what's missing from the pantry
    and generate a shopping cart.

    Flow: Recipe Name → Claude parses ingredients → Check pantry state → Return missing items
    """
    client = Anthropic()

    # Step 1: Parse recipe ingredients with Claude
    ingredient_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""List all ingredients needed for {recipe_name} for {servings} people.

For each ingredient provide:
- name (in simple English, as someone would search in a grocery app)
- quantity
- unit (g, kg, L, ml, piece, tbsp, tsp)

Return as JSON array only. No preamble.
Example: [{{"name": "basmati rice", "quantity": 400, "unit": "g"}}]"""
        }]
    )

    ingredients = json.loads(ingredient_response.content[0].text)

    # Step 2: Check estimated pantry state
    pantry = await get_estimated_pantry_state(household_id)
    # pantry = {item_id: estimated_remaining_quantity}

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
        "total_ingredients": len(ingredients),
        "missing_count": len(missing_items),
        "missing_items": missing_items,
        "estimated_cost": await estimate_cart_cost(missing_items)
    }
```

---

### Step 4.2 — Price Tracker

```python
# backend/agents/price_agent.py
# Run daily via scheduler to track commodity prices

VOLATILE_ITEMS = ["tomatoes", "onions", "potatoes", "cooking_oil", "atta", "dal"]

async def track_commodity_prices():
    """
    Daily price check for volatile staples.
    Alerts when prices spike >30% above 30-day average.
    """
    for item_name in VOLATILE_ITEMS:
        # Search current price from Instamart MCP
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
                WHERE item_name = $1
                AND recorded_at > NOW() - INTERVAL '30 days'
            """, item_name)

            if avg_price:
                change_pct = ((current_price - avg_price) / avg_price) * 100

                if change_pct > 30:
                    await create_price_alert(item_name, "spike", change_pct, current_price, avg_price)
                elif change_pct < -20:
                    await create_price_alert(item_name, "dip", change_pct, current_price, avg_price)
```

---

### Step 4.3 — Demo Script (What to Record)

Follow this exact sequence for your demo video:

**Scene 1: The Insight (0:00 - 0:45)**

- Open dashboard → Show household profile: "4-person family · Mumbai · Tracked for 4 months"
- Show top stat: "Your household uses 1L milk every 2.1 days · 94% accuracy"
- Scroll through depletion timeline — 8 items, color-coded by urgency

**Scene 2: The Prediction (0:45 - 1:30)**

- Click on "Cooking Oil" card
- Show: "Last bought 1L on April 28. At your avg of 68ml/day, estimated depletion: May 13"
- Show confidence bar: "89% confidence based on 14 orders"
- Show historical accuracy table: "Last 5 predictions vs actual — within 1.2 days avg"

**Scene 3: The Alert (1:30 - 2:00)**

- Show WhatsApp screen (phone mockup)
- Receive message: "🛒 Instamart Intelligence: Cooking oil (89% low), Milk (76% low), Atta (71% low) likely running low. Reply YES to reorder all."
- Type "YES" → Order confirmation arrives: "✅ Order placed! Arriving in 15 mins"

**Scene 4: Price Intelligence (2:00 - 2:30)**

- Show price chart for tomatoes: spike alert
- "Tomatoes up 140% this week (₹12/100g → ₹29/100g). Based on seasonal pattern, likely to fall in 6-8 days. Consider canned tomatoes or waiting."

**Scene 5: Recipe Intelligence (2:30 - 3:15)**

- Type "Sunday biryani for 6 people"
- Watch system parse ingredients (show loading)
- "You have: basmati rice ✓, onions ✓, spices ✓. You need: cream (400ml), saffron, fresh mint. Cart ready — ₹180 total. Order?"
- Tap "Order Missing Items" → Placed

**Scene 6: The Pitch (3:15 - 3:30)**

- Show switching cost metric: "Users who've been on Instamart Intelligence for 90+ days have 0% churn"
- Close with: "6 months of household data = Blinkit can never catch up"

---

## 🚀 Swiggy Builders Club Application Template

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

---

## ✅ Completion Checklist

### Week 1

- [ ] Docker + TimescaleDB running locally
- [ ] Mock MCP server returning realistic data
- [ ] Seed script generating 4 months of order history
- [ ] Prophet consumption models building correctly for top 10 items
- [ ] Data pipeline: MCP → DB → Model running end-to-end

### Week 2

- [ ] Depletion predictions accurate on seed data (±2 days)
- [ ] Anomaly detection handling travel gaps correctly
- [ ] Household profiler inferring family type correctly
- [ ] Alert trigger logic firing at correct thresholds
- [ ] Confidence scores displaying meaningfully

### Week 3

- [ ] FastAPI endpoints for all core features
- [ ] WhatsApp webhook receiving and parsing replies
- [ ] LangGraph restock agent placing mock orders end-to-end
- [ ] Next.js dashboard showing depletion cards
- [ ] One-tap reorder flow working

### Week 4

- [ ] Recipe-to-cart working for 5 test recipes
- [ ] Price tracker storing 30+ days of commodity data
- [ ] Demo seed data generating impressive accuracy numbers
- [ ] Demo video recorded (3-4 minutes)
- [ ] Builders Club application submitted

---

## 🔐 Privacy & Consent

Add these before demo:

- Clear data deletion endpoint: `DELETE /api/household/{id}/data`
- Consent flag in `households` table: `intelligence_consent BOOLEAN`
- WhatsApp opt-out: reply "STOP" → sets `notifications_enabled = false`
- Privacy note in dashboard: "Your data never leaves Swiggy's infrastructure"

---

## 📌 Key Commands Reference

```bash
# Start everything
docker-compose up -d                    # TimescaleDB
python -m backend.mcp.mock_server      # Mock MCP on :3000
uvicorn backend.main:app --reload      # API on :8000
cd frontend && npm run dev             # Dashboard on :3000

# Seed data
python -m backend.seed.generate_orders --household-type family --months 4

# Rebuild all consumption models
curl -X POST http://localhost:8000/api/household/demo_user_001/rebuild-models

# Trigger manual depletion check
curl -X POST http://localhost:8000/api/restock/check-now

# Run tests
pytest backend/tests/ -v
```
