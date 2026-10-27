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
| Documentation sync | **DONE 2026-10-27, scope corrected 2026-10-27.** Recipes are in v1 as plan-confirm-add; proactivity is money-and-truth only; replies stay English. Stale "current" notes were removed from PRD, ARCHITECTURE, DESIGN, GLOSSARY and the ADR index. The scope table lives in `TASKS.md`. |
| Lint | **PASS 2026-10-27:** `ruff check backend tests` → `All checks passed!` |
| Offline tests | **PASS 2026-10-27:** 103 passed, 66 deselected (`pytest -q -m "not db and not live"`). |
| DB tests | **PASS 2026-10-27:** 46 passed on `grocer_test` (`pytest -q -m "db"`). |
| Live tests | **22 collected, not run.** `test_catalog_search.py` calls the live Gemini evaluator and is marked `live`. |
| Full test collection | **169 tests collected 2026-10-27.** |
| Full suite claim | The old "136 passed, 0 skipped" claim is retired. The current verified set is 103 offline + 46 DB; live is excluded by default. Scripted tests are marked `scripted` and never counted as live proof. |
| Live Swiggy smoke | **PASS 2026-10-27:** real token, real MCP. 3 addresses, 20 milk products with live prices, 12-item cart read, 0 orders, 10 payment methods, 0 coupons. Cart add verified then restored (12 items, same spins and quantities). No order placed. Raw: `scripts/live_smoke.py`. |
| Live Groq pass | **PASS 2026-10-27:** 10 real messages → 10 correct routes (item_info ×3, list_addresses, order_history, list_coupons, payment_options, add_items, chat, track_order) with real read answers. 55s. |
| Live checkout lock | **PASS 2026-10-27:** with `LIVE_CHECKOUT_ENABLED=false`, the real path returned "Checkout is locked" and a sentinel client proved no Swiggy method ran. |
| Checkout deploy lock | **DONE 2026-10-27:** `LIVE_CHECKOUT_ENABLED=false` is enforced in `execute_3_lock_checkout` before any Swiggy call. A test proves no client call and no approval consumption while locked. |
| Checkout money core | **DONE (simulated) 2026-10-27:** claim, attempt row and result each commit separately; no transaction spans the Swiggy call. CAS binds approval + user. UPI sends `generateUPIQR`. Timeout/5xx reconciles against `get_orders` with one retry; stuck attempts are resolved by the payment poller. Cap raise returns the receipt to payable. Proof: 8 new DB tests incl. duplicate, concurrent, crash, timeout, unconfirmed and cap-raise. Never live-tested. |
| Inbound dedupe | **DONE 2026-10-27:** user + `inbound_messages` row commit before the turn; the per-user lock is session-scoped and asyncpg releases it on pool release (probe run). |
| Post-payment truth | **DONE (code) 2026-10-27:** `track_order` is called with saved coordinates, with `get_delivery_status` as the no-map fallback. `store_info` answers honestly instead of inventing a store or window. Split orders poll every order id; each order+milestone fires once via `notified_milestones` (migration 004). A payment made while Render slept is confirmed on wake; an auth failure leaves the row pending instead of failed. Proof: 3 new DB tests, 5 read tests. |
| Test isolation | **DONE 2026-10-27:** `grocer_test` database live; the DSN guard refuses any test DSN that is not `grocer_test`. |
| Account lifecycle | **DONE (code) 2026-10-27:** grounding uses Swiggy's default address, not `addresses[0]`. A mid-basket switch warns, then clears and rebuilds the basket at the new store and names what is missing. The active-delivery delete guard runs on the real delete path. Typed-text address add geocodes through `recommend_address(query=...)`. OAuth login only accepts a signed bot link. Parked lists replay automatically after login. |
| No fake sends | **DONE 2026-10-27:** the production mock branch in `WhatsAppClient` is gone. Tests inject a recording client instead, so a test can never silently "deliver" to nobody. |
| Conversation trust (Phase 7 Batch 1) | **DONE (code) 2026-10-27:** AI outage now says so instead of "I didn't catch that", with an 8-second deadline and one retry only when it can help (`backend/agent/router.py`, `backend/agent/llm.py`). Every inbound message is marked read with a typing indicator (`backend/channels/whatsapp_client.py`, `backend/channels/whatsapp.py`). Receipts show the delta, Swiggy's stock cap, the old basket and the total; `Keep only new` is stateless (`backend/agent/composite_cart.py`, `backend/agent/basket_actions.py`). A total above the ₹1,000 cap is named at add time. `view_basket` answers "what's in my basket". Address cards are shortened with up to 3 switch buttons. Vague staples auto-pick with a working `Change item` and swap; discretionary items show choices; the blind rank-1 fallback is gone. Out-of-stock answers name real `similarProducts`. Every route decision is logged as JSON with latency. A text after an hour idle with a non-empty basket gets a Keep/Clear prompt. |
| Code cleanup (repo audit) | **DONE 2026-10-27:** removed 1,212 lines and added 442 (including the new test fixture client), net -770. Deleted three dead formatter functions and module, a 97-line duplicate go-to/address-switch engine, the unused small-cart fee and launch-cap helpers, the test-only park helpers, the dead milestone helper, and the legacy 2-part cap raise. Removed seven settings with no reader, the duplicate `AddressReply`, the unused `LLMResult.model`, dead evaluator result fields, the parsed-but-unused button title, unused client header/footer params, and frontend dead paths. Moved the fixture playback engine out of the production Swiggy client into `tests/fixture_client.py`. Fixed `drive_grocer.py` checking 6 tables instead of 8. No money or lock logic changed. Dead schema columns and the unused approvals index are deferred to Phase 6. |
| Live Batch 1 check | **PASS (routing) 2026-10-28:** real signed messages to the Render app. `milk` → HTTP 200 `cart_updated` in 11.9s; latest approval is ₹283 with 2 items including milk. `what's in my basket` → HTTP 200 `view_basket` in 4.8s, 359-char reply with 2 item bullets. `show my addresses` → HTTP 200 `list_addresses` in 4.1s, 366-char card with 3 numbered entries. No order, no checkout. Blue ticks/typing are unproven because the wamid was simulated. The exact receipt copy is not stored: session history keeps a 26-char summary (`Basket updated. Total ₹283`) instead of the receipt sent, so the delta-receipt copy needs a handset look or a fix to store the real text. |
| Router eval (live Groq) | **PASS with one miss 2026-10-27:** 39/40 exact (97.5%), 0 unsafe writes, 0 under-acted writes, 0 LLM errors. Miss: "how long till my food arrives" → `store_info`, expected `track_order`. Latency was not recorded by the harness. Raw: `.scratch/eval_phase2.json`. |
| One LLM brain | **DONE 2026-10-27:** routing and candidate evaluation both call `backend/agent/llm.py`. Direct Gemini calls and the second classification call are gone. Gemini key is optional. |
| Live reads | Recorded live on 2026-10-26: price/stock, addresses, order history, cancel help, payment options, coupons. Not re-run on 2026-10-27. |
| Live refresh | Recorded 2026-10-26: forced refresh returned a new token pair; new expiry 2026-11-25. Journal also records a fixture-only refresh proof. Treat the live proof as recorded, not re-verified. |
| Live checkout | **Never tested. No order placed.** |
| Migration 004 | **VERIFIED 2026-10-27:** `python scripts/migrate.py` applied `004_checkout_milestones.sql` to the app database; `verify_db.py` exits 0 with 8 tables, `notified_milestones` present, and the required indexes. `grocer_test` is also at 004. |
| Production readiness | **No.** |
| Current gate | **Gate 2 — Concierge Answers.** 6 of 8 pass; 1 partial (reorder needs a past order); 1 code-complete but not tapped live ("milk" now auto-picks with a working Change button, discretionary items show choices). See §2. |

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
| 8 | "milk" | Never silently substitute; name the pick and offer a working Change, or show real products | A staple auto-picks with a `Change item` button that lists real alternatives and swaps on tap. Discretionary items show choices. Blind rank-1 fallback removed | **PASS (code) — live tap pending** |

**Done means:** every case shows its real answer, `ruff` clean, offline tests green, and docs updated. That is not met.

---

## 3. Capability Truth

| Safety class | Capabilities | Reality |
|---|---|---|
| **read** (10) | chat, item_info, store_info, view_basket, list_addresses, order_history, track_order, list_coupons, payment_options, cancel_help | Nine are live-proven. `view_basket` reads the real cart and is fixture-tested; it needs a WhatsApp read. `store_info` gives the live cart quote and says Swiggy does not expose the store or window. `track_order` calls the tracking tool when coordinates are saved, else delivery status. |
| **basket** (4) | add_items, change_item, clear_basket, reorder | `add_items` works live. Change, clear and reorder are fixture-proven only. Reorder's live write is blocked. `add_items` makes one routing call plus one candidate-evaluation call per item; that is the intended design (ADR 0012). |
| **account** (3) | add_address, switch_address, delete_address | Address list works live. Switch warns, clears and rebuilds the basket at the new store. Delete is blocked while a delivery is in flight and guarded again on the final tap. Typed-text add geocodes and reuses the flat/name/city steps. Live add/delete is still unproven (needs the one throwaway address). |
| **money** (1) | checkout | Button path is wired end to end and no longer holds a DB transaction across the Swiggy call. Text "place the order" returns a not-ready reply by design: Lock 1 requires a physical tap. Never live-tested; no order placed. |

**Capability count:** 18 declared. 17 are dispatched from the router; `checkout` is reachable only from the pay button, by design (Lock 1).

---

## 4. P0 — Fix Before Any Live Order

**No P0 is open as of 2026-10-27.** The last one is fixed in Phase 5 below.

**Fixed in Phase 3 (2026-10-27):**

1. **Checkout ran inside a DB transaction.** `execute_3_lock_checkout` now takes the pool and commits the CAS, the attempt row and the result separately. No transaction spans a Swiggy call, and `button_router` no longer opens one. Proof: duplicate-tap, concurrent-tap and crash tests in `tests/test_checkout_locks.py`.
2. **UPI arguments were incomplete.** `SwiggyClient.checkout` sends `generateUPIQR=true` for UPI, or `intentApp` when one is given. Proof: `test_upi_checkout_sends_qr_request`.
3. **Not idempotent; retry guard unused.** The pre-checkout snapshot is now required. On timeout/5xx the order list is compared with it, the call retries once only, and `reconcile_attempting_checkouts` resolves attempts left by a crash. Proof: timeout-recovered, clean-failure, unconfirmed and crash tests.
4. **Lock 1 did not bind the approval to the tapper.** The CAS matches `id + user_id`, and the webhook passes the real `message_type` instead of a hardcoded one. Proof: `test_lock_3_cas_rejects_another_user`.
5. **Budget-raise was a dead end.** A cap failure returns the approval to `shown`. The button carries `budget:raise:<approval_id>:<paise>`; the handler raises the cap and re-sends the pay button. Proof: `test_cap_raise_keeps_receipt_payable`.
8. **Dedupe could roll back.** The user and `inbound_messages` rows commit before the turn runs. The per-user lock is session-scoped; a probe proved asyncpg releases it when the connection returns to the pool.

**Fixed in Phase 4 (2026-10-27):**

7. **Pollers could die, spam and skip orders.** `SwiggyAuthExpiredError` is now caught by every loop and by each row inside the payment batch, so one 401 no longer aborts the batch or marks a payment failed. Each order id in a split checkout is polled, and `notified_milestones` (migration 004) sends each order+milestone once. A pending payment older than five minutes is checked on wake rather than failed blindly. Proof: split-milestone, wake-payment and auth-failure tests.

**Fixed in Phase 5 (2026-10-27):**

6. **Park and replay were disconnected.** The webhook now parks as `awaiting_link`, the OAuth callback stores the token and schedules `replay_parked_request`, and the replay runs the stored message through the normal webhook pipeline under a fresh `wamid.replay.*` id. A failed replay puts the row back to `awaiting_link` instead of losing the list. Proof: `test_park_sends_a_signed_reconnect_link`, `test_replay_reruns_a_parked_text_once`, `test_token_expiration_parks_request_and_replays`.

**Honest limit:** none of this is proof that a live order works. It is proof that a live order cannot double-place or charge without a tap.

---

## 5. P1 — Real, Lower Blast Radius

- Money math outside checkout still uses floats and `round()` for paise (`backend/integrations/commerce/schemas.py:90`, `backend/agent/composite_cart.py:137`). The checkout path now parses response rupees through `parse_price_to_paise`.
- Coupons run only on the add-items path. Only the first two applicable coupons are tried. The savings message is built but never sent (`backend/agent/customer_advocate.py:251`).
- Receipt bodies are still truncated at 1024 characters for long fresh baskets (`backend/channels/whatsapp_client.py:46`). Delta receipts now avoid the full dump when the basket already had items.
- The dead go-to add and post-order add buttons were deleted with their dead code in the 2026-10-27 cleanup. `item:change` works. `report_error` is still not wired to chat.
- Rapid messages: the second is still `concurrency_dropped` with no reply. Merge/queue is Batch 2.
- Recipes, list pickers, the full message in the evaluator prompt, grouped search, queue/merge and receipt chunking are Batch 2. Itemized bill, coupon apply, the savings line and the support report are Batch 3.
- DPDP scrubs some fields but leaves `sessions.onboarding_context`, `users.display_name`, delivery coordinates, `address_coords`, the user row, and approval/checkout rows (`backend/agent/dpdp.py:19`, `backend/agent/dpdp.py:112`).
- No RLS on any table and PII is plaintext. The caller-supplied-phone hole was closed in Phase 5 with signed bot links; PKCE state is still in process memory (`backend/integrations/commerce/token_vault.py:73`).
- The landing page footer says "Systems Operational" with no health check, and the page falls back to a fake WhatsApp number (`app/page.tsx:76`, `app/page.tsx:269`).
- Render free plan sleeps, so pollers stop when idle (`render.yaml:6`).
- The app still fails to boot if the database is unreachable at startup, so `/health` cannot report that first failure. It reports later DB failures.

**Fixed in Phase 1 (2026-10-27):** `verify_db.py` table/column/index check, `verify.ps1` offline default, `/health` 503 mapping, `ruff` dev requirements, real test database, DSN guard, live-test marker, mock-based "live" test rename.

**Fixed in Phase 3 (2026-10-27):** checkout transaction boundary, CAS ownership, UPI args, timeout/5xx reconcile, crash reconcile, cap-raise loop, checkout `response_total_paise`, independent inbound dedupe.

**Fixed in Phase 4 (2026-10-27):** real `track_order` with map fallback, honest `store_info`, tappable choices for one-word requests, split-order milestone latch, wake reconciliation, 401 isolation per row.

**Fixed in Phase 5 (2026-10-27):** default-address grounding, switch-with-rebuild, delete guard on the real path, typed-text address add, signed OAuth links, park/replay wired, production WhatsApp mock branch deleted, scripted tests labeled.

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
103 passed, 66 deselected in 1.01s

pytest -q -m "db"
46 passed, 123 deselected in 27.02s

pytest --collect-only -q
169 tests collected

powershell -File verify.ps1 -Db
=== [PASS] Grocer v1.0 verification complete ===
# 2026-10-27 after cleanup: schema check exit 0, ruff clean,
# 103 offline pass, 46 DB pass, Next.js build pass, script exit 0
```

**New in Phase 5:** 12 DB tests in `tests/test_phase5_account.py` (default grounding, switch rebuild, missing-item report, delete guard both ways, typed add with and without PIN, unresolvable text, link-token roundtrip/tamper/expiry, phone-only login rejected, parked replay) and 3 webhook tests in `tests/test_whatsapp_webhook.py` that post the exact Meta JSON for a button tap: duplicate tap, pay tap while locked (spy client never called), and a signed reconnect link. The outbound mock branch was deleted; tests inject a recording client instead.

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
| 0002 | Active | Grounding now uses Swiggy's default address. Fingerprint includes payable paise, so any paise change fails. |
| 0003 | Active with gaps | Coupon guard works. Savings message is not sent. Tracking now calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Amended | The 5-day/no-refresh claim is obsolete. Refresh token exists. Park and replay are wired. Vague staples auto-pick with a working Change/swap; discretionary items show choices. |
| 0005 | Partial | Receipt buttons are Pay, Keep only new (when the basket had items), Change item (vague staples) and Clear. COD and Change Address are still target. |
| 0006 | Partial | ₹1,000 cap stays. Cap-raise now re-opens the same receipt. DPDP is partial. |
| 0007 | Active | Switch clears and rebuilds the basket at the new store. Delete guard runs on the real delete path. Split orders poll every id. |
| 0008 | Partial | Typed-text address add is built. Reorder is fixture-only and needs a past order. |
| 0009 | Amended | Recipes are in v1 as a plan-confirm-add flow (decided 2026-10-27). Fee warning and post-order truth are Phase 7. One-time destination is parked. |
| 0010 | Active | Refresh first, park only on refresh failure. Park status matches replay, and the callback replays in the background. |
| 0011 | Superseded | Replaced by ADR 0012. No extra classification call; candidate evaluation is one call per item and is intentional. |
| 0012 | Active | Groq is primary and the only adapter. Direct Gemini calls are gone; the key is optional. |

---

## 8. Next Action

**Phases 0-5 are done.** Checkout is transaction-safe with reconcile, the read path answers from live Swiggy data, and pollers handle split orders, repeats, 401s and wake. Live smoke on 2026-10-27 proved real reads, a real cart add/restore, 10/10 Groq routes, and a checkout that stops before Swiggy. Migration 004 is applied to both databases and `verify.ps1 -Db` exits 0. The 2026-10-27 doc pass corrected scope and removed stale notes.

**Next: Phase 7 Batch 2 and Batch 3.** Batch 1 is done in code (2026-10-27): honest AI-outage copy, typing and read receipts, delta receipts with Swiggy's cap, Keep only new / Change item, view basket, readable address card, working Change swap, real out-of-stock alternatives, decision logging. Batch 2: list pickers that accept a typed number, a queue that merges additive messages instead of dropping the second one, recipe plan-confirm-add, the full message in the model prompt, grouped search, receipt chunking. Batch 3: coupons on every cart path, savings sent, fee warning, itemized bill, support report wiring. **Then Phase 6 privacy:** finish the DPDP scrub and delete cascade, decide RLS or service-only access, redact logs, add CHECK constraints and `updated_at` triggers.

**Open proofs:** Gate 2 case 7 (needs a past order), case 8 (vague-item behavior is model-dependent), and the Phase 2 latency miss. Re-run the full gate at launch.

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
