# GROCER master specification

> Version: 5.0
> Updated: 2026-09-18
> Status: active product and engineering source of truth

## Product

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. A customer can message naturally—“i wanna make pasta under 1500”, “only keep milk and bread”, “add one more bread”, or “3 Coke”—and Grocer turns natural human intent into real, verified grocery carts.

The goal is not a generic chatbot. The goal is to preserve the customer’s intended basket and budget while live store catalogue, cart state, prices, and inventory availability can change dynamically.

The landing site (`grocerr.vercel.app`) explains GROCER and facilitates OAuth reconnection. WhatsApp is the primary conversational shopping interface.

## Product boundary

In scope: Natural-language English WhatsApp shopping, recipe and shopping-kit deduction, autonomous catalog search, pack and variant selection, budget and dietary constraint enforcement, live cart reconciliation, address resolution, server-side gated checkout confirmation, dynamic UPI payment link/QR generation, provider-backed verification, and Swiggy Instamart integration via `CommercePort`.

Out of scope: internal retail operations, warehouse/inventory/supplier software, generic multi-marketplace aggregation, browser-owned commerce state, silent substitutions that violate dietary constraints, autonomous checkout without explicit customer confirmation, and any claim that an unverified provider action succeeded.

## Customer experience contract

1. Free English text is the primary conversational input. Native WhatsApp interactive buttons (`Confirm Order`, `Change Items`) accelerate final decisions.
2. The agent uses autonomous ReAct reasoning with smart defaults: for staple goods (e.g. milk, eggs, bread), it automatically selects popular in-stock variants matching customer preferences rather than halting with interrogations.
3. For multi-item goals (e.g. "pasta tonight under ₹1,500"), the agent deduces complete ingredient kits, verifies local dark-store stock, checks prices against the budget, and populates the cart in one turn.
4. Grocer provides a transparent itemized summary before checkout:
   - Itemized list with pack sizes, quantities, and individual prices in ₹.
   - Grand total including delivery and packaging fees.
   - Delivery address badge (e.g., `Home, Kingsbury Pune`).
   - Explicit confirmation question: *"Would you like me to place this order?"*.
5. Current explicit request strictly overrides remembered preferences and session defaults.
6. Checkout is strictly server-side gated: no order can be placed without explicit customer authorization (`is_user_confirmed: True`).
7. Dynamic UPI payment: on confirmation, Swiggy generates a dynamic UPI QR / payment intent link (`bridge_url` / `upi_intent_url`), delivered directly into WhatsApp so the customer securely pays via UPI.
8. Plain English transparency: provider errors and out-of-stock states are communicated clearly without technical error codes or false success claims.

## Authoritative state and architecture

```text
Meta WhatsApp Cloud API
        ↓
FastAPI Webhook (/api/whatsapp/webhook)
        ↓
GroceryAgentEngine (backend/agent/engine.py)
  ├── Context-aware ReAct reasoning loop (Gemini 3.5 Flash Lite)
  ├── SwiggyAgentTools (backend/agent/tools.py)
  │     ├── get_saved_addresses (resolves user delivery addresses)
  │     ├── search_products (live store catalogue inventory search)
  │     ├── get_cart (reads active cart contents, fees, and grand total)
  │     ├── update_cart (adds/modifies SKUs, respects stock & budget)
  │     ├── clear_cart (empties active cart upon request)
  │     └── checkout (server-side gated, generateUPIQR: True)
  ├── Deterministic fail-closed guard (blocks hallucinated order success)
  └── Dynamic payment bridge injection (delivers clickable UPI pay links)
        ↓
CommercePort / SwiggyMCPAdapter (backend/integrations/commerce/)
        ↓
Swiggy Instamart Live MCP Gateway (https://mcp.swiggy.com/im)
```

`GroceryAgentEngine` and `CommercePort` form the authoritative boundary:
- `GroceryAgentEngine` manages the multi-turn conversational state, invokes Gemini function calling with typed tool schemas, and enforces strict post-processing safety guards.
- `CommercePort` is the only provider-neutral commerce interface. Swiggy MCP JSON-RPC protocol handling, OAuth tokens, and response normalization remain encapsulated inside `SwiggyMCPAdapter`.
- `OAuth Bridge`: `backend/api/oauth.py` provides `/connect` and `/auth/callback` for seamless browser-based Swiggy authorization from mobile devices via reverse proxy (Ngrok) or production Vercel.

## Intelligence and deterministic enforcement

The Gemini model (`gemini-3.5-flash-lite`) interprets language, infers ingredient lists from open-ended recipes, selects in-stock pack sizes within budget, and proposes actions through function calling.

Deterministic Python code strictly enforces:
1. **Server-Side Checkout Gating**: `SwiggyAgentTools.checkout` enforces `is_user_confirmed: True`. If an LLM calls checkout without user confirmation, the tool immediately aborts with `CONFIRMATION_REQUIRED`.
2. **Deterministic Anti-Hallucination Guard**: Regex pattern classification (`_ORDER_SUCCESS_PATTERNS`, `_explains_failure`) inspects the LLM response whenever checkout fails or returns `PAYMENT_PENDING`. If the model falsely claims the order was placed/dispatched or fails to explain provider errors, the deterministic guard overrides the response, logs a warning, and presents the actual status and payment link.
3. **Dynamic UPI QR / Link Delivery**: For UPI orders, Swiggy Instamart creates a payment bridge (`bridge_url` / `upi_intent_url`). The engine ensures this clickable link is formatted cleanly in WhatsApp for one-tap payment.
4. **Calculated Totals and Fees**: Item totals, delivery fees, and packaging fees are calculated directly from verified provider payloads, never hallucinated by the model.

## Live Pune dark store proof

The autonomous agent architecture was verified end-to-end on a physical smartphone via official WhatsApp Cloud API (`+1 555 663-1707`):
- **User prompt**: *"i wanna make pasta i want grociers uner 1500"*
- **Agent execution**:
  1. Resolved customer delivery address at *Kingsbury, Charholi Budruk, Pune*.
  2. Autonomously deduced 7 essential pasta ingredients (pasta, pasta sauce, mozzarella cheese, butter, onion, garlic, capsicum).
  3. Queried the live Pune dark-store catalog and selected in-stock variants respecting the ₹1,500 budget limit.
  4. Executed cart additions into live Swiggy Instamart cart ID `8c64c847` (Grand Total: ₹506 including delivery and packaging).
  5. Delivered full itemized breakdown and interactive WhatsApp confirmation controls.
  6. Generated verified UPI payment link upon order confirmation.

## Reliability and error policy

After every cart mutation or checkout call, Grocer reads back and verifies the actual provider state:
- If an item is out of stock (`ItemOutOfStockError`), the agent conversationally suggests an available alternative or continues with remaining items.
- If customer authentication expires (`ProviderAuthError`), the agent returns an `AUTH_EXPIRED` signal and prompts the customer with a direct `/connect` re-authentication link.
- If a transient network glitch occurs, the WhatsApp adapter provides a friendly retry prompt while preserving basket integrity.
- Under no circumstances is a failed, rejected, or unverified action reported as successful to the customer.

## Security and release rules

- Zero provider secrets, OAuth tokens, personal addresses, or customer phone numbers in frontend code, client bundles, logs, or repository commits.
- All dynamic OAuth tokens are encrypted at rest using AES-GCM via `DATA_ENCRYPTION_KEY` in private PostgreSQL storage (`backend/database.py`).
- `CHECKOUT_MODE=review` is the default safe mode: allows full live catalogue queries, inventory checks, and real cart mutations while stopping before chargeable order placement.
- `CHECKOUT_MODE=live` is enabled only for authorized production orders with verified payment triggers.

## Migration status

- **Complete**: Replaced legacy 12-state FSM (`backend/intent/`) with autonomous Gemini ReAct agent engine (`GroceryAgentEngine`, `SwiggyAgentTools`).
- **Complete**: Local browser OAuth bridge (`/connect`, `/auth/callback`) with numeric customer ID support.
- **Complete**: Dynamic UPI QR and payment link generation (`generateUPIQR: True`).
- **Complete**: Deterministic fail-closed anti-hallucination verification guard.
- **Verified**: 258/258 pytest suite passing green (100%).
- **Verified**: Next.js 16 production build passing cleanly.
- **Verified**: ESLint passing with 0 errors and 0 warnings.
