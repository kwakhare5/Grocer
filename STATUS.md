# STATUS.md — Grocer Current Truth

> **Updated:** 2026-11-07
> **Authority:** This is the only current status document. `PRD.md` is the v1 target. `ARCHITECTURE.md` is the design plus known gaps. `DESIGN.md` is the WhatsApp UI plus the website landing page. `TASKS.md` is the plan. `JOURNAL.md` is append-only history. `docs/adr/` records decisions, amended not rewritten.
> **Rule:** DONE needs a proof command, date, and raw output. Everything else is PARTIAL, BROKEN, or NOT VERIFIED. A green test is not proof that the live product works.
> **History:** the pre-2026-11-07 detailed proof log is preserved in git at `aa395f0` and in `JOURNAL.md`; this page keeps current state, open proofs and rules only.

---

## 0. Environment & Fixed Constraints

| Item | Current fact |
|---|---|
| Git | `main` is `aa395f0` and deployed. Work branch `chore/structure-cleanup` has three code commits plus this docs pass, is not pushed and not merged. Rollback target: `db6a297`. |
| Supabase | One project until launch. App data lives in the `postgres` database, schema `grocer` (8 app tables + `schema_migrations`); migrations 001–010 applied. Tests use the separate `grocer_test` database. |
| LLM | Groq `openai/gpt-oss-120b` is the only LLM, through `backend/agent/llm.py`. Free tier: 8k tokens/minute, 200k/day; pace live runs. |
| Swiggy auth | Allowlisted OAuth redirect `https://grocerr.vercel.app/`. Backend calls `https://mcp.swiggy.com/im` with the customer token. |
| Checkout | `LIVE_CHECKOUT_ENABLED=false`, enforced in code before any Swiggy call. The build is real-order capable; no live order. |
| Order cap | ₹1,000 default (`100000` paise); raises need a tap and stay under the max cap. |
| Hosting | Render free plan (sleeps when idle); pollers reconcile from the database on wake. Vercel hosts the landing page. `keep_warm.yml` was deleted 2026-11-07. |
| Landing number | The page renders no phone number. The chat link comes only from `NEXT_PUBLIC_WHATSAPP_NUMBER`. |
| Product goal | Chat is the front door to all 20 Instamart tools. `PRD.md` §3 journeys are examples, not a checklist. |
| Build-time order policy | No live order during the build. Checkout proof is simulated plus recorded responses. Karan places the first real order after handoff. |
| Address test writes | One throwaway address on Karan's account may be created and deleted. |
| Landing OAuth | Number-first, ownership-proven. The form mints a signed 10-minute code; the bot sends the login link only to the matching `wa_id`. Handset connect + OAuth passed 2026-11-04; live reconnect is open. The state-cookie/origin patch stays parked in `.scratch/parked/oauth-state-cookie.patch`. |
| Landing page | Live on Vercel. Palette, graphics, motion, phone mock and copy pass are in `c16b924`; `/proof` shows the current counts. `public/demo.mp4` is absent, so the demo stage shows the recording state. No `/proof` link on the landing. |
| Next.js | 16.4.3; `npm audit --omit=dev` reports 0 vulnerabilities. |
| Test isolation | The DSN guard refuses any test DSN that is not `grocer_test`. Tests never write the real `grocer` schema. |

---

## 1. Current State — One Screen

| Item | State |
|---|---|
| Current gate | **PASS 2026-11-07:** `verify.ps1 -Db` exit 0 — schema, ruff, 185 offline + 82 database tests, Next 16.4.3 build with 9 routes. |
| Test collection | **287 tests:** 185 offline, 82 DB, 20 live-only, 92 of the offline tests scripted. Live is excluded by default. |
| Production deploy | `main` auto-deploys Render and Vercel. The structure cleanup was verified live at `a557c3a`: Render deploy `dep-dbnhbjm8bjmc73a800ng` is `live`, `/health` returns 200 with `database: connected`, the webhook exposes no test hooks, and Vercel `/proof` shows 287. |
| Structure cleanup | Merged to `main` at `a557c3a`: `whatsapp.py` 1,042 → 436 lines; the conversational turn moved verbatim to `turn_pipeline.py` (377 lines); media/connect/delete commands moved to `whatsapp_commands.py`; location and typed-address steps moved to `whatsapp_onboarding.py`; both add paths share one pay-receipt builder; `checkout_executor.py` split into placement and `checkout_settlement.py`; both background pollers claim and settle one row per transaction; the unused `intent_app` option and one duplicate CSS rule are gone. |
| Router eval | **40/40 exact (2026-10-31):** 0 unsafe writes, 0 under-acted, 0 errors; avg 1312ms, p95 1735ms, max 1889ms. |
| Offline scorecard | **31/31 (2026-10-28):** Python checks with the model out of the loop. |
| Live scorecard | **25/26 by intent (2026-11-04):** half one 12/13, half two 13/13. The one miss was an empty-cart payment expectation, later disproved with items. |
| Live Swiggy smoke | **PASS 2026-10-27:** real token and MCP; 3 addresses, 20 milk products, 12-item cart read, 0 orders, 10 payment methods, 0 coupons; cart add verified then restored. No order. |
| Live reads/writes | Reads recorded live 2026-10-26/27. Add, set, remove and clear routed live 2026-10-29. Live add/delete address and reconnect remain open. |
| Checkout | **Never live-tested.** Money core is simulated; the lock is enforced. No order has ever been placed. |
| DPDP | 24h scrub, delete-my-data, geocode cleanup and `grocer_app` least-privilege role are built. Live 24h TTL after real traffic is pending. |
| Open proofs | Live checkout; OAuth reconnect; address add/delete; 24h scrub; typed plan pick; same-name picker; reactions/blue ticks/typing on a real wamid; demo video. |
| P0 | **No P0 open.** |

---

## 2. Gate 2 — Actual Results

Gate 2 is read-only. No checkout, order, payment call, or address write is in scope.

| # | Customer says | Required | Actual | Result |
|---|---|---|---|---|
| 1 | "How much is Amul milk?" | Real price and pack size; cart untouched | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 2 | "Is Amul milk in stock?" | Real availability at the default store | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 3 | "Which store? When will it arrive?" | Real store and delivery window | Honest cart quote; Swiggy exposes no store name or window before an order | **PASS (honest)** |
| 4 | "What addresses do I have?" | Saved addresses, default marked | Live 2026-10-27: 3 addresses, default marked | **PASS** |
| 5 | "Show my last orders" | Real history; 0 is truth | Live 2026-10-27: 0 orders, said so | **PASS** |
| 6 | "Where is my order?" | Track the order or say there are none | `track_order` with saved coords; `get_delivery_status` fallback; empty account says so | **PASS (no-order path live)** |
| 7 | "Reorder that" | Build the basket, stop before checkout | Fixture-proven only; the account has 0 orders | **PARTIAL** |
| 8 | "milk" | Never silently substitute | Staple auto-picks with a working Change item; discretionary items show choices | **PASS (code) — handset tap pending** |

---

## 3. Capability Truth

| Safety class | Capabilities | Reality |
|---|---|---|
| **read** (13) | chat, item_info, store_info, view_basket, list_addresses, order_history, order_bill, track_order, list_coupons, payment_options, cancel_help, plan_meal, placed_order_add | Ten are live-proven. `view_basket` reads the real cart and is fixture-tested. `plan_meal` is built and fixture-proven; its live Groq route and Add-all tap are unproven. `store_info` gives the live cart quote and says Swiggy exposes no store/window. `track_order` uses saved coordinates, else delivery status. |
| **basket** (5) | add_items, set_item, remove_item, clear_basket, reorder | Add, set, remove and clear routed live on 2026-10-29. Reorder's live write is blocked by the locked checkout. One routing call plus one batched evaluation per turn. |
| **account** (4) | add_address, switch_address, delete_address, report_issue | Address list works live. Switch warns, clears and rebuilds at the new store. Delete is blocked while a delivery is in flight. Live add/delete remains unproven. |
| **money** (1) | checkout | Button path is wired end to end; text "place the order" returns a not-ready reply by design. Never live-tested. |

**Capability count:** 23 declared. 22 are dispatched from the router; `checkout` is reachable only from the pay button, by design (Lock 1).

---

## 4. P0 — Fix Before Any Live Order

**No P0 is open as of 2026-11-07.** The money core commits the claim, attempt and result separately; the CAS binds approval + user; timeout/5xx reconciles against `get_orders`; crashed attempts are reconciled; the lock is enforced before any Swiggy call. The historical P0 fixes are in `JOURNAL.md` and git history.

**Honest limit:** none of this proves a live order works. It proves a live order cannot double-place or charge without a tap.

---

## 5. P1 — Real, Lower Blast Radius

- Live 24h scrub after real traffic is pending; the backdated-row proof is green on `grocer_test`.
- A first-time location pin is not parked for replay; the customer must resend it after connecting. First-time text is parked.
- Reorder and the live itemised bill need a past order. No order has been placed.
- Reactions, blue ticks and typing are unproven on a real wamid. A direct reaction call returned 200; simulated wamids cannot be reacted to.
- Live OAuth reconnect and live address add/delete are open. Handset connect + first OAuth passed 2026-11-04.
- The demo video is absent; the stage shows the recording state.
- CI runs after Render auto-deploys `main`. It reports failures; it does not gate the deploy.
- Coupons run on every cart write and the guard is tested; a live coupon-saving receipt is not recorded.
- Receipts over 1024 chars are sent whole with Pay/Clear in a short follow-up; a live long basket is pending.
- The read confidence floor is 0.00; write classes keep their floors (basket 0.80, account 0.85, money 0.95).
- `LIVE_CHECKOUT_ENABLED=false` must stay the default until Karan's first real order.

---

## 6. Test Truth (2026-11-07)

| Kind | Where | Proves | Does not prove |
|---|---|---|---|
| Live smoke | `scripts/live_smoke.py` | Real Swiggy reads, a real cart add/restore, real Groq routing, the checkout lock stopping before Swiggy | That a live order completes |
| Scripted tests | `tests/test_checkout_locks.py`, `ScriptedClient`, 92 marked tests | Grocer's own logic on failure paths that cannot be triggered on demand | Any live Swiggy behavior |
| Fixture tests | `tests/test_staging_fixtures.py`, `tests/fixtures/` | Response shapes parse | That the live service returns them today. Fixtures are hand-written with placeholder IDs, not recorded live responses. |
| DB tests | `-m db` on `grocer_test` | Real SQL, constraints, CAS, pollers against real Postgres | Nothing about Swiggy |
| Turn trace | `backend/observability.py` + a real signed turn | Request id, capability, safety, latency, Swiggy/model counts | Correctness; it measures, it does not grade |

```
ruff check backend tests
All checks passed!

pytest -q -m "not db and not live"
185 passed, 102 deselected

pytest -q -m "db"
82 passed, 205 deselected

pytest --collect-only -q
287 tests collected
```

Live tests are excluded by default (`-m live` opts in). Scripted tests are never counted as live proof. No test was weakened to pass.

---

## 7. ADR Status

| ADR | Status | Current note |
|---|---|---|
| 0001 | Amended | 25ms ACK and 50ms button path are targets. The webhook is synchronous today. |
| 0002 | Active | Grounding uses Swiggy's default address. The fingerprint includes payable paise. |
| 0003 | Active | Coupon guard works; a coupon that changes items is refused; savings show on receipts. Tracking uses `track_order` with saved coordinates. |
| 0004 | Amended | Refresh token exists. Park and replay are wired. Vague staples auto-pick with a working Change. |
| 0005 | Partial | Receipt buttons are Pay, Keep only new, Change item and Clear. COD is parked; address change starts from the address card. |
| 0006 | Partial | ₹1,000 cap stays. Cap-raise re-opens the receipt. The DPDP scrub and delete cascade are built; app queries run as `grocer_app`. RLS is skipped because public roles have zero schema access. |
| 0007 | Active | Switch clears and rebuilds the basket at the new store. Delete guard runs on the real path. Split orders poll every id. |
| 0008 | Partial | Typed-text address add is built. Reorder is fixture-only and needs a past order. |
| 0009 | Amended | Recipes are plan-confirm-add. The priced plan is stored for 30 minutes; Python computes packs. One-time destination is parked. |
| 0010 | Active | Refresh first; park only on refresh failure. The callback replays in the background. |
| 0011 | Superseded | Replaced by ADR 0012. |
| 0012 | Active, amended 2026-11-04 | Groq is the only LLM; item evaluation is one batched call per turn. |

---

## 8. Next Action

**Where we are (2026-11-07).** `main` at `a557c3a` is live on Render and Vercel; `/health` is 200 and Vercel `/proof` shows 287. The structure cleanup is merged and deployed. The gate is green at 185 offline + 82 DB, ruff and 9 routes.

**Do next, in order:**
1. Live handset proofs: OAuth reconnect, address add/delete, typed plan pick, same-name picker, reactions/blue ticks.
2. Check the 24h scrub after a real day of traffic.
3. Add `public/demo.mp4` and verify the player, or keep the recording stage.
4. Decide whether to merge `chore/structure-cleanup`.
5. The first real order is Karan's, after handoff. Checkout stays locked.

**No push or merge without Karan's explicit go.** No live order during the build.

---

## 9. Rules for Every Future Chat

1. Read `STATUS.md`, `.scratch/HANDOFF.md`, and the latest `JOURNAL.md` entry before planning.
2. Do not edit code without showing the exact plan and getting `proceed`.
3. Do not place an order during the build. `LIVE_CHECKOUT_ENABLED=false` must stay enforced in code.
4. Cart changes need approval. Tests never write the real `grocer` schema.
5. Do not fake Swiggy, Groq, WhatsApp, or the database.
6. Do not claim a live result you did not run. Label it "recorded" or "not verified".
7. Do not delete data without listing it first.
8. Do not weaken a test to pass. If the feature is broken, say so.
9. Show `git diff`, test output, and database proof.
10. Update `STATUS.md`, `.scratch/HANDOFF.md`, and `JOURNAL.md` before ending the session.
11. A Swiggy `success:false` answer is an error, not data. Raise `SwiggyToolError`; the customer gets the reason with HTTP 200, never a 500.

---

## 10. Handoff Checklist (Phase 9)

Run in this order. Do not press Pay; checkout stays locked.

1. ~~Commit and push the current tree.~~ DONE 2026-10-28; `main` is deployed.
2. ~~Render deploy and `/health` 200.~~ DONE; re-verify after any push.
3. ~~Vercel `NEXT_PUBLIC_WHATSAPP_NUMBER` and deploy.~~ DONE; production returns 200.
4. WhatsApp, non-payment:
   - `1 litre milk` → receipt plus one reaction. (Receipt passed live; reaction unproven.)
   - `what's in my basket` → full basket. (Passed live.)
   - `make pizza for 5` → plan card; Add all; typed pick on a fresh plan.
   - Tap `Change item` on a vague staple.
   - Two quick messages → both answered, no lost write.
   - Long basket → whole receipt, Pay/Clear follow-up.
   - `show payment options` → UPI only.
   - `is the store open` → honest cart signal.
   - `show my addresses` → real list; add and delete one throwaway address.
   - Reconnect Swiggy once from a bot link; confirm the callback returns to WhatsApp.
   - Check blue ticks/typing on a real inbound message.
5. Leave `delete my data` off the main account; it would wipe the only real token.
6. After 24 hours of real traffic, verify the scrub with a read-only query.
7. Record each result here; any failure stays open.

**Not included:** checkout, reorder, live bill, Gate 2 case 7. They need a real past order, and no order will be placed during the build.
