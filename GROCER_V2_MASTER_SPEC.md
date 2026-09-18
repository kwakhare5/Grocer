# GROCER master specification

> Version: 4.0
> Updated: 2026-09-16
> Status: active product and engineering source of truth

## Product

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. A person can write naturally—“only keep milk and bread”, “add one more bread”, or “3 Coke”—and Grocer must make the next action understandable and safe.

The goal is not a generic chatbot. The goal is to preserve the customer’s intended basket while live catalogue, cart, price, and delivery state can change.

The landing site explains GROCER and starts the Swiggy connection. WhatsApp is the shopping interface.

## Product boundary

In scope: English WhatsApp shopping, basket changes, product resolution, confirmed preferences, cart reconciliation, address/payment selection, explicit checkout approval, provider-backed status, reliability tests, and Swiggy Instamart through `CommercePort`.

Out of scope: internal retail operations, warehouse/inventory/supplier software, a generic marketplace, browser-owned shopping state, silent substitutions, autonomous checkout, refunds not supported by the provider, and any claim that an unverified provider outcome succeeded.

## Customer experience contract

1. Free English text is the primary input. Native WhatsApp buttons/lists accelerate only small, bounded choices.
2. Every message becomes a **proposed typed operation**, never direct provider authority.
3. Grocer asks one short, specific question when product, brand, pack, quantity, intent, cart ownership, or cancellation meaning is ambiguous.
4. Confirmed preferences can suggest an exact basket, but the customer sees and approves the complete proposed basket before a provider-cart change.
5. Current explicit text wins over a current session choice, a confirmed preference, and a default.
6. A provider cart is never silently used, merged, or cleared. If it is nonempty and not part of the current task, offer **Keep it**, **Start fresh**, or **Cancel**.
7. Resolve every essential item before mutation. If one essential is unavailable or needs a choice, do not partially change the cart.
8. Re-read and verify the provider result before telling the customer a change succeeded.
9. Checkout is a separate, backend-enforced explicit confirmation of the verified basket.
10. Customer messages are short, structured, plain English, and never expose raw provider errors.

## Authoritative state and architecture

```text
Meta WhatsApp event
  → signature verification
  → durable inbox
  → ShoppingTask application service
  → language proposal
  → deterministic task reducer
  → catalogue resolution
  → complete basket preview and approval
  → explicit provider-cart decision
  → CommercePort / SwiggyMCPAdapter
  → provider read-back and verifier
  → durable outbox
  → WhatsApp reply
```

`ShoppingTask` is the source of truth for a conversation. Its desired basket is what the customer wants; a Swiggy cart is only an external provider projection. The application records state transitions with optimistic versioning and deduplicates inbound provider events.

`CommercePort` is the only provider-neutral commerce boundary. Swiggy MCP payloads, OAuth, and retry semantics stay inside `SwiggyMCPAdapter`.

## Intelligence and deterministic enforcement

The model may interpret language, extract candidate items, recognize context, propose substitutions, and write friendly explanations. It must not be the final authority for quantity, price/budget arithmetic, constraints, task state, cart mutation, retries, or checkout.

Deterministic code validates the typed proposal, transitions the task, resolves the live catalogue, verifies the provider cart, and controls all consequential actions.

## Reliability policy

After any meaningful provider mutation, Grocer observes the live result and compares it with the approved desired basket and constraints.

- A documented safe transient operation may retry within a bounded policy.
- A provider rejection, partial result, stale cart, changed pack, budget drift, unavailable item, or unknown outcome requires verification and then either a safe repair or a customer decision.
- A recovery is never described as successful until it has been verified.

The active regression suite uses the same `CommercePort` contracts as the live path to test unavailable products, ambiguous variants, pack/price drift, stale carts, partial results, and safe retries.

## Security and release rules

- No provider secret, OAuth token, address, or customer data in frontend code, logs, or committed files.
- Managed PostgreSQL stores private task/inbox/outbox state. OAuth tokens and sensitive customer state must be encrypted at rest.
- The browser never owns commerce truth or checkout authority.
- `CHECKOUT_MODE=review` is the required submission setting. It truthfully stops before a chargeable order.
- `CHECKOUT_MODE=live` is permitted only after durable storage, Meta inbound/outbound verification, Swiggy OAuth/cart/address/payment review-mode testing, transcript replays, and an explicit authorized decision.

## Current migration status

Implemented: typed task model, reducer, natural-language operation boundary, catalogue resolver, provider-cart adoption guard, active durable WhatsApp route, private PostgreSQL schema/repository, encrypted OAuth storage, provider-response validation, and acceptance coverage.

Not yet complete: authenticated end-to-end replay of the latest reliability build against Swiggy review mode, restart/concurrency/retry verification, and an optional independent background outbox worker beyond webhook-driven retry.

Do not represent GROCER as live-checkout ready before those gates pass.
