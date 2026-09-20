# GROCER architecture

> Updated: 2026-09-20
> Status: Autonomous Gemini ReAct agent engine with Ultra-Low Latency, Multi-Turn Self-Healing, and Swiggy Instamart Live MCP integration is active and verified in production.

## Product boundary

GROCER is an English-first WhatsApp grocery replenishment agent for Swiggy Instamart. The landing page (`grocerr.vercel.app`) explains the product and facilitates OAuth reconnection; shopping occurs natively inside WhatsApp (`+1 555 663-1707`). GROCER is not an internal dark-store operations platform, inventory management system, or browser-owned cart.

## Active architecture

```text
Meta WhatsApp Cloud API
        ↓ (Instant <200ms blue ticks via mark_message_read)
Vercel Edge Proxy (/api/whatsapp/webhook)
        ↓ (Fast-Ack HTTP 200 OK + Async HMAC-verified forward)
FastAPI Webhook (/api/whatsapp/webhook on Render)
        ↓ (Per-customer asyncio.Lock concurrency serialization)
GroceryAgentEngine (backend/agent/engine.py)
  ├── Autonomous ReAct loop (Gemini Flash-Lite Latest: ~0.8s generation)
  ├── Persistent HTTP/2 connection pooling with keep-alive (zero handshake latency)
  ├── Automatic self-healing multi-turn history reset (handles Gemini thought-signature 400 errors)
  ├── 6-turn sliding window history pruning & payload compaction
  ├── Concurrent tool execution via asyncio.gather (parallel multi-item search)
  ├── SwiggyAgentTools (backend/agent/tools.py)
  │     ├── search_products (parallel live store catalogue inventory search)
  │     ├── update_cart (adds SKUs, respects stock, budget & min-order thresholds)
  │     ├── get_cart (reads back verified totals, fees & line items)
  │     ├── get_saved_addresses (resolves user delivery addresses)
  │     ├── select_delivery_address (switches active delivery destination)
  │     ├── clear_cart (empties cart when requested)
  │     ├── checkout (server-side gated, generateUPIQR: True)
  │     └── track_order (live delivery status, driver info, and ETA)
  ├── Deterministic fail-closed guard (blocks false order success claims)
  ├── Post-payment polling daemon (_poll_payment_status: checks order every 5s for 60s)
  └── Interactive quick-reply buttons ([Confirm Order], [Change Items])
        ↓
CommercePort / SwiggyMCPAdapter (backend/integrations/commerce/)
        ↓
Swiggy Instamart Live MCP Gateway (https://mcp.swiggy.com/im)
```

## Module boundaries

| Boundary | Responsibility | Source Path |
|---|---|---|
| **WhatsApp Channel** | Verify Meta webhook HMAC signatures, parse incoming payloads, mark messages read (<200ms blue ticks), map sender phone numbers to customer IDs, format and deliver outbound messages up to 4,096 chars, and handle media fallbacks. | `backend/channels/whatsapp.py`, `backend/api/whatsapp.py` |
| **GroceryAgentEngine** | Manage conversational history with 6-turn sliding window pruning, coordinate ReAct tool invocations with Gemini function calling concurrently via `asyncio.gather`, serialize rapid texts with per-customer `asyncio.Lock`, run background payment polling, and enforce fail-closed post-processing guards with self-healing recovery. | `backend/agent/engine.py` |
| **SwiggyAgentTools** | High-signal tool registry exposing typed Swiggy operations to Gemini; computes pre-formatted currency (`₹XX`), exposes store minimum order thresholds and serviceability, and maps tool parameters to `CommercePort` methods. | `backend/agent/tools.py` |
| **CommercePort** | The sole provider-neutral commerce contract defining async methods for address resolution, catalog search, cart mutations, checkout, and tracking. | `backend/integrations/commerce/port.py` |
| **SwiggyMCPAdapter** | Encapsulates Swiggy MCP JSON-RPC transport, payload normalization, error classification, and response parsing. | `backend/integrations/commerce/swiggy_adapter.py`, `swiggy_parsers.py`, `swiggy_client.py` |
| **OAuth Bridge** | Direct browser endpoints (`/connect`, `/auth/callback`) enabling customers to re-authenticate with Swiggy from their mobile browser via reverse proxy or web. | `backend/api/oauth.py`, `backend/integrations/commerce/swiggy_oauth.py` |
| **Token Vault & DB** | Fernet / AES-GCM encrypted persistence of dynamic Swiggy OAuth tokens at rest in PostgreSQL with connection pooling. | `backend/database.py`, `backend/integrations/commerce/token_vault.py` |
| **Keep-Warm Automation** | Scheduled GitHub Actions workflow pinging backend `/health` every 10 minutes to eliminate cold starts on Render. | `.github/workflows/keep_warm.yml` |

## Conversation policy

Free natural English is the primary input. Grocer uses autonomous ReAct reasoning to interpret conversational requests, deduce multi-item recipe kits, and make immediate progress without stalling:

1. **Hybrid Product Resolution**: For basic daily staples (milk, bread, eggs, butter, curd), Grocer selects the standard in-stock variant and adds it directly to the cart. For variant-rich or ambiguous categories (chocolates, biscuits, snacks), Grocer presents 2–3 options with prices and sizes for customer choice.
2. **Multi-Item Batching & Parallel Search**: When a customer requests multiple staples ("bread and eggs"), Grocer fires parallel `search_products` queries concurrently using `asyncio.gather` and adds all items in a single unified `update_cart` turn, slashing turnaround latency to ~3–4 seconds.
3. **Instant Blue Ticks**: Upon webhook receipt, Grocer dispatches `mark_message_read()` in <200ms, providing instant visual acknowledgement on WhatsApp.
4. **Zero-Redundancy Receipts**: Basket summaries are formatted as single, consolidated WhatsApp receipts with line items, subtotal, combined delivery & fees, and grand total. Item names are never repeated in the lead-in text.
5. **Explicit Checkout Authorization**: Once the cart is assembled, Grocer presents the receipt with interactive WhatsApp buttons (`Confirm Order`, `Change Items`). Checkout invocation is server-side gated requiring explicit customer confirmation (`is_user_confirmed: True`).
6. **Dynamic UPI Payment & Autonomous Polling**: When the order is confirmed, Swiggy generates a dynamic UPI QR / payment intent link (`bridge_url` / `upi_intent_url`). Grocer formats this into a one-tap WhatsApp payment link and launches a 60-second background polling daemon that automatically messages the customer the moment UPI payment completes.
7. **Real-Time Order Tracking**: Customers can inquire about in-flight orders ("where is my order?"); Grocer calls `track_order` to report rider status, contact details, and estimated delivery time.

## Safety and deterministic reliability

Deterministic Python code strictly guarantees that the model cannot violate commerce rules or make false claims:

1. **Fail-Closed Anti-Hallucination Guard**: When checkout returns a failure or `PAYMENT_PENDING`, the response is verified against 6 strict regex pattern classes (`_ORDER_SUCCESS_PATTERNS`). If the LLM prematurely claims the order was placed or fails to explain provider errors, the deterministic guard overrides the response with an honest explanation and the actual payment link.
2. **Server-Side Checkout Gating**: `SwiggyAgentTools.checkout` rejects calls where `is_user_confirmed` is not true, preventing unauthorized mutations.
3. **Automatic Self-Healing History Reset**: If Gemini returns an HTTP 400 error due to missing or invalid `thought_signature` fields across multi-turn sessions, `_call_gemini` automatically clears stale history and re-calls with the current user turn in <1s.
4. **Verified Provider State & Pre-Computed Currency**: All totals, item prices, packaging fees, and delivery fees are read back from verified Swiggy Instamart responses and formatted in Python (`₹XX`), eliminating model arithmetic hallucination.
5. **Store Minimum Order & Serviceability Guard**: If dark store order minimums are not met or if delivery is unserviceable, deterministic status flags are surfaced so the user is warned upfront.
6. **Credential Security**: OAuth tokens are encrypted at rest using AES-GCM; secrets and tokens are never exposed in logs, API responses, or frontend state.

## Zero-Docker Serverless Architecture

GROCER does not use Docker in production or development:
- **Frontend**: Serverless Next.js deployed on Vercel Edge.
- **Backend**: Native Python 3.12 Web Service on Render with persistent HTTP/2 connection pooling.
- **Database**: Managed PostgreSQL with AES-GCM encrypted persistence.
- Eliminating Docker container wrapping shaved 800MB from build footprints and eliminated container cold-start delays.

## Test & verification status

All 273 backend unit, contract, and empirical tests pass green in 5.24s. Next.js 16 production build compiles with Turbopack cleanly. ESLint clean with 0 errors/warnings.
