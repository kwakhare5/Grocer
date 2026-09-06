# Graph Report - Grocer  (2026-09-06)

## Corpus Check
- 105 files · ~116,340 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1456 nodes · 3103 edges · 100 communities (88 shown, 12 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 326 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ede06908`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SwiggyMCPAdapter
- main.py
- tools.py
- AgentState
- AGENTS.md — GROCER Project Rules
- MockCommerceAdapter
- compilerOptions
- AsyncSession
- ARCHITECTURE.md — GROCER v2
- 16.1 Core metrics
- Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent
- dependencies
- 20. Recommended implementation sequence
- SwiggyClient
- EventBus
- Core metrics
- stores.py
- Initial scenario set
- get_recommendation
- 5. Intent Contract
- core.py
- CONTEXT.md — GROCER Domain Context
- CustomerService
- asyncio
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
- 7. Phase 5 — Recovery engine
- 5. Phase 3 — Policy and memory
- 6. Phase 4 — Intent Verifier
- scenarioEngine.ts
- recommendations.py
- metricsEngine.ts
- Grocer — Historical Context & ADRs
- 10. Recovery engine
- types.ts
- schemas.py
- graphify
- workflows/graphify.md
- simulations.py
- runner.py
- decision/models.py
- 11. Conversation behavior
- 3.1 IN SCOPE
- Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me)
- 12. Agent architecture
- GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification
- 13. State model
- 1. Product identity
- products.py
- conftest.py
- 21. Flagship demo
- IP as Logo
- IP as Logo
- env.py
- 7. Memory and preferences
- 8. Commerce architecture
- eslint.config.mjs
- 9. Intent verification
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- Tracer Bullets: Codebase Cleanup, Architecture Refactoring & Bloat Purge
- 11. Phase 9 — Live Swiggy hardening
- 3. Phase 1 — Intent Contract
- 9. Phase 7 — Deterministic failure simulation
- test_health_endpoint_reports_db_status
- 23. Anti-drift rules for coding agents
- IMPLEMENTATION_PLAN.md
- 4. Product job-to-be-done
- 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)
- test_phase8_commerce.py
- _enum_val
- ProductResponse
- health_check
- GROCER_V2_MASTER_SPEC.md
- ProviderAuthError
- agents/__init__.py
- services/__init__.py
- 8. Phase 6 — Agent orchestration
- 2. Phase 0 — Consumer boundary cleanup
- AGENTS.md — GROCER Coding Agent Contract
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
- `node_execute()` --indirect_call--> `apply_discount()`  [INFERRED]
  backend/agents/execution/nodes.py → backend/agents/execution/tools.py
- `node_execute()` --indirect_call--> `create_reorder()`  [INFERRED]
  backend/agents/execution/nodes.py → backend/agents/execution/tools.py

## Import Cycles
- None detected.

## Communities (100 total, 12 thin omitted)

### Community 0 - "SwiggyMCPAdapter"
Cohesion: 0.24
Nodes (5): Any, Classify errors from Swiggy envelope per official error taxonomy., Production adapter for Swiggy Instamart MCP server., Execute JSON-RPC tool call against Swiggy Instamart MCP endpoint., SwiggyMCPAdapter

### Community 1 - "main.py"
Cohesion: 0.27
Nodes (6): Settings, get_db(), AsyncSession, lifespan(), BaseSettings, FastAPI

### Community 2 - "tools.py"
Cohesion: 0.15
Nodes (29): LangGraph node functions for the GROCER v2 execution agent (spec section 19).…, apply_discount(), _assert_approved(), create_reorder(), create_transfer(), _enum_val(), get_inventory(), get_recommendation() (+21 more)

### Community 3 - "AgentState"
Cohesion: 0.12
Nodes (27): build_execution_graph(), LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section…, Fail fast if validate produced an error., Divert to recover if world state has changed., Divert to recover on execution error., Divert to recover if verification failed., Build and return the compiled LangGraph execution graph., _route_after_execute() (+19 more)

### Community 4 - "AGENTS.md — GROCER Project Rules"
Cohesion: 0.11
Nodes (18): 10. SWIGGY MCP RULES, 11. UI RULES, 12. SAFETY INVARIANTS, 13. QUALITY GATE, 14. DECISION RULE FOR NEW IDEAS, 1. PROJECT IDENTITY — LOCKED, 2. TARGET FLOW, 3. NEVER BUILD THESE INSIDE GROCER (+10 more)

### Community 5 - "MockCommerceAdapter"
Cohesion: 0.11
Nodes (36): AddressNotServiceableError, CommerceError, ItemOutOfStockError, MinOrderNotMetError, Canonical exception taxonomy for CommercePort and Swiggy Instamart integration., Raised when checkout is attempted without explicit human/user confirmation. In…, Raised when the target delivery address is outside dark store service radius., Raised when an item or variant requested in update_cart is not in stock. (+28 more)

### Community 6 - "compilerOptions"
Cohesion: 0.07
Nodes (28): dom, dom.iterable, esnext, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules (+20 more)

### Community 7 - "AsyncSession"
Cohesion: 0.16
Nodes (16): checkout_customer(), list_customers(), AsyncSession, post, Process user message in the WhatsApp simulation., Execute 1-tap WhatsApp customer replenishment. Deducts store inventory and…, Schedule a simulated restock reminder., Record customer skip decision. (+8 more)

### Community 8 - "ARCHITECTURE.md — GROCER v2"
Cohesion: 0.07
Nodes (28): 10. Technology posture, 11. Architectural non-goals, 1. System identity, 2. Core architecture, 3.1 Intent is the source of truth for the user's goal, 3.2 Backend is authoritative, 3.3 Deterministic enforcement beats LLM confidence, 3.4 Provider isolation (+20 more)

### Community 9 - "16.1 Core metrics"
Cohesion: 0.17
Nodes (12): 16.1 Core metrics, 16.2 Regression testing, 16. Evaluation framework, Budget deviation, Hard constraint satisfaction, Human intervention rate, Intent preservation rate, Provider/tool efficiency (+4 more)

### Community 10 - "Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent"
Cohesion: 0.10
Nodes (20): Architecture, Autonomy model, Backend, Core loop, Deterministic evaluation, Development, Documentation, Engineering roadmap (+12 more)

### Community 11 - "dependencies"
Cohesion: 0.04
Nodes (45): clsx, eslint, eslint-config-next, framer-motion, lucide-react, next, dependencies, clsx (+37 more)

### Community 12 - "20. Recommended implementation sequence"
Cohesion: 0.17
Nodes (12): 20. Recommended implementation sequence, Phase 0 — Boundary cleanup, Phase 10 — Demo hardening, Phase 1 — Intent Contract, Phase 2 — Intent extraction, Phase 3 — Policy and preference layer, Phase 4 — Cart verifier, Phase 5 — Recovery engine (+4 more)

### Community 13 - "SwiggyClient"
Cohesion: 0.29
Nodes (5): base64UrlEncode(), generateCodeChallenge(), generateRandomString(), SwiggyClient, SwiggyTokenResponse

### Community 14 - "EventBus"
Cohesion: 0.09
Nodes (26): EventBus, Any, AsyncSession, UUID, In-process event bus for GROCER v2. LOCKED (spec §30): async in-process pub/sub…, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler. (+18 more)

### Community 15 - "Core metrics"
Cohesion: 0.18
Nodes (11): 10. Phase 8 — Evaluation, Budget deviation, Core metrics, Human intervention rate, Intent preservation rate, MCP/tool calls, Recovery attempts, Recovery success rate (+3 more)

### Community 16 - "stores.py"
Cohesion: 0.14
Nodes (28): BaseSchema, BatchResponse, EventResponse, ForecastResponse, InventoryItemResponse, RiskResponse, StoreDetailResponse, StoreInventoryResponse (+20 more)

### Community 17 - "Initial scenario set"
Cohesion: 0.25
Nodes (8): 15. Deterministic failure simulation, Initial scenario set, Scenario A — happy path, Scenario B — preferred item unavailable, Scenario C — budget drift, Scenario D — ambiguous substitution, Scenario E — stale cart, Scenario F — transient provider failure

### Community 18 - "get_recommendation"
Cohesion: 0.43
Nodes (7): get_recommendation(), list_recommendations(), get, List recommendations with optional filters., Get a single recommendation by ID., _to_response(), RecommendationResponse

### Community 19 - "5. Intent Contract"
Cohesion: 0.29
Nodes (7): 5.1 Required conceptual fields, 5.2 Example, 5.3 Precedence rules, 5.4 Hard vs soft, 5. Intent Contract, Hard constraint, Soft preference

### Community 20 - "core.py"
Cohesion: 0.06
Nodes (119): Action, Batch, Customer, Event, Forecast, Inventory, Order, OrderItem (+111 more)

### Community 21 - "CONTEXT.md — GROCER Domain Context"
Cohesion: 0.11
Nodes (18): 10. UI rule, 11. External provider rule, 12. Quality gate, 1. Project identity, 2. Canonical terms, 3. Product objective, 4. Intent precedence, 5. Autonomy rules (+10 more)

### Community 22 - "CustomerService"
Cohesion: 0.09
Nodes (23): CustomerService, Any, AsyncSession, UUID, Fetch payment options (UPI, COD) via CommercePort., Consequential customer checkout. Strictly requires explicit confirmation. If db…, Get live order delivery status and ETA via CommercePort., Internal helper to record commerce order into shared database and deduct stock. (+15 more)

### Community 23 - "asyncio"
Cohesion: 0.12
Nodes (17): asyncio, POST /api/customers/{id}/reorder should deduct inventory and create order., POST /api/customers/{id}/remind should schedule reminder., POST /api/customers/{id}/skip should record skip., GET /api/customers should list all seeded customers., GET /api/customers/{id} should return customer profile and pantry staples., GET /api/customers/{id} should return 404 for unknown customer., GET /api/customers/{id}/messages should return proactive alert. (+9 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.20
Nodes (10): Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx), [MODIFY] [`GrocerFooter.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerFooter.tsx), [MODIFY] [`GrocerHero.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerHero.tsx), [MODIFY] [`GrocerIntegrations.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerIntegrations.tsx), [MODIFY] [`GrocerValueProp.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerValueProp.tsx) & [`GrocerVelocityCalculator.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerVelocityCalculator.tsx) (+2 more)

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
Cohesion: 0.11
Nodes (23): clear_customer_cart(), get_adapter_info(), get_customer(), get_customer_addresses(), get_customer_cart(), get_customer_go_to_items(), get_customer_messages(), get_customer_payment_options() (+15 more)

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "apiClient.ts"
Cohesion: 0.08
Nodes (21): BackendAgentRun, BackendAgentRunEvent, BackendCommerceCartItem, BackendCommercePaymentOption, BackendCommerceProductVariant, BackendCustomerDetail, BackendCustomerListItem, BackendCustomerMessageResponse (+13 more)

### Community 32 - "risk/engine.py"
Cohesion: 0.07
Nodes (48): evaluate_risks(), get_risk(), list_risks(), AsyncSession, get, post, UUID, Risk REST API — spec §32. Endpoints: GET /api/risks — list risks with optional… (+40 more)

### Community 33 - "Log Entries"
Cohesion: 0.14
Nodes (13): [Grocer — Complete WhatsApp Demo Redesign & Operational Clutter Removal] 2026-09-04, [Grocer — Customer Replenishment, Swiggy MCP Integration & Full 10-Phase Completion] 2026-09-05, [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — Official App Icon Design & Full UI Architecture Overhaul] 2026-09-02, [Grocer — Phase 0 Audit, Phase 1 Backend Foundation & Phase 2 Simulator Engine] 2026-08-27, [Grocer — Phase 0 Repository Audit & v2 Architecture Alignment] 2026-08-26, [Grocer — Phase 9 Customer / WhatsApp Integration & Phase 10 Hardening & Polish] 2026-08-28, [Grocer — Saved Exact Figma Notification Layout & WhatsApp Icon] 2026-08-15 (+5 more)

### Community 34 - "7. Phase 5 — Recovery engine"
Cohesion: 0.29
Nodes (7): 7. Phase 5 — Recovery engine, Core loop, Expand after first scenario is stable, First recovery wedge, Goal, Preferred item becomes unavailable, Terminal states

### Community 35 - "5. Phase 3 — Policy and memory"
Cohesion: 0.33
Nodes (6): 5. Phase 3 — Policy and memory, Acceptance, Do not store as permanent preference, Goal, Memory examples, Precedence

### Community 36 - "6. Phase 4 — Intent Verifier"
Cohesion: 0.33
Nodes (6): 6. Phase 4 — Intent Verifier, First tests, Goal, Inputs, Output, Required properties

### Community 38 - "scenarioEngine.ts"
Cohesion: 0.16
Nodes (15): INITIAL_RECOMMENDATIONS, BaselineStepResult, buildFailureScenario(), buildHeroScenario(), buildPerishablesScenario(), getScenario(), mulberry32(), runScenarioStep() (+7 more)

### Community 39 - "recommendations.py"
Cohesion: 0.21
Nodes (16): approve_recommendation(), batch_evaluate_recommendations(), evaluate_recommendation(), AsyncSession, post, UUID, Recommendations REST API -- spec sections 17, 18 (Human-in-the-loop).…, Approve a recommendation for execution (spec section 18 -- LOCKED human… (+8 more)

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

### Community 42 - "10. Recovery engine"
Cohesion: 0.40
Nodes (5): 10.1 Recovery loop, 10.2 Initial recovery classes, 10.3 Candidate ranking, 10.4 Recovery limits, 10. Recovery engine

### Community 43 - "types.ts"
Cohesion: 0.18
Nodes (10): ActionStatus, ActionType, CustomerOrderItem, PhoneMockupProps, RecommendationAlternative, RiskSeverity, ScenarioState, SimulationState (+2 more)

### Community 44 - "schemas.py"
Cohesion: 0.14
Nodes (32): FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8). Provides: - GET…, AgentRunResponse, CartItemUpdatePayload, CommerceAdapterInfoResponse, CommerceCartItemResponse, CommerceCartResponse, CommerceCartUpdateRequest, CommerceCheckoutRequest (+24 more)

### Community 47 - "simulations.py"
Cohesion: 0.09
Nodes (41): advance_simulation(), AdvanceTimeRequest, ApplyScenarioRequest, create_simulation(), CreateSimulationRequest, get_active_simulation(), _get_or_restore_engine(), get_simulation() (+33 more)

### Community 48 - "runner.py"
Cohesion: 0.15
Nodes (12): Execution agent subpackage -- LangGraph 5-node execution graph., ExecutionRunner, _naive_now(), AsyncSession, datetime, UUID, Agent ExecutionRunner -- async entry point for the execution graph. Usage:…, Typed result returned by ExecutionRunner.run(). (+4 more)

### Community 49 - "decision/models.py"
Cohesion: 0.08
Nodes (31): Evaluate decision for a risk and persist the top recommendation. Returns the…, Decision Engine service package., ActionScorer, CandidateAction, DecisionResult, DiscountInput, ExplainabilityFacts, HoldInput (+23 more)

### Community 50 - "11. Conversation behavior"
Cohesion: 0.40
Nodes (5): 11.1 Normal case, 11.2 Automatic recovery, 11.3 Ambiguity, 11.4 Checkout, 11. Conversation behavior

### Community 51 - "3.1 IN SCOPE"
Cohesion: 0.40
Nodes (5): 3.1 IN SCOPE, 3.2 OUT OF SCOPE, 3. Product boundary, Consumer experience, Engineering

### Community 52 - "Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me)"
Cohesion: 0.40
Nodes (5): Automated Tests, Finalized Architecture & Design Decisions, Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me), Manual Verification, Verification Plan

### Community 53 - "12. Agent architecture"
Cohesion: 0.50
Nodes (4): 12.1 Responsibilities of the LLM, 12.2 Responsibilities of deterministic code, 12.3 Core rule, 12. Agent architecture

### Community 54 - "GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification"
Cohesion: 0.14
Nodes (13): 1. Visual Foundation & Tone, 2.1 Surfaces & Structure, 2.2 Operator Action Tokens (The 4 Core Actions), 2.3 Risk Severity Tokens, 2. Comprehensive Color & Semantic Token System, 3. Button & Interactive Element Hierarchy, 4. Typography Hierarchy, 5. Operations Cockpit Layout (3-Column Architecture) (+5 more)

### Community 55 - "13. State model"
Cohesion: 0.50
Nodes (4): 13.1 Session state, 13.2 Commerce snapshot, 13.3 Event/outcome record, 13. State model

### Community 56 - "1. Product identity"
Cohesion: 0.50
Nodes (4): 1.1 One-sentence definition, 1.2 What changed from the previous scope, 1.3 Core thesis, 1. Product identity

### Community 57 - "products.py"
Cohesion: 0.31
Nodes (8): get_product(), list_products(), AsyncSession, get, UUID, Products REST API — spec §32.4. Endpoints: GET /api/products — list all catalog…, List all 25 catalog products., Get a single product by ID.

### Community 58 - "conftest.py"
Cohesion: 0.18
Nodes (13): client(), db_session(), event_loop(), AsyncClient, AsyncSession, fixture, Create a single event loop for the entire test session., Create all tables before each test, drop after. (+5 more)

### Community 59 - "21. Flagship demo"
Cohesion: 0.50
Nodes (4): 21. Flagship demo, System, User, What the demo must prove

### Community 60 - "IP as Logo"
Cohesion: 0.20
Nodes (9): Color and canvas, Complexity budget, Delivery behavior, IP as Logo, Prompt skeleton, Route constraints by generator capability, Shape language and composition, Simplicity and visual treatment (+1 more)

### Community 61 - "IP as Logo"
Cohesion: 0.22
Nodes (8): Agent compatibility, Install, IP as Logo, License, Model behavior, Repository structure, Use, What it guides

### Community 62 - "env.py"
Cohesion: 0.60
Nodes (3): do_run_migrations(), run_async_migrations(), run_migrations_online()

### Community 63 - "7. Memory and preferences"
Cohesion: 0.50
Nodes (4): 7.1 What may be stored, 7.2 What should not be treated as permanent policy, 7.3 Precedence, 7. Memory and preferences

### Community 64 - "8. Commerce architecture"
Cohesion: 0.50
Nodes (4): 8.1 Existing foundation to preserve, 8.2 Swiggy MCP rules, 8.3 Checkout guard, 8. Commerce architecture

### Community 66 - "9. Intent verification"
Cohesion: 0.50
Nodes (4): 9.1 Verification inputs, 9.2 Verification output, 9.3 Verification principles, 9. Intent verification

### Community 71 - "11. Phase 9 — Live Swiggy hardening"
Cohesion: 0.50
Nodes (4): 11. Phase 9 — Live Swiggy hardening, Acceptance, Goal, Rules

### Community 72 - "3. Phase 1 — Intent Contract"
Cohesion: 0.50
Nodes (4): 3. Phase 1 — Intent Contract, Acceptance, Goal, Required fields

### Community 73 - "9. Phase 7 — Deterministic failure simulation"
Cohesion: 0.50
Nodes (4): 9. Phase 7 — Deterministic failure simulation, Acceptance, Goal, Initial scenarios

### Community 74 - "test_health_endpoint_reports_db_status"
Cohesion: 0.38
Nodes (6): AsyncClient, asyncio, Health endpoint should report database connectivity., Health endpoint should return 200 with status healthy., test_health_endpoint_reports_db_status(), test_health_endpoint_returns_200()

### Community 75 - "23. Anti-drift rules for coding agents"
Cohesion: 0.67
Nodes (3): 23. Anti-drift rules for coding agents, ALWAYS, NEVER

### Community 76 - "IMPLEMENTATION_PLAN.md"
Cohesion: 0.17
Nodes (11): 0. Implementation rules, 12. Phase 10 — Demo hardening, 13. Definition of done for implementation, 1. Execution order, 4. Phase 2 — Intent extraction, Examples, Flagship narrative, Goal (+3 more)

### Community 77 - "4. Product job-to-be-done"
Cohesion: 0.67
Nodes (3): 4. Product job-to-be-done, Primary job, Secondary jobs

### Community 78 - "2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)"
Cohesion: 0.18
Nodes (10): 1. Executive Summary, 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK), 3. Test & Runtime Baseline, DELETE / DEPRECATE, Key Audit Findings, MISSING, Phase 0: Repository Audit & Technical Baseline, REFACTOR (+2 more)

### Community 80 - "test_phase8_commerce.py"
Cohesion: 0.17
Nodes (26): CartItemUpdate, Request to modify quantity of a variant in the cart., create_app(), asyncio, Phase 8: CommercePort and Customer Replenishment Tests (Spec Section 5.1, 28, &…, test_api_adapter_info(), test_api_cart_crud_operations(), test_api_checkout_confirmed_and_tracking() (+18 more)

### Community 87 - "health_check"
Cohesion: 0.50
Nodes (4): health_check(), AsyncSession, get, Health check endpoint. Verifies API and database connectivity.

### Community 88 - "GROCER_V2_MASTER_SPEC.md"
Cohesion: 0.14
Nodes (13): 0. Purpose of this document, 14. Error and retry semantics, 17. Security and safety invariants, 18. Existing GROCER UX foundation, 19. Repository boundary and cleanup, 22. Engineering standards, 24. Definition of done, 2. Product goals (+5 more)

### Community 91 - "ProviderAuthError"
Cohesion: 0.17
Nodes (4): CartExpiredError, ProviderAuthError, Raised when the session or cart has timed out., Raised on authentication or token expiration from provider MCP endpoint.

### Community 103 - "8. Phase 6 — Agent orchestration"
Cohesion: 0.50
Nodes (4): 8. Phase 6 — Agent orchestration, Desired flow, Goal, Rule

### Community 109 - "2. Phase 0 — Consumer boundary cleanup"
Cohesion: 0.25
Nodes (8): 2. Phase 0 — Consumer boundary cleanup, Acceptance, Goal, Inspect first, Preserve, Remove fake consumer → dark-store mutation, Remove/isolate old operations residue, Required work

### Community 117 - "AGENTS.md — GROCER Coding Agent Contract"
Cohesion: 0.12
Nodes (15): 10. Frontend rules, 11. Engineering behavior, 12. Quality commands, 13. What to do when requirements appear ambiguous, 1. Read this first, 2. Non-negotiable product boundary, 3. Extend, do not replace, 4. LLM responsibility (+7 more)

### Community 129 - "agent.py"
Cohesion: 0.22
Nodes (12): execute_recommendation(), get_run_status(), list_runs(), AsyncSession, get, post, UUID, Agent Execution REST API -- spec sections 19-21. Endpoints: POST… (+4 more)

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
- **372 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+367 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CustomerService` connect `CustomerService` to `service.py`, `CommerceProductItem`, `MockCommerceAdapter`, `schemas.py`, `test_phase8_commerce.py`, `core.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `Inventory` connect `core.py` to `risk/engine.py`, `tools.py`, `service.py`, `stores.py`, `test_phase8_commerce.py`, `CustomerService`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `SimulationEngine` connect `core.py` to `test_phase8_commerce.py`, `simulations.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `CustomerService` (e.g. with `UnconfirmedCheckoutError` and `CartItemUpdate`) actually correct?**
  _`CustomerService` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `SimulationEngine` (e.g. with `Batch` and `Customer`) actually correct?**
  _`SimulationEngine` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `SwiggyMCPAdapter` (e.g. with `AddressNotServiceableError` and `CartExpiredError`) actually correct?**
  _`SwiggyMCPAdapter` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Product` (e.g. with `ActionStatus` and `ActionType`) actually correct?**
  _`Product` has 19 INFERRED edges - model-reasoned connections that need verification._