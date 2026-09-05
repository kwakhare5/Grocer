# ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification

> Source of Truth: [GROCER_V2_MASTER_SPEC.md](file:///d:/Grocer/GROCER_V2_MASTER_SPEC.md)

---

## 1. PRODUCT VISION & SCOPE

GROCER is an **AI-assisted quick-commerce inventory decision and execution system**. It connects two sides of a shared simulated universe:

1. **Customer Side (Proactive Replenishment):** Context-aware WhatsApp assistant predicting household staple depletion (Prophet ML) and enabling low-friction 1-tap reorders before morning rush.
2. **Operations Side (Dark Store Command Center):** 5-store Mumbai network control deck predicting store-level stockout & spoilage risks, evaluating 4 candidate interventions (`TRANSFER`, `REORDER`, `DISCOUNT`, `HOLD`), explaining root-cause tradeoffs with a structured WHY panel, and executing approved actions via a Level-2 LangGraph agent.

```text
OBSERVE ──► PREDICT ──► DETECT ──► EVALUATE ──► RECOMMEND ──► APPROVE ──► AGENT EXECUTE ──► VERIFY ──► MEASURE
```

---

## 2. MODULAR MONOLITH ARCHITECTURE

```text
                         ┌────────────────────────────────────────┐
                         │               NEXT.JS 16               │
                         │   Operations Cockpit | WhatsApp Flow   │
                         └───────────────────┬────────────────────┘
                                             │
                                     REST + WebSockets
                                             │
                         ┌───────────────────▼────────────────────┐
                         │           FASTAPI MODULAR MONOLITH     │
                         ├────────────────────────────────────────┤
                         │ • Simulation Engine (Time/Scenarios)   │
                         │ • Inventory & Batch Expiry Service     │
                         │ • Forecasting & Anomaly Gate Engine    │
                         │ • Risk & Stockout/Spoilage Detection   │
                         │ • Deterministic Decision Engine        │
                         │ • Recommendation & Alternatives Rerank │
                         │ • LangGraph Execution Agent (Level 2)  │
                         │ • CommercePort & Swiggy MCP Adapter    │
                         └───────────────┬────────────────┬───────┘
                                         │                │
                                 Controlled Tools   Swiggy MCP Tools
                                         │                │
                    ┌────────────────────▼────┐    ┌──────▼─────────────────┐
                    │ SIMULATED DARK STORES   │    │ SWIGGY INSTAMART MCP   │
                    │ Bandra · Andheri · etc. │    │ POST mcp.swiggy.com/im │
                    └─────────────────────────┘    └────────────────────────┘
```

---

## 3. CORE FRONTEND VIEWS & CAPABILITIES

### A. Navigation & View Controller (`app/page.tsx`)
- **Landing Mode (`"landing"`):** Product showcase with 64px `GrocerHeader`, Hero, Value Prop bento grid, Developer Webhook Terminal, and FAQ.
- **Operations Mode (`"operations"`):** 56px `CockpitHeader`, multi-tab operations center (`OperationsDashboard`), and bottom-docked `SimulationFloatingIsland`.
- **Customer Mode (`"customer"`):** Interactive iPhone 17 Pro household replenishment simulator (`CustomerReplenishmentView`) with live Swiggy MCP Commerce Drawer and real-time delivery tracking.

### B. Operations Deck Tabs
1. **Stock Replenishment Matrix (`SkuInventoryTable.tsx`):** High-density replenishment matrix across 5 fleet nodes with real-time stock status meters, demand velocity, supplier lead time, restock deltas, and 1-click PO triggers.
2. **Decision Stream (`RecommendationStream.tsx` & `WhyInspectorPanel.tsx`):** Live recommendation cards with structured WHY reasoning (Stockout ETA, Supplier Lead Time, Safe Excess, and Alternatives trade-offs).
3. **Mumbai Dark Store Map (`SpatialTopologyView.tsx`):** Spatial SVG fleet network with active transfer courier particles and inter-store balance indicators.

### C. Floating Simulation Island (`SimulationFloatingIsland.tsx`)
- Universal simulation clock (`Day 07 · 12:00 UTC`).
- Controls: `Run`, `Pause`, `+1h`, `+6h`, `+24h`, `Reset`.
- Benchmark Scenarios (§25 Hero Scenario, §26 Perishables Spoilage, §27 Stale Pre-Check Failure).

### D. Customer Replenishment & Swiggy MCP Commerce (`CustomerReplenishmentView.tsx`)
- **Decoupled CommercePort:** Connects customer grocery replenishments via `MockCommerceAdapter` (deterministic Mumbai dark stores) or `SwiggyMCPAdapter` (`POST mcp.swiggy.com/im`).
- **Live Commerce Cart:** Interactive SKU list with spinId tags, quantity steppers, Go-To staple quick-add, and transparent fee breakdown (subtotal, delivery, packaging, grand total).
- **Consequential Checkout Guard (Spec §28.3):** Enforces explicit human confirmation modal (`explicit_confirmation: true`) before order dispatch.
- **Express Tracking:** Real-time rider tracking (`Ramesh Kamble`, ETA in mins, live GPS status).

---

## 4. SAFETY INVARIANTS & AUTONOMY BOUNDARIES
- **Level-2 Autonomy:** Autonomous agents cannot self-approve or self-execute newly consequential replenishment transfers; operator sign-off is required.
- **Consequential Action Barrier (Spec §28.3 & §39.15):** Autonomous agents must not execute financial checkouts without human authorization. Unconfirmed checkouts return `UnconfirmedCheckoutError` (HTTP 400).
- **Batch Conservation Invariant:** Inter-store transfers must deduct strictly FIFO from source batches and generate exact equivalent batches at recipient stores.

---

## 5. DESIGN & TYPOGRAPHY TOKENS
- **Design System:** Clean Apple Light (`--background: #FAFAFA`, `--surface-card: #FFFFFF`, `--primary: #064E3B`, `--border: #E4E4E7`).
- **Geometry:** 12px card radii, 8px button geometry, 6px badge radius.
- **Typography:** `Geist Sans` body copy (crisp 400 regular weight), `TWK Lausanne Pan 800` display headings, `Geist Mono` tabular telemetry, and strictly upright `PP Editorial New` accents.
- **Zero AI Slop:** Lucide React SVG vectors only; zero emojis in buttons.
