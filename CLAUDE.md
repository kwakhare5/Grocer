# CLAUDE.md — Project Context

# Hard cap: 200 lines. Global rules are in C:\Users\kwakh\.gemini\config\AGENTS.md

# Domain terms → CONTEXT.md (read every session)

# Heavy architecture → ARCHITECTURE.md (load on-demand)

---

## 1. PROJECT IDENTITY

**Name:** PreFill
**Goal:** Brand-agnostic WhatsApp Restock Agent & AI extension for Quick Commerce platforms (Blinkit, Zepto, Instamart) that eliminates Kirana store leakage and automated household stockouts.
**Showcase Web App:** Single-page showcase featuring the **Mockup iPhone (`PhoneMockup.tsx`)** as a Live Interactive Product Prototype, surrounded by the Macro Project Narrative and Executive ROI Analytics (`ExecutivePanel.tsx`).
**Stack type:** Python FastAPI backend + LangGraph agents + Next.js 16 frontend

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

## 6. MISTAKES TO AVOID

<!-- AI appends here after every VERIFY failure -->
<!-- Format: [YYYY-MM-DD] What went wrong → What to do instead -->

---

## 7. SESSION RESUME

_AI fills this at the END of every session. Read this at the START of the next session._

**Last session date:** 2026-07-28

**What we built / changed:**
- **Sensible Pastel Color Distribution & Rebranding ([page.tsx](file:///d:/PreFill/frontend/app/page.tsx), [PreFillFeatureSidebar.tsx](file:///d:/PreFill/frontend/components/PreFillFeatureSidebar.tsx), [PreFillPracticalUse.tsx](file:///d:/PreFill/frontend/components/PreFillPracticalUse.tsx), [PreFillBentoGrid.tsx](file:///d:/PreFill/frontend/components/PreFillBentoGrid.tsx))**:
  - Balanced pastel color highlights across the landing page so the overall design is crisp, clean, and never overly colorful or plain.
  - Kept primary section containers clean off-white (`#F6F7F8` / `#FFFFFF`) and applied subtle pastel badges (`badge-blue`, `badge-green`, `badge-yellow`, `badge-red`) to highlight status indicators, key metrics, and bento grid feature cards.
- **GitHub Commit History**:
  - All changes pushed and synced cleanly to `origin/main` ([`8f9ef30`](https://github.com/kwakhare5/PreFill/commit/8f9ef30)).
- Verified 0 build errors (`npm run build`), 0 lint warnings (`npm run lint`), and 100% pytest pass (16/16).

**Immediate next task:**
- Step 3: Zero-Cost Deployment ($0 Budget) setup on Vercel + Render / Koyeb when requested.

**Open blockers:**
- None. Dev server running on `http://localhost:3000`.

**Files most recently changed:**
- `d:\PreFill\frontend\app\page.tsx`
- `d:\PreFill\CLAUDE.md`







