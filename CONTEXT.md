# CONTEXT.md — Domain Language & Rules
# Read at the START of EVERY session.

---

## Core Entities & Product Purpose

| Term | What it means in THIS app | Never call it |
|---|---|---|
| Grocer | AI-assisted quick-commerce inventory decision & execution system prototype | Standalone supermarket, SaaS |
| Operations Cockpit | Internal dark store replenishment & decision command center | Admin portal |
| Customer View | Interactive WhatsApp proactive replenishment simulator (`CustomerReplenishmentView`) | Chatbot |
| Safe Excess | Excess inventory at a source store that can be transferred without creating risk: `inventory - demand - buffer` | Extra stock |
| 4 Decision Actions | Deterministic interventions: `TRANSFER`, `REORDER`, `DISCOUNT`, `HOLD` | LLM guesses |
| WHY Panel | Structured explainability drawer exposing risk probabilities, supplier lead times, safe excess, and alternatives | AI chat response |
| Level-2 Autonomy | Agent executes approved actions with server-side validation; cannot self-execute newly consequential actions | Full auto-pilot |
| 5 Dark Store Nodes | Mumbai Fleet: `Bandra West`, `Andheri East`, `Powai Galleria`, `Lower Parel`, `Thane West` | Warehouses |

---

## Invariants & Design Rules (Never Break)

1. **Two-Sided Shared World:** Customer WhatsApp reorders and Operations replenishment modify the exact same simulation state.
2. **Deterministic Decision Engine:** Intervention scoring and safe excess math are deterministic, not hallucinated by LLMs.
3. **Clean Apple Light UI:** `#FAFAFA` background, `#FFFFFF` cards, `#064E3B` forest emerald accent, `12px` card radius, `8px` button geometry.
4. **Swiss Logistics Typography:** `Geist Sans` (400 body copy), `TWK Lausanne Pan 800` (display titles), `Geist Mono` (tabular numbers/clock), strictly upright `PP Editorial New` (accents).
5. **Zero AI Slop:** Pure Lucide React SVG icons; strictly zero emojis in buttons.
6. **Passing Builds:** Always ensure `npm run build` and `npm run lint` exit with 0 errors.
