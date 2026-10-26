# Grocer v1.0 Session Handoff & Continuity Brief

> **Target Workspace:** `D:\Grocer-v5`  
> **Branch:** `grocer-v1` (Synced with `https://github.com/kwakhare5/Grocer`)  
> **Status:** Phase 0, Phase 1, Phase 2, and Phase 3 Complete (67/67 Tests Green). Ready for Phase 4: 3-Lock Payment Gate & Web Checkout.  

---

## 1. Goal
Build Grocer v1.0 from scratch as a production-grade WhatsApp Swiggy Instamart concierge and account manager. Operates on real dark-store data across all 20 native MCP tools, zero fake mocks, integer paise math, wallet advocacy, and a deterministic Python 3-lock checkout gate.

---

## 2. Changes Completed in this Session (Phase 3: Commerce & Account Lifecycle)
1. **Composite Cart Manager (`backend/agent/composite_cart.py`):** Target cart assembly preserving existing basket items on destructive `update_cart`, read-after-write `get_cart` diffing, non-blocking out-of-stock card ("⚠️ *Not added*"), mid-basket address switching and rebuild, and 1-tap "Go-To Items" reordering.
2. **Address & Session Lifecycle (`backend/agent/address_lifecycle.py`):** Two-step pin geocoding onboarding (ADR 0008), address deletion guardrail blocking deletion during active deliveries (ADR 0007), interactive confirmation buttons for idle address deletion, one-time destination order anchoring preserving primary address (ADR 0009), and 5-day token expiration request parking with JIT replay (ADR 0010).
3. **Swiggy MCP Tools Integration (`backend/integrations/commerce/swiggy_client.py`):** Added typed methods and generic `call_remote_tool` handling JSON-RPC 2.0 tools with typed `SwiggyAuthExpiredError` on 401 Unauthorized.
4. **Comprehensive Test Suites:**
   - `tests/test_composite_cart.py` (4 tests)
   - `tests/test_address_lifecycle.py` (6 tests)

---

## 3. Passing Tests & Verification Proof
- **Database:** `scripts/verify_db.py` confirms 6/6 tables in Supabase over live SSL.
- **Linting:** `ruff check backend tests` passed with 0 errors.
- **Formatting:** `ruff format --check backend tests` passed with 20 files clean.
- **Test Suite:** 67/67 passing tests across invariants, staging fixtures, channels, catalog search, composite cart, and address lifecycle (all green, 0 mocks).
- **Web Build:** Next.js Turbopack production build succeeds in 6.2s.
- **Universal Verification:** `.\verify.ps1` exits 0 with 100% green output.

---

## 4. Immediate Next Action for the Next Session
Proceed directly to **Phase 4: 3-Lock Payment Gate & Web Checkout** in `TASKS.md`:
1. Implement Lock 1 (physical WhatsApp button ID only; text "yes" rejected).
2. Implement Lock 2 (re-verification of price, integer paise math, stock, and ₹1 price-drift abort).
3. Implement Lock 3 (atomic PostgreSQL CAS on `grocer.approvals` + pre-checkout order ID snapshot).
4. Format Swiggy HTTPS `bridgeUrl` into WhatsApp CTA URL button (strictly reject `upi://` schemes).
5. Implement Small-Cart Fee Warning (ADR 0009: warn customer if order is below dark store's free delivery threshold).
6. Implement `check_payment_status` ~19-second durable background poller (up to 5 min timeout).
7. Implement Multi-Store Split Order handling (ADR 0007: unified WhatsApp receipt + split tracking links).
8. Implement Order Cancellation Protocol (ADR 0007: phone escalation to Swiggy Care `080-67466729`).
9. Implement Post-Payment Session Reset (ADR 0010: clear session basket upon payment confirmation).
10. Implement Post-Order Additions (ADR 0009: propose add-to-active-order if packing; else start second order).
11. Implement real-time GPS rider tracking transition on payment confirmation (`track_order`).
12. Write test suite `tests/test_checkout_locks.py`.

---

## 5. Copy-Paste Resume Prompt for Fresh Chat
```text
Resume Grocer v1.0 from .scratch/HANDOFF.md. Phase 3 is 100% verified and complete (67/67 tests green). Let's start Phase 4: 3-Lock Payment Gate & Web Checkout in TASKS.md. Follow all AGENTS.md rules and TDD.
```
