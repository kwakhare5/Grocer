# AGENTS.md — Project Rules

# Hard cap: 120 lines. Fill Sections 1-4 at project start.
# AI fills Sections 5-7 automatically during development.

---

## 1. PROJECT IDENTITY

**Name:** PreFill
**Goal:** High-conversion business carrier & predictive restock platform.
**Status:** In Progress
**Repo:** Local d:\PreFill

---

## 2. TECH STACK

- **Frontend:** Next.js 16 (Turbopack), React 19, Tailwind CSS v4
- **Backend:** FastAPI (Python), SQLAlchemy (AsyncSession), PostgreSQL
- **UI System:** PreFill Design System (`Outfit` sans, `Cambo` serif, custom pill buttons & card surfaces)
- **Language:** TypeScript + Python

---

## 3. DEV COMMANDS

```bash
# Frontend
npm run dev        # start dev server
npm run build      # production build
npm run lint       # ESLint + TypeScript check

# Backend
uvicorn backend.main:app --reload
pytest
```

---

## 4. ENGINEERING PRINCIPLES

- Simplest implementation that fully meets current requirements.
- Modular, well-scoped components in `frontend/components/prefill/`.
- Standardized design system tokens in `frontend/app/globals.css`.

---

## 7. SESSION RESUME

**Last session date:** 2026-08-10

**What we built / changed:**
- **Dead Code Purge & Shared Primitive Refactoring**: (1) Purged dead file `frontend/components/ui/iphone.tsx` and removed unused `Iphone` import from `PhoneMockup.tsx`, (2) Refactored all section components (`PreFillMeasurableValue`, `PreFillIntegrations`, `PreFillFAQ`, `PreFillAppPreview`, `PreFillTestimonialSection`) to consume deep `<CardSurface>`, `<PillBadge>`, and `<PillButton>` primitives, and (3) Achieved zero code duplication across UI cards.
- **Verification**: `npx tsc --noEmit` (0 errors) & `npm run build` compiled in 2.7s with 0 warnings or errors.

**Immediate next task:**
- Ready for next user feature request or deployment.

**Open blockers:**
- None.

**Files most recently changed:**
- `frontend/components/PhoneMockup.tsx`
- `frontend/components/prefill/PreFillMeasurableValue.tsx`
- `frontend/components/prefill/PreFillIntegrations.tsx`
- `frontend/components/prefill/PreFillFAQ.tsx`
