# GROCER final recovery and delivery plan

> Final cutover decision (2026-09-17): the website is landing/OAuth only. The
> durable ShoppingTask route is the only conversation runtime in this checkout.
> Legacy browser/orchestrator/evaluation code was removed after the active route
> and its focused tests were established; hosted review-mode proof is still open.

## 1. Outcome

Deliver the final Swiggy submission as an English-first WhatsApp Instamart agent that can safely complete the real journey up to checkout, with checkout disabled during current testing. One real order may be placed later only after every earlier gate passes and the user explicitly approves it.

The project is complete only when the deployed WhatsApp route—not an isolated unit—passes the acceptance transcripts and reaches a verified real Swiggy checkout preview.

## 2. Locked product scope

### Required

- Natural-English grocery requests.
- Add, remove, replace, keep-only, quantity, brand, and pack changes.
- Clarification for uncertain meaning, product, pack, quantity, or destructive action.
- WhatsApp buttons/lists for bounded choices.
- Existing Swiggy cart decision: Keep, Start fresh, or Cancel.
- Selection and change of existing saved Swiggy addresses.
- Complete basket preview before provider mutation.
- Resolve every essential item before any provider mutation.
- Read the Swiggy cart before each cart-affecting turn and after each mutation.
- Cash on Delivery and UPI payment selection.
- Final items, charges, address, and payment summary.
- A distinct backend-enforced checkout confirmation.
- Basic order tracking.
- Plain-English failures and recovery.
- Durable conversation state, inbound deduplication, and outbound-delivery records.
- English input and output only for this release.

### Excluded

- Creating or deleting Swiggy addresses.
- Coupons and promotional recommendations.
- Multilingual and voice support.
- Silent substitutions or autonomous checkout.
- Admin, warehouse, inventory, supplier, or marketplace features.
- Claims that every possible human sentence can be understood without clarification.

## 3. Evidence-based diagnosis

The deployed WhatsApp path uses the durable ShoppingTask service and its
context-aware Gemini language boundary. The legacy browser API, orchestrator,
and evaluation suite are no longer part of the repository, leaving one public
conversation runtime and one active test path.

```text
Meta → Vercel proxy → FastAPI webhook → ShoppingTaskApplicationService
→ regex-only MessageUnderstandingService → reducer
→ CommercePort → Swiggy MCP
```

The permanent repair is a context-aware Gemini structured proposal at the
existing MessageUnderstanding boundary. The reducer remains authoritative.
Buttons and equivalent text must normalize to the same operation. Customer
intent and observed Swiggy cart state remain separate.

## 4. Final architecture

```text
Meta webhook
  → authenticate and normalize message
  → durable inbound-message deduplication
  → ShoppingTaskApplicationService
      → one MessageUnderstanding boundary
      → one deterministic ShoppingTask reducer
      → one response renderer
      → CommercePort
          → SwiggyMCPAdapter
      → verified task state
  → durable outbound record
  → WhatsApp sender
```

### Ownership rules

- `ShoppingTask` owns the customer's desired basket, selected address/payment, pending decisions, and confirmation snapshot.
- Swiggy owns the actual provider cart, prices, stock, serviceability, payment availability, and order state.
- The LLM proposes one typed operation. It cannot mutate state, call Swiggy, select a product silently, or authorize checkout.
- The reducer is the only component allowed to transition conversation state.
- Buttons and text are normalized into the same typed operations.
- Any basket, address, payment, price, availability, or provider-cart change invalidates prior confirmation.

## 5. Typed operation set

The final operation vocabulary must cover:

- Basket: start, add, remove, replace, keep-only, set quantity.
- Choice: select product/pack, keep provider cart, start fresh cart.
- Address: select and change saved address.
- Payment: select and change payment method.
- Lifecycle: confirm basket, confirm checkout, cancel pending step, cancel task, track order, ask for help.
- Safety: clarification needed.

Unknown or low-confidence language becomes clarification; it never defaults to starting or mutating a basket.

## 6. Repository cleanup matrix

### Keep

- Landing page, layout, styles, shared UI, logo, and Vercel analytics.
- Vercel backend/OAuth/WhatsApp proxy routes; they remain transport-only.
- FastAPI health, configuration, pseudonymous identity, and Swiggy smoke test.
- WhatsApp signature parsing, payload normalization, interactive formatting, and Meta sender.
- `CommercePort`, normalized commerce models/errors, mock adapter, Swiggy adapter/client/parsers/normalizers/OAuth, and provider fixtures.
- `task_model.py`, `task_reducer.py`, `message_understanding.py`, `catalog_resolution.py`, `cart_adoption.py`, `task_repository.py`, and the database migration.
- Provider contract tests, signed-webhook tests, transcript fixtures, and final application-service tests.
- Root Python requirements, package manifests, Docker, Render, lint, TypeScript, and pytest configuration.

### Remaining release work

- Verify the active `backend/api/whatsapp.py` route and stateless channel boundary against hosted replay.
- Move `backend/channels/whatsapp.py` process-memory dedupe/outbox state to PostgreSQL while preserving Meta transport logic.
- Wire the repository created in `backend/main.py` into the live service and readiness checks.
- Complete the task model/reducer for address, payment, checkout, cancellation, and tracking.
- Continue improving the typed language boundary only when a real replay demonstrates a missing case.
- Replace the `/tmp` token vault with encrypted PostgreSQL token storage.
- Persist OAuth PKCE pending state; it is currently process-memory only.
- Wire `DATA_ENCRYPTION_KEY` into real encryption; it is currently declared but unused.
- Keep provider-response fixtures and active application-service coverage aligned with the new boundary.
- Restrict production CORS to the real frontend origin.
- Make readiness fail when required production database, encryption, Meta, or Swiggy configuration is absent.
- Keep GitHub Actions installing the canonical dependency files and running on `main`.
- Make the Swiggy smoke script read-only by default. Any cart mutation must require an explicit destructive flag, preserve/restore or obtain ownership of an existing cart, avoid command-line tokens, and report that checkout was not verified.

### Completed cleanup

The retired browser API, legacy orchestrator/session/stage/recovery modules,
legacy evaluation harness, and tests coupled to them have been deleted. Git
history remains the recovery mechanism; no second runtime should be restored.

### Delete or consolidate as repository hygiene

- Generated `.next`, `node_modules`, `.venv`, `.uv-cache*`, `.pytest_cache`, and `graphify-out` may be locally regenerated and stay ignored; they are not product source.
- Do not delete any currently tracked runtime file merely to reduce file count.
- Consolidate final public truth into README, master spec, architecture, current state, context, reviewer walkthrough, and the Claude handoff. Keep the journal as history.
- Remove superseded audit/research/planning documents only after their still-relevant evidence is merged into an active document.

## 7. Implementation phases and stop gates

### Phase 0 — Freeze and baseline

- Freeze new features and architectural alternatives.
- Record the current deployed route and configuration without secrets.
- Convert real failed WhatsApp conversations into sanitized transcript fixtures.
- Establish the exact command that runs transcript replays.

**Gate:** No production behavior changes until the reported failures are reproducibly red through the actual channel/controller seam.

### Phase 1 — Red-capable acceptance harness (next)

- Add a generalized multi-item replay for ambiguous product confirmation (bread/eggs is one fixture, not special logic).
- Add transcript replays through the ShoppingTask service using `MockCommerceAdapter`.
- Add a signed Meta webhook replay verifying deduplication and exactly one outbound result.
- Capture a correlation ID, state transition, provider tool name, and sanitized provider result for every turn.
- Assert visible replies, states, and CommercePort calls—not only HTTP status.

**Gate:** The harness fails for the current bug, is deterministic, runs unattended, and completes in seconds.

### Phase 1A — Atomic message processing and identity safety

- Add explicit inbound processing states and claim one customer turn at a time.
- Commit task compare-and-save plus outbound enqueue in one PostgreSQL transaction.
- Reconcile an unknown Swiggy mutation result before retrying or claiming failure.
- Make pending outbound delivery independently recoverable and observable.
- Bind OAuth only after proving control of the complete E.164 WhatsApp identity.

**Gate:** Crash, concurrency, provider-timeout, and send-then-mark tests cannot lose a message, double-mutate the provider cart, overwrite another customer token, or emit an unverified safety claim.

### Phase 2 — Complete the deterministic task engine

- Extend task operations and state for address, payment, confirmation, tracking, and cancellation.
- Add a confirmation snapshot/version and invalidate it on every meaningful change.
- Add explicit pending decisions for ambiguity and provider-cart ownership.
- Replace “unknown text means start task” with clarification.
- Test every transition as a pure state change with no provider access.

**Gate:** The state-transition matrix passes, including invalid and out-of-order messages.

### Phase 3 — Build one application service

The one service performs this order:

1. Load/create the task and deduplicate the message ID.
2. Interpret text or button into one typed operation.
3. Validate and reduce the operation.
4. Fetch saved addresses when required.
5. Resolve the entire desired basket for the selected address.
6. Ask for product/pack decisions if an essential is ambiguous or unavailable.
7. Show and obtain approval for the complete basket plan.
8. Read the current Swiggy cart and obtain Keep/Start fresh/Cancel when needed.
9. Apply the approved complete cart through `CommercePort`.
10. Read the provider cart back and compare it with the approved basket.
11. Fetch live payment options and build the final confirmation snapshot.
12. Stop before checkout while `CHECKOUT_MODE=review`.
13. Persist task and outbound result.

**Gate:** All mock transcript replays pass through this service with exact provider-call assertions.

### Phase 4 — Durable state and safe credentials

- Apply the private PostgreSQL migration using the private Session Pooler `DATABASE_URL` configured directly in Render.
- Persist task state, inbound dedupe, outbound delivery, OAuth state, and encrypted Swiggy tokens.
- Test restart recovery, duplicate delivery, concurrent messages, and outbound failure.

**Gate:** Restarting cannot lose a pending task or process the same WhatsApp message twice.

### Phase 5 — Single-route hardening

- Keep the ShoppingTask service as the only conversation brain.
- Resolve every essential item before the first basket approval.
- Render provider-selected product names and pack sizes in the basket.
- Convert unexpected exceptions into durable, retryable task outcomes while logging the sanitized stack trace internally.
- Ensure a duplicate inbound message cannot create a second provider mutation or duplicate outbound reply.

**Gate:** The exact multi-item confirmation replay passes repeatedly with no duplicate transition, no generic fallback, and no unverified success.

### Phase 6 — Real Swiggy review-mode verification

- Fetch real saved addresses and address-specific products.
- Handle real variants, availability, and a pre-existing cart.
- Build the real cart only after basket approval.
- Read back and verify the real cart.
- Fetch real payment options and show the final checkout summary.
- Stop without calling `checkout`.

**Gate:** Every critical transcript passes repeatedly through the deployed WhatsApp number.

### Phase 7 — Payment review and controlled live readiness

- Use only payment methods returned as available.
- For UPI, use the returned payment link and polling limits; never ask for a UPI ID.
- Keep tracking and order history out of this submission until the core ordering journey is proven.
- On uncertain checkout failure, query order history before any retry; never blind-retry placement.

**Gate:** Contract replays pass. A real order remains disabled until separately authorized.

### Phase 8 — Submission proof and documentation cleanup

- Keep the review-only route enabled.
- Run the hosted WhatsApp acceptance matrix repeatedly.
- Remove stale documentation that describes deleted runtimes or unsupported features.
- Publish the reviewer walkthrough with known limits stated plainly.

**Gate:** No production import references legacy runtime; lint, build, tests, transcript replays, and real review-mode checks are green.

## 8. Mandatory acceptance transcripts

At minimum:

1. “1 litre milk and one bread.”
2. “Add one more bread.”
3. “Remove the Coke.”
4. “Actually only keep milk and bread.”
5. “Replace brown bread with white bread.”
6. Ambiguous “three Coke” requiring clarification.
7. Unavailable essential item with no partial mutation.
8. Existing unrelated cart → Keep/Start fresh/Cancel.
9. Change address from final confirmation.
10. Change payment from final confirmation.
11. Button and free text producing the same transition.
12. Duplicate webhook producing one transition/reply.
13. Backend restart mid-conversation.
14. Expired or revoked Swiggy authorization.
15. Swiggy timeout before and after cart mutation.
16. Checkout review with available COD/UPI options.
17. Cancel and restart.
18. Unexpected English leading to clarification rather than a wrong mutation.

## 9. Verification

```text
pytest backend/tests
npm run lint
npm run build
```

Additional gates:

- Mock transcript replay.
- Signed Meta webhook replay.
- Sanitized Swiggy response replay.
- Real WhatsApp review-mode matrix.
- Secret/personal-data scan.
- No raw provider error exposed to the customer.

## 10. Definition of done

GROCER is done when a customer can use ordinary English on the deployed WhatsApp number, safely create and revise a grocery task, make bounded choices through text or buttons, choose a saved address and live payment option, reach a verified real Swiggy checkout preview, and receive truthful recovery messages without losing state or repeating side effects.

Unit tests, a successful landing-page build, or an independent Swiggy MCP call are not sufficient evidence.

## 11. Current safety boundary

`CHECKOUT_MODE=review` stays enabled. Current implementation and provider testing stop immediately before `checkout`. Enabling one real order requires a separate explicit decision after every earlier gate passes.
