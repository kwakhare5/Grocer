# AGENTS.md - Grocer

## What this is
WhatsApp consumer grocery replenishment assistant with deterministic intent verification, bounded recovery, and Swiggy Instamart integration.

## Stack
- Frontend: Next.js 16 (App Router) + React 19 + TypeScript 5 + Tailwind CSS v4
- Backend: Python 3.11 + FastAPI + asyncpg + Supabase Postgres
- Hosting: Render (FastAPI) & Vercel (Next.js)

## Commands (how to run/build/test)
- Install: `npm install` and `pip install -r requirements.txt`
- Dev server: `npm run dev` & `uvicorn backend.main:app --reload --port 8000`
- Test: `pytest backend/tests/test_whatsapp_postgres_e2e.py`
- E2E: `pytest backend/tests/test_whatsapp_postgres_e2e.py`
- Lint: `npm run lint`
- Done check = Test + Lint both exit 0.

## Issue tracker
GitHub Issues (`kwakhare5/Grocer`) via `gh` CLI. See `docs/agents/issue-tracker.md`.

## Design source of truth
UI-style skill for this project: `taste-skill`. Load only this one.
Fonts and colors come from tokens file.

## Gotchas (project decisions)
- WhatsApp webhooks require signature validation and idempotency tokens.
- Live external LLM calls are disabled by default in test runner (`-m "not live_llm"`).
- State transitions enforce strict deterministic state bounds before placing orders.
- Anti-drift: Never build dark-store dashboards, fleet logistics, or generic shopping bots; Intent is an extension of the WhatsApp agent.
- Autonomy & Safety: Server-side gated checkout with explicit confirmation; deterministic code enforces/verifies, LLM only proposes.
- Swiggy MCP Boundary: Swiggy Instamart integration is isolated to `backend/integrations/commerce/swiggy_adapter.py` (follow https://mcp.swiggy.com/builders/llms.txt).
- Do not touch: `GROCER_V2_MASTER_SPEC.md`, `migrations/`.

Global rules: read C:\Users\kwakh\.agents\AGENTS.md
