# GROCER — Engineering Worklog

This document provides historical engineering context for completed milestones. It records what was built, real integrations verified, obstacles faced, and resolutions.

---

## 2026-09-07 — Live Meta WhatsApp Cloud API & Swiggy MCP Real Commerce Verification

### 1. Milestone Overview
Completed the live integration and end-to-end verification of the official Meta WhatsApp Business Platform Cloud API alongside the live Swiggy Instamart Model Context Protocol (MCP) commerce adapter. Verified real bidirectional conversation on mobile with out-of-stock recovery, interactive WhatsApp lists/buttons, and server-gated order placement.

### 2. What Was Implemented
1. **Decoupled Channel Transport Layer (`backend/channels/`):**
   * Abstracted channel ingress/egress from domain orchestration via `BaseChannelAdapter`.
   * Created unified data models: `NormalizedIncomingMessage`, `NormalizedOutgoingResponse`, and `InteractiveAction`.
   * Built `WhatsAppChannelAdapter` with support for Meta Graph API v20.0, HMAC-SHA256 signature verification (`X-Hub-Signature-256`), in-memory message deduplication, interactive list message formatting (up to 10 rows), and interactive button replies (up to 3 buttons).
2. **Webhook Verification & Proxying (`backend/api/whatsapp.py` & `app/api/whatsapp/webhook/route.ts`):**
   * Implemented `GET /api/whatsapp/webhook` to handle Meta hub challenge verification (`hub.mode`, `hub.verify_token`, `hub.challenge`).
   * Implemented `POST /api/whatsapp/webhook` with strict HMAC signature check and dispatch to `GrocerOrchestrator`.
   * Provided Next.js edge route proxy with self-contained verification challenge handling for seamless Vercel integration.
3. **Swiggy MCP Protocol Hardening (`backend/integrations/commerce/swiggy_adapter.py`):**
   * Configured official Builders Club headers: `Accept: application/json, text/event-stream`.
   * Handled SSE chunk decoding and structured content extraction (`structuredContent` payload unwrapping).
   * Integrated server-side token resolution via `SwiggyTokenVault`.
4. **Interactive Clarification & Confirmation Flows:**
   * Bound `NEEDS_DECISION` state to WhatsApp interactive lists (`[ ☰ Select Alternative ]`).
   * Bound `AWAITING_CONFIRMATION` state to native quick reply buttons (`[ Confirm Order ]` / `[ Change Items ]`).
   * Maintained double-gated server authorization preventing unconfirmed checkout.

### 3. Important Files Changed / Created
* `backend/channels/base.py` — Channel abstraction base class.
* `backend/channels/models.py` — Normalized channel schemas.
* `backend/channels/whatsapp.py` — Meta WhatsApp Cloud API adapter.
* `backend/api/whatsapp.py` — FastAPI webhook endpoints.
* `app/api/whatsapp/webhook/route.ts` — Next.js webhook edge proxy.
* `backend/integrations/commerce/swiggy_adapter.py` — Swiggy MCP protocol client.
* `backend/intent/orchestrator.py` — Multi-turn conversational flow.
* `backend/tests/test_whatsapp_channel.py` — Channel test suite.

### 4. Tests Performed
* `pytest backend/tests -q`: 147/147 tests passed (100% green).
* `npm run lint`: 0 ESLint errors, 0 warnings.
* `npm run build`: Next.js 16.2.6 (Turbopack) production build passed cleanly.
* `swiggy_smoke_test.py --mock`: All 6 commerce stages passed without fault.

### 5. Real Integrations Verified
* **Meta WhatsApp Cloud API Sandbox (`+1 555 663-XXXX`):** Live messaging verified with user's mobile device.
* **Swiggy Instamart Gateway (`https://mcp.swiggy.com/im`):** Live address lookup (Nashik/Pune), catalog search, and cart mutation verified using authenticated customer session (`SwiggyTokenVault`).
* **Consequential Checkout:** Verified explicit checkout resulting in confirmed order ID (`OD-68355847`).

### 6. Problems Encountered & Solutions
* **Issue:** Meta webhook POST verification failed with `401 Unauthorized` during automated test runs once live `WHATSAPP_APP_SECRET` was populated in `.env`.
  * **Solution:** Updated the webhook test fixture in `test_whatsapp_channel.py` to dynamically compute valid HMAC-SHA256 signatures when `default_whatsapp_adapter.app_secret` is present, verifying authentic signature checking under both development and production configurations.
* **Issue:** Meta Cloud API limits interactive quick reply buttons to a maximum of 3 items, causing payload rejection when presenting multiple substitution candidates.
  * **Solution:** Wired dynamic layout switching in `WhatsAppChannelAdapter`: scenarios with 2 options render as quick reply buttons, while scenarios with 3–10 candidates automatically render as an interactive List Picker (`[ ☰ Select Alternative ]`).
* **Issue:** Swiggy MCP returns responses as Server-Sent Events (SSE) or with non-standard `structuredContent` envelopes that failed standard JSON unpacking.
  * **Solution:** Added headers `Accept: application/json, text/event-stream` and unwrapped `structuredContent` directly into the normalized result dictionary.

### 7. Known Limitations
* Meta developer access tokens expire after 24 hours unless exchanged for a permanent System User Token in Meta Business Suite.
* Webhook ingestion in local development depends on a running reverse tunnel (`localtunnel` or `ngrok`).
* Live driver tracking in `track_order` is implemented per schema but has not been verified with a live physical rider en route.

### 8. Recommended Next Milestone
* Containerize the FastAPI backend and deploy to persistent cloud infrastructure (e.g., Fly.io or AWS).
* Generate a permanent Meta System User token.
* Connect persistent state storage (Redis/Postgres) to preserve conversational session memory across container restarts.
