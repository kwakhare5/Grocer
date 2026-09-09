# Targeted Merge-Blocker Remediation Plan

> Branch: `audit/codex-deep-review`
> Scope: only the independently reported merge blockers and current Swiggy provider-contract gaps.
> Current verdict: **NOT READY** until the confirmed items below are fixed and fully verified.

## Evidence classification

| # | Finding | Classification | Planned disposition |
|---|---|---|---|
| 1 | General COUNT versus PACK semantics | CONFIRMED | Fix and add regression coverage. |
| 2 | Unsupported hard dietary constraints | CONFIRMED | Fail closed and add parameterized coverage for every parsed tag. |
| 3 | Instamart checkout below ₹1000 | PROVIDER DOC CHANGED / NOT APPLICABLE | Do not add a gate. Current official docs limit ₹1000 to Food, not Instamart. |
| 4 | Saved-address selection | CONFIRMED | Require an explicit choice even when one address is returned. |
| 5 | Provider/auth failure preservation | CONFIRMED | Preserve auth, revoked-session, timeout, network, and empty-result states. |
| 6 | User-selected payment method | CONFIRMED | Add an explicit multi-option selection step and invalidate stale confirmation. |
| 7 | UPI polling-cap finalization | CONFIRMED | At the headless polling cap, call `confirm/confirm_order` once and map the result truthfully. |
| 8 | Conversational order tracking | CONFIRMED, PARTIALLY EXTERNAL | Prefer rich tracking only with trustworthy provider-returned coordinates; otherwise use the documented ETA fallback transparently. Defer undocumented coordinate-field wiring/live validation. |
| 9 | CommercePort lifecycle contract | CONFIRMED | Make required lifecycle capabilities abstract and align the provider-neutral tracking signature. |

## Implementation slices

### 1. Quantity semantics

- Introduce a general semantic distinction between individual `COUNT` and `PACK_COUNT`.
- Treat numeric requests and explicit `pcs`/`pieces`/`units` as individual counts.
- Treat explicit `pack`/`packs`/`packet`/`packets` as pack counts.
- Preserve mass, volume, dozen, and ordinary unqualified single-item behavior.
- Reuse one conversion rule across search selection, verification, and recovery.
- Reject non-divisible underfill/overfill unless separately authorized by existing policy.

Regression-first coverage:

- six individual pieces against a six-piece provider pack selects one pack;
- six individual pieces against one-piece provider units selects six units;
- `3 packs biscuits` selects three packs;
- four bananas follows count semantics;
- non-divisible quantity remains blocked across selection, verification, and recovery.

### 2. Hard dietary verification

- Preserve known deterministic negative checks.
- Add an explicit unsupported/unverifiable hard-constraint violation.
- Fail closed whenever authoritative cart/provider metadata cannot prove a requested hard dietary property.
- Never infer or fabricate dietary metadata.

Regression-first coverage:

- parameterize every currently parsed tag and alias: vegetarian, vegan, halal, kosher, Jain, gluten-free, dairy-free, egg-free, and sugar-free;
- retain obvious contradiction coverage;
- prove unverifiable metadata never produces PASS.

### 3. Explicit saved-address choice

- Remove sole-address auto-selection.
- Keep provider IDs server-side and require a choice before product search or cart mutation.
- Preserve truthful zero-address behavior and existing multi-address selection.

Regression-first coverage:

- one and multiple addresses both make zero search/cart calls before selection;
- an accepted choice proceeds with the exact returned address ID;
- invented/stale choices remain rejected.

### 4. Provider failure taxonomy

- Replace the targeted broad catches in address resolution, search/pick, recovery catalog refresh, and payment-option retrieval.
- Map authentication/session revocation to reauthentication-required state.
- Map timeout/network/upstream failures to temporary provider-unavailable state.
- Keep genuine empty results distinct.
- Keep user messages safe and free of raw provider internals.

Regression-first coverage:

- auth, session revoked, timeout, generic provider/network error, and genuine empty results at each affected seam.

### 5. Payment selection and confirmation integrity

- When multiple usable live options exist, enter an explicit payment-choice state rather than choosing index zero.
- Offer only current provider-returned choices.
- Preserve the exact returned option ID, kind, and checkout method.
- After selection, create a fresh basket-bound confirmation snapshot.
- Reject stale, unavailable, or invented selections; changing payment invalidates prior confirmation.
- Keep the single-option flow simple while clearly surfacing the selected method, as allowed by current checkout guidance.

Regression-first coverage:

- multiple options cannot reach approval/checkout without selection;
- choosing the second option forwards its exact ID/kind/method;
- stale selection is rejected;
- changed choice issues a new nonce;
- unlisted choices are rejected.

### 6. Headless UPI cap finalization

- At the documented polling deadline while still pending, invoke `confirm_order` exactly once with stored provider-returned identifiers.
- Never retry checkout.
- Map success, failed, pending, and ambiguous results without overstating success.
- Record the current recipe/reference wording discrepancy in the audit evidence.

Regression-first coverage:

- deadline causes one confirmation call;
- ambiguous/pending finalization remains `ORDER_STATE_UNKNOWN`;
- repeated status handling cannot confirm twice.

### 7. Conversational tracking

- Route conversational tracking phrases to the primary tracking path.
- Use `track_order` only when coordinates came from trustworthy provider data.
- With no trustworthy coordinates, make zero rich-tracking calls and explicitly use the provider-supported structured ETA fallback.
- Preserve normalized/raw status, ETA, rider/store/delivery locations, store/delivery details, items, payment facts, and polling interval when rich tracking data is available.
- Do not add background notifications or undocumented coordinate extraction.

Regression-first coverage:

- all listed phrases enter the conversational tracking path;
- provider-returned coordinates call rich tracking;
- missing coordinates never produce synthesized values and use the explicit fallback;
- rich provider facts survive normalization.

### 8. CommercePort lifecycle contract

- Make lifecycle methods required by the supported application flow explicit abstract capabilities.
- Align `track_order` with a provider-neutral optional coordinate input.
- Keep Swiggy-specific validation and argument mapping inside `SwiggyMCPAdapter`.
- Update only test fakes directly affected by the stronger contract.

Regression-first coverage:

- incomplete adapters cannot instantiate;
- production adapters instantiate;
- port and adapters accept the same tracking contract.

## Documentation updates

Update only claims materially changed by the fixes in:

- `docs/audit/CODEX_AUDIT_REPORT.md`;
- `docs/audit/ADVERSARIAL_TEST_MATRIX.md`;
- `CURRENT_STATE.md`.

Use only: LIVE VERIFIED, TEST VERIFIED, IMPLEMENTED BUT NOT LIVE VERIFIED, SIMULATED, DEFERRED/EXTERNAL.

## Verification and delivery

1. Run each new regression red before its production fix.
2. Run focused tests after every minimal correction.
3. Run `pytest backend/tests`.
4. Run the adversarial evaluation command already used by the repository.
5. Run `npm run lint` and `npm run build` (including TypeScript checking in the build).
6. Run `git diff --check`.
7. Review only the cumulative changes from this remediation pass for introduced regressions.
8. Update the session-resume and journal records required by repository policy.
9. Commit the fixes in logical conventional commits and push `audit/codex-deep-review`.
10. Do not merge `main`.

## Explicit exclusions

- no new broad audit;
- no unrelated cleanup or refactor;
- no persistence, deployment, or proactive-worker work;
- no live provider mutation or checkout;
- no invented metadata, addresses, payment options, coordinates, or provider semantics.

