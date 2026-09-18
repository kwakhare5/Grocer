# GROCER capability truth audit — 2026-09-17

## Scope and evidence

This is a read-only comparison of the working tree, committed history, public health endpoints, and official Gemini/Swiggy documentation. It deliberately distinguishes **local code**, **public availability**, and **proven end-to-end behaviour**.

## Bottom line

GROCER has a sound **shape** for a safe WhatsApp shopping agent, but it is not yet proven as a complete real-world agent. The local working tree now contains a Gemini-backed language interpreter. It is **not proven deployed**, because these changes are uncommitted after `a194809` and no deployment/replay evidence exists for them. The public Render health endpoint returned HTTP 200, but its payload explicitly says `database: "not_checked"`; that proves only that the web process is reachable.

## What the local architecture can actually do

| Capability | Evidence | Truth status |
| --- | --- | --- |
| Receive signed Meta WhatsApp text and native interactive replies | `backend/api/whatsapp.py`, `backend/channels/whatsapp.py` | Implemented locally; not independently replayed in this audit. |
| Keep durable per-customer task/inbox/outbox state | `backend/intent/task_repository.py`, `backend/intent/task_service.py` | Implemented; database connectivity not verified by `/api/health`. |
| Interpret free English into a bounded shopping operation | `backend/intent/model_understanding.py`; wiring in `backend/main.py` lines 52–73 | Implemented **locally** when all of `SHOPPING_TASK_ROUTE=true`, `UNDERSTANDING_MODEL_ENABLED=true`, and `GEMINI_API_KEY` are present. |
| Fall back safely if Gemini is unavailable or malformed | `backend/intent/message_understanding.py` lines 45–58 | Yes, but the fallback is limited rule-based parsing, so conversational quality falls sharply during Gemini failure. |
| Search live products, use returned SKU IDs, update/re-read cart | `backend/intent/catalog_resolution.py`, `backend/integrations/commerce/swiggy_adapter.py` | Code follows the provider shape; authenticated real-provider replay remains unproven. |
| Show bounded WhatsApp options | `backend/channels/whatsapp.py`, `backend/intent/task_service.py` | Buttons/lists exist for product, address, payment, adoption and confirmation taps. |
| Stop before an order is charged | `CHECKOUT_MODE=review` in `render.yaml`; `task_service.py` lines 173–182 | Local release setting is review mode. It must be checked again in Render before testing. |

## Gemini: exact boundary

Gemini does **not** place an order and does not speak directly to Swiggy. In the local code it receives a customer message plus only this context: task state, pending question, basket item names, selected address ID, and selected payment method (`task_service.py` lines 259–268). It returns a Pydantic-validated `MessageUnderstanding` proposal. The reducer then controls task state and the commerce adapter controls typed provider calls.

That boundary is correct. Google documents structured output as suitable for extraction, classification and tool/API inputs, but explicitly requires application validation; valid JSON is not proof of a correct interpretation. [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)

### Is Gemini live?

- **Local working tree:** yes, conditionally wired.
- **Committed Git revision:** no proof; the Gemini files and their wiring are uncommitted.
- **Render deployment:** unknown/not proven. The public service is healthy, but health does not expose route flags, key presence, database connectivity, or the deployed Git revision.
- **Real WhatsApp behaviour:** unproven after this cutover. No legitimate audit can claim it works until one fresh hosted WhatsApp conversation reaches the review confirmation.

## Swiggy MCP: exact boundary

Swiggy MCP does not understand user free text such as “get milk and bread.” GROCER/Gemini must turn that into deterministic actions. Swiggy receives JSON-RPC `tools/call` requests with a tool name and typed fields such as `search_products({addressId, query})` and `update_cart({selectedAddressId, items})`. [What is Swiggy MCP](https://mcp.swiggy.com/builders/docs/start/what-is-swiggy-mcp.md)

Swiggy requires a real selected address before product search, requires the customer to choose a specific returned variant, and requires returned `spinId`/`skuId` in cart updates. [search_products](https://mcp.swiggy.com/builders/docs/reference/instamart/search_products.md)

`update_cart` replaces the whole cart with the supplied items and can return out-of-stock removals or quantity caps. The official response must be read and explained to the customer before checkout. [update_cart](https://mcp.swiggy.com/builders/docs/reference/instamart/update_cart.md)

Checkout is a mutating provider action. Swiggy requires an explicit final user confirmation after showing live cart, address, and payment method. [checkout](https://mcp.swiggy.com/builders/docs/reference/instamart/checkout.md)

## Known capability gaps (not hidden)

1. **Typed references are not durable.** Product choices are rendered as IDs such as `select_product:name:spinId`, but the offered candidates are not stored in `ShoppingTask`. The model context does not contain them. A tap can work; “the second one”, “the 110 g one”, or “the cheaper one” is not reliable. `SELECT_OPTION` exists in the enum but the reducer has no handler.

2. **Short-stock and out-of-stock recovery is incomplete.** The adapter preserves `reducedQuantityItems`, but the task service only compares expected and actual quantities, then sends a generic stop message. It does not offer “continue with available quantity / substitute / remove.” Official Swiggy documentation says those availability changes must be surfaced and refreshed. [update_cart](https://mcp.swiggy.com/builders/docs/reference/instamart/update_cart.md)

3. **The context is too thin for a human-like agent.** It has no persisted offered choices and no recent-turn/history summary. Therefore pronouns and references cannot be guaranteed.

4. **The live route does not implement every declared operation.** `TRACK_ORDER` sets `requested_action` in the reducer, but `ShoppingTaskApplicationService` has no branch that calls the tracking provider methods. The legacy runtime contains more features, but it is not the permanent live path.

5. **Failure handling is safe but generic.** Any `CommerceError` becomes one broad “could not complete that with Swiggy” reply. It does not yet distinguish timeout, minimum order, cart expiry, serviceability, stock, or provider recovery options.

6. **No background delivery worker.** Gemini, Swiggy, and Meta delivery still occur during the webhook request. Durable outbound records exist, but retry depends on a Meta webhook replay rather than an independent worker.

7. **Tests are not live proof.** The working tree contains many legacy-orchestrator and mock-adapter tests. They are useful regressions, but they do not prove production Meta, Render, Gemini, Supabase, OAuth, or Swiggy interaction.

8. **Legacy files remain.** They are no longer mounted by the local `main.py`, but they remain in the repository and are still used by legacy tests/evaluation. They add confusion but do not execute merely because they exist.

## Simple next actions only

1. Deploy the already-prepared Gemini cutover and verify Render’s actual variables: `SHOPPING_TASK_ROUTE`, `UNDERSTANDING_MODEL_ENABLED`, Gemini key, database URL, encryption key, `COMMERCE_ADAPTER_TYPE=swiggy_mcp`, and `CHECKOUT_MODE=review`.
2. Run one fresh real WhatsApp journey: greeting → natural basket → approve → select address → select real variant → choose payment → final review. Do not confirm final checkout.
3. Add one small persisted `offered_choices` field to `ShoppingTask`; put visible product/address/payment choices in it and accept tap/number/ordinal against the same IDs.
4. Convert Swiggy capped/unavailable responses into three explicit choices: continue with available, choose substitute, remove item.
5. Add one live-route test per failed real transcript before deleting any legacy modules.

## What must not be claimed yet

- “Gemini is deployed and working on WhatsApp.”
- “All natural English is understood.”
- “Swiggy MCP understands customer language.”
- “Real checkout is ready.”
- “Every component communicates perfectly.”

Those claims need hosted, authenticated evidence—not more mocked tests.
