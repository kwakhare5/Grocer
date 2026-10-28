# STATUS.md — Grocer Current Truth

> **Updated:** 2026-10-28  
> **Authority:** This is the only current status document. `PRD.md` is the v1 target. `ARCHITECTURE.md` is the design plus known gaps. `DESIGN.md` is the WhatsApp UI plus the website landing page. `JOURNAL.md` is append-only history. `docs/adr/` records decisions, amended not rewritten.  
> **Rule:** DONE needs a proof command, date, and raw output. Everything else is PARTIAL, BROKEN, or NOT VERIFIED. A green test is not proof that the live product works.

---

## 0. Environment & Fixed Constraints

| Item | Current fact |
|---|---|
| Git branch | `main` is the only branch and deploys Render and Vercel |
| Supabase | One project until launch. App data lives in the `postgres` database, schema `grocer` (8 app tables + `schema_migrations`). Both the app database and `grocer_test` are migrated through 010 (app DB applied 2026-10-28; `schema_migrations` lists 001–010). |
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
| Doc truth pass | **DONE 2026-10-28:** corrected pre-Batch-3 claims in ARCHITECTURE Layer 2/4, DESIGN A2/A6/A8/A9, PRD payment, GLOSSARY fee term, ADR index rows 0003–0006/0009, STATUS counts/constraints/next action, and the verify-grocer skill. No code changed. |
| Landing page (Phase 8) | **DONE (code) 2026-10-28, deploy pending:** rebuilt per `DESIGN.md` Part B in plain language for customers and the Swiggy team. Live/in-testing labels, safety, privacy, Swiggy strip and FAQ; no fake uptime or test numbers. OAuth card only for `?t=` or callback. Missing env disables the CTA with a visible note; the placeholder number is display-only. `npm run build` pass; checked at 1440px and real 360px emulation with no overflow. Vercel deploy not run. |
| Lint | **PASS 2026-10-28:** `ruff check backend tests` → `All checks passed!` |
| Offline tests | **PASS 2026-10-28:** 142 passed, 86 deselected (`pytest -q -m "not db and not live"`). |
| DB tests | **PASS 2026-10-28:** 66 passed on `grocer_test` (`pytest -q -m "db"`). |
| Live tests | **20 live-only tests collected, not run.** `test_catalog_search.py` calls the live router/model path and is marked `live`. |
| Full test collection | **228 tests collected 2026-10-28.** |
| Full suite claim | The old "136 passed, 0 skipped" claim is retired. The current verified set is 142 offline + 66 DB (228 collected, 20 of them live-only); live is excluded by default. Scripted tests are marked `scripted` and never counted as live proof. |
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
| Live Batch 1 check | **PASS (routing) 2026-10-28:** real signed messages to the Render app. `milk` → HTTP 200 `cart_updated` in 11.9s; latest approval is ₹283 with 2 items including milk. `what's in my basket` → HTTP 200 `view_basket` in 4.8s, 359-char reply with 2 item bullets. `show my addresses` → HTTP 200 `list_addresses` in 4.1s, 366-char card with 3 numbered entries. No order, no checkout. Blue ticks/typing are unproven because the wamid was simulated. Fixed 2026-10-28: session history now stores the real receipt (see the next row). |
| Live basket receipt | **PASS 2026-10-28:** after the receipt fix, a real `1 litre doodh` turn returned a full basket with `＋` on the new line, `You had 3 items (₹283)` and `Your Basket (4 items)`. No "Ask *what's in my basket*" copy. The receipt is stored in session history now. |
| Live natural-language eval (20 cases) | **MIXED 2026-10-28:** 20 messy messages against Render, real Groq + real Swiggy, no fixtures. 13/20 answered on the first pass. 7/20 got the honest AI-outage copy from Groq's 8k TPM burst limit; retried with 20s spacing, 5/7 then passed. Genuine failures: `make pizza for 5 people` asked "How many pizza bases?" instead of a recipe plan, and `add milk and bread` only handled the milk. Copy gap: the existing-milk prompt says "Do you want the total to be 1, or 1 more?" which is confusing. `show payment options` lists COD and Swiggy Money even though v1 supports UPI only; `is the store open` gives a quote, not a yes/no. Raw: `.scratch/live_eval_20.json` and `.scratch/live_eval_retry.json`. |
| Reactions and card emojis | **DONE (code) 2026-10-28:** one reaction per inbound message, chosen by Python from the turn outcome (`backend/channels/reactions.py`), sent off the critical path after the reply (`backend/channels/whatsapp.py`). 🏠 addresses, 🛒 basket, 📦 orders, 🛵 tracking, 🎟️ coupons, 💳 payments, 🍳 meal plan; ❓ when the bot needs a choice; 📍 when it asks for a pin. No reaction on chat, misses, locks, auth or outages. Cards carry at most one header emoji (address, orders, track, coupons, payments, reorder); error and money copy carries none. Payload: `backend/channels/whatsapp_client.py`. Proof: `verify.ps1 -Db` exit 0, 113 offline + 52 DB, including a signed-webhook test that asserts exactly one 🏠 for an address question. Meta's live reaction delivery is unproven until a real inbound wamid is reacted to. |
| Batch 2 first slice | **DONE (code) 2026-10-28:** multi-item text adds now process every requested item. Root cause of the eval failure `add milk and bread`: the single existing-item branch returned early and dropped bread. That branch now runs only when exactly one item is asked for, and its copy/buttons say "Add 1 more" / "Make total 1". Recipe plans are live in code as plan-confirm-add: a new `plan_meal` read capability carries dish + servings + ingredient packs from the model; `backend/agent/meal_planner.py` searches and prices each line; `[Add all]` re-checks live stock and writes all ingredients or none; `[Let me pick]` asks for item numbers. The plan card is stored in dialogue history. No hardcoded recipe list (ADR 0011). Proof: 5 new offline tests, 5 new webhook tests, 1 router test; full gate 113 offline + 52 DB. The live Groq route for "make pizza for 5" and a live Add-all tap are not tested yet. |
| Q3 AI load fix | **DONE (code) 2026-10-28:** one Groq call gate shared by routing and item evaluation (`backend/agent/llm.py`). Calls are spaced; a 429 or a zero-token header parks every thread until the reset; a wait longer than an 8-second call budget fails honestly instead of hanging. Multi-item turns now evaluate all items in one model call (`evaluate_customer_intents_batch`), with per-item deterministic fallback and no extra call (`backend/agent/candidate_evaluator.py`). A 4-item add drops from 5 model calls to 2. Proof: `verify.ps1 -Db` exit 0, 120 offline + 52 DB, 192 collected; 7 new queue/batch tests. Live Groq burst behavior is not re-tested. |
| Q1/Q2 stored plan and pack math | **DONE (code) 2026-10-28:** the exact priced recipe plan is stored in `grocer.sessions.pending_plan` with a 30-minute expiry (migration 005), replacing the old base64 button token. The model now gives each ingredient an amount and unit (`250 g`, `1 l`, `5 pieces`); Python reads the store pack size (`backend/agent/meal_planner.py:parse_pack_size`) and computes whole packs, falling back to the model's pack count when the store text cannot be compared. Add-all re-checks live stock and writes all or none; the confirmed SKU is never swapped for a lookalike — a gone SKU is reported missing. Picks write only the chosen rows. The plan is cleared after a write, on expiry, by the 24-hour DPDP scrub, and by "delete my data". The numbered reply to `Let me pick` is now real: number-shaped text ("1 and 3") picks items with no model call, and anything with words routes normally. Proof: new pack-math, stored-spin, gone-SKU, partial-pick, expired-plan, typed-picker and plan-cap tests; `verify.ps1 -Db` exit 0, 142 offline + 61 DB, 223 collected. Live recipe route and a live tap are still unproven. |
| Router eval (live Groq) | **PASS with one miss 2026-10-27:** 39/40 exact (97.5%), 0 unsafe writes, 0 under-acted writes, 0 LLM errors. Miss: "how long till my food arrives" → `store_info`, expected `track_order`. Latency was not recorded by the harness. Raw: `.scratch/eval_phase2.json`. |
| Router eval rerun (live Groq) | **PASS 2026-10-28:** 40/40 exact (100%), 0 unsafe writes, 0 under-acted writes, 0 remaining LLM errors. Latency: avg 1574ms, p95 2265ms, max 3422ms. One 429 on case 11 was retried and passed. Raw: `.scratch/eval_router_20261028_reviewfix.json`. |
| One LLM brain | **DONE 2026-10-27:** routing and candidate evaluation both call `backend/agent/llm.py`. Direct Gemini calls and the second classification call are gone. Gemini key is optional. |
| Live reads | Recorded live on 2026-10-26: price/stock, addresses, order history, cancel help, payment options, coupons. Not re-run on 2026-10-27. |
| Live refresh | Recorded 2026-10-26: forced refresh returned a new token pair; new expiry 2026-11-25. Journal also records a fixture-only refresh proof. Treat the live proof as recorded, not re-verified. |
| Live checkout | **Never tested. No order placed.** |
| Migration 004 | **VERIFIED 2026-10-27:** `python scripts/migrate.py` applied `004_checkout_milestones.sql` to the app database; `verify_db.py` exits 0 with 8 tables, `notified_milestones` present, and the required indexes. `grocer_test` is also at 004. |
| Phase 6 privacy slice | **DONE (code) 2026-10-28:** 24h scrub clears onboarding state/context, plan-time coordinates, geocode rows older than 24h, and expired PKCE states. "delete my data" deletes inbound messages and geocodes, clears plan/onboarding/coords, and anonymizes the user row. Migration 006 adds `updated_at` triggers and non-negative money checks. Migration 007 adds the non-superuser `grocer_app` role (DML on the 8 app tables, no CREATE) and drops the two never-read columns; 009/010 make the migration ledger read-only for that role. App queries run as that role, a DDL attempt is refused, and a missing role fails loudly. `anon`/`authenticated` have zero schema usage and zero table grants, so RLS is skipped by design, not by omission. Migrations 001–010 are applied to the app DB. No Render env change was made. Live 24h scrub after a real TTL is pending. |
| Block 1 hardening | **DONE (code) 2026-10-28:** PKCE state moved from process memory to `grocer.oauth_states` with a 10-minute TTL and one-time consume (migration 008); expired rows are deleted on consume and by the scrub. Startup waits at most 5 seconds for the DB, then serves with `/health` 503 and retries migrations with backoff. Migrations run on a separate owner connection; the app pool refuses to run without `grocer_app`, so there is no owner fallback. Rupee-to-paise conversion uses `Decimal(str(value))` in every schema property and the order bill. Proof: 141 offline, 66 DB, 227 collected; real dead-DB subprocess test, role DDL/ledger-refusal test, PKCE TTL/expiry test, backdated scrub test. |
| Migration 005 | **APPLIED 2026-10-28:** `python scripts/migrate.py` added `sessions.pending_plan` and `sessions.pending_plan_expires_at` to the app database; `verify_db.py` exits 0. `grocer_test` applied it through the DB suite. Render applies pending migrations at startup on the next deploy. |
| Migrations 007–010 | **APPLIED 2026-10-28:** `python scripts/migrate.py` applied 007 (grocer_app role, two dropped columns), 008 (`grocer.oauth_states`), 009 (ledger write revoked), and 010 (ledger read restored) to the app database. `verify_db.py` exits 0 with 9 tables, proves app queries run as `grocer_app`, no CREATE on `grocer`, and no INSERT on `schema_migrations`. `grocer_test` applied them through the DB suite. |
| Live deploy 50fc967 | **PASS 2026-10-28:** pushed `b03573c..50fc967` to `origin/main`; Render deploy `dep-dbgugmi9lscs7394rr80` built that commit and reached `live`. `GET https://grocer-backend-qwk4.onrender.com/health` → HTTP 200 `{"status":"healthy","database":"connected","app":"Grocer","environment":"development"}`. No env var was changed. |
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
| **read** (13) | chat, item_info, store_info, view_basket, list_addresses, order_history, order_bill, track_order, list_coupons, payment_options, cancel_help, plan_meal, placed_order_add | Ten are live-proven. `view_basket` reads the real cart and is fixture-tested; it needs a WhatsApp read. `plan_meal` is built and fixture-proven (2026-10-28), stores its priced plan for 30 minutes, and accepts a typed numbered pick; the live Groq route for "make pizza for 5" is not tested. `store_info` gives the live cart quote and says Swiggy does not expose the store or window. `track_order` calls the tracking tool when coordinates are saved, else delivery status. |
| **basket** (4) | add_items, change_item, clear_basket, reorder | `add_items` works live and handles multiple items in one message. Change, clear and reorder are fixture-proven only. Reorder's live write is blocked. `add_items` makes one routing call plus one batched evaluation call per turn (changed 2026-10-28; ADR 0012 amended). |
| **account** (4) | add_address, switch_address, delete_address, report_issue | Address list works live. Switch warns, clears and rebuilds the basket at the new store. Delete is blocked while a delivery is in flight and guarded again on the final tap. Typed-text add geocodes and reuses the flat/name/city steps. Live add/delete is still unproven (needs the one throwaway address). |
| **money** (1) | checkout | Button path is wired end to end and no longer holds a DB transaction across the Swiggy call. Text "place the order" returns a not-ready reply by design: Lock 1 requires a physical tap. Never live-tested; no order placed. |

**Capability count:** 22 declared. 21 are dispatched from the router; `checkout` is reachable only from the pay button, by design (Lock 1).

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

- Money conversion uses `Decimal(str(value))` in every schema property and the order bill; no float `round()` remains in the paise path. The charge percentage is integer math.
- Coupons run on every cart write (text, buttons, plans, picks, reorder, address switch). Only the first two applicable coupons are tried, a coupon that changes items or quantities is refused, and savings show on the receipt and in reorder/switch replies.
- Receipts over the 1024-char button limit are sent whole as a text message, with Pay/Clear in a short follow-up (`send_receipt`). The interactive body limit itself still truncates any other long body; those bodies are short by design.
- The dead go-to add and post-order add buttons were deleted with their dead code in the 2026-10-27 cleanup. `item:change` works. `report_issue` now files a Swiggy report and returns the reference and support email; itemised bills use `get_order_details`.
- Rapid messages: the second waits up to 12 seconds for the first turn, then answers against the fresh cart. A turn still running after that gets an honest resend reply (`concurrency_wait_timeout`).
- Recipes are built in code (2026-10-28) with a stored plan, typed picks, queueing, whole-message evaluation, duplicate grouping and receipt chunking. Batch 3 is code-complete: coupons on every cart path, savings line, 35% charges warning, itemised bill, support report, payment truth, store-open truth and post-order add truth.
- DPDP: the 24h scrub clears history, plan, onboarding state/context, plan-time coordinates, the geocode cache and expired PKCE states; "delete my data" deletes inbound messages and cached geocodes and anonymizes the user row (`deleted-<uuid>`, no name, no Swiggy id) while audit rows keep an anonymous id. App queries run as `grocer_app`, which has DML on the 8 app tables and read-only access to the ledger; the backdated-row scrub is proven on `grocer_test`, while live TTL verification is pending.
- No RLS policies, by design: `anon` and `authenticated` have zero schema usage and zero table grants (checked 2026-10-28). PII is plaintext except Swiggy tokens; disk encryption is Supabase's. The caller-supplied-phone hole was closed in Phase 5 with signed bot links; PKCE state now lives in `grocer.oauth_states`, not process memory.
- The landing page was rebuilt on 2026-10-28: no health badge, no fake uptime, no fallback WhatsApp link. Missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the button with a visible note; the display number stays the placeholder. The OAuth card appears only for a bot link or callback.
- Render free plan sleeps, so pollers stop when idle (`render.yaml:6`).
- Startup waits at most 5 seconds for the database, then serves with `/health` returning 503 and retries migrations with backoff. A dead DB no longer crashes the process.

**Fixed in Phase 1 (2026-10-27):** `verify_db.py` table/column/index check, `verify.ps1` offline default, `/health` 503 mapping, `ruff` dev requirements, real test database, DSN guard, live-test marker, mock-based "live" test rename.

**Fixed in Phase 3 (2026-10-27):** checkout transaction boundary, CAS ownership, UPI args, timeout/5xx reconcile, crash reconcile, cap-raise loop, checkout `response_total_paise`, independent inbound dedupe.

**Fixed in Phase 4 (2026-10-27):** real `track_order` with map fallback, honest `store_info`, tappable choices for one-word requests, split-order milestone latch, wake reconciliation, 401 isolation per row.

**Fixed in Phase 5 (2026-10-27):** default-address grounding, switch-with-rebuild, delete guard on the real path, typed-text address add, signed OAuth links, park/replay wired, production WhatsApp mock branch deleted, scripted tests labeled.

**Observed live 2026-10-27:** calling `update_cart` on a 12-item real cart (₹1751 quote) left all 12 items and quantities intact but Swiggy priced three lines at ₹0 (NOICE peanut butter, Alt Co almond beverage, Amul butter), so its own total became ₹753. Nothing was removed by Grocer. Lock 2 would abort checkout on that drift, which is the intended behavior, but the cause is Swiggy-side and worth watching.

---

## 6. Test Truth (2026-10-28)

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
142 passed, 86 deselected

pytest -q -m "db"
66 passed, 161 deselected

pytest --collect-only -q
228 tests collected

python scripts/eval_router.py --provider groq
Exact capability match: 40/40 (100.0%)
Latency (last call per case): avg 1574ms, p95 2265ms, max 3422ms
Unsafe writes: 0, under-acted: 0, errors: 0
# 2026-10-28 after Block 1 hardening + review fixes:
# schema check exit 0 (9 tables, grocer_app), ruff clean,
# 142 offline pass, 66 DB pass, Next.js build pass, script exit 0
```

**New in Block 1 (2026-10-28):** restricted-role test (`current_user = grocer_app`, DDL refused), live/expired PKCE state test, backdated 24-hour scrub test, and a subprocess boot test with an unreachable DB. The router eval rerun scored 40/40 with latency.

**New in Q1/Q2 (2026-10-28):** pack math (`packs_for`: g/kg, ml/l, pieces), stored-plan shape, stored-spin preference, add-all all-or-nothing, partial picks that name the missing rows, numbered-reply parsing, an expired-plan tap that writes nothing, a typed pick that adds only the chosen row, a normal text that is not hijacked, and numbers with an expired plan that route normally. Proof: 12 planner tests, 8 webhook tests, 1 router test.

**New in Batch 2 first slice and reactions (2026-10-28):** 5 meal-planner tests (`test_meal_planner.py`: card contents, Add-all rebuild, missing ingredient blocks the whole write, button-length limit), 1 router test (plan fields and read safety), 2 payload/mapping tests (reaction payload, sparse map), 1 webhook reaction test (exactly one 🏠 for an address question), and 5 webhook tests (multi-item merge, clearer existing-item prompt, recipe card with no write, Add-all tap with Pay, missing ingredient with no write). The unsent savings line, coupon paths, queue/merge and receipt chunking remain unproven by design.

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
| 0003 | Active | Coupon guard works, a coupon that changes cart items is refused, savings are on the receipt, and reorder/switch replies name them. Tracking now calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Amended | The 5-day/no-refresh claim is obsolete. Refresh token exists. Park and replay are wired. Vague staples auto-pick with a working Change/swap; discretionary items show choices. |
| 0005 | Partial | Receipt buttons are Pay, Keep only new (when the basket had items), Change item (vague staples) and Clear. COD is parked; address change happens from the address card. |
| 0006 | Partial | ₹1,000 cap stays. Cap-raise now re-opens the same receipt. The DPDP scrub and delete cascade are built; app queries run as `grocer_app` with no DDL. RLS is skipped because public roles have zero schema access. |
| 0007 | Active | Switch clears and rebuilds the basket at the new store. Delete guard runs on the real delete path. Split orders poll every id. |
| 0008 | Partial | Typed-text address add is built. Reorder is fixture-only and needs a past order. |
| 0009 | Amended | Recipes are in v1 as a plan-confirm-add flow (decided 2026-10-27; built in code 2026-10-28). The exact priced plan is stored in `grocer.sessions.pending_plan` for 30 minutes; the model gives amounts and units and Python computes packs. The fee warning and post-order truth are built. One-time destination is parked. |
| 0010 | Active | Refresh first, park only on refresh failure. Park status matches replay, and the callback replays in the background. |
| 0011 | Superseded | Replaced by ADR 0012. No extra classification call; candidate evaluation is one call per item and is intentional. |
| 0012 | Active, amended 2026-10-28 | Groq is primary and the only adapter. Direct Gemini calls are gone; the key is optional. Item evaluation is one batched call per turn, not one per item. |

---

## 8. Next Action

**Where we are (2026-10-28).** Phases 0, 1, 3, 4 and 5 are done. Phase 2 is done after the 40/40 live rerun with latency recorded. Phase 6 is done in code: DPDP, `grocer_app`, dead columns, and durable PKCE state. Phase 7 is code-complete. Phase 8 is built in code (Vercel deploy pending); Phase 9 handoff remains. The last full gate is green: 142 offline + 66 DB, 228 collected; live router eval 40/40, avg 1574ms, p95 2265ms. `main` replaces the old unrelated history; `50fc967` was live on Render on branch `grocer-v1`, and the switch to `main` is in progress. The old `main` and codex tips are kept as tags `legacy-main-2026-10-28` and `legacy-codex-2026-10-28`.

**Phase 7 backlog — code-complete; live proofs open.**

| # | Item | State | Proof needed |
|---|---|---|---|
| 1 | LLM queue/backoff for Groq free-tier bursts | **DONE (code) 2026-10-28** | 20-case live run with 0 first-pass outages |
| 1b | Batch item evaluation in one call | **DONE (code) 2026-10-28** | Live multi-item turn shows 2 model calls, not 5 |
| 1c | Stored plan + amount-to-pack math | **DONE (code) 2026-10-28** | Live recipe route; a live Add-all tap that reads the stored plan |
| 2 | List pickers that accept a typed number | **DONE (code) 2026-10-28** | Live reply "1 and 3" against a real plan card |
| 3 | Message merge/queue for rapid second text | **DONE (code) 2026-10-28** | two quick messages both answered, conflicting writes serialized; live double-text unproven |
| 4 | Full message in the model prompt | **DONE (code) 2026-10-28** | batch test proves the whole text reaches the evaluator; live check pending |
| 5 | Grouped search for related items | **DONE (code), narrowed 2026-10-28** | identical queries share one search and one evaluation; cross-item grouping rejected because it mixes candidate pools |
| 6 | Receipt chunking over 1024 chars | **DONE (code) 2026-10-28** | long receipt sent whole as text, Pay/Clear follow in a short message; live long basket pending |
| 7 | Coupons on every cart path; savings line sent | **DONE (code) 2026-10-28** | every cart write optimizes (text, buttons, plan, picks, reorder, address switch); savings show on the receipt and in reorder/switch replies; a coupon that changes items is refused |
| 8 | Fee warning | **DONE (code) 2026-10-28** | charges at 35% or more of item value get one honest warning line on the receipt |
| 9 | Itemized bill (`get_order_details`) | **DONE (code) 2026-10-28** | `order_bill` capability; fixture-proven; live bill waits for a real past order |
| 10 | Support report (`report_error`) | **DONE (code) 2026-10-28** | `report_issue` (account) files with the order id and returns the reference; live filing unproven |
| 11 | Payment-method truth (UPI only) | **DONE (code) 2026-10-28** | answer names UPI as the only supported method and says COD/Swiggy Money cannot be used here |
| 12 | Store-open truth | **DONE (code) 2026-10-28** | cart quote plus the honest open signal: items adding means the store is taking orders; no invented flag |
| 13 | Post-order add truth | **DONE (code) 2026-10-28** | `placed_order_add` says the order is locked and offers a new basket |

**After Phase 7:** Phase 6 is done in code (DPDP scrub/delete, `grocer_app` role, dead columns, durable PKCE state, lazy boot, integer paise). Live 24h TTL proof is pending. Phase 8 is built in code; the Vercel deploy is pending. Phase 9 handoff remains. No live order during the build.

**Open proofs:** reactions drawn on a real handset; live Groq route for "make pizza for 5" and a live Add-all tap; live Change-item tap; blue ticks/typing with a real wamid; live address add/delete; Gate 2 case 7 (needs a past order) and case 8 (live tap); live 24-hour scrub after real traffic. Re-run the full gate at launch.

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

---

## 10. Handoff Checklist (Phase 9)

Run in this order. Do not press Pay; checkout stays locked.

1. ~~Commit and push the current tree after Karan approves.~~ DONE 2026-10-28: `50fc967` on `origin/main`.
2. ~~Render deploy: wait for `/health` 200.~~ DONE 2026-10-28: deploy `dep-dbgugmi9lscs7394rr80` for `50fc967` is `live`; `/health` is 200 with `database: connected`. Still open: one live read from the bot (`what's in my basket`) and a live reaction/blue-tick check on a real wamid. No env changes.
3. Vercel: set `NEXT_PUBLIC_WHATSAPP_NUMBER`, deploy, open the page at 360px and desktop, and confirm the CTA opens the real chat.
4. WhatsApp, non-payment:
   - `1 litre milk` → receipt plus one reaction.
   - `what's in my basket` → full basket.
   - `make pizza for 5` → plan card; tap Add all; then try a typed pick on a fresh plan.
   - tap `Change item` on a vague staple.
   - send two messages quickly → both answered, no lost write.
   - long basket → whole receipt, Pay/Clear follow-up.
   - `show payment options` → UPI only, no COD claim.
   - `is the store open` → honest cart signal.
   - `show my addresses` → real addresses; add and delete one throwaway address.
   - Reconnect Swiggy once from a bot link; confirm the callback returns to WhatsApp.
   - Check blue ticks/typing on a real inbound message.
5. Leave `delete my data` off the main account; it is proven on `grocer_test` and would wipe the only real token.
6. After 24 hours of real traffic, verify the scrub with a read-only query.
7. Record each result in `STATUS.md`; any failure stays open.

Not included: checkout, reorder, live bill, Gate 2 case 7. They need a real past order, and no order will be placed.
