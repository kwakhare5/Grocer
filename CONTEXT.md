# CONTEXT.md — Domain Language
# Read at the START of EVERY session.

---

## Core Entities & Product Purpose

| Term | What it means in THIS app | Never call it |
|---|---|---|
| Grocer | Brand-agnostic quick commerce predictive inventory showcase & SDK module | App, standalone platform |
| Landing Page | The engineering prototype showcase (`app/page.tsx`) demonstrating applied depletion forecasting & agent flows | Marketing site |
| Phone Mockup | **The real app user interface demo** (`PhoneMockup.tsx`) where visitors test live features | Static image, graphic |
| Item | A product in the user's household inventory (e.g. Milk, Tomatoes, Eggs) | SKU, product, good |
| Restock Alert | AI recommendation sent via 1-tap WhatsApp 24h before stock runs out | Push notice |
| Consumption Velocity | Daily rate of usage modeled per item (`0.48L/day` for milk) | Rate, depletion |
| Simulation Engine | Pure TypeScript depletion math and 5-node state machine (`lib/simulationEngine.ts`) | Backend, mock server |

---

## Business Rules (Never Break)

1. **100% Brand Agnostic:** Never hardcode specific quick commerce brand names in UI/copy.
2. **Single Unified Mobile View:** All Grocer capabilities render inside a single, seamless scrollable tab.
3. **iPhone 16 Pro Hardware Dimensions:** Mockup container locked to 1800 × 3680 pixel ratio (`w-[275px] h-[562px] aspect-[1800/3680] shrink-0 overflow-hidden`).
4. **Zero AI Slop:** No casual emojis in UI buttons, headings, or chat options. Use clean Lucide icons.
5. **Clean Typography:** Display/UI headings in `Outfit`, editorial title accents in `Cambo` (normal weight, no italics).
6. **Passing Builds:** Run `npm run build` (0 warnings/errors) and `npm run lint` after edits.
7. **1:1 Mockup Design System Alignment:** Mock iPhone inner UI MUST use global landing page tokens (`#252525`, `#F6F7F8`, `.card-neutral-droxy`, `.btn-droxy-pill-*`, `.badge-*`).
