# Graph Report - Grocer  (2026-09-05)

## Corpus Check
- 102 files · ~117,953 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1514 nodes · 3156 edges · 99 communities (88 shown, 11 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 326 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0754bc26`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SwiggyMCPAdapter
- create_app
- MockCommerceAdapter
- compilerOptions
- ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification
- README.md
- dependencies
- EventBus
- stores.py
- .agents/AGENTS.md
- SimulationEngine
- core.py
- Read at the START of EVERY session.
- CustomerService
- test_customer_api.py
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- forecasting/engine.py
- .prettierrc.json
- mockData.ts
- layout.tsx
- UUID
- Changes Made
- apiClient.ts
- risk/engine.py
- Log Entries
- scenarioEngine.ts
- recommendations.py
- metricsEngine.ts
- Grocer — Historical Context & ADRs
- types.ts
- schemas.py
- graphify
- workflows/graphify.md
- simulations.py
- runner.py
- decision/models.py
- 4. Locked product decisions
- resolve_risk
- 10. Data model
- GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification
- products.py
- db_session
- 15. Recommended Antigravity task sequence
- IP as Logo
- IP as Logo
- env.py
- Other pages
- Locked simulation
- eslint.config.mjs
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- Tracer Bullets: Codebase Cleanup, Architecture Refactoring & Bloat Purge
- 8. Technology stack
- test_health_endpoint_reports_db_status
- 38. Immediate implementation order (100% Complete & Verified)
- IMPLEMENTATION_PLAN.md
- 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)
- test_phase8_commerce.py
- 21. Inventory invariants
- 8. Phase 5 — Decision engine
- 31. Code review standards
- health_check
- GROCER_V2_MASTER_SPEC.md
- 32. AI coding-agent workflow
- 12. Phase 9 — Integration, testing, and hardening
- CommerceError
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
- 5.1 Customer replenishment workflow
- 12. Risk engine
- 15. Explainability
- 23. Scenario mode
- 28. Swiggy MCP integration
- AGENTS.md
- 34. Demo narrative
- agent.py
- service.py
- CommerceProductItem
- CustomerReplenishmentView.tsx
- page.tsx

## God Nodes (most connected - your core abstractions)
1. `CustomerService` - 47 edges
2. `SimulationEngine` - 44 edges
3. `SwiggyMCPAdapter` - 42 edges
4. `Product` - 38 edges
5. `Inventory` - 37 edges
6. `Batch` - 36 edges
7. `MockCommerceAdapter` - 35 edges
8. `Store` - 35 edges
9. `Event` - 35 edges
10. `CommercePort` - 31 edges

## Surprising Connections (you probably didn't know these)
- `CustomerReplenishmentViewProps` --references--> `CustomerPersona`  [EXTRACTED]
  components/customer/CustomerReplenishmentView.tsx → lib/types.ts
- `AppGlobalHeaderProps` --references--> `CustomerPersona`  [EXTRACTED]
  components/navigation/AppGlobalHeader.tsx → lib/types.ts
- `GrocerConsumerApp()` --calls--> `transformStores()`  [EXTRACTED]
  app/page.tsx → lib/apiClient.ts
- `RunResult` --uses--> `AgentState`  [INFERRED]
  backend/agents/execution/runner.py → backend/agents/execution/state.py
- `ExecutionRunner` --uses--> `AgentState`  [INFERRED]
  backend/agents/execution/runner.py → backend/agents/execution/state.py

## Import Cycles
- None detected.

## Communities (99 total, 11 thin omitted)

### Community 0 - "SwiggyMCPAdapter"
Cohesion: 0.18
Nodes (8): DeliveryTrackingStatus, Live status and ETA of an in-flight order., Any, Classify errors from Swiggy envelope per official error taxonomy., Production adapter for Swiggy Instamart MCP server., Execute JSON-RPC tool call against Swiggy Instamart MCP endpoint., SwiggyMCPAdapter, Get live order delivery status and ETA via CommercePort.

### Community 1 - "create_app"
Cohesion: 0.24
Nodes (10): get_db(), AsyncSession, create_app(), lifespan(), client(), AsyncClient, Provide an async HTTP client for API testing., set_sqlite_pragma() (+2 more)

### Community 5 - "MockCommerceAdapter"
Cohesion: 0.12
Nodes (27): ItemOutOfStockError, MinOrderNotMetError, Canonical exception taxonomy for CommercePort and Swiggy Instamart integration., Raised when checkout is attempted without explicit human/user confirmation. In…, Raised when an item or variant requested in update_cart is not in stock., Raised when cart grand total is below minimum order threshold., UnconfirmedCheckoutError, Commerce integration layer for Grocer (Spec §5.1, §28, & §38.9). Provides the… (+19 more)

### Community 6 - "compilerOptions"
Cohesion: 0.07
Nodes (28): dom, dom.iterable, esnext, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules (+20 more)

### Community 8 - "ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification"
Cohesion: 0.18
Nodes (10): 1. PRODUCT VISION & SCOPE, 2. MODULAR MONOLITH ARCHITECTURE, 3. CORE FRONTEND VIEWS & CAPABILITIES, 4. SAFETY INVARIANTS & AUTONOMY BOUNDARIES, 5. DESIGN & TYPOGRAPHY TOKENS, A. Navigation & View Controller (`app/page.tsx`), ARCHITECTURE.md — Grocer v2 System Architecture & Design Specification, B. Operations Deck Tabs (+2 more)

### Community 10 - "README.md"
Cohesion: 0.12
Nodes (15): 1. Frontend Setup, 1. Proactive WhatsApp Conversational Restock, 2. Backend Setup, 2. Interactive Household Pantry Telemetry, 3. Swiggy Instamart CommercePort Integration, 4. Strict Consequential Action Guard (Spec §28.3 & §39.15), 5. 25 Realistic Mumbai Household Personas, 📱 Features (+7 more)

### Community 11 - "dependencies"
Cohesion: 0.04
Nodes (45): clsx, eslint, eslint-config-next, framer-motion, lucide-react, next, dependencies, clsx (+37 more)

### Community 14 - "EventBus"
Cohesion: 0.09
Nodes (25): EventBus, Any, AsyncSession, UUID, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler., Publish an event. - Calls all registered handlers for *event_type*. - If… (+17 more)

### Community 16 - "stores.py"
Cohesion: 0.14
Nodes (28): BaseSchema, BatchResponse, EventResponse, ForecastResponse, InventoryItemResponse, RiskResponse, StoreDetailResponse, StoreInventoryResponse (+20 more)

### Community 18 - ".agents/AGENTS.md"
Cohesion: 0.29
Nodes (6): 1. PROJECT IDENTITY, 2. TECH STACK, 3. DEV COMMANDS, 4. LOCAL RULES & DESIGN INVARIANTS, 5. EXTERNAL DOCS — SWIGGY BUILDERS CLUB, 6. SESSION RESUME

### Community 19 - "SimulationEngine"
Cohesion: 0.08
Nodes (24): Any, AsyncSession, datetime, UUID, Advance simulation time, generate new orders, handle batch expiry. Returns…, Reset simulation: clear generated data, re-seed, restart clock., Seed stores, suppliers, products, and customers., Create initial inventory and batches for all store-product pairs. (+16 more)

### Community 20 - "core.py"
Cohesion: 0.05
Nodes (137): build_execution_graph(), LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section…, Fail fast if validate produced an error., Divert to recover if world state has changed., Divert to recover on execution error., Divert to recover if verification failed., Build and return the compiled LangGraph execution graph., _route_after_execute() (+129 more)

### Community 21 - "Read at the START of EVERY session."
Cohesion: 0.50
Nodes (3): Core Entities & Product Purpose, Invariants & Design Rules (Never Break), Read at the START of EVERY session.

### Community 22 - "CustomerService"
Cohesion: 0.09
Nodes (22): CustomerService, Any, AsyncSession, UUID, Fetch payment options (UPI, COD) via CommercePort., Consequential customer checkout. Strictly requires explicit confirmation. If db…, Internal helper to record commerce order into shared database and deduct stock., List all customers with home store linkage and quick pantry status. (+14 more)

### Community 23 - "test_customer_api.py"
Cohesion: 0.15
Nodes (18): asyncio, Tests for Phase 9 Customer / WhatsApp replenishment endpoints (Spec §22 &…, POST /api/customers/{id}/reorder should deduct inventory and create order., POST /api/customers/{id}/remind should schedule reminder., POST /api/customers/{id}/skip should record skip., GET /api/customers should list all seeded customers., GET /api/customers/{id} should return customer profile and pantry staples., GET /api/customers/{id} should return 404 for unknown customer. (+10 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.13
Nodes (15): Automated Tests, Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, Finalized Architecture & Design Decisions, Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me), Manual Verification, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx) (+7 more)

### Community 25 - "forecasting/engine.py"
Cohesion: 0.09
Nodes (41): evaluate_models(), generate_forecasts(), list_forecasts(), AsyncSession, get, post, UUID, Forecast REST API — spec §32. Endpoints: GET /api/forecasts — list forecasts… (+33 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "mockData.ts"
Cohesion: 0.23
Nodes (12): PhoneMockup(), IphoneFrame(), IphoneFrameProps, getSimulatedPantryStaples(), processWhatsAppSimulationMessage(), usePhoneDemoEngine(), DEFAULT_CUSTOMER_PERSONA, DEFAULT_PANTRY_STAPLES (+4 more)

### Community 28 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 29 - "UUID"
Cohesion: 0.08
Nodes (38): checkout_customer(), clear_customer_cart(), get_adapter_info(), get_customer(), get_customer_addresses(), get_customer_cart(), get_customer_go_to_items(), get_customer_messages() (+30 more)

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "apiClient.ts"
Cohesion: 0.08
Nodes (21): BackendAgentRun, BackendAgentRunEvent, BackendCommerceCartItem, BackendCommercePaymentOption, BackendCommerceProductVariant, BackendCustomerDetail, BackendCustomerListItem, BackendCustomerMessageResponse (+13 more)

### Community 32 - "risk/engine.py"
Cohesion: 0.09
Nodes (32): _naive_now(), AsyncSession, datetime, UUID, GROCER v2 Risk Engine. Orchestrates risk detection across inventory, forecasts,…, Mark an active risk as RESOLVED and emit RISK_RESOLVED event., Return naive current UTC datetime for database compatibility., Scan all inventory and batches, evaluate risks, persist rows and emit events.… (+24 more)

### Community 33 - "Log Entries"
Cohesion: 0.14
Nodes (13): [Grocer — Complete WhatsApp Demo Redesign & Operational Clutter Removal] 2026-09-04, [Grocer — Customer Replenishment, Swiggy MCP Integration & Full 10-Phase Completion] 2026-09-05, [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — Official App Icon Design & Full UI Architecture Overhaul] 2026-09-02, [Grocer — Phase 0 Audit, Phase 1 Backend Foundation & Phase 2 Simulator Engine] 2026-08-27, [Grocer — Phase 0 Repository Audit & v2 Architecture Alignment] 2026-08-26, [Grocer — Phase 9 Customer / WhatsApp Integration & Phase 10 Hardening & Polish] 2026-08-28, [Grocer — Saved Exact Figma Notification Layout & WhatsApp Icon] 2026-08-15 (+5 more)

### Community 38 - "scenarioEngine.ts"
Cohesion: 0.16
Nodes (15): INITIAL_RECOMMENDATIONS, BaselineStepResult, buildFailureScenario(), buildHeroScenario(), buildPerishablesScenario(), getScenario(), mulberry32(), runScenarioStep() (+7 more)

### Community 39 - "recommendations.py"
Cohesion: 0.17
Nodes (23): approve_recommendation(), batch_evaluate_recommendations(), evaluate_recommendation(), get_recommendation(), list_recommendations(), AsyncSession, get, post (+15 more)

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

### Community 43 - "types.ts"
Cohesion: 0.18
Nodes (10): ActionStatus, ActionType, CustomerOrderItem, PhoneMockupProps, RecommendationAlternative, RiskSeverity, ScenarioState, SimulationState (+2 more)

### Community 44 - "schemas.py"
Cohesion: 0.13
Nodes (36): FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8). Provides: - GET…, AgentRunResponse, AgentRunStatusResponse, CartItemUpdatePayload, CommerceAdapterInfoResponse, CommerceCartItemResponse, CommerceCartResponse, CommerceCartUpdateRequest (+28 more)

### Community 47 - "simulations.py"
Cohesion: 0.06
Nodes (60): advance_simulation(), AdvanceTimeRequest, ApplyScenarioRequest, create_simulation(), CreateSimulationRequest, get_active_simulation(), _get_or_restore_engine(), get_simulation() (+52 more)

### Community 48 - "runner.py"
Cohesion: 0.19
Nodes (9): Execution agent subpackage -- LangGraph 5-node execution graph., _naive_now(), AsyncSession, datetime, UUID, Agent ExecutionRunner -- async entry point for the execution graph. Usage:…, Typed result returned by ExecutionRunner.run()., Run the execution graph for the given recommendation. Returns a RunResult… (+1 more)

### Community 49 - "decision/models.py"
Cohesion: 0.08
Nodes (33): AsyncSession, Scan all active risks without pending recommendations and generate decisions.…, Evaluate decision for a risk and persist the top recommendation. Returns the…, Decision Engine service package., ActionScorer, CandidateAction, DecisionResult, DiscountInput (+25 more)

### Community 50 - "4. Locked product decisions"
Cohesion: 0.12
Nodes (17): 4.10 Transfer ETA, 4.11 Supplier simulation, 4.12 Markdown simulation, 4.13 Batch-level expiry, 4.1 Stores, 4.2 Products, 4.3 Customers, 4.4 Historical data (+9 more)

### Community 52 - "resolve_risk"
Cohesion: 0.23
Nodes (12): evaluate_risks(), get_risk(), list_risks(), AsyncSession, get, post, UUID, Resolve an existing risk. (+4 more)

### Community 53 - "10. Data model"
Cohesion: 0.13
Nodes (15): 10.10 Markdown, 10.11 Recommendation, 10.12 Approval, 10.13 Audit/event log, 10.14 Simulation state, 10.1 Store, 10.2 Product, 10.3 Batch (+7 more)

### Community 54 - "GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification"
Cohesion: 0.14
Nodes (13): 1. Visual Foundation & Tone, 2.1 Surfaces & Structure, 2.2 Operator Action Tokens (The 4 Core Actions), 2.3 Risk Severity Tokens, 2. Comprehensive Color & Semantic Token System, 3. Button & Interactive Element Hierarchy, 4. Typography Hierarchy, 5. Operations Cockpit Layout (3-Column Architecture) (+5 more)

### Community 57 - "products.py"
Cohesion: 0.31
Nodes (8): get_product(), list_products(), AsyncSession, get, UUID, Products REST API — spec §32.4. Endpoints: GET /api/products — list all catalog…, List all 25 catalog products., Get a single product by ID.

### Community 58 - "db_session"
Cohesion: 0.25
Nodes (8): db_session(), event_loop(), AsyncSession, fixture, Create a single event loop for the entire test session., Create all tables before each test, drop after., Provide a clean database session for each test., setup_database()

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

### Community 71 - "8. Technology stack"
Cohesion: 0.25
Nodes (8): 8. Technology stack, Agent, Backend, Database, Forecasting, Frontend, Local environment, Realtime

### Community 74 - "test_health_endpoint_reports_db_status"
Cohesion: 0.38
Nodes (6): AsyncClient, asyncio, Health endpoint should report database connectivity., Health endpoint should return 200 with status healthy., test_health_endpoint_reports_db_status(), test_health_endpoint_returns_200()

### Community 75 - "38. Immediate implementation order (100% Complete & Verified)"
Cohesion: 0.18
Nodes (11): 10. Testing + demo hardening — [x] COMPLETE, 1. Repository audit + cleanup — [x] COMPLETE, 2. Backend source-of-truth refactor — [x] COMPLETE, 38. Immediate implementation order (100% Complete & Verified), 3. Data/model consistency — [x] COMPLETE, 4. Simulation engine — [x] COMPLETE, 5. Forecasting + risk — [x] COMPLETE, 6. Decision engine — [x] COMPLETE (+3 more)

### Community 76 - "IMPLEMENTATION_PLAN.md"
Cohesion: 0.17
Nodes (11): 0. Rules for implementation, 13. Phase 10 — Documentation and final demo, 14. Agent execution protocol for Antigravity, 17. What not to build, 18. Final engineering principle, 1. Target architecture, 2. Implementation order, Architecture documentation (+3 more)

### Community 78 - "2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)"
Cohesion: 0.18
Nodes (10): 1. Executive Summary, 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK), 3. Test & Runtime Baseline, DELETE / DEPRECATE, Key Audit Findings, MISSING, Phase 0: Repository Audit & Technical Baseline, REFACTOR (+2 more)

### Community 80 - "test_phase8_commerce.py"
Cohesion: 0.16
Nodes (25): CartItemUpdate, Request to modify quantity of a variant in the cart., asyncio, Phase 8: CommercePort and Customer Replenishment Tests (Spec Section 5.1, 28, &…, test_api_adapter_info(), test_api_cart_crud_operations(), test_api_checkout_confirmed_and_tracking(), test_api_checkout_unconfirmed_rejected() (+17 more)

### Community 82 - "21. Inventory invariants"
Cohesion: 0.18
Nodes (11): 21. Inventory invariants, Invariant 1, Invariant 10, Invariant 2, Invariant 3, Invariant 4, Invariant 5, Invariant 6 (+3 more)

### Community 83 - "8. Phase 5 — Decision engine"
Cohesion: 0.18
Nodes (11): 8. Phase 5 — Decision engine, Acceptance criteria, Candidate actions, Example, Explainability, Goal, Hard constraints, Objective factors (+3 more)

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

### Community 91 - "CommerceError"
Cohesion: 0.13
Nodes (11): AddressNotServiceableError, CartExpiredError, CommerceError, ProviderAuthError, Raised when the target delivery address is outside dark store service radius., Raised when the session or cart has timed out., Base exception for all commerce adapter failures., Raised on authentication or token expiration from provider MCP endpoint. (+3 more)

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

### Community 129 - "agent.py"
Cohesion: 0.19
Nodes (13): ExecutionRunner, Async runner that drives the LangGraph execution graph for a single…, execute_recommendation(), get_run_status(), list_runs(), AsyncSession, get, post (+5 more)

### Community 130 - "service.py"
Cohesion: 0.09
Nodes (19): ABC, get_commerce_adapter(), Factory for obtaining configured CommercePort adapter., Resolve and return active CommercePort adapter based on settings., CommercePort, Abstract port for commerce provider operations., Fetch saved delivery addresses for customer., Fetch active cart with items and bill breakdown. (+11 more)

### Community 132 - "CommerceProductItem"
Cohesion: 0.25
Nodes (4): CommerceProductItem, Catalogue product item containing one or more pack-size variations., Fetch frequently ordered staple items available for this address., Search products available at delivery address.

### Community 133 - "CustomerReplenishmentView.tsx"
Cohesion: 0.18
Nodes (12): CustomerReplenishmentViewProps, DEFAULT_FALLBACK_ADAPTER, DEFAULT_FALLBACK_CART, DEFAULT_GO_TO_ITEMS, PANTRY_ITEMS, WhatsAppIcon(), BackendCommerceCart, BackendCommerceOrderResult (+4 more)

### Community 137 - "page.tsx"
Cohesion: 0.18
Nodes (11): GrocerConsumerApp(), CustomerReplenishmentView(), AppGlobalHeader(), AppGlobalHeaderProps, GrocerLogo(), GrocerLogoProps, BackendCommerceAdapterInfo, grocerApi (+3 more)

## Knowledge Gaps
- **450 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+445 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Inventory` connect `core.py` to `risk/engine.py`, `service.py`, `simulations.py`, `stores.py`, `test_phase8_commerce.py`, `SimulationEngine`, `CustomerService`, `test_customer_api.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `CustomerService` connect `CustomerService` to `SwiggyMCPAdapter`, `service.py`, `CommerceProductItem`, `MockCommerceAdapter`, `schemas.py`, `test_phase8_commerce.py`, `core.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `DecisionOrchestrator` connect `core.py` to `decision/models.py`, `recommendations.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `CustomerService` (e.g. with `UnconfirmedCheckoutError` and `CartItemUpdate`) actually correct?**
  _`CustomerService` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `SimulationEngine` (e.g. with `Batch` and `Customer`) actually correct?**
  _`SimulationEngine` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `SwiggyMCPAdapter` (e.g. with `AddressNotServiceableError` and `CartExpiredError`) actually correct?**
  _`SwiggyMCPAdapter` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Product` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Product` has 19 INFERRED edges - model-reasoned connections that need verification._