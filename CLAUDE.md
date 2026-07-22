# CLAUDE.md — Project Context
# Hard cap: 200 lines. Global rules are in C:\Users\kwakh\.gemini\config\AGENTS.md
# Domain terms → CONTEXT.md (read every session)
# Heavy architecture → ARCHITECTURE.md (load on-demand)

---

## 1. PROJECT IDENTITY

**Name:** PreFill
**Goal:** AI-powered smart inventory management system with LangGraph agents for restocking, pricing, and recipe suggestions
**Status:** In Progress
**Stack type:** Python FastAPI backend + LangGraph agents + Next.js frontend (or standalone backend)

---

## 2. TECH STACK

- **Backend:** FastAPI (Python), SQLAlchemy (AsyncSession only), PostgreSQL
- **Agents:** LangGraph with PostgreSQL checkpointer for state persistence
- **ML:** Prophet for time-series consumption forecasting
- **Scheduler:** APScheduler for notifications
- **Notifications:** WhatsApp via `backend/notifications/whatsapp.py`
- **Testing:** pytest

---

## 3. DEV COMMANDS

```bash
# Backend
uvicorn backend.main:app --reload    # start FastAPI dev server
pytest backend/tests/ -v             # run tests — ALL 16 must pass before commit

# If frontend exists
npm run dev                          # start frontend dev server
npm run build                        # must pass before commit
```

---

## 4. LOCAL RULES

1. **Database — AsyncSession always:**
   - Always `AsyncSession` for SQLAlchemy. Sync SQLAlchemy blocks the FastAPI event loop.
   - All DB queries in `backend/api/routes/` — never direct DB calls from inside agents.

2. **Agents — LangGraph, check first:**
   - Restock: `backend/agents/restock_agent.py` (5 graph nodes)
   - Price: `backend/agents/price_agent.py`
   - Recipe: `backend/agents/recipe_agent.py`
   - LangGraph state MUST be saved with PostgreSQL checkpointer — required for persistence across restarts
   - Check `backend/agents/` before writing any new agent logic

3. **MCP / Catalog — keep in sync:**
   - Mock MCP server responses MUST stay synchronized with `backend/seed/catalog.py`
   - If you update `catalog.py`, update `mock_server.py` too. Both or neither.

4. **ML Pipeline:**
   - `ConsumptionModel` uses Prophet — not scikit-learn linear regression
   - ML models live in `backend/ml/` — check before writing new prediction logic
   - Anomaly-excluded items (`is_anomaly_excluded=True`) MUST be filtered from ML training data

5. **Before marking any task done:**
   - `pytest backend/tests/ -v` → all 16 tests pass
   - Verify mock MCP is in sync with `catalog.py`

---

## 5. PROJECT PATTERNS

### File structure
```
/backend
  /api/routes     — all DB queries and API handlers
  /agents         — LangGraph agent definitions
  /ml             — ML models (Prophet-based)
  /notifications  — WhatsApp, APScheduler
  /seed           — catalog.py (source of truth for mock data)
  /tests          — pytest test suite (16 tests)
/mock_server.py   — must stay in sync with seed/catalog.py
```

### Agent node pattern
Each LangGraph agent has exactly N graph nodes. State flows linearly:
input → node1 → node2 → ... → output, checkpointed to PostgreSQL at each step.

---

## 6. MISTAKES TO AVOID

<!-- AI appends here after every VERIFY failure -->
<!-- Format: [YYYY-MM-DD] What went wrong → What to do instead -->

---

## 7. SESSION RESUME

_AI fills this at the END of every session. Read this at the START of the next session._

**Last session date:** [YYYY-MM-DD]

**What we built / changed:**
- [bullet]

**Immediate next task:**
[Describe exactly]

**Open blockers:**
[Anything unresolved]

**Files most recently changed:**
- [file path]
