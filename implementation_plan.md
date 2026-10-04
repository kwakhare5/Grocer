# GROCER implementation plan — intent-safe commerce

> **Current proposed plan (2026-10-04):** [`docs/GROCER_RECOVERY_PLAN_2026-10-04.md`](docs/GROCER_RECOVERY_PLAN_2026-10-04.md). It supersedes conflicting assumptions below. The sections below are historical implementation context; their claims and open decisions are not current release proof.

> **Mumbai backend feasibility proposal:** [`docs/MUMBAI_BACKEND_PLAN_2026-10-04.md`](docs/MUMBAI_BACKEND_PLAN_2026-10-04.md). Preview work awaits approval before a major architecture change.

## 2026-10-03 core-system correction plan — awaiting review

This section supersedes the older provider, variant, and test assumptions below. The goal is a reliable GROCER shopping and replenishment engine verified with bounded real Swiggy MCP traffic. WhatsApp remains the delivery surface and gets a final live transport check; local E2E remains failure-mode regression proof rather than a substitute for real-provider outcomes.

**Current evidence:** revision `9dd3cf1` is live on Render and Vercel; review-only checkout is active; the real WhatsApp basket read returned the correct empty basket. A six-call read-only Charholi session through GROCER's customer-scoped OAuth vault and Swiggy adapter returned real addresses, empty cart, and milk/pizza-base/Bournvita/tissue catalog results. See `docs/REAL_MCP_FINDINGS_2026-10-03.md`. The signed-webhook/PostgreSQL/recorded-Meta E2E suite passes 29 cases, including a 429 stop-and-wait regression. No real cart mutation or paid order was attempted.

### Decision gate 1 — Swiggy-originated data and external models

Swiggy's current data rules require a signed DPA and cross-border safeguards if our platform processes MCP responses outside India. The configured backend and database are in Singapore; Groq says retained customer data is stored in the US. No signed Swiggy DPA, regional inference guarantee, or approval for exporting this customer's saved-address/cart data to Groq has been verified. Automatic approval review blocked the proposed live model turn on this basis. Do not retry it indirectly.

Resolve the actual contract and region before continuing model-driven live customer tests. Preferred permanent design if no cross-border agreement exists: host Swiggy-token storage and response processing in India; pass only the customer's own utterance and a minimal, non-Swiggy-derived task vocabulary to the model; select variants, budget, cart, receipt, and error behavior in application code without sending MCP payloads, address text, cart lines, or order history to an external LLM. Keep the model as an intent proposal engine, with server-side validation and bounded recovery. A provider with contractual India-only processing is an alternative only after its region and Swiggy terms are verified. Record the decision and migration path before changing production data location.

### Decision gate 2 — variant-safe cart flow

Swiggy's `search_products` reference explicitly requires showing available variants and asking which exact variant the customer wants before `update_cart`. The current `quick_add_items` path silently takes the first matching result and can make one write per item under a budget. Replace this with a durable two-stage flow: search and assemble a complete proposed basket; show exact brand, pack size, quantity, live price, unavailable items, and scoped/whole-basket budget; let the customer approve or edit the grouped variant choices; then issue one bounded cart update and verify the provider cart and payable total. Preserve the proposal across retry/restart and invalidate it if catalog or cart state changes. A customer who named an exact variant may have already made that choice, but still show the whole basket before checkout.

### Verification and rollout

1. Use only the local isolated PostgreSQL database for adversarial E2E fault injection. Run low/medium/high human requests, corrections, pack ambiguity, unavailable products, provider 429/auth/timeout, restart recovery, budget edges, external cart edits, and consented replenishment through the actual engine and state store. Keep test artifacts and call counts.
2. Use one chosen real customer account at Charholi for paced, capped real MCP scenarios. Read addresses once per session; count all calls; stop on 429, auth failure, unknown write outcome, or unexpected cart state. Do not place an order. A real add → get_cart → clear → get_cart cycle begins only after the customer chooses a live variant.
3. For model-driven real scenarios, first satisfy decision gate 1. Save sanitized transcripts and provider-state assertions; do not claim 100% correctness from a finite set. Compare requested-item ledger with the observed cart after every mutation.
4. Migrate material legacy unit-test behavior into full-path E2E, remove the obsolete unit suite and duplicate code only after coverage is retained, run lint/build/E2E with exit code 0, then deploy and verify the exact revision on Render/Vercel and one real WhatsApp round trip.
5. Keep paid checkout disabled until its separate Swiggy contract, payment reconciliation, regional data handling, and authorized real-order gate are complete. Reminder sending remains gated until a Meta-approved proactive template exists.

**Open user decisions:** whether a signed Swiggy DPA/cross-border arrangement exists; whether GROCER should proceed with the India-processing/no-MCP-to-external-LLM design if it does not; which exact Charholi product variant to use for one reversible real-cart test.

## 2026-10-03 full-journey recovery and review-only release

The active full-journey audit and prioritized recovery plan is in
[`docs/SYSTEM_AUDIT_AND_RECOVERY_PLAN.md`](docs/SYSTEM_AUDIT_AND_RECOVERY_PLAN.md).
It records the current failing verification baseline, a replay of the customer's
address-selection/model-outage transcript, Swiggy contract conflicts, and the
required signed WhatsApp-to-outbox acceptance gate. The 2026-10-02 plan below
remains historical context; security-boundary and durable-state changes in the
revision await review of the open decisions in the audit plan.

Status: approved and partially implemented locally on 2026-10-02 against baseline HEAD `5476988` and `Grocer-Complete-Plan.md`. The review-only release is not yet verified against the deployed database or real services. See `docs/RELEASE_RUNBOOK.md` for the release gates and `task.md` for open work.

## Objective and release rule

Make a customer's WhatsApp grocery task survive changing catalog, cart, and payment state without crossing another customer's account, spending beyond approval, claiming an unverified result, or losing an acknowledged message. Keep the existing WhatsApp product and `CommercePort`. `CHECKOUT_MODE=review` remains the default; live checkout waits for the release gate below.

The plan covers confirmed defects, operational configuration, and measured quality improvements. A new framework, broad module layout, HTTP/2 switch, or model replacement is not a prerequisite.

## Decisions

Answered in `/grill`:

- Stop checkout on an unknown or changed complete payable total; show a fresh review.
- Migrate verified old customer records; require reconnect for ambiguous identity records.
- Use existing PostgreSQL for durable state with reversible migrations.
- Authorized external verification: read-only Swiggy calls and WhatsApp review flows. No chargeable orders are authorized.
- Hold further checkout attempts while an earlier outcome is unknown.
- Retain completed conversation history for 30 days, with deletion support.
- Automatically choose a close alternative when a requested item is unavailable, subject to hard constraints; disclose the substitution in the basket review.
- Ask which saved address to use at each new order before cart changes when multiple addresses exist.
- Queue incoming WhatsApp messages in order; apply a later correction before basket approval.
- Support Swiggy UPI QR payment first; defer other payment-option flows.
- Keep stable shopping preferences beyond 30 days until the customer changes or deletes them.
- For an ordinary named-brand request, auto-add a close alternative and disclose it before approval; `only this brand` still blocks substitution.
- Block a dietary/allergy substitute when its ingredients or suitability cannot be verified.
- Accept India-only WhatsApp customers with their full verified E.164 number as identity input.
- Every customer connects their own Swiggy account; static owner credentials do not serve other customers.
- Ship a review-only release first. Live checkout is a separate later rollout after the listed gates.
- Resolve every unavailable requested item with the customer before checkout; a missing item cannot silently disappear from the approved basket.
- Ask before adopting changes made directly in the Swiggy cart.

Explicit `only` brands, allergies, and dietary exclusions remain hard constraints unless the customer changes them.

## Domain invariants

- **ShoppingTask:** one authoritative customer task/version with request, constraints, unresolved items, selected address, and cart ownership. No mirrored mutable dictionaries.
- **VerifiedCart:** provider-observed item IDs, quantities, destination, currency, bill lines, payable total, and observation time/version. Missing data is unknown, never zero.
- **PendingApproval:** exact customer, task version, cart fingerprint, address, payable amount/currency, and expiry shown to the customer. Any mutation or drift invalidates it. A button alone is not permission.
- **CheckoutAttempt:** durable record created before a consequential provider call. Preserve `IN_FLIGHT`, `REVIEW_COMPLETE`, `PAYMENT_PENDING`, `PLACED`, `PARTIAL`, `FAILED`, and `UNKNOWN`. Do not assume remote exactly-once behavior.
- **InboundMessage/OutboundMessage:** durable idempotent intake and delivery. Retrying delivery must not repeat shopping actions.
- Current explicit request overrides stored soft preference. Hard exclusions and known budgets are enforced by code. Unknown account, amount, write outcome, or approval blocks checkout.

## Phase 0 — baseline and red failure cases

1. Record HEAD, deployment SHA, configuration shape, and current test mode without copying secrets. Refresh the stale graph after code changes; graph structure is navigation, not behavioral proof.
2. Enumerate failures before coding: mixed edit+confirm, stale button, changed/unknown total, two customers, duplicate/simultaneous webhook, provider timeout after mutation, restart during checkout/payment, failed or partial Meta send, reduced item quantity, failed address migration, long receipt, old numbered choice, and external cart drift.
3. Add focused failing workflow/contract assertions before each production patch. Run the real local app and database where possible; fake only Meta, LLM, and Swiggy boundaries. Preserve independent provider-response fixtures. Label existing canned-model and prompt-string checks as synthetic.
4. Make ordinary tests write evidence to temporary or opt-in output so they do not overwrite tracked E2E reports.

Exit: each targeted defect has a reproducible failing assertion and a recorded baseline. Never weaken an assertion to fit the implementation.

## Phase 1 — fail closed in the current process

1. **Approval:** accept short whole-message confirmation only in `AWAITING_CONFIRMATION`. Treat mixed edits/questions as proposals. Bind approval to a fresh cart, amount, currency, address, customer, task version, and expiry. Ignore model-supplied `is_user_confirmed` as authority. Re-read before checkout; invalidate on drift. Expose checkout only when approval is valid.
2. **Money:** parse quantity units, per-item cap, and total cap separately with evidence and scope. Use provider bill-line truth and `Decimal` or integer minor units; do not invent fee labels. Unknown, invalid, stale, or currency-mismatched totals block review/checkout. Budget read failures fail closed. Reset order-scoped caps on a new task.
3. **Writes and cart fidelity:** parallelize independent reads only. Queue customer messages in order and apply corrections before approval. Serialize cart/address changes and checkout under one task/version. Compare requested vs provider-returned SKUs/quantities, including reduced or omitted items. Do not claim a full basket from a generic success flag.
4. **Outcomes:** preserve unknown, partial, payment-pending, and simulated status from adapter through response. Unknown checkout blocks another attempt until reconciliation. Review response explicitly says no order was placed. Never assure no charge after an uncertain timeout.
5. **Other actions:** verify clear-cart and address migration before changing local state or receipt destination. Select an address by exact ID/label or one unique grounded match; ask when several addresses match. Separate pause, cart clear, pending-payment stop, and unsupported placed-order cancellation. Never offer Confirm for an empty/unresolved basket.
6. **Receipt:** retain full provider items/fees/address. Split text into <=4,096-character chunks; send approval summary and buttons only after required text parts succeed.
7. **Immediate credential containment:** remove unscoped/global token fallback and cross-customer OAuth aliasing. Use per-customer OAuth in production; confine any static owner token to local development fixtures. Disable tracked bootstrap token loading; inspect its provenance privately before deciding rotation.

Exit: tests prove no unreviewed checkout, cross-customer token use, invented total, conflicting write, false success, or truncated approval receipt. Review mode still makes zero provider checkout calls.

## Phase 2 — verified identity, OAuth, and schema

1. Validate India-only full E.164 WhatsApp identity. Migrate verified last-ten-digit IDs; quarantine collisions for reconnect rather than merging accounts.
2. Issue single-use expiring connect links from a verified WhatsApp sender. Bind OAuth state/callback to that identity. Remove typed-phone ownership assumptions, global token publication, and production token-sync admin reliance on the WhatsApp app secret. Escape fixed HTML errors, use the configured WhatsApp number in reconnect UI, redact token-related logs, restrict credentialed CORS, and rate-limit public connect/sync entry points.
3. Read the deployed PostgreSQL schema and make a backup before migration. Add reversible, checked migrations for existing `grocer_internal.oauth_tokens` and `oauth_pending_flows` plus task, inbox, outbox, attempt, and preference tables. Test fresh install, migration of verified records, rollback, encryption, expiration, reconnect, deletion, and two-customer isolation. Retain completed history 30 days; retain preferences until changed/deleted.
4. Separate liveness from readiness. Readiness checks required DB/schema, model key, encryption key, ingress/delivery settings, and commerce mode; include release SHA without secrets. Remove production `mock_key` calls and make `AI_PROVIDER` control provider order.

Exit: a customer connects only their own account; stale/wrong links fail; migration and rollback work; missing dependencies are visible in readiness.

## Phase 3 — durable message and order lifecycle

1. Verify Meta signature, persist each inbound message ID/body once, then acknowledge. The Vercel proxy propagates forwarding failure unless intake was durable. Process-local reservations remain an optimization only.
2. Process durable inbox records in order with per-customer database coordination/version checks. Apply later corrections before approval. Avoid holding a transaction across LLM/provider calls. Persist task state, constraints, pending stable choice IDs, cart observation, and approval. Old numbered replies cannot target new options.
3. Stage outbound payloads in an outbox; send chunks/actions in order and mark delivery only after success. Retry delivery with backoff and deduplication, not shopping mutations. Report verified state after dispatch failure instead of claiming basket unchanged.
4. Persist checkout attempt before Swiggy call. Reconcile provider order/payment after timeout or restart before another attempt. Preserve child-order and payment states separately; paid does not mean fulfilled. Resume payment watch after restart rather than relying on one 60-second in-process task.
5. Use provider idempotency only if current Swiggy documentation supports it. A local attempt ID alone cannot guarantee exactly-once remote checkout.

Exit: duplicate delivery, worker restart, cold start, timeout, and partial Meta send cannot lose acknowledged input or duplicate consequential writes in the tested workflows.

## Phase 4 — shopping fidelity and conversation quality

1. Treat model output as a proposal. Validate tool allowlist, IDs, quantities, list limits, and grounded references. Malformed JSON is an error, not `{}`. Catalog/provider text is untrusted data.
2. Maintain a requested-item ledger: matched, unavailable, reduced, substituted, skipped, or awaiting decision. Apply explicit request > session choice > soft preference. Auto-add a close alternative for an ordinary named-brand request and disclose it before approval; never cross `only` brand, allergy, or dietary exclusions. Block candidates whose dietary suitability cannot be verified. Resolve each missing requested item with the customer before checkout; the customer may explicitly remove it from the task.
3. Filter out-of-stock products before display cap; retain pack, price, max quantity, similar-item, and paging data where provider-supported. Detect external cart changes and ask before adopting them; recheck address/store stock before approval. Ask among multiple saved addresses at the start of each new order. Limit first payment release to documented UPI QR flow.
4. Remove automatic symptom-to-medicine kits. Shorten prompt after task state and deterministic policy are available. Replace destructive HTTP 400 history repair with payload validation and non-destructive compaction. Code owns factual receipt/status; model explains options and tradeoffs. Keep auth, payment, delivery, and tool-error wording short and state-specific.
5. Build anonymized messy-language evaluations including Hinglish, quantities, corrections, diet, budget, and references. Score outcome correctness, constraints, unnecessary questions, and action count with real model calls and mock commerce. Compare Groq/OpenRouter on identical tasks before changing models.

Exit: every requested item is accounted for; constraints survive turns/restarts; claims match verified commerce state. Evaluation reports state their limits.

## Phase 5 — measured performance and cleanup

1. Record stage latency, provider/model, tokens, searches, cart reads, typed errors, and outcome; clear stale last-LLM error after success. Establish quality and p50/p95 baselines before speed targets.
2. Reuse canonical post-mutation cart for intermediate prompts/receipts while retaining fresh final approval/checkout reads. Fetch cart once for missing-SKU indexing when possible. Benchmark HTTP/2 before enabling; close pooled clients on shutdown.
3. Bound retries/deadlines for safe reads and model calls; respect `Retry-After` where present. Never blindly retry checkout or unknown writes. Defer shared quota scheduling until measured need.
4. Remove dead declarations/config and stale Gemini references after callers are accounted for. Correct README, ARCHITECTURE, task checklist, health, encryption, and test claims. Lock dependencies and verify on Python 3.12. Avoid speculative file splits or media deletion.

Exit: measured improvement without safety regression; docs describe the actual deployed commit and verification mode.

## Verification and rollout gates

For each phase: enumerate failure modes -> run red workflow/contract assertion -> implement smallest sound fix -> run green assertion -> run `pytest backend/tests`, `npm run lint`, and `npm run build` where relevant. Save a verifiable report with commit SHA, environment, mode, assertions, exit code, and external boundaries. Keep ordinary test artifacts untracked; publish release evidence deliberately. Refresh graph after changes.

Before live checkout: every P0 scenario passes on intended deployment; two-customer OAuth isolation, database migration, restart recovery, full receipt/approval, and no-charge real WhatsApp review flow are verified. Check provider read-only contract and reconciliation against current Swiggy docs. Chargeable smoke orders require separate explicit authorization per order. Roll out live mode with a quick return to review mode.

## Risks and deliberate limits

- Provider may lack remote idempotency or reliable order lookup. In that case unknown checkout remains blocked for human resolution; never promise exactly-once ordering.
- Billing/stock can change between observation and checkout. Re-review meaningful drift; a snapshot does not freeze Swiggy.
- Durable outbox cannot prove a customer read a WhatsApp message.
- Model evaluation covers chosen scenarios, not every possible utterance.
- Do not build a new dark-store system, operations dashboard, universal shopping framework, or second commerce abstraction.
