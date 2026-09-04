# Phase 0: Repository Audit & Technical Baseline

> **Version:** GROCER v2  
> **Milestone:** Phase 0 — Repository Audit  
> **Source of Truth:** `GROCER_V2_MASTER_SPEC.md`

---

## 1. Executive Summary

A comprehensive repository audit was conducted across the `kwakhare5/Grocer` codebase to prepare for the v2 evolution.

### Key Audit Findings
1. **Existing Baseline:** The repository currently functions as a pure Next.js 16 + React 19 + TypeScript client-side prototype. It runs cleanly with `npm run build` and `npm run lint`.
2. **Core Reusable Asset:** The interactive iPhone 16 Pro WhatsApp replenishment interface in `components/PhoneMockup.tsx` and accompanying UI primitives in `components/ui/*` provide high-fidelity visual and interaction mechanics for the v2 Customer Mode.
3. **Core Architectural Gaps:** The v1 system lacks a backend process, multi-store data model (5 dark stores), batch-aware inventory, stockout/spoilage risk calculations, deterministic decision scoring (`TRANSFER`, `REORDER`, `DISCOUNT`, `HOLD`), LangGraph execution agent, and Operations Control Center dashboard.

---

## 2. Reusability & Component Disposition

| Component / Subsystem | Current State | Disposition | Rationale |
|---|---|---|---|
| `components/PhoneMockup.tsx` | WhatsApp chat UI & pantry view | **Retain & Refactor** | Retain iOS mockup styling; wire message & cart handlers to backend `/customers/{id}/...` endpoints. |
| `components/ui/*` | Hardware frames, badges, buttons | **Retain** | High quality, brand-agnostic design tokens; zero AI-slop. |
| `lib/types.ts` | Basic v1 interface definitions | **Refactor** | Align with backend Pydantic models (Store, Product, Batch, Risk, Recommendation, Action, Event). |
| `lib/mockData.ts` | 4 hardcoded pantry items & recipes | **Deprecate** | Replace with database-driven catalog of 20–30 products across 5 categories. |
| `lib/simulationEngine.ts` | Hardcoded client depletion math | **Migrate** | Migrate business logic to FastAPI domain services (`backend/services/`). |
| `app/page.tsx` | Single landing page | **Redesign** | Transform into dual-mode switchable console: Operations Control Center ↔ Customer WhatsApp. |

---

## 3. Modular Monolith Target Architecture

```
d:\Grocer\
├── app/                          # Next.js 16 App Router (Dual-mode UI)
│   ├── layout.tsx
│   ├── page.tsx                  # Operations Control Center & Customer Mode Switcher
│   └── globals.css
├── components/
│   ├── PhoneMockup.tsx           # Customer WhatsApp simulator
│   ├── operations/               # New v2 Operations Control Center components
│   │   ├── StoreNetworkMap.tsx   # 5 dark store spatial network
│   │   ├── RiskOverview.tsx      # Stockout & Spoilage feed
│   │   ├── RecommendationCard.tsx# Active intervention cards
│   │   ├── WhyPanel.tsx          # Structured decision reasoning modal
│   │   ├── ActivityTimeline.tsx  # Event & agent execution stream
│   │   └── MetricsComparison.tsx # Baseline vs GROCER outcome graph
│   └── ui/                       # Design tokens & frames
├── backend/                      # Python 3.12 FastAPI Modular Monolith
│   ├── api/                      # REST & WebSocket routes
│   ├── models/                   # SQLAlchemy & Pydantic models (15 core entities)
│   ├── database/                 # Async database session & initialization
│   ├── services/
│   │   ├── simulation/           # Clock, deterministic seed, synthetic history
│   │   ├── inventory/            # Batch-aware FIFO tracking
│   │   ├── forecasting/          # Time-series & baseline velocity models
│   │   ├── risk/                 # Stockout & spoilage detection
│   │   ├── decision/             # Scoring & constraint validation
│   │   ├── recommendation/       # Structured recommendations
│   │   ├── customer/             # Replenishment nudges
│   │   └── metrics/              # Baseline comparison
│   ├── agents/                   # LangGraph Level 2 execution agent
│   ├── tools/                    # Approval-guarded mutation tools
│   ├── events/                   # In-process async event bus
│   └── tests/                    # Pytest test suite
├── docs/                         # Specifications & audit documentation
└── GROCER_V2_MASTER_SPEC.md      # System source of truth
```

---

## 4. Phase 0 Acceptance Verification

- [x] Verified current Next.js application compiles cleanly with `npm run build`.
- [x] Verified ESLint validation passes with 0 errors.
- [x] Cataloged all reusable and deprecated components.
- [x] Established `backend/` modular monolith directory structure.
- [x] Formulated detailed phase-by-phase migration plan and model selection strategy.
