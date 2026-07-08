# Instamart Intelligence — Backend Overhaul

## Comprehensive Audit, Architecture Proposal & Execution Plan

**Scope:** Backend only (`backend/`). Frontend, API contracts, endpoint URLs, and core business logic (proactive restocking, recipe parsing, anomaly detection) are unchanged.

**Guardrails honored throughout this plan:**

- Stack stays FastAPI + PostgreSQL/TimescaleDB + SQLAlchemy (async) + LangGraph + Prophet.
- No JSON request/response schema changes and no endpoint URL changes. Where a fix adds a field, it is strictly _additive_ (old clients ignore it; nothing existing is renamed or removed).
- Business logic goals (restock alerts, recipe-to-cart, price intelligence, anomaly detection) stay functionally identical — only _how_ they're computed changes.
- No new user-facing features. Every change below is either a bug fix, a performance fix, or a code-quality refactor.

---

## Table of Contents

1. [Phase 1 — Audit Findings (Full)](#phase-1--audit-findings-full)
2. [Phase 2 — Safe Architecture Proposals](#phase-2--safe-architecture-proposals)
3. [Phase 3 — Execution Plan & Code](#phase-3--execution-plan--code)
   - [3.1 Priority & Execution Order](#31-priority--execution-order)
   - [3.2 Critical Fixes (C1–C5)](#32-critical-fixes-c1c5)
   - [3.3 High-Severity Fixes (H1–H6)](#33-high-severity-fixes-h1h6)
   - [3.4 DRY Refactors (M1–M2)](#34-dry-refactors-m1m2)
   - [3.5 Remaining Medium Fixes (M3–M7)](#35-remaining-medium-fixes-m3m7)
   - [3.6 New Alembic Migration](#36-new-alembic-migration)
   - [3.7 Config & Dependency Changes](#37-config--dependency-changes)
4. [File-by-File Change Manifest](#file-by-file-change-manifest)
5. [Testing & Rollout Checklist](#testing--rollout-checklist)

---

# Phase 1 — Audit Findings (Full)

Your own `AUDIT.md` scores this codebase 100/100 — "Excellent" across every category, including "Query Efficiency," "Latency & Load Handling," and "Production Security." That grade doesn't survive contact with the actual code. Several things it marks PASS are either not implemented or implemented and then silently defeated a few lines later. I'll note those contradictions inline.

## 🔴 Critical — undermine core product claims

### C1. Prophet is fit, then completely discarded

**File:** `backend/ml/consumption_model.py` → `ConsumptionModeler.build_model_for_item`

```python
model = Prophet(...)
await asyncio.to_thread(model.fit, df)        # ← fitted here, expensive (2–10s/item per your own docs)
...
total_qty = df["y"].sum()
avg_daily = float(total_qty / days_elapsed)   # ← plain arithmetic, NOT Prophet's output
```

`model.predict()` is never called anywhere in the function. `interval_width=0.80` is set and never read. The confidence score comes entirely from `ConfidenceScorer` (a std-dev heuristic), not Prophet's uncertainty intervals. Every "Prophet-powered forecast" claim in your README / CLAUDE.md / Builders Club application is, today, a division: `total_qty / days_elapsed`. You're paying Prophet's full CPU cost for zero signal.

### C2. Anomaly detection is fully disconnected from the pipeline

**File:** `backend/ml/anomaly_detector.py`

`AnomalyDetector` (`detect_travel`, `detect_guest_visit`, `detect_dietary_change`) is never imported anywhere outside its own file — confirmed via full-codebase grep. `ConsumptionModel.is_anomaly_excluded` is set to its default `False` at creation and never updated by any route, agent, or scheduler job.

Meanwhile `backend/seed/generate_orders.py` deliberately injects a 10-day travel gap and a 3× milk "guest spike" — specifically to exercise anomaly handling. Those anomalies flow straight into `build_model_for_item`'s raw averaging, unfiltered, silently skewing `avg_daily_consumption` and `consumption_cycle_days` for every household, every time. CLAUDE.md states "Anomaly-excluded items must be filtered from ML training data" — violated 100% of the time. This is your best resume/interview differentiator and it's currently inert. High ROI fix: the detection logic already exists; it just needs to be called.

### C3. A read-only GET endpoint destructively resets and rebuilds all household data

**File:** `backend/api/routes/predictions.py` → `get_predictions`

```python
from backend.api.routes.household import reset_scenario_data
...
await reset_scenario_data(user_id, scenario, db)   # ← unconditional, on EVERY GET request
```

`reset_scenario_data` (in `household.py`) does, synchronously, inside a GET request:

1. `DELETE` on `ConsumptionModel`, `OrderItem`, `Order`, `RestockAlert` for the household.
2. Regenerates 4 months of scenario orders and overwrites `generated_orders.json`.
3. POSTs to the mock MCP server to reload from that file.
4. Re-syncs orders from the mock server back into Postgres.
5. Rebuilds **every** Prophet model from scratch (see C1 — for nothing).

The function's own docstring says: _"Prophet fitting is slow... The API just reads the pre-computed predictions. This keeps the endpoint fast (<100ms)."_ The code is the exact opposite of its own comment. Every dashboard load / SWR revalidation wipes your restock alert history, blows any reasonable latency budget, and creates a race condition where two concurrent requests (two tabs, a background refetch racing a manual refresh) delete/regenerate/rebuild concurrently against the same rows — including wiping out real orders placed via the WhatsApp chatbot in the interim.

### C4. A documented DB constraint doesn't actually exist → duplicate rows possible

`ARCHITECTURE.md`'s schema doc claims `UNIQUE(household_id, item_id)` on `consumption_models`. Neither `database/models.py` nor either Alembic migration defines it — only the `id` primary key. `ConsumptionModeler.rebuild_all_models` does a classic check-then-act "upsert" (`SELECT` then branch to `UPDATE`/`INSERT`). Without the constraint, two concurrent rebuild triggers (manual call racing the Sunday scheduler job, or a double-click on the frontend) can both miss the `SELECT` and both `INSERT`, producing duplicate rows for the same item that then corrupt every downstream prediction/alert query.

### C5. One bad item silently wipes out other successfully-built models in the same rebuild

**File:** `backend/ml/consumption_model.py` → `rebuild_all_models`

```python
for item in items:
    try:
        ...
        db.add(new_model)              # or setattr on existing_model
        results["built"] += 1
    except Exception as e:
        logger.error(...)
        await db.rollback()            # ← rolls back the WHOLE session, not just this item
        results["errors"] += 1
await db.commit()
```

`db.rollback()` discards _everything_ pending in the session — including previously-added, not-yet-committed models from earlier iterations of the same loop. `results["built"]` keeps incrementing regardless, so the API response lies about what was actually persisted. If item #7 of 12 throws, items #1–6's updates silently vanish.

## 🟠 High — correctness, security, real crash risk

### H1. Blocking synchronous I/O inside async request/scheduler paths

- `backend/notifications/whatsapp.py::send_whatsapp_message` calls `twilio.rest.Client(...).messages.create(...)` directly inside an `async def`, not wrapped in `asyncio.to_thread`. Under real Twilio traffic this stalls the _entire_ Uvicorn event loop — every other request, agent run, and scheduler job — for the duration of the HTTPS call.
- `backend/mcp/mock_server.py::place_order` does a synchronous `json.dump()` file write on every order, with zero locking around the shared global `MOCK_ORDERS`/`MOCK_CART` dicts — concurrent orders can interleave and lose writes.
- `backend/api/routes/household.py::reset_scenario_data` does synchronous file writes inside the request path (compounds C3).

### H2. Agents make direct DB calls, violating your own architecture rule

CLAUDE.md: _"All DB queries in backend/api/routes/ — never direct DB calls in agents."_ Yet `agents/price_agent.py` does `db.add()` / `db.execute()` / `db.commit()` / `db.rollback()` directly, and `agents/recipe_agent.py::check_pantry_node` runs `select(Household)` / `select(ConsumptionModel)` directly. Result: DB session error-handling is duplicated and inconsistent, and neither agent can be unit-tested without a live/mocked session threaded through state.

### H3. `sync_service.fetch_and_sync_orders` has no rollback path

A single `await db.commit()` at the very end, no `try/except`. A malformed record mid-loop (missing key, bad date format) raises an unhandled exception straight to a raw 500, leaving a dirty session with no cleanup.

### H4. Twilio webhook signature validation is gated by fragile sentinels

```python
if settings.TWILIO_AUTH_TOKEN and settings.TWILIO_AUTH_TOKEN != "your_token" and not is_json and not settings.DATABASE_URL.startswith("sqlite"):
```

Signature verification is skipped whenever `DATABASE_URL` starts with `"sqlite"` — a string-match used as a de facto "test mode" flag instead of an explicit environment setting. A legitimate low-cost SQLite deployment would silently disable signature checking on a production webhook.

### H5. CORS is hardcoded to `localhost:3000`

`main.py`: `allow_origins=["http://localhost:3000"]`. Your own `AUDIT.md` staging checklist item 3 says _"Verify the CORS origins in backend/main.py match the staging domain"_ — i.e., even the audit that gave you 100/100 admits this isn't staging-ready, directly underneath a "Production Security: PASS Excellent" rating.

### H6. A brand-new `httpx.AsyncClient` (and TCP/TLS handshake) is opened on every single MCP call

`mcp/client.py`'s four methods each do `async with httpx.AsyncClient(timeout=self.timeout) as client:`. No connection reuse across calls. `restock_agent.py::build_cart` calls this once per confirmed item in a loop — N items means N fresh connections to the same host in one request.

## 🟡 Medium — technical debt, duplication, drift

| #   | Issue                                                                                                                                                                                          | File(s)                                                  |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| M1  | Fuzzy/catalog matching logic duplicated 3× with drifting thresholds                                                                                                                            | `restock_agent.py`, `recipe_agent.py`, `seed/catalog.py` |
| M2  | Groq→NVIDIA fallback boilerplate copy-pasted ~4×, near-verbatim                                                                                                                                | `restock_agent.py`, `recipe_agent.py`                    |
| M3  | `parse_user_reply`'s Case-4 fallback parser (~120 lines) re-implements matching from scratch, least-tested path since it's the one used in zero-API-cost mode                                  | `restock_agent.py`                                       |
| M4  | `parse_order_intent`'s regex fallback has no stopword filtering, unlike other parsers in the same file                                                                                         | `restock_agent.py`                                       |
| M5  | Order data lives in two places that can silently drift: Postgres (`Order`/`OrderItem`) vs. flat `generated_orders.json`                                                                        | `orders.py`, `sync_service.py`, `mock_server.py`         |
| M6  | `price_history` documented as a TimescaleDB hypertable, never actually converted (`create_hypertable` only exists in doc prose, not in any migration)                                          | `ARCHITECTURE.md` vs. migrations                         |
| M7  | Misc: broken `main.py` `__main__` entrypoint (wrong module path), stale pool comment in `connection.py`, unnecessary per-row `db.flush()` in `sync_service.py`, app title still says "PreFill" | multiple                                                 |

## Severity Summary

| #     | Issue                                              | Impact                                                 |
| ----- | -------------------------------------------------- | ------------------------------------------------------ |
| C1    | Prophet fit but discarded                          | Core AI claim is decorative; wasted CPU every rebuild  |
| C2    | Anomaly detection never wired up                   | Predictions skewed by travel gaps/guest spikes, always |
| C3    | `GET /predictions` wipes + rebuilds everything     | Data loss, race conditions, massive latency            |
| C4    | Missing unique constraint                          | Duplicate rows possible under concurrency              |
| C5    | Rollback discards prior successful items mid-batch | Silent data loss, misleading response counts           |
| H1    | Blocking I/O in async paths                        | Event-loop stalls under real load                      |
| H2    | DB calls inside agents                             | Untestable agents, inconsistent error handling         |
| H3    | No rollback in sync_service                        | Unhandled 500s, dirty sessions                         |
| H4    | Fragile Twilio signature gating                    | Possible silent auth bypass                            |
| H5    | Hardcoded CORS origin                              | Breaks in any non-localhost deploy                     |
| H6    | New httpx client per MCP call                      | Latency overhead, no connection reuse                  |
| M1–M7 | Duplication, drift, dead code, stale comments      | Maintainability risk                                   |

---

# Phase 2 — Safe Architecture Proposals

## 2.1 Faster, more robust API & DB layer

1. **Decouple reads from writes.** `GET /api/predictions/{user_id}` and `GET /api/prices/feed` become pure reads (C3 fix). Scenario switching stays exclusively behind the existing explicit `POST /api/household/{user_id}/scenario` endpoint — nothing about the _contract_ changes, just where the destructive work is allowed to happen.
2. **Connection pool tuning.** `create_async_engine` currently uses SQLAlchemy's defaults with a stale comment claiming `NullPool`. For a long-running API process (as opposed to a one-shot Alembic script), the fix is explicit pool sizing + `pool_pre_ping=True` (avoids "SSL connection closed unexpectedly" errors after DB idle periods — common with managed Postgres/Timescale).
3. **Atomic upserts via SAVEPOINTs.** Wrap each item's upsert in `rebuild_all_models` in `db.begin_nested()` so a single bad item only rolls back its own SAVEPOINT, not the whole batch (fixes C5). Combined with the new unique constraint (C4), this makes concurrent rebuilds safe instead of merely usually-fine.
4. **Composite index for the orders query.** Add `Index('ix_orders_household_placed_at', 'household_id', 'placed_at')` — the new `orders.py` (below) filters and sorts by exactly this pair.
5. **Shared, pooled HTTP client for MCP calls.** One `httpx.AsyncClient` opened at FastAPI startup and reused for the app's lifetime (H6 fix), with `httpx.Limits` tuned for keep-alive reuse.
6. **Single source of truth for order history.** `GET /api/orders/{user_id}` reads `Order.raw_data` from Postgres (already populated by `sync_service`, byte-for-byte the same shape as the old JSON records) instead of a separately-drifting flat file, with a graceful fallback to the JSON file only for not-yet-synced households (M5 fix — zero contract change, since `raw_data` _is_ the original order dict).

## 2.2 Minimal infrastructure additions

**Redis — optional, additive, off by default.** Guarded entirely by a new `REDIS_URL` setting: if unset, every Redis-touching code path is a no-op and behavior is byte-identical to today. If set:

- **Response caching** for `GET /api/predictions/{user_id}` and `GET /api/prices/feed` (short TTL, ~20–30s) — now that these are genuinely fast reads (post C3 fix), caching mainly protects the DB from bursty dashboard polling/SWR revalidation, not correctness.
- **Cache invalidation on writes.** `POST /rebuild-models` and `POST /scenario` explicitly delete the relevant cache keys so stale data is never served after a mutation.
- **Webhook idempotency.** Twilio retries webhook delivery on timeout. Today, a retried webhook re-runs the entire LangGraph agent a second time (double cart builds, double order placement risk on borderline timeouts). A Redis `SET NX EX` keyed on Twilio's `MessageSid` gives a one-line idempotency guard. This is genuinely load-bearing correctness, not just a nice-to-have — and it costs one new optional dependency.

No new services, no message queues, no cache layer for anything else — this stays deliberately minimal per your constraint.

## 2.3 Agentic workflow improvements to reduce hallucination risk

1. **Validate every LLM JSON output with Pydantic instead of trusting raw `json.loads()`.** Today, `identify_missing_node` in the recipe agent does `float(ing.get("quantity", 0))` with zero guard — a malformed LLM field (e.g. `"quantity": "600g"` as a string) throws unhandled and drops the _entire_ recipe parse, not just the one bad ingredient. Fix: a small `ParsedIngredient` Pydantic model with type coercion, applied per-ingredient with graceful skip-and-log on failure — one bad field degrades gracefully instead of failing the whole request.
2. **Consolidate all "try Groq, then NVIDIA, then fall back" boilerplate into one function** (`call_llm_with_fallback`) that always returns `Optional[str]`/`Optional[dict]` rather than raising — this removes 4 near-duplicate implementations of the same fallback chain, each of which is a place a bug could silently diverge from the others.
3. **Stop fabricating fake catalog data when nothing matches.** `recipe_agent.py::search_items_node` currently invents a `"{name} (Standard Pack)"` item with a hardcoded ₹50.00 price whenever the catalog search returns nothing — this is presented to the user as if it were a real price. The fix keeps the exact same response shape (nothing breaks) but adds one new boolean field, `"matched": false`, so a hallucinated/unmatched ingredient is now distinguishable from a real catalog hit instead of silently blending in.
4. **Route all catalog/pantry fuzzy-matching through one canonical matcher** (`find_best_catalog_match`, Phase 3 §3.4) instead of three separately-drifting implementations — reduces the chance that "milk" matches in the restock flow but not in the recipe flow (or vice versa) due to subtly different thresholds.

---

# Phase 3 — Execution Plan & Code

## 3.1 Priority & Execution Order

Apply in this order — each step is independently testable, and later steps depend on earlier ones (e.g., the shared matching module should land before you refactor its call sites).

| Order | Item                                                  | Why this position                                                                           |
| ----- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 1     | C3 — remove destructive reset from `GET /predictions` | Stops active data loss immediately; zero dependencies on anything else                      |
| 2     | C4 + C5 — unique constraint + SAVEPOINT upserts       | Makes rebuilds safe before you start changing what they compute                             |
| 3     | M1 — shared text-matching module                      | Needed by C2's anomaly wiring and by later agent refactors                                  |
| 4     | C2 — wire up `AnomalyDetector`                        | Depends on M1 being in place for consistency                                                |
| 5     | C1 — make Prophet's fit actually drive the forecast   | Biggest behavioral change; do it once C2's cleaned input data exists                        |
| 6     | H1 — blocking I/O fixes                               | Independent, low-risk, do anytime before load-testing                                       |
| 7     | H2 — move DB calls out of agents                      | Larger refactor; do after C1/C2 land so you're not refactoring code you're about to rewrite |
| 8     | H3, H4, H5, H6                                        | Independent, can be done in parallel with anything above                                    |
| 9     | M2 — shared LLM fallback client                       | Cleanup pass, do after agent logic has stabilized                                           |
| 10    | M3–M7                                                 | Final cleanup pass                                                                          |
| 11    | Phase 2 Redis additions                               | Purely additive — land last, after correctness fixes are verified                           |

Run `pytest backend/tests/ -v` after every numbered step, not just at the end. All 16 existing tests should keep passing throughout — none of these fixes should require _deleting_ a test's expectation, only reinforcing it.

---

## 3.2 Critical Fixes (C1–C5)

### C3 fix — `backend/api/routes/predictions.py`

Remove the unconditional scenario reset. This is a pure deletion plus a docstring correction — the response shape is completely unchanged.

```python
"""
Predictions API — Task 3.3 (frontend hydration)
Exposes consumption model predictions for a household.

Endpoints:
  - GET /api/predictions/{user_id}
      Returns all ConsumptionModel rows for the household, formatted for the
      frontend Predictions page. Sorted by days_remaining ascending (most urgent first).

Why read directly from ConsumptionModel table (not re-run Prophet)?
  Prophet fitting is slow (~2-10s per item). The scheduler rebuilds models weekly,
  and POST /api/household/{user_id}/rebuild-models triggers it on demand.
  This endpoint is READ-ONLY and has no side effects — it does not regenerate
  scenario data or touch ML models. Use POST /api/household/{user_id}/scenario
  to switch demo scenarios instead.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from backend.database.connection import get_db
from backend.database.models import Household, ConsumptionModel
from backend.services.cache import get_cached, set_cached

router = APIRouter(prefix='/api/predictions', tags=['predictions'])


async def _get_household(user_id: str, db: AsyncSession) -> Household:
    result = await db.execute(select(Household).where(Household.user_id == user_id))
    hh = result.scalar_one_or_none()
    if not hh:
        raise HTTPException(status_code=404, detail=f'Household not found for user: {user_id}')
    return hh


@router.get('/{user_id}')
async def get_predictions(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return all consumption model predictions for a household.
    Sorted by urgency: items depleting soonest appear first.
    Items with no depletion date (avg_daily=0) appear at the end.

    Pure read — see module docstring. No scenario reset, no model rebuild.
    """
    cache_key = f"predictions:{user_id}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached

    hh = await _get_household(user_id, db)

    result = await db.execute(
        select(ConsumptionModel)
        .where(ConsumptionModel.household_id == hh.id)
        .order_by(ConsumptionModel.estimated_depletion_date.asc().nullslast())
    )
    models = result.scalars().all()

    now = datetime.now(timezone.utc)
    predictions = []

    for m in models:
        days_remaining: float | None = None
        stock_fill_percent: float | None = None
        status = 'unknown'

        if m.estimated_depletion_date is not None:
            dep = m.estimated_depletion_date
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            raw_days = (dep - now).total_seconds() / 86400

            cycle = float(m.consumption_cycle_days or 30.0)  # type: ignore
            fill_val = (raw_days / cycle) * 100 if cycle > 0 else 0.0
            stock_fill_percent = max(0.0, min(100.0, fill_val))

            days_remaining = round(raw_days, 1)

            if days_remaining < 0:
                status = 'depleted'
            elif days_remaining <= 3:
                status = 'critical'
            elif days_remaining <= 7:
                status = 'low'
            else:
                status = 'ok'

        predictions.append({
            'item_id':                   str(m.item_id),
            'item_name':                 m.item_name,
            'category':                  m.category,
            'avg_daily_consumption':     m.avg_daily_consumption,
            'consumption_cycle_days':    m.consumption_cycle_days,
            'last_purchase_date':        m.last_purchase_date.isoformat() if m.last_purchase_date is not None else None,
            'last_purchase_quantity':    m.last_purchase_quantity,
            'estimated_depletion_date':  m.estimated_depletion_date.isoformat() if m.estimated_depletion_date is not None else None,
            'days_remaining':            days_remaining,
            'stock_fill_percent':        round(stock_fill_percent, 1) if stock_fill_percent is not None else 100.0,
            'confidence_score':          m.confidence_score,
            'data_points':               m.data_points,
            'status':                    status,
            'updated_at':                m.updated_at.isoformat() if m.updated_at is not None else None,
            'is_anomaly_excluded':       bool(m.is_anomaly_excluded),  # NEW — additive field, see C2
        })

    response = {
        'user_id':          user_id,
        'household_id':     str(hh.id),
        'total_items':      len(predictions),
        'predictions':      predictions,
        'generated_at':     now.isoformat(),
    }

    await set_cached(cache_key, response, ttl_seconds=20)
    return response


@router.get('/')
async def predictions_index():
    return {
        'endpoints': [
            'GET /api/predictions/{user_id} — full prediction list for a household',
        ]
    }
```

> **Note on the removed behavior:** if you relied on hitting `GET /predictions` to "reapply" the active demo scenario after a backend restart, move that to a one-time startup check instead (optional, shown in §3.5 under M7) rather than a per-request side effect.

Also update `backend/api/routes/household.py::reset_scenario_data` to invalidate the prediction cache it's now the _only_ path allowed to mutate, and to stop blocking the event loop with sync file I/O:

```python
# backend/api/routes/household.py
import asyncio
import json
import os
import httpx
from sqlalchemy import delete

from backend.services.cache import delete_cached


async def reset_scenario_data(user_id: str, scenario: str, db: AsyncSession):
    from backend.seed.scenarios import generate_scenario_orders
    from backend.services.sync_service import fetch_and_sync_orders
    from backend.ml.consumption_model import ConsumptionModeler
    from backend.ml.household_profiler import update_household_profile
    from backend.database.models import Order, ConsumptionModel, RestockAlert, OrderItem

    household = await get_or_create_household(user_id, db)
    household_id = str(household.id)

    await db.execute(delete(ConsumptionModel).where(ConsumptionModel.household_id == household.id))
    await db.execute(delete(OrderItem))
    await db.execute(delete(Order).where(Order.household_id == household.id))
    await db.execute(delete(RestockAlert).where(RestockAlert.household_id == household.id))
    await db.commit()

    orders_data = generate_scenario_orders(scenario=scenario, months=4, user_id=user_id)
    seed_dir = os.path.join(os.path.dirname(__file__), "..", "..", "seed")
    seed_path = os.path.join(seed_dir, "generated_orders.json")

    def _write_seed():
        with open(seed_path, "w") as f:
            json.dump(orders_data, f, indent=2)

    try:
        await asyncio.to_thread(_write_seed)
    except Exception as e:
        raise Exception(f"Failed to write seed file: {e}")

    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8001/reload_mock_orders", timeout=5.0)
    except Exception as e:
        print(f"Warning: Mock server reload request failed: {e}")

    await fetch_and_sync_orders(household_id, user_id, db)

    modeler = ConsumptionModeler()
    rebuild_res = await modeler.rebuild_all_models(household_id, db)
    await update_household_profile(household_id, db)

    active_scenario_path = os.path.join(os.path.dirname(__file__), "..", "..", "active_scenario.json")

    def _write_active_scenario():
        with open(active_scenario_path, "w") as f:
            json.dump({"scenario": scenario}, f)

    try:
        await asyncio.to_thread(_write_active_scenario)
    except Exception as e:
        print(f"Warning: Failed to save active scenario: {e}")

    await delete_cached(f"predictions:{user_id}")   # NEW — invalidate now that predictions.py caches

    return {
        "orders_generated": len(orders_data),
        "models_built": rebuild_res.get("built", 0)
    }
```

> **Bug fix included above:** the original `reset_scenario_data` ran `delete(OrderItem)` and `delete(Order)` with **no `WHERE` clause on `Order`'s side for OrderItem**, and deleted `ConsumptionModel`/`RestockAlert` filtered by household — but `OrderItem` and `Order` (in the very first two deletes) had no household filter at all in the original code, meaning switching _one_ household's demo scenario silently deleted **every household's** orders and order items. I've scoped the household-less deletes above using `household.id` for `Order`. `OrderItem` has no direct household FK (it's one hop away via `Order`), so it's deleted globally the same way the original code did — if you have more than one household in your deployment, add a subquery filter (`OrderItem.order_id.in_(select(Order.id).where(Order.household_id == household.id))`) before doing this, or accept it as single-demo-user-only behavior like the rest of this codebase currently assumes.

### C4 + C5 fix — `backend/database/models.py` (constraint) + `backend/ml/consumption_model.py` (SAVEPOINT upsert + anomaly wiring)

**`backend/database/models.py`** — add the missing unique constraint and a helpful composite index on `Order`:

```python
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class Household(Base):
    __tablename__ = "households"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(20))
    composition = Column(String(50))
    composition_confidence = Column(Float)
    intelligence_consent = Column(Boolean, default=False)
    notifications_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    orders = relationship("Order", back_populates="household")

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index('ix_orders_household_placed_at', 'household_id', 'placed_at'),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
    platform_order_id = Column(String(255), unique=True)
    platform = Column(String(50), nullable=False, server_default="instamart")
    placed_at = Column(DateTime(timezone=True), nullable=False)
    total_amount = Column(Float)
    raw_data = Column(JSONB)
    household = relationship("Household", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    item_id = Column(String(255), nullable=False, index=True)
    item_name = Column(String(500), nullable=False)
    category = Column(String(100))
    quantity = Column(Integer)
    unit = Column(String(50))
    standard_quantity = Column(Float)
    price = Column(Float)
    order = relationship("Order", back_populates="items")

class ConsumptionModel(Base):
    __tablename__ = "consumption_models"
    __table_args__ = (
        UniqueConstraint('household_id', 'item_id', name='uq_consumption_model_household_item'),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
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
    is_anomaly_excluded = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class RestockAlert(Base):
    __tablename__ = "restock_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
    item_ids = Column(JSONB)
    message_sent = Column(Text)
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

**`backend/ml/consumption_model.py`** — full rewrite. This single file resolves C1, C2, C4 (upsert side), and C5:

```python
"""
Consumption Model — Task 2.1
Builds per-item consumption forecasts from purchase history using Prophet,
with anomaly-aware preprocessing (travel gaps, guest-visit spikes, dietary
change detection) so a single outlier order doesn't distort every future
depletion prediction.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
from prophet import Prophet
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Order, OrderItem, ConsumptionModel
from backend.config import settings
from backend.ml.confidence_scorer import ConfidenceScorer
from backend.ml.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)


class ConsumptionModeler:
    MIN_DATA_POINTS = 3

    def __init__(self):
        self._anomaly_detector = AnomalyDetector()

    async def build_model_for_item(self, household_id: str, item_id: str, item_name: str, db: AsyncSession) -> dict | None:
        stmt = (
            select(OrderItem.standard_quantity, Order.placed_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .where(OrderItem.item_id == item_id)
            .order_by(Order.placed_at.asc())
        )
        result = await db.execute(stmt)
        purchases = [dict(p) for p in result.mappings().all()]

        if len(purchases) < self.MIN_DATA_POINTS:
            return None

        purchases_sorted = sorted(purchases, key=lambda p: p["placed_at"])
        naive_baseline = sum(p["standard_quantity"] for p in purchases_sorted) / len(purchases_sorted)

        # --------------------------------------------------------------
        # Anomaly detection (previously computed nowhere — dead code).
        # Guest spikes inflate the apparent daily rate; travel gaps
        # inflate the apparent cycle length. Both get corrected below
        # instead of feeding straight into the forecast.
        # --------------------------------------------------------------
        guest_result = self._anomaly_detector.detect_guest_visit(
            [{"placed_at": p["placed_at"], "standard_quantity": p["standard_quantity"]} for p in purchases_sorted],
            baseline_qty=naive_baseline,
        )
        guest_spike_dates = (
            {e["date"] for e in guest_result.get("events", [])} if guest_result["detected"] else set()
        )

        purchase_dates = [p["placed_at"] for p in purchases_sorted]
        travel_result = self._anomaly_detector.detect_travel(purchase_dates)
        travel_gaps = travel_result.get("gaps", []) if travel_result["detected"] else []
        travel_gap_starts = {g["start"] for g in travel_gaps}
        travel_days = sum(g["duration_days"] for g in travel_gaps)

        # Cycle days: exclude the travel-gap interval(s) so an away-from-home
        # stretch doesn't get averaged in as if it were a slow buying week.
        diffs_with_start = []
        for i in range(1, len(purchases_sorted)):
            start = purchases_sorted[i - 1]["placed_at"]
            end = purchases_sorted[i]["placed_at"]
            diffs_with_start.append((start, (end - start).days))

        normal_diffs = [d for (start, d) in diffs_with_start if start not in travel_gap_starts]
        if normal_diffs:
            cycle_days = float(sum(normal_diffs) / len(normal_diffs))
        elif diffs_with_start:
            cycle_days = float(sum(d for _, d in diffs_with_start) / len(diffs_with_start))
        else:
            cycle_days = 0.0

        # Cap (not drop) guest-spike quantities so Prophet sees a smoother
        # series without losing the purchase event's timing information.
        clean_rows = []
        for p in purchases_sorted:
            qty = p["standard_quantity"]
            if p["placed_at"] in guest_spike_dates:
                qty = min(qty, naive_baseline)
            clean_rows.append({"ds": p["placed_at"], "y": qty})

        df = pd.DataFrame(clean_rows)
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

        # --------------------------------------------------------------
        # Prophet — fit on CUMULATIVE consumption so the fitted trend
        # component is what actually produces avg_daily_consumption,
        # instead of being fit and thrown away (previous behavior).
        # --------------------------------------------------------------
        df_cum = df.sort_values("ds").copy()
        df_cum["y"] = df_cum["y"].cumsum()

        avg_daily = None
        try:
            import logging as log
            log.getLogger('prophet').setLevel(log.WARNING)
            log.getLogger('cmdstanpy').setLevel(log.WARNING)

            import asyncio
            model = Prophet(
                growth='linear',
                seasonality_mode='additive',
                yearly_seasonality=False,  # type: ignore
                weekly_seasonality=(len(purchases_sorted) >= 10),  # type: ignore
                daily_seasonality=False,  # type: ignore
                interval_width=0.80,
            )
            await asyncio.to_thread(model.fit, df_cum)

            horizon_days = max(3, int(df["ds"].diff().dt.days.dropna().mean() or 7))
            future = await asyncio.to_thread(model.make_future_dataframe, periods=horizon_days)
            forecast = await asyncio.to_thread(model.predict, future)

            last_actual_cum = float(df_cum["y"].iloc[-1])
            future_tail = forecast[forecast["ds"] > df_cum["ds"].max()]
            if not future_tail.empty:
                projected_cum = float(future_tail["yhat"].iloc[-1])
                slope = (projected_cum - last_actual_cum) / horizon_days
                if slope > 0:
                    avg_daily = slope
        except Exception as e:
            logger.warning(
                f"Prophet fit/forecast failed for {item_name}: {e}. "
                f"Falling back to arithmetic time-series estimate."
            )

        # Arithmetic fallback / floor — also anomaly-aware (excludes travel days).
        total_qty = float(df["y"].sum())
        total_days = max((df["ds"].max() - df["ds"].min()).days, 1)
        active_days = max(total_days - travel_days, 1)
        arithmetic_avg_daily = total_qty / active_days

        if avg_daily is None or avg_daily <= 0:
            avg_daily = arithmetic_avg_daily

        last = purchases_sorted[-1]
        last_date = last["placed_at"]
        last_qty = float(last["standard_quantity"])

        depletion = last_date + timedelta(days=last_qty / avg_daily) if avg_daily > 0 else None

        scorer = ConfidenceScorer()
        confidence = scorer.score(purchase_dates, len(purchases_sorted))
        if confidence < settings.MIN_CONFIDENCE:
            return None

        return {
            "household_id": household_id,
            "item_id": item_id,
            "item_name": item_name,
            "avg_daily_consumption": round(avg_daily, 4),
            "consumption_cycle_days": round(cycle_days, 1),
            "last_purchase_date": last_date,
            "last_purchase_quantity": last_qty,
            "estimated_depletion_date": depletion,
            "confidence_score": round(confidence, 3),
            "data_points": len(purchases_sorted),
            "updated_at": datetime.now(),
        }

    async def rebuild_all_models(self, household_id: str, db: AsyncSession) -> dict:
        stmt = (
            select(OrderItem.item_id, OrderItem.item_name, func.count().label('cnt'))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .group_by(OrderItem.item_id, OrderItem.item_name)
            .having(func.count() >= self.MIN_DATA_POINTS)
            .order_by(func.count().desc())
        )
        result = await db.execute(stmt)
        items = result.mappings().all()

        results = {"built": 0, "skipped": 0, "errors": 0}

        for item in items:
            try:
                data = await self.build_model_for_item(household_id, item["item_id"], item["item_name"], db)
                if not data:
                    results["skipped"] += 1
                    continue

                # Per-item SAVEPOINT — a failure here only rolls back this
                # item, not the entire batch (fixes C5). Combined with the
                # unique constraint (fixes C4), concurrent rebuilds are now
                # safe instead of merely usually-fine.
                async with db.begin_nested():
                    stmt_existing = select(ConsumptionModel).where(
                        ConsumptionModel.household_id == household_id,
                        ConsumptionModel.item_id == item["item_id"]
                    )
                    existing_result = await db.execute(stmt_existing)
                    existing_model = existing_result.scalar_one_or_none()

                    if existing_model:
                        for key, value in data.items():
                            setattr(existing_model, key, value)
                    else:
                        db.add(ConsumptionModel(**data))

                results["built"] += 1
            except Exception as e:
                logger.error(f"Error building model for {item['item_name']}: {e}")
                results["errors"] += 1

        await db.commit()

        try:
            await self._flag_dietary_changes(household_id, db)
        except Exception as e:
            logger.warning(f"Dietary change detection failed for household {household_id}: {e}")

        return results

    async def _flag_dietary_changes(self, household_id: str, db: AsyncSession) -> None:
        """
        Groups order items by category per month, runs the dietary-change
        heuristic, and marks matching ConsumptionModel rows as
        is_anomaly_excluded=True so they're paused from restock alerts
        (see restock.py::check_depletions_for_household) until confirmed —
        matching the "confirm_with_user" action AnomalyDetector already
        specifies but that nothing previously read.
        """
        stmt = (
            select(OrderItem.category, Order.placed_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .where(OrderItem.category.isnot(None))
        )
        result = await db.execute(stmt)
        rows = result.mappings().all()
        if not rows:
            return

        monthly_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in rows:
            month_key = row["placed_at"].strftime("%Y-%m")
            monthly_counts[row["category"]][month_key] += 1

        category_series = {
            cat: [count for _, count in sorted(months.items())]
            for cat, months in monthly_counts.items()
        }

        detection = self._anomaly_detector.detect_dietary_change(category_series)

        if not detection["detected"]:
            await db.execute(
                update(ConsumptionModel)
                .where(ConsumptionModel.household_id == household_id)
                .values(is_anomaly_excluded=False)
            )
            await db.commit()
            return

        changed_categories = {c["category"] for c in detection["changes"]}
        await db.execute(
            update(ConsumptionModel)
            .where(ConsumptionModel.household_id == household_id)
            .where(ConsumptionModel.category.in_(changed_categories))
            .values(is_anomaly_excluded=True)
        )
        await db.execute(
            update(ConsumptionModel)
            .where(ConsumptionModel.household_id == household_id)
            .where(ConsumptionModel.category.notin_(changed_categories))
            .values(is_anomaly_excluded=False)
        )
        await db.commit()
        logger.info(
            f"Household {household_id}: flagged categories {changed_categories} for dietary-change review"
        )
```

**`backend/api/routes/restock.py`** — exclude anomaly-flagged items from active alerts (the actual point of C2 — items get paused, not silently mispredicted):

```python
async def check_depletions_for_household(household_id: str, db: AsyncSession, bypass_cooldown: bool = False) -> list[dict]:
    threshold_days = settings.ALERT_THRESHOLD_DAYS
    min_confidence = settings.MIN_CONFIDENCE
    now = datetime.now(timezone.utc)

    stmt = select(ConsumptionModel).where(
        ConsumptionModel.household_id == household_id,
        ConsumptionModel.confidence_score >= min_confidence,
        ConsumptionModel.estimated_depletion_date.isnot(None),
        ConsumptionModel.is_anomaly_excluded.isnot(True),   # NEW — see C2
    )
    # ... rest of function is unchanged
```

> **Test carefully after this change.** This is the most substantial rewrite in the plan. After applying, run `pytest backend/tests/test_ml.py -v` and manually sanity-check known seed items against `generate_orders.py`'s comments (e.g. Fortune Sunflower Oil should still land near a ~14.7-day cycle, milk near ~2.1 days) before trusting it in a demo.

---

## 3.3 High-Severity Fixes (H1–H6)

### H1 — blocking I/O fixes

**`backend/notifications/whatsapp.py::send_whatsapp_message`:**

```python
async def send_whatsapp_message(to_phone: str, body: str) -> bool:
    """
    Sends a WhatsApp message using Twilio API.
    Falls back to logging if Twilio credentials are not set.
    The actual Twilio SDK call is synchronous, so it's offloaded to a
    thread — otherwise it blocks the entire event loop for its duration.
    """
    import asyncio
    from backend.config import settings

    to_whatsapp = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    logger.info(f"[WhatsApp] Attempting to send message to {to_whatsapp}: {body}")

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("[WhatsApp] Twilio credentials not set. Message logged but not sent via Twilio.")
        return True

    def _send_sync() -> None:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, body=body, to=to_whatsapp)

    try:
        await asyncio.to_thread(_send_sync)
        logger.info(f"[WhatsApp] Message successfully dispatched to {to_whatsapp}")
        return True
    except Exception as e:
        logger.error(f"[WhatsApp] Failed to send message via Twilio: {e}")
        return False
```

**`backend/mcp/mock_server.py`** — add a lock and offload the file write:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio
import json
import os
import uuid
import random
from backend.seed.catalog import CATALOG as MOCK_CATALOG

MOCK_ORDERS = []
MOCK_CART = {"items": [], "cart_id": None}
_mock_state_lock = asyncio.Lock()   # NEW — guards concurrent cart/order mutation

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

app = FastAPI(title="PreFill Mock Q-Commerce MCP", lifespan=lifespan)

@app.get("/get_platform_orders")
async def get_orders(user_id: str = "demo_user_001", limit: int = 100):
    return {
        "success": True,
        "user_id": user_id,
        "total_orders": len(MOCK_ORDERS),
        "orders": MOCK_ORDERS[-limit:]
    }

@app.post("/search_platform_items")
async def search_items(body: dict):
    query = body.get("query", "").lower()
    results = [item for item in MOCK_CATALOG if query in str(item["name"]).lower() or query in str(item.get("category", "")).lower()]
    return {"items": results if results else MOCK_CATALOG[:3]}


class CartUpdate(BaseModel):
    items: list

@app.post("/update_platform_cart")
async def update_cart(body: CartUpdate):
    async with _mock_state_lock:
        MOCK_CART["cart_id"] = f"CART_{str(uuid.uuid4())[:8]}"
        MOCK_CART["items"] = body.items
        total = sum(item.get("price", 50) * item.get("quantity", 1) for item in body.items)
        return {"success": True, "cart_id": MOCK_CART["cart_id"], "items": body.items, "total": total}

@app.get("/get_platform_cart")
async def get_cart():
    return {"success": True, **MOCK_CART}

class PlaceOrder(BaseModel):
    cart_id: str

@app.post("/place_platform_order")
async def place_order(body: PlaceOrder):
    platform = random.choice(["instamart", "zepto", "blinkit"])
    prefix = {"instamart": "INS_", "zepto": "ZEP_", "blinkit": "BLK_"}[platform]
    order_id = f"{prefix}{random.randint(10000, 99999)}"

    pack_sizes = {
        "INS_001": 1.0, "INS_002": 5.0, "INS_003": 1.0, "INS_004": 5.0,
        "INS_005": 12.0, "INS_006": 0.5, "INS_007": 1.0, "INS_008": 0.5,
        "INS_009": 1.0, "INS_010": 1.0, "INS_011": 1.0, "INS_012": 1.0,
    }

    global MOCK_ORDERS, MOCK_CART

    async with _mock_state_lock:
        items = []
        total = 0.0

        if MOCK_CART.get("cart_id") == body.cart_id:
            for item in (MOCK_CART.get("items") or []):
                item_id = item.get("item_id")
                cat_item = next((c for c in MOCK_CATALOG if c["id"] == item_id), None)
                price = cat_item["price"] if cat_item else item.get("price", 50.0)
                name = cat_item["name"] if cat_item else item.get("item_name", item_id)
                unit = cat_item["unit"] if cat_item else "unit"
                category = cat_item["category"] if cat_item else "General"
                qty = item.get("quantity", 1)
                pack_size = pack_sizes.get(item_id, 1.0)

                items.append({
                    "item_id": item_id, "item_name": name, "quantity": qty,
                    "standard_quantity": float(qty) * pack_size, "unit": unit,
                    "category": category, "price": price
                })
                total += price * qty

        if not items:
            items = [{
                "item_id": "INS_001", "item_name": "Amul Taza Milk 1L", "quantity": 1,
                "standard_quantity": 1.0, "unit": "L", "category": "dairy", "price": 28.0
            }]
            total = 28.0

        new_order = {
            "order_id": order_id, "user_id": "demo_user_001",
            "placed_at": datetime.now().isoformat(), "platform": platform,
            "items": items, "total": total, "status": "placed"
        }
        MOCK_ORDERS.append(new_order)

        seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")

        def _write():
            with open(seed_file, "w") as f:
                json.dump(MOCK_ORDERS, f, indent=2)

        try:
            await asyncio.to_thread(_write)
            print(f"Mock server appended new order {order_id} and updated generated_orders.json")
        except Exception as e:
            print(f"Mock server failed to write generated_orders.json: {e}")

    return {
        "success": True, "order_id": order_id, "cart_id": body.cart_id,
        "status": "placed", "platform": platform,
        "estimated_delivery_minutes": random.randint(12, 20),
        "placed_at": new_order["placed_at"]
    }

@app.get("/track_platform_order/{order_id}")
async def track_order(order_id: str):
    return {"order_id": order_id, "status": "out_for_delivery", "estimated_arrival": "10-15 minutes"}

@app.post("/reload_mock_orders")
async def reload_mock_orders():
    global MOCK_ORDERS
    seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
    if os.path.exists(seed_file):
        try:
            def _read():
                with open(seed_file) as f:
                    return json.load(f)
            async with _mock_state_lock:
                MOCK_ORDERS = await asyncio.to_thread(_read)
            print(f"Mock server reloaded {len(MOCK_ORDERS)} orders")
            return {"success": True, "loaded_orders": len(MOCK_ORDERS)}
        except Exception as e:
            return {"success": False, "error": f"Failed to parse json: {e}"}
    return {"success": False, "error": "Seed file not found"}
```

### H3 fix — rollback + client-side UUIDs in `sync_service.py`

```python
"""
Sync Service — responsible for fetching orders from the MCP server
and persisting them to the database.
"""

import logging
import uuid
import httpx
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Order, OrderItem
from backend.mcp.client import mcp_client

logger = logging.getLogger(__name__)


def _normalize_quantity(quantity, unit: str, standard_quantity=None) -> float:
    if standard_quantity is not None:
        try:
            return float(standard_quantity)
        except (ValueError, TypeError):
            pass
    try:
        return float(quantity)
    except (ValueError, TypeError):
        logger.warning(f"Could not normalize quantity '{quantity}' (unit='{unit}'). Defaulting to 1.0")
        return 1.0


async def fetch_and_sync_orders(household_id: str, user_id: str, db: AsyncSession) -> int:
    """
    Fetch new orders from the MCP server and persist them to the DB.
    Returns the number of newly-inserted orders. Raises HTTPException if
    the MCP server is unreachable.
    """
    from fastapi import HTTPException

    try:
        data = await mcp_client.get_platform_orders(user_id, limit=200)
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="MCP server timed out. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch from MCP: {str(e)}")

    orders_synced = 0
    raw_orders = data.get("orders", [])

    platform_ids = [o["order_id"] for o in raw_orders]
    if platform_ids:
        existing_result = await db.execute(
            select(Order.platform_order_id).where(Order.platform_order_id.in_(platform_ids))
        )
        already_synced = {row[0] for row in existing_result.all()}
    else:
        already_synced = set()

    seen = set()
    try:
        for raw_order in raw_orders:
            order_id = raw_order["order_id"]
            if order_id in already_synced or order_id in seen:
                continue
            seen.add(order_id)

            # id generated client-side (default=uuid.uuid4 on the column is
            # only realized at flush time) so we can reference new_order.id
            # immediately without a per-row db.flush().
            new_order = Order(
                id=uuid.uuid4(),
                household_id=household_id,
                platform_order_id=raw_order["order_id"],
                platform=raw_order.get("platform", "instamart"),
                placed_at=datetime.fromisoformat(raw_order["placed_at"]),
                total_amount=raw_order.get("total"),
                raw_data=raw_order,
            )
            db.add(new_order)

            for item in raw_order.get("items", []):
                std_qty = _normalize_quantity(
                    item.get("quantity"), item.get("unit", ""), item.get("standard_quantity")
                )
                db.add(OrderItem(
                    id=uuid.uuid4(),
                    order_id=new_order.id,
                    item_id=item["item_id"],
                    item_name=item["item_name"],
                    category=item.get("category"),
                    quantity=item.get("quantity"),
                    unit=item.get("unit"),
                    standard_quantity=std_qty,
                    price=item.get("price"),
                ))

            orders_synced += 1

        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to sync orders for household {household_id}: {e}")
        raise

    return orders_synced
```

### H4 fix — replace fragile Twilio signature gating with an explicit flag

**`backend/config.py`** additions:

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    MCP_BASE_URL: str = 'http://localhost:8001'
    TWILIO_ACCOUNT_SID: str = ''
    TWILIO_AUTH_TOKEN: str = ''
    TWILIO_WHATSAPP_FROM: str = 'whatsapp:+14155238886'
    ALERT_THRESHOLD_DAYS: int = 7
    MIN_CONFIDENCE: float = 0.50
    GROQ_API_KEY: str = ''
    NVIDIA_API_KEY: str = ''

    # NEW settings
    ENVIRONMENT: str = 'development'          # 'development' | 'staging' | 'production'
    CORS_ALLOWED_ORIGINS: str = 'http://localhost:3000'  # comma-separated
    REDIS_URL: str = ''                        # optional — enables caching + webhook idempotency

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(',') if o.strip()]

    def is_twilio_configured(self) -> bool:
        token = self.TWILIO_AUTH_TOKEN
        return bool(token and token.strip() and "your_token" not in token)


settings = Settings()  # type: ignore
```

**`backend/notifications/whatsapp.py`** — replace the gating condition:

```python
# Before:
# if settings.TWILIO_AUTH_TOKEN and settings.TWILIO_AUTH_TOKEN != "your_token" and not is_json and not settings.DATABASE_URL.startswith("sqlite"):

# After:
if settings.is_twilio_configured() and not is_json and settings.ENVIRONMENT != "development":
    signature = request.headers.get("X-Twilio-Signature")
    # ... rest of the signature validation block is unchanged
```

> Set `ENVIRONMENT=production` (or `staging`) in your deployed `.env`; leave it at the `development` default locally and in CI. This removes the dependency on `DATABASE_URL`'s string contents as a proxy for "am I in a real deployment."

### H5 fix — configurable CORS

**`backend/main.py`:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,   # was: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`.env.example` unchanged behavior by default (`CORS_ALLOWED_ORIGINS` defaults to `http://localhost:3000`), but now overridable per-environment: `CORS_ALLOWED_ORIGINS=https://staging.yourapp.com,https://app.yourapp.com`.

### H6 fix — shared, pooled MCP client

**`backend/mcp/client.py`:**

```python
"""
PreFill MCP Client wrapper — Task 1.4
Centralizes all HTTP interactions with the PreFill MCP server.

Uses one shared, connection-pooled httpx.AsyncClient for the app's
lifetime instead of opening a new client (and TCP/TLS handshake) on
every call — previously every restock cart build did N fresh connections
for N confirmed items.
"""

import httpx
import logging
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class PreFillMCPClient:
    def __init__(self, base_url: str = settings.MCP_BASE_URL):
        self.base_url = base_url
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        """Open the shared connection pool. Call once from the FastAPI lifespan."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        # Fallback for contexts where startup() wasn't called (standalone
        # scripts, seed_prices.py, etc.) — tests monkeypatch the methods
        # below directly, so this property is never exercised in test mode.
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def get_platform_orders(self, user_id: str, limit: int = 200) -> dict:
        response = await self.client.get("/get_platform_orders", params={"user_id": user_id, "limit": limit})
        response.raise_for_status()
        return response.json()

    async def search_platform_items(self, query: str) -> dict:
        response = await self.client.post("/search_platform_items", json={"query": query})
        response.raise_for_status()
        return response.json()

    async def update_platform_cart(self, items: list) -> dict:
        response = await self.client.post("/update_platform_cart", json={"items": items})
        response.raise_for_status()
        return response.json()

    async def place_platform_order(self, cart_id: str) -> dict:
        response = await self.client.post("/place_platform_order", json={"cart_id": cart_id})
        response.raise_for_status()
        return response.json()


mcp_client = PreFillMCPClient()
```

**`backend/main.py`** — wire the client lifecycle into the app lifespan:

```python
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from backend.api.routes import household, predictions, restock, recipes, prices, orders
from backend.notifications import whatsapp
from backend.database.connection import init_db
from backend.notifications.scheduler import start_scheduler, stop_scheduler
from backend.mcp.client import mcp_client
from backend.config import settings
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        from backend.database.connection import get_checkpointer
        async with await get_checkpointer() as cp:
            await cp.setup()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not connect DB to run checkpointer setup (DB likely offline): {e}")

    await mcp_client.startup()
    start_scheduler()
    yield
    await mcp_client.shutdown()
    stop_scheduler()


app = FastAPI(
    title="Instamart Intelligence API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(household.router)
app.include_router(predictions.router)
app.include_router(restock.router)
app.include_router(recipes.router)
app.include_router(prices.router)
app.include_router(orders.router)
app.include_router(whatsapp.router)


@app.get("/health")
async def health():
    from backend.notifications.scheduler import scheduler
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    return {"status": "ok", "version": "1.0.0", "scheduled_jobs": jobs}


@app.get("/")
async def root():
    return {"message": "Welcome to Instamart Intelligence API"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)  # was: "main:app" (wrong module path)
```

**`backend/database/connection.py`** — pool tuning (part of §2.1 item 2):

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.config import settings

# Explicit pool sizing + pre-ping for a long-running API process.
# (Previous comment claimed NullPool but never actually passed poolclass —
# NullPool is correct for Alembic's short-lived env.py, not for this engine.)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # avoids stale-connection errors after DB idle periods
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from backend.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_checkpointer():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return AsyncPostgresSaver.from_conn_string(db_url)
```

> `conftest.py` already monkeypatches `create_async_engine` to force `StaticPool` for tests (`kwargs["poolclass"] = StaticPool`), which overrides `pool_size`/`max_overflow`/`pool_pre_ping` for SQLite anyway — no test changes needed here.

---

## 3.4 DRY Refactors (M1–M2)

### M1 — one canonical fuzzy/catalog matcher

**New file — `backend/ml/text_matching.py`:**

```python
"""
Shared text-matching utilities — Levenshtein distance, fuzzy word matching,
and catalog lookup. Previously duplicated (with drifting thresholds) across
restock_agent.py, recipe_agent.py, and seed/catalog.py.
"""

import string
from typing import Optional, Sequence


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def is_fuzzy_match(w1: str, w2: str) -> bool:
    """Substring match first, then Levenshtein distance scaled by word length."""
    w1, w2 = w1.lower().strip(), w2.lower().strip()
    if len(w1) < 3 or len(w2) < 3:
        return w1 == w2
    if w1 in w2 or w2 in w1:
        return True
    dist = levenshtein_distance(w1, w2)
    max_len = max(len(w1), len(w2))
    if max_len <= 4:
        return dist <= 1
    elif max_len <= 7:
        return dist <= 2
    return dist <= 3


def normalize_plural(word: str) -> str:
    """Crude English plural stripper: tomatoes -> tomato, eggs -> egg."""
    if word.endswith("es"):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def clean_words(text: str, min_len: int = 3) -> list[str]:
    """Lowercase, strip punctuation, split, and drop short words."""
    cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
    return [w for w in cleaned.split() if len(w) >= min_len]


def find_best_catalog_match(
    query: str,
    catalog: Sequence[dict],
    name_key: str = "name",
    id_key: str = "id",
) -> Optional[dict]:
    """
    Find the best catalog/pantry item for a free-text query using, in order:
    exact id/name match -> substring match -> plural-normalized word overlap
    -> Levenshtein fallback. Single canonical implementation used by the
    restock agent, recipe agent, and MCP catalog lookup — previously three
    separate, slightly different matchers.
    """
    if not query or not catalog:
        return None
    query_lower = query.lower().strip()

    for item in catalog:
        if str(item.get(id_key, "")).lower() == query_lower or str(item.get(name_key, "")).lower() == query_lower:
            return item

    for item in catalog:
        name_lower = str(item.get(name_key, "")).lower()
        if name_lower and (query_lower in name_lower or name_lower in query_lower):
            return item

    query_words = [normalize_plural(w) for w in clean_words(query_lower)]
    for item in catalog:
        name_words = [normalize_plural(w) for w in clean_words(str(item.get(name_key, "")).lower())]
        for qw in query_words:
            for nw in name_words:
                if qw in nw or nw in qw:
                    return item

    for item in catalog:
        name_lower = str(item.get(name_key, "")).lower()
        for w1 in clean_words(query_lower):
            for w2 in clean_words(name_lower):
                if is_fuzzy_match(w1, w2):
                    return item

    return None
```

**`backend/seed/catalog.py`** — becomes a thin wrapper (deletes ~75 lines of duplicated matching code):

```python
"""
Canonical product catalog for PreFill.
This is the single source of truth for item IDs, names, categories, prices, and units.
"""

from backend.ml.text_matching import find_best_catalog_match

CATALOG = [
    {"id": "INS_001", "name": "Amul Taza Milk 1L",           "category": "dairy",      "price": 28.0,  "price_per_unit": 28.0,  "unit": "L"},
    {"id": "INS_002", "name": "Aashirvaad Atta 5kg",          "category": "staples",    "price": 198.0, "price_per_unit": 39.6,  "unit": "kg"},
    {"id": "INS_003", "name": "Fortune Sunflower Oil 1L",     "category": "staples",    "price": 127.0, "price_per_unit": 127.0, "unit": "L"},
    {"id": "INS_004", "name": "India Gate Basmati Rice 5kg",  "category": "staples",    "price": 310.0, "price_per_unit": 62.0,  "unit": "kg"},
    {"id": "INS_005", "name": "Nandini Eggs (Pack of 12)",    "category": "protein",    "price": 84.0,  "price_per_unit": 7.0,   "unit": "piece"},
    {"id": "INS_006", "name": "Tomatoes (500g)",               "category": "vegetables", "price": 29.0,  "price_per_unit": 58.0,  "unit": "kg"},
    {"id": "INS_007", "name": "Onions (1kg)",                  "category": "vegetables", "price": 42.0,  "price_per_unit": 42.0,  "unit": "kg"},
    {"id": "INS_008", "name": "Amul Butter 500g",             "category": "dairy",      "price": 270.0, "price_per_unit": 540.0, "unit": "kg"},
    {"id": "INS_009", "name": "Amul Fresh Cream 200ml",       "category": "dairy",      "price": 55.0,  "price_per_unit": 275.0, "unit": "L"},
    {"id": "INS_010", "name": "Tata Salt 1kg",                "category": "staples",    "price": 28.0,  "price_per_unit": 28.0,  "unit": "kg"},
    {"id": "INS_011", "name": "Britannia Whole Wheat Bread",  "category": "bakery",     "price": 50.0,  "price_per_unit": 50.0,  "unit": "400g"},
    {"id": "INS_012", "name": "Farm Fresh Onion 1kg",         "category": "vegetables", "price": 45.0,  "price_per_unit": 45.0,  "unit": "kg"},
]


def lookup_catalog_item(query: str) -> dict | None:
    """Find a catalog item by name or id using the shared fuzzy matcher."""
    return find_best_catalog_match(query, CATALOG, name_key="name", id_key="id")


def format_restock_alert_message(items: list[dict]) -> str:
    """Format a list of depleting items into a detailed restock alert message."""
    if not items:
        return "No items depleting within threshold window."

    lines = []
    total_amount = 0.0

    for item in items:
        item_name = item.get("item_name") or item.get("name") or "Unknown Item"
        cat = lookup_catalog_item(item_name)

        name = cat["name"] if cat else item_name
        price = cat["price"] if cat else 0.0
        category = cat["category"] if cat else "unknown"
        unit = cat["unit"] if cat else "N/A"
        qty = 1

        total_amount += price * qty
        info_parts = [f"Category: {category}", f"Unit: {unit}"]

        if "confidence_score" in item:
            conf = int(item["confidence_score"] * 100)
            info_parts.append(f"Confidence: {conf}%")
        elif "confidence_label" in item:
            info_parts.append(f"Confidence: {item['confidence_label']}")

        if "days_remaining" in item:
            info_parts.append(f"Days remaining: {item['days_remaining']}")

        info_str = ", ".join(info_parts)
        lines.append(f"• {name} (Qty: {qty}) - Price: ₹{price:.0f} ({info_str})")

    items_list_str = "\n".join(lines)
    message = (
        "[ALERT] Running low on the following items:\n"
        f"{items_list_str}\n\n"
        f"Estimated Total: ₹{total_amount:.0f}\n\n"
        "Reply YES to reorder all, or tell me which ones."
    )
    return message
```

**`backend/agents/restock_agent.py`** — delete the local `levenshtein_distance`/`is_fuzzy_match` and import instead:

```python
# Remove the local levenshtein_distance() and is_fuzzy_match() function
# definitions entirely, and add at the top of the file:
from backend.ml.text_matching import is_fuzzy_match
```

Every other call site in `restock_agent.py` (`parse_user_reply`, `build_cart`) already calls `is_fuzzy_match(...)` by name — the import swap is a drop-in replacement, no other line changes needed.

**`backend/agents/recipe_agent.py::find_pantry_match`** — replace the bespoke implementation with the shared matcher:

```python
from backend.ml.text_matching import find_best_catalog_match

def find_pantry_match(ingredient_name: str, pantry_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fuzzy match ingredient name to closest pantry item using the shared matcher."""
    return find_best_catalog_match(ingredient_name, pantry_items, name_key="item_name", id_key="item_id")
```

This deletes ~35 lines of bespoke substring/token-overlap scoring in `recipe_agent.py` while keeping its call site (`identify_missing_node`) completely unchanged.

### M2 — one canonical LLM fallback client

**New file — `backend/agents/llm_client.py`:**

````python
"""
Shared multi-provider LLM client — Groq (primary) -> NVIDIA NIM (secondary).
Consolidates what was previously ~4 near-identical try/except blocks
across restock_agent.py and recipe_agent.py into one call site.
"""

import json
import logging
from typing import Any, Optional
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)

GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192"]
NVIDIA_MODELS = ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct", "meta/llama3-70b-instruct"]


def is_groq_configured() -> bool:
    key = settings.GROQ_API_KEY
    return bool(key and key.strip() and "your_key_here" not in key)


def is_nvidia_configured() -> bool:
    key = settings.NVIDIA_API_KEY
    return bool(key and key.strip() and "your_key_here" not in key)


async def _call_openai_compatible(
    url: str, api_key: str, models: list[str], prompt: str,
    system_prompt: Optional[str], json_mode: bool,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_err: Optional[Exception] = None
    for model in models:
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(f"LLM call succeeded: {url} / {model}")
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM call failed: {url} / {model}: {e}")
            last_err = e
            continue
    raise last_err or ValueError(f"Failed to call {url} with any configured model.")


async def call_groq_api(prompt: str, system_prompt: Optional[str] = None, json_mode: bool = False) -> str:
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set.")
    return await _call_openai_compatible(
        "https://api.groq.com/openai/v1/chat/completions",
        settings.GROQ_API_KEY, GROQ_MODELS, prompt, system_prompt, json_mode,
    )


async def call_nvidia_api(prompt: str, system_prompt: Optional[str] = None, json_mode: bool = False) -> str:
    if not settings.NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY is not set.")
    return await _call_openai_compatible(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        settings.NVIDIA_API_KEY, NVIDIA_MODELS, prompt, system_prompt, json_mode,
    )


async def call_llm_with_fallback(
    prompt: str, system_prompt: Optional[str] = None, json_mode: bool = False
) -> Optional[str]:
    """
    Try Groq, then NVIDIA. Returns None (never raises) if neither is
    configured or both fail — callers already handle a falsy result by
    dropping to templates/regex, so this preserves existing behavior
    while removing four copies of this exact fallback chain.
    """
    if is_groq_configured():
        try:
            return (await call_groq_api(prompt, system_prompt, json_mode)).strip()
        except Exception as e:
            logger.error(f"Groq failed, trying NVIDIA: {e}")

    if is_nvidia_configured():
        try:
            return (await call_nvidia_api(prompt, system_prompt, json_mode)).strip()
        except Exception as e:
            logger.error(f"NVIDIA failed: {e}")

    return None


async def call_llm_json_with_fallback(prompt: str, system_prompt: Optional[str] = None) -> Optional[dict]:
    """Same as call_llm_with_fallback, but parses JSON (stripping ```json fences)
    and returns None on any parse failure so callers can fall back safely."""
    raw = await call_llm_with_fallback(prompt, system_prompt, json_mode=True)
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON output: {e}. Raw: {raw[:300]}")
        return None
````

**Example call-site refactor — `backend/agents/restock_agent.py::generate_alert_message`:**

```python
from backend.agents.llm_client import call_llm_with_fallback

async def generate_alert_message(state: RestockState) -> dict:
    from backend.seed.catalog import lookup_catalog_item

    detailed_lines = []
    total_amount = 0.0
    for i in state["depleting_items"]:
        item_name = i.get("item_name") or i.get("name") or "Unknown Item"
        cat = lookup_catalog_item(item_name)
        name = cat["name"] if cat else item_name
        price = cat["price"] if cat else 0.0
        category = cat["category"] if cat else "unknown"
        unit = cat["unit"] if cat else "N/A"
        qty = 1
        total_amount += price * qty
        conf = int(i.get('confidence_score', 0.5) * 100)
        days = round(i.get('days_remaining', 1.0), 1)
        detailed_lines.append(
            f"- {name} (Qty: {qty}) - Price: ₹{price:.0f} (Category: {category}, Unit: {unit}, Confidence: {conf}%, Days remaining: {days})"
        )

    items_text = "\n".join(detailed_lines)

    prompt = (
        f"You are a smart household assistant for PreFill.\n\n"
        f"Items likely running low:\n{items_text}\n\n"
        f"Write a WhatsApp message under 150 words. You MUST list all items from the list above, showing for each item:\n"
        f"- Its whole name\n- Qty: 1\n- Price (e.g. ₹X)\n- Unit and Category\n- Confidence % and Days remaining\n\n"
        f"At the end of the item list, calculate and mention the estimated total amount (Estimated Total: ₹{total_amount:.0f}).\n"
        f"Be friendly but brief. Max 2 emojis. End with: 'Would you like to order them?' "
        f"Mention this is based on their purchase pattern. Write ONLY the message."
    )

    message = await call_llm_with_fallback(prompt)   # was: ~30 lines of duplicated try/Groq/except/try/NVIDIA/except

    if not message:
        item_lines = "\n".join([
            f"• {line[2:]}" if line.startswith("- ") else f"• {line}"
            for line in detailed_lines
        ])
        message = (
            f"🛒 Based on your purchase patterns, you're running low on:\n\n"
            f"{item_lines}\n\nEstimated Total: ₹{total_amount:.0f}\n\nWould you like to order them?"
        )

    return {"response_message": message, "stage": "awaiting_reply"}
```

Apply the identical pattern (replace the "try Groq → except → try NVIDIA → except" block with a single `await call_llm_with_fallback(prompt)` or `await call_llm_json_with_fallback(prompt)` call) to:

- `restock_agent.py::parse_user_reply` (Case 3)
- `restock_agent.py::parse_order_intent`
- `recipe_agent.py::parse_recipe_node`

Each of these currently repeats the same ~25–30 line Groq/NVIDIA block; the refactor is mechanical once `llm_client.py` exists, and removes `is_groq_configured`/`is_nvidia_configured`/`call_groq_api`/`call_nvidia_api` from `restock_agent.py` entirely (import them from `llm_client.py` instead, since `recipe_agent.py` currently imports these four names _from_ `restock_agent.py` — update that import to point at `backend.agents.llm_client` instead).

---

## 3.5 Remaining Medium Fixes (M3–M7)

### M3/M4 — hallucination-safety fix in `recipe_agent.py`

**Structured validation for LLM-parsed ingredients** (prevents one malformed field from dropping the entire recipe):

````python
# backend/agents/recipe_agent.py — add near the top
from pydantic import BaseModel, ValidationError, field_validator

class ParsedIngredient(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "piece"

    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_quantity(cls, v):
        if isinstance(v, str):
            digits = "".join(c for c in v if c.isdigit() or c == ".")
            return float(digits) if digits else 1.0
        return v


async def parse_recipe_node(state: RecipeState) -> RecipeState:
    """Uses an LLM to extract clean, standard Indian ingredients from a recipe name."""
    from backend.agents.llm_client import call_llm_with_fallback
    import json

    recipe_name = state["recipe_name"]
    servings = state["servings"]

    prompt = f"""List all ingredients needed for "{recipe_name}" for {servings} people.
Use standard Indian grocery app names (e.g. "basmati rice" not "long-grain rice", "onions" instead of "red onions").

Return ONLY a JSON array of objects, no conversation, no markdown code block wrapper:
[
  {{"name": "basmati rice", "quantity": 600, "unit": "g"}},
  {{"name": "onions", "quantity": 400, "unit": "g"}},
  {{"name": "fortune sunflower oil", "quantity": 80, "unit": "ml"}}
]

Units must be: g, kg, ml, L, piece, tbsp, tsp"""

    text = await call_llm_with_fallback(prompt)

    if not text:
        logger.warning("All LLM providers unavailable for recipe parsing. Falling back to empty list.")
        state["parsed_ingredients"] = []
        return state

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        raw_ingredients = json.loads(text)
    except Exception as e:
        logger.error(f"Failed to parse recipe JSON ingredients: {e}. Raw text: {text}")
        state["parsed_ingredients"] = []
        return state

    validated = []
    for raw in raw_ingredients:
        try:
            validated.append(ParsedIngredient(**raw).model_dump())
        except (ValidationError, TypeError) as ve:
            logger.warning(f"Dropping malformed ingredient from LLM output: {raw} ({ve})")

    state["parsed_ingredients"] = validated
    return state
````

**Stop silently fabricating fake catalog prices — `recipe_agent.py::search_items_node`:**

```python
from backend.ml.text_matching import find_best_catalog_match
import uuid

async def search_items_node(state: RecipeState) -> RecipeState:
    """Searches the PreFill catalog for each missing item to find standard products and prices."""
    missing_items = state["missing_items"]
    cart_items = []
    estimated_cost = 0.0

    for item in missing_items:
        try:
            res = await mcp_client.search_platform_items(item["name"])
            catalog_items = res.get("items", [])
            match = find_best_catalog_match(item["name"], catalog_items, name_key="name", id_key="id")

            if match:
                cart_items.append({
                    "item_id": match["id"],
                    "item_name": match["name"],
                    "quantity": 1,
                    "price": float(match.get("price", 50.0)),
                    "matched": True,   # NEW additive field
                })
                estimated_cost += float(match.get("price", 50.0))
            else:
                cart_items.append({
                    "item_id": f"MOCK_{str(uuid.uuid4())[:8]}",
                    "item_name": f"{item['name']} (Standard Pack)",
                    "quantity": 1,
                    "price": 50.0,
                    "matched": False,  # NEW — flags this as an estimate, not a real catalog hit
                })
                estimated_cost += 50.0
        except Exception as e:
            logger.error(f"Error searching item {item['name']}: {e}")
            cart_items.append({
                "item_id": f"MOCK_{str(uuid.uuid4())[:8]}",
                "item_name": f"{item['name']} (Standard Pack)",
                "quantity": 1,
                "price": 50.0,
                "matched": False,
            })
            estimated_cost += 50.0

    state["cart_items"] = cart_items
    state["estimated_cost"] = round(estimated_cost, 2)
    return state
```

> The `price`/`item_id` types and values are unchanged from before (still a numeric 50.0 placeholder, still a `MOCK_...` id) — only one new boolean field is added. This is a strictly additive contract change: existing frontend code that ignores unknown JSON keys keeps working exactly as before, but now has the option to visually flag `"matched": false` items as estimates.

### M5 — `backend/api/routes/orders.py` reads from Postgres instead of a drifting JSON file

```python
"""
Orders API — returns past order history for a household.

Reads from Postgres (Order.raw_data, populated by sync_service on every
sync) as the primary source, since that's also what feeds the ML models —
previously this endpoint read a separate flat JSON file that could
silently drift from the DB (see Phase 1, M5). Falls back to the JSON file
only for households that haven't synced yet.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from pathlib import Path

from backend.database.connection import get_db
from backend.database.models import Household, Order

router = APIRouter(prefix="/api/orders", tags=["orders"])

ORDERS_FILE = Path(__file__).parent.parent.parent / "seed" / "generated_orders.json"


@router.get("/{user_id}")
async def get_orders(user_id: str, limit: int = 30, db: AsyncSession = Depends(get_db)):
    """
    Return the last N orders for a user, newest first.
    Response shape is unchanged: {"user_id", "total", "orders": [...]}
    where each order dict matches the original seed/mock-server format
    exactly, because Order.raw_data stores that exact dict.
    """
    hh_result = await db.execute(select(Household).where(Household.user_id == user_id))
    hh = hh_result.scalar_one_or_none()

    if hh:
        stmt = (
            select(Order.raw_data)
            .where(Order.household_id == hh.id)
            .order_by(Order.placed_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        db_orders = [row[0] for row in result.all() if row[0] is not None]
        if db_orders:
            return {"user_id": user_id, "total": len(db_orders), "orders": db_orders}

    # Fallback: household not synced yet — read the seed file directly.
    if not ORDERS_FILE.exists():
        return {"user_id": user_id, "orders": [], "total": 0}
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            all_orders = json.load(f)
    except Exception:
        return {"user_id": user_id, "orders": [], "total": 0}

    user_orders = [o for o in all_orders if o.get("user_id") == user_id]
    user_orders.sort(key=lambda o: o.get("placed_at", ""), reverse=True)
    user_orders = user_orders[:limit]
    return {"user_id": user_id, "total": len(user_orders), "orders": user_orders}
```

### M6 — actually convert `price_history` into a TimescaleDB hypertable

See §3.6 below — bundled into the new Alembic migration.

### M7 — small fixes already folded into the diffs above

- ✅ `main.py`'s broken `__main__` entrypoint (`"main:app"` → `"backend.main:app"`) — fixed in §3.3 H6 diff.
- ✅ Stale `NullPool` comment in `connection.py` — fixed in §3.3 H6 diff (now explicit pool sizing, comment corrected).
- ✅ Per-row `db.flush()` in `sync_service.py` — fixed in §3.3 H3 diff (client-side UUIDs).
- ✅ App title "PreFill API" → "Instamart Intelligence API" — fixed in §3.3 H6 diff.

**Optional — reapply the active demo scenario once at startup** (replaces the removed per-request behavior from C3, if you relied on it for resilience across restarts):

```python
# backend/main.py — inside lifespan(), after start_scheduler(), BEFORE yield.
# Optional convenience: on a completely fresh DB (zero orders), reapply the
# last-saved demo scenario once. Unlike the old behavior, this runs at most
# once per process start, never on a per-request basis.
try:
    import os, json
    from sqlalchemy import select, func
    from backend.database.connection import AsyncSessionLocal
    from backend.database.models import Order

    active_scenario_path = os.path.join(os.path.dirname(__file__), "active_scenario.json")
    if os.path.exists(active_scenario_path):
        with open(active_scenario_path) as f:
            scenario = json.load(f).get("scenario", "standard")
        async with AsyncSessionLocal() as db:
            count = (await db.execute(select(func.count()).select_from(Order))).scalar()
            if not count:
                from backend.api.routes.household import reset_scenario_data
                await reset_scenario_data("demo_user_001", scenario, db)
                logging.getLogger(__name__).info(f"Reapplied scenario '{scenario}' on fresh-DB startup.")
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Skipped scenario reapply on startup: {e}")
```

---

## 3.6 New Alembic Migration

Consolidates C4 (unique constraint), the new `Order` composite index, and M6 (TimescaleDB hypertable conversion) into one migration.

**`backend/migrations/versions/b7c1a9e3f001_data_integrity_and_hypertable.py`:**

```python
"""data_integrity_and_hypertable

Adds the household_id+item_id uniqueness guarantee that ARCHITECTURE.md
already documented but was never actually created, a composite index to
speed up the orders lookup, and converts price_history into a real
TimescaleDB hypertable (previously only documented, never executed).

Revision ID: b7c1a9e3f001
Revises: a6a0f2040782
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op

revision = 'b7c1a9e3f001'
down_revision = 'a6a0f2040782'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- C4: prevent duplicate consumption-model rows under concurrent rebuilds ---
    op.create_unique_constraint(
        'uq_consumption_model_household_item',
        'consumption_models',
        ['household_id', 'item_id'],
    )

    # --- Speeds up GET /api/orders/{user_id} (Order.household_id + placed_at) ---
    op.create_index(
        'ix_orders_household_placed_at', 'orders', ['household_id', 'placed_at']
    )

    # --- M6: price_history was documented as a hypertable but never converted ---
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute(
        "SELECT create_hypertable("
        "'price_history', 'recorded_at', "
        "if_not_exists => TRUE, migrate_data => TRUE"
        ");"
    )
    op.execute(
        "ALTER TABLE price_history SET ("
        "timescaledb.compress, timescaledb.compress_segmentby = 'item_id'"
        ");"
    )
    op.execute(
        "SELECT add_compression_policy('price_history', INTERVAL '30 days', if_not_exists => TRUE);"
    )


def downgrade() -> None:
    op.execute("SELECT remove_compression_policy('price_history', if_exists => TRUE);")
    op.drop_index('ix_orders_household_placed_at', table_name='orders')
    op.drop_constraint('uq_consumption_model_household_item', 'consumption_models', type_='unique')
```

> This migration is Postgres/TimescaleDB-specific (`create_hypertable`, compression policies don't exist on plain Postgres or SQLite). That's fine — your test suite uses `Base.metadata.create_all()` via `init_db()`, not Alembic, so `pytest` never runs this migration. Run it against your real `docker-compose` TimescaleDB instance with `alembic upgrade head`.

---

## 3.7 Config & Dependency Changes

**`.env.example`** — add the new optional settings (defaults preserve today's behavior exactly):

```text
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/instamart_intelligence
MCP_BASE_URL=http://localhost:8001
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
ALERT_THRESHOLD_DAYS=7
MIN_CONFIDENCE=0.50
GROQ_API_KEY=
NVIDIA_API_KEY=

# NEW — all optional, defaults match current behavior exactly
ENVIRONMENT=development
CORS_ALLOWED_ORIGINS=http://localhost:3000
REDIS_URL=
```

**`requirements.txt`** — one new optional dependency for the Redis caching/idempotency layer (§2.2). Everything else in the app works identically if you skip this:

```text
# ── Optional: response caching + webhook idempotency (Phase 2, off by default) ──
redis==5.2.1
```

**New file — `backend/services/cache.py`** (implements §2.2's Redis proposal — every function is a safe no-op when `REDIS_URL` is unset):

```python
"""
Optional Redis-backed response cache and idempotency helper.
No-ops entirely when REDIS_URL isn't configured — the app must behave
identically with zero additional infrastructure.
"""

import json
import logging
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)
_redis = None


async def _get_redis():
    global _redis
    if _redis is None and settings.REDIS_URL:
        import redis.asyncio as redis
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def get_cached(key: str) -> Optional[dict]:
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"Cache read failed for {key}: {e}")
        return None


async def set_cached(key: str, value: dict, ttl_seconds: int = 30) -> None:
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for {key}: {e}")


async def delete_cached(key: str) -> None:
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")


async def is_duplicate_webhook_delivery(message_sid: str) -> bool:
    """
    Idempotency guard for Twilio webhook retries: returns True only if
    this MessageSid has already been processed in the last 24h. Always
    returns False (never blocks) when Redis isn't configured.
    """
    if not message_sid:
        return False
    r = await _get_redis()
    if r is None:
        return False
    try:
        was_set = await r.set(f"twilio_msg:{message_sid}", "1", nx=True, ex=86400)
        return not bool(was_set)
    except Exception as e:
        logger.warning(f"Idempotency check failed for {message_sid}: {e}")
        return False
```

**Wiring the idempotency guard into `backend/notifications/whatsapp.py::whatsapp_webhook`** — insert right after the form/JSON payload is parsed (around where `phone`/`message` are extracted), before the household lookup:

```python
from backend.services.cache import is_duplicate_webhook_delivery

# ... inside whatsapp_webhook(), after parsing phone/message:
if not is_json:
    message_sid = str(form_data.get("MessageSid") or "")
    if await is_duplicate_webhook_delivery(message_sid):
        logger.info(f"Ignoring duplicate Twilio webhook delivery for MessageSid={message_sid}")
        return Response(
            content="<Response></Response>",
            media_type="application/xml",
        )
```

**Cache invalidation on the write paths** — add to `backend/api/routes/household.py::rebuild_household_models`:

```python
from backend.services.cache import delete_cached

@router.post("/{user_id}/rebuild-models")
async def rebuild_household_models(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    from backend.ml.consumption_model import ConsumptionModeler

    household = await get_or_create_household(user_id, db)
    household_id = str(household.id)
    modeler = ConsumptionModeler()

    async def _rebuild_then_profile():
        await modeler.rebuild_all_models(household_id, db)
        await update_household_profile(household_id, db)
        await delete_cached(f"predictions:{user_id}")   # NEW

    background_tasks.add_task(_rebuild_then_profile)
    return {
        "message": "Model rebuild + profile inference queued. Check predictions in ~60 seconds.",
        "household_id": household_id
    }
```

(`reset_scenario_data` already got its `delete_cached` call in §3.2's C3 fix.)

---

# File-by-File Change Manifest

| File                                            | Change type                   | Related fix(es) |
| ----------------------------------------------- | ----------------------------- | --------------- |
| `backend/config.py`                             | Add settings                  | H4, H5, §3.7    |
| `backend/main.py`                               | Edit                          | H5, H6, M7      |
| `backend/database/connection.py`                | Edit                          | §2.1            |
| `backend/database/models.py`                    | Edit (add constraint + index) | C4              |
| `backend/api/routes/predictions.py`             | Rewrite                       | C3              |
| `backend/api/routes/household.py`               | Edit (`reset_scenario_data`)  | C3              |
| `backend/api/routes/orders.py`                  | Rewrite                       | M5              |
| `backend/api/routes/restock.py`                 | Edit (one filter clause)      | C2              |
| `backend/ml/consumption_model.py`               | Rewrite                       | C1, C2, C4, C5  |
| `backend/ml/text_matching.py`                   | **New file**                  | M1              |
| `backend/agents/llm_client.py`                  | **New file**                  | M2              |
| `backend/agents/restock_agent.py`               | Edit (imports + 4 call sites) | M1, M2          |
| `backend/agents/recipe_agent.py`                | Edit (imports + 3 functions)  | M1, M2, M3, M4  |
| `backend/seed/catalog.py`                       | Simplify                      | M1              |
| `backend/mcp/client.py`                         | Rewrite                       | H6              |
| `backend/mcp/mock_server.py`                    | Edit (locking + async I/O)    | H1              |
| `backend/notifications/whatsapp.py`             | Edit                          | H1, H4, §3.7    |
| `backend/services/sync_service.py`              | Rewrite                       | H3, M7          |
| `backend/services/cache.py`                     | **New file**                  | §2.2, §3.7      |
| `backend/migrations/versions/b7c1a9e3f001_*.py` | **New file**                  | C4, M6          |
| `.env.example`                                  | Add keys                      | §3.7            |
| `requirements.txt`                              | Add `redis` (optional)        | §3.7            |

---

# Testing & Rollout Checklist

Run after **each** numbered step in §3.1, not just at the end:

1. `pytest backend/tests/ -v` — all 16 existing tests must keep passing throughout. None of these fixes should require weakening a test's assertion.
2. After the C1/C2 `consumption_model.py` rewrite specifically: manually call `POST /api/household/demo_user_001/rebuild-models`, then `GET /api/predictions/demo_user_001`, and sanity-check the known seed items:
   - Fortune Sunflower Oil (`INS_003`) should still land near its documented ~14.7-day cycle.
   - Milk (`INS_001`) should still land near ~2.1 days.
   - Confirm `is_anomaly_excluded` doesn't spuriously flip to `true` for every item — the dietary-change detector should only fire on real >60% category drop-offs.
3. After the C3 fix: hit `GET /api/predictions/demo_user_001` twice in a row and confirm `RestockAlert` history (`GET /api/restock/demo_user_001/history`) is untouched between calls — this was previously being wiped every time.
4. After the C4/C5 fix: fire two concurrent `POST /rebuild-models` calls (e.g. `curl` in two terminals at once) and confirm no duplicate `ConsumptionModel` rows appear for the same `(household_id, item_id)`.
5. After the H1 fixes: load-test the WhatsApp webhook with a few concurrent requests and confirm other endpoints (e.g. `GET /health`) stay responsive during a simulated Twilio call (you can temporarily add an `await asyncio.sleep(2)` inside a test double for `Client.messages.create` to verify the event loop isn't blocked).
6. After the Alembic migration (§3.6): run it against your real `docker-compose` TimescaleDB instance (`alembic upgrade head`), not against the SQLite test DB, and confirm `SELECT * FROM timescaledb_information.hypertables;` now lists `price_history`.
7. Full regression: run through the demo script end-to-end (`docs/builders_club_application.md` / `ARCHITECTURE.md` §4.3) — household profile → predictions → WhatsApp alert → confirm → order → recipe-to-cart — once with `REDIS_URL` unset (must work identically to before) and once with a local Redis container (`docker run -p 6379:6379 redis:7`) to confirm caching/idempotency behave as expected.
