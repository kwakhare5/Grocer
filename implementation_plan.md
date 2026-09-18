# GROCER final recovery and delivery plan

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

The live path currently contains competing decision makers:

```text
Meta → Vercel proxy → FastAPI webhook → WhatsApp channel
→ ConversationInterpreter / ConversationController
→ second parser inside GrocerOrchestrator
→ stage-specific handlers → CommercePort → Swiggy MCP
```

This duplicates language interpretation, routing, and state ownership. Buttons and free text can produce different behavior for the same customer intention. The new `ShoppingTask` core is not connected to production and currently handles only basket-level operations.

The reported `change address` failure is proven by the live code path: the action taxonomy has no address-change operation, and free text falls through to the generic orchestrator with the old selected address.

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

### Refactor or replace before cutover

- Replace `backend/api/whatsapp.py` module-global legacy orchestrator with the durable application service.
- Replace `backend/channels/base.py` session/controller ownership with a stateless channel boundary and response renderer.
- Move `backend/channels/whatsapp.py` process-memory dedupe/outbox state to PostgreSQL while preserving Meta transport logic.
- Wire the repository created in `backend/main.py` into the live service and readiness checks.
- Complete the task model/reducer for address, payment, checkout, cancellation, and tracking.
- Replace the rule-only/legacy-dependent understanding prototype with one typed language boundary and deterministic validation.
- Replace the `/tmp` token vault with encrypted PostgreSQL token storage.
- Persist OAuth PKCE pending state; it is currently process-memory only.
- Wire `DATA_ENCRYPTION_KEY` into real encryption; it is currently declared but unused.
- Migrate still-useful quantity, identity, constraint, and read-back verification logic behind the new application service.
- Move the evaluation harness from `GrocerOrchestrator` to the new application boundary.
- Restrict production CORS to the real frontend origin.
- Make readiness fail when required production database, encryption, Meta, or Swiggy configuration is absent.
- Fix `backend/requirements-dev.txt` to include `../requirements.txt` after the deleted backend requirements file.
- Fix GitHub Actions to install the canonical dependency files and run on `main`; the current workflow references a deleted file and watches the wrong push branch.
- Make the Swiggy smoke script read-only by default. Any cart mutation must require an explicit destructive flag, preserve/restore or obtain ownership of an existing cart, avoid command-line tokens, and report that checkout was not verified.

### Delete only after the new route passes and the rollback window closes

- `backend/api/intent_chat.py` and its legacy-only schemas if no final consumer remains.
- `backend/intent/conversation.py`.
- `backend/intent/orchestrator.py` and all `orchestrator_*` modules.
- `backend/intent/session.py`, `storage.py`, and `stages/`.
- Legacy parser/models/enums/validator/taxonomies/policy/preferences/semantics/recovery/formatters modules after needed logic is migrated.
- Legacy exports in `backend/intent/__init__.py`.
- Legacy-only tests after equivalent transcript/application-service coverage exists.
- Legacy evaluation assertions tied to `GrocerOrchestrator`.
- The temporary cutover feature flag.

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

### Phase 1 — Red-capable acceptance harness

- Add a minimal reproduction for `change address` repeating confirmation.
- Add transcript replays through the WhatsApp channel using `MockCommerceAdapter`.
- Add a signed Meta webhook replay verifying deduplication and exactly one outbound result.
- Assert visible replies, states, and CommercePort calls—not only HTTP status.

**Gate:** The harness fails for the current bug, is deterministic, runs unattended, and completes in seconds.

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

### Phase 5 — Route cutover

- Enable the new service behind one temporary route flag.
- Keep legacy only as a short rollback path.
- Migrate or remove `/intent/chat` so a second conversation brain cannot survive.

**Gate:** Signed webhook, transcript, and full backend suites pass with the new route enabled.

### Phase 6 — Real Swiggy review-mode verification

- Fetch real saved addresses and address-specific products.
- Handle real variants, availability, and a pre-existing cart.
- Build the real cart only after basket approval.
- Read back and verify the real cart.
- Fetch real payment options and show the final checkout summary.
- Stop without calling `checkout`.

**Gate:** Every critical transcript passes repeatedly through the deployed WhatsApp number.

### Phase 7 — COD, UPI, tracking, and controlled live readiness

- Use only payment methods returned as available.
- For UPI, use the returned payment link and polling limits; never ask for a UPI ID.
- Handle success, failure, cancellation, cart-changed, pending, and refund states.
- Track with exact returned provider identifiers.
- On uncertain checkout failure, query order history before any retry; never blind-retry placement.

**Gate:** Contract replays pass. A real order remains disabled until separately authorized.

### Phase 8 — Final deletion and documentation cleanup

- Switch the new route on after all gates pass.
- Complete a rollback observation window.
- Delete the legacy runtime and legacy-only tests.
- Remove superseded documents/configuration and rewrite active docs to describe only the final system.
- Remove the cutover flag.

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
16. Checkout uncertainty using order-history-before-retry.
17. UPI success, failure, pending, cart-changed, cancellation, and refund states.
18. Tracking a placed order.
19. Cancel and restart.
20. Unexpected English leading to clarification rather than a wrong mutation.

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
