# AGENTS.md - Grocer

## What this is
WhatsApp consumer grocery concierge with deterministic intent verification, bounded recovery, and full Swiggy Instamart MCP integration.

## Stack
- Frontend: Next.js 16 (App Router) + React 19 + TypeScript 5 + Tailwind CSS v4
- Backend: Python 3.11 + FastAPI + asyncpg + Supabase Postgres
- Hosting: Render (FastAPI) & Vercel (Next.js)

## Commands (how to run/build/test)
- Install: `npm install` and `pip install -r requirements.txt`
- Dev server: `npm run dev` & `uvicorn backend.main:app --reload --port 8000`
- Test: `pytest`
- E2E: `pytest backend/tests/test_whatsapp_postgres_e2e.py`
- Lint: `npm run lint`
- Done check = Test + Lint both exit 0.

## Issue tracker
GitHub Issues (`kwakhare5/Grocer`) via `gh` CLI.

## Design source of truth
UI-style skill for this project: `taste-skill`. Load only this one.
Fonts and colors come from tokens file.

## Gotchas (project decisions)
- WhatsApp webhooks require signature validation and idempotency tokens.
- Fast 50ms Deterministic Action Dispatcher handles WhatsApp buttons (`confirm_order`, `clear_cart`, `check_payment`, `select_address`) directly in Python without LLM overhead.
- Allowed Mocks Only: External 3rd-party billable APIs (Gemini, Meta, Swiggy) mocked at port boundary; zero test skips allowed.
- State transitions enforce strict deterministic state bounds before placing orders.
- Anti-drift: Never build dark-store dashboards, fleet logistics, or generic shopping bots; Grocer is a complete Swiggy Instamart concierge on WhatsApp.
- Strict English Voice: The bot understands customer inputs in any style (including Hinglish and Indian grocery terms), but always responds in strict, natural English only.
- Full Swiggy MCP Suite: Exposes all 20 Swiggy Instamart MCP capabilities (parallel shopping, in-chat address creation/deletion, 1-tap reordering, live GPS rider tracking, coupons, and error reporting).
- Swiggy MCP Boundary: Swiggy Instamart integration is isolated to `backend/integrations/commerce/swiggy_adapter.py`.
- Do not touch: `migrations/`.

## Universal Non-Negotiables & Invariants
1. **Real Data Over Speed**: Never chase speed with hardcoded shortcuts, fake heuristics, or temporary caching. Every catalog search, price, stock check, address, and coupon MUST use live Swiggy MCP data.
2. **Zero Assumptions About Customer Purchases**: Never assume customers only buy milk, bread, or staples. Search the real Swiggy dark-store catalog for whatever item the user asks for.
3. **Zero Assumptions About Geography (Real Address Grounding & In-Chat Creation)**: Never assume customer geography or hardcode specific area names. Delivery is strictly grounded in the customer's real Swiggy address book. If multiple match, present 1-tap quick buttons or list menus. If zero addresses exist or the user wants a new location, let them add and save it directly in chat via text or a WhatsApp GPS location pin (`create_address`).
4. **Customer Advocate Engine (Champion the Wallet)**: Always auto-apply the best valid Swiggy coupon (`list_coupons`). Proactively suggest 1-2 small real staples to cross free-delivery thresholds if it saves net fees. Critical Guardrail: Never apply a coupon if the final grand total increases (e.g. dropping below free-delivery cutoff without adding a staple). Proudly show `Total Saved: ₹...` on receipts.
5. **Sensible Defaults on Vague Requests**: When a request is completely unqualified (e.g., "milk" or "bread"), pick the store's #1 standard staple (500ml toned milk / standard white bread) and provide a 1-tap "Change Items" button. Never substitute specific requests (e.g., "almond milk", "Amul Gold 1L", "gluten-free bread").
6. **1-Tap Mobile UPI Checkout**: Default to clickable `upi://pay` deep links formatted into WhatsApp interactive buttons so users can pay with 1 tap in GPay/PhonePe directly on the same phone, with secondary COD button where supported.
7. **Zero Regex & Zero Keyword Dictionaries for Domain Logic**: Absolutely NO regex word-lists, hardcoded drug lists, symptom dictionaries (`bukhar`, `sirdard`), city arrays, or item name matchers anywhere in business logic. Product safety is governed strictly by Swiggy catalog metadata (`category == "Pharmacy"` / `"Prescription"`). OTC first-aid (Band-Aids, ORS, cotton) is allowed. Conversational symptom nuance is handled by Gemini without keyword interceptors.
8. **Python Muscle vs Gemini Brain**: Gemini handles fuzzy natural language, recipes, and user intent. Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, and checkout gates. The LLM can never place an order or deduct money.
9. **Zero Silent Drops & Radical Truth**: If an item is out of stock or restricted, never quietly omit it. Honestly explain the missing item and offer alternatives. If an error occurs, communicate the exact truth in plain English (e.g., store closed, API temporarily down).
10. **High-Cohesion Architecture**: Code that changes together lives together. No duplicate modules, no obsolete adapters, no 30-file over-fragmentation, and no corrupted line-ending bloat (`\r\r\n`).

Global rules: read C:\Users\kwakh\.agents\AGENTS.md
