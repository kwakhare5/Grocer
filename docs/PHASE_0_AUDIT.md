# Phase 0: Repository Audit & Technical Baseline

> **Version:** GROCER v2  
> **Milestone:** Phase 0 — Repository Audit  
> **Source of Truth:** `GROCER_V2_MASTER_SPEC.md` & `IMPLEMENTATION_PLAN.md`  
> **Audit Date:** 2026-09-05  

---

## 1. Executive Summary

A comprehensive repository audit was conducted across the `kwakhare5/Grocer` codebase to baseline existing capabilities and isolate boundaries before advancing Phase 1 backend authority.

### Key Audit Findings
1. **Existing Backend Services:** The Python 3.12 + FastAPI + SQLAlchemy backend contains comprehensive modular monolith services across simulation, batch inventory, forecasting (exponential smoothing), risk detection, decision scoring, and LangGraph Level 2 execution.
2. **Existing Frontend Baseline:** Next.js 16 + React 19 runs cleanly with Turbopack (0 compilation errors, 0 ESLint warnings).
3. **Core Architectural Gap:** Competing frontend authority. The Next.js frontend has retained local fallback timers, client-side depletion math (`simulationEngine.ts`), and local scenario step advancement (`scenarioEngine.ts`), which must be eliminated to establish the FastAPI backend as the single source of truth.
4. **Resilience Gap:** Simulation engine registry in `backend/api/simulations.py` relied on an in-memory dictionary `_engines`, causing 404s if workers recycled without reloading engine state from the database.

---

## 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)

### REUSE
* **Backend Services (`backend/services/*`)**:
  - `backend/services/simulation/`: Deterministic seeding, time clock, multi-store demand and inventory generation.
  - `backend/services/inventory/`: Batch-aware FIFO tracking and inventory derivation.
  - `backend/services/forecasting/`: Exponential smoothing baseline, uncertainty/confidence estimation.
  - `backend/services/risk/`: Stockout & spoilage detection engines.
  - `backend/services/decision/`: Feasible candidate generation and multi-factor scoring for `TRANSFER`, `REORDER`, `DISCOUNT`, `HOLD`.
  - `backend/services/customer/`: Household consumption forecasting and replenishment nudges.
  - `backend/agents/`: LangGraph Level 2 human-in-the-loop execution agent.
* **Backend Models (`backend/models/*`)**: 15 SQLAlchemy entities with PostgreSQL/SQLite compatibility.
* **Frontend Design System (`components/ui/*`, `components/PhoneMockup.tsx`)**: High-fidelity iOS status bars, tab navigation, and clean Swiss Logistics typography tokens.

### REFACTOR
* **`app/page.tsx`**: Remove client-side simulation clock advancement (`setSimulation(prev => ...)`) and client-side scenario steps. Bind all simulation advancement, scenario triggering, and resets strictly to backend API responses.
* **`lib/apiClient.ts`**: Implement active simulation retrieval (`/api/simulations/active`) and tighten response parsing.
* **`components/operations/SimulationFloatingIsland.tsx`**: Bind time counters and play/pause controls to backend simulation state, adding a clear live connectivity badge.
* **`backend/api/simulations.py`**: Support on-demand engine reconstruction from the database when memory cache misses occur.

### DELETE / DEPRECATE
* **Client-side simulation authority in `lib/simulationEngine.ts`**: Deprecate client-side pantry depletion formulas and local state processing.
* **Client-side scenario driver in `lib/scenarioEngine.ts`**: Deprecate hardcoded local step transitions; scenario state must flow through backend database records.

### MISSING
* **Root `pytest.ini`**: Added to allow seamless CLI test runs across environments.
* **`GET /api/simulations/active`**: Endpoint to fetch the current active simulation or auto-seed a default instance.
* **Authoritative Phase 1 Test Suite**: Comprehensive tests ensuring database persistence across time advances and resets.

### RISK
* **Offline UI State**: Without a client-side fake simulator, when the backend is offline the frontend cannot simulate store changes. This is intentional and compliant with Phase 1 rules. The UI will prominently indicate backend offline status and provide connection guidance.

---

## 3. Test & Runtime Baseline

* **Backend Test Suite:** **185 passed** in 83.06s via `pytest`.
  - `backend/tests/test_agent.py`: 25 passed
  - `backend/tests/test_agent_api.py`: 12 passed
  - `backend/tests/test_customer_api.py`: 8 passed
  - `backend/tests/test_decision.py`: 22 passed
  - `backend/tests/test_decision_api.py`: 15 passed
  - `backend/tests/test_events.py`: 7 passed
  - `backend/tests/test_forecast_api.py`: 18 passed
  - `backend/tests/test_forecasting.py`: 24 passed
  - `backend/tests/test_health.py`: 2 passed
  - `backend/tests/test_models.py`: 8 passed
  - `backend/tests/test_risk.py`: 18 passed
  - `backend/tests/test_risk_api.py`: 12 passed
  - `backend/tests/test_simulation.py`: 14 passed
* **Frontend Lint Baseline:** `npm run lint` → 0 errors, 0 warnings.
* **Frontend Build Baseline:** `npm run build` → Compiled successfully in 7.4s with Turbopack, 0 type errors.
