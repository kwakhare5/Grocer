# CONTEXT.md — Domain Language
# Read at the START of EVERY session.
# AI fills and maintains this via @GRILL. You rarely edit this manually.

---

## Core Entities

| Term | What it means in THIS app | Never call it |
|------|--------------------------|---------------|
| Item | A product in the user's inventory | Product, SKU, good |
| Restock | AI-generated recommendation to purchase more of an Item | Order, purchase, buy |
| Consumption | How fast an Item is being used over time (Prophet per-item model) | Usage, depletion, rate |
| Anomaly | Item flagged as having abnormal consumption — excluded from ML training | Outlier, error, spike |
| Catalog | Master list of available Items (`backend/seed/catalog.py`) — source of truth for MCP | Database, inventory list |
| Agent | A LangGraph graph handling one domain task (Restock, Price, Recipe) | Bot, AI, model |
| Checkpointer | PostgreSQL-backed LangGraph state persistence — survives restarts | Cache, memory, state |
| Depletion Date | Prophet-predicted date when an Item runs out (`estimated_depletion_date`) | Expiry, end date |
| Household | The top-level entity — one per user, contains all orders and models | User, account, profile |

---

## Business Rules (Never Break)

1. Anomaly-excluded items (`is_anomaly_excluded=True`) MUST be filtered from ALL ML training data
2. All DB queries go through `backend/api/routes/` — agents never call DB directly
3. Mock MCP server responses MUST stay in sync with `backend/seed/catalog.py` — update both or neither
4. LangGraph state MUST use the PostgreSQL checkpointer — no in-memory state allowed
5. Always `AsyncSession` — sync SQLAlchemy blocks the FastAPI event loop
6. Run `pytest backend/tests/ -v` after every backend change — all 16 must pass
7. No TimescaleDB — plain PostgreSQL with SQLAlchemy time-series queries

---

## Database Schema

```
Household       → id (UUID), user_id, phone_number,
                  composition (solo/couple/family_small/family_large),
                  composition_confidence, intelligence_consent,
                  notifications_enabled

Order           → id, household_id→Household, instamart_order_id,
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

**Restock Agent nodes (in order):**
1. `generate_alert` — WhatsApp low-stock message via LLM
2. `parse_reply` — interprets YES/NO/partial reply
3. `parse_order_intent` — parses direct order ("2 milk, eggs")
4. `reset_to_order` — cancels flow, returns to order prompt
5. `build_cart` — searches MCP catalog, builds Instamart cart

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI backend | 🟢 Live | All routes implemented |
| API routes (household, orders, predictions, prices, recipes, restock) | 🟢 Live | `api/routes/` |
| SQLAlchemy async models | 🟢 Live | Household, Order, OrderItem, ConsumptionModel |
| Alembic migrations | 🟢 Live | `migrations/versions/36a0f2040781_initial.py` |
| LangGraph Restock Agent | 🟢 Live | `agents/restock_agent.py` |
| Price Agent | 🟢 Live | `agents/price_agent.py` |
| Recipe Agent | 🟢 Live | `agents/recipe_agent.py` |
| ML: ConsumptionModel | 🟢 Live | Prophet-based depletion prediction |
| ML: HouseholdProfiler | 🟢 Live | Infers household size from order patterns |
| ML: AnomalyDetector | 🟢 Live | Removes outliers from training data |
| ML: ConfidenceScorer | 🟢 Live | `ml/confidence_scorer.py` |
| MCP catalog client | 🟢 Live | `mcp/client.py` + `mcp/mock_server.py` |
| WhatsApp notifications | 🟢 Live | `notifications/whatsapp.py` + `scheduler.py` |
| Pytest suite | 🟢 Live | 16 tests, async SQLite in-memory |
| Next.js frontend | 🟢 Live | Dashboard + scenario switcher + chat sandbox |
| Grocery delivery API integration | ⏸️ Paused | Post-production deployment |

---

## Real File Map

```
backend/
├── agents/
│   ├── restock_agent.py     ← LangGraph 5-node WhatsApp flow
│   ├── price_agent.py
│   └── recipe_agent.py
├── api/routes/
│   ├── household.py
│   ├── orders.py
│   ├── predictions.py
│   ├── prices.py
│   ├── recipes.py
│   └── restock.py
├── api/schemas.py           ← Pydantic request/response schemas
├── database/
│   ├── models.py            ← SQLAlchemy models (SOURCE OF TRUTH)
│   └── connection.py        ← AsyncSession setup
├── mcp/
│   ├── client.py
│   └── mock_server.py       ← Must stay synced with seed/catalog.py
├── ml/
│   ├── consumption_model.py ← Prophet-based depletion prediction
│   ├── household_profiler.py
│   ├── anomaly_detector.py
│   └── confidence_scorer.py
├── notifications/
│   ├── whatsapp.py
│   └── scheduler.py
├── seed/
│   ├── catalog.py           ← Source of truth for mock MCP responses
│   └── generate_orders.py
├── tests/                   ← 16 pytest tests (aiosqlite in-memory)
└── migrations/              ← Alembic
```

---

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| DB models | PascalCase | `ConsumptionModel`, `OrderItem` |
| API routes | snake_case path | `/api/restock/{user_id}` |
| Agent files | snake_case | `restock_agent.py` |
| ML model classes | PascalCase | `ConsumptionModel`, `AnomalyDetector` |
| Test files | `test_*.py` | `test_restock_agent.py` |
| SWR hooks (frontend) | camelCase, `use` prefix | `useRestockStatus` |

---

## ADRs — Architecture Decision Records

| Date | Decision | Why |
|------|---------|-----|
| — | FastAPI + Python | LangGraph, Prophet, scikit-learn require Python |
| — | SQLAlchemy AsyncSession | Sync blocks FastAPI event loop |
| — | Prophet for time-series | Better depletion prediction than plain regression |
| — | LangGraph for agents | Stateful multi-turn WhatsApp conversation |
| — | Alembic for migrations | Standard SQLAlchemy migration tool |
| — | Mock MCP must sync with catalog.py | Drift = false test passes |
| — | aiosqlite for tests | Async in-memory DB — no PostgreSQL needed in CI |
| — | No TimescaleDB | Plain PostgreSQL with time-series queries — simpler setup |
| 2026-07-08 | Created SHIPPING_PLAYBOOK.md | Complete guide: localhost → Vercel/Railway production |

---

## Bugs Fixed

_Append-only. Never repeat these._

| Date | Bug | Fix |
|------|-----|-----|
| — | Sync SQLAlchemy in FastAPI | Always `AsyncSession` |
| — | Mock MCP drift from catalog.py | Keep synchronized — update both or neither |
| 2026-07-09 | Restock API 404 in frontend | Synced `restockApi` in `api.ts` to `/api/restock/{user_id}`. Implemented `useRestockStatus` SWR hook. |
