# Implementation Plan — Grocer Engineering Prototype & Refinement

Refactor the **Grocer** codebase to align 100% with the **Engineering Prototype & Problem Exploration** specification documented in [`PRODUCT_SPEC.md`](file:///d:/PreFill/PRODUCT_SPEC.md). 

This plan purges sales-pitch bloat (fake testimonials, vendor ROI calculators, duplicate bento grids) while preserving 100% of our full-stack technical engine (Prophet ML, Anomaly Exclusion, 5-Node LangGraph Agent, Interactive iPhone Mockup).

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions:**
> 1. **Purge Vendor Pitch Components:** We are explicitly deleting `GrocerTestimonialSection.tsx`, `GrocerRoiCalculator.tsx`, and `GrocerMeasurableValue.tsx`. Fake quotes and vendor sales calculators harm credibility in an engineering showcase.
> 2. **Single Consolidated Architecture Grid:** We are merging all technical bento cards into a single, razor-sharp 4-Card Architecture Bento Grid inside `GrocerValueProp.tsx` (Prophet ML, Anomaly Gate, 5-Node LangGraph State Machine, Mock Dark Store API).
> 3. **Clean 6-Section Landing Page Stream:** The landing page (`app/page.tsx`) becomes a 6-section technical walkthrough: Header $\rightarrow$ Hero $\rightarrow$ Architecture Bento & Velocity Simulator $\rightarrow$ Interactive iPhone Mockup $\rightarrow$ Conceptual Webhooks $\rightarrow$ FAQ & Footer.

---

## Complete Action List

### 1. Component Deletions (3 Files)

#### [DELETE] [`GrocerTestimonialSection.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerTestimonialSection.tsx)
- **Rationale:** Fake quotes ("Senior Product Manager says...") undermine technical authenticity.

#### [DELETE] [`GrocerRoiCalculator.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerRoiCalculator.tsx)
- **Rationale:** Sales-oriented financial ROI slider replaced by the interactive [`GrocerVelocityCalculator.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerVelocityCalculator.tsx) (Prophet ML stockout simulator).

#### [DELETE] [`GrocerMeasurableValue.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerMeasurableValue.tsx)
- **Rationale:** Redundant bento cards merged directly into [`GrocerValueProp.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerValueProp.tsx).

---

### 2. Component Refactoring & Copy Updates (5 Files)

#### [MODIFY] [`GrocerValueProp.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerValueProp.tsx)
- **Changes:** Consolidate into a clean 4-card Technical Architecture Bento Grid:
  - **Card 1 (Prophet ML Engine):** Depletion velocity forecasting (`0.48L/day` velocity calculation).
  - **Card 2 (Anomaly Exclusion Filter):** Strips guest spikes $>2.5\times$ & vacation gaps $>5$ days.
  - **Card 3 (5-Node LangGraph Agent):** State machine graph (`check_pantry → generate_alert → parse_user_reply → build_cart → execute_order`).
  - **Card 4 (Mocked SDK Webhook Contract):** Standardized checkout API contract interface (`POST /api/v1/darkstore/checkout`).
- Retain the interactive [`GrocerVelocityCalculator`](file:///d:/PreFill/frontend/components/grocer/GrocerVelocityCalculator.tsx) inside this section.

#### [MODIFY] [`GrocerHero.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerHero.tsx)
- **Changes:** Update kicker badge to *"Engineering Prototype • Pre-Emptive Household Replenishment"* and update headline/subtitle to reflect the technical exploration. Keep the central iPhone 16 Pro mockup stage.

#### [MODIFY] [`GrocerIntegrations.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerIntegrations.tsx)
- **Changes:** Reframe from sales pitch copy to a **Conceptual Integration Architecture**:
  - `POST /api/v1/orders/ingest` (Order history ingest)
  - `WhatsApp Business API` (Native Quick Reply Buttons)
  - `POST /api/v1/darkstore/checkout` (Simulated checkout webhook)
  - `TimescaleDB Price Watcher` (Commodity price dip signals)

#### [MODIFY] [`GrocerFAQ.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerFAQ.tsx)
- **Changes:** Update Q&A to answer technical engineering questions:
  1. How does Prophet ML forecast staple depletion velocity?
  2. How does Anomaly Filtering protect baseline accuracy?
  3. How does the 5-node LangGraph execution state machine handle WhatsApp replies?
  4. How is the dark store integration mocked in this prototype?
  5. How can platforms validate this using the Historical Backtest protocol?

#### [MODIFY] [`GrocerFooter.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerFooter.tsx)
- **Changes:** Update footer sub-links and copyright copy to *"Grocer — Engineering Prototype & Problem Exploration"*.

---

### 3. Page & Layout Refactoring (2 Files)

#### [MODIFY] [`page.tsx`](file:///d:/PreFill/frontend/app/page.tsx)
- **Changes:** Remove deleted component imports (`GrocerTestimonialSection`, `GrocerMeasurableValue`). Render a clean 6-section stream:
  1. `GrocerHeader`
  2. `GrocerHero` (Hero + PhoneMockup stage)
  3. `GrocerValueProp` (Architecture Bento Grid + Velocity Simulator)
  4. `GrocerAppPreview` (Interactive iPhone Prototype Demo container)
  5. `GrocerIntegrations` (Conceptual SDK Webhook Architecture)
  6. `GrocerFAQ` & `GrocerFooter`

#### [MODIFY] [`layout.tsx`](file:///d:/PreFill/frontend/app/layout.tsx)
- **Changes:** Update page metadata title: *"Grocer — Engineering Prototype & Problem Exploration for Quick Commerce Replenishment"*.

---

### 4. Backend Systems (100% Retained)

- [`backend/main.py`](file:///d:/PreFill/backend/main.py)
- [`backend/ml/consumption_model.py`](file:///d:/PreFill/backend/ml/consumption_model.py)
- [`backend/ml/anomaly_detector.py`](file:///d:/PreFill/backend/ml/anomaly_detector.py)
- [`backend/ml/confidence_scorer.py`](file:///d:/PreFill/backend/ml/confidence_scorer.py)
- [`backend/agents/restock_agent.py`](file:///d:/PreFill/backend/agents/restock_agent.py)
- [`backend/mcp/mock_server.py`](file:///d:/PreFill/backend/mcp/mock_server.py)
- [`backend/tests/`](file:///d:/PreFill/backend/tests/)

---

## Verification Plan

### Automated Build & Test Verification
1. **Frontend Production Build:**
   ```bash
   cd d:\PreFill\frontend
   npm run build
   ```
   *Pass criteria:* Zero TypeScript errors, zero ESLint warnings, successful static page generation.

2. **Pytest Backend Verification:**
   ```bash
   cd d:\PreFill
   .\venv\Scripts\python.exe -m pytest backend/tests/ -v
   ```
   *Pass criteria:* All 16 unit & integration tests passing.

### Manual Visual & Interactive Verification
1. **Interactive Demo Test:** Verify that `PhoneMockup.tsx` screen controls (Pantry `-` / `+` steppers, Recipe ingredient checklists, WhatsApp 1-tap ordering chat drawer) work seamlessly without landing page scroll jumps.
2. **Page Flow Audit:** Verify that no dead links, missing components, or broken layouts exist across desktop and mobile screens.
