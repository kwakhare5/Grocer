# GROCER permanent-product architecture audit

**Evidence date:** 2026-09-16. This audits the code and current documentation, not just the failed transcript.

## Verdict

GROCER has the right product idea and several good boundaries. It is not yet a dependable live commerce product. The permanent problem is neither mainly WhatsApp, Vercel, Gemini, nor Swiggy MCP. It is that the application has no durable, authoritative shopping-task model between human language and Swiggy's account-level cart.

The project should not be dropped or repurposed. Intent preservation is the strongest part of the Swiggy submission. The right fix is to retain the channel, CommercePort, MCP adapter, verifier concepts, checkout guard, and landing page, while rebuilding the conversation/cart execution core around durable commands, desired-basket state, and reconciliation.

No honest engineer can promise zero outages, changing inventory, or ambiguous human messages. The permanent standard is: GROCER never silently takes an unintended commerce action; it clearly asks when uncertain; it records enough state to recover safely; and every discovered failure becomes a replay test.

## What should remain

| Area | Evidence | Decision |
|---|---|---|
| Product scope | GROCER_V2_MASTER_SPEC.md has a narrow WhatsApp/Instamart consumer scope and excludes dark-store operations. | **Keep.** |
| Provider boundary | backend/integrations/commerce/port.py and swiggy_adapter.py isolate provider code behind CommercePort. | **Keep and strengthen.** |
| Checkout guard | config defaults CHECKOUT_MODE to review; checkout code requires explicit confirmation. | **Keep.** |
| Domain models | IntentContract, CommerceCart, verifier, recovery and typed provider errors exist. | **Keep, then make state durable.** |
| Channel normalisation | backend/channels/base.py routes text and native interactive IDs through one controller. | **Keep.** |
| WhatsApp UI | BaseChannelAdapter renders lists/buttons for bounded choices. | **Keep and extend.** |
| Landing page | app/page.tsx is a landing/OAuth surface; app/api routes proxy to FastAPI. | **Keep. Do not make React a commerce state machine.** |
| Test seams | MockCommerceAdapter, fixtures, evaluation harness and focused tests exist. | **Keep, but replace component-only confidence with replay/E2E confidence.** |

## Root architecture gaps

### 1. Provider cart ownership is undefined

GrocerOrchestrator creates a local cart identifier, but SwiggyMCPAdapter.get_cart explicitly discards it and reads the authenticated account's current cart. clear_cart similarly clears the active account cart. See backend/intent/orchestrator.py and backend/integrations/commerce/swiggy_adapter.py.

A Grocer session is therefore not an isolated provider basket. Old account-cart products can silently enter a new conversation. That is the direct architecture cause of unrelated Vicks/Coke/vegetables appearing in a new basket. It is not a Meta delivery defect or a language-model defect.

**Permanent design:** persist a ProviderCartBinding containing customer, task, provider-cart fingerprint/version and last verified snapshot. If the active provider cart has products not attributable to the active task, require an explicit native choice: **Keep existing items**, **Start fresh**, or **Cancel**. Never automatically clear a real cart. If Swiggy only supplies one account cart, this explicit adoption gate is the only honest UX.

### 2. Human text becomes commerce mutation too early

ConversationController has broad actions such as BASKET_REQUEST and CHANGE_OR_CANCEL. On a BASKET_REQUEST, GrocerOrchestrator parses and may update the cart in the same turn. The items stage uses generic regexes for remove/swap. See backend/intent/conversation.py, orchestrator.py and stages/items_stage.py.

This does not define distinct meanings for:
- start/adopt a basket;
- add items;
- replace;
- remove;
- keep only these items;
- cancel a pending edit;
- cancel a pending checkout;
- track an order.

Thus “cancel other, just have milk and bread” becomes “remove the item named other just have milk and bread.” This is a command-model defect, not merely an unusual English sentence.

**Permanent design:** one typed command algebra:

    StartTask | AdoptCart | AddItems | SetItems | KeepOnlyItems | RemoveItems
    ReplaceItem | SelectAddress | SelectAlternative | SelectPayment
    ConfirmCheckout | CancelPendingStep | TrackOrder | AskForHelp

The language layer can only propose a typed command, slots, confidence and ambiguity. A deterministic transition validator accepts it, asks for clarification, or rejects it. The model never selects an irreversible action itself.

### 3. Basket mutation is not atomic

_resolve_items() records ITEM_UNRESOLVED but returns updates for available products. orchestrator.py can call update_cart before every essential requested product resolves; quantity ambiguity is checked after the mutation path. See backend/intent/stages/items_stage.py and orchestrator.py.

This allows a request to partially mutate the basket and then fail with a technical verification message.

**Permanent design:**

    interpret -> validate -> resolve all essential items -> clarify ambiguity if needed
    -> calculate full desired basket -> preview diff -> mutate provider once
    -> fetch canonical provider cart -> verify -> persist outcome

No plan executes until all hard requirements resolve. If bhindi is unavailable, the basket must remain unchanged and Grocer offers: Choose alternative, Remove bhindi, Cancel change.

### 4. There are three competing truths

_merge_contracts() exists in items_stage.py but the main turn path sets session.intent_contract directly from the newly parsed contract. It then retains provider-cart products through loose substring matching. The desired basket can therefore diverge between parsed message, stored contract and provider cart.

**Permanent design:** one persisted ShoppingTask aggregate owns a versioned desired basket. A deterministic reducer applies each accepted command. The provider cart is only an observed external projection. A reconciler translates the complete desired basket into provider mutation(s), then verifies the result.

### 5. Catalogue semantics are underspecified

There is an immediate parser defect: ltr/ltrs are missing from backend/intent/taxonomies.py. The deeper issue is _search_and_pick() infers catalog-dependent meaning from package labels. A request such as “3 Coke” may become three retail packs when only a 2L SKU exists, or get normalized differently by the provider.

**Permanent design:** create a CatalogResolution record for requested physical quantity, requested container/pack count, exact SKU, offered physical quantity, offered package count, and resolution status. Only exact or policy-authorized resolutions execute. Otherwise ask a bounded question. Build an English grocery corpus for abbreviations, corrections, quantities, packaging, misspellings and pronouns; unknown must be a safe clarification outcome. Gemini proposes structured slots, while deterministic code validates them against catalog facts.

### 6. Production state is ephemeral and tokens are not safely durable

The active-session mapping, webhook dedupe, outbound retry cache, intent history, preferences, OAuth pending state and customer-payment/address maps are process-local dictionaries. Session/address/token persistence uses best-effort /tmp files; session writes suppress errors in a background thread. SwiggyTokenVault writes bearer tokens in plaintext to /tmp/grocer_tokens.json. See backend/channels/base.py, channels/whatsapp.py, intent/session.py, storage.py, preferences.py, stages/address_stage.py and integrations/commerce/token_vault.py.

This fails across restart, multiple workers, Render/Vercel lifecycle and duplicate delivery. It is not adequate for live customer credentials.

**Permanent design:** use managed PostgreSQL, not Mongo, because this domain needs transactions, row/version locking, idempotency and relational audit trails. Persist tasks, commands, decisions/nonces, cart bindings/snapshots, message IDs, outbound messages, preferences, and OAuth metadata. Encrypt access/refresh tokens using a managed key/secret service. One FastAPI service, Postgres and a worker/outbox are sufficient; microservices are not.

### 7. Webhook work has no durable outbox

backend/api/whatsapp.py synchronously calls language, Swiggy and outbound Meta delivery inside the webhook request. Its duplicate and pending-response state is in memory. A failure after a provider action but before response completion can create a retry with an uncertain action.

**Permanent design:** verify and persist the inbound Meta event atomically by message ID; return promptly; process events in order per shopping task using a worker. Persist the outgoing message before sending and record its delivery attempt/result. Apply idempotency keys and reconcile unknown provider outcomes before retry.

### 8. Current recovery cannot repair missing ownership history

The verifier/recovery/confirmation modules are valuable, but recovery starts only after state is observed or mutated. It cannot infer whether a product in a global provider cart belongs to the task. Local tests also do not prove authenticated live MCP retry/mutation behavior.

**Permanent design:** recovery operates on persisted action plans and before/after provider snapshots, classifying not executed, executed, partially executed and unknown before any retry.

## Component decisions

| Component | Keep | Refactor/replace | Do not do | Build |
|---|---|---|---|---|
| Python | FastAPI, models, CommercePort, verifier, checkout guard | direct parse-to-update_cart turn path | parallel commerce stack | TaskRepository, task reducer, planner, reconciler |
| NLU | Gemini as optional English semantic extractor | typed command/slot extraction with validation | LLM authority over cart/state/checkout | grammar/normaliser, corpus and semantic evaluator |
| Swiggy | MCP client, parsers, normalizers, error taxonomy | provider cart version/fingerprint and capability modelling | pretend cart_id isolates a Swiggy account cart | cart-adoption gate, redacted live contract fixtures |
| WhatsApp | signature check, normalisation, native lists/buttons | state-backed delivery/retry | in-process dedupe as production guarantee | inbound event table, outbox, worker, telemetry |
| Frontend | landing page, OAuth handoff, server-only proxy | copy/status based on verified capabilities | client-side cart authority | reviewer readiness/status view after gates pass |
| Persistence | Pydantic interfaces | replace defaults with repositories | /tmp or RAM for production state/tokens | Postgres migrations, encrypted token storage |
| Docs/tests | master spec, mock/evaluation seams | acceptance scenarios and readiness wording | pass count as product proof | replay suite, provider contract replay, authenticated E2E checklist |

## Correct target architecture

    Meta webhook
      -> signature verification + durable inbound-event record
      -> ordered task worker
          -> Postgres ShoppingTask aggregate
          -> NLU proposes typed command
          -> deterministic state/command validation
          -> desired-basket reducer
          -> catalog resolver (exact / permitted / ask)
          -> provider-cart adoption gate
          -> persisted full-basket action plan
          -> CommercePort / Swiggy MCP
          -> canonical cart snapshot + verifier
          -> recovery or persisted pending decision
          -> durable outbound-message outbox
      -> Meta sender

    Vercel landing page -> OAuth handoff/status only -> FastAPI

This is a modular monolith, not a speculative microservice rebuild.

## Delivery sequence

1. Freeze new user-facing features and correct CURRENT_STATE.md claims: local tests are not live-readiness proof.
2. Record ADRs and executable acceptance scenarios for task/cart ownership, command semantics, durable state, unknown outcomes and checkout.
3. Build PostgreSQL repositories plus encrypted token strategy and migrations.
4. Replace command/state handling with the typed command algebra and deterministic transition table.
5. Build full-basket planning/reconciliation and the explicit existing-cart adoption UX.
6. Harden catalogue semantics against real redacted provider fixtures; exactness or clarification, never silent conversion.
7. Add durable webhook outbox/worker, traceability and scenario replay.
8. Run authenticated controlled WhatsApp/Swiggy tests before live checkout is considered.

## Final readiness standard

GROCER is ready only when it can prove that it:
- never silently adopts, merges or clears a provider cart;
- never partially changes a basket when an essential item is unresolved;
- gives add/remove/replace/keep-only/cancel/confirm distinct deterministic meanings;
- survives restart and duplicate webhooks without losing or repeating work;
- reports unknown provider outcomes honestly and reconciles before retry;
- passes real human conversation replays plus authenticated live provider gates;
- makes only verified claims on the landing page.

## Bottom line

The idea is viable. The permanent fix is a durable task-and-reconciliation architecture that makes language interpretation advisory, makes the desired basket authoritative, and treats Swiggy as a live external system whose cart must be explicitly adopted and continuously verified.
