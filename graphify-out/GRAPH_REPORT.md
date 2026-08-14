# Graph Report - PreFill  (2026-08-14)

## Corpus Check
- 105 files · ~15,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 723 nodes · 1059 edges · 65 communities (59 shown, 6 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Module 0
- Module 1
- Module 2
- Module 3
- Module 4
- Module 5
- Module 6
- Module 7
- Module 8
- Module 9
- Module 10
- Module 11
- Module 12
- Module 13
- Module 14
- Module 15
- Module 16
- Module 17
- Module 18
- Module 19
- Module 20
- Module 21
- Module 22
- Module 23
- Module 24
- Module 25
- Module 26
- Module 27
- Module 28
- Module 29
- Module 30
- Module 31
- Module 32
- Module 33
- Module 34
- Module 35
- Module 36
- Module 37
- Module 38
- Module 39
- Module 40
- Module 41
- Module 45
- Module 46
- Module 47
- Module 49
- Module 50
- Module 51

## God Nodes (most connected - your core abstractions)
1. `Household` - 18 edges
2. `compilerOptions` - 16 edges
3. `ConsumptionModeler` - 14 edges
4. `build_restock_graph()` - 13 edges
5. `init_db()` - 13 edges
6. `GROCER — Engineering Prototype & Problem Exploration` - 12 edges
7. `whatsapp_webhook()` - 12 edges
8. `ARCHITECTURE.md — Product Strategy & User Experience Architecture` - 11 edges
9. `Base` - 11 edges
10. `ConsumptionModel` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `init_db()`  [EXTRACTED]
  scratch/init_timescale.py → backend/database/connection.py
- `test_consumption_modeler_rebuild()` --indirect_call--> `db()`  [INFERRED]
  backend/tests/test_ml.py → backend/tests/test_db.py
- `test_price_agent_tracking()` --indirect_call--> `db()`  [INFERRED]
  backend/tests/test_prices.py → backend/tests/test_db.py
- `lifespan()` --calls--> `get_checkpointer()`  [EXTRACTED]
  backend/main.py → backend/database/connection.py
- `lifespan()` --calls--> `init_db()`  [EXTRACTED]
  backend/main.py → backend/database/connection.py

## Import Cycles
- None detected.

## Communities (65 total, 6 thin omitted)

### Community 0 - "Module 0"
Cohesion: 0.08
Nodes (25): GrocerAppPreview(), GrocerFAQ(), GrocerFooter(), GrocerHeader(), GrocerHero(), GrocerIntegrations(), GrocerValueProp(), GrocerVelocityCalculator() (+17 more)

### Community 1 - "Module 1"
Cohesion: 0.08
Nodes (37): api, APIHouseholdProfile, APIOrder, APIOrdersResponse, APIPredictionsResponse, APIPriceAlertsResponse, APIPriceFeedItem, APIRecipe (+29 more)

### Community 2 - "Module 2"
Cohesion: 0.10
Nodes (33): get_llm(), Centralized LLM client for agents. Handles provider fallback (Groq -> NVIDIA)…, Returns a configured LangChain Chat model. Prefers Groq (Llama-3-70b), falls…, build_cart(), build_restock_graph(), generate_alert_message(), parse_order_intent(), parse_user_reply() (+25 more)

### Community 3 - "Module 3"
Cohesion: 0.09
Nodes (31): get_household_profile(), get_or_create_household(), AsyncSession, get, post, Get an existing household or create one for this user., Switch the mock data scenario (standard, party, vacation). Clears current db…, Fetch the latest orders from the MCP server and persist new ones to the DB. (+23 more)

### Community 4 - "Module 4"
Cohesion: 0.06
Nodes (14): AsyncClient, GrocerMCPClient, Open the shared connection pool. Call once from the FastAPI lifespan., Fetch complete order history for a user., Search products matching query in the catalog., Update or create cart with standard line items., Place the quick commerce order., cleanup_engine() (+6 more)

### Community 5 - "Module 5"
Cohesion: 0.14
Nodes (18): Price Intelligence Agent — Task 4.5 Monitors volatile commodity price trends,…, Orders API — returns past order history for a household. Reads directly from…, Prices API — Task 3.5 (frontend hydration) Exposes commodity price histories…, Restock Alert API — Task 2.3 Exposes endpoints to: - GET /api/restock/{user_id}…, get_db(), Base, ConsumptionModel, Household (+10 more)

### Community 6 - "Module 6"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 7 - "Module 7"
Cohesion: 0.08
Nodes (25): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+17 more)

### Community 8 - "Module 8"
Cohesion: 0.08
Nodes (23): 1. PRODUCT VISION & STRATEGIC PURPOSE, 2. SYSTEM ARCHITECTURE, 2. USER EXPERIENCE & INTERACTION ARCHITECTURE, 3. DATABASE SCHEMA & DATA MODELS, 3. HOW THE USER SEES AND USES THE APP, 4. FRONTEND ARCHITECTURE & DESIGN SYSTEM ("SHADE"), 5. API CONTRACTS & INTEGRATIONS, 6. LANDING PAGE SHOWCASE STREAM (`app/page.tsx`) (+15 more)

### Community 9 - "Module 9"
Cohesion: 0.13
Nodes (22): _get_household(), get_predictions(), predictions_index(), AsyncSession, get, Predictions API — Task 3.3 (frontend hydration) Exposes consumption model…, Return all consumption model predictions for a household. Sorted by urgency:…, get_price_alerts() (+14 more)

### Community 10 - "Module 10"
Cohesion: 0.08
Nodes (23): 1. Clone the Repository, 1. `pytest` command not found, 2. CORS errors between Next.js and FastAPI, 2. Set Up Python Virtual Environment & Install Dependencies, 3. Environment Configuration, 4. Run Pytest Backend Test Suite, 5. Start Backend Server, 6. Set Up Frontend Development Server (+15 more)

### Community 11 - "Module 11"
Cohesion: 0.09
Nodes (23): axios, clsx, framer-motion, dependencies, axios, clsx, framer-motion, lucide-react (+15 more)

### Community 12 - "Module 12"
Cohesion: 0.13
Nodes (21): Any, build_cart_node(), check_pantry_node(), find_pantry_match(), identify_missing_node(), normalize_quantity(), parse_recipe_node(), ParsedIngredient (+13 more)

### Community 13 - "Module 13"
Cohesion: 0.14
Nodes (18): lifespan(), FastAPI, Modern FastAPI lifespan handler — replaces deprecated @app.on_event. Startup…, daily_depletion_check_all(), Scheduler — Task 2.6 Runs background jobs on a cron schedule using APScheduler…, Run every morning at 07:00 IST (before depletion check). Triggers the Price…, Run every Sunday at 02:00 IST. Re-runs the Prophet consumption model for every…, Register all jobs and start the scheduler. Called once on FastAPI startup. (+10 more)

### Community 14 - "Module 14"
Cohesion: 0.17
Nodes (18): AsyncSession, Stateful execution wrapper that runs the Recipe Graph from end to end., recipe_to_cart(), _get_household(), get_recipes(), parse_recipe(), pin_recipe(), AsyncSession (+10 more)

### Community 15 - "Module 15"
Cohesion: 0.11
Nodes (18): author, description, keywords, license, name, scripts, dev, dev:backend (+10 more)

### Community 16 - "Module 16"
Cohesion: 0.14
Nodes (13): ConfidenceScorer, Confidence Scorer — Task 2.2 Scores how reliable a consumption prediction is,…, Calculate prediction confidence for a single item. Args: purchase_dates: List…, Convert a numeric confidence score into a display-friendly label. Used in the…, Gate for whether to include an item in a restock alert. We only alert users on…, asyncio, ML Integration Tests — pytest Run with: pytest backend/tests/test_ml.py -v…, ConfidenceScorer output must always be between 0 and 1. (+5 more)

### Community 17 - "Module 17"
Cohesion: 0.22
Nodes (14): CartUpdate, get_cart(), get_orders(), lifespan(), place_order(), PlaceOrder, BaseModel, FastAPI (+6 more)

### Community 18 - "Module 18"
Cohesion: 0.14
Nodes (13): 1. CORE BEHAVIOR, 2. SESSION RITUAL, 3. CODING LOOP (SIMPLIFIED MATT POCOCK WORKFLOW), 4. CORE COMMANDS REFERENCE, 5. TASK → SKILL ROUTER (auto-load on AUDIT), 7. SESSION RESUME, AGENTS.md — Global Rules for Karan Wakhare, Applies to every project. Read first. (+5 more)

### Community 19 - "Module 19"
Cohesion: 0.15
Nodes (12): 1. CORE BEHAVIOR, 2. SESSION RITUAL, 3. CODING LOOP (SIMPLIFIED MATT POCOCK WORKFLOW), 4. CORE COMMANDS REFERENCE, 5. TASK → SKILL ROUTER (auto-load on AUDIT), AGENTS.md — Global Rules for Karan Wakhare, Applies to every project. Read first., Full Loop (+4 more)

### Community 20 - "Module 20"
Cohesion: 0.23
Nodes (13): check_depletions_for_household(), get_alert_history(), _get_household_by_user_id(), get_restock_status(), AsyncSession, get, post, Return the current depletion status for a household. Useful for the dashboard… (+5 more)

### Community 21 - "Module 21"
Cohesion: 0.15
Nodes (12): 1. Why We Have the Landing Page & Demo, 2. Why We Have the Mockup iPhone, Agents, AI fills and maintains this via @GRILL. You rarely edit this manually., Business Rules (Never Break), CONTEXT.md — Domain Language, Core Entities & Product Purpose, Database Schema (+4 more)

### Community 22 - "Module 22"
Cohesion: 0.15
Nodes (12): 10. Engineering decisions & design invariants (reference), 1. The problem I noticed, 2. What the prototype does, 3. System architecture, 4. How the prediction model works, 5. How the dark-store integration is mocked, 6. If this were ever pursued for real, how I'd want to validate it, 7. Conceptual integration shape (not a request for access) (+4 more)

### Community 23 - "Module 23"
Cohesion: 0.21
Nodes (6): AnomalyDetector, Single order quantity >2.5x baseline = guests visited. Exclude from model., Category purchase count drops >60% in most recent month vs prior average., Gaps of 5+ days between consecutive orders = likely travel., Consumption Model — Task 2.1 Builds per-item consumption forecasts from…, datetime

### Community 24 - "Module 24"
Cohesion: 0.17
Nodes (11): Automated Build & Test Verification, [DELETE] [`EXECUTIVE_PITCH.md`](file:///d:/PreFill/EXECUTIVE_PITCH.md), Documentation Changes & Deletions, Implementation Plan — Markdown Alignment & Codebase Cleanup, [MODIFY] [`.agents/AGENTS.md`](file:///d:/PreFill/.agents/AGENTS.md), [MODIFY] [`ARCHITECTURE.md`](file:///d:/PreFill/ARCHITECTURE.md), [MODIFY] [`CONTEXT.md`](file:///d:/PreFill/CONTEXT.md), [MODIFY] [`README.md`](file:///d:/PreFill/README.md) (+3 more)

### Community 25 - "Module 25"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 26 - "Module 26"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "Module 27"
Cohesion: 0.36
Nodes (7): AsyncSession, Core function for the Price Intelligence Agent. 1. Queries current prices of…, track_and_alert_prices(), asyncio, test_get_price_alerts(), test_get_price_feed(), test_price_agent_tracking()

### Community 28 - "Module 28"
Cohesion: 0.29
Nodes (7): get_checkpointer(), AsyncSession, post, whatsapp_webhook(), asyncio, test_postgres_saver_connection(), Request

### Community 29 - "Module 29"
Cohesion: 0.36
Nodes (6): init_db(), PriceHistory, Seed Price History — Task 3.5 Seeds the `price_history` table in TimescaleDB…, seed_prices(), setup_test_db(), main()

### Community 30 - "Module 30"
Cohesion: 0.25
Nodes (7): 1. Deleted Outdated Pitch Documentation, 1. Pytest Backend Test Suite, 2. Next.js Production Build, 2. Synchronized Master Markdown Files, 🛠️ Executed Cleanup & Alignment, 🧪 Verification Results, Walkthrough — Markdown Alignment & Codebase Cleanup Complete

### Community 31 - "Module 31"
Cohesion: 0.48
Nodes (3): ConsumptionModeler, AsyncSession, Groups order items by category per month, runs the dietary-change heuristic,…

### Community 32 - "Module 32"
Cohesion: 0.29
Nodes (7): asyncio, Verify ConsumptionModel table can be queried without errors., Verify RestockAlert model columns match actual DB columns., Verify price_history hypertable columns exist., test_consumption_model_readable(), test_price_history_schema(), test_restock_alert_schema()

### Community 33 - "Module 33"
Cohesion: 0.33
Nodes (5): [Grocer — Documentation Alignment & Codebase Cleanup] 2026-08-14, How to Maintain This Journal (For the Agent), Log Entries, Product Journal, [Project — Example Entry] 2026-08-12

### Community 34 - "Module 34"
Cohesion: 0.40
Nodes (3): Central settings object — all values loaded from .env (or env vars in…, Settings, BaseSettings

### Community 35 - "Module 35"
Cohesion: 0.60
Nodes (4): asyncio, test_get_recipes_list(), test_parse_recipe_endpoint(), test_pin_recipe_endpoint()

### Community 36 - "Module 36"
Cohesion: 0.60
Nodes (4): asyncio, test_household_sync_and_get_profile(), test_webhook_form(), test_webhook_json()

### Community 37 - "Module 37"
Cohesion: 0.40
Nodes (3): cambo, metadata, outfit

### Community 38 - "Module 38"
Cohesion: 0.60
Nodes (4): clear_alerts_in_db(), main(), Clear restock alerts to bypass the 24-hour alert rate limiter., run_scenario()

### Community 39 - "Module 39"
Cohesion: 0.50
Nodes (4): get_orders(), AsyncSession, get, Return the last N orders for a user, newest first. Reads from the PostgreSQL…

### Community 40 - "Module 40"
Cohesion: 0.50
Nodes (4): health(), get, Health check — also reports scheduler job count., root()

### Community 41 - "Module 41"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

## Knowledge Gaps
- **203 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+198 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Household` connect `Module 5` to `Module 3`, `Module 4`, `Module 9`, `Module 12`, `Module 13`, `Module 14`, `Module 20`, `Module 29`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `GrocerMCPClient` connect `Module 4` to `Module 5`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `init_db()` connect `Module 29` to `Module 16`, `Module 13`, `Module 4`, `Module 5`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `build_restock_graph()` (e.g. with `build_cart()` and `generate_alert_message()`) actually correct?**
  _`build_restock_graph()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `semi`, `singleQuote`, `jsxSingleQuote` to the rest of the system?**
  _203 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Module 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08416389811738649 - nodes in this community are weakly interconnected._
- **Should `Module 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08097165991902834 - nodes in this community are weakly interconnected._