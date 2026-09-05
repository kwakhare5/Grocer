# CONTEXT.md — Domain Language & Rules
# Read at the START of EVERY session.

---

## Core Entities & Product Purpose

| Term | What it means in THIS app | Never call it |
|---|---|---|
| Grocer | AI-assisted quick-commerce inventory decision & execution system prototype | Standalone supermarket, SaaS |
| Operations Cockpit | Internal dark store replenishment & decision command center | Admin portal |
| Customer View | Interactive WhatsApp proactive replenishment simulator (`CustomerReplenishmentView`) | Chatbot |
| CommercePort | Abstracted quick-commerce logistics port connecting customer carts to Swiggy MCP or mock dark-store fleet | Third-party checkout iframe |
| Safe Excess | Excess inventory at a source store that can be transferred without creating risk: `inventory - demand - buffer` | Extra stock |
| 4 Decision Actions | Deterministic interventions: `TRANSFER`, `REORDER`, `DISCOUNT`, `HOLD` | LLM guesses |
| WHY Panel | Structured explainability drawer exposing risk probabilities, supplier lead times, safe excess, and alternatives | AI chat response |
| Level-2 Autonomy | Agent executes approved actions with server-side validation; cannot self-execute newly consequential actions | Full auto-pilot |
| Consequential Action Guard | Spec §28.3 & §39.15 safety invariant requiring explicit human authorization (`explicit_confirmation: true`) before checkout | Silent autonomous payment |
| 5 Dark Store Nodes | Mumbai Fleet: `Bandra West`, `Andheri East`, `Powai Galleria`, `Lower Parel`, `Thane West` | Warehouses |

---

## Invariants & Design Rules (Never Break)

1. **Decoupled Commerce Boundary:** Customer replenishment connects via `CommercePort` (Mock / Swiggy MCP) with synchronized order events, preventing direct mutation of internal dark store stock.
2. **Deterministic Decision Engine:** Intervention scoring and safe excess math are deterministic, not hallucinated by LLMs.
3. **Strict Consequential Action Guard:** Any checkout execution without explicit confirmation (`explicit_confirmation: true`) must fail with `UnconfirmedCheckoutError` (HTTP 400).
4. **Clean Apple Light UI:** `#FAFAFA` background, `#FFFFFF` cards, `#064E3B` forest emerald accent, `12px` card radius, `8px` button geometry.
5. **Swiss Logistics Typography:** `Geist Sans` (400 body copy), `TWK Lausanne Pan 800` (display titles), `Geist Mono` (tabular numbers/clock), strictly upright `PP Editorial New` (accents).
6. **Zero AI Slop:** Pure Lucide React SVG icons; strictly zero emojis in buttons.
7. **Passing Builds:** Always ensure `npm run build` and `npm run lint` exit with 0 errors.
