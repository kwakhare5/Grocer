# Grocer

> **Conversational Grocery Replenishment Assistant for WhatsApp on Swiggy Instamart**  
> *Single-turn tool calling, deterministic intent verification, bounded recovery, and zero-regex product policy.*

[![Next.js](https://img.shields.io/badge/Next.js-16_App_Router-black?logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-blue?logo=react)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?logo=postgresql)](https://supabase.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-88%20Unit%20%2F%20159%20Total-brightgreen.svg)]()

---

## Table of Contents
- [The Problem Grocer Solves](#the-problem-grocer-solves)
- [The Two Core Pillars](#the-two-core-pillars)
  - [1. Intent Preservation (Multi-Turn Cart Memory)](#1-intent-preservation-multi-turn-cart-memory)
  - [2. On-Demand Replenishment (Instant Staple Restocks)](#2-on-demand-replenishment-instant-staple-restocks)
- [Interactive Demo Flows](#interactive-demo-flows)
- [System Architecture](#system-architecture)
- [The 10 Universal Non-Negotiables](#the-10-universal-non-negotiables)
- [Quickstart (Local Development)](#quickstart-local-development)
- [Interactive Web Simulator](#interactive-web-simulator--conversation-showcase)
- [Testing & Verification (88 Unit / 159 Total Tests)](#testing--verification-88-unit--159-total-tests)
- [Environment Configuration](#environment-configuration)
- [Swiggy Builders Club Reviewer Checklist](#swiggy-builders-club-reviewer-checklist)
- [Code Map](#code-map)
- [Production Deployment](#production-deployment)

---

## The Problem Grocer Solves

Quick commerce is fast for delivery, but agonizingly slow for ordering:

1. **The Cart Amnesia & Fragility Problem**: Natural conversations contain corrections, budget constraints, and substitutions. Typical bots suffer from "cart amnesia"—swapping an item silently deletes previously chosen items or loses track of hard spending limits.
2. **Repetitive Friction**: Households re-order the exact same staples (milk, eggs, bread) week after week. Yet users are forced to manually search, select pack sizes, and assemble repetitive baskets from scratch.

**Grocer solves both problems.** It brings **intent-preserving conversational commerce** directly to WhatsApp, powered by Google Gemini, strict server-side state machines, and deep integration with Swiggy Instamart's Model Context Protocol (MCP) gateway.

---

## The Two Core Pillars

### 1. Intent Preservation (Multi-Turn Cart Memory)
Grocer remembers your shopping intent across multiple turns and corrections without losing previously selected items or budget limits:
* **Meal Decomposition**: Say *"pasta for 4 under ₹800"*, and Grocer breaks the meal down into ingredients, matches dark-store pack sizes, and validates total cost against your budget ceiling.
* **Non-Destructive Amendments**: Say *"swap penne for fusilli and make it 2 packs"*, and Grocer updates only that specific line item while preserving the rest of your cart.
* **Deterministic Variant Selection**: When catalog searches return multiple candidates (e.g. 500ml vs 1L milk), Grocer presents numbered interactive choices (`1A`, `1B`). It writes to your cart only after you explicitly select the variant.
* **Indian Grocery Vocabulary & Quantities**: Interprets everyday Indian grocery terms and household quantities (e.g. *"doodh"*, *"atta"*, *"dahi"*, *"packet"*, *"kilo"*) and maps them to verified English dark-store catalog items.

### 2. On-Demand Replenishment (Instant Staple Restocks)
Grocer enables instant 1-tap re-ordering for household staples:
* **Go-To Items**: Ask *"restock my staples"* or *"what do I usually buy?"*, and Grocer retrieves your verified favorites (`your_go_to_items`) directly from Swiggy Instamart.
* **Customer Advocate Engine**: Automatically hunts and applies the best available Swiggy coupons and suggests low-cost staples to cross free-delivery thresholds if it saves net money.
* **Server-Side Gated Checkout**: Grocer **never** automatically charges a card or places an order without explicit customer confirmation.
* **Full Privacy Control**: Text *"delete my data"* at any time to instantly purge your session state, token vault secrets, and conversation history.

---

## Interactive Demo Flows

### Flow A: Natural Language Recipe with Budget Ceiling
```
User:     "Need ingredients for butter chicken for 4 people under ₹600"
Grocer:   "I've selected ingredients within your ₹600 budget:
           1. Fresh Chicken Breast (500g) — ₹180
           2. Amul Butter (100g) — ₹58
           3. Fresh Cream (250ml) — ₹75
           4. Tomato Puree (200g) — ₹40
           5. Kasuri Methi (50g) — ₹35
           Total: ₹388 (Saved ₹212 under budget)
           Deliver to Home (Sangvi, Pune)? Reply YES to confirm address."

User:     "Yes, but add 2 packets of garlic naan too"
Grocer:   "Updated! Added 2x Garlic Naan (₹130).
           New Total: ₹518 (Still within ₹600 cap).
           Reply CONFIRM to lock basket and generate payment link."
```

### Flow B: On-Demand Staple Restock
```
User:     "Restock my staples: 2 milk, 1 bread, and eggs"
Grocer:   "I've added your staples from Swiggy Instamart:
           1. Amul Taaza Toned Milk (500ml) x2 — ₹68
           2. Whole Wheat Brown Bread (400g) x1 — ₹50
           3. Farm Fresh Eggs (6 pcs) x1 — ₹55
           Subtotal: ₹173 | Delivery: ₹15 | Grand Total: ₹188
           Deliver to Home (Sangvi, Pune)? Tap Confirm Order to checkout."
```

---

## System Architecture

```
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                          WhatsApp Client / Simulator                        │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │ Signed Webhook (HMAC-SHA256)
                                          ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                       FastAPI Webhook & Security Gateway                    │
   │  • X-Hub-Signature-256 cryptographic verification                            │
   │  • Replay attack prevention & message idempotency                            │
   │  • Rapid burst debouncing (absorbs rapid multi-text bursts)                 │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
                                          ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                       Supabase PostgreSQL Message Store                     │
   │  • Durable state staging (inbound_messages, outbound_messages)              │
   │  • Customer token vault (AES-256 encrypted OAuth credentials)               │
   │  • Session state persistence (task_state) & checkout audit (checkout_attempts)│
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
                                          ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                    Agent Engine (Gemini 3.5 Flash)                          │
   │  • Single-turn tool calling session                                         │
   │  • Multi-turn conversational history & pending request memory               │
   │  • Constraint bounds & budget ceiling enforcement                           │
   └──────────────────┬───────────────────────────────────────┬──────────────────┘
                      │                                       │
                      ▼ Catalog & Cart Queries                ▼ Order Checkout Gate
   ┌──────────────────────────────────────┐  ┌───────────────────────────────────┐
   │  Swiggy Instamart Commerce Adapter   │  │   Server-Side Gated Checkout      │
   │  • Live Pune Dark-Store Catalog      │  │  • 5 Hard Checkout Locks          │
   │  • 20-Tool JSON-RPC 2.0 Client       │  │  • 1-Tap Mobile UPI (upi://pay)   │
   │  • Real-time stock, prices, coupons  │  │  • Durable Hold Tracking Lock     │
   └──────────────────────────────────────┘  └───────────────────────────────────┘
```

---

## The 10 Universal Non-Negotiables

1. **Real Data Over Speed**: Every catalog search, price, stock check, address, and coupon MUST use real Swiggy MCP data. Zero hardcoded heuristics.
2. **Zero Assumptions About Customer Purchases**: Search real Swiggy dark-store catalog for whatever item the customer asks for.
3. **Zero Assumptions About Geography (The Sangvi Principle)**: Never assume customers live in famous hubs. Match delivery locations strictly against the user's real saved Swiggy addresses (`session.saved_addresses`).
4. **Customer Advocate Engine (Champion the Wallet)**: Auto-apply the best valid Swiggy coupon. Proactively suggest 1-2 small staples to cross free-delivery thresholds if it saves net fees.
5. **Sensible Defaults on Vague Requests**: On unqualified requests (e.g. "milk"), pick the dark-store #1 staple and provide a 1-tap "Change Items" button. Never substitute specific requests.
6. **1-Tap Mobile UPI Checkout**: Default to clickable `upi://pay` deep links formatted into WhatsApp interactive buttons.
7. **Zero Regex & Zero Keyword Dictionaries for Domain Logic**: Absolutely NO regex word-lists, hardcoded drug lists, symptom dictionaries (`bukhar`, `sirdard`), or city arrays in business logic. Product safety is governed strictly by Swiggy catalog metadata (`category == "Pharmacy"` / `"Prescription"`).
8. **Python Muscle vs Gemini Brain**: Gemini handles fuzzy natural language. Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, and checkout gates.
9. **Zero Silent Drops**: If an item is out of stock or restricted, never quietly omit it. Honestly explain the missing item and offer alternatives.
10. **High-Cohesion Architecture**: Code that changes together lives together. No duplicate modules, no corrupted line endings (`\r\r\n`), and clean file organization.

---

## Quickstart (Local Development)

### 1. Clone the Repository
```powershell
git clone https://github.com/kwakhare5/Grocer.git
cd Grocer
```

### 2. Configure Environment
```powershell
cp .env.example .env
# Fill in GEMINI_API_KEY and DATA_ENCRYPTION_KEY
```

### 3. Install Backend Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies
```powershell
npm install
```

### 5. Run the Verification Suite
```powershell
pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py
npm run lint
```

### 6. Start the Servers
Terminal 1 (FastAPI Backend):
```powershell
uvicorn backend.main:app --reload --port 8000
```
Terminal 2 (Next.js Frontend & Simulator):
```powershell
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser to interact with Grocer via the visual simulator.

---

## Interactive Web Simulator & Conversation Showcase

Grocer provides two ways to inspect and test conversations:
* **Verified Conversation Showcase (Production)**: The live landing page at [grocerr.vercel.app](https://grocerr.vercel.app) showcases 6 verified multi-turn journeys, allowing reviewers to inspect exact customer messages, raw tool executions, and backend safety rules.
* **Interactive Local Simulator (Development)**: When running locally (`npm run dev` with `SIMULATOR_ENABLED=true`), `/simulator` provides a live chat console that signs every message with cryptographic HMAC-SHA256 headers, perfectly mirroring Meta's WhatsApp Cloud API.

---

## Testing & Verification (88 Unit / 159 Total Tests)

Grocer enforces a **zero-cheat invariant testing philosophy**. Tests never mock internal modules or database tables—they mock only external third-party network APIs (Meta and Swiggy).

```powershell
# Run the 88 unit & integration tests (no Postgres required)
pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py

# Run the complete 159-test suite (requires local Postgres container)
pytest
```

### Test Suite Structure (159 Tests Total)

| Suite | Focus | Tests | What It Proves |
|---|---|:---:|---|
| **Layer 1: Swiggy MCP Client** | `test_layer1_swiggy_mcp.py` | 14 | JSON-RPC 2.0 protocol, error taxonomy, dark-store tools, and error reporting |
| **Layer 2: Session & Intent** | `test_layer2_session_intent.py` | 11 | Postgres task state serialization, cart fingerprinting, and address disambiguation |
| **Layer 3: Basket Orchestrator** | `test_layer3_basket_orchestrator.py` | 11 | Candidate variant ranking, batch addition, and Sangvi principle defaults |
| **Layer 4: Checkout Gate** | `test_layer4_checkout_gate.py` | 11 | 5 hard checkout locks, 1-tap mobile UPI links (`upi://pay`), and hold tracking |
| **Customer Advocate Engine** | `test_customer_advocate.py` | 5 | Wallet championship, auto-coupon hunter, and free-delivery suggestions |
| **Deterministic Invariants** | `test_invariants.py` | 26 | Rupee budget ceilings, signature verification, and zero unselected mutations |
| **Order Messages** | `test_order_messages.py` | 7 | Code-driven receipt formatting and button generation |
| **2-Step Clear Cart** | `test_two_step_clear_cart.py` | 3 | Cryptographic 2-step cart clearing |
| **PostgreSQL E2E Battery** | `test_whatsapp_postgres_e2e.py` | 71 | Full multi-turn WhatsApp flows, crash recovery, and signed webhooks |

---

## Environment Configuration

| Variable | Required | Default | Description |
|---|:---:|:---:|---|
| `DATABASE_URL` | Yes (Prod) | - | PostgreSQL connection URL (e.g. Supabase connection pooler) |
| `DATA_ENCRYPTION_KEY` | Yes | - | 32-byte Fernet key for encrypting stored OAuth credentials |
| `GEMINI_API_KEY` | Yes | - | Google AI Studio API key |
| `GEMINI_MODEL` | No | `gemini-3.5-flash` | Primary Gemini model for intent parsing and planning |
| `GEMINI_SMALL_CHECK_MODEL` | No | `gemini-3.5-flash-lite` | Small checks model for confirmation checks and claim verification |
| `GEMINI_FALLBACK_MODEL` | No | `gemini-3-flash-preview` | Fallback model used if the primary model hits transient quotas |
| `COMMERCE_ADAPTER_TYPE` | No | `swiggy` | Adapter implementation (`swiggy` for live MCP, `mock` for offline dev) |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (Prod) | - | Meta WhatsApp Cloud API Phone Number ID |
| `WHATSAPP_ACCESS_TOKEN` | Yes (Prod) | - | Meta System User Graph API access token |
| `WHATSAPP_APP_SECRET` | Yes (Prod) | - | Meta App Secret for validating incoming HMAC-SHA256 signatures |
| `WHATSAPP_VERIFY_TOKEN` | Yes (Prod) | - | Verification token for Meta webhook subscription handshake |
| `SIMULATOR_ENABLED` | No | `true` | Enables the `/api/simulator/chat` endpoint for the web playground |
| `SIMULATOR_ACCESS_TOKEN` | No | - | Secret bearer token required to send simulator turns |

---

## Swiggy Builders Club Reviewer Checklist

For evaluators reviewing the Swiggy Builders Club submission:

- [x] **Swiggy MCP Boundary**: All Swiggy Instamart interactions are strictly isolated in `backend/integrations/commerce/swiggy_adapter.py` following [mcp.swiggy.com/builders/llms.txt](https://mcp.swiggy.com/builders/llms.txt).
- [x] **Zero Drift**: Never builds dark-store dashboards, fleet logistics, or generic bots; Grocer is dedicated exclusively to intent-preserving consumer grocery replenishment.
- [x] **Autonomous Gated Checkout**: Server-side approval gate requires explicit customer confirmation before any order attempt is executed.
- [x] **Privacy Sanitization**: Delivery addresses strip private flat and building numbers down to safe area labels (e.g. `Home (Sangvi, Pune)`).
- [x] **Production Verification**: 88 unit tests and 159 total tests passing 100% green; live endpoints deployed on Render (`/ready`) and Vercel.

---

## Code Map

```
Grocer/
├── backend/
│   ├── agent/                      # Core agent reasoning & conversation orchestration
│   │   ├── engine.py               # Facade for incoming WhatsApp message handling
│   │   ├── react_coordinator.py    # Multi-turn conversational loop & tool execution
│   │   ├── tools.py                # Agent tools: search_products, update_cart, checkout
│   │   ├── customer_advocate.py    # Auto-coupon hunter & wallet champion
│   │   ├── checkout_executor.py    # Physical 5-lock gated checkout gatekeeper
│   │   ├── checkout_attempts.py    # Durable hold reservation tracking
│   │   ├── product_policy.py       # Zero-regex pharmacy metadata safety gate
│   │   ├── approval.py             # SHA-256 cart fingerprinting & dual confirmation
│   │   ├── address_tools.py        # Sangvi principle real address disambiguation
│   │   ├── item_drop_guard.py      # Anti-silent-drop item verification
│   │   ├── formatters.py           # WhatsApp receipt formatting & quick buttons
│   │   └── session.py              # In-memory turn session state
│   ├── api/                        # FastAPI REST & webhook endpoints
│   │   ├── whatsapp.py             # Signed Meta WhatsApp Cloud API webhook receiver
│   │   ├── health.py               # Liveness (/health) and readiness (/ready) checks
│   │   ├── oauth.py                # Swiggy Instamart OAuth token exchange callback
│   │   └── simulator.py            # Signed playground webhook bridge for web UI
│   ├── channels/                   # Channel abstractions & message storage
│   │   ├── whatsapp.py             # Meta Graph API sender with 3-attempt staged delivery
│   │   └── message_store.py        # PostgreSQL message ledger & burst debouncer
│   ├── integrations/commerce/      # Swiggy Instamart integration
│   │   ├── swiggy_adapter.py       # Live MCP client & MockCommerceAdapter
│   │   ├── swiggy_mcp_client.py    # Low-level HTTP/2 JSON-RPC 2.0 client
│   │   ├── catalog_parsers.py      # Swiggy dark-store catalog response parsing
│   │   ├── cart_parsers.py         # Dynamic cart & fee breakdown normalization
│   │   ├── order_parsers.py        # Order creation, status & live delivery tracking
│   │   ├── port.py                 # Abstract CommercePort contract
│   │   └── token_vault.py          # Encrypted customer credential vault
│   └── tests/                      # Verification test battery
│       ├── test_layer1_swiggy_mcp.py # Layer 1 Swiggy MCP client tests
│       ├── test_layer2_session_intent.py # Layer 2 state & intent tests
│       ├── test_layer3_basket_orchestrator.py # Layer 3 basket orchestrator tests
│       ├── test_layer4_checkout_gate.py # Layer 4 checkout gate tests
│       ├── test_customer_advocate.py # Wallet champion & coupon tests
│       ├── test_invariants.py      # Deterministic system invariant tests
│       └── test_whatsapp_postgres_e2e.py # Full integration tests
├── app/                            # Next.js 16 App Router frontend
│   ├── layout.tsx                  # Root layout with Geist font tokens & metadata
│   ├── page.tsx                    # Landing page & embedded simulator entry
│   └── globals.css                 # Tailwind CSS v4 design tokens
├── components/                     # Reusable React 19 UI components
│   ├── landing/                    # Showcase sections, feature cards, and FAQs
│   └── simulator/                  # Interactive WhatsApp playground client
├── docs/                           # Architectural specs & Swiggy submission dossier
│   ├── TARGET_ARCHITECTURE_V1.md  # Target architecture specification
│   ├── SWIGGY_INSTAMART_MCP_SPEC.md # Official 20-tool Swiggy Instamart MCP specification
│   └── database_schema.md         # Encrypted PostgreSQL schema reference
├── .github/workflows/              # Continuous integration pipelines
│   ├── quality.yml                 # Runs full test battery & Next.js lint/build
│   └── keep_warm.yml               # Scheduled health pinger for Render web service
├── render.yaml                     # Render Infrastructure-as-Code blueprint
└── package.json                    # Frontend dependencies & scripts
```

---

## Production Deployment

### Backend (Render Web Service)
Grocer is configured for native deployment on Render via `render.yaml`.
- **Health Check Path**: `/ready`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Live Endpoint**: `https://grocer-backend-qwk4.onrender.com/ready`

### Frontend (Vercel)
The Next.js 16 frontend automatically deploys to Vercel on pushes to `main`.
- **Framework**: Next.js App Router (React 19, TypeScript 5)
- **Live Endpoint**: `https://grocerr.vercel.app`

---

<p align="center">
  Built for the <strong>Swiggy Builders Club</strong> · Intent-Preserving Agentic Commerce
</p>
