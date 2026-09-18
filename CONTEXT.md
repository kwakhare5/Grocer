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
| Message understanding | A context-aware Gemini proposal validated into one typed, non-authoritative English operation. |
| CommercePort | The only provider-neutral commerce interface. |
| Cart adoption | The explicit Keep / Start fresh / Cancel decision for an existing provider cart. |
| Offered choice | A durable record of the buttons/list rows shown in the latest Grocer reply. Typed references such as “second one” resolve only against this set. |
| Stock recovery | A provider-verified quantity shortfall that requires the customer to keep the available amount, choose another live variant, or remove the item. |
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
- A model may resolve a reference only to a currently persisted offered choice; it may not invent a product, address, payment, or action ID.
- A Swiggy quantity cap or removed item never silently changes the desired basket. It creates a bounded customer decision and a new basket approval.

## Current implementation status

The typed task core, context-aware English boundary, durable offered choices, stock recovery, catalogue resolver, cart-adoption guard, private PostgreSQL schema/repository, and active-route regression tests exist. The legacy browser/orchestrator/evaluation runtime has been removed, leaving one conversation path. Hosted replay is still required to prove the deployed release.

## External rules

Keep Swiggy-specific schemas and errors inside `SwiggyMCPAdapter`. Use official Swiggy documentation for all MCP behavior. Use managed encrypted PostgreSQL before live checkout. Vercel is a landing/OAuth surface, not a commerce authority.
