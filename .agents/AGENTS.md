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

## 5. SESSION RESUME
- **Current State:** Compact iPhone 16 Pro Chassis (275px) & Site-Wide Copy Overhaul Completed.
  - **Phone Sizing & Chassis:** Reverted phone width strictly to `275px` (`aspect-[1800/3680]`) with accurate Dynamic Island inset (`pt-9`), eliminating all oversized appearance.
  - **WhatsApp Header & Call Icons:** Streamlined top bar to `Grocer Assistant ✓` and `Online`, with crisp 14px Video & Phone icons in `#007AFF`. Removed messy reset buttons from header; placed contextual `↺ Restart Demo` in chat.
  - **Native In-Bubble Actions:** Authentic WhatsApp Business quick reply cells attached directly to message cards with crisp hairlines (`border-t border-zinc-150 divide-y`).
  - **Site-Wide Human Copy Overhaul (`/no-ai-slop`):** Stripped robotic jargon across all pages. Simplified navigation to `Home`, `Store Operations`, `WhatsApp Demo`; calculator to `Household Consumption Estimator`; developer section to `Developer Endpoints`; operations sub-bar to `Inventory Table`, `Transfer Decisions`, `Dark Store Map`; and customer view to `Customer WhatsApp & Pantry Simulator`.
  - **Code Quality & Build:** `npm run build` (Turbopack) passes cleanly in 6.9s with 0 errors; `npm run lint` passes with 0 errors and 0 warnings. Codebase graph synchronized via `graphify update .`.
- **Immediate next task:** Production deployment and demo walkthrough.
- **Open blockers:** None.





