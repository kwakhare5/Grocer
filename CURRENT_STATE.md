# GROCER current state

> Verified locally: 2026-09-16
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
- One canonical root Python dependency file for Render and Docker.

## What is not complete

- The durable ShoppingTask service is not yet the active WhatsApp execution route.
- PostgreSQL is not configured or migrated in the deployed environment.
- OAuth tokens, preferences, idempotency, and locks have not yet moved from temporary legacy storage to encrypted durable storage.
- Durable inbox/outbox delivery worker is not wired to Meta WhatsApp.
- Authenticated Swiggy review-mode and Meta inbound/outbound replay have not yet been rerun against the durable route.
- Live checkout is not authorized or ready.

## Verified checks

- `pytest backend/tests` — 397 passed.
- `npm run lint` — passed.
- `npm run build` — passed.

These prove local regression health, not a real-provider deployment.

## Next release gate

Use the exact Supabase session-pooler connection string (with its password) as a deployment secret, apply the private-schema migration, wire the durable task inbox/outbox into the WhatsApp route, then replay real human conversations against mock and Swiggy review mode. Only after that can legacy state code be retired.
