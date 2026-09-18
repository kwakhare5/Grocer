# GROCER architecture

> Updated: 2026-09-16
> Status: durable ShoppingTask migration in progress. The legacy WhatsApp route remains active only until the new route passes transcript replay and live review gates.

## Product boundary

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. The landing page explains the product and starts OAuth; shopping happens in WhatsApp. GROCER is not an operations platform, marketplace aggregator, or browser-owned cart.

## Permanent architecture

```text
Meta WhatsApp Cloud API
        ↓
FastAPI webhook: verify signature and persist inbound event
        ↓
Durable inbox
        ↓
ShoppingTask application service
  ├── MessageUnderstanding: English text → typed proposal
  ├── Task reducer: deterministic state transition
  ├── Preference policy: current text > session choice > confirmed preference > default
  ├── Catalogue resolver: exact / ambiguous / unavailable
  ├── Cart-adoption policy: keep existing / start fresh / cancel
  ├── Basket plan: complete preview → customer approval
  ├── CommercePort: provider mutation and read-back
  └── Verifier / bounded recovery
        ↓
Durable outbox
        ↓
Meta WhatsApp Cloud API
```

`ShoppingTask.desired_basket` is GROCER's authoritative state. A Swiggy account cart is an external projection, not an automatic source of truth. It is never silently merged, reused, or cleared.

## Module boundaries

| Boundary | Responsibility |
|---|---|
| WhatsApp channel | Verify Meta payloads, normalize inbound messages, send formatted outbound messages. |
| ShoppingTask service | Load/store the task, de-duplicate events, apply one ordered transition, enqueue replies. |
| Message understanding | Convert English into a non-authoritative typed proposal. |
| Task reducer | Enforce safe state transitions without calling a provider. |
| Catalogue resolver | Resolve every requested item before a cart mutation. |
| CommercePort | The only provider-neutral commerce interface. |
| SwiggyMCPAdapter | The only location for Swiggy MCP schemas, OAuth, transport, and error normalization. |
| PostgreSQL | Private durable state for tasks, inbox/outbox, tokens, preferences, and idempotency. |

## Conversation policy

Free text is the primary input. Buttons and lists are offered for bounded choices such as Keep / Start fresh / Cancel, product variants, address, payment, basket approval, and checkout confirmation.

- A vague request gets one clear question, not a guess.
- A confirmed preference can create a preview, never a silent cart update.
- A change like “only keep milk and bread” replaces the task's desired basket as a preview; it cannot remove unrelated provider-cart items until approved.
- The whole intended basket resolves before mutation. An unavailable or ambiguous essential blocks the plan; partial changes are not applied.
- Provider results are re-read and verified before the user is told a change succeeded.
- Unknown, failed, or unsafe outcomes are described plainly, without raw provider error codes or invented success.

## Safety and reliability

1. The LLM interprets and proposes; deterministic code validates, computes, transitions, and verifies.
2. Checkout requires an explicit backend-enforced confirmation of the verified basket.
3. Consequential mutations are never blindly retried. Unknown outcomes are reconciled before another attempt.
4. Secrets stay server-side. OAuth credentials and customer state require encrypted durable persistence.
5. Vercel and React are presentation/OAuth surfaces only; neither owns commerce state.

## Migration status

Implemented foundation: task model, reducer, English command boundary, catalogue resolution, provider-cart adoption guard, private PostgreSQL task/inbox/outbox schema, and regression tests.

Required before retirement of legacy modules: configure PostgreSQL, migrate OAuth tokens/preferences/idempotency/locks, wire inbox/outbox to the webhook, replay real human conversations, verify Swiggy review mode, then switch the WhatsApp route. `CHECKOUT_MODE=review` remains the only truthful release setting until these gates pass.
