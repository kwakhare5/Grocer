# TASKS.md — Grocer v1.0 Phased Implementation Roadmap

> **Status:** Active Roadmap  
> **Source of Truth:** `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `GLOSSARY.md`, ADRs 0001–0010  
> **Rule:** Every phase requires a runnable test script (`.\verify.ps1`) that exits 0 with terminal proof before proceeding to the next phase.

---

## Phase 0: Ground-Truth Staging Fixtures (Zero Code First) — [COMPLETE]
- [x] Connect to Swiggy staging MCP endpoint (`https://mcp.swiggy.com/im`).
- [x] Capture raw JSON responses for all 20 Instamart tools into `tests/fixtures/`.
- [x] Write standalone contract tests validating JSON-RPC 2.0 schemas against committed staging fixtures.
- [x] Set up Supabase PostgreSQL live connection and apply `migrations/001_initial_schema.sql` (6/6 tables active).
- [x] Permanently purge `MockCommerceAdapter` and enforce zero-mock invariant.
- [x] Author universal verification runner `verify.ps1`.
- **Done Condition:** All contract tests pass against real staging fixtures; 0 mocks present; database verified. [VERIFIED: 21/21 tests green, exit 0]

---

## Phase 1: Channel Ingestion Shield & Deduplication — [COMPLETE]
- [x] Implement `POST /api/whatsapp/webhook` with HMAC-SHA256 signature verification (<25ms response).
- [x] Implement PostgreSQL message deduplication (`ON CONFLICT (wa_message_id) DO NOTHING` on `grocer.inbound_messages`).
- [x] Implement in-process / PostgreSQL advisory lock per-user (`pg_try_advisory_xact_lock`) for concurrent message serialization.
- [x] Implement fast 50ms button dispatcher for interactive button taps (`button_reply`, `list_reply`).
- [x] Implement WhatsApp inbound payload parser (`backend/channels/whatsapp_parser.py`) for text, button IDs, and GPS location pins.
- [x] Write integration test `tests/test_channels.py` testing webhook intake, signature validation, replay attacks, and duplicate dropping.
- **Done Condition:** Webhook replay attack tests pass; duplicate messages are dropped with zero double-processing. [VERIFIED: 8/8 tests green, exit 0]

---

## Phase 2: Conversational Brain & Intelligent Candidate Search — [COMPLETE]
- [x] Implement `search_catalog(query)` returning candidate lists from Swiggy Instamart dark stores.
- [x] Implement Gemini candidate evaluation (matching variants against user constraints; strictly no blind rank-1).
- [x] Implement conversational Q&A without forced receipt cards (pure natural language answers).
- [x] Implement vague staple auto-selection (standard pack + "Change items" button).
- [x] Implement snack/drink disambiguation (2–3 quick options with clear pack sizes and prices).
- [x] Implement Recipe Checklist proposals (ADR 0009: e.g. "Making chai" -> proposes milk, tea leaves, ginger, sugar with item toggles).
- [x] Implement Zero-Address Onboarding flow (ADR 0010: detect cold-start user with 0 addresses -> prompt for WhatsApp GPS location pin).
- [x] Write test suite `tests/test_catalog_search.py` with 20 real customer phrases (typos, Hinglish, recipe queries, brand queries).
- **Done Condition:** Test matrix with 20 real customer phrases picks the correct dark-store product 100% of the time. [VERIFIED: 20/20 green, 55/55 total suite green]

---

## Phase 3: Commerce & Account Lifecycle — [COMPLETE]
- [x] Implement full target cart assembly and safe destructive `update_cart`.
- [x] Implement read-after-write verification (`get_cart` diffing, revert detection).
- [x] Implement non-blocking out-of-stock reconciliation ("Not added" receipt card).
- [x] Implement full address lifecycle (`get_addresses`, two-step pin geocoding via `recommend_address`, address switching mid-basket).
- [x] Implement Address Deletion Guardrail (ADR 0007: block address deletion if an active delivery is currently in transit to that address).
- [x] Implement One-Time Destination Orders (ADR 0009: send groceries to parent/friend, then auto-revert session to primary home address).
- [x] Implement 5-day token expiration detection + JIT re-auth parked message replay on OAuth callback (ADR 0010).
- [x] Implement 1-Tap "Go-To Items" reordering (ADR 0008).
- [x] Write test suite `tests/test_composite_cart.py` and `tests/test_address_lifecycle.py`.
- **Done Condition:** Adding an item preserves existing items; missing items appear under "Not added"; address deletion blocked during live deliveries; expired token retains shopping list after login. [VERIFIED: 10/10 green, 67/67 total suite green]

---

## Phase 4: 3-Lock Payment Gate & Web Checkout — [COMPLETE]
- [x] Implement Lock 1 (physical button ID only; text "yes" rejected).
- [x] Implement Lock 2 (re-verification of price, integer paise math, stock, and ₹1 price-drift abort).
- [x] Implement Lock 3 (atomic PostgreSQL CAS on `grocer.approvals` + pre-checkout order ID snapshot).
- [x] Format Swiggy HTTPS `bridgeUrl` into WhatsApp CTA URL button (strictly reject `upi://` schemes).
- [x] Implement Small-Cart Fee Warning (ADR 0009: warn customer if order is below dark store's free delivery threshold).
- [x] Implement `check_payment_status` ~19-second durable background poller (up to 5 min timeout).
- [x] Implement Multi-Store Split Order handling (ADR 0007: unified WhatsApp receipt + split tracking links).
- [x] Implement Order Cancellation Protocol (ADR 0007: phone escalation to Swiggy Care `080-67466729`).
- [x] Implement Post-Payment Session Reset (ADR 0010: clear session basket upon payment confirmation).
- [x] Implement Post-Order Additions (ADR 0009: propose add-to-active-order if packing; else start second order).
- [x] Implement real-time GPS rider tracking transition on payment confirmation (`track_order`).
- [x] Write test suite `tests/test_checkout_locks.py`.
- **Done Condition:** Text "yes" fails to trigger payment; double-tap triggers exactly one checkout; successful payment pushes instant WhatsApp receipt and live GPS tracking map link. [VERIFIED: 13/13 green, 85/85 total suite green]

---

## Phase 5: Wallet Advocate & Production Hardening — [COMPLETE]
- [x] Implement bounded coupon trial-and-reset (max 2 applicable coupons; net savings check).
- [x] Enforce ₹1,000 launch safety cap with 1-tap "Raise Limit" button.
- [x] Implement 24-hour DPDP data minimization scrubber and "delete my data" command.
- [x] Implement milestone-only delivery push notifications (Confirmed, Picked Up, Delivered).
- [x] Build end-to-end staging smoke test suite (`tests/test_e2e_staging.py`).
- **Done Condition:** Full test suite passes; 0 duplicate orders and 0 cart drift errors. [VERIFIED: 8/8 green, 96/96 total suite green, exit 0]
