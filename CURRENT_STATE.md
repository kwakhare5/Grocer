# GROCER current state

> Verified locally & live on WhatsApp: 2026-09-18
> Branch: `dev-live-test` (migrating to `main`)
> Runtime: Autonomous Gemini ReAct agent engine (`backend/agent/`)

## What is complete

- **Autonomous Gemini ReAct Conversation Engine** (`backend/agent/engine.py` & `backend/agent/tools.py`):
  - Equipped with typed Swiggy MCP tools (`search_products`, `update_cart`, `get_cart`, `get_saved_addresses`, `clear_cart`, `checkout`).
  - Driven by `gemini-3.5-flash-lite` with smart defaults for staples and multi-item recipe/kit deduction.
- **Live Pune Dark Store Proof** (Verified on physical smartphone via WhatsApp `+1 555 663-1707`):
  - User requested: *"i wanna make pasta i want grociers uner 1500"*.
  - Agent autonomously resolved the delivery address at *Kingsbury, Charholi Budruk, Pune*, deduced 7 pasta kit items, checked Pune dark store inventory, respected the budget limit, and added all items to live Swiggy Instamart cart ID `8c64c847` (₹506 total).
  - Delivered an itemized breakdown and interactive WhatsApp confirmation controls.
- **Dynamic UPI QR & Payment Links** (`backend/agent/tools.py`, `backend/integrations/commerce/swiggy_adapter.py`):
  - Integrated `generateUPIQR: True` in checkout calls.
  - Returns `bridge_url` / `upi_intent_url` to the customer on WhatsApp in `PAYMENT_PENDING` state, enabling one-tap UPI payments (`upi://pay?...`).
- **Deterministic Fail-Closed Anti-Hallucination Guard** (`backend/agent/engine.py`):
  - Enforces server-side checkout confirmation gating (`is_user_confirmed: True`).
  - Regex pattern classification (`_ORDER_SUCCESS_PATTERNS`, `_explains_failure`) blocks premature or hallucinated order placement claims on provider errors, overriding responses with honest error explanations and payment triggers.
- **Browser OAuth Reconnect Bridge** (`backend/api/oauth.py`):
  - Provides `GET /connect` and `GET /auth/callback` allowing mobile WhatsApp users to re-authenticate with Swiggy directly via browser.
  - Resolved Swiggy numeric customer ID hashing in `backend/integrations/commerce/swiggy_client.py`.
- **Clean Architecture & Legacy Retirement**:
  - Completely retired the legacy 12-state FSM (`backend/intent/`) and obsolete tests.
  - Extracted database connection pooling cleanly to `backend/database.py`.

## Verified quality gates

- `pytest backend/tests`: **258 passed** in 4.73s (100% green).
- `npm run lint`: **passed** with 0 errors and 0 warnings.
- `npm run build`: **passed** with Next.js 16 production build (all static and dynamic API routes compiled cleanly).

## Next release gate

Deploy the hardened backend service to Render (`render.yaml`), verify the live production Meta WhatsApp webhook routing to `GroceryAgentEngine`, and complete a real UPI payment transaction on a physical device.
