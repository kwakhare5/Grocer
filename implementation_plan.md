# Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me)

Clean up the Hero section by removing scenario switcher pills and the outer card container so the raw iPhone 16 Pro mockup sits cleanly on the section canvas. Completely purge all dark mode theme variants, dark cards, dark code terminals, and dark footer callouts across the entire site, replacing them with crisp light slate/sky surfaces and enforcing 100% strict component reuse (`PillButton`, `PillBadge`, `CardSurface`).

## Finalized Architecture & Design Decisions

1. **Clean Hero iPhone Mockup Presentation**:
   - Remove scenario switcher pills (`1-Tap WhatsApp`, `Pantry Velocity`, `Recipe Cart`) above the phone.
   - Remove the outer card container and background glow so the raw iPhone 16 Pro mockup (`PhoneMockup`) sits directly and cleanly on the light hero section background (`bg-[#FCFCFD]`).
   - Interactive sub-tabs stay inside the iPhone screen demo itself.

2. **Complete Dark Mode Theme Purge & Light Theme Alignment**:
   - **No Dark Mode**: Purge all dark mode styles, dark background blocks, dark code containers, and dark card variants.
   - **`PillButton`**: Deprecate `dark` and `shimmer` dark variants. Standardize on `primary` (slate/black pill button), `secondary` (clean border pill button), and `ghost`.
   - **`CardSurface`**: Deprecate `dark` variant. Standardize on `default` (clean white `#FFFFFF` surface with `#E5E7EB` border) and `accent` (`bg-sky-50/60`).
   - **`GrocerIntegrations`**: Replace dark terminal (`bg-gray-950`) with a light, crisp code panel (`bg-[#F8FAFC]` with `#E2E8F0` border and dark slate code text `#0F172A`).
   - **`GrocerFooter`**: Replace giant dark CTA card with a clean light accent surface (`bg-slate-50` with `#E2E8F0` border and dark text).

3. **100% Strict Component Reuse**:
   - Convert all buttons across `GrocerHero`, `GrocerValueProp`, `GrocerVelocityCalculator`, `GrocerIntegrations`, `GrocerFAQ`, and `GrocerFooter` to use `PillButton` and `PillBadge` exclusively.
   - Convert all cards and containers to use `CardSurface` exclusively.

---

## Proposed Changes

### Component 1: Hero Section Clean Up

#### [MODIFY] [`GrocerHero.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerHero.tsx)
- Remove scenario switcher pill buttons above the phone.
- Remove outer container card styling around the iPhone frame so `PhoneMockup` renders directly on `bg-[#FCFCFD]`.

---

### Component 2: Design System Token Clean Up (Dark Mode Purge)

#### [MODIFY] [`PillButton.tsx`](file:///d:/PreFill/frontend/components/ui/PillButton.tsx)
- Purge dark mode variant definitions (`dark`, `shimmer` dark text). Standardize on `primary`, `secondary`, and `ghost`.

#### [MODIFY] [`CardSurface.tsx`](file:///d:/PreFill/frontend/components/ui/CardSurface.tsx)
- Purge `dark` variant. Standardize on light variants (`default`, `accent`, `mesh`).

---

### Component 3: Component-Wide Light Surface Transformation & Component Reuse

#### [MODIFY] [`GrocerIntegrations.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerIntegrations.tsx)
- Transform dark terminal box (`bg-gray-950`) into a crisp light code card (`bg-[#F8FAFC]` border `#E2E8F0`).
- Standardize step cards and cURL copy buttons to use `CardSurface` and `PillButton`.

#### [MODIFY] [`GrocerFooter.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerFooter.tsx)
- Transform giant dark CTA box (`bg-gradient-to-br from-gray-900...`) into a clean light surface (`bg-slate-50 border border-slate-200`).
- Standardize all CTA buttons to use `PillButton`.

#### [MODIFY] [`GrocerValueProp.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerValueProp.tsx) & [`GrocerVelocityCalculator.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerVelocityCalculator.tsx)
- Ensure all bento cards and calculator controls use light surfaces and shared UI components exclusively.

---

## Verification Plan

### Automated Tests
- Run Pytest backend test suite:
  ```powershell
  .\venv\Scripts\python.exe -m pytest backend/tests/ -v
  ```
  *Expected result: 16/16 tests passing.*

- Run Next.js production build check:
  ```powershell
  cd frontend; npm run build
  ```
  *Expected result: Build completes with 0 errors and 0 warnings.*

### Manual Verification
- Verify Hero section: 2-column side-by-side layout with raw iPhone 16 Pro mockup on the right without scenario pills or surrounding box background.
- Verify entire landing page: 0 dark mode blocks, 100% unified light theme (#FCFCFD, #FFFFFF, #F8FAFC, bg-sky-50), crisp typography and component reuse.
