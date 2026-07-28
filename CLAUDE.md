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

**Last session date:** 2026-07-28

**What we built / changed:**
- Updated iPhone chassis SVG frame colors to PreFill Dark Charcoal Titanium (`#252525`) in `iphone.tsx`:
  - **Brand Aligned Chassis Color**: Outer Grade-5 Titanium frame filled with PreFill brand ink color `#252525` (`stroke-[#383838]`) and screen bezel trim `#1A1A1A` matching the landing page brand identity.
  - **Card Height & Spacing Uniformity**: Standardized all cards across all tabs (`Pantry`, `Recipes`, `Signals`, `Home`, `Quick`, `Account`) to exact `p-2.5` (10px) padding and `h-8 w-8 rounded-lg` category icon containers for 100% universal height.
- Verified 0 build errors (`npm run build`) and 100% pytest pass (16/16).

**Immediate next task:**
- Ready for next user instruction or feature extension.

**Open blockers:**
- None.

**Files most recently changed:**
- `d:\PreFill\frontend\components\ui\iphone.tsx`
- `d:\PreFill\frontend\components\PhoneMockup.tsx`
- `d:\PreFill\CLAUDE.md`

