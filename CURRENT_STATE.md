# GROCER current state

> Verified locally: 2026-09-17
> Branch: `main`
> Release mode: `CHECKOUT_MODE=review`

## What is complete

- Consumer-only repository cleanup: obsolete archive documents and generated graph output removed.
- Canonical documentation updated for the WhatsApp-first ShoppingTask architecture.
- Typed ShoppingTask, desired basket, provider-cart binding, and basket-plan models.
- Safe natural-language operations for start, add, keep-only, remove, replace, cancel, and start-fresh requests.
- Full-basket preview/approval rule before provider mutation.
- Catalogue resolution that distinguishes exact, ambiguous, and unavailable items.
- Explicit provider-cart adoption guard.
- Private `grocer_internal` PostgreSQL schema and repository boundary for tasks, inbound events, and outbound messages.
- The durable ShoppingTask route is active on Render with Supabase persistence and encrypted OAuth tokens.
- Provider JSON/SSE responses are validated and malformed responses become safe customer messages.
- Provider calls run inside the authenticated customer's Swiggy context.
- Durable outbound replies are unique per source message, retryable while pending, and marked sent after Meta accepts them.
- Durable task states render native WhatsApp lists and confirmation buttons.
- One canonical root Python dependency file for Render and Docker.
- A context-aware Gemini structured-output interpreter is wired into the
  ShoppingTask service locally; its proposals remain reducer-validated.
- Every visible product, address, payment, confirmation, adoption, and stock-recovery choice is persisted with the task. Typed ordinal and price-reference replies resolve against that durable set.
- A verified Swiggy quantity cap now offers keep available quantity, choose another live variant, or remove the item; any choice produces a fresh basket approval.
- The legacy browser `/api/intent` router, legacy WhatsApp dispatch path, legacy
  orchestrator runtime, and legacy evaluation suite have been removed. Git history
  is the rollback mechanism; there is one active conversation path in this checkout.

## What is not complete

- The latest reliability changes still require deployment and a fresh authenticated WhatsApp replay through address, catalogue, cart, payment, and review confirmation.
- A standalone background outbox worker is not present; delivery is retried through Meta webhook replay while the durable row remains pending.
- Live checkout is not authorized or ready.
- The Gemini cutover and legacy-runtime removal are committed locally; hosted deployment and replay still need verification.
- Real hosted Swiggy access currently needs a valid customer OAuth session; the local read-only probe returned unauthenticated and could not complete a product search.

## Verified checks

- Focused durable-task and Swiggy response suite — 89 passed after the offered-choice and stock-recovery changes.
- `npm run lint` — passed.
- `npm run build` — passed.

These prove local regression health, not a real-provider deployment.

## Next release gate

Deploy the reliability changes, re-establish valid Swiggy OAuth if needed, then replay the real WhatsApp sequence from a fresh task through Swiggy address selection, catalogue resolution, cart verification, payment selection, and final review-mode confirmation. Only after that gate passes is the release proven; no legacy runtime remains in the active checkout.
