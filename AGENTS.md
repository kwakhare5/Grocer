# GROCER engineering contract

Read `GROCER_V2_MASTER_SPEC.md`, `CONTEXT.md`, `ARCHITECTURE.md`, and `CURRENT_STATE.md` before changing code.

## Product boundary

GROCER is an English-first WhatsApp consumer grocery agent for Swiggy Instamart. Its job is to preserve a customer's intended basket while commerce state changes.

Do not add operations/inventory/warehouse/supplier features, marketplace aggregation, browser-owned commerce state, raw provider errors, silent substitutions, or autonomous checkout.

## Architecture rules

```text
WhatsApp → durable inbox → ShoppingTask → CommercePort → Swiggy MCP
                                           ↓
                                  read-back / verifier → durable outbox → WhatsApp
```

- `ShoppingTask.desired_basket` is the authoritative customer intent for a task.
- A Swiggy cart is an external projection. It is only used after the user explicitly chooses Keep, Start fresh, or Cancel.
- `CommercePort` is the sole provider boundary. Keep all Swiggy-specific code in `SwiggyMCPAdapter`.
- The existing legacy conversation/orchestrator runtime is temporary. Do not delete it before the durable route has passed replay and live review gates; do not extend it as the permanent design.

## Language and safety rules

- LLM/model code interprets language and proposes; deterministic code validates, transitions state, resolves products, verifies provider results, and authorizes checkout.
- Current explicit request > session choice > confirmed preference > default.
- Confirmed preferences can create a complete basket preview, not a silent cart mutation.
- Every essential item resolves before a cart mutation. Ambiguous or unavailable essentials stop the plan.
- Checkout always requires a distinct backend-enforced confirmation.
- Never claim a failed or unknown provider action succeeded. Never expose provider error codes to the customer.

## Persistence and provider rules

- Persist task, inbox/outbox, idempotency, preferences, and OAuth state in managed private PostgreSQL storage before enabling live checkout.
- Encrypt sensitive tokens at rest. Do not put secrets in source, logs, or frontend state.
- Read the current official Swiggy Builders Club documentation before changing MCP tool calls or retry behavior. Do not invent tool names or schemas.

## Engineering rules

- Prefer minimal, tested changes. Keep provider calls behind adapters.
- Keep React/Vercel as landing/OAuth presentation; it never owns commerce state.
- Add deterministic tests around hard rules and replay human messages before changing live routing.
- Run the relevant checks and report results honestly:

```text
npm run lint
npm run build
pytest backend/tests
```
