# AGENTS.md - Grocer

Global rules: read C:\Users\kwakh\.agents\AGENTS.md first. This file adds project-specific rules. It can make global limits stricter, never looser. Do not repeat global rules here.

## 1. What this is
- One-line promise: Grocer is Swiggy Instamart on WhatsApp — chat is the front door to shopping, stock/store questions, saved addresses, order history, tracking, coupons, reorders, payments, support, and privacy.
- What is out of scope: Features no Instamart MCP tool can carry out. Live automated checkout during the build (Karan tests and places first real order).

## 2. Stack and commands
- Stack: FastAPI Python 3.12 (backend), Next.js 16 (landing website), Supabase PostgreSQL (`grocer` schema in `postgres` db; tests in `grocer_test`), Groq LLM (`openai/gpt-oss-120b` via `backend/agent/llm.py`), Render (backend free tier), Vercel (website).
- Install: `pip install -r requirements.txt -r requirements-dev.txt` && `npm install`
- Dev server: `uvicorn backend.main:app --reload --port 8000` (backend) / `npm run dev` (frontend)
- Test: `pytest tests/` (or `pytest tests/test_health.py`)
- Build: `npm run build` (Next.js landing)
- Lint / typecheck: `ruff check .` && `npm run lint`
- Database / seed: `python scripts/migrate.py` (migrations in `migrations/`)
- Environment variable names: `DATABASE_URL`, `TEST_DATABASE_URL`, `GROQ_API_KEY`, `SWIGGY_CLIENT_ID`, `SWIGGY_CLIENT_SECRET`, `NEXT_PUBLIC_WHATSAPP_NUMBER`, `LIVE_CHECKOUT_ENABLED`. No secrets or values.

## 3. Project rules
- Data contract: Swiggy OAuth redirect is allowlisted at `https://grocerr.vercel.app/`. MCP endpoint is `https://mcp.swiggy.com/im`.
- Invariants and gotchas:
  - 1 Supabase project: tests use separate `grocer_test` DB and NEVER write real DB.
  - Groq is the only LLM: `openai/gpt-oss-120b` through `backend/agent/llm.py` adapter. No second provider.
  - Real-order capable, live order locked: `LIVE_CHECKOUT_ENABLED=false` by default.
  - ₹1,000 default budget cap.
  - Website number policy: Website renders no phone number. The link comes only from `NEXT_PUBLIC_WHATSAPP_NUMBER`. Never publish Karan's real number.
  - No fake claims: Feature is DONE only with proof command, date, and raw output in `STATUS.md`.
  - Full tool coverage: Every one of the 20 Instamart MCP tools is reachable by chat or gets an honest "not supported" reply.
  - Address writes: One throwaway address on Karan's account may be created and deleted; nothing else touched.
  - No paid hosting: Render stays free tier; pollers reconcile from DB on wake.
  - Python Muscle vs LLM Brain: LLM handles conversation behind provider adapter; never calls Swiggy directly. Python enforces capabilities, safety classes, math, budget caps, cart SHA-256 fingerprints, and 3-lock checkout gate.
  - Physical button tap only (Lock 1): Order placed ONLY if user taps WhatsApp button. Text "yes" never orders.
  - Refresh first, then park: Stored refresh token used on expiry/401.
  - DPDP Compliance & 24h Data Minimization: Customer addresses and order snapshots deleted from DB storage after 24 hours.
  - Unknown never writes: Safety classes (`read`, `basket`, `account`, `money`). Read capability never reaches a write path.
  - Swiggy errors are not data: `success: false` raises `SwiggyToolError` with reason. Never validate as success model.
- Strict types: Strict Pydantic models and TypeScript typing. No `any` or loose casts.
- Never commit secrets, passwords or API keys. Keep them in an untracked `.env` or environment variables.
- (Only with a database) Never modify or delete migrations that have already run (migrations `001` through `010`).
- Security and privacy rules: 24h data minimization. Website stores no phone number; bot sends Swiggy login link only after number messages `connect <code>`.

## 4. UI rules (only for projects with a UI)
- Design source of truth: `DESIGN.md` (WhatsApp product UI and website landing page).
- Follow tokens in `DESIGN.md`. No inline styles.
- Handle loading, empty and error states for every async call.

## 5. Surfaces and verification
- Screen or endpoint map: WhatsApp webhook endpoint, website landing page (`/`, `/privacy`, `/proof`), OAuth connect flow.
- Verification skill path: `python scripts/scorecard_live.py` / `python scripts/eval_router.py`.
- Done check: `pytest tests/` + `ruff check .` exit 0 with pasted raw terminal output. Verification runs logged in `STATUS.md`.

## 6. Project-specific stops
- The phase checklist (Plan -> Scout -> Build -> Review -> Fix -> Verify -> Close) lives in TASKS.md, not here.
- Stops this project adds on top of global limits: Never place a live order (`LIVE_CHECKOUT_ENABLED` stays false). Never alter Karan's real Swiggy account data except the one throwaway test address. Never exceed token rate limits (pace live evaluations at >=25s).

## 7. Folder map
- `backend/`: FastAPI app, agent logic, channels, integrations (`agent/`, `channels/`, `integrations/`).
- `app/`: Next.js landing website and connect UI.
- `migrations/`: Versioned SQL migrations (`001_...` through `010_...`).
- `scripts/`: Operational tools, router evals, scorecard, and migration scripts.
- `tests/`: Pytest suite (unit, integration, and staging tests).

## 8. Open decisions
- Launch checklist and real order verification post-handoff (recorded in `STATUS.md`).

## 9. Do not touch
- Migrations `001_initial_schema.sql` through `010_ledger_read_only.sql` (applied to database).
- Historic tags `legacy-main-2026-10-28` and `legacy-codex-2026-10-28`.

## 10. Doc map
- `STATUS.md`: The single source of current truth.
- `PRD.md`: v1 product target requirements.
- `ARCHITECTURE.md`: Technical architecture and MCP tool map.
- `DESIGN.md`: WhatsApp UI and website design specifications.
- `TASKS.md`: Fix plan and phase status.
- `JOURNAL.md`: Append-only historical log.
- `GLOSSARY.md`: Project terminology.
- `docs/adr/`: Architecture decision records.
