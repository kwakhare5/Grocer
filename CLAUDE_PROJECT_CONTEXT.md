# GROCER — Complete Claude handoff

> Generated: 2026-09-16
> Repository: `kwakhare5/Grocer`
> Branch: `main`
> Latest commit: `d0c3b79`
> Purpose: give a fresh Claude session an evidence-based understanding of the whole project.

## How to use this document

This is a project handoff, not a replacement for reading the source. Treat statements marked **verified** as repository evidence. Treat **target**, **remaining**, and **risk** sections as work that is not yet complete. Inspect actual code before changing the status.

Never copy secrets into chat. The repository contains ignored local environment files (`.env` and `.env.local`) that are intentionally not documented here. The Supabase password was not provided in a usable database connection string, so no database migration has been applied.

## 1. Product identity

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. A customer writes ordinary human messages; Grocer interprets them, asks when a meaningful choice is unclear, proposes a complete basket, obtains approval, uses Swiggy through MCP, reads the result back, and explains the verified outcome.

The project is intended as a serious Swiggy submission, not an operations dashboard or a toy command parser. The landing site explains the product and starts the Swiggy connection. WhatsApp is the shopping interface.

### Product promise

- Human English is the primary input; robotic syntax is not required.
- Ambiguous product, pack, quantity, brand, cancellation, address, payment, or cart ownership meaning is clarified.
- Current explicit text overrides session choices, confirmed preferences, and defaults.
- A remembered preference can create a proposal but can never silently change a provider cart.
- A complete proposed basket is shown and approved before a provider-cart mutation.
- A Swiggy account cart is an external projection, not automatically GROCER state.
- If a provider cart already contains items, the customer must choose Keep, Start fresh, or Cancel.
- Every essential item resolves before mutation. An unavailable or ambiguous essential blocks the whole plan; no unsafe partial update is reported as complete.
- Provider results are read back and verified before success is reported.
- Checkout is a separate backend-enforced explicit confirmation.
- Customer messages are short, structured, understandable English and never raw HTTP/MCP errors.

### Non-goals

Do not bring back the old dark-store operations product, inventory optimization, warehouse/supplier workflows, transfer/reorder/discount tooling, operations maps, generic marketplace aggregation, browser-owned checkout, silent substitutions, or unsupported autonomous refunds.

## 2. Actual request flow today

The currently deployed WhatsApp route is still the legacy path:

```text
Meta WhatsApp webhook
  → Next.js/Vercel proxy: /api/whatsapp/webhook
  → Render FastAPI: /api/whatsapp/webhook
  → WhatsAppChannelAdapter
  → BaseChannelAdapter
  → ConversationInterpreter + ConversationController
  → legacy GrocerOrchestrator
  → CommercePort
  → MockCommerceAdapter or SwiggyMCPAdapter
  → Meta outbound message
```

This path is synchronous and uses in-memory/session or `/tmp` state in several places. It is functional enough to receive replies but is not the permanent reliability architecture.

## 3. Permanent target flow

```text
Meta inbound event
  → signature verification
  → durable inbox / idempotency
  → ordered ShoppingTask application service
  → MessageUnderstanding proposal
  → deterministic task reducer
  → catalogue resolution
  → cart-ownership decision
  → complete basket plan
  → customer approval
  → CommercePort / Swiggy MCP mutation
  → provider read-back + deterministic verifier
  → bounded recovery or customer decision
  → durable outbox
  → Meta outbound message
```

`ShoppingTask.desired_basket` is the authoritative customer intent. The Swiggy cart is only an observed external state that must be bound to a task explicitly and continuously verified.

The LLM interprets and proposes. Deterministic code validates constraints, quantities, catalogue compatibility, arithmetic, state transitions, retries, cart ownership, and checkout authorization.

## 4. Current state

### Verified complete

- Consumer-only product documentation and active architecture rewritten.
- Obsolete documentation archive and generated graph output removed from the tracked product surface.
- Duplicate Python dependency file removed; root `requirements.txt` is used by Render and Docker.
- Typed `ShoppingTask` domain foundation added.
- Deterministic reducer added for safe basket proposals and approval.
- Natural-language operation boundary added for common English changes.
- Catalogue resolver distinguishes exact, ambiguous, and unavailable items.
- Provider-cart adoption guard added.
- PostgreSQL repository boundary and private `grocer_internal` migration added.
- `REPLACE_ITEM` and explicit `START_FRESH_CART` reducer paths added.
- Obsolete `DEMO_MODE` checkout override removed.
- WhatsApp configured-secret sender mapping bug fixed.
- Test-only trace helper moved under `backend/tests/support/`.

### Verified commands

```text
pytest backend/tests  → 397 passed
npm run lint          → passed
npm run build         → passed
```

These prove local regression health only. They do not prove authenticated Meta, Swiggy, or PostgreSQL production readiness.

### Not complete

- The durable ShoppingTask service is not yet the live WhatsApp execution path.
- The PostgreSQL migration has not been applied to Supabase or Render.
- The durable inbox/outbox worker is not wired.
- OAuth tokens, preferences, locks, and idempotency are not all in encrypted durable storage.
- Authenticated replay of real human WhatsApp conversations against the new route is not complete.
- `CHECKOUT_MODE=live` is not authorized.

## 5. Repository map

### Root files

| Path | Responsibility | State |
|---|---|---|
| `package.json` / `package-lock.json` | Next.js, React, Tailwind, ESLint, TypeScript dependencies and scripts | Active |
| `requirements.txt` | Canonical Python/ FastAPI/HTTPX/asyncpg dependencies | Active |
| `render.yaml` | Render web-service build/start/health and secret declarations | Active deployment config |
| `docker-compose.yml` | Local backend container using `backend/Dockerfile` | Active local config |
| `next.config.ts` | Next.js configuration | Active |
| `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `.prettierrc.json` | Frontend tooling | Active |
| `.env.example` | Redacted environment-variable contract | Active documentation |
| `AGENTS.md` | Project engineering contract | Active |
| `.agents/AGENTS.md` | Agent-specific product/session rules | Active |
| `GROCER_V2_MASTER_SPEC.md` | Current product and safety source of truth | Active |
| `ARCHITECTURE.md` | Current target architecture and migration boundary | Active |
| `CONTEXT.md` | Domain vocabulary/invariants | Active |
| `CURRENT_STATE.md` | Verified state and release gates | Active |
| `README.md` | Developer/product/deployment overview | Active |
| `implementation_plan.md` | Current implementation order | Active |
| `task.md` | Delivery checklist | Active |
| `JOURNAL.md` | Chronological project history | Historical record; not architecture authority |
| `CLAUDE_PROJECT_CONTEXT.md` | This fresh-session handoff | New handoff |

Ignored local files/folders include `.env`, `.env.local`, `.venv`, `node_modules`, `.next`, `.pytest_cache`, `.uv-cache*`, `__pycache__`, and `graphify-out`. They are not source and must not be committed.

## 6. Backend map

### Entry point and API

| File | What it does | State |
|---|---|---|
| `backend/main.py` | Creates FastAPI app, CORS, routers, optional asyncpg pool lifecycle | Active; pool is not yet used by WhatsApp route |
| `backend/config.py` | Pydantic settings: adapter, checkout mode, Swiggy, Meta, Gemini, database, encryption config | Active |
| `backend/api/whatsapp.py` | Meta GET verification, POST signature/payload checks, dispatches messages | Active legacy route; must become durable inbox acknowledgement |
| `backend/api/oauth.py` | Server-side Swiggy OAuth login/callback and token-vault storage | Active; token persistence is transitional |
| `backend/api/health.py` | `/api/health` availability response | Active; does not prove DB/provider readiness |
| `backend/api/intent_chat.py` | Browser/session API around legacy orchestrator | Legacy public contract; retire after replacement API exists |
| `backend/api/schemas.py` | Pydantic schemas for legacy intent/session browser API | Legacy API support |

### WhatsApp channel

| File | What it does | State |
|---|---|---|
| `backend/channels/models.py` | Channel type, normalized inbound/outbound message, interactive action models | Active |
| `backend/channels/base.py` | Maps sender to pseudonymous customer, manages legacy active session, delegates interpreter/controller, builds WhatsApp actions | Active legacy bridge; must move active-session state to ShoppingTask repository |
| `backend/channels/whatsapp.py` | Meta payload parsing, HMAC validation, in-memory dedupe/pending delivery, WhatsApp payload formatting and send | Active adapter; transport retained, RAM dedupe/outbox must be replaced |

### New permanent ShoppingTask core

| File | What it does | State |
|---|---|---|
| `backend/intent/task_model.py` | `ShoppingTask`, `TaskState`, `TaskOperation`, desired basket, provider-cart binding, basket plan, understanding models | New permanent foundation |
| `backend/intent/task_reducer.py` | Deterministic no-provider state transitions; preview/approval and safe add/remove/replace/cancel/fresh behavior | New permanent foundation |
| `backend/intent/message_understanding.py` | English operation proposal boundary; rules for keep-only, remove, add, replace, cancel, start fresh | New permanent foundation; current rule extractor still reused |
| `backend/intent/catalog_resolution.py` | Searches provider catalogue and classifies exact/ambiguous/unavailable resolution | New permanent foundation |
| `backend/intent/cart_adoption.py` | Fingerprints observed provider cart and requires explicit Keep/Fresh/Cancel decision | New permanent foundation |
| `backend/intent/task_repository.py` | In-memory test repository, PostgreSQL task/inbox/outbox repository, optimistic versioning, duplicate-event protection, asyncpg pool factory | New foundation; not wired to live route |
| `backend/migrations/001_shopping_task_core.sql` | Private `grocer_internal` schema and task/inbox/outbox tables/indexes/revokes | New; requires exact DB connection to apply |

### Legacy intent and orchestration modules

These are still import-reachable from the live route. They must not be mass-deleted until the new route passes replay and provider gates.

| File/folder | Responsibility |
|---|---|
| `intent/conversation.py` | Gemini/rule classifier into broad `ConversationAction`; controller validates legacy session choices |
| `intent/orchestrator.py` | Legacy main conversation state machine, cart updates, address/payment progression, verification/recovery calls |
| `intent/orchestrator_address.py` | Address discovery/selection and progression |
| `intent/orchestrator_choice.py` | Product/recovery choices and generic change request |
| `intent/orchestrator_confirm.py` | Confirmation snapshot, pre-check, review/live checkout guard |
| `intent/orchestrator_payment.py` | Payment choice handling |
| `intent/orchestrator_tracking.py` | Payment/delivery/order observation |
| `intent/parser.py` | Gemini item extraction and deterministic `RuleBasedExtractor`; currently reused by new language boundary |
| `intent/models.py` | Legacy `IntentContract`, `IntentItem`, constraints, resolved meanings |
| `intent/enums.py` | Legacy intent/policy enum values |
| `intent/validator.py` | Legacy extractor validation and contract construction |
| `intent/semantics.py` | Quantity, pack, identity, and product-head semantics |
| `intent/taxonomies.py` | Units, packaging descriptors, categories, stop words; includes `ltr` normalization |
| `intent/session.py` | Legacy conversation state, confirmation nonce/fingerprint, process/file-backed session store |
| `intent/storage.py` | Legacy intent history/session storage |
| `intent/preferences.py` | Legacy preference cache |
| `intent/stages/` | Legacy item, address, payment, confirmation stage helpers |
| `intent/formatters.py` | Legacy user-facing basket/address/payment/order messages |
| `intent/policy.py` | Legacy hard/soft constraint policy |
| `intent/verifier.py` | Legacy deterministic cart-vs-intent checks |
| `intent/recovery.py` | Legacy recovery domain and failure classification |
| `intent/recovery_loop.py` | Legacy bounded recovery loop |
| `intent/recovery_candidates.py` | Legacy candidate filtering/ranking |
| `intent/recovery_strategies.py` | Legacy concrete recovery strategies |
| `intent/__init__.py` | Re-exports legacy intent public API |

### Commerce integration

| File | What it does | State |
|---|---|---|
| `integrations/commerce/port.py` | Provider-neutral commerce interface | Core boundary; retain |
| `integrations/commerce/models.py` | Products, variants, carts, addresses, payment options, orders | Core models; retain/adapt |
| `integrations/commerce/exceptions.py` | Normalized provider/business/auth/checkout errors | Core boundary; retain |
| `integrations/commerce/factory.py` | Selects mock or Swiggy adapter and token resolver | Active |
| `integrations/commerce/mock_adapter.py` | Deterministic catalogue/cart/order provider and fault injection | Tests/evaluation |
| `integrations/commerce/swiggy_adapter.py` | Swiggy MCP implementation behind CommercePort | Active provider boundary |
| `integrations/commerce/swiggy_client.py` | JSON-RPC/MCP HTTP transport | Active provider transport |
| `integrations/commerce/swiggy_parsers.py` | Swiggy response parsing | Active |
| `integrations/commerce/swiggy_normalizers.py` | Provider payload normalization into canonical models | Active |
| `integrations/commerce/swiggy_oauth.py` | OAuth/PKCE flow and provider token exchange | Active; durable state needed |
| `integrations/commerce/token_vault.py` | Transitional token cache, currently `/tmp`-based | Replace with encrypted PostgreSQL before live checkout |
| `integrations/commerce/__init__.py` | Commerce exports | Active |

### Evaluation and scripts

| File/folder | Responsibility | State |
|---|---|---|
| `evaluation/scenarios.py` | Canonical deterministic failures: unavailable, brand, pack, budget, stale, retry, partial, minimum order | Retain; migrate execution to ShoppingTask |
| `evaluation/harness.py` | Runs scenarios through CommercePort, verifier, policy, recovery and metrics | Retain as reliability subsystem |
| `scripts/swiggy_smoke_test.py` | Real/mock Swiggy addresses, catalogue, cart, payment-option smoke test and OAuth URL helper | Retain for controlled provider verification |
| `tests/conftest.py` | Isolated legacy session/address fixture and HTTP client | Transitional test infrastructure |
| `tests/support/trace.py` | PII-free test trace helper | Test-only |

## 7. Frontend map

| Path | Responsibility | State |
|---|---|---|
| `app/page.tsx` | Consumer landing page and Swiggy connection CTA; no authoritative commerce state | Active |
| `app/layout.tsx` | Metadata/fonts/root layout | Active |
| `app/globals.css` | Global design tokens and layout styling | Active |
| `app/api/_lib/backend.ts` | Server-only backend URL resolver for proxy routes | Active |
| `app/api/auth/swiggy/login/route.ts` | Same-origin proxy to backend OAuth login | Active |
| `app/api/auth/swiggy/callback/route.ts` | Same-origin proxy to backend OAuth callback | Active |
| `app/api/whatsapp/webhook/route.ts` | Same-origin Meta GET verification and POST forward to Render | Active transport proxy |
| `components/navigation/AppGlobalHeader.tsx` | Landing navigation/header | Active |
| `components/ui/GrocerLogo.tsx` | Reusable brand logo | Active |
| `public/logo.svg` | Canonical brand asset | Active |

The frontend must remain a landing/OAuth/presentation surface. It must not implement a second cart, inventory model, checkout authority, or conversation state machine.

## 8. Main known failures and their causes

### `change address` repeats the old confirmation

**Evidence:** The user typed `change address` while `AWAITING_CONFIRMATION`; the response repeated the same bread, address, payment, and total.

**Cause:** The legacy action taxonomy has no dedicated `CHANGE_ADDRESS` operation. The controller only routes `CHANGE_OR_CANCEL` specially when it comes from the `cancel_order` button ID. Free text falls through to generic `orchestrator.handle_turn()`, which reuses `session.address_id` and rebuilds the old confirmation.

**Correct permanent transition:**

```text
AWAITING_CONFIRMATION
→ invalidate old confirmation
→ NEEDS_ADDRESS
→ show saved addresses
→ customer selects address
→ re-check serviceability/prices/cart
→ show new confirmation
→ require new checkout confirmation
```

### “Change Items” is the wrong control for every change

The legacy confirmation formatter exposes a generic `cancel_order` action titled “Change Items”. It does not distinguish address changes, payment changes, item changes, or cancellation. This is a UX and state-model problem, not merely a label problem. The target needs typed actions and context-specific buttons/lists.

### Old unrelated Swiggy items appear

The adapter can read the authenticated account’s active cart while the local orchestrator creates its own local cart identifier. Provider cart ownership is therefore undefined. A previous Vicks/Coke/vegetable item can leak into a new task. The permanent fix is explicit cart adoption plus a complete desired basket and read-back verification.

### Partial updates happen when an essential item fails

The old path resolves and mutates items incrementally. If one item such as `bhindi` cannot be resolved, other items may already have changed. The permanent path resolves the entire plan before any mutation and aborts the plan when an essential item is ambiguous/unavailable.

### Human-language corrections are unreliable

The old system uses several broad actions, Gemini classification, regex item parsing, session flags, and stage-specific fallbacks. “cancel other just have milk and bread” can be treated as literal removal text instead of a keep-only operation. “3 Coke” can be under-specified because pack/container semantics are catalogue-dependent. One schema-bound proposal boundary plus deterministic reducer is required.

### State is not production durable

Active-session maps, webhook dedupe, pending delivery responses, preferences, addresses, OAuth state, and tokens are process-local or `/tmp`-based in the legacy path. Restarts, multiple instances, or webhook retries can lose state or repeat work. PostgreSQL inbox/outbox/task persistence and encrypted token storage are required.

### Webhook work is synchronous

The current POST handler can perform language interpretation, provider calls, and Meta delivery before acknowledging the webhook. A timeout after a provider mutation can cause an uncertain retry. The permanent route must persist the event, acknowledge quickly, process in order, and send from a durable outbox.

## 9. Error-message policy

Customer-facing messages must:

- say what Grocer understood;
- say what is missing or unavailable;
- explain what the customer can choose next;
- use buttons/lists for bounded decisions;
- never expose `404`, stack traces, raw MCP payloads, token errors, or internal exception names;
- never claim an order/cart/payment succeeded without provider verification;
- distinguish “not completed”, “needs your choice”, “review completed”, “payment pending”, and “order confirmed”.

## 10. Security and data rules

- Keep WhatsApp, Swiggy, Gemini, Supabase, and encryption secrets server-side.
- Verify Meta webhook challenge and `x-hub-signature-256`.
- Pseudonymize phone identifiers before commerce/session logs.
- Do not log full addresses, bearer tokens, payment data, or raw private provider payloads.
- Checkout requires backend confirmation, current nonce/fingerprint, and a fresh provider verification.
- The private `grocer_internal` schema is intended not to be exposed through Supabase Data API. The backend should connect with the exact managed Postgres Session Pooler URL and SSL.

## 11. Environment and deployment

### Vercel

The Vercel app is the landing site and same-origin proxy. Important server-side settings:

```text
BACKEND_INTERNAL_URL=<Render backend base URL>
WHATSAPP_VERIFY_TOKEN=<same Meta verification token>
NEXT_PUBLIC_WHATSAPP_NUMBER=<optional presentation number>
```

### Render

`render.yaml` starts:

```text
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Required deployment secret categories include Meta WhatsApp values, Gemini key, Swiggy OAuth client ID, database URL, and encryption key. `CHECKOUT_MODE=review` remains the safe submission default.

### Supabase

The project URL and publishable key were supplied separately, but the Postgres URI still has a password placeholder. The exact Session Pooler URI with password is required before applying `backend/migrations/001_shopping_task_core.sql`. Never place the publishable key or password in this handoff or source code.

## 12. Testing strategy

### Automated local gate

```powershell
$taskUvCache = 'D:\Grocer\.uv-cache-runtime'
$env:UV_CACHE_DIR = $taskUvCache
uv run pytest backend/tests
npm run lint
npm run build
```

### Required durable-core tests

- ordinary English item request;
- vague request using confirmed preferences creates preview only;
- ambiguous pack/container asks instead of choosing;
- `ltr`/volume normalization;
- add one more increments quantity;
- keep-only replaces intended basket in preview;
- replace target item edits preview;
- start-fresh records fresh-cart strategy;
- missing/unavailable essential prevents all mutation;
- duplicate inbound event is ignored;
- stale task version cannot overwrite a newer turn;
- existing provider cart requires Keep/Fresh/Cancel;
- approval is required before synchronization;
- checkout approval is separate from basket approval.

### Real WhatsApp replay matrix

Run these from a fresh permitted Meta test-number chat and save message IDs/screenshots:

```text
hi
1 litre milk and one brown bread
3 Coke
actually only keep milk and bread
add one more bread
replace Coke with Pepsi
change address
change payment to cash on delivery
cancel this change
```

Also test an account with an unrelated existing Swiggy cart, unavailable products, price/budget drift, duplicate webhook delivery, invalid webhook signature, provider timeout, payment pending, and review-mode checkout. A changed basket or address must invalidate the previous confirmation and require a new one.

## 13. Safe cleanup status

### Already removed

- Old documentation archive under `docs/archive/`.
- Generated `graphify-out/` from the product workspace (it may be recreated as ignored analysis output by hooks).
- Duplicate `backend/requirements.txt`.
- Obsolete terminal simulator `backend/scripts/simulate_whatsapp_chat.py`.
- Legacy `DEMO_MODE` checkout bypass.
- Unused `/intent/health` alias.
- Production-tree `backend/intent/trace.py`; helper moved to test support.

### Must remain until durable cutover

Do not delete `backend/api/intent_chat.py`, `backend/api/schemas.py`, `backend/channels/base.py`, `backend/channels/whatsapp.py`, `backend/intent/conversation.py`, `backend/intent/parser.py`, `backend/intent/session.py`, `backend/intent/storage.py`, `backend/intent/preferences.py`, `backend/intent/orchestrator*.py`, `backend/intent/stages/`, `backend/intent/models.py`, `backend/intent/policy.py`, `backend/intent/verifier.py`, `backend/intent/recovery*.py`, or `backend/integrations/commerce/token_vault.py` yet. They are import-reachable from the current WhatsApp or browser API path. Delete them only after the durable route is deployed and replay-tested.

## 14. Recommended next implementation order

1. Add typed operations for address/payment changes and a task application service.
2. Wire `ShoppingTaskRepository` into the WhatsApp webhook with durable inbox/outbox processing.
3. Move OAuth, preference, address, idempotency, and lock state to encrypted PostgreSQL.
4. Build provider-cart synchronization with explicit Keep/Fresh/Cancel and complete-plan atomicity.
5. Add human transcript replay fixtures at the real channel/controller seam.
6. Run MockCommerceAdapter replay, then authenticated Swiggy review-mode replay.
7. Switch the live WhatsApp route to the durable service.
8. Re-run all tests, review logs for redacted data, then delete the legacy runtime in one bounded change.
9. Keep review checkout until Swiggy explicitly authorizes live checkout and evidence supports it.

## 15. Instructions for the next Claude session

- Read this file plus `GROCER_V2_MASTER_SPEC.md`, `CONTEXT.md`, `ARCHITECTURE.md`, and `CURRENT_STATE.md`.
- Do not assume the new core is live merely because its tests pass.
- Do not fix the latest human-language failure with one more isolated regex.
- Build a red-capable regression test at the real channel seam before changing behavior.
- Keep natural-language understanding advisory and deterministic enforcement authoritative.
- Treat address, payment, product, pack, quantity, cart ownership, and checkout as separate typed decisions.
- Preserve `CommercePort`; keep Swiggy-specific behavior in `SwiggyMCPAdapter`.
- Do not delete active legacy modules until the replacement route passes replay and provider gates.
- Separate verified facts, hypotheses, missing evidence, and recommendations in every status report.
- Never include secrets or personal addresses in documentation, logs, prompts, commits, or test fixtures.
