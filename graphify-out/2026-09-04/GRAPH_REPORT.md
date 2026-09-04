# Graph Report - Grocer  (2026-09-04)

## Corpus Check
- 117 files · ~345,265 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1469 nodes · 3132 edges · 96 communities (87 shown, 9 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 271 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `37212752`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- GrocerValueProp.tsx
- test_agent.py
- test_decision.py
- test_risk.py
- GROCER_V2_MASTER_SPEC.md
- core.py
- compilerOptions
- test_decision_api.py
- ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification
- test_forecast_api.py
- README.md
- dependencies
- simulation/engine.py
- test_agent_api.py
- EventBus
- test_risk_api.py
- schemas.py
- seed_data.py
- AGENTS.md — Grocer Project Rules
- SimulationEngine
- AgentState
- Read at the START of EVERY session.
- CustomerService
- create_app
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- forecasting/engine.py
- .prettierrc.json
- types.ts
- layout.tsx
- compute_confidence
- Changes Made
- apiClient.ts
- Simulation
- Log Entries
- test_simulation.py
- DemandPoint
- test_forecasting.py
- RecommendationCard.tsx
- scenarioEngine.ts
- recommendations.py
- page.tsx
- Grocer — Historical Context & ADRs
- test_forecasting_engine_confidence_in_range
- OperationsDashboard.tsx
- customers.py
- graphify
- workflows/graphify.md
- advance_simulation
- runner.py
- tools.py
- 29. Core data model
- asyncio
- risks.py
- 45. Implementation plan
- GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification
- forecasting.py
- ._aggregate_daily_demand
- products.py
- client
- 50. Engineering principles
- IP as Logo
- IP as Logo
- env.py
- 32. API contract
- 6. Locked scope
- eslint.config.mjs
- GrocerHero.tsx
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- task.md
- 10. Technology stack
- 12. ML / forecasting scope
- test_health_endpoint_reports_db_status
- 40. Testing strategy
- 47. Review gates
- PHASE_0_AUDIT.md
- client
- 14. Decision Engine
- _seed_transfer_scenario
- 15. Transfer logic
- 23.1 Modes
- nodes.py
- health_check
- 0. How to use this document
- 28. Baseline vs GROCER
- 34. Frontend information architecture
- 4. Problem
- 5. Core product concept
- agents/__init__.py
- services/__init__.py
- agent.py
- GrocerFooter.tsx

## God Nodes (most connected - your core abstractions)
1. `SimulationEngine` - 65 edges
2. `Product` - 43 edges
3. `Store` - 42 edges
4. `Inventory` - 39 edges
5. `Supplier` - 37 edges
6. `Risk` - 34 edges
7. `Recommendation` - 34 edges
8. `SimulationClock` - 32 edges
9. `RiskEngine` - 30 edges
10. `ForecastingEngine` - 29 edges

## Surprising Connections (you probably didn't know these)
- `WhyInspectorPanelProps` --references--> `RecommendationItem`  [EXTRACTED]
  components/operations/WhyInspectorPanel.tsx → lib/types.ts
- `PhoneMockup()` --calls--> `usePhoneDemoEngine()`  [EXTRACTED]
  components/PhoneMockup.tsx → hooks/usePhoneDemoEngine.ts
- `CustomerReplenishmentViewProps` --references--> `DarkStore`  [EXTRACTED]
  components/customer/CustomerReplenishmentView.tsx → lib/types.ts
- `LiveEventFeedProps` --references--> `SimulationEvent`  [EXTRACTED]
  components/operations/LiveEventFeed.tsx → lib/types.ts
- `MetricsComparisonPanelProps` --references--> `ScenarioState`  [EXTRACTED]
  components/operations/MetricsComparisonPanel.tsx → lib/types.ts

## Import Cycles
- None detected.

## Communities (96 total, 9 thin omitted)

### Community 0 - "GrocerValueProp.tsx"
Cohesion: 0.43
Nodes (4): GrocerValueProp(), GrocerVelocityCalculator(), PantryItem, usePantryEngine()

### Community 1 - "test_agent.py"
Cohesion: 0.15
Nodes (20): node_validate(), Validate that the recommendation exists and is in APPROVED status. Fails fast…, apply_discount(), MUTATION: Apply discount (simulated: emits DISCOUNT_APPLIED event, no price…, TDD tests for Phase 6 LangGraph Agent (spec sections 19-21). Test seams…, APPROVED reorder recommendation., PENDING (not approved) recommendation for rejection tests., AgentState is a TypedDict; required fields can be set. (+12 more)

### Community 2 - "test_decision.py"
Cohesion: 0.05
Nodes (67): AsyncSession, UUID, Set recommendation status to APPROVED (spec section 18 -- human-in-the-loop)., Set recommendation status to REJECTED., Evaluate decision for a risk and persist the top recommendation. Returns the…, Decision Engine service package., ActionScorer, CandidateAction (+59 more)

### Community 3 - "test_risk.py"
Cohesion: 0.05
Nodes (67): ForecastingEngine, Generates Forecast rows from historical Order data in the simulation DB. Usage:…, _naive_now(), AsyncSession, datetime, UUID, GROCER v2 Risk Engine. Orchestrates risk detection across inventory, forecasts,…, Mark an active risk as RESOLVED and emit RISK_RESOLVED event. (+59 more)

### Community 4 - "GROCER_V2_MASTER_SPEC.md"
Cohesion: 0.05
Nodes (40): 11. AI engineering philosophy, 13. Inventory model, 16. Decision scoring, 17. Recommendation object, 18. Human-in-the-loop policy, 19.1 Agent autonomy level, 19. LangGraph agent, 1. Vision (+32 more)

### Community 5 - "core.py"
Cohesion: 0.48
Nodes (25): Action, Batch, Customer, Event, Forecast, Inventory, Order, OrderItem (+17 more)

### Community 6 - "compilerOptions"
Cohesion: 0.07
Nodes (28): dom, dom.iterable, esnext, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules (+20 more)

### Community 7 - "test_decision_api.py"
Cohesion: 0.06
Nodes (36): client(), first_risk_id(), fixture, TDD API tests for Phase 5 Recommendation endpoints (spec sections 17, 18). Test…, 4. After evaluate, list returns the new recommendation., 5. GET /api/recommendations/{id} returns correct recommendation., 6. Unknown recommendation_id -> 404., 7. ?risk_id=<id> filters correctly. (+28 more)

### Community 8 - "ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification"
Cohesion: 0.22
Nodes (8): 1. PRODUCT VISION & SCOPE, 2. MODULAR MONOLITH ARCHITECTURE, 3. CORE FRONTEND VIEWS & CAPABILITIES, 4. DESIGN & TYPOGRAPHY TOKENS, A. Navigation & View Controller (`app/page.tsx`), ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification, B. Operations Deck Tabs, C. Floating Simulation Island (`SimulationFloatingIsland.tsx`)

### Community 9 - "test_forecast_api.py"
Cohesion: 0.07
Nodes (38): asyncio, TDD API tests for Phase 3 endpoints. Seams under test: 1. GET /api/stores —…, GET /api/stores/{id}/inventory returns correct structure., Inventory response has product entries with correct fields., GET /api/stores/{id}/forecasts returns empty list before any forecasts…, GET /api/products returns all 25 seeded products., Each product has the required schema fields., GET /api/products/{id} returns the correct product. (+30 more)

### Community 10 - "README.md"
Cohesion: 0.14
Nodes (13): 1. Frontend Development (Next.js 16), 2. Optional FastAPI Backend, 📌 About the System, 🏗️ Architecture, 📜 Available Scripts, 💻 Getting Started, 🚀 Key Capabilities, 📄 License (+5 more)

### Community 11 - "dependencies"
Cohesion: 0.04
Nodes (45): clsx, eslint, eslint-config-next, framer-motion, lucide-react, next, dependencies, clsx (+37 more)

### Community 12 - "simulation/engine.py"
Cohesion: 0.16
Nodes (9): datetime, GROCER v2 Simulation Engine. Handles deterministic simulation: time control,…, Manages simulated time for a simulation instance., Advance simulation time by N hours. Returns new current time., Reset clock to start time., SimulationClock, SeedCustomer, SeedProduct (+1 more)

### Community 13 - "test_agent_api.py"
Cohesion: 0.06
Nodes (54): Product, Store, Supplier, DecisionOrchestrator, _naive_now(), datetime, GROCER v2 Decision Engine -- DB orchestration layer. Loads risk + inventory +…, Drives the Decision Engine pipeline end-to-end for a single risk. Usage:… (+46 more)

### Community 14 - "EventBus"
Cohesion: 0.09
Nodes (26): EventBus, Any, AsyncSession, UUID, In-process event bus for GROCER v2. LOCKED (spec §30): async in-process pub/sub…, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler. (+18 more)

### Community 15 - "test_risk_api.py"
Cohesion: 0.09
Nodes (31): client(), asyncio, fixture, TDD API tests for Phase 4 Risk endpoints. Seams under test: 1. GET /api/risks —…, GET /api/risks/{risk_id} returns risk details., GET /api/risks/{random_uuid} returns 404., GET /api/risks?store_id=X returns only risks for that store., GET /api/risks?risk_type=stockout returns only stockout risks. (+23 more)

### Community 16 - "schemas.py"
Cohesion: 0.14
Nodes (29): BaseSchema, BatchResponse, EventResponse, ForecastResponse, InventoryItemResponse, Pydantic v2 response schemas for GROCER v2 API. Covers: stores, products,…, RiskResponse, StoreDetailResponse (+21 more)

### Community 17 - "seed_data.py"
Cohesion: 0.33
Nodes (6): _id(), UUID, Deterministic seed data catalog for the GROCER v2 simulator. Defines 5 dark…, Generate a deterministic UUID from a name., SeedStore, SeedSupplier

### Community 18 - "AGENTS.md — Grocer Project Rules"
Cohesion: 0.29
Nodes (6): 1. PROJECT IDENTITY, 2. TECH STACK, 3. DEV COMMANDS, 4. LOCAL RULES & DESIGN INVARIANTS, 5. SESSION RESUME, AGENTS.md — Grocer Project Rules

### Community 19 - "SimulationEngine"
Cohesion: 0.12
Nodes (18): Any, AsyncSession, UUID, Advance simulation time, generate new orders, handle batch expiry. Returns…, Reset simulation: clear generated data, re-seed, restart clock., Seed stores, suppliers, products, and customers., Create initial inventory and batches for all store-product pairs., Generate orders day by day for the historical period. (+10 more)

### Community 20 - "AgentState"
Cohesion: 0.13
Nodes (22): build_execution_graph(), LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section…, Fail fast if validate produced an error., Divert to recover if world state has changed., Divert to recover on execution error., Divert to recover if verification failed., Build and return the compiled LangGraph execution graph., _route_after_execute() (+14 more)

### Community 21 - "Read at the START of EVERY session."
Cohesion: 0.40
Nodes (4): CONTEXT.md — Domain Language & Rules, Core Entities & Product Purpose, Invariants & Design Rules (Never Break), Read at the START of EVERY session.

### Community 22 - "CustomerService"
Cohesion: 0.15
Nodes (19): CustomerReorderResult, CustomerState, PantryStapleState, Customer domain models for Phase 9 Customer / WhatsApp simulation. Defines data…, WhatsAppInteractionMessage, CustomerService, Any, AsyncSession (+11 more)

### Community 23 - "create_app"
Cohesion: 0.12
Nodes (22): get_db(), AsyncSession, create_app(), lifespan(), asyncio, POST /api/customers/{id}/reorder should deduct inventory and create order., POST /api/customers/{id}/remind should schedule reminder., POST /api/customers/{id}/skip should record skip. (+14 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.12
Nodes (15): Automated Tests, Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, Finalized Architecture & Design Decisions, Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me), Manual Verification, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx) (+7 more)

### Community 25 - "forecasting/engine.py"
Cohesion: 0.18
Nodes (19): GROCER v2 Forecasting Engine. Orchestrates forecast generation over simulator…, Fit both models, optionally compare on holdout, return (prediction, model_name,…, baseline_predict(), clean_demand_series(), _compute_dow_multiplier(), detect_anomalies(), evaluate_forecast(), exponential_smoothing_predict() (+11 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "types.ts"
Cohesion: 0.15
Nodes (22): CustomerReplenishmentView(), CustomerReplenishmentViewProps, IphoneFrame(), IphoneFrameProps, usePhoneDemoEngine(), DEFAULT_CUSTOMER_PERSONA, DEFAULT_PANTRY_STAPLES, ICON_MAP (+14 more)

### Community 28 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 29 - "compute_confidence"
Cohesion: 0.20
Nodes (10): compute_confidence(), Return a composite confidence score in [0.0, 1.0]. Four factors combined…, compute_confidence always returns a value in [0.0, 1.0]., Higher coefficient of variation yields lower confidence., More anomalies in history → lower confidence., Fewer data points → lower confidence., test_confidence_lower_for_high_variance(), test_confidence_lower_for_more_anomalies() (+2 more)

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "apiClient.ts"
Cohesion: 0.09
Nodes (20): BackendAgentRun, BackendCustomerDetail, BackendCustomerListItem, BackendCustomerMessageResponse, BackendCustomerMessages, BackendCustomerRemindResponse, BackendCustomerReorderResponse, BackendCustomerSkipResponse (+12 more)

### Community 32 - "Simulation"
Cohesion: 0.39
Nodes (8): AdvanceTimeRequest, create_simulation(), CreateSimulationRequest, BaseModel, Simulation API endpoints for GROCER v2., Create and initialize a new simulation., SimulationResponse, Simulation

### Community 33 - "Log Entries"
Cohesion: 0.15
Nodes (12): [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — iPhone Chassis Scaled to 300px, Button Label Glitch Fixed & WhatsApp Bubble Spacing Refined] 2026-09-04, [Grocer — Official App Icon Design & Full UI Architecture Overhaul] 2026-09-02, [Grocer — Phase 0 Audit, Phase 1 Backend Foundation & Phase 2 Simulator Engine] 2026-08-27, [Grocer — Phase 0 Repository Audit & v2 Architecture Alignment] 2026-08-26, [Grocer — Phase 9 Customer / WhatsApp Integration & Phase 10 Hardening & Polish] 2026-08-28, [Grocer — Saved Exact Figma Notification Layout & WhatsApp Icon] 2026-08-15, [Grocer — UI Aesthetics, 3-Column Cockpit, Phase 3/4/5/6 Engines & Phase 7 Live Integration] 2026-08-27 (+4 more)

### Community 34 - "test_simulation.py"
Cohesion: 0.14
Nodes (24): AsyncClient, asyncio, AsyncSession, TDD tests for the GROCER v2 simulation engine., Same seed should produce same number of orders., Inventory quantities should never be negative after orders., Advancing time should create new orders and update simulation., A Simulation record should be created in the DB. (+16 more)

### Community 35 - "DemandPoint"
Cohesion: 0.10
Nodes (20): DemandPoint, A single daily demand observation., A 48h horizon prediction is approximately double a 24h prediction., Baseline works with as few as 3 data points., Time-series model returns a positive demand forecast for 30d history., Exponential smoothing with upward trend predicts higher than the mean., With only 2 data points, exponential smoothing falls back gracefully (>0)., DemandPoint is a simple data container. (+12 more)

### Community 36 - "test_forecasting.py"
Cohesion: 0.11
Nodes (17): TDD tests for the forecasting engine (spec §12). Test seams, in order of the…, Perfect forecasts yield MAE=0, RMSE=0, MAPE=0., MAE is correctly computed from a worked example., RMSE is correctly computed from a worked example., MAPE is correctly computed from a worked example., evaluate_forecast returns a ModelEvaluationResult dataclass., No anomalies detected when demand is perfectly uniform., Empty series yields empty anomaly list without error. (+9 more)

### Community 37 - "RecommendationCard.tsx"
Cohesion: 0.31
Nodes (6): RecommendationCard(), WhyInspectorPanel(), WhyInspectorPanelProps, formatHours(), formatINR(), formatPercentage()

### Community 38 - "scenarioEngine.ts"
Cohesion: 0.17
Nodes (16): LiveEventFeed(), LiveEventFeedProps, RecommendationCardProps, RecommendationStream(), RecommendationStreamProps, BaselineStepResult, buildFailureScenario(), buildHeroScenario() (+8 more)

### Community 39 - "recommendations.py"
Cohesion: 0.19
Nodes (20): approve_recommendation(), evaluate_recommendation(), get_recommendation(), list_recommendations(), AsyncSession, get, post, UUID (+12 more)

### Community 40 - "page.tsx"
Cohesion: 0.19
Nodes (15): defaultScenarioState(), GrocerApp(), GrocerFAQ(), GrocerIntegrations(), transformRecommendation(), transformStores(), computeBaselineMetrics(), computeGrocerMetrics() (+7 more)

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

### Community 42 - "test_forecasting_engine_confidence_in_range"
Cohesion: 0.29
Nodes (7): asyncio, ForecastingEngine runs on seeded simulation data and writes Forecast rows., All generated Forecast rows have confidence in [0.0, 1.0]., ForecastingEngine emits FORECAST_UPDATED events for each forecast generated., test_forecasting_engine_confidence_in_range(), test_forecasting_engine_emits_event(), test_forecasting_engine_generates_forecasts()

### Community 43 - "OperationsDashboard.tsx"
Cohesion: 0.12
Nodes (21): MetricsComparisonPanel(), MetricsComparisonPanelProps, OperationsDashboard(), OperationsDashboardProps, SimulationFloatingIsland(), SimulationFloatingIslandProps, CATALOG_ITEMS, SkuCatalogItem (+13 more)

### Community 44 - "customers.py"
Cohesion: 0.11
Nodes (33): get_customer(), get_customer_messages(), list_customers(), AsyncSession, get, post, UUID, FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8). Provides: - GET… (+25 more)

### Community 47 - "advance_simulation"
Cohesion: 0.27
Nodes (10): advance_simulation(), get_simulation(), Any, AsyncSession, get, post, Reset simulation to initial state., Get simulation status and details. (+2 more)

### Community 48 - "runner.py"
Cohesion: 0.15
Nodes (13): Execution agent subpackage -- LangGraph 5-node execution graph., ExecutionRunner, _naive_now(), AsyncSession, datetime, UUID, Agent ExecutionRunner -- async entry point for the execution graph. Usage:…, Typed result returned by ExecutionRunner.run(). (+5 more)

### Community 49 - "tools.py"
Cohesion: 0.15
Nodes (21): _assert_approved(), create_reorder(), create_transfer(), _enum_val(), log_agent_event(), _naive_now(), Any, AsyncSession (+13 more)

### Community 50 - "29. Core data model"
Cohesion: 0.12
Nodes (16): 29.10 Risk, 29.11 Recommendation, 29.12 Action, 29.13 Event, 29.14 Simulation, 29.15 Scenario, 29.1 Store, 29.2 Product (+8 more)

### Community 51 - "asyncio"
Cohesion: 0.20
Nodes (14): asyncio, AsyncSession, Should persist Simulation and Scenario., Should persist an Event with JSON payload., Should persist a Store with all required fields., Should persist a Supplier., Should persist a Product linked to a Supplier., Should persist a Customer linked to a home Store. (+6 more)

### Community 52 - "risks.py"
Cohesion: 0.21
Nodes (15): evaluate_risks(), get_risk(), list_risks(), AsyncSession, get, post, UUID, Risk REST API — spec §32. Endpoints: GET /api/risks — list risks with optional… (+7 more)

### Community 53 - "45. Implementation plan"
Cohesion: 0.13
Nodes (15): 45. Implementation plan, Phase 0 — Repository audit, Phase 10 — Scenarios + failure simulation, Phase 11 — Metrics / baseline comparison, Phase 12 — Hardening, Phase 13 — Demo polish, Phase 1 — Backend foundation, Phase 2 — Simulator foundation (+7 more)

### Community 54 - "GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification"
Cohesion: 0.14
Nodes (13): 1. Visual Foundation & Tone, 2.1 Surfaces & Structure, 2.2 Operator Action Tokens (The 4 Core Actions), 2.3 Risk Severity Tokens, 2. Comprehensive Color & Semantic Token System, 3. Button & Interactive Element Hierarchy, 4. Typography Hierarchy, 5. Operations Cockpit Layout (3-Column Architecture) (+5 more)

### Community 55 - "forecasting.py"
Cohesion: 0.21
Nodes (13): evaluate_models(), generate_forecasts(), list_forecasts(), AsyncSession, get, post, UUID, Forecast REST API — spec §32. Endpoints: GET /api/forecasts — list forecasts… (+5 more)

### Community 56 - "._aggregate_daily_demand"
Cohesion: 0.40
Nodes (4): AsyncSession, UUID, Query all delivered orders and aggregate demand by (store, product, day)., Generate forecasts for every (store, product) pair with history. Returns the…

### Community 57 - "products.py"
Cohesion: 0.29
Nodes (10): get_product(), list_products(), AsyncSession, get, UUID, Products REST API — spec §32.4. Endpoints: GET /api/products — list all catalog…, List all 25 catalog products., Get a single product by ID. (+2 more)

### Community 58 - "client"
Cohesion: 0.18
Nodes (11): client(), db_session(), event_loop(), AsyncClient, AsyncSession, fixture, Create a single event loop for the entire test session., Create all tables before each test, drop after. (+3 more)

### Community 59 - "50. Engineering principles"
Cohesion: 0.18
Nodes (11): 50. Engineering principles, Principle 10 — AI is a component, not the architecture, Principle 1 — Don't fake intelligence, Principle 2 — Don't fake integrations, Principle 3 — Don't fake results, Principle 4 — Don't over-engineer, Principle 5 — Keep humans in the loop, Principle 6 — Make decisions explainable (+3 more)

### Community 60 - "IP as Logo"
Cohesion: 0.20
Nodes (9): Color and canvas, Complexity budget, Delivery behavior, IP as Logo, Prompt skeleton, Route constraints by generator capability, Shape language and composition, Simplicity and visual treatment (+1 more)

### Community 61 - "IP as Logo"
Cohesion: 0.22
Nodes (8): Agent compatibility, Install, IP as Logo, License, Model behavior, Repository structure, Use, What it guides

### Community 62 - "env.py"
Cohesion: 0.28
Nodes (5): do_run_migrations(), run_async_migrations(), run_migrations_online(), Settings, BaseSettings

### Community 63 - "32. API contract"
Cohesion: 0.22
Nodes (9): 32.1 Simulation, 32.2 Scenarios, 32.3 Stores, 32.4 Products, 32.5 Recommendations, 32.6 Actions, 32.7 Events, 32.8 Customer / WhatsApp simulation (+1 more)

### Community 64 - "6. Locked scope"
Cohesion: 0.22
Nodes (9): 6.1 Stores, 6.2 Products, 6.3 Customers, 6.4 Historical data, 6.5 Main operator actions, 6.6 Transfer limitation, 6.7 Customer interface, 6.8 Platform integrations (+1 more)

### Community 66 - "GrocerHero.tsx"
Cohesion: 0.40
Nodes (4): GrocerHero(), GrocerHeroProps, PhoneMockup(), WhatsAppIcon()

### Community 71 - "10. Technology stack"
Cohesion: 0.25
Nodes (8): 10. Technology stack, AI agent, Backend, Database, Frontend, Local environment, ML, Realtime

### Community 72 - "12. ML / forecasting scope"
Cohesion: 0.25
Nodes (8): 12.1 Forecasting levels, 12.2 Model evaluation, 12.3 Confidence, 12.4 Anomalies, 12. ML / forecasting scope, Level 1 — baseline, Level 2 — time-series model, Level 3 — deterministic business calculations

### Community 74 - "test_health_endpoint_reports_db_status"
Cohesion: 0.38
Nodes (6): AsyncClient, asyncio, Health endpoint should report database connectivity., Health endpoint should return 200 with status healthy., test_health_endpoint_reports_db_status(), test_health_endpoint_returns_200()

### Community 75 - "40. Testing strategy"
Cohesion: 0.29
Nodes (7): 40.1 Unit tests, 40.2 Integration tests, 40.3 Agent tests, 40.4 API tests, 40.5 Frontend/E2E tests, 40.6 Simulation tests, 40. Testing strategy

### Community 76 - "47. Review gates"
Cohesion: 0.29
Nodes (7): 47. Review gates, Agent review, Architecture review, Demo review, Logic review, ML review, UX review

### Community 78 - "PHASE_0_AUDIT.md"
Cohesion: 0.33
Nodes (5): 1. Executive Summary, 2. Reusability & Component Disposition, 3. Modular Monolith Target Architecture, 4. Phase 0 Acceptance Verification, Key Audit Findings

### Community 79 - "client"
Cohesion: 0.40
Nodes (5): client(), fixture, Seed simulator data and return the db session., HTTP client wired to the seeded test DB via dependency override., seeded_db()

### Community 80 - "14. Decision Engine"
Cohesion: 0.40
Nodes (5): 14.1 Transfer, 14.2 Reorder, 14.3 Discount, 14.4 Hold, 14. Decision Engine

### Community 81 - "_seed_transfer_scenario"
Cohesion: 0.18
Nodes (14): node_pre_check(), Re-verify world state before executing the action. For TRANSFER: check source…, get_inventory(), Return current inventory quantity for (store, product)., Read-only validation: re-check whether the approved transfer is still feasible.…, validate_transfer(), Create two stores, a product, two inventory rows, and an APPROVED transfer rec., _seed_transfer_scenario() (+6 more)

### Community 83 - "15. Transfer logic"
Cohesion: 0.50
Nodes (4): 15.1 Safe excess, 15.2 Candidate sources, 15.3 Hard transfer constraints, 15. Transfer logic

### Community 84 - "23.1 Modes"
Cohesion: 0.50
Nodes (4): 23.1 Modes, 23. Simulator, Controlled Simulation, Scenario Mode

### Community 85 - "nodes.py"
Cohesion: 0.16
Nodes (13): _enum_val(), node_execute(), node_verify(), Any, LangGraph node functions for the GROCER v2 execution agent (spec section 19).…, Dispatch to the appropriate tool based on action_type. HOLD: no-op execution…, Verify that the execution side-effects are reflected in the DB. For TRANSFER:…, get_recommendation() (+5 more)

### Community 87 - "health_check"
Cohesion: 0.50
Nodes (4): health_check(), AsyncSession, get, Health check endpoint. Verifies API and database connectivity.

### Community 88 - "0. How to use this document"
Cohesion: 0.67
Nodes (3): 0. How to use this document, GROCER v2 — Master Engineering Specification, Status labels

### Community 89 - "28. Baseline vs GROCER"
Cohesion: 0.67
Nodes (3): 28. Baseline vs GROCER, Baseline, GROCER

### Community 90 - "34. Frontend information architecture"
Cohesion: 0.67
Nodes (3): 34.1 Customer mode, 34.2 Operations mode, 34. Frontend information architecture

### Community 91 - "4. Problem"
Cohesion: 0.67
Nodes (3): 4. Problem, Problem A — stockouts / availability, Problem B — perishable waste

### Community 92 - "5. Core product concept"
Cohesion: 0.67
Nodes (3): 5.1 Availability loop, 5.2 Waste loop, 5. Core product concept

### Community 95 - "agent.py"
Cohesion: 0.23
Nodes (11): execute_recommendation(), get_run_status(), AsyncSession, get, post, UUID, Agent Execution REST API -- spec sections 19-21. Endpoints: POST…, Trigger the LangGraph execution agent for an APPROVED recommendation. Returns… (+3 more)

### Community 99 - "GrocerFooter.tsx"
Cohesion: 0.28
Nodes (6): GrocerFooter(), GrocerFooterProps, AppGlobalHeader(), AppGlobalHeaderProps, GrocerLogo(), GrocerLogoProps

## Knowledge Gaps
- **313 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+308 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SimulationEngine` connect `SimulationEngine` to `Simulation`, `test_agent.py`, `test_simulation.py`, `test_risk.py`, `test_forecasting.py`, `core.py`, `test_decision_api.py`, `test_forecast_api.py`, `test_forecasting_engine_confidence_in_range`, `simulation/engine.py`, `test_agent_api.py`, `client`, `test_risk_api.py`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `Product` connect `test_agent_api.py` to `test_agent.py`, `test_simulation.py`, `test_risk.py`, `core.py`, `test_forecast_api.py`, `simulation/engine.py`, `schemas.py`, `_seed_transfer_scenario`, `SimulationEngine`, `asyncio`, `CustomerService`, `products.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `Store` connect `test_agent_api.py` to `test_agent.py`, `test_simulation.py`, `core.py`, `test_forecast_api.py`, `simulation/engine.py`, `test_risk_api.py`, `schemas.py`, `tools.py`, `_seed_transfer_scenario`, `SimulationEngine`, `asyncio`, `CustomerService`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `SimulationEngine` (e.g. with `Batch` and `Customer`) actually correct?**
  _`SimulationEngine` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Product` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Product` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Store` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Store` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Inventory` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Inventory` has 17 INFERRED edges - model-reasoned connections that need verification._