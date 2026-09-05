# AGENTS.md — Grocer Project Rules

---

## 1. PROJECT IDENTITY
- **Name:** Grocer
- **Goal:** Proactive household grocery depletion forecasting, conversational WhatsApp restocking assistant, and Swiggy Instamart quick-commerce fulfillment integration (`CommercePort`).
- **Status:** Complete, standalone Next.js + FastAPI application.
- **Companion Repository:** https://github.com/kwakhare5/Dark-store-operator (Autonomous Quick-Commerce Dark Store Fleet Operations Deck).
- **Repo:** https://github.com/kwakhare5/Grocer

---

## 2. TECH STACK
- **Framework:** Next.js 16 (Turbopack) + React 19 + TypeScript 5
- **Styling & UI:** Tailwind CSS v4 + Framer Motion + Lucide React
- **Backend:** Python 3.11+ + FastAPI + Pydantic v2 + SQLite Async
- **Commerce Integration:** Abstracted `CommercePort` with `SwiggyMCPAdapter` & `MockCommerceAdapter`
- **Linting & Code Quality:** ESLint 9

---

## 3. DEV COMMANDS
```bash
npm run dev      # Start Next.js development server on port 3000
npm run build    # Build optimized production bundle
npm run lint     # Run ESLint validation

# Backend
cd backend
pytest tests/    # Run customer commerce test suite
uvicorn backend.main:app --reload --port 8000
```

---

## 4. LOCAL RULES & DESIGN INVARIANTS
1. **Consequential Action Guard:** Spec §28.3 & §39.15 safety invariant strictly requiring explicit user authorization (`explicit_confirmation: true`) before checkout execution.
2. **Zero AI Slop:** Direction 1 Swiss Logistics typography (`PP Mori` primary sans, `Geist Mono` tabular telemetry, and strictly upright `PP Editorial New` editorial accents), crisp Lucide icons, no emojis in buttons.
3. **Single-Source of Truth:** All catalog and customer persona definitions live in `lib/mockData.ts`.
4. **Passing Builds:** Always ensure `npm run build` and `pytest backend/tests` pass with zero regressions.

---

## 5. EXTERNAL DOCS — SWIGGY BUILDERS CLUB
This project integrates Swiggy MCP servers. Before writing Swiggy code, fetch the authoritative docs:
- Index: https://mcp.swiggy.com/builders/llms.txt
- Full text: https://mcp.swiggy.com/builders/llms-full.txt
- Per-page: append `.md` to any https://mcp.swiggy.com/builders/docs/... URL

Use `/docs/reference/{food,instamart,dineout}` for tool schemas and `/docs/operate/errors` for the canonical error taxonomy. Do not invent tool names or parameters.

---

## 6. SESSION RESUME
- **Current State:** Decoupled Subsystem Split Complete & Verified.
  - **Dark Store Operator Platform:** Migrated to standalone repo at `https://github.com/kwakhare5/Dark-store-operator`, initialized, verified with 286/286 pytest tests green and clean build, and pushed to `origin main`.
  - **Grocer WhatsApp Assistant:** Streamlined to focus 100% on the consumer grocery experience, household pantry depletion tracking, interactive WhatsApp iPhone 17 Pro UI, Swiggy Instamart CommercePort, and Consequential Action Guard.
  - **Verification:** 46/46 customer commerce tests passing (100% green). Frontend `npm run lint` passes (0 errors, 0 warnings). `npm run build` passes in 3.8s with Turbopack.
- **Immediate next task:** None. Architecture split and verification complete.
- **Open blockers:** None.
