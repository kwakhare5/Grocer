# AGENTS.md — Grocer Project Rules

---

## 1. PROJECT IDENTITY
- **Name:** Grocer
- **Goal:** Intelligent grocery inventory tracking, depletion forecasting, and automated WhatsApp alert assistant prototype.
- **Status:** Complete & Self-Contained Next.js Application
- **Repo:** https://github.com/kwakhare5/Grocer

---

## 2. TECH STACK
- **Framework:** Next.js 16 (Turbopack) + React 19 + TypeScript 5
- **Styling & UI:** Tailwind CSS v4 + Framer Motion + Lucide React
- **Simulation Layer:** Pure TypeScript Depletion Math & 5-Node State Machine (`lib/simulationEngine.ts`)
- **Linting & Code Quality:** ESLint 9

---

## 3. DEV COMMANDS
```bash
npm run dev      # Start Next.js development server on port 3000
npm run build    # Build optimized production bundle
npm run lint     # Run ESLint validation
```

---

## 4. LOCAL RULES & DESIGN INVARIANTS
1. **Zero AI Slop:** Direction 1 Swiss Logistics typography (`PP Mori` primary sans, `Geist Mono` tabular telemetry, and strictly upright `PP Editorial New` editorial accents), crisp Lucide icons, no emojis in buttons.
2. **Single-Source of Truth:** All catalog and customer persona definitions live in `lib/mockData.ts`.
3. **Passing Builds:** Always ensure `npm run build` passes with zero errors and zero type regressions.

---

## 5. EXTERNAL DOCS — SWIGGY BUILDERS CLUB
This project integrates Swiggy MCP servers. Before writing Swiggy code, fetch the authoritative docs:
- Index: https://mcp.swiggy.com/builders/llms.txt
- Full text: https://mcp.swiggy.com/builders/llms-full.txt
- Per-page: append `.md` to any https://mcp.swiggy.com/builders/docs/... URL

Use `/docs/reference/{food,instamart,dineout}` for tool schemas and `/docs/operate/errors` for the canonical error taxonomy. Do not invent tool names or parameters.

---

## 6. SESSION RESUME
- **Current State:** 100% Complete & Verified Across All 10 Master Spec Phases (§38).
  - **All 10 Phases Shipped & Verified:**
    - *Phase 1*: Repository Audit & Bloat Purge complete (zero dead code, legacy SaaS pages deleted, clean tree).
    - *Phase 2*: Backend Source-of-Truth Refactor (`SimulationClock`, SQLite persistence, REST endpoints).
    - *Phase 3*: Data/Model Consistency (Batches as physical inventory truth, strict lifecycle states).
    - *Phase 4*: Simulation Engine (Deterministic Poisson demand, 5 dark stores, benchmark scenarios).
    - *Phase 5*: Forecasting & Risk Engine (Holt double exponential smoothing, 7-dimensional risk scoring).
    - *Phase 6*: Decision Engine (Multi-factor Pareto optimization, 16 reason codes, candidate ranking).
    - *Phase 7*: LangGraph 5-Node Autonomous Execution Agent (Level-2 human approval, FIFO deduction, dynamic recovery).
    - *Phase 8*: Operations UI (3-column control center with dual-mode live backend sync and fallback).
    - *Phase 9*: Customer Replenishment & Swiggy MCP CommercePort (`MockCommerceAdapter`, `SwiggyMCPAdapter`, Consequential Action Guard).
    - *Phase 10*: Testing & Demo Hardening (`test_phase10_demo_hardening.py`, primary/secondary demo narratives verified, Spec §21 invariants locked).
  - **Verification:** 286/286 backend pytest tests passing (100% green). Frontend `npm run lint` passes (0 errors, 0 warnings). `npm run build` passes in 6.8s with Turbopack.
- **Immediate next task:** None. Final production milestone reached.
- **Open blockers:** None.
