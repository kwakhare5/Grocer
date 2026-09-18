# GROCER domain context

> Updated: 2026-09-16
> Product authority: `GROCER_V2_MASTER_SPEC.md`

## Identity

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. It handles ordinary customer language and protects the intended basket across provider changes.

## Canonical terms

| Term | Meaning |
|---|---|
| ShoppingTask | The durable aggregate for one customer shopping task. |
| Desired basket | The customer’s intended items before they are projected into Swiggy. |
| Provider cart | An observed external Swiggy cart, never automatic task state. |
| Basket plan | A complete proposed desired basket awaiting customer approval. |
| Message understanding | A typed, non-authoritative interpretation of one English message. |
| CommercePort | The only provider-neutral commerce interface. |
| Cart adoption | The explicit Keep / Start fresh / Cancel decision for an existing provider cart. |
| Confirmed preference | A preference the customer previously approved; it may assist a preview but cannot override current text. |

## Invariants

```text
current explicit request
  > session choice
  > confirmed preference
  > default
```

- The LLM proposes; deterministic code enforces and verifies.
- A full basket preview is approved before provider mutation.
- Every essential item resolves before mutation; no partial cart updates for a failed plan.
- A provider result is read back and verified before a success message.
- Checkout is explicitly confirmed in the backend.
- Free text stays primary; buttons/lists are for small bounded choices.

## Current implementation status

The typed task core, English operation boundary, catalogue resolver, cart-adoption guard, private PostgreSQL schema/repository, and regression tests exist. The old in-memory WhatsApp runtime is still active while the durable inbox/outbox task service is wired and replay-tested.

Do not delete legacy runtime modules early. Do not build further permanent behavior on them.

## External rules

Keep Swiggy-specific schemas and errors inside `SwiggyMCPAdapter`. Use official Swiggy documentation for all MCP behavior. Use managed encrypted PostgreSQL before live checkout. Vercel is a landing/OAuth surface, not a commerce authority.
