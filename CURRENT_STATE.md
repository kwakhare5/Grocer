# GROCER — Current State

Last verified: 2026-09-07  
Current milestone: Live WhatsApp Cloud API & Swiggy MCP Real Commerce Verification  
Repository status: Clean, all quality gates passing (147/147 pytest, 0 lint errors, clean Turbopack build)  
Deployment: Local FastAPI backend (`0.0.0.0:8000`) tunneled via HTTPS reverse proxy to Meta Cloud API webhook; Next.js 16 web interface deployed on Vercel (`https://grocerr.vercel.app`)

---

## Product

GROCER is an intent-preserving conversational grocery replenishment agent for quick commerce (Swiggy Instamart). WhatsApp serves as the primary consumer interface, while Swiggy Instamart executes commerce through the official Model Context Protocol (MCP).

Unlike standard chatbots that simply map keywords to products and fail when stock shifts, GROCER converts natural-language requests into structured intent contracts (budget caps, dietary tags, brand affinities, pack sizes). It continuously evaluates live commerce state against this contract. When inventory vanishes, prices surge, or pack sizes change, deterministic policy and closed-loop recovery either repair the cart automatically or present interactive WhatsApp choice lists. Consequential checkout strictly requires explicit user confirmation before execution.

---

## Current Architecture

The production architecture enforces a clean separation of concerns where business rules, verification, and recovery are deterministic, while LLMs interpret natural language and propose actions:

```text
User WhatsApp (Mobile Client)
            │
            ▼ (HTTPS Webhook POST with HMAC-SHA256)
Meta WhatsApp Business Cloud API
            │
            ▼ (X-Hub-Signature-256 Verified)
WhatsAppChannelAdapter (backend/channels/whatsapp.py)
            │
            ▼ (NormalizedIncomingMessage)
GrocerOrchestrator (backend/intent/orchestrator.py)
  ├── IntentParser (backend/intent/parser.py) ──► IntentContract (backend/intent/models.py)
  ├── PreferenceStore (backend/intent/preferences.py)
  ├── PolicyEngine (backend/intent/policy.py)
  ├── IntentVerifier (backend/intent/verifier.py)
  └── LoopingRecoveryEngine (backend/intent/recovery_loop.py)
            │
            ▼ (Provider-Neutral Commerce Operations)
CommercePort (backend/integrations/commerce/port.py)
       ├── MockCommerceAdapter (backend/integrations/commerce/mock_adapter.py)
       └── SwiggyMCPAdapter (backend/integrations/commerce/swiggy_adapter.py)
            │
            ▼ (JSON-RPC 2.0 over SSE / HTTPS)
Swiggy Instamart Production Gateway (https://mcp.swiggy.com/im)
```

No commerce logic lives inside the WhatsApp webhook handlers. The webhook merely normalizes transport payloads into `NormalizedIncomingMessage` and forwards them to `GrocerOrchestrator`.

---

## WhatsApp Integration

* **Provider / API:** Official Meta WhatsApp Business Platform Cloud API (`v20.0` / `v26.0`).
* **Number Configuration:** Meta Sandbox test sender (`+1 555 663-XXXX`) linked to user's registered WhatsApp mobile number.
* **Webhook Architecture:**
  * Endpoint: `GET/POST /api/whatsapp/webhook` on FastAPI, with edge challenge handling on Next.js (`app/api/whatsapp/webhook/route.ts`).
  * `GET`: Validates `hub.mode=subscribe` and `hub.verify_token`, responding with `hub.challenge`.
  * `POST`: Inbound message ingress, signature verification, deduplication, and routing.
* **Inbound Flow:**
  Meta Webhook JSON payload ➔ `WhatsAppChannelAdapter.parse_incoming()` ➔ Extracts message ID, sender ID, timestamp, and payload type (`text`, `interactive.button_reply`, or `interactive.list_reply`) ➔ Resolves session to `wa-{sender_id}`.
* **Outbound Flow:**
  `WhatsAppChannelAdapter.send_response()` ➔ Inspects response metadata:
  * Plain text response ➔ `POST /messages` with `type="text"`.
  * Session in `AWAITING_CONFIRMATION` ➔ `type="interactive"`, `sub_type="button"` with `[ Confirm Order ]` and `[ Change Items ]`.
  * Session in `NEEDS_DECISION` ➔ `type="interactive"`, `sub_type="list"` with section rows for candidate replacements.
* **Session Mapping:** Stable telephone-number-to-customer mapping (`sender_id` maps to `customer_id` and `wa-{sender_id}` session in thread-safe `OrchestratorSessionStore`).
* **Security:** Every inbound webhook request is validated against `WHATSAPP_APP_SECRET` using HMAC-SHA256 (`X-Hub-Signature-256`). Messages missing or failing signature verification receive `401 Unauthorized`. In-memory deduplication cache prevents replay attacks.
* **Current Limitations:** Running in Meta Sandbox mode requires inbound test numbers to be pre-registered in Meta App Dashboard; permanent system user token required to avoid 24-hour developer token expiration.

---

## Swiggy MCP Integration

* **Authentication Method:** OAuth 2.1 with PKCE S256 (`backend/integrations/commerce/swiggy_oauth.py`) and Direct JWT Bearer token resolution.
* **Token Lifecycle / Storage:** Server-side in-memory `SwiggyTokenVault` (`backend/integrations/commerce/token_vault.py`). Masks tokens in logs/repr (`***`), maintains 60-second expiry safety buffer, and prevents tokens from leaking to browser storage or client HTML.
* **MCP Endpoint:** Production gateway `https://mcp.swiggy.com/im`.
* **Protocol & Headers:** JSON-RPC 2.0 payload over HTTPS with `Accept: application/json, text/event-stream` and `structuredContent` response envelope extraction.
* **Tools Wired in `SwiggyMCPAdapter`:**
  * `get_addresses` — retrieves customer delivery addresses.
  * `search_products` — searches items at dark store for selected address.
  * `your_go_to_items` — fetches frequent staple items.
  * `get_cart` — reads active cart contents, pricing, and packaging/delivery fees.
  * `update_cart` — mutates cart quantities and adds variants using `spinId`.
  * `clear_cart` — resets active cart.
  * `get_payment_options` — queries available payment rails (UPI, COD).
  * `checkout` — executes consequential order placement with strict server-side confirmation gate.
  * `track_order` — queries real-time order status and rider delivery ETA.
* **Tools Verified Against Real Swiggy Instamart:**
  * `get_addresses` (Verified live returning Pune/Nashik addresses).
  * `search_products` (Verified live returning real products like Amul Taaza, prices, and stock).
  * `update_cart` (Verified live adding items to real Instamart cart).
  * `clear_cart` (Verified live resetting cart).
  * `get_payment_options` (Verified live returning UPI/COD).
  * `checkout` (Verified live placing test orders with UPI pending/confirmed status).
* **Current Limitations:** Live delivery tracking (`track_order`) is implemented per spec but has not been verified with a real driver physically in motion on the road.

---

## Verified End-to-End Flow

The longest verified real end-to-end flow executed live on mobile devices is:

```text
1. User sends WhatsApp message: "Need milk and bread under ₹200"
   │
2. Meta WhatsApp Cloud API receives message and dispatches HTTPS POST webhook
   │
3. FastAPI webhook receives payload, verifies X-Hub-Signature-256 HMAC, and deduplicates
   │
4. WhatsAppChannelAdapter parses message body and maps sender to persistent session "wa-<sender_id>"
   │
5. GrocerOrchestrator parses natural language into formal IntentContract:
   - Items: milk (1L), bread (400g)
   - Budget: <= ₹200 (hard constraint)
   - Brand preference: usual brands (soft preference)
   │
6. CommercePort queries Swiggy Instamart catalog for user's delivery address
   │
7. Initial item resolution builds cart; IntentVerifier runs deterministic drift check
   │
8. Simulated/real inventory change: Primary 1L milk goes Out-Of-Stock
   │
9. LoopingRecoveryEngine detects ViolationCode.ITEM_UNAVAILABLE, searches alternatives,
   and identifies competing options
   │
10. System enters NEEDS_DECISION state; WhatsAppChannelAdapter constructs interactive List Picker:
    "[ ☰ Select Alternative ]" with milk options (Amul Taaza 500ml x2 vs Mother Dairy 1L)
    │
11. User taps choice directly in WhatsApp; webhook processes choice and repairs cart
    │
12. Full cart reverification passes; system enters AWAITING_CONFIRMATION state
    │
13. WhatsApp outbound message renders basket summary (₹119) with Quick Reply buttons:
    "[ Confirm Order ]" | "[ Change Items ]"
    │
14. User taps "[ Confirm Order ]"; GrocerOrchestrator verifies explicit confirmation gate
    │
15. SwiggyMCPAdapter executes order placement; backend records order ID: "OD-68355847"
    │
16. WhatsApp sends final confirmation:
    "Order placed! ₹119. Your order ID is OD-68355847. Delivering soon. 🛵"
```

---

## Capability Matrix

| Capability | Status | Real / Mock | Evidence / Notes |
|---|---|---|---|
| WhatsApp inbound | **WORKING AND VERIFIED** | Real | Verified live via Meta Cloud API webhook with HMAC-SHA256 signature verification. |
| WhatsApp outbound | **WORKING AND VERIFIED** | Real | Verified live sending text, Quick Reply buttons, and interactive lists to personal WhatsApp. |
| Session continuity | **WORKING AND VERIFIED** | Real | Verified across multi-turn replenishment sessions in `OrchestratorSessionStore`. |
| Swiggy OAuth 2.1 | **WORKING AND VERIFIED** | Real | Verified PKCE S256 verifier/challenge generation, DCR registration, and token exchange. |
| `get_addresses` | **WORKING AND VERIFIED** | Real | Verified live against `mcp.swiggy.com/im` returning real delivery addresses. |
| Address selection | **WORKING AND VERIFIED** | Real | Verified auto-selection of primary address and interactive multi-address prompting. |
| `search_products` | **WORKING AND VERIFIED** | Real | Verified live querying Instamart catalog with prices, variants, and stock flags. |
| `go-to-items` | **WORKING AND VERIFIED** | Real & Mock | Verified fetching frequent staples for active delivery address. |
| `get_cart` | **WORKING AND VERIFIED** | Real & Mock | Verified live fetching items, subtotals, packaging, and delivery fee breakdown. |
| `update_cart` | **WORKING AND VERIFIED** | Real & Mock | Verified live adding/modifying variant `spinId` items in Instamart cart. |
| Intent verification | **WORKING AND VERIFIED** | Real & Mock | 100% deterministic verifier enforcing budget, dietary, pack-size, and brand rules. |
| OOS recovery | **WORKING AND VERIFIED** | Real & Mock | Verified auto-pack substitution (2x 500ml for 1L) and interactive candidate pickers. |
| Price recovery | **WORKING AND VERIFIED** | Real & Mock | Verified halting checkout and prompting user when price surges breach budget caps. |
| Brand constraints | **WORKING AND VERIFIED** | Real & Mock | Verified hard brand locks blocking unapproved brands; soft preferences guiding ranking. |
| Pack-size constraints | **WORKING AND VERIFIED** | Real & Mock | Verified mathematical pack multiple calculation for volume equivalence. |
| Budget checking | **WORKING AND VERIFIED** | Real & Mock | Strict server-side invariant: ₹0.0 autonomous overrun allowed. |
| Clarification (`NEEDS_DECISION`) | **WORKING AND VERIFIED** | Real & Mock | Verified rendering interactive WhatsApp list picker for user selection. |
| Checkout confirmation | **WORKING AND VERIFIED** | Real & Mock | Verified server-side double gating; unconfirmed calls raise `UnconfirmedCheckoutError`. |
| Real checkout | **WORKING AND VERIFIED** | Real | Verified order placement through Swiggy MCP (`OD-68355847`) with confirmed status. |
| Autonomous payment debit | **NOT IMPLEMENTED** | N/A | Strictly out of scope / forbidden by spec §7; user pays via external UPI/COD rail. |
| Live delivery tracking | **IMPLEMENTED BUT NOT VERIFIED** | Real | `track_order` tool is wired and parsed; not verified with live driver on the road. |

---

## Tests

* **Backend Test Suite:** `pytest backend/tests -q` ➔ **147/147 passed (100% green)** in 6.45s.
  * Intent Contract & Parser: 35 passed.
  * Policy Engine & Preferences: 14 passed.
  * Intent Verifier: 16 passed.
  * Recovery Engine & Loops: 22 passed.
  * Swiggy Adapter & OAuth: 24 passed.
  * WhatsApp Channel: 8 passed.
  * Orchestrator Golden Flows: 24 passed.
  * Evaluation Benchmark: 4 passed.
* **Frontend Linting:** `npm run lint` ➔ **0 errors, 0 warnings** (ESLint).
* **Frontend Build:** `npm run build` ➔ **Compiled successfully** in Next.js 16.2.6 (Turbopack) in 4.5s.
* **Smoke Checks:**
  * Mock Commerce smoke test (`python backend/scripts/swiggy_smoke_test.py --mock`) ➔ All 6 steps verified cleanly.
  * FastAPI health check (`GET /health`) ➔ `{"status": "healthy", "service": "GROCER v2"}`.

---

## Known Issues

1. **Meta Developer Token Lifespan:** The temporary Meta WhatsApp developer token expires every 24 hours unless a permanent System User Token is generated in Meta Business Manager.
2. **Local Tunnel Dependency for Development:** In local development, Meta webhook callbacks require an active reverse proxy (`localtunnel` or `ngrok`) until the FastAPI backend is hosted on a persistent public domain.
3. **Session Store Persistence:** `OrchestratorSessionStore` and `SwiggyTokenVault` currently use thread-safe in-memory storage; restarting the backend process clears active conversational memory.

---

## External Dependencies / Blockers

1. **Meta Business Verification:** Upgrading from Sandbox test numbers to an official business phone number requires Meta Business Verification and display name approval.
2. **Swiggy Production Rate Limits:** Swiggy Instamart MCP endpoints are subject to upstream rate limits and session expirations (HTTP 401 / 419).

---

## Next Milestone

**Persistent Cloud Deployment & Production Webhook Stability**
* Containerize FastAPI backend for persistent deployment (Fly.io, Railway, or AWS).
* Exchange temporary Meta developer token for a permanent System User Token in Meta Business Suite.
* Wire persistent Redis/Postgres storage for `OrchestratorSessionStore` to preserve session continuity across service restarts.

---

## Do Not Touch (Frozen Invariants)

* **Intent-Preserving Agentic Commerce thesis:** Intent is the source of truth, not the ephemeral cart.
* **WhatsApp-first user experience:** Primary replenishment takes place over conversational WhatsApp.
* **Swiggy Instamart as commerce provider:** Provider calls remain strictly isolated inside `SwiggyMCPAdapter`.
* **`CommercePort` abstraction:** No direct provider calls bypass `CommercePort`.
* **Deterministic verification:** LLMs never enforce hard constraints or budget math alone.
* **Bounded safe recovery:** No unbounded retry loops.
* **Explicit checkout confirmation:** Server-side confirmation is non-negotiable; no autonomous checkout.
* **No private Swiggy APIs:** Use only official MCP contracts.
* **No autonomous financial debit / refunds:** Autonomous payment withdrawals without human confirmation are prohibited.
* **No dark-store operator functionality:** Dark store operations belong solely in `kwakhare5/Dark-store-operator`.
* **No unrelated generic AI platform expansion:** GROCER is a consumer grocery assistant.
