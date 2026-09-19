# GROCER Engineering Contract

Read `ARCHITECTURE.md` and `docs/SWIGGY_MCP_API.md` before modifying code.

## 1. Product Boundary

GROCER is an English-first WhatsApp grocery replenishment agent for Swiggy Instamart.
Its job is to help customers order groceries effortlessly from their local dark store directly inside WhatsApp.

Never build:
- Dark-store operator dashboards or inventory management systems;
- Cross-marketplace aggregators or competitor price comparison engines;
- Browser-owned commerce state;
- Silent substitutions or autonomous unconfirmed checkouts.

## 2. Active Architecture

```text
Meta WhatsApp Cloud API
        ↓
FastAPI Webhook (/api/whatsapp/webhook)
        ↓
GroceryAgentEngine (backend/agent/engine.py)
  ├── Autonomous ReAct loop (Gemini 2.0 / 3.5 Flash Lite)
  ├── SwiggyAgentTools (backend/agent/tools.py)
  │     ├── get_saved_addresses (resolves user delivery addresses)
  │     ├── select_delivery_address (switches active delivery destination)
  │     ├── search_products (live store catalogue inventory search)
  │     ├── get_cart (reads verified totals, fees & line items)
  │     ├── update_cart (sets variants with mandatory spin_id & sku_id)
  │     ├── clear_cart (empties cart when requested)
  │     ├── checkout (server-side gated, generateUPIQR: True)
  │     └── track_order (live delivery status, driver info, and ETA)
  ├── Deterministic fail-closed guard (blocks hallucinated order success)
  └── Interactive quick-reply buttons ([Confirm Order], [Change Items])
        ↓
CommercePort / SwiggyMCPAdapter (backend/integrations/commerce/)
        ↓
Swiggy Instamart Live MCP Gateway (https://mcp.swiggy.com/im)
```

## 3. Language & Safety Invariants

1. **Deterministic Enforcement**:
   - The LLM interprets customer language and proposes actions; deterministic Python enforces hard constraints, calculates prices, blocks unauthorized mutations, and verifies outcomes.
2. **Explicit Confirmation Before Checkout**:
   - Checkout is strictly server-side gated (`is_user_confirmed: True`). The model may only invoke `checkout` after explicit customer approval (e.g. "Confirm", "Yes", or tapping `[Confirm Order]`).
3. **Fail-Closed Anti-Hallucination Guard**:
   - If checkout fails or returns `PAYMENT_PENDING`, deterministic regex patterns (`_ORDER_SUCCESS_PATTERNS`) inspect model output. The agent will never falsely claim or imply an order was placed without completed payment.
4. **Token Security**:
   - Swiggy customer OAuth tokens are encrypted at rest using Fernet / AES-GCM in PostgreSQL (`grocer_internal.oauth_tokens`). Never expose tokens in logs, URLs, or frontend state.
5. **Zero-Redundancy Receipts**:
   - Basket line items must be presented exactly once inside a clean receipt card. Never repeat item names in the lead-in text.

## 4. Quality Gate

Always run and verify before committing changes:

```bash
pytest backend/tests
npm run lint
npm run build
```
