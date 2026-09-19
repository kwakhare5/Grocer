# GROCER Engineering Contract

Read [`ARCHITECTURE.md`](file:///ARCHITECTURE.md), [`docs/SWIGGY_MCP_API.md`](file:///docs/SWIGGY_MCP_API.md), and [`.agents/AGENTS.md`](file:///.agents/AGENTS.md) before modifying code.

## 1. Product Boundary

GROCER is an English-first WhatsApp grocery replenishment agent for Swiggy Instamart.
Its job is to help customers order groceries effortlessly from their local dark store directly inside WhatsApp.

Never build:
- Dark-store operator dashboards or inventory management systems;
- Cross-marketplace aggregators or competitor price comparison engines;
- Browser-owned commerce state;
- Silent substitutions or autonomous unconfirmed checkouts.

## 2. Invariants & Architecture

Detailed rules, state machine specifications, and operational instructions are maintained in:
- [`.agents/AGENTS.md`](file:///.agents/AGENTS.md) — Comprehensive rules, invariants, and session logs.
- [`ARCHITECTURE.md`](file:///ARCHITECTURE.md) — Architecture diagrams, system components, and database schema.
- [`docs/SWIGGY_MCP_API.md`](file:///docs/SWIGGY_MCP_API.md) — Swiggy MCP tool interface and schema contract.

## 3. Quality Gate

Always verify before committing:

```bash
pytest backend/tests
npm run lint
npm run build
```
