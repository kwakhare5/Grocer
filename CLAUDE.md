# CLAUDE.md — Project Context & Product Vision
# Hard cap: 200 lines. Global rules are in C:\Users\kwakh\.gemini\config\AGENTS.md
# Domain terms → CONTEXT.md (read every session)
# Product Architecture → ARCHITECTURE.md (load on-demand)

---

## 1. PROJECT IDENTITY & PRODUCT VISION

**Name:** PreFill
**Goal:** Intelligent household inventory restock assistant for quick-commerce platforms, predicting grocery stockouts and enabling 1-tap WhatsApp reorders.
**Status:** Live & Production Ready

### Why We Have the Landing Page
The landing page (`app/page.tsx`) is the primary showcase and narrative engine. It explains to quick-commerce operators and users why automated household restocking is essential:
- Eliminates 2 hours of manual grocery reordering every week.
- Recaptures local Kirana store leakage (76% lost grocery spend).
- Lifts 90-day household customer retention floor from 24% to 82%.

### Why We Have the Mockup iPhone
The mockup iPhone (`PhoneMockup.tsx` & `ui/iphone.tsx`) is **the real app demo itself** embedded right inside the landing page hero stage. Instead of reading about features, visitors experience the exact user interface and interaction flow:
- Viewing real-time household pantry depletion velocity (Milk, Tomatoes, Eggs, Bread).
- Testing the Recipe Ingredient Checker to fulfill missing ingredients in 1 tap.
- Monitoring market price signals (Dips & Spikes).
- Triggering 1-tap WhatsApp restocking chat to confirm 10-minute grocery delivery.

---

## 2. TECH STACK

- **Backend:** FastAPI (Python), SQLAlchemy (AsyncSession only), PostgreSQL
- **Agents & ML:** LangGraph restock workflow, Prophet consumption velocity modeling
- **Notifications:** WhatsApp automated restock agent
- **Frontend:** Next.js (TypeScript), Tailwind CSS ("Shade" design system)
- **Testing:** pytest backend suite (16/16 pass) + Next.js build verification

---

## 3. DEV COMMANDS

```bash
# Backend
uvicorn backend.main:app --reload    # start FastAPI dev server
.\venv\Scripts\python.exe -m pytest backend/tests/ -v # run backend tests (16/16 pass)

# Frontend
npm run dev                          # start frontend dev server
npm run build                        # production build verification
```

---

## 4. LOCAL RULES & USER EXPERIENCE PRINCIPLES

1. **Treat the Mockup iPhone as the Real App:**
   - Every button, stepper, recipe card, and WhatsApp chat chip inside `PhoneMockup.tsx` must behave like a live, production mobile application.
   - All interactive actions (adding to cart, recipe fulfillment, WhatsApp replies) must provide instant visual feedback and update pantry stock levels.

2. **Zero Layout Distortion & Scroll Isolation:**
   - Mockup dimensions locked to 6.3" iPhone screen (`w-[305px] h-[638px] aspect-[71.5/149.6] shrink-0 overflow-hidden`).
   - Chat window scroll uses container `scrollTop` so interacting with the phone NEVER jumps the landing page window scroll position.

3. **1:1 Design System Alignment ("Shade"):**
   - Inner phone UI uses landing page design tokens (`#252525`, `#F6F7F8`, `round-card-droxy`, `card-pastel-*`, `btn-droxy-pill-*`, `badge-*`, `Outfit`/`Cambo` fonts).

4. **Database & Backend Integrity:**
   - Always `AsyncSession` for SQLAlchemy.
   - All 16 pytest tests must pass before completing tasks.

---

## 6. MISTAKES TO AVOID

<!-- AI appends here after every VERIFY failure -->
<!-- Format: [YYYY-MM-DD] What went wrong → What to do instead -->

---

## 7. SESSION RESUME

_AI fills this at the END of every session. Read this at the START of the next session._

**Last session date:** 2026-07-29

**What we built / changed:**
- Executed multi-device responsive scaling and viewport optimization across Mobile (`<640px`), Tablet (`640px–1024px`), and Desktop (`>1024px`) viewports while preserving 100% of feature content and desktop controls.
- Enforced `overflow-x-hidden` on main container ([page.tsx](file:///d:/PreFill/frontend/app/page.tsx)) to eliminate horizontal scroll blowouts on small mobile devices (`320px`–`430px`).
- Scaled 4 top KPI cards in [ExecutivePanel.tsx](file:///d:/PreFill/frontend/components/ExecutivePanel.tsx) (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`).
- Upgraded stock percentage chips (`20%`, `65%`, `35%`, `15%`) and price action signal pills (`SPIKE`, `DIP`, `STABLE`, `Stocked`, `Low`) in [PhoneMockup.tsx](file:///d:/PreFill/frontend/components/PhoneMockup.tsx) with crisp `px-2 py-0.5` padding, `font-mono text-[9.5px]` typography, `inline-flex items-center justify-center` vertical alignment, and high-contrast status borders.
- Removed unnecessary nested boxes (`card-neutral-droxy` and inner `bg-stone-50` box container) from Section 4 ("Automate grocery reordering before stock runs out") in [PreFillFeatureSidebar.tsx](file:///d:/PreFill/frontend/components/PreFillFeatureSidebar.tsx), creating a clean, airy single-level canvas for feature titles, descriptions, and motion graphics.
- Verified ESLint (`npm run lint` — 0 warnings / 0 errors) and Next.js production build (`npm run build` — compiled in 4.6s with 0 errors).

**Immediate next task:**
- Ready for next user request.

**Open blockers:**
- None.

**Files most recently changed:**
- `d:\PreFill\frontend\components\ExecutivePanel.tsx`
- `d:\PreFill\frontend\app\page.tsx`
- `d:\PreFill\frontend\components\PhoneMockup.tsx`
- `d:\PreFill\frontend\components\PreFillFeatureSidebar.tsx`
- `d:\PreFill\CLAUDE.md`









