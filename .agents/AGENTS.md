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
- **Current State:** Whole-Codebase Audit, Bloat Purge & Dual-Workflow Architecture Refactoring Complete & 100% Verified.
  - **Purged Legacy SaaS Marketing Landing Page:** Deleted `components/grocer/` (6 files, 637 lines), `hooks/usePantryEngine.ts`, and 6.5+ MB of unreferenced assets (`wallpaper.png`, `figma.zip`, `grocer-app-icons-master.svg`) in strict alignment with Spec §3 and §24.
  - **Removed Competing Simulation Code:** Deleted non-authoritative `lib/simulationEngine.ts` per Spec §27.1; colocated pure presentation helper routines directly inside `hooks/usePhoneDemoEngine.ts`.
  - **Domain Colocation & Streamlined UI:** Relocated `PhoneMockup.tsx` into `components/customer/PhoneMockup.tsx`. Streamlined `CustomerReplenishmentView.tsx` (pruned ~340 lines of static `storyboard` slides and `showcase` badges), standardizing on the high-signal 3-column Workbench + Consequential Action Guard modal.
  - **Direct Dual-Workflow App Root:** Refactored `AppGlobalHeader.tsx` and `app/page.tsx` for immediate access to `Store Operations` and `Customer Replenishment` (Spec §5 Two Workflows).
  - **Cleaned Backend Vestiges:** Removed 4 empty unused backend directories (`backend/tools/`, `backend/services/inventory/`, `backend/services/metrics/`, `backend/services/recommendation/`).
  - **Verification:** 281/281 pytest tests passing across all 8 phases. Frontend `npm run lint` passes (0 errors, 0 warnings). `npm run build` passes in 6.6s with Turbopack. Knowledge graph rebuilt (2,076 nodes, 4,740 edges).
- **Immediate next task:** Production Polish & Live Swiggy Instamart MCP Connection Verification.
- **Open blockers:** None.
