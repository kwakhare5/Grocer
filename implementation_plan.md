# GROCER — Swiggy Submission Plan

## Product contract

GROCER is an English-only, WhatsApp-first Swiggy Instamart grocery agent.

- The landing page explains and links the user's Swiggy account; WhatsApp owns shopping.
- Free English text is understood as a proposed command, never as commerce authority.
- GROCER asks before every user-facing change: product, brand, pack, quantity, price,
  budget, address, payment, or checkout outcome.
- Native WhatsApp buttons and lists make bounded decisions quick; free text remains
  available for open-ended changes.
- Explicit confirmation is required for every checkout.
- `CHECKOUT_MODE=review` is the submission default. It truthfully stops before a
  chargeable order. `CHECKOUT_MODE=live` is an explicit later deployment choice.

## Architecture

```text
WhatsApp
  -> ConversationInterpreter (English text -> bounded command)
  -> ConversationController (session/nonce validation)
  -> GrocerOrchestrator (intent, policy, verification, recovery, confirmation)
  -> CommercePort
  -> SwiggyMCPAdapter
```

The model interprets. Deterministic code validates, changes commerce state, and
authorizes checkout.

## Completed in this consolidation

- Removed the unsafe direct model-to-commerce workflow.
- Made `GrocerOrchestrator` the sole commerce authority.
- Added validated free-text command routing alongside native WhatsApp IDs.
- Removed hardcoded frontend backend URLs, phone number, and webhook-token fallbacks.
- Removed public OAuth-status enumeration routes.
- Added a review-safe checkout mode and honest checkout result state.
- Replaced hardcoded ETA/tracking claims with provider-backed wording.
- Updated the landing page for English-only, no-silent-substitution messaging.
- Corrected active documentation that overstated durability or live verification.

## Remaining submission gates

1. **Conversation contracts**
   - Add black-box tests for English text, buttons/lists, stale choices, changes during
     confirmation, unavailable items, payment states, model failure, and order tracking.
   - Add frozen interpreter fixtures to the evaluation harness.

2. **Durable state**
   - Replace process-local sessions, OAuth state/tokens, webhook idempotency, and locks
     with one durable encrypted database before `CHECKOUT_MODE=live`.
   - Do not claim Render `/tmp` persistence is durable.

3. **Real integration verification**
   - Verify OAuth against the whitelisted `https://grocerr.vercel.app/` URI.
   - Verify one Meta test-number inbound and outbound journey.
   - Verify real Swiggy search/cart/address/payment behavior in review mode.
   - Enable live checkout only after explicit authorization and a controlled test account.

4. **Release evidence**
   - Add CI for backend tests and frontend lint/build.
   - Record PII-redacted turn/provider/verification events after durable deployment storage exists.
   - Publish a reviewer walkthrough covering normal ordering, clarification, stockout,
     stale cart, payment pending, unknown checkout, and delivery failure.

## Explicit non-goals

- No dark-store operations, dashboard, warehouse, supplier, or inventory product.
- No generic marketplace or Walmart integration.
- No browser-owned cart, checkout, or chat state.
- No silent substitutions, fabricated ETA, or raw provider errors.
- No claim that zero external-provider failures are possible.
