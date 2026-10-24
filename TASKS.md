# TASKS.md — Active Implementation Checklist

## Current Milestone: V2 Concierge Realignment & Bloat Purge
**Goal:** Eliminate 4 months of defensive bloat and split-brain architecture, slim down `tools.py` and `engine.py`, fix the 9 runtime bugs in commerce/channels, realign test suites to real customer flows, and achieve verified 0-exit with raw terminal proof.

---

## Phase 1: Single Source of Truth Documentation & Real Infrastructure Enforcement
- [x] **Task 1.1:** Consolidate master requirements into root [PRD.md](file:///d:/Grocer/PRD.md) and delete `GROCER_V2_MASTER_SPEC.md`.
  - _Verification:_ `PRD.md` is complete; `GROCER_V2_MASTER_SPEC.md` deleted.
- [x] **Task 1.2:** Consolidate technical blueprint into root [ARCHITECTURE.md](file:///d:/Grocer/ARCHITECTURE.md) and delete `docs/TARGET_ARCHITECTURE_V1.md`.
  - _Verification:_ `ARCHITECTURE.md` contains full Mermaid blueprint and subsystem specs; `docs/TARGET_ARCHITECTURE_V1.md` deleted.
- [x] **Task 1.3:** Maintain root design rules in [DESIGN.md](file:///d:/Grocer/DESIGN.md) and domain definitions in [GLOSSARY.md](file:///d:/Grocer/GLOSSARY.md).
  - _Verification:_ Both files match tokens and V2 terminology.
- [x] **Task 1.4:** Enforce Live Supabase and Live Swiggy MCP across the stack:
  - Auto-load `.env` in `backend/tests/conftest.py`.
  - Remove `127.0.0.1` and `_local_dsn()` in `backend/tests/suites/helpers.py`; bind strictly to live Supabase Postgres.
  - Remove `127.0.0.1:5432` socket ping from `verify.ps1`; verify live Supabase connectivity via asyncpg.
  - Default `COMMERCE_ADAPTER_TYPE` to `swiggy_mcp` in `backend/config.py` and `backend/integrations/commerce/factory.py`.
  - _Verification:_ Live Supabase ping returns `SELECT 1 = 1` and `COMMERCE_ADAPTER_TYPE` resolves to `SwiggyMCPAdapter`.

---

## Phase 2: Engine Consolidation & Tools Slimdown
- [x] **Task 2.1:** Clean `backend/agent/engine.py` into a lean single-turn coordinator:
  - Purged unused imports and dead bouncer references.
  - Wires incoming messages cleanly: 50ms fast button router -> single-turn Gemini brain -> deterministic `composite_cart` execution -> receipt card.
  - _Verification:_ `verify.ps1` exits 0 with 127/127 tests passing; zero obsolete state properties remain.
- [x] **Task 2.2:** Slim down `backend/agent/tools.py` and purge dead code:
  - Deleted `AddedItem` dead model and `suggest_grocery_items` bouncer.
  - Removed `_catalog_cache` to enforce live Swiggy MCP dark store searches under Universal Non-Negotiable #1.
  - Delegated basket operations directly to `CompositeCartManager` (`backend/agent/composite_cart.py`).
  - _Verification:_ `verify.ps1` exits 0 with 127/127 tests passing; clean passthroughs for all 20 Swiggy MCP tools.

---

## Phase 3: The 9 Runtime Commerce & Channels Bugs
- [x] **Task 3.1:** Fix Store Closed Masking in `backend/agent/button_router.py:53-64`:
  - Stop generic exception swallowing; explicitly check store status and inform the customer instead of clearing approval and claiming "basket is empty".
- [x] **Task 3.2:** Fix False Payment Pending in `backend/agent/button_router.py:168`:
  - Route `check_payment` to `commerce.check_payment_status` instead of `get_delivery_status`. Handle real status transitions cleanly.
- [x] **Task 3.3:** Fix Address Selection Sync in `backend/agent/button_router.py:304`:
  - Call `await commerce.update_cart(address_id=addr_id)` upon address tap to re-price, verify stock, and recalculate delivery fees.
- [x] **Task 3.4:** Fix Meta 1024-Char Limit in `backend/channels/whatsapp_formatter.py:23-35`:
  - Compute total message length including the appended UPI deep link *before* truncating, preventing Meta HTTP 400 delivery drops.
- [x] **Task 3.5:** Purge Hardcoded `swiggy@icici` VPA:
  - Remove fake fallback from `backend/agent/checkout_executor.py:295`; raise or handle missing gateway VPA gracefully.
- [x] **Task 3.6:** Fix Missing `paas_id` in `backend/agent/engine.py`:
  - Pass distinct `paas_id` from checkout outcome and session to `payment_poller.start_polling` instead of reusing `order_id`.
- [x] **Task 3.7:** Harden `backend/channels/payment_poller.py`:
  - Clean up finished tasks from `_active_tasks` to prevent memory leaks; persist session state to Postgres on payment confirmation; call `commerce.confirm_order`.
- [x] **Task 3.8:** Fix Fragile Substring Matching in `backend/integrations/commerce/cart_parsers.py:89-101`:
  - Prevent "Free delivery discount" from being classified as a positive delivery fee.
- [x] **Task 3.9:** Add Explicit Dark Store Error Classification in `backend/integrations/commerce/swiggy_client.py:98-117`:
  - Map `STORE_CLOSED`, `UNSERVICEABLE_LOCATION`, and `POD_OFFLINE` to structured exceptions.

---

## Phase 4: Webhook Reply Persistence & Test Suite Realignment
- [x] **Task 4.1:** Fix Outgoing WhatsApp DB Persistence in `backend/channels/whatsapp.py`:
  - Ensure outgoing webhook replies insert records into `whatsapp_messages` table with `reply_to = message.id` to fix 48 `NoneType` unpack errors in E2E tests.
- [x] **Task 4.2:** Retire Obsolete Bouncer Tests in `backend/tests/suites/`:
  - Prune tests in `planning_repairs.py` and `recipe_and_budgets.py` that assert on deleted bouncers (`item_drop_guard`, `claim_check`) or expect intermediate address questions.
- [x] **Task 4.3:** Realign `backend/tests/test_whatsapp_postgres_e2e.py` around Real Customer Flows:
  - Assert on end-to-end customer outcomes (webhook idempotency, button fast path, basket additions, coupon optimization, UPI link generation).
- [x] **Task 4.4:** Closed-Loop Terminal Proof:
  - Run `.\verify.ps1`. Confirm 100% test pass rate and 0 exit code with raw terminal output.
