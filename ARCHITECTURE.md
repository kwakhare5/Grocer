# Grocer Architecture

Updated: 2026-10-10. Authoritative technical specification for the Grocer WhatsApp replenishment assistant, detailing the conversational reasoning pipeline, deterministic safety boundaries, and Swiggy Instamart Model Context Protocol (MCP) integration.

---

## 1. Request Lifecycle & Pipeline

```text
Meta WhatsApp Cloud Webhook
  → Next.js Edge proxy (https://grocerr.vercel.app/api/whatsapp/webhook)
  → FastAPI HMAC-SHA256 signature verification & rapid burst debouncing
  → PostgreSQL inbound_messages (durable commit before HTTP 200 ACK)
  → Customer-serialized worker (per-phone asyncio.Lock)
  → GroceryAgentEngine (Gemini 3.5 Flash-Lite ReAct loop)
      ├── Address Sanitizer: resolves destination as Label (Area, City)
      ├── Intent Preservation: atomic multi-turn basket edits (manage_basket)
      ├── Replenishment Engine: cadence checks via grocer_internal.replenishment
      └── Deterministic Guards: budget caps, hesitation holds, negation checks
  → CommercePort (SwiggyMCPAdapter or MockCommerceAdapter)
  → PostgreSQL outbound_messages (3-attempt staged delivery retry)
  → Meta WhatsApp Cloud API outbound dispatch
```

---

## 2. Customer Identity, OAuth & Address Privacy

- **Customer Identity**: The signed WhatsApp sender provides a verified India E.164 phone number (`+91...`). Customer identities are hashed and mapped pseudonymously.
- **Single-Use Connect Tickets**: WhatsApp requests generate 10-minute single-use tickets binding the OAuth flow directly to that phone identity, preventing unauthorized account linking from arbitrary browser sessions.
- **Address Privacy Boundary**: Swiggy address responses are parsed to extract structured `area` and `city` tokens. Output representations strictly format as `Label (Area, City)` (e.g., `Home (Viman Nagar, Pune)` or `Office (Baner, Pune)`). Flat numbers, floor numbers, and society details are stripped before reaching language models, logs, receipts, or chat UI.

---

## 3. Conversational Reasoning & Intent Preservation

- **Gemini 3.5 Flash-Lite Engine**: Google Gemini acts as the reasoning engine (~1.2s turn latency), handling compound meal requests (decomposing recipes into concrete items), Hinglish vocabulary, and search queries.
- **Intent Preservation**: Rather than wiping state between turns, the engine preserves active shopping items, dietary exclusions, and budget caps across conversational amendments. Edits ("drop sauce, make bread 2") execute atomically without losing previously selected items.
- **Replenishment Cadence**: Consented purchase history is encrypted with Fernet in `grocer_internal.replenishment`. The system computes median repurchase intervals for staples (milk, eggs, bread) and answers restock queries conversationally (`check_replenishment`), accepting user stock corrections ("I have enough milk for 4 days") without mutating the active cart.

---

## 4. Deterministic Safety Guards & Gated Checkout

1. **Hard Budget Ceilings**: The Python layer verifies that total costs (subtotal + delivery + handling fees) do not breach user-specified budget limits (`total <= budget_inr`).
2. **Hesitation Hold**: Words indicating hesitation ("wait", "hold on", "let me think") immediately freeze the cart and suspend checkout without timing out the basket.
3. **Server-Side Gated Checkout**:
   - `CHECKOUT_MODE=review` (default): Simulates checkout review and generates simulated payment QR bridges for safe demonstrations without charging payment methods.
   - `CHECKOUT_MODE=live`: Requires explicit human confirmation ("Confirm") before calling the Swiggy checkout endpoint. Orders generate official UPI payment links with background reconciliation.
4. **Post-Restart Payment Reconciliation**: Handled by `PostgresCheckoutAttemptStore` and background pollers, ensuring that pending payment outcomes survive process restarts and notify the user once resolved.

---

## 5. Persistence & Data Governance

- **Storage**: PostgreSQL (`grocer_internal` schema) stores encrypted OAuth tokens, connect tickets, inbox/outbox queues, checkout attempts, task snapshots, and replenishment history.
- **Data Deletion (`delete my data`)**: Customers sending "delete my data" trigger an immediate cryptographic purge of their conversation history, token vault records, and learned purchase habits.
- **Liveness & Readiness**: `GET /api/ready` validates database connectivity and migration integrity, while `GET /api/health` reports process liveness.
