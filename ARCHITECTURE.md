# GROCER architecture

> Updated: 2026-09-18
> Status: Autonomous Gemini ReAct agent engine is the active conversation runtime; verified live with WhatsApp and Swiggy Instamart MCP.

## Product boundary

GROCER is an English-first WhatsApp grocery agent for Swiggy Instamart. The landing page explains the product and facilitates OAuth reconnection; shopping occurs natively inside WhatsApp. GROCER is not an internal dark-store operations platform, inventory management system, or browser-owned cart.

## Active architecture

```text
Meta WhatsApp Cloud API
        ↓
FastAPI Webhook (/api/whatsapp/webhook)
        ↓
GroceryAgentEngine (backend/agent/engine.py)
  ├── Context-aware ReAct reasoning loop (Gemini 3.5 Flash Lite)
  ├── SwiggyAgentTools (backend/agent/tools.py)
  │     ├── search_products (live store catalogue inventory search)
  │     ├── update_cart (adds SKUs, respects stock & budget)
  │     ├── get_cart (reads back verified totals & fees)
  │     ├── get_saved_addresses (resolves user delivery addresses)
  │     ├── clear_cart (empties cart when requested)
  │     └── checkout (server-side gated, generateUPIQR: True)
  ├── Deterministic fail-closed guard (blocks hallucinated order success)
  └── Payment bridge injection (delivers clickable UPI pay links)
        ↓
CommercePort / SwiggyMCPAdapter (backend/integrations/commerce/)
        ↓
Swiggy Instamart Live MCP Gateway (https://mcp.swiggy.com/im)
```

## Module boundaries

| Boundary | Responsibility | Source Path |
|---|---|---|
| **WhatsApp Channel** | Verify Meta webhook HMAC signatures, parse incoming payloads, map sender phone numbers to customer IDs, format and deliver outbound messages. | `backend/channels/whatsapp.py`, `backend/api/whatsapp.py` |
| **GroceryAgentEngine** | Manage conversational history, coordinate ReAct tool invocations with Gemini function calling, format interactive WhatsApp actions, and enforce fail-closed post-processing guards. | `backend/agent/engine.py` |
| **SwiggyAgentTools** | High-signal tool registry exposing typed Swiggy operations to Gemini; maps tool parameters to `CommercePort` methods. | `backend/agent/tools.py` |
| **CommercePort** | The sole provider-neutral commerce contract defining async methods for address resolution, catalog search, cart mutations, and checkout. | `backend/integrations/commerce/port.py` |
| **SwiggyMCPAdapter** | Encapsulates Swiggy MCP JSON-RPC transport, payload normalization, error classification, and response parsing. | `backend/integrations/commerce/swiggy_adapter.py`, `swiggy_client.py` |
| **OAuth Bridge** | Direct browser endpoints (`/connect`, `/auth/callback`) enabling customers to re-authenticate with Swiggy from their mobile browser via reverse proxy or web. | `backend/api/oauth.py`, `backend/integrations/commerce/swiggy_oauth.py` |
| **Token Vault & DB** | AES-GCM encrypted persistence of dynamic Swiggy OAuth tokens at rest in PostgreSQL with connection pooling. | `backend/database.py`, `backend/integrations/commerce/token_vault.py` |

## Conversation policy

Free natural English is the primary input. Grocer uses autonomous ReAct reasoning to interpret conversational requests, deduce multi-item recipe kits, and make immediate progress without stalling:

1. **Smart Defaults for Staples**: When a customer asks for standard goods (e.g., milk, eggs, bread), Grocer searches the live store, selects the standard in-stock variant, and adds it directly to the cart rather than demanding variant clarification.
2. **Recipe & Multi-Item Kits**: Open-ended requests (e.g., "pasta tonight under ₹1,500") trigger automated ingredient deduction, dark-store inventory checks, and cart compilation within the stated budget in a single turn.
3. **Explicit Checkout Authorization**: Once the cart is assembled, Grocer presents a complete summary (items, prices, delivery fee, grand total, and delivery address) with interactive WhatsApp buttons (`Confirm Order`, `Change Items`). Checkout tool invocation is server-side gated requiring explicit customer confirmation (`is_user_confirmed: True`).
4. **Dynamic UPI Payment Completion**: When the order is confirmed, Swiggy generates a dynamic UPI QR / payment intent link (`bridge_url` / `upi_intent_url`). Grocer formats this into a one-tap WhatsApp payment link so the user completes payment securely via UPI.

## Safety and deterministic reliability

Deterministic Python code strictly guarantees that the model cannot violate commerce rules or make false claims:

1. **Fail-Closed Anti-Hallucination Guard**: When checkout returns a failure or `PAYMENT_PENDING`, the response is verified against 6 strict regex pattern classes (`_ORDER_SUCCESS_PATTERNS`). If the LLM prematurely claims the order was placed or fails to explain provider errors, the deterministic guard overrides the response with an honest explanation and the actual payment link.
2. **Server-Side Checkout Gating**: `SwiggyAgentTools.checkout` rejects calls where `is_user_confirmed` is not true, preventing unauthorized mutations.
3. **Verified Provider State**: All totals, item prices, packaging fees, and delivery fees are read back from verified Swiggy Instamart responses, not generated by model inference.
4. **Credential Security**: OAuth tokens are encrypted at rest using AES-GCM; secrets and tokens are never exposed in logs, API responses, or frontend state.

## Migration status

The legacy 12-state FSM and ordinal parsing system (`backend/intent/`) have been completely retired. The autonomous Gemini ReAct engine (`backend/agent/`) is the sole active conversation runtime across both local testing and live WhatsApp webhooks. All 258 backend unit and integration tests pass green.
