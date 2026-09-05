# Graph Report - Grocer  (2026-09-05)

## Corpus Check
- 127 files · ~363,487 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1885 nodes · 4158 edges · 129 communities (108 shown, 21 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 293 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dc0d793e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- GrocerValueProp.tsx
- Inventory
- test_decision.py
- test_risk.py
- transfer.py
- test_phase2_simulator.py
- compilerOptions
- test_decision_api.py
- ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification
- test_forecast_api.py
- README.md
- dependencies
- test_phase5_decision.py
- core.py
- EventBus
- test_risk_api.py
- stores.py
- seed_data.py
- AGENTS.md — Grocer Project Rules
- .initialize
- test_agent.py
- Read at the START of EVERY session.
- CustomerService
- create_app
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- forecasting/engine.py
- .prettierrc.json
- types.ts
- layout.tsx
- ForecastingEngine
- Changes Made
- apiClient.ts
- test_phase4_risk.py
- Log Entries
- asyncio
- DemandPoint
- test_forecasting.py
- RecommendationItem
- scenarioEngine.ts
- recommendations.py
- page.tsx
- Grocer — Historical Context & ADRs
- ._fit_and_predict
- OperationsDashboard.tsx
- customers.py
- graphify
- workflows/graphify.md
- simulations.py
- agent.py
- asyncio
- 4. Locked product decisions
- asyncio
- risks.py
- 10. Data model
- GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification
- forecasting.py
- SimulationEngine
- schemas.py
- client
- 15. Recommended Antigravity task sequence
- IP as Logo
- IP as Logo
- env.py
- Other pages
- Locked simulation
- eslint.config.mjs
- StockoutCalculator
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- task.md
- 8. Technology stack
- asyncio
- MetricsComparisonPanel.tsx
- test_health_endpoint_reports_db_status
- fixture
- IMPLEMENTATION_PLAN.md
- .run
- 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)
- client
- get_store_distance_matrix
- 38. Immediate implementation order
- 21. Inventory invariants
- 8. Phase 5 — Decision engine
- detect_anomalies
- seeded_db
- 31. Code review standards
- health_check
- GROCER_V2_MASTER_SPEC.md
- 32. AI coding-agent workflow
- 12. Phase 9 — Integration, testing, and hardening
- apply_scenario
- 22. Simulator
- agents/__init__.py
- services/__init__.py
- 24. Frontend / UX
- 27. Known repository issues to address
- 29. Testing strategy
- 16. Definition of done
- 13. Decision engine
- 6. Phase 3 — Forecasting
- 7. Phase 4 — Risk engine
- 9. Phase 6 — Human approval + LangGraph execution
- 11. Forecasting system
- 9. Responsibility boundaries
- 11. Phase 8 — Customer replenishment workflow
- 3. Phase 0 — Repository audit and baseline
- 4. Phase 1 — Backend as the single source of truth
- test_execute_unknown_recommendation_returns_404
- 5.1 Customer replenishment workflow
- 12. Risk engine
- 15. Explainability
- 23. Scenario mode
- 28. Swiggy MCP integration
- AGENTS.md
- 34. Demo narrative
- test_execute_pending_recommendation_returns_409
- test_execute_approved_hold_returns_completed
- test_execute_approved_transfer_returns_completed
- test_execute_response_has_status_field
- test_execute_response_has_action_type_field
- test_execute_response_has_events_list
- test_execute_stale_inventory_returns_requires_human_review
- test_execute_marks_recommendation_executed
- test_get_run_status_unknown_returns_404
- test_get_run_status_after_execution

## God Nodes (most connected - your core abstractions)
1. `SimulationEngine` - 99 edges
2. `Inventory` - 62 edges
3. `Product` - 56 edges
4. `Store` - 54 edges
5. `Risk` - 53 edges
6. `Recommendation` - 51 edges
7. `Batch` - 47 edges
8. `Supplier` - 42 edges
9. `ForecastingEngine` - 42 edges
10. `RiskEngine` - 41 edges

## Surprising Connections (you probably didn't know these)
- `GrocerApp()` --calls--> `getScenario()`  [EXTRACTED]
  app/page.tsx → lib/scenarioEngine.ts
- `GrocerApp()` --calls--> `runScenarioStep()`  [EXTRACTED]
  app/page.tsx → lib/scenarioEngine.ts
- `CustomerReplenishmentViewProps` --references--> `DarkStore`  [EXTRACTED]
  components/customer/CustomerReplenishmentView.tsx → lib/types.ts
- `LiveEventFeedProps` --references--> `SimulationEvent`  [EXTRACTED]
  components/operations/LiveEventFeed.tsx → lib/types.ts
- `MetricsComparisonPanelProps` --references--> `ScenarioState`  [EXTRACTED]
  components/operations/MetricsComparisonPanel.tsx → lib/types.ts

## Import Cycles
- None detected.

## Communities (129 total, 21 thin omitted)

### Community 0 - "GrocerValueProp.tsx"
Cohesion: 0.43
Nodes (4): GrocerValueProp(), GrocerVelocityCalculator(), PantryItem, usePantryEngine()

### Community 1 - "Inventory"
Cohesion: 0.12
Nodes (48): node_verify(), Verify that the execution side-effects are reflected in the DB. Enforces…, ExecutionRunner, Async runner that drives the LangGraph execution graph for a single…, create_transfer(), MUTATION: Apply a stock transfer from source to destination store. Validates…, Inventory, Recommendation (+40 more)

### Community 2 - "test_decision.py"
Cohesion: 0.08
Nodes (44): ActionScorer, Compute how many units a source store can safely transfer away., Return number of units safely transferable (>=0)., Applies hard reject rules before scoring any transfer., Scores each candidate action using spec section 16 weighted formula., All scoring weights in one place -- no magic numbers scattered., SafeExcessCalculator, ScoringWeights (+36 more)

### Community 3 - "test_risk.py"
Cohesion: 0.17
Nodes (18): All information needed to evaluate spoilage risk for one (store, product)., Evaluates spoilage risk for expiring batches. Supports both single-batch legacy…, SpoilageCalculator, SpoilageInput, TDD tests for the Risk Engine (spec §5, §13, §29.10, Phase 4). Test seams in…, Product expiring in 3 days with low inventory → no spoilage risk., Large stock, expiry in 4h, demand won't cover it → critical spoilage., Probability always in [0.0, 1.0]. (+10 more)

### Community 4 - "transfer.py"
Cohesion: 0.12
Nodes (23): calculate_transfer_eta_minutes(), clear_active_transfers(), dispatch_transfer(), get_active_transfers(), InTransitTransfer, process_arriving_transfers(), AsyncSession, datetime (+15 more)

### Community 5 - "test_phase2_simulator.py"
Cohesion: 0.18
Nodes (20): apply_supplier_delay(), clear_active_pos(), create_purchase_order(), get_active_pos(), process_supplier_deliveries(), PurchaseOrder, AsyncSession, datetime (+12 more)

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

### Community 12 - "test_phase5_decision.py"
Cohesion: 0.08
Nodes (49): DecisionOrchestrator, _naive_now(), AsyncSession, datetime, UUID, GROCER v2 Decision Engine -- DB orchestration layer. Loads risk + inventory +…, Scan all active risks without pending recommendations and generate decisions.…, Set recommendation status to APPROVED and stage a pending Action (spec §18, §21… (+41 more)

### Community 13 - "core.py"
Cohesion: 0.19
Nodes (48): Action, Batch, Customer, Event, Forecast, Order, OrderItem, Product (+40 more)

### Community 14 - "EventBus"
Cohesion: 0.09
Nodes (26): EventBus, Any, AsyncSession, UUID, In-process event bus for GROCER v2. LOCKED (spec §30): async in-process pub/sub…, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler. (+18 more)

### Community 15 - "test_risk_api.py"
Cohesion: 0.09
Nodes (31): client(), asyncio, fixture, TDD API tests for Phase 4 Risk endpoints. Seams under test: 1. GET /api/risks —…, GET /api/risks/{risk_id} returns risk details., GET /api/risks/{random_uuid} returns 404., GET /api/risks?store_id=X returns only risks for that store., GET /api/risks?risk_type=stockout returns only stockout risks. (+23 more)

### Community 16 - "stores.py"
Cohesion: 0.17
Nodes (21): BatchResponse, StoreInventoryResponse, get_store(), get_store_forecasts(), get_store_inventory(), get_store_risks(), _hours_remaining(), list_stores() (+13 more)

### Community 17 - "seed_data.py"
Cohesion: 0.25
Nodes (8): _id(), UUID, Deterministic seed data catalog for the GROCER v2 simulator. Defines 5 dark…, Generate a deterministic UUID from a name., SeedCustomer, SeedProduct, SeedStore, SeedSupplier

### Community 18 - "AGENTS.md — Grocer Project Rules"
Cohesion: 0.25
Nodes (7): 1. PROJECT IDENTITY, 2. TECH STACK, 3. DEV COMMANDS, 4. LOCAL RULES & DESIGN INVARIANTS, 5. EXTERNAL DOCS — SWIGGY BUILDERS CLUB, 6. SESSION RESUME, AGENTS.md — Grocer Project Rules

### Community 19 - ".initialize"
Cohesion: 0.11
Nodes (15): Any, AsyncSession, datetime, UUID, Advance simulation time, generate new orders, handle batch expiry. Returns…, Reset simulation: clear generated data, re-seed, restart clock., Create initial inventory and batches for all store-product pairs., Generate orders day by day for the historical period. (+7 more)

### Community 20 - "test_agent.py"
Cohesion: 0.05
Nodes (87): build_execution_graph(), LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section…, Fail fast if validate produced an error., Divert to recover if world state has changed., Divert to recover on execution error., Divert to recover if verification failed., Build and return the compiled LangGraph execution graph., _route_after_execute() (+79 more)

### Community 21 - "Read at the START of EVERY session."
Cohesion: 0.40
Nodes (4): CONTEXT.md — Domain Language & Rules, Core Entities & Product Purpose, Invariants & Design Rules (Never Break), Read at the START of EVERY session.

### Community 22 - "CustomerService"
Cohesion: 0.15
Nodes (19): CustomerReorderResult, CustomerState, PantryStapleState, Customer domain models for Phase 9 Customer / WhatsApp simulation. Defines data…, WhatsAppInteractionMessage, CustomerService, Any, AsyncSession (+11 more)

### Community 23 - "create_app"
Cohesion: 0.11
Nodes (29): get_db(), AsyncSession, create_app(), lifespan(), set_sqlite_pragma(), asyncio, Tests for Phase 9 Customer / WhatsApp replenishment endpoints (Spec §22 &…, POST /api/customers/{id}/reorder should deduct inventory and create order. (+21 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.13
Nodes (15): Automated Tests, Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, Finalized Architecture & Design Decisions, Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me), Manual Verification, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx) (+7 more)

### Community 25 - "forecasting/engine.py"
Cohesion: 0.29
Nodes (9): GROCER v2 Forecasting Engine. Orchestrates forecast generation over simulator…, compute_confidence(), evaluate_forecast(), ModelEvaluationResult, GROCER v2 Forecasting — Pure mathematical models. Implements spec §12: Level 1…, Return a composite confidence score in [0.0, 1.0]. Four factors combined…, Compute MAE, RMSE, and MAPE from parallel actual/predicted sequences., Evaluation of a forecast model against known ground truth. (+1 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "types.ts"
Cohesion: 0.10
Nodes (31): CustomerReplenishmentView(), CustomerReplenishmentViewProps, DemoLayoutMode, PANTRY_ITEMS, GrocerHero(), GrocerHeroProps, PhoneMockup(), IphoneFrame() (+23 more)

### Community 28 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 29 - "ForecastingEngine"
Cohesion: 0.09
Nodes (28): ForecastingEngine, Generates Forecast rows from historical Order data in the simulation DB. Usage:…, asyncio, ForecastingEngine runs on seeded simulation data and writes Forecast rows., All generated Forecast rows have confidence in [0.0, 1.0]., ForecastingEngine emits FORECAST_UPDATED events for each forecast generated., test_forecasting_engine_confidence_in_range(), test_forecasting_engine_emits_event() (+20 more)

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "apiClient.ts"
Cohesion: 0.11
Nodes (17): BackendAgentRun, BackendCustomerDetail, BackendCustomerListItem, BackendCustomerMessageResponse, BackendCustomerMessages, BackendCustomerRemindResponse, BackendCustomerReorderResponse, BackendCustomerSkipResponse (+9 more)

### Community 32 - "test_phase4_risk.py"
Cohesion: 0.13
Nodes (26): GROCER v2 Risk Engine. Orchestrates risk detection across inventory, forecasts,…, BatchInfo, discount_tier_for_hours(), DiscountTier, MultiBatchSpoilageInput, str, GROCER v2 Risk Engine — Pure deterministic risk models. Implements spec §5…, Computed risk assessment for one (store, product, risk_type) combination. (+18 more)

### Community 33 - "Log Entries"
Cohesion: 0.15
Nodes (12): [Grocer — Complete WhatsApp Demo Redesign & Operational Clutter Removal] 2026-09-04, [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — Official App Icon Design & Full UI Architecture Overhaul] 2026-09-02, [Grocer — Phase 0 Audit, Phase 1 Backend Foundation & Phase 2 Simulator Engine] 2026-08-27, [Grocer — Phase 0 Repository Audit & v2 Architecture Alignment] 2026-08-26, [Grocer — Phase 9 Customer / WhatsApp Integration & Phase 10 Hardening & Polish] 2026-08-28, [Grocer — Saved Exact Figma Notification Layout & WhatsApp Icon] 2026-08-15, [Grocer — UI Aesthetics, 3-Column Cockpit, Phase 3/4/5/6 Engines & Phase 7 Live Integration] 2026-08-27 (+4 more)

### Community 34 - "asyncio"
Cohesion: 0.12
Nodes (23): AsyncClient, asyncio, AsyncSession, Same seed should produce same number of orders., Inventory quantities should never be negative after orders., Advancing time should create new orders and update simulation., A Simulation record should be created in the DB., POST /api/simulations/ should create a simulation. (+15 more)

### Community 35 - "DemandPoint"
Cohesion: 0.11
Nodes (26): baseline_predict(), clean_demand_series(), _compute_dow_multiplier(), DemandPoint, exponential_smoothing_predict(), Return a cleaned copy of *series* with anomalous quantities replaced by the…, Predict total demand over *horizon_hours* using a moving average baseline.…, Return the seasonal multiplier for a given day-of-week. Multiplier =… (+18 more)

### Community 36 - "test_forecasting.py"
Cohesion: 0.09
Nodes (21): TDD tests for the forecasting engine (spec §12). Test seams, in order of the…, compute_confidence always returns a value in [0.0, 1.0]., Higher coefficient of variation yields lower confidence., More anomalies in history → lower confidence., Fewer data points → lower confidence., Perfect forecasts yield MAE=0, RMSE=0, MAPE=0., MAE is correctly computed from a worked example., RMSE is correctly computed from a worked example. (+13 more)

### Community 37 - "RecommendationItem"
Cohesion: 0.17
Nodes (15): LiveEventFeed(), LiveEventFeedProps, RecommendationCard(), RecommendationCardProps, RecommendationStream(), RecommendationStreamProps, WhyInspectorPanel(), WhyInspectorPanelProps (+7 more)

### Community 38 - "scenarioEngine.ts"
Cohesion: 0.27
Nodes (9): BaselineStepResult, buildFailureScenario(), buildHeroScenario(), buildPerishablesScenario(), getScenario(), mulberry32(), runScenarioStep(), ScenarioDefinition (+1 more)

### Community 39 - "recommendations.py"
Cohesion: 0.17
Nodes (23): approve_recommendation(), batch_evaluate_recommendations(), evaluate_recommendation(), get_recommendation(), list_recommendations(), AsyncSession, get, post (+15 more)

### Community 40 - "page.tsx"
Cohesion: 0.13
Nodes (19): defaultScenarioState(), GrocerApp(), GrocerFAQ(), GrocerFooter(), GrocerFooterProps, GrocerIntegrations(), AppGlobalHeader(), AppGlobalHeaderProps (+11 more)

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

### Community 42 - "._fit_and_predict"
Cohesion: 0.27
Nodes (6): AsyncSession, UUID, Query all delivered orders and aggregate demand by (store, product, day) with…, Fit both models, optionally compare on holdout, return (prediction, model_name,…, Perform empirical rolling-origin backtesting across historical orders. Splits…, Generate forecasts for every (store, product) pair across specified horizons.…

### Community 43 - "OperationsDashboard.tsx"
Cohesion: 0.20
Nodes (12): OperationsDashboard(), CATALOG_ITEMS, SkuCatalogItem, SkuInventoryTable(), SkuInventoryTableProps, SkuRowItem, SpatialTopologyView(), SpatialTopologyViewProps (+4 more)

### Community 44 - "customers.py"
Cohesion: 0.11
Nodes (33): get_customer(), get_customer_messages(), list_customers(), AsyncSession, get, post, UUID, FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8). Provides: - GET… (+25 more)

### Community 47 - "simulations.py"
Cohesion: 0.14
Nodes (29): advance_simulation(), AdvanceTimeRequest, ApplyScenarioRequest, create_simulation(), CreateSimulationRequest, get_active_simulation(), _get_or_restore_engine(), get_simulation() (+21 more)

### Community 48 - "agent.py"
Cohesion: 0.10
Nodes (22): Execution agent subpackage -- LangGraph 5-node execution graph., _naive_now(), AsyncSession, datetime, UUID, Agent ExecutionRunner -- async entry point for the execution graph. Usage:…, Typed result returned by ExecutionRunner.run()., Run the execution graph for the given recommendation. Returns a RunResult… (+14 more)

### Community 49 - "asyncio"
Cohesion: 0.15
Nodes (13): asyncio, Advancing through high order volume never drives inventory or batch quantities…, Expired batches must have quantity=0 or be excluded from inventory derivation., Identical seeds produce identical simulation clocks and entity counts., GET /api/simulations/{id}/network returns store nodes and distance matrix., GET /api/simulations/{id}/in-transit returns active transfers and purchase…, POST /api/simulations/{id}/scenario applies operational scenario., test_api_apply_scenario() (+5 more)

### Community 50 - "4. Locked product decisions"
Cohesion: 0.12
Nodes (17): 4.10 Transfer ETA, 4.11 Supplier simulation, 4.12 Markdown simulation, 4.13 Batch-level expiry, 4.1 Stores, 4.2 Products, 4.3 Customers, 4.4 Historical data (+9 more)

### Community 51 - "asyncio"
Cohesion: 0.23
Nodes (12): asyncio, AsyncSession, Should persist an Event with JSON payload., Should persist a Store with all required fields., Should persist a Supplier., Should persist a Product linked to a Supplier., Should persist a Customer linked to a home Store., test_create_customer_with_store_fk() (+4 more)

### Community 52 - "risks.py"
Cohesion: 0.21
Nodes (15): evaluate_risks(), get_risk(), list_risks(), AsyncSession, get, post, UUID, Risk REST API — spec §32. Endpoints: GET /api/risks — list risks with optional… (+7 more)

### Community 53 - "10. Data model"
Cohesion: 0.13
Nodes (15): 10.10 Markdown, 10.11 Recommendation, 10.12 Approval, 10.13 Audit/event log, 10.14 Simulation state, 10.1 Store, 10.2 Product, 10.3 Batch (+7 more)

### Community 54 - "GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification"
Cohesion: 0.14
Nodes (13): 1. Visual Foundation & Tone, 2.1 Surfaces & Structure, 2.2 Operator Action Tokens (The 4 Core Actions), 2.3 Risk Severity Tokens, 2. Comprehensive Color & Semantic Token System, 3. Button & Interactive Element Hierarchy, 4. Typography Hierarchy, 5. Operations Cockpit Layout (3-Column Architecture) (+5 more)

### Community 55 - "forecasting.py"
Cohesion: 0.21
Nodes (13): evaluate_models(), generate_forecasts(), list_forecasts(), AsyncSession, get, post, UUID, Forecast REST API — spec §32. Endpoints: GET /api/forecasts — list forecasts… (+5 more)

### Community 56 - "SimulationEngine"
Cohesion: 0.08
Nodes (40): Detects inventory stockout and batch spoilage risks. Usage: engine =…, RiskEngine, Core simulation engine for GROCER v2. Handles: - Database seeding (stores,…, SimulationEngine, Full seeded DB: sim + forecast + risks evaluated., seeded_db(), test_recalculate_options_creates_new_recommendation(), Seed simulator, run forecasting, run risk evaluation, return db. (+32 more)

### Community 57 - "schemas.py"
Cohesion: 0.18
Nodes (18): get_product(), list_products(), AsyncSession, get, UUID, Products REST API — spec §32.4. Endpoints: GET /api/products — list all catalog…, List all 25 catalog products., Get a single product by ID. (+10 more)

### Community 58 - "client"
Cohesion: 0.18
Nodes (11): client(), db_session(), event_loop(), AsyncClient, AsyncSession, fixture, Create a single event loop for the entire test session., Create all tables before each test, drop after. (+3 more)

### Community 59 - "15. Recommended Antigravity task sequence"
Cohesion: 0.13
Nodes (15): 15. Recommended Antigravity task sequence, Task 01, Task 02, Task 03, Task 04, Task 05, Task 06, Task 07 (+7 more)

### Community 60 - "IP as Logo"
Cohesion: 0.20
Nodes (9): Color and canvas, Complexity budget, Delivery behavior, IP as Logo, Prompt skeleton, Route constraints by generator capability, Shape language and composition, Simplicity and visual treatment (+1 more)

### Community 61 - "IP as Logo"
Cohesion: 0.22
Nodes (8): Agent compatibility, Install, IP as Logo, License, Model behavior, Repository structure, Use, What it guides

### Community 62 - "env.py"
Cohesion: 0.28
Nodes (5): do_run_migrations(), run_async_migrations(), run_migrations_online(), Settings, BaseSettings

### Community 63 - "Other pages"
Cohesion: 0.14
Nodes (14): 10. Phase 7 — Operations frontend, Acceptance criteria, Activity/Audit, Customer, Dashboard, Goal, Inventory, Other pages (+6 more)

### Community 64 - "Locked simulation"
Cohesion: 0.14
Nodes (14): 5. Phase 2 — Operational simulator, Acceptance criteria, Batches, Demand, Goal, Historical demand, Invariants, Locked simulation (+6 more)

### Community 66 - "StockoutCalculator"
Cohesion: 0.09
Nodes (29): Evaluates stockout risk from current inventory vs forecast demand. Algorithm:…, Configurable thresholds and weights for the Risk Engine., All information needed to evaluate stockout risk for one (store, product)., RiskConfig, StockoutCalculator, StockoutInput, Low forecast confidence widens the required safety buffer, increasing risk., Custom RiskConfig thresholds alter the severity cutoffs. (+21 more)

### Community 71 - "8. Technology stack"
Cohesion: 0.25
Nodes (8): 8. Technology stack, Agent, Backend, Database, Forecasting, Frontend, Local environment, Realtime

### Community 72 - "asyncio"
Cohesion: 0.15
Nodes (13): asyncio, Derivation invariant: sum of active batch quantities matches inventory for all…, POST /api/simulations/{id}/reset cleans and creates a new simulation ID., GET /api/simulations/active creates and initializes a default simulation if…, Subsequent calls to /api/simulations/active return the same simulation., POST /api/simulations/{id}/advance updates current_time in DB and returns state., Simulation operations succeed even when in-memory _engines dict is wiped., test_active_simulation_creates_default_when_empty() (+5 more)

### Community 73 - "MetricsComparisonPanel.tsx"
Cohesion: 0.26
Nodes (9): MetricsComparisonPanel(), MetricsComparisonPanelProps, OperationsDashboardProps, SimulationFloatingIsland(), SimulationFloatingIslandProps, computeDeltas(), SCENARIOS, ScenarioState (+1 more)

### Community 74 - "test_health_endpoint_reports_db_status"
Cohesion: 0.38
Nodes (6): AsyncClient, asyncio, Health endpoint should report database connectivity., Health endpoint should return 200 with status healthy., test_health_endpoint_reports_db_status(), test_health_endpoint_returns_200()

### Community 75 - "fixture"
Cohesion: 0.22
Nodes (9): client(), client_with_hold(), client_with_pending(), client_with_transfer(), fixture, HTTP client wired to seeded DB., HTTP client wired to DB that has an approved transfer rec., HTTP client wired to DB that has an approved hold rec. (+1 more)

### Community 76 - "IMPLEMENTATION_PLAN.md"
Cohesion: 0.17
Nodes (11): 0. Rules for implementation, 13. Phase 10 — Documentation and final demo, 14. Agent execution protocol for Antigravity, 17. What not to build, 18. Final engineering principle, 1. Target architecture, 2. Implementation order, Architecture documentation (+3 more)

### Community 77 - ".run"
Cohesion: 0.25
Nodes (7): _naive_now(), AsyncSession, datetime, UUID, Mark an active risk as RESOLVED and emit RISK_RESOLVED event., Return naive current UTC datetime for database compatibility., Scan all inventory and batches, evaluate risks, persist rows and emit events.…

### Community 78 - "2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)"
Cohesion: 0.18
Nodes (10): 1. Executive Summary, 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK), 3. Test & Runtime Baseline, DELETE / DEPRECATE, Key Audit Findings, MISSING, Phase 0: Repository Audit & Technical Baseline, REFACTOR (+2 more)

### Community 79 - "client"
Cohesion: 0.40
Nodes (5): client(), fixture, Seed simulator data and return the db session., HTTP client wired to the seeded test DB via dependency override., seeded_db()

### Community 80 - "get_store_distance_matrix"
Cohesion: 0.25
Nodes (8): calculate_haversine_distance(), get_store_distance_matrix(), Calculate the great-circle distance between two geographic points in kilometers., Generate the 5x5 inter-store distance matrix (in km) for the dark store network., Bandra to Andheri distance should be ~7.4 km., Matrix should cover all 5 dark stores with zero diagonal and positive symmetric…, test_calculate_haversine_distance(), test_store_network_distance_matrix()

### Community 81 - "38. Immediate implementation order"
Cohesion: 0.18
Nodes (11): 10. Testing + demo hardening, 1. Repository audit + cleanup, 2. Backend source-of-truth refactor, 38. Immediate implementation order, 3. Data/model consistency, 4. Simulation engine, 5. Forecasting + risk, 6. Decision engine (+3 more)

### Community 82 - "21. Inventory invariants"
Cohesion: 0.18
Nodes (11): 21. Inventory invariants, Invariant 1, Invariant 10, Invariant 2, Invariant 3, Invariant 4, Invariant 5, Invariant 6 (+3 more)

### Community 83 - "8. Phase 5 — Decision engine"
Cohesion: 0.18
Nodes (11): 8. Phase 5 — Decision engine, Acceptance criteria, Candidate actions, Example, Explainability, Goal, Hard constraints, Objective factors (+3 more)

### Community 84 - "detect_anomalies"
Cohesion: 0.20
Nodes (10): detect_anomalies(), _percentile(), Return list of indices in *series* whose quantity is a statistical outlier.…, Compute a percentile from a pre-sorted list using linear interpolation., Z-score > 3 on a 6x spike is flagged as anomaly., No anomalies detected when demand is perfectly uniform., Empty series yields empty anomaly list without error., test_detect_anomalies_empty_series_returns_empty() (+2 more)

### Community 85 - "seeded_db"
Cohesion: 0.67
Nodes (3): fixture, Seed database with simulation base data., seeded_db()

### Community 86 - "31. Code review standards"
Cohesion: 0.22
Nodes (9): 31. Code review standards, Agent boundary, Architecture, Correctness, Explainability, Invariants, Scope, Security (+1 more)

### Community 87 - "health_check"
Cohesion: 0.50
Nodes (4): health_check(), AsyncSession, get, Health check endpoint. Verifies API and database connectivity.

### Community 88 - "GROCER_V2_MASTER_SPEC.md"
Cohesion: 0.07
Nodes (27): 0. How to use this document, 14. Decision scoring, 16. Recommendation ranking, 17. Human approval and safety, 18. LangGraph agent, 19. Execution tools, 1. Product definition, 20. Verification (+19 more)

### Community 89 - "32. AI coding-agent workflow"
Cohesion: 0.22
Nodes (9): 32. AI coding-agent workflow, Phase A — audit, Phase B — foundation, Phase C — intelligence, Phase D — execution, Phase E — simulation, Phase F — customer integration, Phase G — frontend (+1 more)

### Community 90 - "12. Phase 9 — Integration, testing, and hardening"
Cohesion: 0.22
Nodes (9): 12. Phase 9 — Integration, testing, and hardening, Failure testing, Full system test, Performance, Required scenario tests, Scenario A — Stockout, Scenario B — Spoilage, Scenario C — Network imbalance (+1 more)

### Community 91 - "apply_scenario"
Cohesion: 0.17
Nodes (12): apply_scenario(), get_scenario_config(), Any, AsyncSession, Retrieve scenario configuration parameters., Inject scenario conditions into the live simulation database., All 5 canonical scenarios exist with distinct demand and lead-time…, network_imbalance creates severe excess in Bandra and drains Andheri. (+4 more)

### Community 92 - "22. Simulator"
Cohesion: 0.25
Nodes (8): 22.1 Initial state, 22.2 Time control, 22.3 Demand generation, 22.4 Expiry, 22.5 Supplier flow, 22.6 Transfer flow, 22.7 Markdown flow, 22. Simulator

### Community 95 - "24. Frontend / UX"
Cohesion: 0.25
Nodes (8): 24.1 Primary navigation, 24.2 Overview page, 24.3 Inventory page, 24.4 Recommendation UI, 24.5 Detail pages, 24.6 Map, 24.7 Visual references, 24. Frontend / UX

### Community 99 - "27. Known repository issues to address"
Cohesion: 0.25
Nodes (8): 27.1 Frontend simulation state duplication, 27.2 Simulation advance bug, 27.3 Reset/stale simulation IDs, 27.4 Decision engine simplicity, 27.5 Transfer verification, 27.6 Stale implementation plan, 27.7 Swiggy integration boundary, 27. Known repository issues to address

### Community 100 - "29. Testing strategy"
Cohesion: 0.25
Nodes (8): 29.1 Unit tests, 29.2 Domain invariant tests, 29.3 Integration tests, 29.4 API tests, 29.5 Frontend tests, 29.6 Scenario tests, 29.7 Regression suite, 29. Testing strategy

### Community 101 - "16. Definition of done"
Cohesion: 0.25
Nodes (8): 16. Definition of done, Agents, Architecture, Customer workflow, Frontend, Intelligence, Quality, Simulation

### Community 102 - "13. Decision engine"
Cohesion: 0.29
Nodes (7): 13.1 Candidate actions, 13.2 Hard constraints, 13.3 Transfer reasoning, 13.4 Reorder reasoning, 13.5 Discount reasoning, 13.6 Hold reasoning, 13. Decision engine

### Community 103 - "6. Phase 3 — Forecasting"
Cohesion: 0.29
Nodes (7): 6. Phase 3 — Forecasting, Acceptance criteria, Evaluation, Goal, Implement, Rule, Tests

### Community 104 - "7. Phase 4 — Risk engine"
Cohesion: 0.29
Nodes (7): 7. Phase 4 — Risk engine, Acceptance criteria, Goal, Requirements, Spoilage risk, Stockout risk, Tests

### Community 105 - "9. Phase 6 — Human approval + LangGraph execution"
Cohesion: 0.29
Nodes (7): 9. Phase 6 — Human approval + LangGraph execution, Acceptance criteria, Critical rules, Failure cases, Goal, LangGraph flow, Verification

### Community 106 - "11. Forecasting system"
Cohesion: 0.33
Nodes (6): 11.1 Goal, 11.2 Baseline first, 11.3 Model selection, 11.4 Confidence, 11.5 Anomalies, 11. Forecasting system

### Community 107 - "9. Responsibility boundaries"
Cohesion: 0.33
Nodes (6): 9. Responsibility boundaries, Database, Decision engine, Forecasting, LLM / agent, Risk engine

### Community 108 - "11. Phase 8 — Customer replenishment workflow"
Cohesion: 0.33
Nodes (6): 11. Phase 8 — Customer replenishment workflow, Acceptance criteria, Flow, Goal, Integration boundary, Swiggy MCP safety

### Community 109 - "3. Phase 0 — Repository audit and baseline"
Cohesion: 0.33
Nodes (6): 3. Phase 0 — Repository audit and baseline, Acceptance criteria, Audit questions, Deliverable, Goal, Inspect

### Community 110 - "4. Phase 1 — Backend as the single source of truth"
Cohesion: 0.33
Nodes (6): 4. Phase 1 — Backend as the single source of truth, Acceptance criteria, Goal, Implement, Required fixes, Tests

### Community 112 - "5.1 Customer replenishment workflow"
Cohesion: 0.40
Nodes (5): 5.1 Customer replenishment workflow, 5.2 Operations workflow, 5. Two workflows, External commerce integration, Safety

### Community 113 - "12. Risk engine"
Cohesion: 0.50
Nodes (4): 12.1 Stockout risk, 12.2 Spoilage risk, 12.3 Severity, 12. Risk engine

### Community 114 - "15. Explainability"
Cohesion: 0.50
Nodes (4): 15. Explainability, Why did this happen?, Why not the alternatives?, Why this action?

### Community 115 - "23. Scenario mode"
Cohesion: 0.50
Nodes (4): 23. Scenario mode, Scenario A — cross-store stockout, Scenario B — perishable expiry, Scenario C — supplier delay

### Community 116 - "28. Swiggy MCP integration"
Cohesion: 0.50
Nodes (4): 28.1 Adapter architecture, 28.2 Customer flow, 28.3 Credential safety, 28. Swiggy MCP integration

### Community 118 - "34. Demo narrative"
Cohesion: 0.67
Nodes (3): 34. Demo narrative, Primary demo, Secondary demo

## Knowledge Gaps
- **443 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+438 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SimulationEngine` connect `SimulationEngine` to `Inventory`, `test_risk.py`, `transfer.py`, `test_phase2_simulator.py`, `test_decision_api.py`, `test_forecast_api.py`, `test_phase5_decision.py`, `core.py`, `test_risk_api.py`, `seed_data.py`, `.initialize`, `test_agent.py`, `create_app`, `forecasting/engine.py`, `ForecastingEngine`, `test_phase4_risk.py`, `asyncio`, `test_forecasting.py`, `simulations.py`, `asyncio`, `client`, `seeded_db`, `apply_scenario`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `ForecastingEngine` connect `ForecastingEngine` to `test_phase4_risk.py`, `test_risk.py`, `test_forecasting.py`, `test_decision_api.py`, `._fit_and_predict`, `test_phase5_decision.py`, `core.py`, `test_risk_api.py`, `test_agent.py`, `forecasting.py`, `SimulationEngine`, `forecasting/engine.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `Inventory` connect `Inventory` to `test_phase4_risk.py`, `test_risk.py`, `transfer.py`, `test_phase2_simulator.py`, `test_phase5_decision.py`, `core.py`, `test_risk_api.py`, `stores.py`, `.initialize`, `test_agent.py`, `CustomerService`, `create_app`, `SimulationEngine`, `forecasting/engine.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `SimulationEngine` (e.g. with `Batch` and `Customer`) actually correct?**
  _`SimulationEngine` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Inventory` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Inventory` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Product` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Product` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Store` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Store` has 19 INFERRED edges - model-reasoned connections that need verification._