# GROCER architecture

Updated 2026-10-02. This describes the **local implementation**, not a verified production deployment. The first release target is review-only checkout. See [the rollout runbook](docs/RELEASE_RUNBOOK.md) for the required database and provider checks.

## Request path

```text
Meta WhatsApp webhook
  → Next.js forwarding route
  → FastAPI signature verification
  → PostgreSQL inbound_messages (commit before HTTP 200)
  → durable worker, ordered by customer
  → GroceryAgentEngine (customer-scoped task state)
  → CommercePort → SwiggyMCPAdapter or MockCommerceAdapter
  → PostgreSQL outbound_messages → Meta WhatsApp send
```

The worker processes a customer's queued messages in order. A `PROCESSING` inbound record or `SENDING` outbound record left by an interruption is held for operator review; automatically replaying either could duplicate a commerce write or a message. This is durable intake with conservative recovery, not guaranteed exactly-once delivery. A multi-process, real-database restart test is still required.

## Customer identity and account connection

The signed WhatsApp sender supplies an India-only E.164 number. The internal customer ID is derived from the full number. A 10-minute, single-use ticket binds the OAuth start to that sender; the browser cannot choose a customer by typing a phone number. Swiggy tokens are encrypted with Fernet in PostgreSQL and looked up only for the current customer. Existing last-ten-digit IDs require verified migration or reconnect; no automatic legacy mapping has been run.

## Basket and approval

The agent can propose searches and cart changes. The server checks tool inputs, serializes writes, reads the resulting cart, and compares submitted SKU quantities with the provider response. An approval records a fingerprint of provider items, bill lines, payable total, currency, and address for 15 minutes. Checkout re-reads the cart and refuses unknown or changed totals, unresolved item reductions, unreviewed external cart changes, and budget overages. Provider bill fields are still represented as Python floats; exact minor-unit accounting remains a live-checkout gate.

Multiple saved addresses require a fresh selection for each order. Explicit `only` brand and dietary constraints are described in the prompt, but a complete requested-item ledger, ingredient verification, and durable soft preferences are **not yet enforced by code**. The review-only release must not claim those guarantees.

## Checkout and uncertainty

`CHECKOUT_MODE=review` is the default and returns a simulated `REVIEW_COMPLETE`; it makes no provider checkout call. Live mode additionally requires `LIVE_CHECKOUT_ENABLED=true`, durable PostgreSQL state, and a reserved checkout attempt before the provider call. Unknown, partial, and payment-pending attempts block another live checkout for that customer. A live checkout failure never asserts that the account was not charged without proof. There is no automated post-restart order/payment reconciliation yet. The existing in-process payment poller is insufficient for live release.

## Data and operations

`grocer_internal` holds OAuth tokens, pending OAuth flows, connect tickets, inbox, outbox, checkout attempts, encrypted task snapshots, and privacy deletion requests. Task snapshots and completed message history expire after 30 days. The exact signed WhatsApp command `delete my data` removes customer conversation and token data; unresolved financial attempt records are retained until reconciliation. The existing schema must be inspected and backed up before applying migrations. `/health` is liveness; `/ready` checks essential runtime dependencies.

## Verification boundary

Local Python tests, ESLint, and the Next.js build are the current executable checks. No local PostgreSQL daemon, deployment secrets, chargeable order authorization, or real provider checkout are available in this workspace. Synthetic model tests do not establish live model behavior or production latency.
