# Graph Report - Grocer  (2026-09-06)

## Corpus Check
- 128 files · ~143,260 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1973 nodes · 4672 edges · 114 communities (101 shown, 13 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 445 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `06726f20`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SwiggyMCPAdapter
- main.py
- tools.py
- agent.py
- AGENTS.md — GROCER Project Rules
- MockCommerceAdapter
- compilerOptions
- ConstraintType
- ARCHITECTURE.md — GROCER v2
- 16.1 Core metrics
- Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent
- dependencies
- 20. Recommended implementation sequence
- SwiggyClient
- EventBus
- Core metrics
- Initial scenario set
- IntentContract
- 5. Intent Contract
- core.py
- CONTEXT.md — GROCER Domain Context
- CustomerService
- intent/__init__.py
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- forecasting/engine.py
- .prettierrc.json
- IntentVerifier
- layout.tsx
- UUID
- Changes Made
- apiClient.ts
- risk/models.py
- Log Entries
- 7. Phase 5 — Recovery engine
- 5. Phase 3 — Policy and memory
- 6. Phase 4 — Intent Verifier
- scenarioEngine.ts
- metricsEngine.ts
- Grocer — Historical Context & ADRs
- 10. Recovery engine
- RecoveryEngine
- schemas.py
- graphify
- workflows/graphify.md
- simulations.py
- _make_contract
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
- intent_chat.py
- 7. Memory and preferences
- 8. Commerce architecture
- eslint.config.mjs
- 9. Intent verification
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- task.md
- 11. Phase 9 — Live Swiggy hardening
- 3. Phase 1 — Intent Contract
- 9. Phase 7 — Deterministic failure simulation
- test_health_endpoint_reports_db_status
- IntentItem
- IMPLEMENTATION_PLAN.md
- 4. Product job-to-be-done
- 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)
- test_phase8_commerce.py
- PreferenceStore
- SimulationEngine
- GrocerOrchestrator
- IntentParser
- RuleBasedExtractor
- asyncio
- GROCER_V2_MASTER_SPEC.md
- Batch
- GROCER v2 — Flagship Golden Flow: Intent-Preserving Grocery Replenishment
- swiggy_adapter.py
- OrchestratorSessionStore
- agents/__init__.py
- services/__init__.py
- IntentSessionStore
- PendingClarification
- ._make_awaiting_confirmation
- .to_summary_dict
- 8. Phase 6 — Agent orchestration
- ._parse_intent
- orchestrator
- 19. Repository boundary and cleanup
- test_handle_choice_preserves_unrelated_items_and_quantity
- 2. Phase 0 — Consumer boundary cleanup
- test_handle_choice_invalid_unlisted_rejected
- test_handle_choice_violating_hard_constraint_handled_safely
- AGENTS.md — GROCER Coding Agent Contract
- CommercePort

## God Nodes (most connected - your core abstractions)
1. `IntentContract` - 77 edges
2. `CommerceCart` - 62 edges
3. `RecoveryEngine` - 60 edges
4. `MockCommerceAdapter` - 56 edges
5. `CartItemUpdate` - 54 edges
6. `GrocerOrchestrator` - 54 edges
7. `IntentVerifier` - 54 edges
8. `VerificationResult` - 50 edges
9. `CommercePort` - 48 edges
10. `CommerceProductItem` - 47 edges

## Surprising Connections (you probably didn't know these)
- `RunResult` --uses--> `AgentState`  [INFERRED]
  backend/agents/execution/runner.py → backend/agents/execution/state.py
- `ExecutionRunner` --uses--> `AgentState`  [INFERRED]
  backend/agents/execution/runner.py → backend/agents/execution/state.py
- `EventBus` --uses--> `Event`  [INFERRED]
  backend/events/bus.py → backend/models/core.py
- `MockCommerceAdapter` --uses--> `CommerceError`  [INFERRED]
  backend/integrations/commerce/mock_adapter.py → backend/integrations/commerce/exceptions.py
- `SwiggyMCPAdapter` --uses--> `CommerceError`  [INFERRED]
  backend/integrations/commerce/swiggy_adapter.py → backend/integrations/commerce/exceptions.py

## Import Cycles
- None detected.

## Communities (114 total, 13 thin omitted)

### Community 0 - "SwiggyMCPAdapter"
Cohesion: 0.24
Nodes (5): Any, Classify errors from Swiggy envelope per official error taxonomy., Production adapter for Swiggy Instamart MCP server., Execute JSON-RPC tool call against Swiggy Instamart MCP endpoint., SwiggyMCPAdapter

### Community 1 - "main.py"
Cohesion: 0.13
Nodes (13): do_run_migrations(), run_async_migrations(), run_migrations_online(), health_check(), AsyncSession, get, Health check endpoint. Verifies API and database connectivity., Settings (+5 more)

### Community 2 - "tools.py"
Cohesion: 0.07
Nodes (59): build_execution_graph(), LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section…, Fail fast if validate produced an error., Divert to recover if world state has changed., Divert to recover on execution error., Divert to recover if verification failed., Build and return the compiled LangGraph execution graph., _route_after_execute() (+51 more)

### Community 3 - "agent.py"
Cohesion: 0.10
Nodes (24): Execution agent subpackage -- LangGraph 5-node execution graph., ExecutionRunner, _naive_now(), AsyncSession, datetime, UUID, Agent ExecutionRunner -- async entry point for the execution graph. Usage:…, Typed result returned by ExecutionRunner.run(). (+16 more)

### Community 4 - "AGENTS.md — GROCER Project Rules"
Cohesion: 0.10
Nodes (19): 10. SWIGGY MCP RULES, 11. UI RULES, 12. SAFETY INVARIANTS, 13. QUALITY GATE, 14. DECISION RULE FOR NEW IDEAS, 15. SESSION RESUME, 1. PROJECT IDENTITY — LOCKED, 2. TARGET FLOW (+11 more)

### Community 5 - "MockCommerceAdapter"
Cohesion: 0.09
Nodes (14): MinOrderNotMetError, Raised when cart grand total is below minimum order threshold., MockCommerceAdapter, Deterministic in-memory commerce simulation adapter with failure injection., Initialize instance-isolated catalog copies., Simulate an item variant going out of stock in real-time., Simulate a supplier or store-level price surge., Simulate session expiry or store becoming unserviceable. (+6 more)

### Community 6 - "compilerOptions"
Cohesion: 0.07
Nodes (28): dom, dom.iterable, esnext, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules (+20 more)

### Community 7 - "ConstraintType"
Cohesion: 0.08
Nodes (72): AmbiguitySeverity, BrandTolerance, ConstraintType, PrecedenceLevel, PreferenceType, Enum, str, Domain enums for GROCER Intent Contract (Spec §5). Encodes explicit vocabulary… (+64 more)

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
Nodes (24): EventBus, Any, AsyncSession, UUID, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler., Publish an event. - Calls all registered handlers for *event_type*. - If… (+16 more)

### Community 15 - "Core metrics"
Cohesion: 0.18
Nodes (11): 10. Phase 8 — Evaluation, Budget deviation, Core metrics, Human intervention rate, Intent preservation rate, MCP/tool calls, Recovery attempts, Recovery success rate (+3 more)

### Community 17 - "Initial scenario set"
Cohesion: 0.25
Nodes (8): 15. Deterministic failure simulation, Initial scenario set, Scenario A — happy path, Scenario B — preferred item unavailable, Scenario C — budget drift, Scenario D — ambiguous substitution, Scenario E — stale cart, Scenario F — transient provider failure

### Community 18 - "IntentContract"
Cohesion: 0.06
Nodes (33): CommerceCart, Active customer cart with bill breakdown., IntentContract, The canonical structured representation of user shopping intent (Spec §5). The…, Validate critical domain invariants across the contract., Check whether a specific dietary constraint applies., Check if target attribute is governed by a hard constraint., Get brand preference for a product or category. (+25 more)

### Community 19 - "5. Intent Contract"
Cohesion: 0.29
Nodes (7): 5.1 Required conceptual fields, 5.2 Example, 5.3 Precedence rules, 5.4 Hard vs soft, 5. Intent Contract, Hard constraint, Soft preference

### Community 20 - "core.py"
Cohesion: 0.11
Nodes (35): In-process event bus for GROCER v2. LOCKED (spec §30): async in-process pub/sub…, Action, Forecast, Inventory, Recommendation, Risk, ActionStatus, ActionType (+27 more)

### Community 21 - "CONTEXT.md — GROCER Domain Context"
Cohesion: 0.11
Nodes (18): 10. UI rule, 11. External provider rule, 12. Quality gate, 1. Project identity, 2. Canonical terms, 3. Product objective, 4. Intent precedence, 5. Autonomy rules (+10 more)

### Community 22 - "CustomerService"
Cohesion: 0.09
Nodes (23): CustomerService, Any, AsyncSession, UUID, Fetch payment options (UPI, COD) via CommercePort., Consequential customer checkout. Strictly requires explicit confirmation. If db…, Get live order delivery status and ETA via CommercePort., Internal helper to record commerce order into shared database and deduct stock. (+15 more)

### Community 23 - "intent/__init__.py"
Cohesion: 0.07
Nodes (64): ProductVariant, SKU-level variant with provider-specific spinId., GROCER Intent Contract Subsystem (Spec §5). Provides canonical domain…, OrchestratorTurnResult, BaseModel, GrocerOrchestrator — end-to-end conversational commerce loop (Spec §12, §20…, Output of a single conversational turn through GrocerOrchestrator., ActionProposal (+56 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.20
Nodes (10): Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx), [MODIFY] [`GrocerFooter.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerFooter.tsx), [MODIFY] [`GrocerHero.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerHero.tsx), [MODIFY] [`GrocerIntegrations.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerIntegrations.tsx), [MODIFY] [`GrocerValueProp.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerValueProp.tsx) & [`GrocerVelocityCalculator.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerVelocityCalculator.tsx) (+2 more)

### Community 25 - "forecasting/engine.py"
Cohesion: 0.13
Nodes (30): ForecastingEngine, AsyncSession, UUID, GROCER v2 Forecasting Engine. Orchestrates forecast generation over simulator…, Query all delivered orders and aggregate demand by (store, product, day) with…, Fit both models, optionally compare on holdout, return (prediction, model_name,…, Perform empirical rolling-origin backtesting across historical orders. Splits…, Generates Forecast rows from historical Order data in the simulation DB. Usage:… (+22 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "IntentVerifier"
Cohesion: 0.13
Nodes (41): CartItem, Item present in active commerce cart., IntentVerifier, Deterministic engine that compares live commerce state to IntentContract. All…, _bread_item(), _make_cart(), _make_contract(), _milk_item() (+33 more)

### Community 28 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 29 - "UUID"
Cohesion: 0.08
Nodes (39): checkout_customer(), clear_customer_cart(), get_adapter_info(), get_customer(), get_customer_addresses(), get_customer_cart(), get_customer_go_to_items(), get_customer_messages() (+31 more)

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "apiClient.ts"
Cohesion: 0.06
Nodes (57): CustomerReplenishmentView(), CustomerReplenishmentViewProps, DEFAULT_FALLBACK_ADAPTER, DEFAULT_FALLBACK_CART, DEFAULT_GO_TO_ITEMS, PANTRY_ITEMS, ChatMessage, IntentCommerceWorkbench() (+49 more)

### Community 32 - "risk/models.py"
Cohesion: 0.09
Nodes (28): _naive_now(), datetime, Return naive current UTC datetime for database compatibility., Scan all inventory and batches, evaluate risks, persist rows and emit events.…, BatchInfo, discount_tier_for_hours(), DiscountTier, MultiBatchSpoilageInput (+20 more)

### Community 33 - "Log Entries"
Cohesion: 0.13
Nodes (14): [GROCER — Cleanroom Intent Refactor & Flagship Golden Flow Completion] 2026-09-06, [Grocer — Complete WhatsApp Demo Redesign & Operational Clutter Removal] 2026-09-04, [Grocer — Customer Replenishment, Swiggy MCP Integration & Full 10-Phase Completion] 2026-09-05, [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — Official App Icon Design & Full UI Architecture Overhaul] 2026-09-02, [Grocer — Phase 0 Audit, Phase 1 Backend Foundation & Phase 2 Simulator Engine] 2026-08-27, [Grocer — Phase 0 Repository Audit & v2 Architecture Alignment] 2026-08-26, [Grocer — Phase 9 Customer / WhatsApp Integration & Phase 10 Hardening & Polish] 2026-08-28 (+6 more)

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
Cohesion: 0.12
Nodes (17): BaselineStepResult, buildFailureScenario(), buildHeroScenario(), buildPerishablesScenario(), DarkStore, getScenario(), INITIAL_RECOMMENDATIONS, INITIAL_STORES (+9 more)

### Community 40 - "metricsEngine.ts"
Cohesion: 0.20
Nodes (5): DarkStore, MetricDelta, RecommendationItem, SimulationEvent, SimulationMetrics

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

### Community 42 - "10. Recovery engine"
Cohesion: 0.40
Nodes (5): 10.1 Recovery loop, 10.2 Initial recovery classes, 10.3 Candidate ranking, 10.4 Recovery limits, 10. Recovery engine

### Community 43 - "RecoveryEngine"
Cohesion: 0.12
Nodes (40): Deterministic recovery and candidate ranking engine (Spec §10)., RecoveryEngine, Full output of a verification pass (Spec §9.2)., VerificationResult, engine(), _make_cart(), _make_catalog(), _make_contract() (+32 more)

### Community 44 - "schemas.py"
Cohesion: 0.10
Nodes (46): FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8). Provides: - GET…, BaseSchema, BatchResponse, CartItemUpdatePayload, CommerceAdapterInfoResponse, CommerceCartItemResponse, CommerceCartResponse, CommerceCartUpdateRequest (+38 more)

### Community 47 - "simulations.py"
Cohesion: 0.10
Nodes (41): advance_simulation(), AdvanceTimeRequest, ApplyScenarioRequest, create_simulation(), CreateSimulationRequest, get_active_simulation(), _get_or_restore_engine(), get_simulation() (+33 more)

### Community 48 - "_make_contract"
Cohesion: 0.17
Nodes (12): _make_contract(), Adding non-veg item to vegetarian contract → BLOCKED., Price pushes total over hard budget with zero deviation → BLOCKED., Small overrun within allowed deviation → ASK_USER (not blocked)., Different brand for brand-locked product → BLOCKED., Helper to build a minimal IntentContract with overrides., Any checkout proposal must return REQUIRE_CONFIRMATION (Spec §8.3)., test_ask_user_for_budget_within_deviation() (+4 more)

### Community 49 - "decision/models.py"
Cohesion: 0.08
Nodes (30): Evaluate decision for a risk and persist the top recommendation. Returns the…, ActionScorer, CandidateAction, DecisionResult, DiscountInput, ExplainabilityFacts, HoldInput, PureDecisionEvaluator (+22 more)

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
Cohesion: 0.29
Nodes (10): get_product(), list_products(), AsyncSession, get, UUID, Products REST API — spec §32.4. Endpoints: GET /api/products — list all catalog…, List all 25 catalog products., Get a single product by ID. (+2 more)

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

### Community 62 - "intent_chat.py"
Cohesion: 0.10
Nodes (30): clear_session(), get_session(), intent_chat(), intent_choice(), intent_confirm(), delete, get, post (+22 more)

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

### Community 75 - "IntentItem"
Cohesion: 0.12
Nodes (22): IntentItem, An individual item requested within an intent., LoopingRecoveryEngine, Bounded, deterministic recovery loop orchestrator (Spec §10)., Run the multi-turn recovery loop up to max_attempts., Find in-stock product variants matching the target's category or name., Calculate multiple packs if primary pack size is unavailable (Spec §10.2 item…, Verify brand lock constraint registers as non-negotiable hard constraint (Spec… (+14 more)

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
Cohesion: 0.07
Nodes (47): CartItemUpdate, Request to modify quantity of a variant in the cart., Update or replace cart items with given variants and quantities., Search commerce for an IntentItem and pick the best matching variant. Strategy:…, Resolve each IntentItem into a CartItemUpdate via CommercePort search., _search_and_pick(), create_app(), asyncio (+39 more)

### Community 82 - "PreferenceStore"
Cohesion: 0.10
Nodes (19): PreferenceStore, BaseModel, Get all durable preferences for a customer., Convert stored brand preferences to domain BrandPreference models. Only returns…, Convert stored non-brand preferences to domain SoftPreference models. Only…, Remove preferences older than the threshold (Spec §7.2). Returns the number of…, Check if a preference should be rejected per Spec §7.2. Rejects: - price-type…, Remove all preferences for a customer. (+11 more)

### Community 83 - "SimulationEngine"
Cohesion: 0.06
Nodes (49): Customer, Order, OrderItem, Product, Scenario, Store, Supplier, Any (+41 more)

### Community 84 - "GrocerOrchestrator"
Cohesion: 0.19
Nodes (28): GrocerOrchestrator, Stateless conversational commerce orchestrator (Spec §12, Phase 6).…, new_session(), asyncio, Phase 6 — GrocerOrchestrator end-to-end tests (Spec §20 Phase 6). Tests the…, Checkout must strictly require AWAITING_CONFIRMATION state and cannot be…, Return a fresh (session_id, customer_id) pair., test_api_chat_endpoint() (+20 more)

### Community 85 - "IntentParser"
Cohesion: 0.07
Nodes (25): IntentParser, Parse WhatsApp natural language into a validated IntentContract. Architecture…, Parse natural language text into a validated IntentContract. Args: text: Raw…, parser(), fixture, vegetarian only, use my usual brands' → dietary=hard, brands=soft., vegetarian items, also get chicken' → HIGH ambiguity flagged., get some apples' → MEDIUM ambiguity on quantity. (+17 more)

### Community 86 - "RuleBasedExtractor"
Cohesion: 0.11
Nodes (13): Deterministic pattern-based extraction of intent fields from natural language., Extract raw intent fields from text. Returns a dict of candidate fields., Extract the high-level shopping goal., Extract budget constraint from text., Extract individual shopping items with quantities and units., Build an item dict with category hint., Extract dietary constraints (always hard)., Extract brand-level preferences and hard locks. (+5 more)

### Community 87 - "asyncio"
Cohesion: 0.20
Nodes (14): asyncio, AsyncSession, Should persist Simulation and Scenario., Should persist an Event with JSON payload., Should persist a Store with all required fields., Should persist a Supplier., Should persist a Product linked to a Supplier., Should persist a Customer linked to a home Store. (+6 more)

### Community 88 - "GROCER_V2_MASTER_SPEC.md"
Cohesion: 0.14
Nodes (13): 0. Purpose of this document, 14. Error and retry semantics, 17. Security and safety invariants, 18. Existing GROCER UX foundation, 22. Engineering standards, 23. Anti-drift rules for coding agents, 24. Definition of done, 2. Product goals (+5 more)

### Community 89 - "Batch"
Cohesion: 0.12
Nodes (28): Batch, Event, apply_supplier_delay(), create_purchase_order(), get_active_pos(), process_supplier_deliveries(), PurchaseOrder, AsyncSession (+20 more)

### Community 90 - "GROCER v2 — Flagship Golden Flow: Intent-Preserving Grocery Replenishment"
Cohesion: 0.14
Nodes (13): 1. Executive Summary & Product Thesis, 2. The Flagship Scenario, 3. End-to-End Execution Trace (10-Step Loop), 4. Automated Test Verification, 5. Interactive UI Workbench, 6. Non-Negotiable Invariants Upheld, Detailed Trace, Extracted Intent Contract (+5 more)

### Community 91 - "swiggy_adapter.py"
Cohesion: 0.13
Nodes (18): AddressNotServiceableError, CartExpiredError, CommerceError, ItemOutOfStockError, ProviderAuthError, Canonical exception taxonomy for CommercePort and Swiggy Instamart integration., Raised when checkout is attempted without explicit human/user confirmation. In…, Raised when the target delivery address is outside dark store service radius. (+10 more)

### Community 92 - "OrchestratorSessionStore"
Cohesion: 0.18
Nodes (8): OrchestratorSession, OrchestratorSessionStore, Full per-session conversational commerce state. Created on first turn for a…, Thread-safe in-memory store for OrchestratorSession objects. Keyed by…, Return existing session or create a fresh READY session., asyncio, Conversational GrocerOrchestrator turn-by-turn with OOS recovery and explicit…, test_golden_orchestrator_turn_with_oos_recovery()

### Community 95 - "IntentSessionStore"
Cohesion: 0.13
Nodes (8): IntentSessionStore, In-memory session store providing snapshot versioning for IntentContracts., Save an intent contract snapshot into session history., Get the latest (highest version) IntentContract for a session., Retrieve an IntentContract by its unique intent_id., Retrieve a specific version of the IntentContract for a session., List all version snapshots for a session in ascending order., Clear all intent history for a session.

### Community 99 - "PendingClarification"
Cohesion: 0.17
Nodes (11): _candidates_to_options(), _msg_clarification(), _msg_failed(), _msg_ordered(), Process one conversational message through the full commerce loop. Flow: parse…, Resolve a NEEDS_DECISION clarification with the user's chosen spin_id., Execute checkout after explicit user confirmation (Spec §6, §8.3). CRITICAL:…, Load established soft preferences and apply where not overridden (Spec §7).… (+3 more)

### Community 100 - "._make_awaiting_confirmation"
Cohesion: 0.29
Nodes (7): _build_basket_summary(), _msg_auto_recovered(), _msg_basket_ready(), Any, Convert a CommerceCart + contract into a BasketSummary., Transition to AWAITING_CONFIRMATION and return the full result., BasketSummary

### Community 103 - "8. Phase 6 — Agent orchestration"
Cohesion: 0.50
Nodes (4): 8. Phase 6 — Agent orchestration, Desired flow, Goal, Rule

### Community 105 - "._parse_intent"
Cohesion: 0.33
Nodes (6): _is_fresh_request(), _is_incremental_add(), _merge_contracts(), Parse message → IntentContract, inheriting session_id., Heuristic: treat message as fresh grocery request vs a refinement., Merge new contract onto existing, respecting intent precedence (Spec §5.3).

### Community 106 - "orchestrator"
Cohesion: 0.29
Nodes (7): fresh_store(), mock_adapter(), orchestrator(), fixture, Return a clean, isolated session store for each test., Return a fresh MockCommerceAdapter per test., GrocerOrchestrator wired to the mock adapter and an isolated session store.

### Community 107 - "19. Repository boundary and cleanup"
Cohesion: 0.67
Nodes (3): 19. Repository boundary and cleanup, Keep and extend, Refactor or remove from GROCER

### Community 109 - "2. Phase 0 — Consumer boundary cleanup"
Cohesion: 0.25
Nodes (8): 2. Phase 0 — Consumer boundary cleanup, Acceptance, Goal, Inspect first, Preserve, Remove fake consumer → dark-store mutation, Remove/isolate old operations residue, Required work

### Community 117 - "AGENTS.md — GROCER Coding Agent Contract"
Cohesion: 0.12
Nodes (15): 10. Frontend rules, 11. Engineering behavior, 12. Quality commands, 13. What to do when requirements appear ambiguous, 1. Read this first, 2. Non-negotiable product boundary, 3. Extend, do not replace, 4. LLM responsibility (+7 more)

### Community 130 - "CommercePort"
Cohesion: 0.08
Nodes (30): ABC, get_commerce_adapter(), Factory for obtaining configured CommercePort adapter., Resolve and return active CommercePort adapter based on settings., High-fidelity mock commerce adapter for local simulation and testing., CommerceOrderResult, DeliveryAddress, DeliveryTrackingStatus (+22 more)

## Knowledge Gaps
- **384 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+379 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CommerceCart` connect `IntentContract` to `SwiggyMCPAdapter`, `CommercePort`, `MockCommerceAdapter`, `IntentVerifier`, `IntentItem`, `RecoveryEngine`, `test_phase8_commerce.py`, `CustomerService`, `intent/__init__.py`, `swiggy_adapter.py`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `CartItemUpdate` connect `test_phase8_commerce.py` to `SwiggyMCPAdapter`, `CommercePort`, `PendingClarification`, `MockCommerceAdapter`, `ConstraintType`, `IntentItem`, `schemas.py`, `RecoveryEngine`, `test_handle_choice_preserves_unrelated_items_and_quantity`, `IntentContract`, `GrocerOrchestrator`, `CustomerService`, `intent/__init__.py`, `swiggy_adapter.py`, `UUID`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `IntentContract` connect `IntentContract` to `PendingClarification`, `._make_awaiting_confirmation`, `.to_summary_dict`, `ConstraintType`, `._parse_intent`, `IntentItem`, `RecoveryEngine`, `test_phase8_commerce.py`, `_make_contract`, `IntentParser`, `intent/__init__.py`, `IntentVerifier`, `IntentSessionStore`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `IntentContract` (e.g. with `AmbiguitySeverity` and `BrandTolerance`) actually correct?**
  _`IntentContract` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `CommerceCart` (e.g. with `MockCommerceAdapter` and `CommercePort`) actually correct?**
  _`CommerceCart` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `RecoveryEngine` (e.g. with `GrocerOrchestrator` and `OrchestratorTurnResult`) actually correct?**
  _`RecoveryEngine` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `MockCommerceAdapter` (e.g. with `AddressNotServiceableError` and `CommerceError`) actually correct?**
  _`MockCommerceAdapter` has 15 INFERRED edges - model-reasoned connections that need verification._