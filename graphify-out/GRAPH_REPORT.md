# Graph Report - PreFill  (2026-08-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 591 nodes · 970 edges · 52 communities (49 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `19c50b05`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- hooks.ts
- page.tsx
- restock_agent.py
- conftest.py
- ConsumptionModeler
- compilerOptions
- devDependencies
- Household
- dependencies
- cache.py
- main.py
- recipes.py
- models.py
- package.json
- household.py
- whatsapp.py
- restock.py
- mock_server.py
- datetime
- frontend/.prettierrc.json
- .prettierrc.json
- db
- test_db.py
- init_db
- update_household_profile
- Settings
- test_prices.py
- test_recipes.py
- test_webhook.py
- layout.tsx
- deep_test_suite.py
- get_orders
- health
- eslint.config.mjs
- next.config.ts
- postcss.config.mjs

## God Nodes (most connected - your core abstractions)
1. `Household` - 25 edges
2. `ConsumptionModeler` - 19 edges
3. `compilerOptions` - 16 edges
4. `ConsumptionModel` - 15 edges
5. `build_restock_graph()` - 13 edges
6. `init_db()` - 13 edges
7. `PreFillMCPClient` - 12 edges
8. `whatsapp_webhook()` - 12 edges
9. `Base` - 11 edges
10. `RestockAlert` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `init_db()`  [EXTRACTED]
  scratch/init_timescale.py → backend/database/connection.py
- `RecipeParseRequest` --uses--> `Household`  [INFERRED]
  backend/api/routes/recipes.py → backend/database/models.py
- `RecipePinRequest` --uses--> `Household`  [INFERRED]
  backend/api/routes/recipes.py → backend/database/models.py
- `ConsumptionModeler` --uses--> `Order`  [INFERRED]
  backend/ml/consumption_model.py → backend/database/models.py
- `ConsumptionModeler` --uses--> `OrderItem`  [INFERRED]
  backend/ml/consumption_model.py → backend/database/models.py

## Import Cycles
- None detected.

## Communities (52 total, 3 thin omitted)

### Community 0 - "hooks.ts"
Cohesion: 0.07
Nodes (44): PhoneMockup(), PhoneMockupProps, PRICE_SIGNALS, RECIPE_DB, Iphone(), IphoneProps, api, APIHouseholdProfile (+36 more)

### Community 1 - "page.tsx"
Cohesion: 0.09
Nodes (21): PreFillAppPreview(), PreFillFAQ(), PreFillFooter(), PreFillHeader(), PreFillHero(), PreFillIntegrations(), PreFillMeasurableValue(), PreFillRoiCalculator() (+13 more)

### Community 2 - "restock_agent.py"
Cohesion: 0.10
Nodes (33): get_llm(), Centralized LLM client for agents. Handles provider fallback (Groq -> NVIDIA)…, Returns a configured LangChain Chat model. Prefers Groq (Llama-3-70b), falls…, build_cart(), build_restock_graph(), generate_alert_message(), parse_order_intent(), parse_user_reply() (+25 more)

### Community 3 - "conftest.py"
Cohesion: 0.07
Nodes (15): AsyncClient, PreFillMCPClient, Open the shared connection pool. Call once from the FastAPI lifespan., Fetch complete order history for a user., Search products matching query in the catalog., Update or create cart with standard line items., Place the quick commerce order., cleanup_engine() (+7 more)

### Community 4 - "ConsumptionModeler"
Cohesion: 0.09
Nodes (19): AnomalyDetector, Single order quantity >2.5x baseline = guests visited. Exclude from model., Category purchase count drops >60% in most recent month vs prior average., Gaps of 5+ days between consecutive orders = likely travel., ConfidenceScorer, Calculate prediction confidence for a single item. Args: purchase_dates: List…, Convert a numeric confidence score into a display-friendly label. Used in the…, Gate for whether to include an item in a restock alert. We only alert users on… (+11 more)

### Community 5 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 6 - "devDependencies"
Cohesion: 0.08
Nodes (25): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+17 more)

### Community 7 - "Household"
Cohesion: 0.13
Nodes (23): Any, build_cart_node(), check_pantry_node(), find_pantry_match(), identify_missing_node(), normalize_quantity(), parse_recipe_node(), ParsedIngredient (+15 more)

### Community 8 - "dependencies"
Cohesion: 0.09
Nodes (23): axios, clsx, framer-motion, dependencies, axios, clsx, framer-motion, lucide-react (+15 more)

### Community 9 - "cache.py"
Cohesion: 0.13
Nodes (21): _get_household(), get_predictions(), predictions_index(), AsyncSession, get, Return all consumption model predictions for a household. Sorted by urgency:…, get_price_alerts(), get_price_feed() (+13 more)

### Community 10 - "main.py"
Cohesion: 0.15
Nodes (12): Predictions API — Task 3.3 (frontend hydration) Exposes consumption model…, Prices API — Task 3.5 (frontend hydration) Exposes commodity price histories…, get_checkpointer(), get_db(), lifespan(), FastAPI, Modern FastAPI lifespan handler — replaces deprecated @app.on_event. Startup…, PreFill MCP Client wrapper — Task 1.4 Centralizes all HTTP interactions with… (+4 more)

### Community 11 - "recipes.py"
Cohesion: 0.18
Nodes (18): AsyncSession, Stateful execution wrapper that runs the Recipe Graph from end to end., recipe_to_cart(), _get_household(), get_recipes(), parse_recipe(), pin_recipe(), AsyncSession (+10 more)

### Community 12 - "models.py"
Cohesion: 0.16
Nodes (15): Orders API — returns past order history for a household. Reads directly from…, Base, Order, OrderItem, Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online() (+7 more)

### Community 13 - "package.json"
Cohesion: 0.11
Nodes (18): author, description, keywords, license, name, scripts, dev, dev:backend (+10 more)

### Community 14 - "household.py"
Cohesion: 0.21
Nodes (16): get_household_profile(), get_or_create_household(), AsyncSession, get, post, Get an existing household or create one for this user., Switch the mock data scenario (standard, party, vacation). Clears current db…, Fetch the latest orders from the MCP server and persist new ones to the DB. (+8 more)

### Community 15 - "whatsapp.py"
Cohesion: 0.19
Nodes (13): AsyncSession, Price Intelligence Agent — Task 4.5 Monitors volatile commodity price trends,…, Core function for the Price Intelligence Agent. 1. Queries current prices of…, track_and_alert_prices(), RestockAlert, AsyncSession, post, Sends a WhatsApp message using Twilio API. Falls back to logging if Twilio… (+5 more)

### Community 16 - "restock.py"
Cohesion: 0.23
Nodes (14): check_depletions_for_household(), get_alert_history(), _get_household_by_user_id(), get_restock_status(), AsyncSession, get, post, Restock Alert API — Task 2.3 Exposes endpoints to: - GET /api/restock/{user_id}… (+6 more)

### Community 17 - "mock_server.py"
Cohesion: 0.22
Nodes (14): CartUpdate, get_cart(), get_orders(), lifespan(), place_order(), PlaceOrder, BaseModel, FastAPI (+6 more)

### Community 18 - "datetime"
Cohesion: 0.19
Nodes (5): Confidence Scorer — Task 2.2 Scores how reliable a consumption prediction is,…, Consumption Model — Task 2.1 Builds per-item consumption forecasts from…, Scheduler — Task 2.6 Runs background jobs on a cron schedule using APScheduler…, Seed Data Generator — Task 4.6 Generates realistic PreFill order history for an…, datetime

### Community 19 - "frontend/.prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 20 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 21 - "db"
Cohesion: 0.24
Nodes (10): daily_depletion_check_all(), Run every morning at 07:00 IST (before depletion check). Triggers the Price…, Run every Sunday at 02:00 IST. Re-runs the Prophet consumption model for every…, Register all jobs and start the scheduler. Called once on FastAPI startup., Run every morning at 08:00 IST. For every household with notifications enabled,…, rebuild_all_models_job(), start_scheduler(), track_commodity_prices() (+2 more)

### Community 22 - "test_db.py"
Cohesion: 0.28
Nodes (8): asyncio, DB Integration Tests — pytest Run with: pytest backend/tests/test_db.py -v…, Verify ConsumptionModel table can be queried without errors., Verify RestockAlert model columns match actual DB columns., Verify price_history hypertable columns exist., test_consumption_model_readable(), test_price_history_schema(), test_restock_alert_schema()

### Community 23 - "init_db"
Cohesion: 0.43
Nodes (5): init_db(), PriceHistory, Seed Price History — Task 3.5 Seeds the `price_history` table in TimescaleDB…, seed_prices(), main()

### Community 24 - "update_household_profile"
Cohesion: 0.38
Nodes (6): infer_composition(), AsyncSession, Household Profiler — Task 2.4 Infers household composition…, Run `infer_composition` and persist the result to the Household table. Called…, Compare household's observed consumption rates to benchmark profiles. Returns…, update_household_profile()

### Community 25 - "Settings"
Cohesion: 0.40
Nodes (3): Central settings object — all values loaded from .env (or env vars in…, Settings, BaseSettings

### Community 26 - "test_prices.py"
Cohesion: 0.60
Nodes (4): asyncio, test_get_price_alerts(), test_get_price_feed(), test_price_agent_tracking()

### Community 27 - "test_recipes.py"
Cohesion: 0.60
Nodes (4): asyncio, test_get_recipes_list(), test_parse_recipe_endpoint(), test_pin_recipe_endpoint()

### Community 28 - "test_webhook.py"
Cohesion: 0.60
Nodes (4): asyncio, test_household_sync_and_get_profile(), test_webhook_form(), test_webhook_json()

### Community 29 - "layout.tsx"
Cohesion: 0.40
Nodes (3): cambo, metadata, outfit

### Community 30 - "deep_test_suite.py"
Cohesion: 0.60
Nodes (4): clear_alerts_in_db(), main(), Clear restock alerts to bypass the 24-hour alert rate limiter., run_scenario()

### Community 31 - "get_orders"
Cohesion: 0.50
Nodes (4): get_orders(), AsyncSession, get, Return the last N orders for a user, newest first. Reads from the PostgreSQL…

### Community 32 - "health"
Cohesion: 0.50
Nodes (4): health(), get, Health check — also reports scheduler job count., root()

## Knowledge Gaps
- **108 isolated node(s):** `PhoneMockupProps`, `IphoneProps`, `APIOrder`, `APIRecipe`, `APIRestockAlert` (+103 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Household` connect `Household` to `conftest.py`, `cache.py`, `main.py`, `recipes.py`, `models.py`, `household.py`, `whatsapp.py`, `restock.py`, `datetime`, `update_household_profile`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `PreFillMCPClient` connect `conftest.py` to `main.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `ConsumptionModeler` connect `ConsumptionModeler` to `Household`, `models.py`, `household.py`, `whatsapp.py`, `datetime`, `db`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `Household` (e.g. with `ParsedIngredient` and `RecipeIngredients`) actually correct?**
  _`Household` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `ConsumptionModeler` (e.g. with `ConsumptionModel` and `Order`) actually correct?**
  _`ConsumptionModeler` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `ConsumptionModel` (e.g. with `ParsedIngredient` and `RecipeIngredients`) actually correct?**
  _`ConsumptionModel` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PhoneMockupProps`, `IphoneProps`, `APIOrder` to the rest of the system?**
  _108 weakly-connected nodes found - possible documentation gaps or missing edges._