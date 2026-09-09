# GROCER — Current State

Last verified: 2026-09-09
Branch: audit/codex-deep-review (unmerged)
Milestone: deep audit, safety hardening, and final verification
Readiness: single-process demo/research system; not production-ready

## Verified product boundary

GROCER is a WhatsApp-first consumer grocery replenishment assistant. Natural language is interpreted into an explicit IntentContract; deterministic code enforces quantity, identity, budget, recovery, confirmation, payment, and order-state rules. Commerce is executed only through CommercePort, backed by MockCommerceAdapter or SwiggyMCPAdapter.

No dark-store operations, warehouse tooling, supplier workflow, or autonomous financial debit belongs in this repository.

## Audited architecture

    WhatsApp / browser demo
            |
    GrocerOrchestrator
      |-- Intent parser and contract
      |-- deterministic verifier and policy
      |-- bounded recovery
      '-- basket-bound one-time confirmation
            |
    CommercePort
      |-- MockCommerceAdapter
      '-- SwiggyMCPAdapter
            |
    Swiggy Instamart MCP

The backend owns commerce truth. A checkout requires explicit_confirmation=true and the unexpired nonce bound to the displayed cart ID, item/SKU composition, quantity, prices, fees, discount, total, address, intent version, and exact payment option.

## Implemented and verified locally

- physical volume, mass, count, and exact pack-multiple preservation;
- tokenized product identity with known derivative exclusions;
- current-request precedence and deterministic brand/substitution policy;
- bounded recovery with post-mutation cart refetch and reverification;
- serialized, one-time checkout confirmation with stale-basket invalidation;
- exact provider payment-option ID/kind propagation for UPI intent or QR;
- truthful PAYMENT_PENDING, PAYMENT_FAILED, PARTIAL_ORDER, ORDERED, and ORDER_STATE_UNKNOWN transitions;
- provider polling cadence/deadline enforcement and confirm-once behavior after verified payment success;
- fail-closed checkout uncertainty with no blind retry or fabricated order ID;
- session capability/ownership checks, per-customer provider token resolution, webhook signature checks, and local replay control;
- provider order-detail and delivery-status reads without invented values;
- a 102-scenario adversarial coverage ledger.

## Current quality gates

- Python: 240 tests passed.
- Evaluation: 10/10 canonical scenarios pass; autonomous recovery rate is evidence-based at 40%, with zero unsafe recovery mutations in the harness. Checkout authorization is verified separately.
- Frontend: ESLint passes.
- Frontend: Next.js production build and TypeScript checks pass.
- Dependency checks: npm dependency tree valid; Compose configuration parses.
- Safety scans: no tracked environment files or hard-coded secret assignments found.
- No live provider mutation, payment, or order was performed during this audit.

## Known limitations and release blockers

1. Session, intent, token, replay, checkout-attempt, and notification state are process-local. Restart/multi-worker guarantees require durable storage and an inbox/outbox.
2. The documented get_orders response lacks a defensible cart correlation key. A timed-out checkout therefore fails closed as ORDER_STATE_UNKNOWN; positive reconciliation is not claimed.
3. OAuth helpers and token isolation exist, but production login, token eviction/re-auth on every provider auth failure, encrypted durable storage, and logout revocation are not integrated end-to-end.
4. Structured get_delivery_status works, but primary track_order needs provider-returned coordinates that the current OrderSummary boundary does not retain. Live rider tracking is unverified.
5. Provider models do not expose authoritative dietary metadata; name heuristics cannot prove compliance when metadata is absent.
6. Webhook validation has a fixed 1 MB pre-parse limit, but the limit is not configurable and malformed-envelope/phone-ID boundary coverage is incomplete.
7. Proactive tracking-change notifications and deduplication are deferred with the durable worker/outbox milestone.
8. Corrected payment/order/tracking behavior is contract-tested against mocked official payloads, not revalidated by placing a live order.
9. Multi-store child outcomes are preserved and aggregated at checkout, but later payment/detail/delivery reads still follow the primary order ID rather than polling every child independently.

## Historical evidence

Earlier project logs record live WhatsApp and Swiggy experiments. Those records are historical evidence, not proof that the audited branch is production-ready. Stale milestone documents were moved to docs/archive.

## Deferred next milestone

Production persistence/deployment is intentionally not started on this branch. It includes durable authenticated identity, encrypted OAuth storage, inbox/outbox idempotency, checkout-attempt correlation, a polling/notification worker, deployment/observability, and approved live validation.

## Frozen invariants

- Intent is authoritative over ephemeral cart state.
- LLMs interpret/propose; deterministic code enforces.
- Current explicit requests outrank memory.
- Hard constraints are never silently relaxed.
- Checkout always requires a fresh basket-bound user confirmation.
- Pending, partial, failed, and unknown outcomes are never reported as success.
- Provider-specific MCP behavior stays inside SwiggyMCPAdapter.
- No real order is placed by tests or evaluation.
