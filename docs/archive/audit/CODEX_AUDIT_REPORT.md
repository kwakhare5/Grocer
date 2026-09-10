# CODEX Audit Report

> Historical audit report for branch `audit/codex-deep-review` (now merged into `ag/mainline`). Line references identify the `de32abb` baseline unless a later commit is named.

## Executive verdict

The baseline is a functioning single-process demonstration, not a production-safe commerce agent. Its existing 147 tests, lint, and build are green, but several tests encode unsafe behavior and the application can report success for pending or partial commerce outcomes.

The critical risk chain is real in code:

```text
unauthenticated or unsigned input
  -> caller-selected/predictable session
  -> shared live provider credential/cart
  -> replayable confirmation
  -> concurrent non-idempotent checkout
  -> pending/partial/unknown outcome reported as ORDERED
```

No real provider mutation or order was executed during this audit.

## Final verification update — 2026-09-09

The critical baseline chain above has been broken for the supported single-process scope. Physical quantity and product identity are deterministic; confirmation is nonce-bound, expiring, material-state fingerprinted, one-time, and serialized; exact provider payment choices reach checkout; pending/partial/failed/unknown outcomes remain distinct; and checkout uncertainty cannot be retried through the consumed approval.

Latest local evidence:

| Gate | Result |
|---|---|
| Python suite | 302 passed |
| Canonical evaluation | 10/10 passed; 40% evidence-based autonomous recovery |
| Unsafe autonomous recovery mutations | 0 |
| ESLint | passed |
| Next.js build / TypeScript | passed |
| Adversarial matrix | 58 automated, 24 partial, 26 uncovered, 1 not applicable |
| Secret scan | no tracked environment file or hard-coded assignment match |
| Live commerce during audit | none |

The result is substantially safer and reviewable, but it is not a production-readiness claim. Durable identity/state/idempotency, integrated OAuth lifecycle, defensible positive timeout reconciliation, authoritative dietary metadata, complete webhook envelope/size defenses, and approved live lifecycle validation remain explicit blockers.

### Independent merge-blocker remediation

- explicit individual COUNT requests are distinct from PACK_COUNT and convert only through exact provider pack arithmetic;
- every parsed hard dietary constraint fails closed when authoritative provider metadata cannot prove compliance;
- the current provider documentation does not impose the reported ₹1000 Instamart checkout cap, so no stale limit was added;
- every Swiggy saved-address set requires an exact user choice, including a single returned address;
- auth, revoked-session, timeout/network, generic provider failure, and genuine empty results remain distinct;
- multiple live payment options require an exact user choice and a fresh basket-bound confirmation;
- reaching the headless UPI polling cap calls `confirm_order` once, never retries checkout, and preserves unknown outcomes;
- conversational tracking uses `track_order` only with provider-returned coordinates and otherwise reports the structured ETA fallback explicitly;
- supported payment/order/tracking methods are required CommercePort capabilities rather than optional runtime failures.

Provider-contract evidence rechecked on 2026-09-09:

- `https://mcp.swiggy.com/builders/docs/reference/instamart/checkout.md` contains no ₹1000 Instamart restriction. `https://mcp.swiggy.com/builders/llms-full.txt` assigns the ₹1000 cap to Food documentation, so the Instamart gate remains not applicable.
- `https://mcp.swiggy.com/builders/docs/reference/instamart/track_order.md` defines `track_order` as the primary conversational tracking tool and requires trustworthy delivery coordinates.
- `https://mcp.swiggy.com/builders/docs/reference/instamart/get_delivery_status.md` permits structured delivery ETA/status refreshes and says to prefer `track_order` for conversational answers; it does not classify the tool as widget-only. The truthful limited fallback therefore remains valid when coordinates are unavailable.

### Post-review defects corrected

- the orchestrator no longer treats an omitted nonce as the expected nonce;
- an explicit-confirmation flag now defaults closed at the authoritative boundary;
- payment option ID/kind is included in the approval fingerprint and passed through CommercePort unchanged;
- Swiggy alone maps payment selection to intentApp or generateUPIQR and no longer sends the Food-only addressId argument to Instamart payment-options lookup;
- an OrderStateUnknownError remains ORDER_STATE_UNKNOWN instead of becoming FAILED;
- payment-status orderId is retained before confirm_order;
- provider cadence/deadline prevents tight-loop polling;
- UNSUCCESSFUL, UNPAID, and OUT_FOR_DELIVERY cannot be inverted by substring normalization;
- missing order IDs cannot yield ORDER_PLACED;
- child-order states are authoritative over contradictory top-level success, and an unknown child cannot become complete success;
- budget recovery validates exact physical quantity and projected line total before mutating;
- price-increasing automatic recovery now requires explicit authorization in the contract rather than an implicit test assumption;
- non-transient and authentication failures are not retried as transient recovery;
- conversational confirmation now displays the approval-bound items, costs, address, and exact provider payment label;
- the evaluation harness no longer counts its no-recovery happy path as autonomous recovery.

### Intentionally not expanded in final verification

- GrocerOrchestrator was not split solely because of file size.
- Provider-neutral renaming of every legacy paasId/bridge URL storage field was deferred; provider tool arguments remain isolated, while a broader mechanical rename would add review surface without changing current safety.
- Positive checkout-timeout reconciliation remains fail-closed because the documented order-history schema does not expose a defensible checkout/cart correlation key.
- Proactive tracking polling, durable inbox/outbox, and deployment were not started.
- Multi-store children are preserved and aggregated at checkout, but independent post-checkout payment/detail/delivery polling for every child remains deferred.

## Baseline evidence

| Check | Recovered result |
|---|---|
| Branch | `audit/codex-deep-review` |
| Fixed point | `de32abb` / `main` |
| Worktree at recovery | clean |
| Audit commits at recovery | none |
| Python | 147 passed |
| Frontend lint | passed |
| Next.js build | passed |
| Graph | 106 files, 1,675 nodes, no detected import cycle; built from baseline commit |

## Sources inspected

Repository evidence includes:

- root and project `AGENTS.md`, `CONTEXT.md`, `GROCER_V2_MASTER_SPEC.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`;
- all tracked backend modules and tests under `backend/`;
- all application, component, library, and API-route files under `app/`, `components/`, and `lib/`;
- `package.json`, lockfile, Python requirements, Docker files, pytest configuration, environment example, ignore rules, public assets;
- README, current-state, walkthrough, cleanroom, golden-flow, project-history, legacy-architecture, and UI-spec documents;
- Graphify report and dependency/reference searches.

Official Swiggy sources checked and re-checked through 2026-09-09:

- `https://mcp.swiggy.com/builders/llms.txt`
- `https://mcp.swiggy.com/builders/llms-full.txt`
- current Instamart `get_addresses`, `search_products`, `your_go_to_items`, `update_cart`, `get_cart`, `clear_cart`, `get_payment_options`, `checkout`, `check_payment_status`, `confirm_order`, `get_orders`, `get_order_details`, `track_order`, and `get_delivery_status` references;
- current grocery-ordering and UPI recipes, error reference, authentication guide, and production guide.

## Critical and high findings

### A-001 — Explicit physical quantity is not preserved (critical)

- `backend/intent/orchestrator.py:153-169` chooses the cheapest candidate before validating total physical quantity and multiplies requested quantity twice in some cases.
- `backend/intent/recovery.py:548-556` repeats incompatible pack-multiple arithmetic.
- `backend/intent/verifier.py:408-437` compares cart pack count with requested numeric quantity rather than normalized volume/mass/count.
- Reproduced baseline behavior: `12 eggs` selected twelve 6-egg packs; `1.5L milk` selected one 500 ml pack; `2L milk` selected two 500 ml packs.

Decision: introduce one shared, deterministic physical-quantity module and use it in selection, verification, recovery, and approval snapshots.

### A-002 — Product identity is substring-based and unsafe (critical)

- `backend/intent/verifier.py:320-406` and recovery/orchestrator candidate selection use containment rather than structured identity.
- Baseline verifier accepted milk powder and chocolate milkshake for `milk`, and accepted a 500 ml fresh-milk pack for `1 L milk`.
- Provider category/brand metadata exists in commerce models but is not consistently preserved into the cart or used by verification.

Decision: normalize lexical identities, exclude derivative product heads, prefer provider category/brand fields, and clarify rather than cross an uncertain product boundary.

### A-003 — Current explicit brand can silently lose to price (critical)

- `backend/intent/orchestrator.py:144-165` falls back to every candidate when no branded result exists, then chooses the cheapest.
- Reproduced: explicit `Mother Dairy milk` silently selected Amul.

Decision: an explicit item brand is a current-request constraint for autonomous selection. If unavailable, ask or apply only an explicitly allowed substitution policy.

### A-004 — Confirmation is not bound to the displayed basket (critical)

- `backend/intent/session.py:120-153` stores no approval snapshot, fingerprint, nonce, expiry, or consumption state.
- `backend/intent/orchestrator.py:789-829` fetches a fresh cart and checks only whether it still broadly satisfies intent.
- Baseline probe displayed a ₹101 basket, changed the price, and checked out at ₹115 without renewed approval.
- Static action IDs in `backend/channels/base.py:143-170` allow stale buttons to target later states.

Decision: store a canonical material snapshot covering item identity, quantities, normalized physical quantity, prices, all fees/discounts, total, address, payment choice, intent version, expiry, and nonce. Any mismatch requires a new confirmation.

### A-005 — Concurrent confirmation can call checkout twice (critical)

- State is read at `backend/intent/orchestrator.py:778-782` and only becomes terminal after the external call at `:842-846`.
- `OrchestratorSessionStore` returns mutable sessions after a short dictionary lock (`backend/intent/session.py:159-194`); it does not serialize a business transaction.
- The port has no checkout attempt/correlation contract (`backend/integrations/commerce/port.py:65-77`).
- A baseline concurrency probe produced two checkout attempts.

Decision: per-session lock plus atomic one-time approval consumption and durable-ready checkout-attempt state. An unknown outcome locks further checkout pending reconciliation.

### A-006 — Payment pending and partial orders are reported as success (critical)

- `backend/integrations/commerce/swiggy_adapter.py:575-585` can return `PAYMENT_PENDING`.
- `backend/intent/orchestrator.py:842-851` unconditionally writes `ORDERED` and says “Delivering soon.”
- Multi-store child results remain raw dictionaries and default counts imply success (`backend/integrations/commerce/models.py:100-122`).

Decision: model payment selection/pending/confirmed/failed, placed/partial/unknown orders, and child orders. Only a confirmed placed order enters an ordered state.

### A-007 — Official UPI lifecycle is incomplete (critical)

Official flow for headless/WhatsApp operation is payment options -> checkout -> poll `check_payment_status` at provider-returned cadence/cap -> call `confirm_order` only after terminal payment success when not already confirmed. The current port and adapter omit the last two operations.

Decision: add provider-neutral normalized operations without leaking Swiggy schemas upward. Never tight-loop, invent a method, or treat pending payment as ordered.

### A-008 — Live adapter fabricates provider facts (critical)

Baseline Swiggy paths include fallback address/payment/order/status/ETA/location data such as `addr_default`, `SWIGGY-ORDER`, confirmed status defaults, 15-minute ETA, and Mumbai coordinates. Unknown fields become plausible-looking facts.

Decision: all live-path unknowns remain `None`, `UNKNOWN`, or explicit failure. Synthetic values remain only in the mock adapter and are labeled simulated.

### A-009 — Checkout timeout reconciliation can attach the wrong order (critical)

The adapter calls `get_orders` with an unsupported `offset` and accepts the first historical order without matching timestamp, cart, address, items, or total. It can convert an unrelated order into this checkout's success.

Official guidance permits observing orders before a retry after a timeout, but not assuming any recent order is the current attempt.

Decision: use supported parameters and require defensible correlation; otherwise return `ORDER_STATE_UNKNOWN` and prohibit blind retry.

### A-010 — Browser intent API is unauthenticated and subject to IDOR (critical)

- `backend/api/intent_chat.py:77-166` accepts caller-supplied customer/session/address/payment values for chat, choice, confirm, read, and delete.
- `explicit_confirmation=true` is treated as authorization.
- `lib/apiClient.ts` sends no authenticated session capability.

Decision: add opaque session capabilities and ownership enforcement for the demo API; identity must be server-derived in a production deployment.

### A-011 — Live provider identity is shared/disconnected (critical)

- `backend/integrations/commerce/factory.py:19-22` builds one adapter from `SWIGGY_AUTH_TOKEN`.
- Commerce methods after address lookup do not carry customer identity.
- OAuth stores tokens in a separate in-memory vault that the factory does not resolve.
- `backend/api/swiggy_oauth.py:69-83` permits request customer data to override flow ownership.
- `backend/integrations/commerce/swiggy_oauth.py:232` incorrectly uses `SWIGGY_AUTH_TOKEN` as a client-ID override.

Decision: unify on server-side token resolution bound to an authenticated customer. Until durable identity exists, live multi-user mode must fail closed rather than sharing a cart.

### A-012 — WhatsApp webhook validation fails open (critical)

- `backend/channels/whatsapp.py:107-115` returns true when the app secret is missing.
- both Next and backend use a public default verification token.
- `.env.example` claims no variables are required.

Decision: explicit application mode; live mode requires non-default credentials and rejects unsigned traffic. Test mode bypass must be deliberate and isolated.

### A-013 — Deduplication is not durable replay protection (high)

The cache is unlocked, process-local, one-hour, and marks a message before successful dispatch (`backend/channels/whatsapp.py:137-172`). Restart/multi-worker replay and concurrent duplicates remain possible, while a failed dispatch can be permanently suppressed in that process.

Decision: make local processing atomic and truthful now; explicitly defer durable inbox/outbox and multi-worker exactly-once behavior to production persistence work.

### A-014 — Webhook acknowledges lost work (high)

`backend/api/whatsapp.py:58-68` swallows dispatch failures and returns 200; `BaseChannelAdapter.dispatch()` ignores outbound false. This can acknowledge a lost user response or checkout outcome.

Decision: distinguish accepted/processed/delivery-failed states. Do not repeat consequential commerce work merely to resend a message.

### A-015 — Session lifecycle is predictable, stale, and process-local (high)

- `backend/channels/base.py:34-51` creates a ghost empty-key session and repeatedly generates a predictable `_1` ID.
- reset drops only the customer mapping, leaving the terminal session available for reuse.
- session, intent, token, dedup, cart, and order stores are all process-local.

Decision: opaque IDs, complete local cleanup, scoped action tokens, per-session serialization, and candid documentation. Persistence is required before multi-worker production but is not added merely for aesthetics in this mission.

### A-016 — Sensitive data is over-logged/retained (high)

Full phone, inbound text, bot reply, recipient, and provider error bodies are logged or retained in `backend/api/whatsapp.py`, `backend/channels/whatsapp.py`, and intent/session stores. Session GET exposes commerce details without ownership checks.

Decision: hash/redact identities, stop logging raw content, bound test outbox retention, minimize stored raw payloads, and protect session reads.

### A-017 — Tracking models invent certainty (high)

`DeliveryTrackingStatus` requires a narrow known status and integer ETA (`backend/integrations/commerce/models.py:125-136`), while provider fields are optional and may be unavailable. The application has no conversational tracking route and no proactive transition system.

Decision: nullable facts, normalized plus raw status, child-order tracking, read-only queries, and semantic transition events. Production polling/outbox remains deferred until durable infrastructure exists.

### A-018 — Active UI and docs overstate live truth (high)

- the workbench hardcodes UPI/COD, labels baskets verified, and renders checkout success from `ORDERED` regardless of payment/partial state;
- the header claims `Swiggy CommercePort Active` without runtime evidence;
- `CURRENT_STATE.md`, `.agents/AGENTS.md`, `walkthrough.md`, and cleanroom docs make unconditional production/replay/safety claims contradicted by code;
- `docs/UI_AESTHETICS_SPEC.md` contains forbidden dark-store cockpit semantics.

Decision: make UI state backend-derived, archive misleading history/specs, and rewrite active state docs after implementation.

## Maintainability and cleanup findings

- `backend/intent/orchestrator.py` (858 baseline lines) and `backend/intent/recovery.py` (728 lines) mix selection, state transitions, formatting, and policy arithmetic. Extract only shared semantic/state mechanisms justified by fixes.
- duplicate Next/browser OAuth and backend OAuth are disconnected; the browser path is presently unused and misleading.
- Python dependencies for SQLAlchemy, asyncpg, Alembic, aiosqlite, aiofiles, and LangGraph have no active imports; Docker Compose still starts an obsolete Postgres service.
- frontend dependencies `clsx`, `framer-motion`, and `recharts` have no imports.
- `lib/formatters.ts` and `lib/utils.ts` appear unreferenced; several frame/icon/assets require final reference confirmation.
- duplicate pytest configuration exists at root and `backend/`.
- error handling contains broad catches that collapse empty catalog, provider failure, auth failure, and unknown checkout into user-facing generic failure.
- API CORS is wildcard plus credentials, an unsafe and internally inconsistent baseline.

## Disposition ledger

| Area / file | Baseline disposition | Reason |
|---|---|---|
| `GROCER_V2_MASTER_SPEC.md` | KEEP | Product authority remains sound |
| `CONTEXT.md` | MODIFY | Preserve domain model; add audited lifecycle terms/limits |
| `ARCHITECTURE.md` | MODIFY | Document identity, approval, payment/order/tracking, durability boundaries |
| `IMPLEMENTATION_PLAN.md` | MODIFY | Replace completed-phase fiction with actual audit execution/remaining work |
| `README.md`, `CURRENT_STATE.md` | MODIFY | Remove unsafe/live overclaims and document secure setup |
| `docs/UI_AESTHETICS_SPEC.md` | ARCHIVE | Active forbidden dark-store cockpit spec |
| `docs/PHASE_0_AUDIT.md`, `docs/PROJECT_HISTORY.md` | ARCHIVE | Useful historical record but misleading as current architecture |
| `walkthrough.md`, `docs/CLEANROOM_STATUS.md`, `docs/GOLDEN_FLOW.md` | MODIFY or ARCHIVE | Fixed counts/branches and completion claims are stale |
| `backend/intent/models.py` | MODIFY | Explicit quantity/brand and authorization semantics |
| `backend/intent/parser.py` | MODIFY | Quantity/unit/brand parsing and material ambiguity |
| `backend/intent/verifier.py` | MODIFY | Shared physical quantity and safe product identity |
| `backend/intent/recovery.py`, `recovery_loop.py` | MODIFY | Same semantics, bounded mutations, safe candidates |
| `backend/intent/orchestrator.py` | MODIFY | Approval, concurrency, lifecycle, truthfulness, query routing |
| `backend/intent/session.py`, `storage.py` | MODIFY | Approval/attempt state, locks, ownership, cleanup/TTL |
| `backend/integrations/commerce/models.py` | MODIFY | Truthful payment/order/tracking models |
| `backend/integrations/commerce/port.py` | MODIFY | Complete lifecycle and identity/correlation boundary |
| `backend/integrations/commerce/swiggy_adapter.py` | MODIFY | Official schemas, no fabricated defaults, safe reconciliation |
| `backend/integrations/commerce/mock_adapter.py` | MODIFY | Mirror semantics and idempotency while remaining explicitly simulated |
| `backend/integrations/commerce/factory.py` | MODIFY | Coherent token resolution and fail-closed live identity |
| backend OAuth/vault | MODIFY/MERGE | One server authority, correct client ID, ownership, expiry |
| browser/Next OAuth path | DELETE or MERGE | Disconnected duplicate; no current consumer |
| backend intent/WhatsApp APIs | MODIFY | Auth/capability, validation, safe error/log behavior |
| Next WhatsApp route | MODIFY/MERGE | Thin proxy only; eliminate divergent security defaults |
| `lib/apiClient.ts`, workbench/header/types | MODIFY | Backend-derived truthful states and capabilities |
| unused frontend helpers/components/assets | DELETE after reference proof | Dead surface and maintenance noise |
| Python/Node dependencies | MODIFY | Remove packages with no code/config consumer |
| obsolete Postgres Compose service | DELETE/MODIFY | No active database use; misleading runtime |
| tests/evaluation | MODIFY/ADD | Current green suite misses or encodes critical failures |
| `.env.example`, CORS/settings | MODIFY | Secure explicit configuration and runtime modes |

## Deferred production work

These are required before a production or multi-worker claim but are not silently fabricated in this branch:

- durable authenticated user/account mapping;
- encrypted durable OAuth token storage;
- durable inbox/outbox and webhook idempotency across workers/restarts;
- durable checkout-attempt/order correlation records;
- scheduler/worker for provider polling and WhatsApp transition notifications;
- production deployment, observability, retention policy, and incident operations;
- approved live validation of the corrected payment/order/tracking flow.

## Open questions tracked as fail-closed decisions

- Provider responses may omit order-detail/tracking fields or tools may not be rolled out to an account. GROCER will preserve unknown/unavailable, not backfill facts.
- Swiggy checkout exposes no documented client idempotency key. GROCER will serialize locally, consume approval once, reconcile cautiously, and hold unknown outcomes rather than blind retry.
- The repository has no production identity provider. The browser demo will use an opaque session capability; this is not represented as full end-user authentication.
- In-memory persistence can support deterministic tests/single-process demo only. Documentation will say so explicitly.
