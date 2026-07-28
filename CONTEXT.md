# CONTEXT.md — Domain Language
# Read at the START of EVERY session.
# AI fills and maintains this via @GRILL. You rarely edit this manually.

---

## Core Entities

| Term | What it means in THIS app | Never call it |
|------|--------------------------|---------------|
| PreFill | Brand-agnostic quick commerce inventory extension & SDK module | App, standalone platform |
| Item | A product in the user's inventory | Product, SKU, good |
| Restock | AI-generated recommendation to purchase more of an Item | Order, purchase, buy |
| Consumption | How fast an Item is being used over time (Prophet per-item model) | Usage, depletion, rate |
| Anomaly | Item flagged as having abnormal consumption — excluded from ML training | Outlier, error, spike |
| Catalog | Master list of available Items (`backend/seed/catalog.py`) | Database, inventory list |
| Agent | A LangGraph graph handling one domain task (Restock, Price, Recipe) | Bot, AI, model |
| Checkpointer | PostgreSQL-backed LangGraph state persistence — survives restarts | Cache, memory, state |
| Depletion Date | Prophet-predicted date when an Item runs out (`estimated_depletion_date`) | Expiry, end date |
| Household | The top-level entity — one per user, contains all orders and models | User, account, profile |
| PreFill Tab | Single host bottom tab housing Pantry Stock, Recipe Checker, & Price Signals | Separate screens |

---

## Business Rules (Never Break)

1. **100% Brand Agnostic:** Never hardcode specific quick commerce brand names in UI/copy.
2. **Single Unified Mobile View:** All PreFill capabilities render inside a single, seamless scrollable tab.
3. **iPhone 16 Pro Hardware Dimensions:** Mockup container locked to 71.5mm × 149.6mm physical ratio (`w-[305px] aspect-[71.5/149.6]`).
4. **Zero AI Slop:** No casual emojis in UI buttons, headings, or chat options. Use clean Lucide icons.
5. **Clean Typography:** Display/UI headings in `Outfit`, editorial title accents in `Cambo` (normal weight, no italics).
6. **AsyncSession always:** Sync SQLAlchemy blocks the FastAPI event loop.
7. **Passing Tests:** Run `pytest backend/tests/ -v` (16/16 pass) & `npm run build` (0 warnings/errors) after every edit.

---

## Database Schema

```
Household       → id (UUID), user_id, phone_number,
                  composition (solo/couple/family_small/family_large),
                  composition_confidence, intelligence_consent,
                  notifications_enabled

Order           → id, household_id→Household, quick_commerce_order_id,
                  placed_at, total_amount, raw_data (JSONB)

OrderItem       → id, order_id→Order, item_id, item_name, category,
                  quantity, unit, standard_quantity (normalized), price

ConsumptionModel → id, household_id, item_id, item_name, category,
                   avg_daily_consumption, consumption_cycle_days,
                   last_purchase_date, last_purchase_quantity,
                   estimated_depletion_date, confidence_score,
                   data_points, is_anomaly_excluded (bool)
```
_Migrations: Alembic. Source of truth: `backend/database/models.py`_

---

## Agents

| Agent | File | Nodes | Purpose |
|-------|------|-------|---------|
| Restock | `backend/agents/restock_agent.py` | 5 | WhatsApp low-stock alert + cart build |
| Price | `backend/agents/price_agent.py` | — | Monitors commodity prices, sends alerts |
| Recipe | `backend/agents/recipe_agent.py` | — | Parses recipes, checks pantry, builds cart |

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI backend | 🟢 Live | All routes implemented |
| SQLAlchemy async models | 🟢 Live | Household, Order, OrderItem, ConsumptionModel |
| LangGraph Restock Agent | 🟢 Live | `agents/restock_agent.py` |
| ML: ConsumptionModel | 🟢 Live | Prophet-based depletion prediction |
| Pytest suite | 🟢 Live | 16/16 tests passing |
| Interactive iPhone Prototype | 🟢 Live | `PhoneMockup.tsx` — hands-on demo of PreFill Pantry tab + WhatsApp 1-tap ordering |
| Single-Page Narrative Showcase | 🟢 Live | `page.tsx` — Macro project story, Kirana leakage problem, architecture & ROI analytics |
| Strict 2-Font System | 🟢 Live | 100% `Outfit` (UI/body) + `Cambo` (serif accent) |
| Zero CTA Slop | 🟢 Live | Pure product showcase — all pitch buttons purged |
| Brand-agnostic UI | 🟢 Live | 0 brand occurrences across frontend |

---

## Real File Map

```
PreFill/
├── backend/
│   ├── agents/ (restock_agent.py, price_agent.py, recipe_agent.py)
│   ├── api/ (routes/ orders.py, predictions.py, prices.py, recipes.py, restock.py)
│   ├── database/ (connection.py, models.py)
│   ├── ml/ (consumption_model.py, anomaly_detector.py, confidence_scorer.py)
│   └── tests/ (16 pytest test files)
└── frontend/
    ├── app/ (page.tsx, layout.tsx, globals.css)
    └── components/ (Header.tsx, PhoneMockup.tsx, ExecutivePanel.tsx, ui/iphone.tsx)
```
