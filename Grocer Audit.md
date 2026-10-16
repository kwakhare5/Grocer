GROCER: FULL CODE AUDIT AND FIX PLAN
16 October 2026

Repository: https://github.com/kwakhare5/Grocer
Audited commit: 0fda2b805984e8786de3c96e074a9e4b2a34f309
The remote HEAD was checked again after testing and still matched this commit.
No repository files were changed. No real customer accounts, paid model runs,
payments, orders, or provider credentials were used.

CONTENTS
1. The real issue
2. What the checks actually showed
3. Architecture to move toward
4. Subsystem decisions: keep, fix, simplify, delete/defer
5. Individual findings, with source locations and fixes
6. Ranked fix order and release gates
7. Corrections to earlier diagnoses
8. Scope, limits and file coverage


1. THE REAL ISSUE

Grocer has useful pieces, but it does not have one agreed shopping contract
from the customer's words through to the final order.

One part says: search, show exact products, wait for the customer's choice.
Another part says: choose products automatically and immediately change the
basket. The prompts, function descriptions, tests, session state and response
code have not moved together. This is an unfinished behavior change, not
merely a weak prompt or a bad model.

The deeper problem is that too much meaning lives in loosely connected text,
flags and helper functions. There is no durable record of every requested
item, its hard constraints, its selected product, the intended cart change,
and its verified outcome. As a result, a plausible receipt can replace proof
that the whole request was done correctly.

This shows up as five root problems:

A. Conflicting contracts.
   Automatic cart changes, old exact-choice behavior and old safety rules
   coexist. Some safety helpers are present and tested but never called by
   the active shopping path.

B. Intent is not a first-class object.
   Items, extras, exclusions, quantities, budgets and clarifications are
   reconstructed from words and model calls. Missing items can disappear
   rather than remain outstanding. A ranker can choose an unrelated product.

C. Uncertainty is treated as a temporary inconvenience.
   Unknown checkout outcomes become FAILED after a timer or reset. A cart
   write whose read-back failed can be attempted again in the same turn.
   Neither timeout nor clearing a cart proves that an earlier order failed.

D. State, effects and delivery are not one durable workflow.
   State snapshots, inbound message grouping, provider writes, approvals
   and outbound delivery have separate lifecycles. A review exists before
   it is delivered. Burst messages lose their individual action meaning.

E. Verification does not describe what is deployed or what was tested.
   The landing page claims a verified live journey and an all-green test
   count. It is mostly fixed data. Many tests still demand the old shopping
   contract. A test with 'real_model' in its name normally uses scripted calls.

The answer is not a rewrite of every file. Keep the commerce boundary,
signed intake, encrypted durable storage and final checkout checks. Replace
the contradictory orchestration with one small, typed shopping workflow.
Keep live checkout disabled until its uncertainty and approval paths pass.


2. WHAT THE CHECKS ACTUALLY SHOWED

Backend:
- Full collected suite: 114 cases.
- With an isolated local PostgreSQL instance: 69 passed, 45 failed.
- Runtime: about 80 seconds.
- Command: GROCER_E2E_DATABASE_URL=<isolated local database> python -m pytest -q --tb=short
- Initial run without PostgreSQL had 33 passes and 81 setup errors. Those
  setup errors were resolved; they are not the final result of this audit.
- The 45 failures are not 45 independent defects. Many assert the retired
  exact-variant-choice flow. Others expose real problems that remain under
  either design: missing request items, failed-readback retries, lost
  clarification, budget handling and misleading recovery.

Frontend:
- npm ci completed.
- npm run lint passed.
- npm run build passed.
- These checks do not prove the login journey or live provider integration.

Additional offline reproductions, using local fakes only:
1. A numeric toPay with no root currency raises AttributeError.
2. An unexplained Rs 50 billing gap becomes 'Surcharges & Fees' and
   billing_complete=True.
3. A 2024 delivered order with no cart/address identifiers is accepted as
   recovery of a new checkout, with status ORDER_PLACED.
4. A client scoped to customer B sends customer A's configured fallback token
   when the resolver returns no token. This is a latent construction risk;
   the normal factory does not supply that fallback token.
5. 'please confirm whether milk is available' is treated as confirmation.
6. Customer B can read customer A's basket in the shared mock adapter.
7. Tracking through the wrapper cannot supply required coordinates.
8. A Confirm button followed by 'wait' becomes text 'Confirm\nwait' while
   retaining interactive_id=confirm_order. Preflight then replaces that
   combined text with an affirmative checkout sentence.
9. Searching for fresh milk with only a dishwash-liquid candidate selects
   the dishwash liquid.
10. Adding one unit of an existing product whose quantity is three leaves
    quantity one, not four.
11. In ONE turn, a provider write followed by failed read-back led to THREE
    provider writes before a generic processing-limit reply.

No claim here establishes current Swiggy availability, real model quality,
production database contents, deployed configuration or successful live
checkout. Those need their own controlled tests after the code is fixed.

Evidence labels below:
- REPRO: directly reproduced offline in this audit.
- TEST: observed in the checked-in full test run, with caveats where needed.
- SOURCE: follows from the active code; not a live-service incident claim.
- DESIGN: a proposed simplification, separate from a proved defect.

Priority:
- P0: fix before enabling live checkout, or before trusting money/approval.
- P1: core shopping correctness, isolation, durability or customer recovery.
- P2: maintenance, truthfulness, operations and unfinished scope.


3. ARCHITECTURE TO MOVE TOWARD

Use one path:

Signed message -> durable ordered event -> parse typed shopping intent ->
resolve address -> find eligible products -> rank eligible products ->
validate a cart change -> write once -> verify once -> produce a review ->
deliver the review -> accept approval for that review -> checkout once ->
reconcile until the provider outcome is known.

The model should propose intent, not silently decide whether money-related
state is complete. Deterministic code should decide whether a change is
allowed and whether the outcome is known.

A small set of records is enough:

ShoppingIntent
- One row/item per requested product or recipe ingredient.
- Source wording, quantity operation (add/set/remove), pack, brand rules,
  exclusions and budget scope.
- Each item ends as fulfilled, unavailable, restricted, budget-blocked,
  or awaiting a decision. Never silently absent.

CartChange
- Base cart version/fingerprint, intended line changes and constraints.
- Stable operation ID; state such as prepared, sent, verified or unknown.
- An unknown write must be reconciled before another write.

Review
- Exact verified basket, address, full payable total and payment choice.
- Unique review ID, expiry, content hash and outbound delivery reference.
- A button identifies this review, not a generic 'confirm_order' action.

CheckoutAttempt
- Customer, review ID, approved amount and provider correlation identifiers.
- Prepared/in-flight/payment-pending/unknown/terminal outcome.
- UNKNOWN remains unresolved until evidence resolves it. An operator may
  resolve it with recorded evidence; a timer may escalate it, not erase it.

CustomerSession
- Typed fields, one serializer, versioned persistence and safe turn ownership.
- No dynamic fields that disappear at the next load.

Keep HTTP calls outside long database transactions. Use a short durable
lease or version compare-and-swap for turn ownership, plus independent
operation records for commerce effects. Do not solve the current short-lock
problem by holding a pooled database transaction through model/provider HTTP.

Do not turn this into a generic workflow platform or add more services now.
A few explicit records and transitions are enough. The important part is
that every path uses the same records and rules.


4. SUBSYSTEM DECISIONS

Commerce port and provider adapter: KEEP, FIX
- Keep CommercePort and the separation between application and provider.
- Fix parser fidelity, tenant-token fallback, timeout correlation and mock
  isolation. Test the real response shapes with redacted fixtures.

Shopping orchestration: SIMPLIFY
- One shopping contract; one typed intent; one cart-change entry point.
- Remove the unfinished mix of old variant choice and automatic mutation.
- Keep a product choice only when a hard constraint or real ambiguity needs it.
- Defaulting an ordinary household pack can be fine. Ignoring an explicit
  pack, brand, diet or 'skip if unavailable' rule is not.

Product search and ranking: KEEP SEPARATE, FIX
- Eligibility first, ranking second. Search rank is not proof of identity.
- Preserve stock, diet, pack and maximum-quantity evidence through all layers.

Cart execution and budgets: KEEP, CENTRALIZE
- Preserve untouched lines and current-cart checks.
- Represent add vs set explicitly. Validate complete merged changes before
  the provider write. Treat unverified writes as a blocked operation.

Approval and checkout: KEEP, HARDEN
- Existing fingerprints, expiry, final reads, budget gates, payment-option
  checks and durable attempts are valuable.
- Bind approval to a delivered review and payment choice. Never release an
  unresolved order hold merely because time passed or the basket was reset.

Session storage: KEEP, SIMPLIFY
- CustomerSession already replaced most independent state dictionaries.
- Remove redundant compatibility plumbing as callers move over; finish the
  typed serializer and concurrency model rather than replacing PostgreSQL.

WhatsApp intake/outbox: KEEP, FIX
- Keep signature checks, message-ID deduplication, durable queue and stale
  processing recovery.
- Do not merge interactive actions as plain text. Add per-chunk delivery
  state and a practical recovery view for UNKNOWN outcomes.

Authentication and privacy: KEEP, FIX LIFECYCLE
- Keep one-time customer-bound tickets, OAuth state/PKCE and encrypted tokens.
- Remove the obsolete phone-number login UI. Make deletion cancel pending
  auth and invalidate caches across instances.

Replenishment: DEFER OR ISOLATE
- On-demand history estimates can remain if they are wanted and tested.
- Automatic reminders are not delivered; the chat discloses that templates
  are pending. The background history-refresh function is not wired up.
- Do not keep selling a scheduled feature while only storing its settings.
  Hide/defer scheduling and remove unused runtime branches, or finish the
  worker, delivery permission/template and timing contract as separate work.
- Preserve migration history. Do not blindly drop existing production tables.

Frontend landing page: KEEP THE SMALL SITE, FIX THE CLAIMS
- The site builds. It is not evidence of a working live journey.
- Label fixed conversation data as an example. Show honest connection state.

Tests/CI: KEEP, REBASE ON THE CHOSEN CONTRACT
- CI now runs the full suite, not just a few unit tests.
- Rewrite assertions that deliberately belong to the old UX, but retain the
  safety behaviors behind them. Add tests through the real active path.


5. INDIVIDUAL FINDINGS

P0: MONEY, APPROVAL AND UNKNOWN OUTCOMES

F01. Checkout holds expire without evidence that checkout failed.
Priority: P0. Evidence: SOURCE.
Where: backend/agent/checkout_attempts.py:23-46,58-66;
       backend/agent/fast_paths.py:49-58;
       backend/agent/preflight_handler.py:140-150.
What: start() changes IN_FLIGHT older than 60 seconds, expired PAYMENT_PENDING,
and UNKNOWN older than 300 seconds to FAILED. clear_unresolved_hold() marks
IN_FLIGHT and UNKNOWN failed, and a successful basket reset invokes it.
Why it matters: a delayed, paid or placed order can still exist. This removes
the durable duplicate-checkout barrier without reconciling the provider.
Fix: use expiry to trigger recovery/escalation, not terminal failure. Keep an
unresolved hold until a correlated provider result or an evidenced operator
resolution. Basket reset must not resolve an order attempt.
Test: delayed response, crash after provider acceptance, expired payment poll,
and reset while checkout is unknown must all keep the duplicate barrier.

F02. Checkout timeout recovery can claim an unrelated old order succeeded.
Priority: P0. Evidence: REPRO.
Where: backend/integrations/commerce/swiggy_adapter.py:304-374.
What: the probe accepts the first order with an ID unless a present cart or
address field disagrees. Missing correlation fields are accepted. There is
no attempt time window, approved amount or item match. An old DELIVERED
order became ORDER_PLACED for a new cart in the offline reproduction.
Fix: correlate by a provider attempt/idempotency reference where supported.
Otherwise require sufficient positive evidence, including time and the
reviewed order details. Missing evidence means UNKNOWN, not success.
Test: old orders, missing identifiers, multiple orders, same address and
same total on different attempts, delayed results and partial orders.

F03. The app can turn an availability question into checkout confirmation.
Priority: P0. Evidence: REPRO.
Where: backend/agent/guards.py:207-237;
       backend/agent/preflight_handler.py:155.
What: bare 'ok', 'cool' and similar replies count; a substring 'confirm' is
enough in sentences such as 'please confirm whether milk is available'.
There ARE pending-review, fingerprint and final-cart gates. This is not a
claim that any random sentence can place an unreviewed order. The issue is
that an ambiguous reply can satisfy the human-confirmation part of an
otherwise valid pending review.
Fix: accept an affirmative only as a reply to a specific current review,
with no competing intent. Ask when the sentence is a question or mixed action.
Test: availability/payment questions, generic thanks/ok, revisions, hesitation,
and genuine affirmative replies to the exact reviewed basket.

F04. Burst merging can erase 'wait' after a Confirm tap.
Priority: P0. Evidence: REPRO and SOURCE.
Where: backend/api/whatsapp.py:71-79;
       backend/agent/preflight_handler.py:55-65,155.
What: merging appends later text but keeps the first message's interactive ID.
Confirm followed by wait becomes 'Confirm\nwait' with confirm_order attached.
Preflight replaces the whole text using that ID and sets confirmation true.
Fix: never coalesce interactive/payment/approval/reset/deletion events with
plain messages. Process ordered events; a later pause must invalidate an
unexecuted approval. If text grouping remains, retain all event IDs/types
and interpret the group before any action.
Test: confirm->wait, wait->confirm, payment selection->change, address tap->
correction, clear->add, and deletion in a message burst.

F05. Generic buttons do not identify the reviewed basket or payment choice.
Priority: P0. Evidence: SOURCE; replay risk not a live exploit test.
Where: backend/agent/approval.py:13-37;
       backend/agent/response_synthesizer.py:253-318;
       backend/agent/preflight_handler.py:57-65,203-240.
What: every review uses confirm_order. A tap from an old message is interpreted
against the current pending approval. Fingerprints include basket/address/
amount but not payment choice, review ID or outbound delivery identity.
Fix: issue a one-use review ID bound to exact contents, address, total,
payment method/option and customer. Put it in the button and require that
same unexpired review. Reject buttons for superseded reviews.
Test: tap an old review after a cart change, after a new review, after payment
selection and after a session restart.

F06. Approval is recorded before the review is known to be delivered.
Priority: P0. Evidence: SOURCE.
Where: backend/agent/response_synthesizer.py:276-318;
       backend/channels/message_store.py:112-128,164-202.
What: response synthesis re-reads the cart and records pending approval before
outbox delivery. A failed or partial send can leave a valid server approval
that the customer never fully received. There is no delivery-bound review
record to distinguish this from a reviewed basket.
Fix: persist the immutable review with its outbound message/chunks; activate
approval on the chosen delivery/acknowledgment rule. Keep ambiguity explicit
for delivery timeouts. A bare yes must not target an unseen newer review.
Test: receipt chunk fails, action chunk succeeds/fails, send times out after
acceptance, restart before/after delivery.

F07. Unexplained billing differences are invented as verified fees.
Priority: P0. Evidence: REPRO.
Where: backend/integrations/commerce/cart_parsers.py:66-88,112-152.
What: any positive difference is added as 'Surcharges & Fees', then the
mismatch is set to zero and billing_complete becomes true. The repro turned
an unexplained Rs 50 gap into a verified charge. Unknown provider labels
are also retained in bill_lines, so adding a synthetic difference may
represent the same charge twice in displayed detail. This does not itself
change the authoritative provider grand total, but it falsely claims the
charge breakdown was understood.
Fix: parse real fee labels and preserve unknown lines. Keep the provider total
separate from whether the breakdown is explained. Do not manufacture a fee
to pass the complete-bill checkout gate. Define any allowed tolerance openly.
Test: rain/platform/late-night fees, unknown labels, negative discounts,
multiple fee lines, rounding differences and unexplained positive gaps.

F08. Unverified cart writes can be retried inside the same model loop.
Priority: P0. Evidence: REPRO; corroborated by failing end-to-end test.
Where: backend/agent/cart_actions.py:138-150;
       backend/agent/react_coordinator.py:231-238,397-442,511-535.
What: execute_update_cart returns CART_WRITE_UNVERIFIED and retryable=False,
but the coordinator does not stop this mutation path or create a durable
reconciliation hold. A scripted model caused three writes in ONE turn after
three failed read-backs. The final reply was a generic step-limit message.
Fix: a provider write followed by uncertain read-back must stop further
mutations immediately, save its operation identity and enter RECOVERING.
Re-read/reconcile the cart; do not ask the model to retry the write.
Test: uncertain write with same tool repeated, process crash, transport timeout,
and a subsequent customer request before reconciliation.


P1: SHOPPING INTENT, CART AND PRODUCT CORRECTNESS

F09. A supported numeric provider total crashes the cart parser.
Priority: P1. Evidence: REPRO.
Where: backend/integrations/commerce/cart_parsers.py:91-124.
What: numeric toPay is explicitly accepted at lines 97-98, then code calls
to_pay.get("currency") when root currency is absent. The result is an
AttributeError rather than a cart or a controlled incomplete-provider state.
Fix: normalize the total/currency envelope once and type-check every fallback.
Apply the same discipline to optional nested bill fields and malformed values.
Test: numeric/object/string/missing toPay, absent currency, malformed bill
objects and non-finite prices/totals. Bad provider data must fail safely,
not crash a shopping turn or be converted into fabricated verified data.

F10. The active shopping contract contradicts its function schema.
Priority: P1. Evidence: SOURCE and many TEST failures.
Where: backend/agent/schemas.py:43-62,120;
       backend/agent/basket_manager.py:212-234;
       backend/agent/prompts.py:10-61.
What: quick_add_items says it does not change the basket and requires exact
customer choices. It actually calls the mutating basket manager. Other
prompts tell the model to auto-select standard packs. A model obeying the
schema can unintentionally cause writes it was told were only searches.
Fix: choose the product behavior once, then update schema, prompts, tool
names, implementation, session states, UI and tests together. Prefer names
that disclose effects. Separate product search from cart commit internally.

F11. Planning mode uses the general mutation prompt, not its own prompt.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/prompts.py:10-18;
       backend/agent/engine.py:355-374;
       backend/agent/react_coordinator.py:216-237,309-320.
What: _SHOPPING_PLAN_PROMPT is unused. planning_only exposes quick_add_items
but still uses the general prompt telling the model to call manage_basket.
Planning/conversational classification also changes with whether a cart
exists. The same request has different authority/tool exposure depending on
incidental basket state.
Fix: define explicit intent/operation stages and matching prompts/tool sets.
Do not use a word regex and cart emptiness as the sole effect boundary.

F12. Recipe/list repair guards are not connected to the active loop.
Priority: P1. Evidence: SOURCE and TEST.
Where: backend/agent/react_coordinator.py:13-14,28-77,265-375;
       backend/agent/guards.py: recipe/list reconciliation helpers;
       backend/tests/suites/planning_repairs.py;
       backend/tests/suites/budget_and_symptoms.py.
What: is_invalid_item_plan, build_recipe_repair_prompt, missing_recipe_staples
and reconcile_explicit_items exist or are imported, but the active loop does
not call them to validate the plan. Tests of the helpers do not establish
runtime enforcement. Actual replies in the failing suite omit requested
extras or include model-invented items and move directly to a cart review.
Fix: validate the whole typed request before search/write. Account for every
named item and hard exclusion. Repair a bad plan without mutating; retain
unresolved items if repair fails. Do not enforce a universal recipe when the
customer explicitly says some ingredients are already at home.

F13. Product matching has no minimum identity requirement.
Priority: P1. Evidence: REPRO.
Where: backend/agent/catalog_ranker.py:23-36,56-122.
What: matching returns true for nearly everything except two negative cases.
Every candidate starts with a positive score. With no milk candidate, the
ranker selected Dishwash Liquid for 'fresh milk'.
Fix: establish product/category identity and explicit constraints before
ranking. A search result with no eligible match must return no selection,
not the top unrelated result. Test poor provider search results deliberately.

F14. Explicit brand, pack and dietary limits are not hard selection rules.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/catalog_ranker.py:82-114;
       backend/agent/tools.py:59-94,143-156;
       backend/agent/prompts.py: dietary/brand rules.
What: brand/pack matches add points but mismatches are not rejected. Diet data
such as is_veg is dropped before selection. The model-facing schema has no
structured 'only this brand', allergy or substitution policy object. Prompt
instructions cannot make a deterministic selector enforce data it never gets.
Fix: carry explicit constraints with the intent, keep evidence through the
catalog layer, reject ineligible products and ask only when required evidence
is absent. A similar product is not proof of allergen/diet safety.

F15. Stock and maximum-quantity fields can be lost by the catalog parser.
Priority: P1. Evidence: SOURCE.
Where: backend/integrations/commerce/catalog_parsers.py:65-92;
       backend/agent/tools.py:61,91,143-156.
What: missing inventory defaults to {}, so the dict branch runs and ignores
top-level inStock/isInStock/maxAllowedQuantity. Unknown stock then passes
'in_stock is not False'. Compaction drops stock evidence before ranking.
Fix: read nested values when present, fall back field-by-field to supported
top-level values, and distinguish unknown from verified stock. Revalidate
selected products before committing rather than describing unknown as live.

F16. Catalog cache is not scoped to customer and can be stale for five minutes.
Priority: P1. Evidence: SOURCE; cross-customer effect depends on provider IDs.
Where: backend/agent/tools.py:41-43,129-157.
What: cache keys contain query and address ID, not customer identity or
provider account. This is unsafe if address IDs are not globally unique,
and even a correctly scoped cache is only a hint for live stock/prices.
Fix: include tenant/provider/location context, bound/evict entries, and
revalidate before write. Use a cache only for discovery, not live guarantees.

F17. 'Add' overwrites the quantity of an existing product.
Priority: P1. Evidence: REPRO.
Where: backend/agent/cart_actions.py:288-319;
       backend/agent/basket_manager.py:151-173.
What: a selected addition uses requested quantity as the final line quantity.
An existing line with three became one after adding one. Absolute updates
are valid for set_quantity, but not for 'one more'.
Fix: represent add(delta), set(quantity) and remove explicitly. Compute the
final quantity using the current cart once and validate the resulting line.
Test: add one more, add two, make it two, swaps and repeated identical calls.

F18. Duplicate selections bypass parts of quantity and predicted-budget checks.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/cart_actions.py:288-320,323-339.
What: if a second query selects the same spin, quantity is added and the loop
continues before maximum quantity and price-delta checks. Extra quantity
updates also change predicted_total without applying the same limit checks.
There is a later payable-budget check/rollback, but this is after the write
and does not repair every maximum-quantity case.
Fix: merge all intended operations by exact product first, then validate final
quantity, provider maximum, full total and scoped totals before one write.

F19. Budget capture is a phrase matcher, not complete intent understanding.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/budget.py:7-55;
       backend/agent/preflight_handler.py:78-88.
What: supported 'under/budget/total' forms work, including many plain-number
forms. Other clear limits such as 'I only have Rs 20' are not captured.
Ingredient scope and extras are inferred from a short wording window and
keyword overlap; short names such as oil/dal can fail extra classification.
Fix: parse budget and scope into the typed intent, validate numbers, retain
previous scope across edits and ask only when scope is genuinely unclear.
Do not advertise complete natural-language budget enforcement from regexes.

F20. Raw quantity-edit path omits the order-wide budget at cart mutation time.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/tool_executor.py:152-158;
       backend/agent/cart_actions.py:117-167;
       backend/agent/checkout_executor.py:116-137.
What: raw update_cart receives ingredient budget but not overall budget.
A quantity edit can change the basket beyond the cap before checkout.
The final checkout budget check exists and is useful; this is not a claim
that every such overage can be charged.
Fix: route all cart edits through one validated change executor carrying all
constraints. Block or clearly review over-cap changes before mutating.

F21. Ingredient-budget membership can become incomplete or stale.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/preflight_handler.py:80-88;
       backend/agent/tool_executor.py:93-94,112-113;
       backend/agent/budget.py:45-55.
What: a new cap clears ingredient IDs even with an existing cart; membership
is inferred through words rather than persistent request roles. Empty ID
results are not assigned because updates are guarded by truthiness.
Fix: persist ingredient/extra role per request/cart line. Replace membership
even when the new set is empty; reconcile it on remove, swap and restart.

F22. Removal and quantity matching are broad enough to change the wrong lines.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/catalog_ranker.py:39-53;
       backend/agent/basket_manager.py:62-97;
       backend/agent/guards.py:240 onward;
       backend/agent/react_coordinator.py:355-373.
What: substring matching can match milk to Dairy Milk chocolate and apply
the change to every matching line. 'without/no/skip' phrases are injected
as removals even when the user meant a constraint on new ingredients rather
than deletion of an existing basket item.
Fix: resolve edits to exact line IDs and quantities using current cart context.
Keep exclusion constraints separate from explicit delete operations. Ask if
multiple real lines fit, rather than changing all of them.

F23. The old cart-edit validator does not cover the new mutation surface.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/react_coordinator.py:322;
       backend/agent/react_coordinator.py:70-107: validate_cart_edit_calls;
       backend/agent/basket_manager.py:16-28.
What: validation focuses on update_cart calls while manage_basket has its own
remove/set paths. Ordinal-reference handling is also too broad to establish
which exact line a model is allowed to change.
Fix: validate the resolved CartChange, independent of which function proposed
it. Test wrong SKU, wrong line, ordinal ambiguity and extra model changes.

F24. Lists above 30 items and bad entries can be silently ignored.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/basket_manager.py:101-113,185-209;
       backend/agent/tools.py:123-127.
What: basket manager only processes additions when 1 <= len(add) <= 30;
invalid entries are skipped. The search layer and old plan validator allow
up to 45. A 31-item list can produce a success/no-change receipt instead of
an explicit rejected/unfinished list.
Fix: validate the entire batch, use one consistent limit and report every
rejected entry. If batching is needed, retain a durable outstanding list.

F25. Failed cart reads can be represented as a fake empty cart.
Priority: P1. Evidence: SOURCE, limited effect.
Where: backend/agent/basket_manager.py:33-52,185-209;
       backend/agent/cart_actions.py:81-114.
What: a general initial read failure constructs new_cart with no items and
serviceable=True. A later update path normally re-reads and blocks a mismatch,
so this is not proof that it blindly wipes baskets. A no-change response can
still show an invented empty state and the fallback hides the true failure.
Fix: return CART_UNAVAILABLE and stop mutation/review. A missing cart and an
unreadable cart are different states.

F26. Provider-omitted items are not durably blocked on the automatic-add paths.
Priority: P1. Evidence: SOURCE and TEST.
Where: backend/agent/cart_actions.py:169-198;
       backend/agent/tool_executor.py:75-114 versus 159-168;
       backend/agent/response_synthesizer.py:249-274.
What: manage_basket/quick_add update fingerprints but do not persist returned
unresolved_items as raw update_cart does. The response layer also clears
unresolved/budget-blocked items on broad affirmative text before proving
they were resolved or that the partial basket was deliberately accepted.
Fix: keep every omitted/changed request item in the durable intent ledger.
Resolve with specific evidence or a specific partial-basket decision, never
a generic yes. No approval while an unaccepted difference remains.

F27. 'Added items' can report requested rather than accepted additions.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/cart_actions.py:396-399;
       backend/agent/basket_manager.py:175-182.
What: the cart action filters budget-blocked selections for added_items,
but basket manager overwrites it with every selected product. The fresh
receipt is more reliable than this field, yet the outcome object itself
can falsely say a blocked item was added.
Fix: return accepted, blocked, omitted and verified lines from one result
object. Do not rebuild accepted outcomes from the original request.


P1: ADDRESS, STATE, RECOVERY AND TENANT SAFETY

F28. Address selection has two paths, only one of which migrates the cart.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/preflight_handler.py:311-357;
       backend/agent/address_tools.py:64-106.
What: choosing a pending address or matching an explicit address directly
changes session fields. It bypasses select_delivery_address, which migrates
an active cart. Session labels and the provider cart can disagree. Final
checkout checks may block it, but the customer can still see a misleading
intermediate destination and location-based searches.
Fix: use one address-change command, verify provider migration/read-back,
update session only after a known outcome, then issue a fresh review.

F29. Address migration failure messages can imply a rollback that was not proved.
Priority: P1. Evidence: SOURCE.
Where: backend/agent/address_tools.py:73-93.
What: after an exception during provider update, the response says the previous
destination remains selected. The provider may already have applied it.
A mismatched return likewise has no verified rollback.
Fix: enter ADDRESS_CHANGE_UNKNOWN, re-read and resolve. Only state that an old
address remains selected after verifying it. Clear old approvals first.

F30. Address data is dropped between parsing, presentation and tracking.
Priority: P1. Evidence: SOURCE.
Where: backend/integrations/commerce/order_parsers.py:153-207;
       backend/agent/address_tools.py: saved-address response;
       backend/agent/address_resolver.py;
       backend/integrations/commerce/models.py: DeliveryAddress.
What: parsed addresses omit coordinates/default metadata; tool address output
also omits area used by address matching. Matching relies heavily on text.
The UI offers at most three buttons even if more addresses are listed.
Fix: preserve supported metadata, separate private raw address from safe
labels, use stable IDs and paged/list choices for all saved destinations.

F31. Order tracking is not wired to the inputs the provider requires.
Priority: P1. Evidence: REPRO and SOURCE.
Where: backend/agent/tools.py:412-438;
       backend/agent/schemas.py:190-200;
       backend/integrations/commerce/swiggy_adapter.py:489-500.
What: wrapper calls get_addresses() without required customer_id, catches the
error, and would then access .lat/.lng rather than latitude/longitude.
Coordinates are not in the tool schema and are dropped by address parsing.
The provider adapter requires them. get_orders/get_order_details exist below
but are not exposed as a complete 'track my last order' resolution path.
Fix: resolve the authorized customer's actual order and its delivery location,
not the first saved address. Pass the provider's required fields explicitly.
Test: last order, explicit ID, different delivery address, missing location,
multiple active orders and expired auth.

F32. Clarification state disappears on durable reload.
Priority: P1. Evidence: SOURCE and TEST.
Where: backend/agent/react_coordinator.py:279-281;
       backend/agent/preflight_handler.py:389-397;
       backend/agent/session.py: CustomerSession;
       backend/agent/session_manager.py:108-173.
What: pending_clarification is dynamically assigned but not declared or
serialized. Each durable load creates a new CustomerSession without it.
The next answer can lose its connection to the original question.
Fix: declare typed pending question/intent fields and include them in a
versioned serializer. Add round-trip/restart tests for every state field.

F33. The database lock protects load/save, not the turn between them.
Priority: P1. Evidence: SOURCE; queue protection caveat matters.
Where: backend/agent/engine.py:245-260;
       backend/agent/task_state.py:23-33.
What: transaction advisory lock is released after load, before model/provider
work; save locks again later. Two independent engine instances can load the
same version and overwrite each other. The ordinary durable queue already
serializes much same-customer work, so this is not a claim that every normal
webhook is concurrent. The state store's stated cross-node guarantee is not
provided by these short locks alone.
Fix: durable turn lease or version compare-and-swap, plus operation IDs and
queue ownership. Keep HTTP outside long database transactions.

F34. Burst absorption marks messages finished before their work is durable.
Priority: P1. Evidence: SOURCE.
Where: backend/channels/message_store.py:89-110;
       backend/api/whatsapp.py:71-79.
What: all pending messages for the customer are marked PROCESSED before the
combined turn is staged. There is no short burst window, event-type filter
or durable link to a parent turn. UPDATE RETURNING also does not promise the
SELECT order. A crash can leave constituent messages without their own
recoverable response/work record.
Fix: persist an ordered group with member IDs and ownership. Complete its
members atomically with the durable group result. Keep destructive and
interactive events separate. Do not use bulk PROCESSED as 'claimed'.

F35. Retrying an entire WhatsApp response can duplicate successful chunks.
Priority: P1. Evidence: SOURCE.
Where: backend/api/whatsapp.py:27-47;
       backend/channels/whatsapp.py:184-215;
       backend/channels/message_store.py:188-202.
What: the sender transmits several payloads, returns false if a later one fails,
and the outbox retries the whole response three times. Already accepted
chunks are resent. Accepted provider message IDs and per-chunk state are
not retained; HTTP success is called delivery without receipt confirmation.
Fix: durable chunk IDs, accepted Meta IDs, per-chunk checkpoints and receipt
processing. Distinguish rejected, accepted, delivered and unknown. An unknown
send needs reconciliation/review, not a blind full-response retry.

F36. General turn failure asks the customer to repeat a possibly applied action.
Priority: P1. Evidence: SOURCE.
Where: backend/api/whatsapp.py:109-124;
       backend/channels/message_store.py:13-24.
What: a timeout/exception returns READY and asks the customer to try again or
rephrase. A provider action may have occurred already. The stale-processing
recovery has a safer uncertainty response, but the immediate failure path
does not use it.
Fix: track whether any effect was sent. If its outcome is not known, stage
an uncertainty reply and block conflicting changes until reconciliation.
Only recommend retry when the attempted action is known not to have run.

F37. A fallback token can bypass customer ownership checks.
Priority: P1, release-security blocker for affected construction. Evidence: REPRO.
Where: backend/integrations/commerce/swiggy_client.py:62-79,153-165;
       backend/integrations/commerce/factory.py:21-27.
What: resolve_token has ownership restrictions, but call_tool unconditionally
falls back to self._auth_token when scoped resolution produces no token.
The offline customer-B call sent customer-A's token. The normal production
factory currently supplies a resolver without a configured fallback token;
this is not evidence that deployed customers are crossing accounts today.
Fix: one authoritative token-resolution function. Never use an unscoped
fallback for an explicitly scoped customer. Test the actual call_tool path,
not just resolve_token directly.

F38. The mock adapter shares a basket across customers.
Priority: P1. Evidence: REPRO.
Where: backend/integrations/commerce/mock_adapter.py: cart storage/get_cart/
       update_cart; backend/integrations/commerce/port.py: customer_scope.
What: mock uses the inherited no-op customer scope and common default-cart.
Customer B read the milk added for customer A. This contaminates multi-user
simulation and can hide isolation bugs. It matters more because there are
silent fallback routes to the mock adapter.
Fix: customer-key every mock state object or require per-customer fixtures.
Mock behavior should enforce the same identity rules as production.

F39. A production configuration mistake can silently select fake commerce.
Priority: P1. Evidence: SOURCE, not a deployed-runtime claim.
Where: backend/main.py:88-96;
       backend/integrations/commerce/factory.py:15-32;
       backend/api/health.py: readiness_check.
What: Swiggy configured without DATABASE_URL becomes mock with a warning;
unknown adapter names also become mock. Readiness does not explicitly report
and validate the actual adapter or its expected mode. Missing database is
caught by readiness, so do not claim every fallback instance reports ready.
A typo with other dependencies present is a different risk.
Fix: production must fail closed on incomplete or unknown commerce config.
Require an explicit local/test mode for mock, report selected adapter in
readiness and make simulated receipts unambiguous.

F40. Deleting a token does not invalidate other processes' token caches.
Priority: P1. Evidence: SOURCE.
Where: backend/integrations/commerce/token_vault.py:217-242,279 onward;
       backend/api/whatsapp.py:91-105;
       backend/integrations/commerce/swiggy_oauth.py:288.
What: get_token_durable returns an unexpired local cache before checking the
DB. Deletion affects local cache and DB, but another worker can retain its
cached token. A provider revoke_session method exists but is not part of
this deletion path.
Fix: make revocation/deletion visible across instances through an auth epoch,
short validated cache or invalidation channel. Use provider revocation when
supported and appropriate; report uncertain revocation honestly.

F41. Pending OAuth can restore an account connection after data deletion.
Priority: P1. Evidence: SOURCE.
Where: backend/channels/message_store.py:228-259;
       backend/integrations/commerce/swiggy_oauth.py: pending flow store;
       backend/api/oauth.py:46-66,87-107.
What: purge removes tokens/tickets/state but not pending OAuth flows. Pending
flow customer information is inside encrypted payloads without a purgeable
customer index. A callback can later write a new token after deletion.
Fix: store a purgeable customer reference/auth generation, cancel pending
flows, and reject callbacks from an earlier deleted generation. Apply the
same check before both callback paths persist credentials.


P2: SIMPLIFICATION, UX, OPERATIONS AND TEST TRUTH

F42. The no-ticket login UI is incompatible with the secure backend.
Priority: P2, immediate onboarding blocker. Evidence: SOURCE.
Where: components/landing/ConnectInstamartModal.tsx:34-57;
       backend/api/oauth.py:16-24;
       app/page.tsx:22-49.
What: modal collects a phone number and posts phone_number when no ticket
exists. Backend requires ticket, so that path yields validation failure.
The backend's customer-bound ticket requirement is correct; do not weaken
it to make the old UI work. Presence of a ticket and ?connected=true also
produce trust/status cues without server confirmation.
Fix: explain that linking starts in the verified WhatsApp chat, provide that
route, and only open ticket-based OAuth. Show success from the validated
callback, not a query flag or mere ticket presence.

F43. One-time OAuth state is consumed before remote success, making retries brittle.
Priority: P2. Evidence: SOURCE.
Where: backend/api/oauth.py:21-39;
       backend/integrations/commerce/swiggy_oauth.py: flow consume/exchange.
What: connection ticket is consumed before initiate_flow succeeds; pending
state is consumed before code exchange finishes. A transient external failure
requires a fresh link. One-time semantics are protective, not a reason to
reuse arbitrary state after unknown token exchange.
Fix: model short processing/terminal/unknown states and give a reliable fresh
link recovery. Keep replay safety; do not casually make consumed state reusable.

F44. Response orchestration discards useful outcome meaning and resets review state.
Priority: P2. Evidence: SOURCE.
Where: backend/agent/react_coordinator.py:528-531;
       backend/agent/response_synthesizer.py:31 onward,319-328.
What: any receipt ends the loop with final_text emptied, so the prompt's
promised friendly summary or remaining follow-up is not produced by that
next step. The synthesizer then reconstructs meaning from many flags and
fields. It also clears pending approval on non-checkout turns without
confirmation actions, even when the customer only asked something unrelated.
Fix: build a typed TurnOutcome with verified changes, outstanding request
items, next decision and review. Render it once. Invalidate approvals for
meaningful changes/expiry, not incidental response-button choices.

F45. Non-English filtering can replace an important payment/failure message.
Priority: P2. Evidence: SOURCE.
Where: backend/agent/response_synthesizer.py:18-28,330.
What: any Devanagari text triggers whole-message replacement or preservation
of only the receipt tail. A legitimate item name or one Hindi phrase can
remove an explanation, payment link or uncertainty notice.
Fix: preserve factual outcome text and structured payment/recovery fields.
Use an English generation/translation pass without deleting content. Local
product names must not erase a safety notice.

F46. Unused variant-choice branches can fail if they become reachable.
Priority: P2. Evidence: SOURCE.
Where: backend/agent/react_coordinator.py:457-467;
       backend/agent/preflight_handler.py:307-309;
       backend/agent/session.py: pending_variant_selection.
What: groups/needs_variant_choice branches call engine._cart_proposal_state
and engine._variant_choice_response, which are not implemented. Preflight
just discards pending variant selection. This is leftover architecture, not
a working fallback selection flow.
Fix: delete the old flow completely if automatic selection is the decision,
or implement one real choice state end-to-end. Do not retain half a dormant
workflow because old tests still mention it.

F47. The fee-drift shortcut is unsafe and its required state is unfinished.
Priority: P2 now; P0 if activated without fixing. Evidence: SOURCE.
Where: backend/agent/drift_guard.py:20-41;
       backend/agent/session.py; backend/agent/session_manager.py:12-24,108-173.
What: any fingerprint change with total difference <= Rs 10 is called a minor
fee fluctuation and rebound to the old approval, without checking that items
and address are unchanged. known_cart_total is neither a declared/serialized
field nor set by normal record_pending_approval. It can be set by accepting
external changes in a live process, but is lost on durable reload.
Fix: remove tolerance for now. If wanted later, allow only explicit fee-only
changes under a user-approved rule with item/address identity unchanged.
Never allow changed products because their total happens to be close.

F48. Model error recovery can erase tool evidence; rate control is only local.
Priority: P2. Evidence: SOURCE.
Where: backend/agent/gemini.py:56-61,123-137;
       backend/agent/engine.py:363-374;
       backend/agent/prompts.py: build_system_instruction.
What: HTTP 400 salvage sends text-only history, dropping function calls and
results that establish which effects occurred. The prompt context also does
not explicitly carry the full structured budget/pending-operation state.
The time throttle is an unlocked per-client timestamp, not a cross-request
quota controller. A second model on the same key may share quota limits.
Fix: repair/validate model history without dropping the operation ledger.
Pass current typed intent and pending outcome explicitly. Keep rate limiting
and backoff distinct from model choice. The fallback IS a different model
in this commit; do not repeat the old 'same model fallback' diagnosis.

F49. Replenishment schedule settings outlive a missing runtime capability.
Priority: P2. Evidence: SOURCE.
Where: backend/agent/replenishment.py:90-137,196-229;
       backend/agent/preflight_handler.py:96-111;
       backend/agent/schemas.py:204-210;
       backend/main.py:38-78,140-156.
What: the app stores daily/weekly/time settings and advertises reminders.
Chat correctly says automatic WhatsApp reminders await template approval.
There is no running reminder worker, and refresh_due is tested directly but
is not invoked by main's workers. On-demand history reads are separate and
can still work. Stored schedule hour is not an actual delivered commitment.
Fix: defer scheduled reminders and hide inactive settings/claims, or build
one explicit scheduler/history-refresh/delivery path with consent, template
approval, timezone and missed-run recovery. Do not infer consumption certainty
from sparse order intervals; preserve 'may be running low' language.

F50. Public verification/runtime claims are stronger than the code evidence.
Priority: P2. Evidence: SOURCE and this audit's test results.
Where: components/landing/data.ts: VERIFIED_JOURNEY_TURNS and PIPELINE_NODES;
       components/landing/WhatsAppSimulator.tsx:34-44,270 onward;
       components/landing/ArchitectureSection.tsx: verification status;
       components/landing/Footer.tsx: bottom verification badge;
       components/landing/HeroSection.tsx; components/landing/FaqSection.tsx.
What: fixed conversation data is labelled recorded live/verified. Technical
payloads, timings, outcomes and a mock payment bridge are hardcoded. The site
claims 94/94 automated tests and live MCP runtime, while this source has 114
collected cases and this audit found 45 failures. '100% accurate stock/pricing'
and complete intent preservation are not supported by these checks.
Fix: label examples as examples. Derive any test/revision badge from a real
build artifact, with test scope/date. Do not call a mock trace a live recording.
This is a mismatch in repository page content, not evidence that a currently
deployed account is using mock commerce.

F51. The test suite is split between old behavior and new behavior.
Priority: P2, blocks a reliable release decision. Evidence: TEST and SOURCE.
Where: backend/tests/test_invariants.py;
       backend/tests/suites/planning_and_orders.py, cart_and_addresses.py,
       recipe_and_budgets.py, budget_and_symptoms.py;
       .github/workflows/quality.yml.
What: many tests demand customer variant choices and zero writes before a
choice, while the implementation/invariant tests now allow automatic add.
The full run is genuinely red, but not every red assertion is a product
regression. CI does run the full pytest suite now, plus frontend lint/build.
Fix: document the chosen contract in executable acceptance tests. Rewrite
retired UX assertions, not safety expectations. Keep explicit checks for
all requested items, no wrong edits, correct budget scope, unknown writes,
restart recovery, tenant isolation and one reviewed checkout.

F52. The 'real model' and burst tests do not prove the named live behaviors.
Priority: P2. Evidence: SOURCE.
Where: backend/tests/suites/recipe_and_budgets.py:269-310;
       backend/tests/test_invariants.py: burst/helper tests;
       backend/tests/suites/planning_repairs.py.
What: real_model cases normally substitute scripted model calls. Their optional
real branch constructs the engine with gemini_api_key='local-test', so simply
setting a real key in settings does not make that engine valid. Burst testing
of local concatenation does not exercise durable absorption and interactive
precedence. Direct helper tests miss the unwired runtime guards.
Fix: split deterministic, provider-contract, real-model and controlled-live
suites. Skip visibly when prerequisites are absent; never count a scripted
case as live evidence. Run safety tests through the actual message-to-effect
path and assert provider call counts, not just final text.

F53. Local verification can report success after silently skipping integration tests.
Priority: P2. Evidence: SOURCE.
Where: scripts/test.ps1; requirements.txt; supabase/config.toml.
What: test.ps1 checks port 5432 and prints a successful verification even when
the database suite is skipped. CI uses port 55432 and Supabase local config
uses 54322. Python dependencies are open-ended lower bounds, so a later
install is not necessarily the tested environment. Supabase config names a
seed.sql that is not tracked and does not itself wire the root migration
folder into the default Supabase migration layout.
Fix: one explicit DATABASE_URL-based test command, clear passed/skipped/failed
summary and reproducible dependency constraints. Choose and test one local
schema setup route. Treat the unused Supabase defaults as scaffolding, not
a verified database provisioning path.

F54. Retention and operational recovery are incomplete.
Priority: P2. Evidence: SOURCE.
Where: backend/channels/message_store.py:228-304;
       backend/agent/task_state.py: load/delete_expired;
       backend/integrations/commerce/swiggy_oauth.py: pending-flow expiry;
       backend/agent/engine.py:115-123,149-157;
       backend/api/health.py; .github/workflows/keep_warm.yml.
What: task snapshots and most message records have cleanup, but there is no
single retention policy covering expired tokens, pending auth flows, terminal
checkout attempts and replenishment history. Pending-flow cleanup is tied
to writes, not a complete scheduled purge. Message payloads retain raw sender
and message data in normal JSON, unlike encrypted token/task blobs. Local
session/lock/catalog maps lack a clear idle bound. UNKNOWN delivery/order
states have logs/counts but no practical resolution interface. The keep-warm
job logs HTTP status but does not fail on a bad status; readiness mainly
checks configuration/database, not end-to-end provider/model ability.
Fix: explicit retention by data class, minimize raw payloads, bounded idle
caches, and an operator view for unresolved operations with evidence-based
resolution. Separate liveness, readiness and controlled synthetic checks.
Do not claim all application data is encrypted merely because tokens are.
No missing live credential or unavailable provider is asserted by this audit.


6. RANKED FIX ORDER AND RELEASE GATES

1. Freeze unsafe effects, preserve evidence.
   Keep CHECKOUT_MODE=review and LIVE_CHECKOUT_ENABLED=false. Remove timer/
   reset-based resolution of unknown attempts. Stop writes on uncertain
   read-back. Split interactive events from text bursts. Fix the old-order
   recovery probe and token fallback. These are more urgent than UI polish.

2. Pick the one shopping contract and remove contradictions.
   Automatic ordinary-pack selection is compatible with low-friction UX,
   but hard constraints and real ambiguity still need a decision. Update
   schema/prompts/tests together. Delete unused variant paths and unused
   planning scaffolding instead of leaving both designs active.

3. Put the full request into a typed intent ledger.
   Every named extra and recipe ingredient needs an outcome. Store add/set/
   remove semantics, hard constraints, budget scope and pending questions.
   Connect plan validation and repair to the actual active path.

4. Fix product eligibility and cart math before more model tuning.
   Reject unrelated results; preserve stock/diet/pack evidence. Merge exact
   lines before maximum/budget checks. Recheck the final cart against the
   intended change. Correct 'add one more' and partial-basket accounting.

5. Unify address and durable state transitions.
   One verified address-change command; one typed serializer; versioned turn
   ownership; durable group membership for any text coalescing. Fix deletion,
   pending OAuth and cross-instance token invalidation.

6. Bind approval to a delivered, immutable review.
   Exact basket/address/total/payment, one-use review ID, expiry and a durable
   outbound reference. Generic buttons and a loose confirm regex are not an
   adequate human-approval record.

7. Finish checkout and delivery reconciliation.
   Never infer failure from elapsed time. Add correlated order recovery,
   per-chunk Meta acceptance/receipt tracking, UNKNOWN recovery and an
   operator resolution path. Test crashes at every effect boundary.

8. Rebuild the test/release truth.
   Rebase tests to the chosen UX while keeping safety rules. Fix the genuine
   behavior failures. Make real-model tests actually use the configured key
   and label their scope honestly. Pin a tested environment. Remove fixed
   'all tests passed/live verified' marketing until there is current evidence.

9. Only then decide whether replenishment earns its ongoing complexity.
   If not, defer scheduling and remove inactive product claims. If yes,
   ship it as a separate consented, monitored capability rather than another
   branch in checkout orchestration.

Minimum release gates:
- Full deterministic/integration suite passes under the chosen contract.
- Every requested item has a visible final status; no silent omissions.
- No product selected outside explicit identity/pack/brand/diet constraints.
- No retry after an unknown cart write or checkout without reconciliation.
- Confirm->wait and old-button replay cannot authorize a checkout.
- Review binds exact address, final payable amount and payment choice.
- Restart and multi-instance tests preserve state and tenant isolation.
- Deletion prevents pending callbacks/cache copies from restoring access.
- Tracking works for the real order destination with required fields.
- A controlled real-model run and provider-contract checks pass separately.
- Any controlled live money test has its own explicit approval, amount,
  account and recovery plan. It is not part of this audit.


7. CORRECTIONS TO EARLIER DIAGNOSES

Do not carry these old statements forward:

- 'Eight independent session dictionaries' is outdated. Most engine maps are
  now _SessionDictView views over CustomerSession. Remaining issues are typed
  field coverage, snapshot lifecycle, compatibility plumbing and concurrency.
- The checkout path is not wholly ungated. It checks confirmation, current
  cart/address, fingerprint, total, currency, bill completeness, budget and
  payment choices. The failures are specific gaps around those gates.
- CI does not only run two tests. quality.yml runs the full pytest collection
  with Postgres plus frontend lint/build.
- The initial 81 errors were missing local Postgres, not 81 proved bugs.
  After supplying isolated Postgres, the result was 69 passed / 45 failed.
- The model fallback is not simply a retry of the same named model in this
  commit. Shared quota and evidence-loss recovery remain separate concerns.
- Recipe/list guard functions being present does not mean the active path
  uses them. The earlier implication of complete runtime repair is incorrect.
- The replenishment chat discloses that automatic WhatsApp reminders await
  template approval. The remaining mismatch is stored/advertised scheduling
  and the missing running refresh/reminder workflow, not a hidden promise
  in every reminder reply.
- A mock fallback exists in source, but this audit did not establish that the
  current deployed runtime is using it. Likewise, the fallback-token bug is
  reproduced under an alternate client configuration, not a demonstrated
  deployed cross-account incident.


8. SCOPE, LIMITS AND FILE COVERAGE

This was a source audit of the current commit, not a penetration test or a
certification. Source evidence establishes what the code can do under the
stated inputs; it does not establish a production incident.

Read and checked:
- All active backend Python modules, including the agent, API, channel,
  identity/config/database and commerce integration folders.
- All Python tests and test-suite modules.
- All frontend application routes, proxy handlers, components and CSS.
- All migration up/down SQL and fresh bootstrap SQL. Down-migration drops
  were not mistaken for automatic production deletion.
- Deployment/CI, package/config files, environment template and test script.
- Tracked file inventory was reconciled against these categories.

Excluded from a claim of line-by-line executable review:
- README, architecture/spec/journal and other prose documents as truth about
  behavior. They were not substituted for actual code. Repository instructions
  and embedded application prompts were treated only as source data.
- package-lock.json was used by npm ci, not manually interpreted line by line.
- public/demo.mp4, logo assets, generated build output, dependencies, Git
  internals and generated build/type output were not audited as executable logic.
- No visual/accessibility certification of the rendered website or video.
- No authenticated live Swiggy/Gemini/Meta journey or deployment-state validation.

The request to read every line was applied to the tracked executable source,
tests, migrations and relevant configuration, not expanded into a claim of
having watched every binary byte or reviewed installed dependencies. The
inventory below makes the source coverage inspectable.

SOURCE FILE INVENTORY (paths relative to the audited repository)
.editorconfig (26 lines)
.env.example (38 lines)
.gitattributes (1 lines)
.github/workflows/keep_warm.yml (16 lines)
.github/workflows/quality.yml (56 lines)
.gitignore (48 lines)
.prettierrc.json (12 lines)
.vscode/settings.json (3 lines)
app/api/_lib/backend.ts (15 lines)
app/api/auth/swiggy/callback/route.ts (28 lines)
app/api/auth/swiggy/login/route.ts (28 lines)
app/api/simulator/chat/route.ts (25 lines)
app/api/whatsapp/webhook/route.ts (58 lines)
app/globals.css (114 lines)
app/layout.tsx (54 lines)
app/page.tsx (93 lines)
app/simulator/page.tsx (11 lines)
backend/__init__.py (1 lines)
backend/agent/__init__.py (1 lines)
backend/agent/address_resolver.py (99 lines)
backend/agent/address_tools.py (125 lines)
backend/agent/approval.py (38 lines)
backend/agent/basket_manager.py (234 lines)
backend/agent/budget.py (55 lines)
backend/agent/cart_actions.py (399 lines)
backend/agent/catalog_ranker.py (122 lines)
backend/agent/checkout_attempts.py (234 lines)
backend/agent/checkout_executor.py (304 lines)
backend/agent/checkout_outcome.py (148 lines)
backend/agent/drift_guard.py (83 lines)
backend/agent/engine.py (375 lines)
backend/agent/fast_paths.py (146 lines)
backend/agent/formatters.py (220 lines)
backend/agent/gemini.py (152 lines)
backend/agent/guards.py (294 lines)
backend/agent/preflight_handler.py (411 lines)
backend/agent/product_policy.py (27 lines)
backend/agent/prompts.py (116 lines)
backend/agent/react_coordinator.py (582 lines)
backend/agent/replenishment.py (306 lines)
backend/agent/response_synthesizer.py (350 lines)
backend/agent/schemas.py (212 lines)
backend/agent/session.py (73 lines)
backend/agent/session_manager.py (173 lines)
backend/agent/task_state.py (63 lines)
backend/agent/tool_executor.py (329 lines)
backend/agent/tools.py (478 lines)
backend/api/__init__.py (1 lines)
backend/api/health.py (53 lines)
backend/api/oauth.py (153 lines)
backend/api/simulator.py (129 lines)
backend/api/whatsapp.py (213 lines)
backend/channels/__init__.py (1 lines)
backend/channels/message_store.py (304 lines)
backend/channels/models.py (52 lines)
backend/channels/whatsapp.py (225 lines)
backend/channels/whatsapp_crypto.py (58 lines)
backend/channels/whatsapp_formatter.py (138 lines)
backend/channels/whatsapp_parser.py (67 lines)
backend/config.py (42 lines)
backend/database.py (25 lines)
backend/identity.py (22 lines)
backend/integrations/commerce/__init__.py (48 lines)
backend/integrations/commerce/cart_parsers.py (172 lines)
backend/integrations/commerce/catalog_parsers.py (112 lines)
backend/integrations/commerce/connect_tickets.py (61 lines)
backend/integrations/commerce/exceptions.py (96 lines)
backend/integrations/commerce/factory.py (32 lines)
backend/integrations/commerce/mock_adapter.py (492 lines)
backend/integrations/commerce/mock_catalog.py (67 lines)
backend/integrations/commerce/models.py (296 lines)
backend/integrations/commerce/order_parsers.py (610 lines)
backend/integrations/commerce/port.py (132 lines)
backend/integrations/commerce/swiggy_adapter.py (502 lines)
backend/integrations/commerce/swiggy_client.py (236 lines)
backend/integrations/commerce/swiggy_oauth.py (306 lines)
backend/integrations/commerce/token_vault.py (298 lines)
backend/main.py (232 lines)
backend/tests/__init__.py (1 lines)
backend/tests/conftest.py (2 lines)
backend/tests/suites/address_disambiguation.py (137 lines)
backend/tests/suites/budget_and_symptoms.py (280 lines)
backend/tests/suites/cart_and_addresses.py (455 lines)
backend/tests/suites/helpers.py (100 lines)
backend/tests/suites/planning_and_orders.py (346 lines)
backend/tests/suites/planning_repairs.py (169 lines)
backend/tests/suites/recipe_and_budgets.py (483 lines)
backend/tests/suites/replenishment_and_webhooks.py (393 lines)
backend/tests/suites/turn_recovery.py (149 lines)
backend/tests/suites/webhook_and_simulator.py (212 lines)
backend/tests/test_invariants.py (716 lines)
backend/tests/test_whatsapp_postgres_e2e.py (127 lines)
components/landing/ArchitectureSection.tsx (220 lines)
components/landing/ConnectInstamartModal.tsx (186 lines)
components/landing/FaqSection.tsx (41 lines)
components/landing/Footer.tsx (98 lines)
components/landing/HeroSection.tsx (55 lines)
components/landing/VideoSection.tsx (74 lines)
components/landing/WhatsAppSimulator.tsx (293 lines)
components/landing/data.ts (240 lines)
components/landing/types.ts (45 lines)
components/navigation/AppGlobalHeader.tsx (93 lines)
components/simulator/SimulatorClient.tsx (162 lines)
components/ui/GrocerLogo.tsx (86 lines)
components/ui/WhatsAppIcon.tsx (52 lines)
eslint.config.mjs (22 lines)
migrations/001_connect_tickets.down.sql (1 lines)
migrations/001_connect_tickets.up.sql (11 lines)
migrations/002_messages.down.sql (8 lines)
migrations/002_messages.up.sql (59 lines)
migrations/003_checkout_attempts.down.sql (1 lines)
migrations/003_checkout_attempts.up.sql (20 lines)
migrations/004_task_state.down.sql (1 lines)
migrations/004_task_state.up.sql (8 lines)
migrations/005_privacy_deletions.down.sql (1 lines)
migrations/005_privacy_deletions.up.sql (4 lines)
migrations/006_inbound_claimed_at.down.sql (2 lines)
migrations/006_inbound_claimed_at.up.sql (12 lines)
migrations/007_outbound_sending_started_at.down.sql (2 lines)
migrations/007_outbound_sending_started_at.up.sql (10 lines)
migrations/008_payment_followups.down.sql (10 lines)
migrations/008_payment_followups.up.sql (19 lines)
migrations/009_replenishment.down.sql (1 lines)
migrations/009_replenishment.up.sql (14 lines)
migrations/bootstrap_fresh.sql (22 lines)
next-env.d.ts (6 lines)
next.config.ts (22 lines)
package.json (29 lines)
postcss.config.mjs (7 lines)
pytest.ini (4 lines)
render.yaml (47 lines)
scripts/test.ps1 (49 lines)
supabase/config.toml (414 lines)
tsconfig.json (34 lines)

Inventory: 134 source/config files, 18,006 lines.
Line counts include comments, empty lines, declarations and boilerplate.
They are a coverage index, not a claim that every line contains a defect.

END OF AUDIT
