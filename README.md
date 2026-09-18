# Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent

[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Swiggy Instamart MCP](https://img.shields.io/badge/Swiggy-Instamart%20MCP-FC8019?style=flat)](https://mcp.swiggy.com/builders/llms.txt)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?style=flat&logo=typescript)](https://www.typescriptlang.org/)

**Grocer** is an English-first WhatsApp grocery agent for Swiggy Instamart. It accepts ordinary human messages, turns them into a safe basket proposal, and keeps the user in control of meaningful shopping choices.

> **Readiness:** The durable task core is under migration. Local tests, lint, and production build pass; live WhatsApp, Swiggy OAuth, durable PostgreSQL, and checkout verification remain release gates. See [CURRENT_STATE.md](CURRENT_STATE.md) for verified evidence and limits.

The agent does not force robotic commands. It understands a message as a **proposal**, validates it against the current task and live catalogue, shows the complete intended basket, and asks for approval before changing the provider cart. It asks when a human decision is genuinely needed—for example, “3 Coke” could mean cans, bottles, or a multipack.

> **Grocer does not just build your cart. It tries to keep the cart faithful to what you actually asked for.**

## Product boundary

This repository contains the **consumer WhatsApp experience** and its quick-commerce integration.

The former dark-store operations system has been split into a separate repository:

- [Dark Store Operator](https://github.com/kwakhare5/Dark-store-operator)

Do not treat dark-store inventory optimization, warehouse operations, supplier workflows, transfer/reorder decisioning, or an operations cockpit as part of Grocer.

## How a shopping task works

```text
WhatsApp message
      ↓
Durable ShoppingTask
      ↓
Natural-language understanding (proposal only)
      ↓
Deterministic state transition + catalogue resolution
      ↓
Full basket preview → user approval
      ↓
Explicit provider-cart decision: keep / start fresh / cancel
      ↓
CommercePort → Swiggy MCP
      ↓
Read back and verify
      ↓
Address / payment / explicit checkout confirmation
      ↓
Checkout and verified outcome
```

The product differentiator is the **closed-loop intent → proposal → approval → action → verification → recovery cycle**, not a generic shopping chatbot.

## Example

User:

> get my weekly groceries under ₹2,000, vegetarian, use my usual brands.

Grocer turns that request into an `IntentContract` containing items, hard constraints, soft preferences, budget, substitution policy, and authorization scope.

Suppose the preferred milk becomes unavailable.

Grocer should:

1. detect that the current cart no longer satisfies the intent;
2. check the user's substitution policy;
3. find valid alternatives;
4. keep hard constraints intact;
5. explain the available repair options;
6. ask the user before a purchase-facing choice changes;
7. verify the repaired cart again.

## Customer-protection rules

* Current explicit request beats session choices, confirmed preferences, and defaults.
* A remembered preference may only form a proposed basket; the user approves it before a cart change.
* A provider account cart is not silently reused or cleared. Grocer asks the user to keep it, start fresh, or cancel.
* Every item is resolved against the live catalogue before a provider mutation. Missing or ambiguous essentials stop the whole planned change.
* Checkout always requires an explicit backend-enforced confirmation.

## Autonomy model

| Situation | Grocer behavior |
|---|---|
| Safe + deterministic + policy-authorized | Act automatically |
| Meaningfully ambiguous | Ask the user |
| Financially consequential | Require explicit confirmation |

Checkout is always explicitly confirmed and backend-enforced.

## Architecture

```text
Meta WhatsApp Cloud API
  ↓
FastAPI webhook → durable inbox
  ↓
ShoppingTask application service
  ├── language proposal
  ├── deterministic reducer
  ├── catalogue resolver
  ├── cart-ownership guard
  └── verifier / recovery policy
  ↓
CommercePort
  ├── MockCommerceAdapter (tests)
  └── SwiggyMCPAdapter (live provider boundary)
  ↓
Durable outbox → Meta WhatsApp Cloud API
```

### Important engineering rule

**LLM interprets and proposes. Deterministic backend code enforces and verifies.**

The LLM can interpret language and propose a substitution. Deterministic services must enforce hard constraints, calculate totals, verify cart state, control retries, and authorize checkout.

## Failure recovery

Initial failure classes include:

- unavailable product;
- unavailable preferred brand;
- changed pack size;
- budget drift;
- stale cart;
- safely retryable transient failure;
- partial cart success;
- repairable basket/minimum-order failure.

Recovery is bounded and ends in one of:

```text
RECOVERED
NEEDS_USER_DECISION
BLOCKED
FAILED
```

A failed or unknown operation must never be reported as success.

## Deterministic evaluation

Grocer includes an internal failure-simulation/evaluation layer so behavior can be measured without pretending simulated failures are live provider behavior.

Core metrics include:

- intent preservation rate;
- recovery success rate;
- hard-constraint satisfaction;
- human intervention rate;
- unnecessary clarification rate;
- unsafe autonomous action rate — target **0**;
- budget deviation;
- recovery attempts;
- commerce/MCP calls per task.

## Swiggy Instamart integration

Commerce operations go through the existing provider-neutral `CommercePort`.

Swiggy-specific MCP calls remain inside `SwiggyMCPAdapter`.

Before changing the integration, read the current Swiggy Builders Club documentation and do not invent tool names, arguments, or retry semantics.

### Live Deployment & Builders Club Architecture

GROCER operates across a multi-surface deployment:

- **Frontend on Vercel (`grocerr.vercel.app`)**:
  - Dedicated consumer product landing page (`app/page.tsx`) with plain human copy, strict typography (`font-editorial` headlines, `font-sans` body, `font-mono` tokens), fixed `+91` phone input badge, and WhatsApp mobile conversation preview.
  - Same-origin Next.js API proxy routes (`/api/auth/swiggy/login`, `/api/auth/swiggy/callback`) relaying requests server-side to Render to eliminate browser CORS preflight errors.
  - Official whitelisted redirect URI for Swiggy OAuth 2.1 PKCE.
  - Meta WhatsApp Cloud API webhook handler (`app/api/whatsapp/webhook/route.ts`).
- **Backend on Render**:
  - Hosts FastAPI and the current WhatsApp route. The durable ShoppingTask runtime is implemented but is not yet wired live.
  - Must use managed PostgreSQL and encrypted OAuth-token storage before live checkout.
  - Communicates directly with Swiggy Instamart MCP gateway (`https://mcp.swiggy.com/im`).
- **WhatsApp Cloud API (`+1 555 663-1707`)**:
  - Delivers native interactive List Messages for saved address selection and pack-size ambiguity resolution.
  - Requires explicit interactive confirmation buttons before checkout.
- **Review Checkout Guard (`CHECKOUT_MODE=review`)**:
  - Uses real cart and verification behavior while truthfully stopping before a chargeable order. `CHECKOUT_MODE=live` is a deliberate deployment setting after durable state and live-provider verification.

## Safety invariants

1. No checkout without explicit user confirmation.
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
- Python 3.11+

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
pip install -r requirements.txt -r backend/requirements-dev.txt
pytest backend/tests
uvicorn backend.main:app --reload --port 8000

```

On macOS/Linux, activate with source .venv/bin/activate.

## Release gates

1. Run the private-schema PostgreSQL migration using the exact Supabase session-pooler URL.
2. Wire the durable inbox/outbox worker to the WhatsApp route and replay real human transcripts.
3. Move OAuth tokens, preferences, and task state out of memory and `/tmp` into encrypted durable storage.
4. Verify real Swiggy review-mode cart, address, payment, and order-status flows.
5. Enable live checkout only after explicit test evidence and review approval.

## Documentation

- `GROCER_V2_MASTER_SPEC.md` — authoritative product and engineering specification
- `CONTEXT.md` — coding-session context and anti-drift rules
- `ARCHITECTURE.md` — system boundaries and data/control flow
- `CURRENT_STATE.md` — latest evidence, readiness, and deferred limits
- `docs/RESEARCH_WHATSAPP_INSTAMART_SUBMISSION.md` — official platform constraints used by the submission
- `.agents/AGENTS.md` — Antigravity/Gemini repository rules
- `AGENTS.md` — general coding-agent contract

## License

MIT © 2026 Karan Wakhare
