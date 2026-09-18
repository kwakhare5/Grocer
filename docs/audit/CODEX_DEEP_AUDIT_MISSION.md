# CODEX Deep Audit Mission

> Status (2026-09-09): audit implementation, post-fix review, and local verification are complete. The branch is ready for independent review and remains unmerged. Production persistence/deployment remains outside this branch.

> Branch: `audit/codex-deep-review`
> Baseline: `de32abb` (`main`)
> Started: 2026-09-07
> Authority: `GROCER_V2_MASTER_SPEC.md` plus the attached Codex goal objective

## Mission

Make GROCER a materially safer, simpler, and more truthful intent-preserving WhatsApp grocery commerce agent without replacing its existing architecture, placing a real order, or merging to `main`.

The implementation boundary remains:

```text
WhatsApp / web demo
        -> GrocerOrchestrator
        -> CommercePort
        -> MockCommerceAdapter | SwiggyMCPAdapter
```

The model may interpret and propose. Deterministic code owns quantities, product identity, hard constraints, state transitions, recovery authorization, confirmation integrity, checkout safety, and outcome truthfulness.

## Recovered execution state

The previous run ended during inspection, before repository changes:

- branch is `audit/codex-deep-review`;
- `HEAD` equals `main` at `de32abb`;
- `main..HEAD` contains no commits;
- worktree and index are clean;
- required audit artifacts did not exist;
- no cross-file refactor was in flight;
- baseline verification is green: 147 Python tests, ESLint, and Next.js production build.

Completed audit workstreams:

- repository instructions, product boundaries, graph map, tree, primary backend paths, provider adapter, WhatsApp ingress, frontend, configs, dependencies, tests, and documentation inspected;
- current official Swiggy Builders Club pages inspected for cart, checkout, payment, order, tracking, authentication, errors, and production requirements;
- independent backend/domain, Swiggy, and WhatsApp/security reviews substantially completed and synthesized.

Partially complete:

- per-file disposition ledger;
- frontend/dead-code and test-coverage independent challenge reviews;
- provider lifecycle design at the domain boundary.

Untouched at recovery:

- all behavioral fixes;
- adversarial test expansion;
- cleanup/deletion/archive work;
- documentation synchronization;
- logical commits and final branch review.

## Confirmed priority order

### P0 — Stop unsafe or false consequential behavior

1. Bind approval to a material basket fingerprint and one-time nonce.
2. Serialize confirmation per session and consume approval before checkout.
3. Make duplicate confirmations idempotent and unknown outcomes non-retryable without reconciliation.
4. Represent payment pending, payment failed, partial order, and unknown order separately from ordered success.
5. Remove invented facts from the live Swiggy adapter.
6. Fail closed for unsigned WhatsApp webhooks in live mode.
7. Prevent cross-user session/provider-cart access; make unsupported live multi-user operation fail closed.

### P1 — Restore semantic intent correctness

1. Introduce general physical-quantity normalization for volume, mass, and count.
2. Resolve pack counts without underfilling explicit requested physical quantity.
3. Reject or clarify dimension mismatches and unsafe overfill.
4. Replace substring product matching with normalized product identity rules.
5. Treat explicit brands as authoritative for the current request.
6. Reuse the same semantics in selection, verification, recovery, and confirmation snapshots.

### P1 — Complete provider lifecycle truthfully

1. Normalize only payment options returned by Swiggy.
2. Extend `CommercePort` for payment-status and order-confirmation operations where supported.
3. Parse single-order, multi-store, pending-payment, partial, and unknown results without defaults that imply success.
4. Track child orders independently and preserve raw provider status.
5. Keep ETA, coordinates, rider, store, items, and payment facts nullable/unknown when absent.
6. Support read-only conversational order detail and tracking requests without claiming unsupported modification.

### P2 — Security, privacy, and operational safety

1. Make browser APIs session-capability protected and enforce customer/session ownership.
2. Make WhatsApp action IDs scoped to the current approval/decision.
3. Fix opaque session creation, terminal-session reuse, cancellation, and intent-history cleanup.
4. Reduce PII/raw-message/provider-error logging and retention.
5. Restrict CORS and document secure environment requirements.
6. Clearly mark in-memory stores/dedup/outbox as single-process development limitations; do not pretend they are durable production infrastructure.

### P2 — Repository cleanup

1. Remove disconnected browser OAuth implementation and obsolete routes if no live call path consumes them.
2. Remove unused UI components, assets, helpers, dependencies, and obsolete database/runtime dependencies when reference audits prove they are dead.
3. Remove dark-store language/data from active consumer UI and active docs.
4. Archive historically useful but misleading documents; delete only files with no remaining value.
5. Keep the WhatsApp customer surface and `CommercePort` foundation intact.

### P3 — Evaluation and documentation

1. Add a compact, high-value adversarial suite rather than padding test counts.
2. Add a direct-selection baseline only if it produces honest comparative evidence.
3. Update README, current state, architecture, implementation plan, task board, agent resume, and journal after code is truthful.
4. Separate `LIVE VERIFIED`, `TEST VERIFIED`, `IMPLEMENTED BUT NOT LIVE VERIFIED`, `SIMULATED`, external limitations, and deferred work.

## Test-first execution slices

Each behavioral slice follows red -> fix -> targeted green -> related regression:

1. quantity and identity semantics;
2. approval fingerprint, expiry, invalidation, and concurrency;
3. payment/order state normalization;
4. Swiggy parsing and live-path no-fabrication;
5. WhatsApp signature/action/session hardening;
6. auth/session ownership;
7. tracking and order-detail truthfulness;
8. cleanup and documentation.

## Commit plan

Keep commits reviewable and dependency ordered:

1. `docs(audit): record baseline findings and execution plan`
2. `fix(intent): normalize physical quantity and product identity`
3. `fix(checkout): bind and serialize basket confirmation`
4. `fix(commerce): model payment order and tracking truthfully`
5. `fix(security): harden webhook sessions auth and privacy`
6. `refactor(cleanup): remove obsolete duplicate and legacy paths`
7. `test(adversarial): expand reliability matrix and evaluation`
8. `docs: synchronize audited implementation state`

Commits may be combined when a smaller coherent history is clearer. No merge to `main`.

## Verification gates

- targeted Python tests after every behavioral slice;
- full `pytest backend/tests`;
- configured Python static/lint checks if present or added;
- `npm run lint`;
- `npm run build`;
- secret/reference/dead-code scans justified by changes;
- final `git diff main...HEAD` standards review;
- independent specification review against the goal objective and master spec;
- final no-real-order audit of all test paths.

## Non-goals and external boundaries

- no dark-store operations features;
- no new microservice or speculative event-sourcing framework;
- no raw payment credential collection;
- no private Swiggy API;
- no invented provider capability;
- no automated live checkout;
- no claim of multi-worker durability until a real persistent store/inbox/outbox exists;
- no claim of live verification for changes not exercised against approved external services.

## Definition of done

The mission is complete only when the branch is reviewable, all supported gates pass, the high-risk behaviors above are deterministically covered, active documentation matches implementation, every material live-path provider fact is sourced or explicitly unknown, and remaining external/deferred limits are stated without euphemism.
