# TASKS.md — Grocer v5.0 Phased Implementation Roadmap

> **Status:** Active Roadmap  
> **Rule:** Every phase requires a runnable test script that exits 0 with terminal proof before proceeding to the next phase.

---

## Phase 0: Ground-Truth Staging Fixtures (Zero Code First)
- [ ] Connect to Swiggy staging MCP endpoint (`https://mcp.swiggy.com/im`).
- [ ] Capture raw JSON responses for all 19 Instamart tools into `grocer-v5/tests/fixtures/`.
- [ ] Write standalone contract tests validating JSON-RPC 2.0 schemas against committed staging fixtures.
- [ ] Permanently purge `MockCommerceAdapter`.
- **Done Condition:** All contract tests pass against real staging fixtures; 0 mocks present.

---

## Phase 1: Channel Ingestion Shield & Deduplication
- [ ] Implement `POST /api/whatsapp/webhook` with HMAC-SHA256 signature verification (<25ms response).
- [ ] Implement PostgreSQL message deduplication (`ON CONFLICT (wa_message_id) DO NOTHING`).
- [ ] Implement in-process / PostgreSQL per-user concurrency lock.
- [ ] Implement fast 50ms button dispatcher for interactive button taps.
- **Done Condition:** Webhook replay attack tests pass; duplicate messages are dropped with zero double-processing.

---

## Phase 2: Conversational Brain & Intelligent Candidate Search
- [ ] Implement `search_catalog(query)` returning real Swiggy candidates (name, pack size, price, in_stock).
- [ ] Implement Gemini candidate evaluation (matching variants against user constraints; no blind rank-1).
- [ ] Implement conversational Q&A without forced receipt cards.
- [ ] Implement vague staple auto-selection (standard pack + "Change items" button).
- [ ] Implement snack/drink disambiguation (2–3 quick options).
- **Done Condition:** Test matrix with 20 real customer phrases (typos, recipes, brand queries) picks the correct dark-store product 100% of the time.

---

## Phase 3: Cart Reconciliation & JIT Re-Auth
- [ ] Implement full target cart assembly and safe destructive `update_cart`.
- [ ] Implement read-after-write verification (`get_cart` diffing, revert detection).
- [ ] Implement non-blocking out-of-stock reconciliation ("Not added" receipt card).
- [ ] Implement 5-day token expiration detection + parked message replay on OAuth callback.
- **Done Condition:** Adding an item preserves existing items; missing items appear under "Not added"; expired token retains the customer's shopping list after login.

---

## Phase 4: 3-Lock Payment Gate & Web Checkout
- [ ] Implement Lock 1 (physical button ID only; text "yes" rejected).
- [ ] Implement Lock 2 (re-verification of price, paise math, and stock).
- [ ] Implement Lock 3 (atomic PostgreSQL CAS + order ID snapshot).
- [ ] Format Swiggy HTTPS `bridgeUrl` into WhatsApp CTA URL button.
- [ ] Implement `check_payment_status` ~19-second durable background poller.
- **Done Condition:** Text "yes" fails to trigger payment; double-tap triggers exactly one checkout; successful payment pushes instant WhatsApp receipt.

---

## Phase 5: Wallet Advocate & Production Hardening
- [ ] Implement bounded coupon trial-and-reset (max 2 applicable coupons).
- [ ] Enforce ₹1,000 launch safety cap with 1-tap "Raise Limit" button.
- [ ] Implement 24-hour DPDP data minimization scrubber and "delete my data" command.
- [ ] Implement milestone-only delivery push notifications (Confirmed, Picked Up, Delivered).
- **Done Condition:** 7 consecutive days on staging with 0 duplicate orders and 0 cart drift errors.
