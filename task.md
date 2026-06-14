# task.md — Active TODO List
# Agent: update this before ending every session. No exceptions (R5).
# Format: [x] done | [/] in progress | [ ] not started

## 🔴 In Progress
- [ ] Task 3.1: Twilio WhatsApp Sandbox Configuration — Configure Twilio credentials in `.env`, test sandbox join flow.

## 🟡 Up Next
- [ ] Task 3.2: WhatsApp Webhook (`backend/notifications/whatsapp.py`) — Implement `/api/webhook/whatsapp` receiver to parse YES/NO replies and drive restock_agent.
- [ ] Task 3.3: Frontend Real API Hydration — Wire `predictions/page.tsx` and `price-alerts/page.tsx` to live `/api/predictions/{user_id}` and `/api/restock/{user_id}` endpoints.

## 🟢 Done
- [x] Task 0.1-0.3: Project setup — folder structure, Docker TimescaleDB, Python venv + dependencies — [2026-05-16]
- [x] Task 1.1-1.3: Database schema (Alembic migration), SQLAlchemy models, TimescaleDB hypertable for price_history — [2026-05-16]
- [x] Task 1.4-1.6: Mock Swiggy MCP server (port 8001), 100-order seed data generator, sync_service — [2026-05-16]
- [x] Task 1.7: Prophet Consumption Model Builder (`backend/ml/consumption_model.py`) — [2026-05-16]
- [x] Task 1.8: FastAPI main.py + CORS + all routers registered — [2026-05-16]
- [x] Task 2.1: Anomaly Detector (`backend/ml/anomaly_detector.py`) — travel/guest/dietary shift detection — [2026-05-16]
- [x] Task 2.2: Confidence Scorer (`backend/ml/confidence_scorer.py`) — regularity × 0.6 + data × 0.4 — [2026-05-16]
- [x] Task 2.3: Restock Alert API (`backend/api/routes/restock.py`) — depletion check, de-duplication, REST endpoints — [2026-05-16]
- [x] Task 2.4: Household Profiler (`backend/ml/household_profiler.py`) — Euclidean benchmark composition inference — [2026-05-17]
- [x] Task 2.5: LangGraph Restock Agent (`backend/agents/restock_agent.py`) — stateful 4-node conversation graph — [2026-05-17]
- [x] Frontend UI Overhaul — Industrial Utilitarian redesign of all 5 pages with SVG sparklines, depletion bars, dot-grid backgrounds — [2026-05-17]
- [x] Code hygiene: Next.js Link components, JSX apostrophe escaping, requirements.txt lock, package.json scripts — [2026-05-17]
- [x] Task 2.6: APScheduler (`backend/notifications/scheduler.py`) — 3 cron jobs wired into FastAPI lifespan — [2026-05-19]
- [x] Task 2.7: Week 2 Integration Tests — all endpoints verified live against DB and MCP — [2026-05-19]
- [x] Codebase Alignment Sprint — fixed RestockAlert schema mismatch, implemented predictions.py + recipes.py real endpoints, proper pytest tests, .env/.env.example sync, config.py documented — [2026-05-19]

## 🚫 Blocked
- [ ] Real Swiggy API access — Swiggy has no public sandbox. Using Mock MCP (port 8001) for all development.

## 💡 Backlog (post-Week-3)
- [ ] Recipe AI Agent (`backend/agents/recipe_agent.py`) — Claude generates recipes from depleting inventory.
- [ ] Price Intelligence Agent (`backend/agents/price_agent.py`) — alert on price drops >10% from 30-day average.
- [ ] Expand price_history data — currently populated by scheduler; add historical backfill script.
- [ ] Add pytest-asyncio integration test suite for all live endpoints.
