# Grocer — Intent-Preserving WhatsApp Grocery Commerce Agent

[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Swiggy Instamart MCP](https://img.shields.io/badge/Swiggy-Instamart%20MCP-FC8019?style=flat)](https://mcp.swiggy.com/builders/llms.txt)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?style=flat&logo=typescript)](https://www.typescriptlang.org/)

**Grocer** is the existing WhatsApp grocery replenishment assistant, extended with an **intent-preserving commerce layer**.

> **Readiness:** Verified live integration for the Swiggy Builders Club with WhatsApp replenishment, live Swiggy MCP OAuth 2.1 PKCE gateway, deterministic verification, and safe demo-mode checkout gating. See [CURRENT_STATE.md](CURRENT_STATE.md) for verified gates and architectural details.

The idea is simple: a user tells Grocer what outcome they want, the agent builds the basket through Swiggy Instamart, and then keeps checking whether the live commerce state still matches the original intent. When something changes, Grocer recovers automatically when the decision is safe and asks the user when the choice is genuinely ambiguous.

> **Grocer does not just build your cart. It tries to keep the cart faithful to what you actually asked for.**

## Product boundary

This repository contains the **consumer WhatsApp experience** and its quick-commerce integration.

The former dark-store operations system has been split into a separate repository:

- [Dark Store Operator](https://github.com/kwakhare5/Dark-store-operator)

Do not treat dark-store inventory optimization, warehouse operations, supplier workflows, transfer/reorder decisioning, or an operations cockpit as part of Grocer.

## Core loop

```text
WhatsApp request
      ↓
Intent extraction
      ↓
Intent Contract
      ↓
Policy / memory
      ↓
Build cart
      ↓
Verify cart against intent
      ↓
If drift → recover / replan / ask
      ↓
Verify again
      ↓
Explicit checkout confirmation
      ↓
Checkout
      ↓
Outcome verification
```

The product differentiator is the **closed-loop intent → action → verification → recovery cycle**, not a generic shopping chatbot.

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
5. apply the repair automatically when it is clearly safe;
6. ask the user when multiple materially different choices exist;
7. verify the repaired cart again.

## Intent Contract

The user goal is modeled explicitly instead of being left only inside an LLM prompt.

```text
IntentContract
├── goal
├── items
├── hard constraints
├── soft preferences
├── budget
├── quantities / pack sizes
├── brand preferences
├── dietary constraints
├── substitution policy
├── authorization scope
├── confidence / ambiguities
└── version
```

### Precedence

```text
current explicit request
    > session choice
    > stored soft preference
    > default
```

Memory is for convenience. It never silently overrides the current request.

## Autonomy model

| Situation | Grocer behavior |
|---|---|
| Safe + deterministic + policy-authorized | Act automatically |
| Meaningfully ambiguous | Ask the user |
| Financially consequential | Require explicit confirmation |

Checkout is always explicitly confirmed and backend-enforced.

## Architecture

```text
WhatsApp
  ↓
Conversation Agent
  ↓
Intent Parser
  ↓
Intent Contract
  ↓
Policy / Memory
  ↓
GrocerOrchestrator
  ↓
CommercePort
  ├── MockCommerceAdapter
  └── SwiggyMCPAdapter
  ↓
Commerce State
  ↓
Intent Verifier
  ├── PASS → approval / continue
  └── FAIL → Recovery Engine → verify again / ask
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
  - Hosts the FastAPI `GrocerOrchestrator`, deterministic verifier, and recovery loop.
  - Manages `SwiggyTokenVault` with disk-backed JSON persistence surviving container cold starts.
  - Communicates directly with Swiggy Instamart MCP gateway (`https://mcp.swiggy.com/im`).
- **WhatsApp Cloud API (`+1 555 663-1707`)**:
  - Delivers native interactive List Messages for saved address selection and pack-size ambiguity resolution.
  - Requires explicit interactive confirmation buttons before checkout.
- **Demo Safety Guard (`DEMO_MODE`)**:
  - Setting `DEMO_MODE=true` on Render exercises 100% of live catalog search, pack resolution, and cart mutation, while intercepting the final provider checkout call to simulate `ORDER_PLACED` safely without incurring financial charges.

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
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest backend/tests  # 360 tests passing (100% green)
uvicorn backend.main:app --reload --port 8000

```

On macOS/Linux, activate with source .venv/bin/activate.

## Engineering roadmap

The implementation sequence is intentionally narrow:

```text
0. Consumer boundary cleanup
1. Intent Contract
2. Intent extraction
3. Policy + memory
4. Intent verification
5. First recovery scenario
6. End-to-end agent loop
7. Failure simulation
8. Evaluation
9. Live Swiggy hardening
10. Demo hardening
```

Start with one extremely polished recovery scenario before expanding the failure surface.

## Documentation

- `GROCER_V2_MASTER_SPEC.md` — authoritative product and engineering specification
- `CONTEXT.md` — coding-session context and anti-drift rules
- `ARCHITECTURE.md` — system boundaries and data/control flow
- `docs/archive/IMPLEMENTATION_PLAN.md` — historical execution order (archived)
- `CURRENT_STATE.md` — latest evidence, readiness, and deferred limits
- `docs/archive/audit/` — historical deep-audit mission, findings, and coverage ledger
- `.agents/AGENTS.md` — Antigravity/Gemini repository rules
- `AGENTS.md` — general coding-agent contract

## License

MIT © 2026 Karan Wakhare
