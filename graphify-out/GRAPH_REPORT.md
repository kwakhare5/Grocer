# Graph Report - Grocer  (2026-09-06)

## Corpus Check
- 92 files · ~112,918 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1404 nodes · 3251 edges · 99 communities (87 shown, 12 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 425 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `da01bc8b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SwiggyMCPAdapter
- env.py
- CommerceCart
- test_canonical_recovery_regression.py
- AGENTS.md — GROCER Project Rules
- MockCommerceAdapter
- compilerOptions
- intent/__init__.py
- ARCHITECTURE.md — GROCER v2
- 16.1 Core metrics
- Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent
- dependencies
- 20. Recommended implementation sequence
- SwiggyClient
- UUID
- Core metrics
- Intent Cleanroom Audit
- Initial scenario set
- ConstraintViolation
- 5. Intent Contract
- GROCER Cleanroom Status
- CONTEXT.md — GROCER Domain Context
- Intent Phase Next
- test_policy_engine.py
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- IphoneFrame.tsx
- .prettierrc.json
- IntentVerifier
- layout.tsx
- 23. Anti-drift rules for coding agents
- Changes Made
- IntentCommerceWorkbench.tsx
- .get_cart
- Log Entries
- 7. Phase 5 — Recovery engine
- 5. Phase 3 — Policy and memory
- 6. Phase 4 — Intent Verifier
- scenarioEngine.ts
- .get_go_to_items
- metricsEngine.ts
- Grocer — Historical Context & ADRs
- 10. Recovery engine
- RecoveryEngine
- .search_products
- graphify
- workflows/graphify.md
- LEGACY_ARCHITECTURE.md
- 11. Conversation behavior
- 3.1 IN SCOPE
- Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me)
- 12. Agent architecture
- GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification
- 13. State model
- 1. Product identity
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
- GROCER — Active Task Board
- 11. Phase 9 — Live Swiggy hardening
- 3. Phase 1 — Intent Contract
- 9. Phase 7 — Deterministic failure simulation
- test_health_endpoint_returns_200
- IntentItem
- IMPLEMENTATION_PLAN.md
- 4. Product job-to-be-done
- 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)
- CartItemUpdate
- PreferenceStore
- GrocerOrchestrator
- IntentParser
- RuleBasedExtractor
- GROCER_V2_MASTER_SPEC.md
- GROCER v2 — Flagship Golden Flow: Intent-Preserving Grocery Replenishment
- CommerceError
- OrchestratorSessionStore
- agents/__init__.py
- IntentContract
- orchestrator.py
- 8. Phase 6 — Agent orchestration
- orchestrator
- RecoveryCandidate
- 2. Phase 0 — Consumer boundary cleanup
- AGENTS.md — GROCER Coding Agent Contract
- CommercePort

## God Nodes (most connected - your core abstractions)
1. `IntentContract` - 85 edges
2. `CommerceCart` - 72 edges
3. `IntentVerifier` - 64 edges
4. `RecoveryEngine` - 63 edges
5. `GrocerOrchestrator` - 63 edges
6. `VerificationResult` - 62 edges
7. `MockCommerceAdapter` - 60 edges
8. `RecoveryOutcome` - 53 edges
9. `CartItemUpdate` - 52 edges
10. `CommercePort` - 51 edges

## Surprising Connections (you probably didn't know these)
- `IntentCommerceWorkbenchProps` --references--> `CustomerPersona`  [EXTRACTED]
  components/customer/IntentCommerceWorkbench.tsx → lib/types.ts
- `SwiggyMCPAdapter` --uses--> `AddressNotServiceableError`  [INFERRED]
  backend/integrations/commerce/swiggy_adapter.py → backend/integrations/commerce/exceptions.py
- `SwiggyMCPAdapter` --uses--> `CartExpiredError`  [INFERRED]
  backend/integrations/commerce/swiggy_adapter.py → backend/integrations/commerce/exceptions.py
- `SwiggyMCPAdapter` --uses--> `CommerceError`  [INFERRED]
  backend/integrations/commerce/swiggy_adapter.py → backend/integrations/commerce/exceptions.py
- `SwiggyMCPAdapter` --uses--> `ItemOutOfStockError`  [INFERRED]
  backend/integrations/commerce/swiggy_adapter.py → backend/integrations/commerce/exceptions.py

## Import Cycles
- None detected.

## Communities (99 total, 12 thin omitted)

### Community 0 - "SwiggyMCPAdapter"
Cohesion: 0.24
Nodes (5): Any, Classify errors from Swiggy envelope per official error taxonomy., Production adapter for Swiggy Instamart MCP server., Execute JSON-RPC tool call against Swiggy Instamart MCP endpoint., SwiggyMCPAdapter

### Community 1 - "env.py"
Cohesion: 0.22
Nodes (7): do_run_migrations(), run_async_migrations(), run_migrations_online(), Settings, get_db(), AsyncSession, BaseSettings

### Community 2 - "CommerceCart"
Cohesion: 0.08
Nodes (30): CommerceCart, CommerceProductItem, ProductVariant, SKU-level variant with provider-specific spinId., Catalogue product item containing one or more pack-size variations., Active customer cart with bill breakdown., LoopingRecoveryResult, BaseModel (+22 more)

### Community 3 - "test_canonical_recovery_regression.py"
Cohesion: 0.14
Nodes (23): FailureClass, LoopingRecoveryEngine — canonical bounded multi-turn recovery loop (Spec §10,…, Enum, str, Recovery Engine — deterministic intent drift repair and candidate ranking (Spec…, Terminal or intermediate state of a recovery attempt (Spec §10.4)., Normalized taxonomy of commerce intent failures (Spec §10.2)., RecoveryState (+15 more)

### Community 4 - "AGENTS.md — GROCER Project Rules"
Cohesion: 0.10
Nodes (19): 10. SWIGGY MCP RULES, 11. UI RULES, 12. SAFETY INVARIANTS, 13. QUALITY GATE, 14. DECISION RULE FOR NEW IDEAS, 15. SESSION RESUME, 1. PROJECT IDENTITY — LOCKED, 2. TARGET FLOW (+11 more)

### Community 5 - "MockCommerceAdapter"
Cohesion: 0.10
Nodes (10): MinOrderNotMetError, Raised when cart grand total is below minimum order threshold., MockCommerceAdapter, Deterministic in-memory commerce simulation adapter with failure injection., Initialize instance-isolated catalog copies., Simulate an item variant going out of stock in real-time., Simulate a supplier or store-level price surge., Simulate session expiry or store becoming unserviceable. (+2 more)

### Community 6 - "compilerOptions"
Cohesion: 0.07
Nodes (28): dom, dom.iterable, esnext, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules (+20 more)

### Community 7 - "intent/__init__.py"
Cohesion: 0.14
Nodes (47): AmbiguitySeverity, BrandTolerance, ConstraintType, PrecedenceLevel, PreferenceType, Enum, str, Domain enums for GROCER Intent Contract (Spec §5). Encodes explicit vocabulary… (+39 more)

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

### Community 14 - "UUID"
Cohesion: 0.15
Nodes (10): EventBus, Any, AsyncSession, In-process event bus for GROCER v2. LOCKED (spec §30): async in-process pub/sub…, Simple in-process async event pub/sub bus. Usage: bus = EventBus()…, Decorator to register a handler for a given event type., Programmatically register a handler., Publish an event. - Calls all registered handlers for *event_type*. - If… (+2 more)

### Community 15 - "Core metrics"
Cohesion: 0.18
Nodes (11): 10. Phase 8 — Evaluation, Budget deviation, Core metrics, Human intervention rate, Intent preservation rate, MCP/tool calls, Recovery attempts, Recovery success rate (+3 more)

### Community 16 - "Intent Cleanroom Audit"
Cohesion: 0.33
Nodes (5): Decisions, First failure scenario, Golden path, Intent Cleanroom Audit, Non-goals

### Community 17 - "Initial scenario set"
Cohesion: 0.25
Nodes (8): 15. Deterministic failure simulation, Initial scenario set, Scenario A — happy path, Scenario B — preferred item unavailable, Scenario C — budget drift, Scenario D — ambiguous substitution, Scenario E — stale cart, Scenario F — transient provider failure

### Community 18 - "ConstraintViolation"
Cohesion: 0.13
Nodes (13): ConstraintViolation, PreferenceDeviation, BaseModel, Compare cart state to intent contract. Args: contract: The active…, Full verification pass with checkout authorization gate (Spec §8.3, §17.1).…, Check for items in active cart that have become out-of-stock or unserviceable., Return (budget_delta, violations). budget_delta = grand_total - max_budget…, Return (missing_item_names, deviations_for_non_essential_missing). (+5 more)

### Community 19 - "5. Intent Contract"
Cohesion: 0.29
Nodes (7): 5.1 Required conceptual fields, 5.2 Example, 5.3 Precedence rules, 5.4 Hard vs soft, 5. Intent Contract, Hard constraint, Soft preference

### Community 20 - "GROCER Cleanroom Status"
Cohesion: 0.33
Nodes (5): Cleanup rules, Completion gate, Current worktree, GROCER Cleanroom Status, Target boundary

### Community 21 - "CONTEXT.md — GROCER Domain Context"
Cohesion: 0.11
Nodes (18): 10. UI rule, 11. External provider rule, 12. Quality gate, 1. Project identity, 2. Canonical terms, 3. Product objective, 4. Intent precedence, 5. Autonomy rules (+10 more)

### Community 22 - "Intent Phase Next"
Cohesion: 0.40
Nodes (4): Acceptance criteria, First failure, Intent Phase Next, Target

### Community 23 - "test_policy_engine.py"
Cohesion: 0.10
Nodes (34): ActionProposal, AutonomyLevel, PolicyDecision, PolicyEngine, BaseModel, Enum, str, Policy Engine — deterministic agent autonomy classification (Spec §6).… (+26 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.20
Nodes (10): Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx), [MODIFY] [`GrocerFooter.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerFooter.tsx), [MODIFY] [`GrocerHero.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerHero.tsx), [MODIFY] [`GrocerIntegrations.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerIntegrations.tsx), [MODIFY] [`GrocerValueProp.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerValueProp.tsx) & [`GrocerVelocityCalculator.tsx`](file:///d:/Grocer/frontend/components/grocer/GrocerVelocityCalculator.tsx) (+2 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "IntentVerifier"
Cohesion: 0.13
Nodes (41): CartItem, Item present in active commerce cart., IntentVerifier, Deterministic engine that compares live commerce state to IntentContract. All…, _bread_item(), _make_cart(), _make_contract(), _milk_item() (+33 more)

### Community 28 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 29 - "23. Anti-drift rules for coding agents"
Cohesion: 0.67
Nodes (3): 23. Anti-drift rules for coding agents, ALWAYS, NEVER

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 31 - "IntentCommerceWorkbench.tsx"
Cohesion: 0.09
Nodes (38): Home(), BasketCard(), ChatMessage, formatMoney(), IntentCommerceWorkbench(), IntentCommerceWorkbenchProps, newSessionId(), AppGlobalHeader() (+30 more)

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
Cohesion: 0.07
Nodes (47): health_check(), get, Report API health without depending on the retired operations database., clear_session(), get_session(), intent_chat(), intent_choice(), intent_confirm() (+39 more)

### Community 63 - "7. Memory and preferences"
Cohesion: 0.50
Nodes (4): 7.1 What may be stored, 7.2 What should not be treated as permanent policy, 7.3 Precedence, 7. Memory and preferences

### Community 64 - "8. Commerce architecture"
Cohesion: 0.50
Nodes (4): 8.1 Existing foundation to preserve, 8.2 Swiggy MCP rules, 8.3 Checkout guard, 8. Commerce architecture

### Community 66 - "9. Intent verification"
Cohesion: 0.50
Nodes (4): 9.1 Verification inputs, 9.2 Verification output, 9.3 Verification principles, 9. Intent verification

### Community 70 - "GROCER — Active Task Board"
Cohesion: 0.22
Nodes (8): GROCER — Active Task Board, Non-negotiables, P0 — Cleanroom boundary, P1 — Intent correctness, P2 — Golden vertical slice, P3 — Reliability + evaluation, P4 — Experience, Tracer Bullets: Cleanroom Intent-Preserving Commerce & Golden Flow

### Community 71 - "11. Phase 9 — Live Swiggy hardening"
Cohesion: 0.50
Nodes (4): 11. Phase 9 — Live Swiggy hardening, Acceptance, Goal, Rules

### Community 72 - "3. Phase 1 — Intent Contract"
Cohesion: 0.50
Nodes (4): 3. Phase 1 — Intent Contract, Acceptance, Goal, Required fields

### Community 73 - "9. Phase 7 — Deterministic failure simulation"
Cohesion: 0.50
Nodes (4): 9. Phase 7 — Deterministic failure simulation, Acceptance, Goal, Initial scenarios

### Community 74 - "test_health_endpoint_returns_200"
Cohesion: 0.40
Nodes (4): AsyncClient, asyncio, Health endpoint should return a healthy API status., test_health_endpoint_returns_200()

### Community 75 - "IntentItem"
Cohesion: 0.09
Nodes (39): BudgetConstraint, IntentItem, PackSizeRules, An individual item requested within an intent., Budget boundary for the shopping task., Rules governing pack size substitutions., LoopingRecoveryEngine, Bounded, deterministic recovery loop orchestrator (Spec §10, §12). (+31 more)

### Community 76 - "IMPLEMENTATION_PLAN.md"
Cohesion: 0.17
Nodes (11): 0. Implementation rules, 12. Phase 10 — Demo hardening, 13. Definition of done for implementation, 1. Execution order, 4. Phase 2 — Intent extraction, Examples, Flagship narrative, Goal (+3 more)

### Community 77 - "4. Product job-to-be-done"
Cohesion: 0.67
Nodes (3): 4. Product job-to-be-done, Primary job, Secondary jobs

### Community 78 - "2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK)"
Cohesion: 0.18
Nodes (10): 1. Executive Summary, 2. Component Disposition (REUSE / REFACTOR / DELETE / MISSING / RISK), 3. Test & Runtime Baseline, DELETE / DEPRECATE, Key Audit Findings, MISSING, Phase 0: Repository Audit & Technical Baseline, REFACTOR (+2 more)

### Community 80 - "CartItemUpdate"
Cohesion: 0.11
Nodes (7): CartItemUpdate, Request to modify quantity of a variant in the cart., Update or replace cart items with given variants and quantities., Search commerce for an IntentItem and pick the best matching variant. Strategy:…, Resolve each IntentItem into a CartItemUpdate via CommercePort search., _search_and_pick(), FakeCommercePort

### Community 82 - "PreferenceStore"
Cohesion: 0.10
Nodes (19): PreferenceStore, BaseModel, Get all durable preferences for a customer., Convert stored brand preferences to domain BrandPreference models. Only returns…, Convert stored non-brand preferences to domain SoftPreference models. Only…, Remove preferences older than the threshold (Spec §7.2). Returns the number of…, Check if a preference should be rejected per Spec §7.2. Rejects: - price-type…, Remove all preferences for a customer. (+11 more)

### Community 84 - "GrocerOrchestrator"
Cohesion: 0.18
Nodes (29): GrocerOrchestrator, Stateless conversational commerce orchestrator (Spec §12, Phase 6).…, new_session(), asyncio, Phase 6 — GrocerOrchestrator end-to-end tests (Spec §20 Phase 6). Tests the…, handle_choice rejects spins not in pending_clarification.candidates., Checkout must strictly require AWAITING_CONFIRMATION state and cannot be…, Return a fresh (session_id, customer_id) pair. (+21 more)

### Community 85 - "IntentParser"
Cohesion: 0.09
Nodes (28): IntentParser, Parse WhatsApp natural language into a validated IntentContract. Architecture…, Parse natural language text into a validated IntentContract. Args: text: Raw…, parser(), fixture, Unit tests for GROCER Phase 2 Intent Parser (Spec §5, §12, IMPLEMENTATION_PLAN…, vegetarian only, use my usual brands' → dietary=hard, brands=soft., vegetarian items, also get chicken' → HIGH ambiguity flagged. (+20 more)

### Community 86 - "RuleBasedExtractor"
Cohesion: 0.11
Nodes (13): Deterministic pattern-based extraction of intent fields from natural language., Extract raw intent fields from text. Returns a dict of candidate fields., Extract the high-level shopping goal., Extract budget constraint from text., Extract individual shopping items with quantities and units., Build an item dict with category hint., Extract dietary constraints (always hard)., Extract brand-level preferences and hard locks. (+5 more)

### Community 88 - "GROCER_V2_MASTER_SPEC.md"
Cohesion: 0.14
Nodes (13): 0. Purpose of this document, 14. Error and retry semantics, 17. Security and safety invariants, 18. Existing GROCER UX foundation, 19. Repository boundary and cleanup, 22. Engineering standards, 24. Definition of done, 2. Product goals (+5 more)

### Community 90 - "GROCER v2 — Flagship Golden Flow: Intent-Preserving Grocery Replenishment"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Product Thesis, 2. The Flagship Scenario, 3. End-to-End Execution Trace (10-Step Loop), 4. Canonical Recovery Loop & Automated Test Verification, 5. Interactive UI Workbench, 6. Non-Negotiable Invariants Upheld, Canonical Recovery Engine Architecture, Detailed Trace (+6 more)

### Community 91 - "CommerceError"
Cohesion: 0.12
Nodes (16): AddressNotServiceableError, CartExpiredError, CommerceError, ItemOutOfStockError, ProviderAuthError, Canonical exception taxonomy for CommercePort and Swiggy Instamart integration., Raised when checkout is attempted without explicit human/user confirmation. In…, Raised when the target delivery address is outside dark store service radius. (+8 more)

### Community 92 - "OrchestratorSessionStore"
Cohesion: 0.14
Nodes (10): OrchestratorSession, OrchestratorSessionStore, Full per-session conversational commerce state. Created on first turn for a…, Thread-safe in-memory store for OrchestratorSession objects. Keyed by…, Return existing session or create a fresh READY session., Proves GrocerOrchestrator -> LoopingRecoveryEngine -> CommercePort ->…, test_orchestrator_oos_recovery_canonical_path(), asyncio (+2 more)

### Community 95 - "IntentContract"
Cohesion: 0.04
Nodes (35): IntentContract, Any, The canonical structured representation of user shopping intent (Spec §5). The…, Validate critical domain invariants across the contract., Check whether a specific dietary constraint applies., Check if target attribute is governed by a hard constraint., Get brand preference for a product or category., Return True if any ambiguity blocks safe deterministic execution. (+27 more)

### Community 99 - "orchestrator.py"
Cohesion: 0.10
Nodes (26): _build_basket_summary(), _candidates_to_options(), _is_fresh_request(), _is_incremental_add(), _merge_contracts(), _msg_auto_recovered(), _msg_basket_ready(), _msg_clarification() (+18 more)

### Community 103 - "8. Phase 6 — Agent orchestration"
Cohesion: 0.50
Nodes (4): 8. Phase 6 — Agent orchestration, Desired flow, Goal, Rule

### Community 106 - "orchestrator"
Cohesion: 0.29
Nodes (7): fresh_store(), mock_adapter(), orchestrator(), fixture, Return a clean, isolated session store for each test., Return a fresh MockCommerceAdapter per test., GrocerOrchestrator wired to the mock adapter and an isolated session store.

### Community 108 - "RecoveryCandidate"
Cohesion: 0.15
Nodes (19): A scored alternative product variant considered during recovery., RecoveryCandidate, BasketItem, BasketSummary, ConversationState, PendingClarification, BaseModel, Enum (+11 more)

### Community 109 - "2. Phase 0 — Consumer boundary cleanup"
Cohesion: 0.25
Nodes (8): 2. Phase 0 — Consumer boundary cleanup, Acceptance, Goal, Inspect first, Preserve, Remove fake consumer → dark-store mutation, Remove/isolate old operations residue, Required work

### Community 117 - "AGENTS.md — GROCER Coding Agent Contract"
Cohesion: 0.12
Nodes (15): 10. Frontend rules, 11. Engineering behavior, 12. Quality commands, 13. What to do when requirements appear ambiguous, 1. Read this first, 2. Non-negotiable product boundary, 3. Extend, do not replace, 4. LLM responsibility (+7 more)

### Community 130 - "CommercePort"
Cohesion: 0.12
Nodes (25): ABC, get_commerce_adapter(), Factory for obtaining configured CommercePort adapter., Resolve and return active CommercePort adapter based on settings., Commerce integration layer for Grocer (Spec §5.1, §28, & §38.9). Provides the…, High-fidelity mock commerce adapter for local simulation and testing., CommerceOrderResult, DeliveryAddress (+17 more)

## Knowledge Gaps
- **386 isolated node(s):** `Critical anti-drift rule`, `2. TARGET FLOW`, `3. NEVER BUILD THESE INSIDE GROCER`, `4. INTENT RULES`, `5. AUTONOMY RULES` (+381 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `IntentContract` connect `IntentContract` to `CommerceCart`, `orchestrator.py`, `test_canonical_recovery_regression.py`, `intent/__init__.py`, `IntentItem`, `RecoveryCandidate`, `RecoveryEngine`, `CartItemUpdate`, `ConstraintViolation`, `IntentParser`, `test_policy_engine.py`, `IntentVerifier`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `GrocerOrchestrator` connect `GrocerOrchestrator` to `CommerceCart`, `orchestrator.py`, `CommercePort`, `test_canonical_recovery_regression.py`, `intent/__init__.py`, `IntentVerifier`, `orchestrator`, `IntentItem`, `RecoveryCandidate`, `RecoveryEngine`, `CartItemUpdate`, `IntentParser`, `test_policy_engine.py`, `CommerceError`, `OrchestratorSessionStore`, `intent_chat.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `IntentParser` connect `IntentParser` to `orchestrator.py`, `intent/__init__.py`, `RecoveryCandidate`, `PreferenceStore`, `GrocerOrchestrator`, `RuleBasedExtractor`, `test_policy_engine.py`, `OrchestratorSessionStore`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `IntentContract` (e.g. with `AmbiguitySeverity` and `BrandTolerance`) actually correct?**
  _`IntentContract` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `CommerceCart` (e.g. with `MockCommerceAdapter` and `CommercePort`) actually correct?**
  _`CommerceCart` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `IntentVerifier` (e.g. with `GrocerOrchestrator` and `OrchestratorTurnResult`) actually correct?**
  _`IntentVerifier` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `RecoveryEngine` (e.g. with `GrocerOrchestrator` and `OrchestratorTurnResult`) actually correct?**
  _`RecoveryEngine` has 24 INFERRED edges - model-reasoned connections that need verification._