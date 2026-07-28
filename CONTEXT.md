# CONTEXT.md — Domain Language
# Read at the START of EVERY session.
# AI fills and maintains this via @GRILL. You rarely edit this manually.

---

## Core Entities & Product Purpose

| Term | What it means in THIS app | Never call it |
|------|--------------------------|---------------|
| PreFill | Brand-agnostic quick commerce inventory extension & SDK module | App, standalone platform |
| Landing Page | The narrative showcase (`app/page.tsx`) communicating ROI, retention gains, and setup ease to operators | Marketing site |
| Phone Mockup | **The real app user interface demo** (`PhoneMockup.tsx` & `ui/iphone.tsx`) where visitors test live features | Static image, graphic |
| Item | A product in the user's household inventory (e.g. Milk, Tomatoes, Eggs) | SKU, product, good |
| Restock Alert | AI recommendation sent via 1-tap WhatsApp 24h before stock runs out | Push notice |
| Consumption Velocity | Daily rate of usage modeled per item (`0.48L/day` for milk) | Rate, depletion |
| PreFill Tab | Single host bottom tab housing Pantry Stock, Recipe Checker, & Price Signals | Separate screens |
| Sub-Tabs | Header pills (`Pantry Stock`, `Recipes`, `Price Signals`, `All`) inside the Phone Mockup | Page links |
| Floating WhatsApp | Bottom-right circular `#25D366` green trigger icon launching live restock chat | Support button |

---

## Why We Have the Landing Page & Mockup iPhone

### 1. Why We Have the Landing Page
The landing page (`app/page.tsx`) addresses the fundamental challenge faced by quick-commerce platforms (Zepto, Blinkit, Instamart, BigBasket):
- **The Problem:** 76% of grocery spend leaks back to local Kirana stores due to unexpected stockouts. 90-day retention floor is only 24%.
- **The Pitch:** PreFill embeds an AI house manager into quick commerce apps, predicting household depletion dates 24h in advance.
- **The Proof:** Lifts 90-day retention from 24% to 82% and recaptures ₹1,450/household in lost monthly GMV.

### 2. Why We Have the Mockup iPhone
The mockup iPhone (`PhoneMockup.tsx` & `ui/iphone.tsx`) is **the hands-on interactive product demo**:
- **What the User Sees:** A sleek 6.3" iPhone screen displaying Green Park delivery location, search bar, segmented feature sub-tabs (`Pantry Stock`, `Recipes`, `Price Signals`, `All`), pantry depletion fill bars, recipe ingredient checklists, market price badges, and a floating WhatsApp restock button.
- **How the User Interacts:**
  1. **Pantry Tab:** Adjust item quantities with `-` / `+` steppers, view stock fill bars (`20% LOW`), see daily velocity rates.
  2. **Recipes Tab:** Select dishes (Biryani, Dal, Paneer, Oats), cross-check pantry inventory, tap *"Add Missing Ingredients"* to fulfill cart in 1 tap.
  3. **Price Signals Tab:** View market commodity trends (Tomatoes `SPIKE +140%`, Sunflower Oil `DIP -23%`).
  4. **WhatsApp Restock Chat:** Tap floating WhatsApp button, reply `YES` to simulate order placement, and watch pantry stock automatically replenish to 100%.

---

## Business Rules (Never Break)

1. **100% Brand Agnostic:** Never hardcode specific quick commerce brand names in UI/copy.
2. **Single Unified Mobile View:** All PreFill capabilities render inside a single, seamless scrollable tab.
3. **iPhone 16 Pro Hardware Dimensions:** Mockup container locked to 71.5mm × 149.6mm physical ratio (`w-[305px] h-[638px] aspect-[71.5/149.6] shrink-0 overflow-hidden`).
4. **Zero AI Slop:** No casual emojis in UI buttons, headings, or chat options. Use clean Lucide icons.
5. **Clean Typography:** Display/UI headings in `Outfit`, editorial title accents in `Cambo` (normal weight, no italics).
6. **AsyncSession always:** Sync SQLAlchemy blocks the FastAPI event loop.
7. **Passing Tests:** Run `pytest backend/tests/ -v` (16/16 pass) & `npm run build` (0 warnings/errors) after every edit.
8. **1:1 Mockup Design System Alignment:** Mock iPhone inner UI MUST use global landing page tokens (`#252525`, `#F6F7F8`, `round-card-droxy`, `card-pastel-*`, `btn-droxy-pill-*`, `badge-*`). Inner chat views MUST use container scrolling (`scrollTop`) rather than window `scrollIntoView()` to prevent landing page scroll jumps.
9. **Interactive Mockup Product Demo Integrity:** Treat the iPhone mockup (`PhoneMockup.tsx`) as the real user-facing application:
   - Segmented Sub-Tabs Bar (`Pantry Stock`, `Recipes`, `Price Signals`, `All`) for clutter-free feature exploration.
   - Circular floating WhatsApp button on the bottom-right corner (`bottom-14 right-3 z-40`) with unread notification dot.
   - Unified cart drawer (`bottom-14 left-3 right-16 z-30`) collecting items across pantry steppers and recipe ingredient fulfillments.
   - WhatsApp order confirmation loop that resets depleted pantry stock back to 100% fill level.

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
| FastAPI backend | 🟢 Live | All routes implemented (`orders`, `predictions`, `prices`, `recipes`, `restock`) |
| SQLAlchemy async models | 🟢 Live | Household, Order, OrderItem, ConsumptionModel |
| LangGraph Restock Agent | 🟢 Live | `agents/restock_agent.py` 5-node graph with Postgres checkpointer |
| ML: ConsumptionModel | 🟢 Live | Prophet-based depletion velocity & anomaly exclusion |
| Pytest suite | 🟢 Live | 16/16 tests passing |
| Interactive iPhone Prototype | 🟢 Live | `PhoneMockup.tsx` — hands-on demo of PreFill Pantry tab + WhatsApp 1-tap ordering |
| Single-Page Narrative Showcase | 🟢 Live | `page.tsx` — Ultra-crisp hero (*"Predict stockouts. Automate restocks."*), 13 sections |
| Interactive Feature Sidebar | 🟢 Live | `PreFillFeatureSidebar.tsx` — 5 core capabilities (Prophet, LangGraph, Recipe, Price, Anomaly) |
| Practical Use Cases | 🟢 Live | `PreFillPracticalUse.tsx` — Household categories (Dairy, Staples, Cleaners, Organics) |
| Technical Bento Grid | 🟢 Live | `PreFillBentoGrid.tsx` — 6 bento cards (Prophet ML, Checkpointer, Webhooks, WhatsApp 1-Tap) |
| Balanced Pastel Color System | 🟢 Live | `globals.css` — 4 pastel color families (Sky Blue, Mint Green, Warm Amber, Rose Red) |
| 100% Brand Agnostic | 🟢 Live | 0 brand occurrences across frontend copy |

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
    └── components/ (Header.tsx, PhoneMockup.tsx, ExecutivePanel.tsx, PreFillFeatureSidebar.tsx, PreFillPracticalUse.tsx, PreFillBentoGrid.tsx)
```
