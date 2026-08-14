# Graph Report - PreFill  (2026-08-14)

## Corpus Check
- 105 files · ~15,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 741 nodes · 1087 edges · 59 communities (53 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.54)
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
- Module 40
- Module 41
- Module 42
- Module 44
- Module 45
- Module 46

## God Nodes (most connected - your core abstractions)
1. `Household` - 23 edges
2. `compilerOptions` - 16 edges
3. `ConsumptionModel` - 14 edges
4. `ConsumptionModeler` - 14 edges
5. `build_restock_graph()` - 13 edges
6. `init_db()` - 13 edges
7. `GROCER — Engineering Prototype & Problem Exploration` - 12 edges
8. `GrocerMCPClient` - 12 edges
9. `whatsapp_webhook()` - 12 edges
10. `ARCHITECTURE.md — Product Strategy & User Experience Architecture` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `init_db()`  [EXTRACTED]
  scratch/init_timescale.py → backend/database/connection.py
- `RecipeState` --uses--> `ConsumptionModel`  [INFERRED]
  backend/agents/recipe_agent.py → backend/database/models.py
- `RecipeState` --uses--> `Household`  [INFERRED]
  backend/agents/recipe_agent.py → backend/database/models.py
- `ParsedIngredient` --uses--> `ConsumptionModel`  [INFERRED]
  backend/agents/recipe_agent.py → backend/database/models.py
- `ParsedIngredient` --uses--> `Household`  [INFERRED]
  backend/agents/recipe_agent.py → backend/database/models.py

## Import Cycles
- None detected.

## Communities (59 total, 6 thin omitted)

### Community 0 - "Module 0"
Cohesion: 0.05
Nodes (44): get_price_alerts(), get_price_feed(), AsyncSession, get, Prices API — Task 3.5 (frontend hydration) Exposes commodity price histories…, Returns only active price alerts (spikes or dips)., Returns the daily price feed for the commodities: Tomato, Oil, Onion, Milk.…, get_checkpointer() (+36 more)

### Community 1 - "Module 1"
Cohesion: 0.04
Nodes (48): axios, clsx, eslint, eslint-config-next, framer-motion, dependencies, axios, clsx (+40 more)

### Community 2 - "Module 2"
Cohesion: 0.07
Nodes (44): PhoneMockup(), PhoneMockupProps, PRICE_SIGNALS, RECIPE_DB, Iphone(), IphoneProps, api, APIHouseholdProfile (+36 more)

### Community 3 - "Module 3"
Cohesion: 0.05
Nodes (20): AsyncClient, Centralized LLM client for agents. Handles provider fallback (Groq -> NVIDIA)…, Central settings object — all values loaded from .env (or env vars in…, Settings, GrocerMCPClient, Grocer MCP Client wrapper — Task 1.4 Centralizes all HTTP interactions with the…, Open the shared connection pool. Call once from the FastAPI lifespan., Fetch complete order history for a user. (+12 more)

### Community 4 - "Module 4"
Cohesion: 0.10
Nodes (32): get_llm(), Returns a configured LangChain Chat model. Prefers Groq (Llama-3-70b), falls…, build_cart(), build_restock_graph(), generate_alert_message(), parse_order_intent(), parse_user_reply(), place_order() (+24 more)

### Community 5 - "Module 5"
Cohesion: 0.11
Nodes (18): GrocerAppPreview(), GrocerFAQ(), GrocerFooter(), GrocerHeader(), GrocerHero(), GrocerIntegrations(), GrocerValueProp(), GrocerVelocityCalculator() (+10 more)

### Community 6 - "Module 6"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 7 - "Module 7"
Cohesion: 0.18
Nodes (18): Price Intelligence Agent — Task 4.5 Monitors volatile commodity price trends,…, Orders API — returns past order history for a household. Reads directly from…, Base, ConsumptionModel, Household, Order, OrderItem, PriceHistory (+10 more)

### Community 8 - "Module 8"
Cohesion: 0.08
Nodes (23): 1. PRODUCT VISION & STRATEGIC PURPOSE, 2. SYSTEM ARCHITECTURE, 2. USER EXPERIENCE & INTERACTION ARCHITECTURE, 3. DATABASE SCHEMA & DATA MODELS, 3. HOW THE USER SEES AND USES THE APP, 4. FRONTEND ARCHITECTURE & DESIGN SYSTEM ("SHADE"), 5. API CONTRACTS & INTEGRATIONS, 6. LANDING PAGE NARRATIVE SHOWCASE (`app/page.tsx`) (+15 more)

### Community 9 - "Module 9"
Cohesion: 0.13
Nodes (21): Any, build_cart_node(), check_pantry_node(), find_pantry_match(), identify_missing_node(), normalize_quantity(), parse_recipe_node(), ParsedIngredient (+13 more)

### Community 10 - "Module 10"
Cohesion: 0.10
Nodes (20): 1. Component Deletions (3 Files), 2. Component Refactoring & Copy Updates (5 Files), 3. Page & Layout Refactoring (2 Files), 4. Backend Systems (100% Retained), Automated Build & Test Verification, Complete Action List, [DELETE] [`GrocerMeasurableValue.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerMeasurableValue.tsx), [DELETE] [`GrocerRoiCalculator.tsx`](file:///d:/PreFill/frontend/components/grocer/GrocerRoiCalculator.tsx) (+12 more)

### Community 11 - "Module 11"
Cohesion: 0.10
Nodes (19): 1. PROJECT IDENTITY, 2. TECH STACK, 3. DEV COMMANDS, 4. ENGINEERING PRINCIPLES, 4b. LOCAL RULES, 5. PROJECT PATTERNS, 6. MISTAKES TO AVOID, 7. SESSION RESUME (+11 more)

### Community 12 - "Module 12"
Cohesion: 0.17
Nodes (18): AsyncSession, Stateful execution wrapper that runs the Recipe Graph from end to end., recipe_to_cart(), _get_household(), get_recipes(), parse_recipe(), pin_recipe(), AsyncSession (+10 more)

### Community 13 - "Module 13"
Cohesion: 0.11
Nodes (18): author, description, keywords, license, name, scripts, dev, dev:backend (+10 more)

### Community 14 - "Module 14"
Cohesion: 0.14
Nodes (8): AnomalyDetector, Single order quantity >2.5x baseline = guests visited. Exclude from model., Category purchase count drops >60% in most recent month vs prior average., Gaps of 5+ days between consecutive orders = likely travel., Consumption Model — Task 2.1 Builds per-item consumption forecasts from…, Scheduler — Task 2.6 Runs background jobs on a cron schedule using APScheduler…, Seed Data Generator — Task 4.6 Generates realistic Grocer order history for an…, datetime

### Community 15 - "Module 15"
Cohesion: 0.14
Nodes (13): ConfidenceScorer, Confidence Scorer — Task 2.2 Scores how reliable a consumption prediction is,…, Calculate prediction confidence for a single item. Args: purchase_dates: List…, Convert a numeric confidence score into a display-friendly label. Used in the…, Gate for whether to include an item in a restock alert. We only alert users on…, asyncio, ML Integration Tests — pytest Run with: pytest backend/tests/test_ml.py -v…, ConfidenceScorer output must always be between 0 and 1. (+5 more)

### Community 16 - "Module 16"
Cohesion: 0.20
Nodes (16): check_depletions_for_household(), get_alert_history(), _get_household_by_user_id(), get_restock_status(), AsyncSession, get, post, Restock Alert API — Task 2.3 Exposes endpoints to: - GET /api/restock/{user_id}… (+8 more)

### Community 17 - "Module 17"
Cohesion: 0.17
Nodes (16): get_household_profile(), get_or_create_household(), AsyncSession, get, post, Get an existing household or create one for this user., Switch the mock data scenario (standard, party, vacation). Clears current db…, Fetch the latest orders from the MCP server and persist new ones to the DB. (+8 more)

### Community 18 - "Module 18"
Cohesion: 0.22
Nodes (14): _get_household(), get_predictions(), predictions_index(), AsyncSession, get, Predictions API — Task 3.3 (frontend hydration) Exposes consumption model…, Return all consumption model predictions for a household. Sorted by urgency:…, delete_cached() (+6 more)

### Community 19 - "Module 19"
Cohesion: 0.22
Nodes (14): CartUpdate, get_cart(), get_orders(), lifespan(), place_order(), PlaceOrder, BaseModel, FastAPI (+6 more)

### Community 20 - "Module 20"
Cohesion: 0.13
Nodes (14): 1. Clone & Set Up Virtual Environment, 2. Run Test Suite & Start Backend Server, 3. Start Frontend Development Server, 📌 About the Project, 🏗️ Architecture & File Map, 👨‍💻 Author, 🚀 Features, Karan Wakhare (+6 more)

### Community 21 - "Module 21"
Cohesion: 0.15
Nodes (12): 1. CORE BEHAVIOR, 2. SESSION RITUAL, 3. CODING LOOP (SIMPLIFIED MATT POCOCK WORKFLOW), 4. CORE COMMANDS REFERENCE, 5. TASK → SKILL ROUTER (auto-load on AUDIT), AGENTS.md — Global Rules for Karan Wakhare, Applies to every project. Read first., Full Loop (+4 more)

### Community 22 - "Module 22"
Cohesion: 0.15
Nodes (13): AsyncSession, Core function for the Price Intelligence Agent. 1. Queries current prices of…, track_and_alert_prices(), daily_depletion_check_all(), Run every morning at 07:00 IST (before depletion check). Triggers the Price…, Run every Sunday at 02:00 IST. Re-runs the Prophet consumption model for every…, Run every morning at 08:00 IST. For every household with notifications enabled,…, rebuild_all_models_job() (+5 more)

### Community 23 - "Module 23"
Cohesion: 0.15
Nodes (12): 1. Why We Have the Landing Page & Demo, 2. Why We Have the Mockup iPhone, Agents, AI fills and maintains this via @GRILL. You rarely edit this manually., Business Rules (Never Break), CONTEXT.md — Domain Language, Core Entities & Product Purpose, Database Schema (+4 more)

### Community 24 - "Module 24"
Cohesion: 0.15
Nodes (12): 10. Engineering decisions & design invariants (reference), 1. The problem I noticed, 2. What the prototype does, 3. System architecture, 4. How the prediction model works, 5. How the dark-store integration is mocked, 6. If this were ever pursued for real, how I'd want to validate it, 7. Conceptual integration shape (not a request for access) (+4 more)

### Community 25 - "Module 25"
Cohesion: 0.17
Nodes (11): 1. Executive Summary, 1. Stateful Conversational Agent (LangGraph + PostgreSQL Checkpointer), 2. The Business Moat (LTV & Retention), 2. Time-Series Consumption Forecasting (Facebook Prophet + Interquartile Range Anomaly Filtering), 3. Asynchronous High-Throughput FastAPI Backend, 3. Technical Architecture & Innovation, 4. Zero-Cost Live Prototype Architecture, 5. Contact & Collaboration (+3 more)

### Community 26 - "Module 26"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "Module 27"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 28 - "Module 28"
Cohesion: 0.25
Nodes (9): infer_composition(), AsyncSession, Run `infer_composition` and persist the result to the Household table. Called…, Compare household's observed consumption rates to benchmark profiles. Returns…, update_household_profile(), AsyncSession, post, whatsapp_webhook() (+1 more)

### Community 29 - "Module 29"
Cohesion: 0.22
Nodes (8): 1. Pytest Backend Test Suite, 1. Vendor Pitch Component Deletions (3 Files Purged), 2. Next.js Production Build, 2. UI Component Refactoring (5 Files Reframed), 3. Page & Metadata Stream (2 Files Streamlined), 🛠️ Changes Executed, 🧪 Verification Results, Walkthrough — Grocer Refactoring & Alignment Complete

### Community 30 - "Module 30"
Cohesion: 0.48
Nodes (3): ConsumptionModeler, AsyncSession, Groups order items by category per month, runs the dietary-change heuristic,…

### Community 31 - "Module 31"
Cohesion: 0.29
Nodes (7): asyncio, Verify ConsumptionModel table can be queried without errors., Verify RestockAlert model columns match actual DB columns., Verify price_history hypertable columns exist., test_consumption_model_readable(), test_price_history_schema(), test_restock_alert_schema()

### Community 32 - "Module 32"
Cohesion: 0.33
Nodes (5): [Grocer — Engineering Prototype & Problem Exploration Refactoring] 2026-08-14, How to Maintain This Journal (For the Agent), Log Entries, Product Journal, [Project — Example Entry] 2026-08-12

### Community 33 - "Module 33"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online()

### Community 34 - "Module 34"
Cohesion: 0.40
Nodes (3): cambo, metadata, outfit

### Community 35 - "Module 35"
Cohesion: 0.50
Nodes (4): get_orders(), AsyncSession, get, Return the last N orders for a user, newest first. Reads from the PostgreSQL…

### Community 36 - "Module 36"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

## Knowledge Gaps
- **218 isolated node(s):** `semi`, `singleQuote`, `jsxSingleQuote`, `trailingComma`, `printWidth` (+213 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Household` connect `Module 7` to `Module 3`, `Module 9`, `Module 12`, `Module 14`, `Module 16`, `Module 17`, `Module 18`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `init_db()` connect `Module 0` to `Module 3`, `Module 15`, `Module 22`, `Module 7`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Household` (e.g. with `ParsedIngredient` and `RecipeIngredients`) actually correct?**
  _`Household` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ConsumptionModel` (e.g. with `ParsedIngredient` and `RecipeIngredients`) actually correct?**
  _`ConsumptionModel` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `semi`, `singleQuote`, `jsxSingleQuote` to the rest of the system?**
  _218 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Module 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05389610389610389 - nodes in this community are weakly interconnected._
- **Should `Module 1` be split into smaller, more focused modules?**
  _Cohesion score 0.04081632653061224 - nodes in this community are weakly interconnected._