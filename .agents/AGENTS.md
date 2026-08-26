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
1. **Zero AI Slop:** Clean typography (`Outfit` and `Cambo`), crisp Lucide icons, no emojis in buttons.
2. **Single-Source of Truth:** All catalog, recipe, and price signal definitions live in `lib/mockData.ts`.
3. **Passing Builds:** Always ensure `npm run build` passes with zero errors and zero type regressions.

---

## 5. SESSION RESUME
**Last session date:** 2026-08-26
- **Current State:** Full codebase cleaned up and restructured into a pure Next.js 16 + React 19 application. Removed over-engineered Python backend, deleted 15k+ lines of dead code/databases/virtualenvs, unified all simulation math in `lib/simulationEngine.ts`, and verified 0 errors with `npm run build` and `npm run lint`.
- **Immediate next task:** None. Production ready.
- **Open blockers:** None.
