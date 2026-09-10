# Live Swiggy Integration Hardening Plan

**Status:** Completed and merged into `ag/mainline` (Archived)  
**Branch:** `ag/mainline` (formerly `live/swiggy-integration-hardening`)  
**Completed:** 2026-09-10

## Objective

Harden the existing GROCER WhatsApp consumer-commerce flow against real Instamart
catalog variability and provider behavior. Preserve `GrocerOrchestrator →
CommercePort → SwiggyMCPAdapter`; do not add provider calls outside the adapter,
product-name rules, persistence infrastructure, or an autonomous checkout path.

## Evidence and non-negotiable invariants

- A bare quantity remains catalog-dependent until selected live SKU evidence makes
  its physical meaning safe, or GROCER asks the user.
- The canonical provider cart, not an `update_cart` acknowledgement or requested
  mutation, determines accepted quantities and success messaging.
- Provider `None` remains unknown. Only `is True` and `is False` establish a
  provider fact.
- Recovery is targeted to the failed intent item, bounded, constraint-filtered,
  and never silently accepts material underfulfilment.
- Checkout remains explicitly backend-authorized.

## Official MCP contract checked

Checked on 2026-09-09:

- https://mcp.swiggy.com/builders/llms.txt
- https://mcp.swiggy.com/builders/llms-full.txt
- https://mcp.swiggy.com/builders/docs/reference/instamart/search_products.md
- https://mcp.swiggy.com/builders/docs/reference/instamart/update_cart.md
- https://mcp.swiggy.com/builders/docs/reference/instamart/get_cart.md
- https://mcp.swiggy.com/builders/docs/reference/errors.md

The implementation will enforce these exact outbound adapter arguments:

| Tool | Outbound arguments |
| --- | --- |
| `search_products` | `addressId`, non-empty `query`, optional `offset` |
| `update_cart` | `selectedAddressId`, complete `items[]` with `spinId`, `skuId`, and `quantity` |
| `get_cart` | `{}` |

`cartId` is optional response metadata, not a documented argument to either cart
tool. `update_cart` replaces the entire cart; any mutation therefore needs a
fresh canonical `get_cart` read before GROCER reports its outcome.

## Implementation slices

### 1. Establish red real-response regressions

- Add a sanitized fixture loader for structural Instamart responses, kept under
  backend test fixtures and free of tokens, phones, address text, and unnecessary
  provider IDs.
- Capture fixtures for gram-based catalog variants, omitted serviceability,
  `maxQuantity`, and `reducedQuantityItems`/canonical cart underfulfilment.
- Add failing regression tests for each reported live behavior before production
  changes.

### 2. Make quantity semantics explicitly unresolved until catalog resolution

- Extend the existing quantity model/normalizer with a catalog-dependent bare
  dimension while retaining explicit COUNT, PACK_COUNT, MASS, and VOLUME wording.
- Keep original expression, explicitness, requested dimension, and normalized
  physical requirement intact; no item-name allowlists.
- Implement a deterministic resolver over selected catalog variation evidence
  (`quantityDescription`, SKU availability, and pack/count compatibility).
- Produce one provider-neutral resolved-meaning value shared by selection,
  mutation, verification, recovery, and messaging. It will carry the selected
  variant, cart quantity, expected fulfilment, confidence/status, clarification
  need, and concise explanation.

### 3. Integrate selection and WhatsApp clarification messaging

- Resolve bare requests after `search_products`, before price ranking or cart
  mutation.
- Auto-act only for explicit or high-confidence catalog-backed meanings, while
  surfacing a concise material interpretation in the existing conversation flow.
- Stop and request a choice when catalog evidence leaves a material ambiguity.
- Keep message wording derived from the resolved meaning so the user-facing
  statement matches the actual planned cart quantity.

### 4. Correct adapter contract and tri-state normalization

- Update `SwiggyMCPAdapter` to omit undocumented `cartId` outbound arguments,
  preserve returned `skuId`, and accept missing optional cart metadata.
- Parse provider caps/reduced quantities into provider-neutral commerce models
  without fabricating serviceability or availability facts.
- Use identity checks for all relevant optional provider booleans so `None` is
  observable unknown rather than false or true.
- Add exact outbound-dictionary contract tests for search, cart update, and cart
  fetch; invert legacy expectations that treat `cartId` as a request argument.

### 5. Reconcile every material cart mutation against canonical cart truth

- Model a mutation outcome that preserves requested and accepted quantities.
- After each material update, re-fetch `get_cart({})`, compare the canonical
  items/caps to the resolved meaning, and classify exact, provider-limited,
  partially fulfilled, unavailable, or unverifiable outcomes.
- Ensure cart health is not downgraded merely because optional serviceability is
  absent, while actual negative evidence remains actionable.
- Block full-success messaging when canonical quantity is lower than requested.

### 6. Add targeted provider-limit recovery

- For a quantity cap or accepted shortfall, calculate unmet quantity from the
  canonical cart and search the failed intent item with a non-empty query.
- Evaluate alternate variants, larger packs, multipacks, same-brand options, and
  policy-permitted cross-brand options through existing deterministic constraints.
- Safely apply only a resolved, constraint-valid repair; otherwise request a
  specific user decision. Keep attempts bounded and never use `get_go_to_items`
  as the universal recovery catalog.

### 7. Add safe interpretation observability and generalized coverage

- Emit concise structured internal trace events for original request, catalog
  evidence, resolved plan, canonical cart, shortfall, classification, and next
  action; exclude provider credentials and user PII.
- Add deterministic generated/table-driven matrices spanning explicit/bare
  wording, catalog package forms, quantity caps, ambiguity, and canonical-cart
  mismatches.
- Assert semantic invariants: explicit dimensions do not drift, bare quantities
  resolve only from evidence or clarify, UNKNOWN is preserved, price ranking is
  post-semantic, and cart truth wins.

## Expected files and boundaries

Primary implementation seams are expected to be limited to:

- `backend/intent/models.py`, `semantics.py`, `parser.py`, `orchestrator.py`,
  `verifier.py`, `recovery.py`, and possibly `recovery_loop.py`;
- `backend/integrations/commerce/models.py`, `port.py`, `mock_adapter.py`, and
  `swiggy_adapter.py`;
- focused backend regression/evaluation tests and sanitized fixtures.

The final file list will be constrained to the seams actually required by failing
tests. No frontend state machine, new database, queue, worker, or deployment
work is part of this milestone.

## Verification gates

1. New sanitized replay suite and generated/table-driven quantity suite.
2. Focused intent, recovery, commerce-port, and Swiggy adapter tests.
3. Full `pytest backend/tests`.
4. Existing adversarial evaluation harness.
5. `npm run lint` and `npm run build`.
6. `git diff --check`.
7. No live checkout/payment; bounded live WhatsApp re-test only after all local
   gates pass.

## Completion report

Report reproduced live issues, root causes, generalized changes, fixtures,
semantic-test coverage, verification results, current docs/date, changed files,
remaining live-only unknowns, persistence/deployment deferrals, branch, and HEAD
SHA. End with `READY FOR BOUNDED LIVE WHATSAPP RE-TEST`.
