# Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent

[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Swiggy Instamart MCP](https://img.shields.io/badge/Swiggy-Instamart%20MCP-FC8019?style=flat)](https://mcp.swiggy.com/builders/llms.txt)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![Tests](https://img.shields.io/badge/Tests-273%20Passed-brightgreen?style=flat)](backend/tests/)

**Grocer** is an English-first WhatsApp grocery agent for Swiggy Instamart. It accepts ordinary human messages, turns them into real Swiggy Instamart grocery carts, and keeps the customer in control of meaningful shopping choices, pack sizes, and budgets.

> **Production Readiness:** The autonomous Gemini ReAct conversation engine (`GroceryAgentEngine`, `SwiggyAgentTools`) with the Ultra-Low Latency & Multi-Turn Self-Healing Overhaul is active and verified live on WhatsApp with Swiggy Instamart MCP. Local regression suite (273 passed in 5.24s), ESLint (0 errors/warnings), and Next.js 16 production build pass 100% green. See [ARCHITECTURE.md](ARCHITECTURE.md) for verified technical specifications.

The agent does not force rigid commands or multi-step clarification forms. It interprets requests with smart defaults, deduces complete multi-item cooking kits, verifies live dark-store inventory, shows the complete itemized basket with delivery fees, and requests explicit confirmation before checkout.

> **Grocer does not just build your cart. It preserves your shopping intent and budget while live commerce state changes.**

## Product boundary

GROCER is an English-first WhatsApp grocery replenishment agent for Swiggy Instamart.
Its job is to help customers order groceries effortlessly from their local dark store directly inside WhatsApp.

GROCER is not an internal warehouse management platform, cross-marketplace price aggregator, or browser-owned cart. It is a focused consumer replenishment assistant that preserves shopping intent across changing live dark-store inventory.

## How shopping works

```text
WhatsApp message (Meta Cloud API)
      ↓ (Instant <200ms Blue Ticks via mark_message_read + HTTP 200 Fast-Ack Proxy)
FastAPI Webhook (/api/whatsapp/webhook)
      ↓ (Per-customer asyncio.Lock concurrency serialization)
Gemini ReAct Agent Engine (gemini-flash-lite-latest + persistent HTTP/2 pooling: ~0.8s)
      ↓ (Automatic self-healing multi-turn history reset on thought-signature errors)
Autonomous Function Calling (Swiggy MCP Tools via asyncio.gather)
  ├── search_products (parallel live dark-store inventory check)
  ├── update_cart (adds items, respects pack sizes, budget & store thresholds)
  ├── get_cart (reads back verified totals & fees)
  ├── get_saved_addresses (resolves user delivery addresses)
  ├── select_delivery_address (switches active delivery destination)
  ├── clear_cart (empties cart when requested)
  ├── checkout (server-side gated, generateUPIQR: True)
  └── track_order (live delivery tracking and ETA)
      ↓
Cart Summary & Grand Total Preview → User WhatsApp Confirmation
      ↓
Server-Side Gated Checkout Tool (generateUPIQR: True)
      ↓
Dynamic UPI Payment Link (upi://pay?...) delivered to WhatsApp
      ↓
Post-Payment Polling Daemon (_poll_payment_status: every 5s for 60s)
      ↓
Proactive WhatsApp Confirmation & Real-Time Rider Tracking
```

The core differentiator is **autonomous conversational resolution + deterministic safety guards**: Gemini deduces complete multi-item shopping lists (e.g. pasta kits, weekly staples) and drives the live dark-store inventory directly, while deterministic Python guards enforce budget caps, server-side checkout authorization, and prevent false success claims on provider errors.

## Proven live example

User:

> *"i wanna make pasta i want grociers uner 1500"*

Grocer:
1. Resolved customer delivery address from saved Swiggy address book.
2. Autonomously deduced all 7 required ingredients (penne pasta, pasta sauce, mozzarella/cheddar cheese, butter, onions, garlic, capsicum).
3. Checked real dark-store stock in parallel via `asyncio.gather`.
4. Added all items into the live Swiggy Instamart cart (`8c64c847`) for ₹506 (well under the ₹1,500 budget limit).
5. Provided complete itemized breakdown and interactive WhatsApp confirmation controls (`[Confirm Order]`, `[Change Items]`).
6. On user confirmation, executed checkout with dynamic UPI QR generation (`generateUPIQR: True`), delivered the clickable UPI payment link, and launched background status polling.

## Customer-protection rules

* Current explicit request beats session choices, confirmed preferences, and defaults.
* A remembered preference may only form a proposed basket; the user approves it before a cart change.
* Every item is resolved against the live catalogue before a provider mutation. Missing or ambiguous essentials stop the planned change.
* Checkout always requires an explicit backend-enforced confirmation (`is_user_confirmed: True`).
* Dynamic UPI QR / intent links ensure the customer completes real payment securely.

## Autonomy model

| Situation | Grocer behavior |
|---|---|
| Safe + deterministic + policy-authorized | Act automatically (smart staple defaults, parallel inventory query, cart update) |
| Meaningfully ambiguous | Ask the user conversationally |
| Financially consequential | Require explicit confirmation before checkout |

Checkout is always explicitly confirmed and backend-enforced.

## Architecture

```text
Meta WhatsApp Cloud API
  ↓ (Instant <200ms mark_message_read + fast-ack proxy on Vercel)
FastAPI Webhook (/api/whatsapp/webhook on Render)
  ↓ (Per-customer asyncio.Lock concurrency serialization)
GroceryAgentEngine (backend/agent/engine.py)
  ├── Context-aware ReAct reasoning loop (Gemini Flash-Lite Latest: ~0.8s generation)
  ├── Persistent HTTP/2 connection pooling with keep-alive across engine & channels
  ├── Automatic self-healing multi-turn history reset (handles Gemini thought-signature 400 errors)
  ├── 6-turn sliding window history pruning & payload compaction
  ├── Concurrent tool execution via asyncio.gather (parallel multi-item search)
  ├── SwiggyAgentTools (backend/agent/tools.py)
  │     ├── search_products (parallel live store catalogue inventory search)
  │     ├── update_cart (adds SKUs, respects stock, budget & store thresholds)
  │     ├── get_cart (reads back verified totals & fees)
  │     ├── get_saved_addresses (resolves user delivery addresses)
  │     ├── select_delivery_address (switches active delivery destination)
  │     ├── clear_cart (empties cart when requested)
  │     ├── checkout (server-side gated, generateUPIQR: True)
  │     └── track_order (live delivery status, driver info, and ETA)
  ├── Deterministic fail-closed guard (blocks false success claims)
  ├── Autonomous post-payment polling daemon (_poll_payment_status)
  └── Interactive quick-reply buttons ([Confirm Order], [Change Items])
  ↓
CommercePort / SwiggyMCPAdapter (backend/integrations/commerce/)
  ↓
Swiggy Instamart Live MCP Gateway (https://mcp.swiggy.com/im)
```

### Important engineering rule

**LLM interprets and proposes. Deterministic backend code enforces and verifies.**

The LLM interprets natural language, resolves recipe kits, and proposes tool calls. Deterministic Python services enforce hard budget constraints, calculate totals, verify cart state, control retries, and gate checkout.

## Failure recovery and deterministic guards

Initial failure classes include:

- unavailable product / out of stock;
- expired customer authentication (`AUTH_EXPIRED`);
- changed pack size;
- budget drift;
- safely retryable transient failure;
- provider payment pending state (`PAYMENT_PENDING`);
- LLM thought-signature historical validation errors (self-healing reset).

The deterministic fail-closed guard (`_ORDER_SUCCESS_PATTERNS`, `_explains_failure`) inspects the LLM response whenever checkout fails or returns `PAYMENT_PENDING`. If the model falsely claims the order was placed or fails to explain provider errors, the deterministic guard overrides the response with an honest explanation and the actual payment link. Under no circumstances is an unverified or failed operation reported as successful.

## Deterministic regression coverage

Grocer's active regression suite exercises provider responses through the same `CommercePort` boundary used by the live route.

Core metrics include:

- intent preservation rate;
- recovery success rate;
- hard-constraint satisfaction;
- human intervention rate;
- unsafe autonomous action rate — target **0**;
- budget deviation;
- commerce/MCP calls per task;
- turn turnaround latency: sub-3.5s target.

## Swiggy Instamart integration

Commerce operations go through the provider-neutral `CommercePort`.

Swiggy-specific MCP calls remain inside `SwiggyMCPAdapter` and `swiggy_client.py`.

Before changing the integration, read the current Swiggy Builders Club documentation and do not invent tool names, arguments, or retry semantics.

### Live Deployment & Builders Club Architecture

GROCER operates across a multi-surface deployment:

- **Frontend on Vercel (`grocerr.vercel.app`)**:
  - Dedicated consumer product landing page (`app/page.tsx`) with plain human copy, strict typography (`font-editorial` headlines, `font-sans` body, `font-mono` tokens), fixed `+91` phone input badge, and WhatsApp mobile conversation preview.
  - Same-origin Next.js API proxy routes (`/api/auth/swiggy/login`, `/api/auth/swiggy/callback`) relaying requests server-side to Render to eliminate browser CORS preflight errors.
  - Official whitelisted redirect URI for Swiggy OAuth 2.1 PKCE.
  - Meta WhatsApp Cloud API fast-ack webhook proxy (`app/api/whatsapp/webhook/route.ts`).
- **Backend on Render (`grocer-backend-qwk4.onrender.com`)**:
  - Hosts FastAPI and the autonomous Gemini ReAct conversation runtime (`GroceryAgentEngine`).
  - Native Python deployment with persistent HTTP/2 pooling, eliminating Docker container overhead.
  - Keep-warm GitHub Actions automation (`keep_warm.yml`) pinging `/health` every 10 minutes to eliminate cold starts.
  - Communicates directly with Swiggy Instamart MCP gateway (`https://mcp.swiggy.com/im`).
  - Connects to private PostgreSQL with AES-GCM encrypted OAuth token storage.
- **WhatsApp Cloud API (`+1 555 663-1707`)**:
  - Instant blue ticks (`mark_message_read`) in <200ms.
  - Delivers native interactive buttons (`Confirm Order`, `Change Items`) before checkout.
  - Delivers clickable UPI payment links (`upi://pay?...`) generated directly by Swiggy Instamart.
- **Review Checkout Guard (`CHECKOUT_MODE=review`)**:
  - Uses real cart and verification behavior while truthfully stopping before a chargeable order. `CHECKOUT_MODE=live` is a deliberate deployment setting after durable state and live-provider verification.

## Safety invariants

1. No checkout without explicit user confirmation (`is_user_confirmed: True`).
2. No provider credentials in frontend code, logs, or committed files.
3. No hard-constraint enforcement that depends only on LLM behavior.
4. No blind retry of consequential operations.
5. No silent hard-constraint violation.
6. No unsupported autonomous refund/remediation claims.
7. Current explicit user instructions override stored memory.
8. Simulated behavior must be labeled as simulated.

## Development

### Prerequisites

- Node.js 20+
- Python 3.12+

### Frontend

```bash
npm install
npm run dev
npm run lint
npm run build
```

### Backend

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pytest backend/tests
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## Release gates

1. Run the private-schema PostgreSQL migration using the exact Supabase session-pooler URL.
2. Verify OAuth token encryption at rest via `DATA_ENCRYPTION_KEY`.
3. Verify real Swiggy review-mode cart, address, payment, and order-status flows.
4. Enable live checkout only after explicit test evidence and review approval.

## Documentation

- `ARCHITECTURE.md` — system boundaries and technical architecture
- `docs/SWIGGY_MCP_API.md` — authoritative Swiggy MCP tool interface and schema contract
- `docs/REVIEWER_WALKTHROUGH.md` — reviewer and evaluator verification walkthrough
- `.agents/AGENTS.md` — operational engineering rules and session logs
- `AGENTS.md` — project engineering contract pointer

## License

MIT © 2026 Grocer Project
