# STATUS.md — Grocer v1 Current Truth

> **Updated:** 2026-10-27  
> **Authority:** This is the only current status document. `PRD.md` is the v1 target. `ARCHITECTURE.md` is the design plus known gaps. `DESIGN.md` is the WhatsApp UI plus the website landing page. `JOURNAL.md` is append-only history. `docs/adr/` records decisions, amended not rewritten.  
> **Rule:** DONE needs a proof command, date, and raw output. Everything else is PARTIAL, BROKEN, or NOT VERIFIED. A green test is not proof that the live product works.

---

## 0. Environment & Fixed Constraints

| Item | Current fact |
|---|---|
| Git branch | `grocer-v1`; main branch is `main` |
| Supabase | One project until launch. App data lives in the `postgres` database, schema `grocer` (7 app tables + `schema_migrations`). Both the app database and `grocer_test` are migrated through 004 (app DB applied 2026-10-27). |
| LLM | Groq `openai/gpt-oss-120b` is primary for development and tests. Gemini is optional and its free quota is not a dependency. |
| Swiggy auth | Allowlisted OAuth redirect: `https://grocerr.vercel.app/`. Backend calls `https://mcp.swiggy.com/im` with the customer token. |
| Checkout | `LIVE_CHECKOUT_ENABLED=false`. The build must stay real-order capable. No live order without Karan's explicit approval. |
| Order cap | ₹1,000 default (`100000` paise). |
| Hosting | Backend on Render free plan (sleeps when idle). Landing page on Vercel. |
| Landing page number | Display placeholder `+91 98765 43210`. Real WhatsApp link comes only from `NEXT_PUBLIC_WHATSAPP_NUMBER`. Karan's real number is never committed or published. |
| Product goal | Chat is the front door to all 20 Instamart tools. `PRD.md` §3 journeys are examples, not a checklist. |
| Build-time order policy | No live order during the build. Checkout proof is simulated plus recorded responses. Karan places the first real order after handoff. |
| Address test writes | One throwaway address on Karan's account may be created and deleted. |
| Hosting | Render free plan; pollers reconcile from the DB on wake. No paid instance. |
| Landing OAuth | Phone-entry form is removed. OAuth is a bot-sent bridge only. |

---

## 1. Current State — One Screen

| Item | State |
|---|---|
| Documentation sync | **DONE 2026-10-27.** Docs share one authority map, one current status, and one scope: full tool coverage, journeys are examples. `TASKS.md` now exists. |
| Lint | **PASS 2026-10-27:** `ruff check backend tests` → `All checks passed!` |
| Offline tests | **PASS 2026-10-27:** 100 passed, 56 deselected (`pytest -q -m "not db and not live"`). |
| DB tests | **PASS 2026-10-27:** 34 passed on `grocer_test` (`pytest -q -m "db"`). |
| Live tests | **22 collected, not run.** `test_catalog_search.py` calls the live Gemini evaluator and is now marked `live`. |
| Full test collection | **156 tests collected 2026-10-27.** |
| Full suite claim | The old "136 passed, 0 skipped" claim is retired. The current verified set is 100 offline + 34 DB; live is excluded by default. |
| Live Swiggy smoke | **PASS 2026-10-27:** real token, real MCP. 3 addresses, 20 milk products with live prices, 12-item cart read, 0 orders, 10 payment methods, 0 coupons. Cart add verified then restored (12 items, same spins and quantities). No order placed. Raw: `scripts/live_smoke.py`. |
| Live Groq pass | **PASS 2026-10-27:** 10 real messages → 10 correct routes (item_info ×3, list_addresses, order_history, list_coupons, payment_options, add_items, chat, track_order) with real read answers. 55s. |
| Live checkout lock | **PASS 2026-10-27:** with `LIVE_CHECKOUT_ENABLED=false`, the real path returned "Checkout is locked" and a sentinel client proved no Swiggy method ran. |
| Checkout deploy lock | **DONE 2026-10-27:** `LIVE_CHECKOUT_ENABLED=false` is enforced in `execute_3_lock_checkout` before any Swiggy call. A test proves no client call and no approval consumption while locked. |
| Checkout money core | **DONE (simulated) 2026-10-27:** claim, attempt row and result each commit separately; no transaction spans the Swiggy call. CAS binds approval + user. UPI sends `generateUPIQR`. Timeout/5xx reconciles against `get_orders` with one retry; stuck attempts are resolved by the payment poller. Cap raise returns the receipt to payable. Proof: 8 new DB tests incl. duplicate, concurrent, crash, timeout, unconfirmed and cap-raise. Never live-tested. |
| Inbound dedupe | **DONE 2026-10-27:** user + `inbound_messages` row commit before the turn; the per-user lock is session-scoped and asyncpg releases it on pool release (probe run). |
| Post-payment truth | **DONE (code) 2026-10-27:** `track_order` is called with saved coordinates, with `get_delivery_status` as the no-map fallback. `store_info` answers honestly instead of inventing a store or window. Split orders poll every order id; each order+milestone fires once via `notified_milestones` (migration 004). A payment made while Render slept is confirmed on wake; an auth failure leaves the row pending instead of failed. Proof: 3 new DB tests, 5 read tests. |
| Test isolation | **DONE 2026-10-27:** `grocer_test` database live; the DSN guard refuses any test DSN that is not `grocer_test`. |
| Router eval (live Groq) | **PASS with one miss 2026-10-27:** 39/40 exact (97.5%), 0 unsafe writes, 0 under-acted writes, 0 LLM errors. Miss: "how long till my food arrives" → `store_info`, expected `track_order`. Latency was not recorded by the harness. Raw: `.scratch/eval_phase2.json`. |
| One LLM brain | **DONE 2026-10-27:** routing and candidate evaluation both call `backend/agent/llm.py`. Direct Gemini calls and the second classification call are gone. Gemini key is optional. |
| Live reads | Recorded live on 2026-10-26: price/stock, addresses, order history, cancel help, payment options, coupons. Not re-run on 2026-10-27. |
| Live refresh | Recorded 2026-10-26: forced refresh returned a new token pair; new expiry 2026-11-25. Journal also records a fixture-only refresh proof. Treat the live proof as recorded, not re-verified. |
| Live checkout | **Never tested. No order placed.** |
| Migration 004 | **VERIFIED 2026-10-27:** `python scripts/migrate.py` applied `004_checkout_milestones.sql` to the app database; `verify_db.py` exits 0 with 8 tables, `notified_milestones` present, and the required indexes. `grocer_test` is also at 004. |
| Production readiness | **No.** |
| Current gate | **Gate 2 — Concierge Answers.** 6 of 8 pass (3 of them live on 2026-10-27), 1 partial (reorder needs a past order), 1 unverified on WhatsApp ("milk" choices). See §2. |

---

## 2. Gate 2 — Actual Results

Gate 2 is read-only. No checkout, order, payment call, or address write is in scope.

| # | Customer says | Required | Actual | Result |
|---|---|---|---|---|
| 1 | "How much is Amul milk?" | Real price and pack size; cart untouched | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 2 | "Is Amul milk in stock?" | Real availability at the default store | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 3 | "Which store? When will it arrive?" | Real store and delivery window | Honest: the cart quote plus "Swiggy doesn't share the dark store name or a delivery window before an order is placed" (`backend/agent/read_actions.py:66`) | **PASS (honest)** |
| 4 | "What addresses do I have?" | The 3 saved addresses, default marked | Live 2026-10-27: 3 addresses, default marked | **PASS** |
| 5 | "Show my last orders" | Real history; 0 is truth | Live 2026-10-27: 0 orders, said so | **PASS** |
| 6 | "Where is my order?" | Track the order or say there are none | `track_order` with saved coords, `get_delivery_status` fallback; with 0 orders says so (`backend/agent/read_actions.py:129`) | **PASS (no-order path live)** |
| 7 | "Reorder that" | Build the basket, stop before checkout | Fixture-proven only; live write blocked because the account has 0 orders | **PARTIAL** |
| 8 | "milk" | Tappable choices for real products; never "couldn't find" | One-word requests now return up to 3 real products as tappable `cart:add` buttons (`backend/channels/whatsapp.py:812`) | **UNVERIFIED on WhatsApp** |

**Done means:** every case shows its real answer, `ruff` clean, offline tests green, and docs updated. That is not met.

---

## 3. Capability Truth

| Safety class | Capabilities | Reality |
|---|---|---|
| **read** (9) | chat, item_info, store_info, list_addresses, order_history, track_order, list_coupons, payment_options, cancel_help | All 9 answer live. `store_info` gives the live cart quote and says Swiggy does not expose the store or window. `track_order` calls the tracking tool when coordinates are saved, else delivery status. |
| **basket** (4) | add_items, change_item, clear_basket, reorder | `add_items` works live. Change, clear and reorder are fixture-proven only. Reorder's live write is blocked. `add_items` still makes a second legacy LLM call. |
| **account** (3) | add_address, switch_address, delete_address | Address list is a read capability and works. Switch only writes `sessions.active_address_id`; it does not clear or rebuild the basket. Delete has a confirmation but the active-delivery guard is not wired; actual delete is unproven. Typed-text add is not built; every pin restarts onboarding. |
| **money** (1) | checkout | Button path is wired end to end and no longer holds a DB transaction across the Swiggy call. Text "place the order" still returns a not-ready reply (`backend/channels/whatsapp.py:697`). Never live-tested; no order placed. |

**Capability count:** 17 declared, 16 reachable. `checkout` is the unwired one.

---

## 4. P0 — Fix Before Any Live Order

**Still open (Phase 5):**

6. **Park and replay are disconnected.** The webhook writes `status='parked'` (`backend/channels/whatsapp.py:910`). Replay only claims `awaiting_link` (`backend/agent/address_lifecycle.py:216`). The OAuth callback returns the payload to the browser but never re-executes or sends it (`backend/channels/swiggy_auth.py:158`). The current test proves the unused path.

**Fixed in Phase 3 (2026-10-27):**

1. **Checkout ran inside a DB transaction.** `execute_3_lock_checkout` now takes the pool and commits the CAS, the attempt row and the result separately. No transaction spans a Swiggy call, and `button_router` no longer opens one. Proof: duplicate-tap, concurrent-tap and crash tests in `tests/test_checkout_locks.py`.
2. **UPI arguments were incomplete.** `SwiggyClient.checkout` sends `generateUPIQR=true` for UPI, or `intentApp` when one is given. Proof: `test_upi_checkout_sends_qr_request`.
3. **Not idempotent; retry guard unused.** The pre-checkout snapshot is now required. On timeout/5xx the order list is compared with it, the call retries once only, and `reconcile_attempting_checkouts` resolves attempts left by a crash. Proof: timeout-recovered, clean-failure, unconfirmed and crash tests.
4. **Lock 1 did not bind the approval to the tapper.** The CAS matches `id + user_id`, and the webhook passes the real `message_type` instead of a hardcoded one. Proof: `test_lock_3_cas_rejects_another_user`.
5. **Budget-raise was a dead end.** A cap failure returns the approval to `shown`. The button carries `budget:raise:<approval_id>:<paise>`; the handler raises the cap and re-sends the pay button. Proof: `test_cap_raise_keeps_receipt_payable`.
8. **Dedupe could roll back.** The user and `inbound_messages` rows commit before the turn runs. The per-user lock is session-scoped; a probe proved asyncpg releases it when the connection returns to the pool.

**Fixed in Phase 4 (2026-10-27):**

7. **Pollers could die, spam and skip orders.** `SwiggyAuthExpiredError` is now caught by every loop and by each row inside the payment batch, so one 401 no longer aborts the batch or marks a payment failed. Each order id in a split checkout is polled, and `notified_milestones` (migration 004) sends each order+milestone once. A pending payment older than five minutes is checked on wake rather than failed blindly. Proof: split-milestone, wake-payment and auth-failure tests.

**Honest limit:** none of this is proof that a live order works. It is proof that a live order cannot double-place or charge without a tap.

---

## 5. P1 — Real, Lower Blast Radius

- Address grounding uses `addresses[0]`, not Swiggy's default address (`backend/channels/whatsapp.py:430`).
- Address switch does not clear or rebuild the basket, so the basket can belong to the old store.
- The active-delivery delete guard exists but is called only in tests (`backend/agent/address_lifecycle.py:304`).
- Money math outside checkout still uses floats and `round()` for paise (`backend/integrations/commerce/schemas.py:90`, `backend/agent/composite_cart.py:137`). The checkout path now parses response rupees through `parse_price_to_paise`.
- Coupons run only on the add-items path. Only the first two applicable coupons are tried. The savings message is built but never sent (`backend/agent/customer_advocate.py:251`).
- Receipt bodies are truncated at 1024 characters, so long bills silently lose lines (`backend/channels/whatsapp_client.py:105`).
- Dead buttons end at "Action processed": recipe, item change, go-to add, post-order add, and proceed checkout (`backend/agent/customer_advocate.py:111`, `backend/agent/candidate_evaluator.py:481`).
- DPDP scrubs some fields but leaves `sessions.onboarding_context`, `users.display_name`, delivery coordinates, `address_coords`, the user row, and approval/checkout rows (`backend/agent/dpdp.py:19`, `backend/agent/dpdp.py:112`).
- No RLS on any table; PII is plaintext; OAuth login accepts any phone and binds the token to the caller-supplied phone (`backend/channels/swiggy_auth.py:63`, `migrations/001_initial_schema.sql:9`).
- The landing page footer says "Systems Operational" with no health check, and the page falls back to a fake WhatsApp number (`app/page.tsx:76`, `app/page.tsx:269`).
- Render free plan sleeps, so pollers stop when idle (`render.yaml:6`).
- The app still fails to boot if the database is unreachable at startup, so `/health` cannot report that first failure. It reports later DB failures.

**Fixed in Phase 1 (2026-10-27):** `verify_db.py` table/column/index check, `verify.ps1` offline default, `/health` 503 mapping, `ruff` dev requirements, real test database, DSN guard, live-test marker, mock-based "live" test rename.

**Fixed in Phase 3 (2026-10-27):** checkout transaction boundary, CAS ownership, UPI args, timeout/5xx reconcile, crash reconcile, cap-raise loop, checkout `response_total_paise`, independent inbound dedupe.

**Fixed in Phase 4 (2026-10-27):** real `track_order` with map fallback, honest `store_info`, tappable choices for one-word requests, split-order milestone latch, wake reconciliation, 401 isolation per row.

**Observed live 2026-10-27:** calling `update_cart` on a 12-item real cart (₹1751 quote) left all 12 items and quantities intact but Swiggy priced three lines at ₹0 (NOICE peanut butter, Alt Co almond beverage, Amul butter), so its own total became ₹753. Nothing was removed by Grocer. Lock 2 would abort checkout on that drift, which is the intended behavior, but the cause is Swiggy-side and worth watching.

---

## 6. Test Truth (2026-10-27)

**What each kind of test proves.**

| Kind | Where | Proves | Does not prove |
|---|---|---|---|
| Live smoke | `scripts/live_smoke.py` (run by hand with real tokens) | Real Swiggy reads, a real cart add/restore, real Groq routing, the checkout lock stopping before Swiggy | That a live order completes |
| Scripted tests | `tests/test_checkout_locks.py`, `ScriptedClient` | Grocer's own logic on failure paths that cannot be triggered on demand (timeout, 5xx, crash, another user's tap) | Any live Swiggy behavior |
| Fixture tests | `tests/test_staging_fixtures.py` | Response shapes parse correctly | That the live service returns them today |
| DB tests | `-m db` on `grocer_test` | Real SQL, constraints, CAS, pollers against real Postgres | Nothing about Swiggy |

Scripted tests are not fake product tests. They inject failures the live API will not produce on request. They are never counted as proof of a live capability; every live claim in this file is tied to a dated smoke run.

```
ruff check backend tests
All checks passed!

pytest -q -m "not db and not live"
100 passed, 56 deselected in 0.74s

pytest -q -m "db"
34 passed, 122 deselected in 33.49s

pytest --collect-only -q
156 tests collected

powershell -File verify.ps1 -Db
=== [PASS] Grocer v1.0 verification complete ===
# 2026-10-27 after migration 004: schema check exit 0, ruff clean,
# 100 offline pass, 34 DB pass, Next.js build pass, script exit 0
```

**New in Phase 4:** 5 read-path tests (track with coords, track without coords, no active order, honest store info, tappable choices) and 3 DB tests (split milestones sent once, wake payment confirmed, 401 keeps the row pending). `npm run build` passes. `verify.ps1 -Db` now exits 0 after migration 004 was applied to the app database on 2026-10-27.

**New in Phase 3:** duplicate tap, two simultaneous taps, another user's button, timeout with a recovered order, clean failure that leaves the receipt payable, unverifiable outcome that blocks retry, crash reconcile with and without an order, cap raise, and UPI QR args. Raw log: `.scratch/verify_phase3.log`.

**Guard proof:** with `TEST_DATABASE_URL` set to the app DSN, pytest exits 1:
```
RuntimeError: Refusing to run tests against database 'postgres'. TEST_DATABASE_URL must point at grocer_test.
```

**Real schema proof:** before and after the DB run, `grocer` held the same counts
(`users=1, sessions=1, approvals=0, checkouts=0, inbound_messages=10, oauth_tokens=1, address_coords=0`).
`grocer_test.users` was 0 after cleanup.

**Not run:** live Swiggy calls, live WhatsApp sends, live Groq eval, and checkout. `test_catalog_search` is marked `live` and excluded by default.

---

## 7. ADR Status

| ADR | Status | Current note |
|---|---|---|
| 0001 | Amended | 25ms ACK and 50ms button path are targets. The webhook is synchronous today. |
| 0002 | Active with deviation | Grounding uses the first saved address, not the default. Fingerprint includes payable paise, so any paise change fails. |
| 0003 | Active with gaps | Coupon guard works. Savings message is not sent. Tracking now calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Amended | The 5-day/no-refresh claim is obsolete. Refresh token exists. Parked replay is broken. |
| 0005 | Partial | Payment buttons are Pay + Clear only. COD, Change Address and Change Items are target. |
| 0006 | Partial | ₹1,000 cap stays. Cap-raise now re-opens the same receipt. DPDP is partial. |
| 0007 | Partial | Address switch does not rebuild the cart. Delete guard is not wired. |
| 0008 | Partial | Typed-text address add is missing. Reorder is fixture-only. |
| 0009 | Not implemented | Examples, not v1 scope. Recipes have no tool. Do not describe as live. |
| 0010 | Amended | Refresh first, park only on refresh failure. The parked status does not match replay. |
| 0011 | Superseded | Replaced by ADR 0012. The legacy second LLM call is removed. |
| 0012 | Active | Groq is primary and the only adapter. Direct Gemini calls are gone; the key is optional. |

---

## 8. Next Action

**Phases 0-4 are done.** Checkout is transaction-safe with reconcile, the read path answers from live Swiggy data, and pollers handle split orders, repeats, 401s and wake. Live smoke on 2026-10-27 proved real reads, a real cart add/restore, 10/10 Groq routes, and a checkout that stops before Swiggy. Migration 004 is applied to both databases and `verify.ps1 -Db` exits 0.

**Phase 5: account and address lifecycle.** Ground to the default address, clear and rebuild the basket on switch, wire the delete guard, typed-text address add, OAuth state bound to the user, park/replay wired end to end (open P0 #6).

**Open proofs:** Gate 2 case 7 (needs a past order), case 8 ("milk" choices need a WhatsApp tap), and the Phase 2 latency miss. Re-run the full gate at launch.

---

## 9. Rules for Every Future Chat

1. Read `STATUS.md`, `.scratch/HANDOFF.md`, and the latest `JOURNAL.md` entry before planning.
2. Do not edit code without showing the exact plan and getting `proceed`.
3. Do not place an order during the build. Karan places the first real order himself after handoff. `LIVE_CHECKOUT_ENABLED=false` must be enforced in code.
4. Cart changes need approval. Tests never write the real `grocer` schema.
5. Do not fake Swiggy, Groq, Gemini, WhatsApp, or the database.
6. Do not claim a live result you did not run. Label it "recorded" or "not verified".
7. Do not delete data without listing it first.
8. Do not weaken a test to pass. If the feature is broken, say so.
9. Show `git diff`, test output, and database proof.
10. Update `STATUS.md`, `.scratch/HANDOFF.md`, and `JOURNAL.md` before ending the session.
