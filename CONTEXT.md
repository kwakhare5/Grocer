# CONTEXT.md — Domain Language & Rules
# Read at the START of EVERY session.

---

## Core Entities & Product Purpose

| Term | What it means in THIS app | Never call it |
|---|---|---|
| Grocer | Proactive WhatsApp grocery replenishment assistant & Swiggy Instamart CommercePort | Generic shopping chatbot, standalone supermarket |
| WhatsApp Assistant View | Interactive iPhone 17 Pro proactive replenishment simulator (`CustomerReplenishmentView`) | Dummy chat screen |
| CommercePort | Abstracted quick-commerce logistics port connecting household carts to Swiggy Instamart MCP or mock adapter | Third-party checkout iframe |
| Pantry Depletion Engine | Deterministic household staple consumption model (daily rates, days remaining, fill %) | Random depletion timer |
| Consequential Action Guard | Spec §28.3 & §39.15 safety invariant requiring explicit human authorization (`explicit_confirmation: true`) before checkout | Silent autonomous payment |
| Dark Store Operator | Standalone companion operations platform (`kwakhare5/Dark-store-operator`) | Internal admin page |

---

## Invariants & Design Rules (Never Break)

1. **Decoupled Commerce Boundary:** Customer replenishment connects via `CommercePort` (Mock / Swiggy MCP) with structured order events.
2. **Strict Consequential Action Guard:** Any checkout execution without explicit human confirmation (`explicit_confirmation: true`) must fail with `UnconfirmedCheckoutError` (HTTP 400).
3. **Clean Apple Light UI:** `#FAFAFA` background, `#FFFFFF` cards, `#064E3B` forest emerald accent, `12px` card radius, `8px` button geometry.
4. **Swiss Logistics Typography:** `PP Mori` (primary sans), `Geist Mono` (tabular numbers/clock), strictly upright `PP Editorial New` (accents).
5. **Zero AI Slop:** Pure Lucide React SVG icons; strictly zero emojis in buttons.
6. **Passing Builds:** Always ensure `npm run build` and `npm run lint` exit with 0 errors.
