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
- **Current State:** iPhone Chassis Calibrated to 290px, Duplicate Label Glitch Fixed & WhatsApp Spacing Refined.
  - **Chassis Dimensions:** Calibrated phone chassis to `290px` (`w-[290px] h-[593px] aspect-[1800/3680]`) in both `GrocerHero.tsx` and `PhoneMockup.tsx`.
  - **Duplicate Plus Glitch:** Fixed `+ + Bread` to single `<Plus /> <span>Add Bread (₹50)</span>` in `PhoneMockup.tsx`.
  - **Quick Action Ergonomics:** Upgraded quick reply button rows to `py-2` for full-width buttons and `py-1.5 px-2` for split rows (`Remind Later` | `Not Now`) with centered Lucide `Clock` icon and hairline dividers.
  - **Bubble Typography & Spacing:** Refined body copy to `10px`, timestamps to `7.5px`, card padding to `p-2.5`, and max bubble width to `90%`.
  - **Code Quality & Build:** `npm run build` passes cleanly in 5.3s with 0 errors; `npm run lint` passes with 0 warnings. Code graph updated.
- **Immediate next task:** Production deployment or customer walkthrough.
- **Open blockers:** None.
