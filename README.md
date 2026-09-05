<!-- ╔══════════════════════════════════════════════════════════════════╗
     ║          Grocer v2.0 — README                                   ║
     ║          AI Quick-Commerce Decision & Execution System          ║
     ╚══════════════════════════════════════════════════════════════════╝ -->

<div align="center">

  # GROCER v2.0

  ### *AI-Assisted Quick-Commerce Inventory Decision & Execution System*

  <br/>

  ![Version](https://img.shields.io/badge/version-2.2.0-blue?style=for-the-badge)
  ![Phases](https://img.shields.io/badge/phases-10%2F10%20complete-success?style=for-the-badge)
  ![Tests](https://img.shields.io/badge/tests-286%2F286%20passing-brightgreen?style=for-the-badge)
  ![Next.js](https://img.shields.io/badge/Next.js-16.2_(Turbopack)-black?style=for-the-badge&logo=nextdotjs&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
  ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

  <br/>

  <a href="#-about-the-system">About</a> &nbsp;·&nbsp;
  <a href="#-architecture">Architecture</a> &nbsp;·&nbsp;
  <a href="#-implementation-phases-1010-complete">Phases</a> &nbsp;·&nbsp;
  <a href="#-the-2-minute-demo-guide">2-Min Demo Guide</a> &nbsp;·&nbsp;
  <a href="#-key-capabilities">Key Capabilities</a> &nbsp;·&nbsp;
  <a href="#-getting-started">Getting Started</a>

</div>

---

## 📌 About the System

**GROCER v2** is an applied AI engineering prototype that connects two sides of a shared quick-commerce universe:

1. **Customer Experience:** Context-aware WhatsApp assistant that detects household staple depletion (via Prophet ML) and offers 1-tap reorders.
2. **Operations Cockpit:** A 3-column internal control center that predicts dark store stockout & spoilage risks, evaluates candidate interventions (transfer, reorder, discount, hold), explains root-cause tradeoffs, and safely executes approved actions via a 5-node LangGraph agent.

```text
OBSERVE ──► PREDICT ──► DETECT ──► EVALUATE ──► RECOMMEND ──► APPROVE ──► AGENT EXECUTION ──► VERIFY ──► MEASURE
```

---

## 🏗️ Architecture

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
                         │  • Simulation Engine   • Forecasting   │
                         │  • Risk Engine         • Decision ML   │
                         │  • Customer Service    • Metrics (§28) │
                         └───────────┬────────────────┬───────────┘
                                     │                │
                             ┌───────▼────────┐  ┌────▼─────────────────┐
                             │   PostgreSQL   │  │   LangGraph Agent    │
                             │   (SQLAlchemy) │  │   (5-Node Pipeline)  │
                             └────────────────┘  └────────────┬─────────┘
                                                              │
                                                     Controlled Tools
                                                              │
                                                 ┌────────────▼──────────┐
                                                 │ Inter-Store Transfers │
                                                 │ Supplier POs & Price  │
                                                 └───────────────────────┘
```

---

## 🚦 Implementation Phases (10/10 Complete & Verified)

| Phase | Description | Status | Verification & Deliverables |
|---|---|:---:|---|
| **Phase 1** | Repository Audit + Cleanup | ✅ | Purged legacy SaaS marketing code, colocated phone mockup, cleaned unreferenced assets. |
| **Phase 2** | Backend Source-of-Truth Refactor | ✅ | Authoritative clock & SQLite persistence (`test_phase1_authority.py`). |
| **Phase 3** | Data / Model Consistency | ✅ | Batch-level inventory & status lifecycle (`test_models.py`). |
| **Phase 4** | Simulation Engine | ✅ | Deterministic time advancement & benchmark scenarios (`test_phase2_simulator.py`). |
| **Phase 5** | Forecasting + Risk Engine | ✅ | Holt smoothing & 7-dimensional risk scoring (`test_phase3_forecasting.py`, `test_phase4_risk.py`). |
| **Phase 6** | Decision Engine | ✅ | Pareto trade-off optimization & 16 reason codes (`test_phase5_decision.py`). |
| **Phase 7** | Approval + LangGraph Agent | ✅ | 5-node autonomous pipeline with Level-2 approval gate (`test_phase6_agent.py`). |
| **Phase 8** | Operations UI | ✅ | 3-column control center with live backend sync & fallback. |
| **Phase 9** | Customer Workflow & CommercePort | ✅ | Swiggy MCP protocol adapter + MockCommerceAdapter (`test_phase8_commerce.py`). |
| **Phase 10** | Testing & Demo Hardening | ✅ | End-to-end scenario suites & invariants (`test_phase10_demo_hardening.py`, 286/286 passed). |

---

## 🎬 The 2-Minute Demo Guide

### Scenario 1: Hero Stockout & Inter-Store Transfer (§25)
1. Click **`⚡ Demo Flow`** in the top navigation (or pick *Hero Scenario* in the benchmark dropdown).
2. **Observe:** Demand spike at *Powai Galleria (St 04)* creates an impending dairy stockout (2.4h). Nearby *Bandra West (St 02)* has 36 units of safe excess.
3. **Inspect:** Click the top recommendation card in Column 2. Column 3 reveals root causes, evaluated alternatives, transit distance (6.8 km), and net financial benefit (`+₹1,420`).
4. **Approve:** Click **`Approve`**. Watch the animated transfer particle cross the SVG topology map in Column 1 and stockout risk resolve to Nominal.
5. **Measure:** On completion, inspect the **Baseline vs GROCER** comparison chart showing 80% reduction in stockouts.

### Scenario 2: Perishable Spoilage & Dynamic Markdowns (§26)
1. Select *Perishables Scenario* from the benchmark dropdown.
2. **Observe:** 42 loaves of Artisan Bread at *Andheri East (St 01)* expire in 8 hours with only 12 expected sales.
3. **Evaluate:** Decision engine evaluates inter-store transfer vs 30% discount vs hold, ranking the 30% discount highest.
4. **Approve:** Approve the markdown. Real-time consumption velocity increases, avoiding ₹1,260 in food waste.

### Scenario 3: Agent Pre-Check Failure & Safe Recovery (§27)
1. Select *Failure Scenario* from the dropdown.
2. Operator approves a transfer, but source store inventory changes unexpectedly before dispatch.
3. **Recovery:** LangGraph pre-check node detects stale inventory, aborts execution, recalculates alternatives, and presents a safe revised reorder recommendation.

---

## 🚀 Key Capabilities

| Domain | Capability | Implementation |
|---|---|---|
| **Topology & Fleet Mesh** | Real-time SVG canvas with inter-store distance calculation, active transit particles, and store health meters. | `SpatialTopologyView.tsx` |
| **Decision Intelligence** | Deterministic candidate ranking across 16 reason codes, safe excess formulas, and supplier lead times. | `backend/services/decision/` |
| **Autonomous Execution** | 5-node LangGraph pipeline (`validate → pre_check → execute → verify → finalize`) with server-side approval gates. | `backend/agents/execution/` |
| **Household WhatsApp Flow** | iPhone 16 Pro simulator with 1-tap restock chips, 24h reminders, and skip actions across 25 Mumbai personas. | `components/customer/PhoneMockup.tsx` |
| **Swiggy CommercePort** | Dual commerce adapter (`MockCommerceAdapter` & official `SwiggyMCPAdapter`) with strict Consequential Action Guard. | `backend/integrations/commerce/` |
| **Shared Simulation State** | Customer WhatsApp orders immediately deplete dark-store inventory in the operations cockpit with real-time audit logging. | `app/page.tsx` |
| **Fair Baseline Comparison** | Benchmark comparison comparing GROCER against traditional reorder-point policies across 8 standard metrics. | `lib/metricsEngine.ts` |

---

## 💻 Getting Started

### Prerequisites
- **Node.js 18+** / **Node.js 20+**
- **Python 3.11+** (for optional FastAPI backend)

### 1. Frontend Development (Next.js 16)
```bash
# Clone & install dependencies
git clone https://github.com/kwakhare5/Grocer.git
cd Grocer
npm install

# Start Next.js development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 2. Optional FastAPI Backend
```bash
# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows
pip install -r backend/requirements.txt

# Start FastAPI server
uvicorn backend.main:app --reload --port 8000
```

---

## 📜 Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Next.js dev server on port 3000 (Turbopack) |
| `npm run build` | Compile optimized Next.js production build |
| `npm run lint` | Run ESLint verification |
| `pytest backend/tests` | Run Python backend & agent test suite |

---

## 📄 License
MIT License. Created by [Karan Wakhare](https://github.com/kwakhare5).
