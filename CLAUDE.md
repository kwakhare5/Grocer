# CLAUDE.md — Local Rules & Project Instructions
# Read at the START of EVERY session.

---

## 1. STACK & ARCHITECTURE

- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS v4 (`@import "tailwindcss";`), Lucide SVG icons, Framer Motion.
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy (async via `asyncpg`/`aiosqlite`), Pydantic v2.
- **ML / AI:** Prophet (`ml/consumption_model.py` per-item consumption modeling), LangGraph (`agents/restock_agent.py` 5-node state graph with PostgreSQL checkpointer).
- **Design Tokens:** Canvas (`#F6F7F8`), Text (`#252525`), Secondary (`#64717E`), Cards (`bg-white border-stone-200 shadow-sm rounded-2xl`), Buttons (`btn-droxy-pill-primary`, `btn-droxy-pill-secondary`).
- **Strict 2-Font System:** Body/UI: `Outfit` (`var(--font-outfit)`). Titles: `Cambo` (`var(--font-cambo)`). No default browser fonts.

---

## 2. COMMANDS

```bash
# Frontend (run inside ./frontend)
npm run dev        # Dev server at http://localhost:3000
npm run lint       # Run ESLint (must be 0 errors, 0 warnings)
npm run build      # Production build check

# Backend (run inside root with virtualenv active)
.\venv\Scripts\python.exe -m pytest backend/tests/ -v   # Run full test suite (16 tests)
fastapi dev backend/main.py                              # FastAPI dev server at http://localhost:8000
```

---

## 3. CODING RULES (Strict Enforce)

1. **Brand Agnostic (Rule #1):** 100% brand-agnostic. Never hardcode brand names in UI or copy.
2. **Zero AI Slop:** No casual emojis in UI buttons, headings, or chat options. Use clean Lucide SVG icons.
3. **iPhone 16 Pro Ratio:** Phone mockup container locked to `w-[305px] aspect-[71.5/149.6]`.
4. **Passing Tests:** Run pytest (16/16) and frontend build after every edit before declaring complete.

---

## 4. DOMAIN TERMS (From CONTEXT.md)

- **Item:** A product in user's inventory (not product, SKU).
- **Restock:** AI-generated recommendation to purchase more of an Item.
- **Consumption:** Daily velocity of item usage via Prophet model.
- **Anomaly:** Irregular purchase spike excluded from ML training.
- **Depletion Date:** Predicted date when item stock hits 0.

---

## 5. MISTAKES TO AVOID

- Do NOT use emojis in CTA buttons, badges, or section headers.
- Do NOT hardcode third-party quick commerce brand names in UI text.
- Do NOT use standard browser fonts — enforce `Outfit` and `Cambo`.
- Do NOT introduce unhandled exceptions or stub returns in API endpoints.

---

## 6. VERIFICATION LOOP

```bash
npm run lint
npm run build
.\venv\Scripts\python.exe -m pytest backend/tests/ -v
```

---

## 7. SESSION RESUME

_AI fills this at the END of every session. Read this at the START of the next session._

**Last session date:** 2026-07-28 (Synced)

**What we built / changed:**
- **PreFill Project Domain Copywriting Rewrite ([PreFillFeatureSidebar.tsx](file:///d:/PreFill/frontend/components/PreFillFeatureSidebar.tsx), [PreFillPracticalUse.tsx](file:///d:/PreFill/frontend/components/PreFillPracticalUse.tsx), [PreFillBentoGrid.tsx](file:///d:/PreFill/frontend/components/PreFillBentoGrid.tsx), [page.tsx](file:///d:/PreFill/frontend/app/page.tsx))**:
  - Aligned 100% of website copy with `CONTEXT.md` project domain rules:
    - **Ultra Short & Crisp Hero Copy**:
      - Badge: `Predictive Household Inventory Engine`
      - H1: `Predict stockouts. Automate restocks.`
      - Subtitle: `PreFill models daily consumption velocity to trigger 1-tap WhatsApp grocery orders 24h before items run out.`
      - CTAs: `Try Prototype` & `View ROI`.
    - **Technical Feature Showcases**: Prophet ML Depletion Modeling, LangGraph Restock Agent, Recipe Gap Analyzer, Commodity Price Signals, and Anomaly Exclusion Engine.
    - Enforced 100% brand-agnostic copy (Business Rule 1).
- **GitHub Heatmap & Commit Sync**:
  - Pushed all commits cleanly to `origin/main` for today's date (`2026-07-28`).
- Verified 0 build errors (`npm run build`), 0 lint warnings (`npm run lint`), and 100% pytest pass (16/16).

**Immediate next task:**
- Step 3: Zero-Cost Deployment ($0 Budget) setup on Vercel + Render / Koyeb when requested.

**Open blockers:**
- None. Dev server running on `http://localhost:3000`.

**Files most recently changed:**
- `d:\PreFill\frontend\components\PreFillFeatureSidebar.tsx`
- `d:\PreFill\frontend\components\PreFillPracticalUse.tsx`
- `d:\PreFill\frontend\components\PreFillBentoGrid.tsx`
- `d:\PreFill\frontend\app\page.tsx`
- `d:\PreFill\CLAUDE.md`
