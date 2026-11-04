# TASKS.md — Grocer Fix Plan

> **Goal:** Swiggy Instamart on WhatsApp. Chat is the front door to everything the Instamart MCP allows.  
> **Scope bar:** all 20 tools in `ARCHITECTURE.md` §4 are reachable by chat or get an honest "not supported" reply. `PRD.md` §3 journeys are examples, not a checklist.  
> **Truth:** `STATUS.md` wins. This file is the plan and phase status.  
> **Done means:** proof command, date, and raw output in `STATUS.md`. A green test is not proof the live product works.

## Fixed decisions (2026-10-27)

1. No live order during the build. Checkout proof uses simulated failures and recorded real responses. Karan places the first real order after handoff.
2. Live address add/delete is allowed on Karan's account for testing: one throwaway address, deleted after.
3. Render stays on the free plan. Pollers reconcile from the database on wake.
4. The landing page has no phone-entry OAuth form. OAuth is a bot-sent bridge only.
5. Recipes are in v1 as a plan-confirm-add flow: propose the ingredient checklist and pack counts, wait for a physical tap, then write. Nothing is added before the tap. Decided by Karan on 2026-10-27.
6. Proactivity is limited to money and truth: fees, the budget cap, stock caps, price drift and expired carts. No upsell, no recommendations. Decided by Karan on 2026-10-27.
7. Replies are English only. Hinglish and Hindi input is understood, never mirrored. Decided by Karan on 2026-10-27.
8. Tests use a separate `grocer_test` database in the same Supabase project. The app schema stays `grocer` in both, so no query has to change.

## v1 Scope (2026-10-27)

The bar is still full tool coverage. These experiences use existing tools, so they are in scope.

| Experience | Status | Rule |
|---|---|---|
| Recipes and meal planning | **IN — Phase 7** | Propose a checklist with pack counts, tap to add. Nothing written before the tap. |
| Fee, cap, stock-cap and price warnings | **IN — Phase 7** | Money and truth only. |
| Post-order add | **IN — Phase 7** | A placed order cannot change. Say so, then offer a separate order. |
| Itemized bill and support report | **IN — Phase 7** | `get_order_details`, `report_error`. |
| One-time destination ("send to Mom") | **PARKED** | Needs Karan's call. No work until then. |
| COD and SwiggyPay | **PARKED** | UPI only for v1. |
| Upsell and recommendations | **OUT** | Proactivity stays limited to money and truth. |

## Checkpoints

| # | Phase | Status | Work | Proof |
|---|---|---|---|---|
| 0 | Doc closeout | **DONE 2026-10-27** | Scope reframed: tool coverage, journeys are examples. Added `TASKS.md`. Synced PRD, AGENTS, STATUS, ARCHITECTURE, DESIGN, GLOSSARY, ADR 0009. The recipe exclusion from this pass was reversed by Karan on 2026-10-27; see the scope table above. | Docs grepped for stale scope claims; placeholder number only. |
| 1 | Safety rails and verification | **DONE 2026-10-27** | `LIVE_CHECKOUT_ENABLED` is enforced in `execute_3_lock_checkout` before any Swiggy call. Created the separate `grocer_test` database; tests run there, the DSN guard refuses any other name. `verify_db.py` checks 8 tables, key columns and indexes. `verify.ps1` is offline by default; `-Db` and `-Live` opt in. `/health` returns 503 when the DB check fails. `ruff` moved to `requirements-dev.txt`. Live Gemini tests are marked `live`; the fake WhatsApp loop test is renamed. | `verify.ps1` exit 0; 94 offline pass; 23 DB pass on `grocer_test`; `grocer` counts unchanged; guard refuses the app DSN. |
| 2 | One brain (Groq) | **DONE 2026-10-28** | One adapter is the only LLM path, the second classification call is gone, direct Gemini calls are gone, the Gemini key is optional, JSON is validated as an object, one retry on transient errors. The old `store_info` miss is fixed by a clear new-basket vs placed-order rule. | Live 40-case eval 40/40 (100%), 0 unsafe writes, 0 under-acted writes, 0 errors; avg 1574ms, p95 2265ms, max 3422ms. Raw: `.scratch/eval_router_20261028_reviewfix.json`. |
| 3 | Checkout money core | **DONE (simulated) 2026-10-27** | Claim → attempt → call → record, each committed separately. CAS bound to approval + user. Snapshot required; timeout/5xx compares `get_orders`, one retry only; the payment poller reconciles crashed attempts. UPI sends `generateUPIQR` (or `intentApp`). Cap-raise re-opens the same receipt. Dedupe commits before the turn. | `verify.ps1 -Db` exit 0; 95 offline + 31 DB pass. Duplicate, concurrent, crash, timeout, unconfirmed and cap-raise tests: 0 duplicate orders, 0 unapproved orders. |
| 4 | Post-payment truth + Gate 2 | **DONE (code) 2026-10-27** | Real `track_order` with saved coordinates and a delivery-status fallback. Honest store/window answer. Tappable products for one-word requests like "milk". Pollers catch 401s per row, latch each order+milestone once (migration 004), poll every id in a split order, and confirm payments made while Render slept. Live smoke on the real account: reads, cart add/restore, 10/10 Groq routes, checkout lock. Migration 004 applied to the app database. | `verify.ps1 -Db` exit 0: 100 offline + 34 DB pass, ruff clean, Next build pass; 5 read tests + 3 poller tests. Open: Gate 2 case 8 needs a WhatsApp tap, case 7 needs a past order. |
| 5 | Account and address lifecycle | **DONE (code) 2026-10-27** | Grounding uses Swiggy's default address. Switch warns, clears and rebuilds at the new store. Delete guard runs on the real path. Typed-text add geocodes via `recommend_address(query=...)`. OAuth login only accepts a signed bot link. Park/replay runs after the callback. Also deleted the production WhatsApp mock branch and labeled scripted tests. | `verify.ps1 -Db` exit 0: 99 offline + 45 DB, ruff clean, Next build pass. Proof: 12 account tests + 3 webhook button tests. Open: live add/delete of the one throwaway address. |
| 6 | Privacy and data | **DONE (code) 2026-10-28** | 24h scrub covers onboarding/coords/geocode cache/expired PKCE states; delete-my-data removes messages and geocodes and anonymizes the user row; phone log removed; migration 006 adds `updated_at` triggers and non-negative money checks. Migration 007 adds the non-superuser `grocer_app` role (DML on the 8 app tables, no CREATE), drops the two never-read columns, and runs every app query as that role; a missing role fails loudly and a DDL attempt is refused. Migrations 009/010 keep the ledger read-only for the app. `anon`/`authenticated` have zero schema usage and zero table grants, so RLS is skipped by design. Migration 008 moves PKCE state into `grocer.oauth_states` with a 10-minute one-time TTL. Startup waits at most 5s for the DB, then `/health` reports 503 and migrations retry with backoff. Money conversion uses Decimal, not float rounding. | `verify.ps1 -Db` exit 0, 142 offline + 66 DB, 228 collected; restricted-role DDL/ledger tests, backdated scrub test, PKCE TTL/expiry test, real dead-DB boot test. Open: live 24h TTL after a real day of traffic. |
| 7 | Conversation quality and tool coverage | **IN PROGRESS — Batch 1 DONE (code) 2026-10-27; Batch 2 DONE (code) 2026-10-28; Batch 3 DONE (code) 2026-10-28** | Map all 20 tools to capabilities and safety classes. Fill gaps and give honest "not supported" replies. Trust pass done in Batch 1: honest AI-outage copy, 8s per-call budget, read receipts and typing indicator, outcome-based message reactions with sparse card emojis, delta receipt with Swiggy's stock cap, existing-basket delta plus Keep only new / Change item, view basket, readable address card with switch buttons, deterministic vague-staple rule with a working Change button, real out-of-stock alternatives, no blind rank-1, decision logging at both LLM calls, idle-basket notice. Batch 2 first slice: multi-item adds process every item (the old early return dropped the second item), the existing-item prompt is "Add 1 more / Make total 1", and recipe plans run as plan-confirm-add with a `plan_meal` capability, live pricing, Add all or Let me pick, and no write before a tap. Q3: shared Groq call gate and one batched evaluation per turn. Q1/Q2: the priced plan is stored in `sessions.pending_plan` for 30 minutes (migration 005); the model gives amounts and units and Python computes whole packs; Add all, Let me pick, and typed "1 and 3" replies all read the stored plan; a gone SKU is reported missing, never swapped. Batch 2 closed with the rapid-message queue, whole-message evaluation, duplicate grouping and receipt chunking. Batch 3 added coupons on every cart path, the savings line, the 35% charges warning, itemised bills, the support report, payment truth, store-open truth and post-order add truth. Open items are tracked in the Phase 7 backlog table below. | Gate after Batch 3: `verify.ps1 -Db` exit 0, 142 offline + 61 DB on `grocer_test`, 223 collected. Live WhatsApp run per flow still open; reactions, the live Groq recipe route and a live plan tap await a real message. |
| 8 | Landing page and deploy | **LIVE 2026-11-02, updated 2026-11-04** | Redesign per `DESIGN.md` Part B: printed sample receipt + 9:16 demo slot in the hero, six job rows with Live / In testing / Opening next, dark three-step safety band with a sample checkout and cap meter, six backend facts led by 20 tools, a small 257-tests line, six FAQs, compact footer. Every sample stamped; no founder, proof-stat band, chat demo, phone form or separate privacy section. Audit fixes: skip links removed, security headers added, upstream error detail stopped, copy claims corrected, full-bleed edges and 1024px hero squeeze fixed. The OAuth state-cookie hardening is parked for a handset test; the proven routes are live. | `verify.ps1 -Db` exit 0 (179 offline + 78 DB, ruff, build); 0 overflow at 1440/1024/768/390/360; first Tab lands on the brand; `/privacy` and `/proof` render; `<20-message` smoke and next-day scorecard pending. Demo video file still missing; phone tap still unproven. |
| 8b | Repo, name and CI hygiene | **DONE 2026-10-28** | `main` is the only branch and holds the current tree; old unrelated history is kept only as tags `legacy-main-2026-10-28` and `legacy-codex-2026-10-28`. Product renamed to "Grocer" in every tracked file. Render deploys `main`; Vercel deploys `main`. Added `README.md` and `quality.yml` (ruff 0.17.3, all non-live tests on throwaway Postgres, Next build) plus `keep_warm.yml`. | `git push --force-with-lease` accepted; Render live with `/health` 200; CI green on `42d5b56`, `da5853a`, and `c4ea0a3`; `verify.ps1 -Db` exit 0 (142 offline + 66 DB, build pass). Vercel CTA verified with 3 `wa.me` links. |
| 9 | Handoff gate | **IN PROGRESS** | Checklist written in `STATUS.md` §10. Run every gate except a live order, then a short WhatsApp proof session with Karan. | Raw output for each gate; checklist results in `STATUS.md`. Checkout stays simulated; no order will be placed. |

## Current next actions (2026-11-03)

Local `main` and `origin/main` match through `a5c1ea9`; the one-provider cleanup and the scorecard redaction are in the working tree. Render serves the latest pushed `main`; Vercel `/` and `/proof` show the 255-test build. Last gate: `verify.ps1 -Db` exit 0 — 177 offline + 78 DB, ruff, Next 16.4.3 build. Offline scorecard 31/31.

**Live scorecard (2026-11-04):** Karan authorized the stored token to read the real cart and add items, no order. The cart was cleared (`clear_cart` verified, 0 items), then both halves ran against the deployed app: **25/26 (96.2%)**, half one 12/13 and half two 13/13. The one miss was case 3's empty-cart payment expectation; case 21 proved the UPI list with items. Case 17 was replaced because dragon fruit is now in stock. The run found a real remove-miss bug: only 3 basket lines were named and the rest silently dropped; fixed with "and N more" plus 2 tests. Scorecard now redacts saved address lines from proof output.

1. Confirm Render `/health` and the 255-test line on Vercel after the deletion push.
2. When Swiggy access returns: clear the cart, run the live scorecard 1–13, wait an hour, run 14–26; measure item 5 before/after on the same add; handset taps; live OAuth; address add/delete; 24h scrub.
3. First real order is Karan's, after handoff. Checkout stays locked.

**What is already done (2026-11-04):** Swiggy `success:false` raises `SwiggyToolError` and gets an honest HTTP 200 reply instead of a 500; set/remove picker labels name pack + quantity; Next 16.4.3 has 0 production advisories. The truth batch adds honest pay/unknown-button replies, a per-turn JSON trace (wamid, capability, safety, latency, Swiggy/model counts), and `source: llm | fallback | rule` on the evaluator. Batch 2 adds exact cart-review recovery steps on both paths, first-connect parking/replay, and one 429/-32000 retry with `Retry-After`. Batch 3 makes every write button honest and folds the session-cap queries into `get_session_budget_cap`. Batch 4 leaves one paise conversion, one stored-plan decoder and one token-to-client builder; stale proof folders are deleted. Item 5 skips the evaluator for a unique exact brand+size add. The cleanup removes invented tracking links, a default ETA, dead code and duplicated helpers; tracking now shows only Swiggy's real status, ETA and rider. The retest proves the skip with three other products and a real live tracking turn with no invented link. Proof: `verify.ps1 -Db` exit 0 (177 offline + 78 DB); `.scratch/verify_retest_20261104.log`; `.scratch/live_retest_tracking.log`; `.scratch/verify_cleanup_20261104.log`; `.scratch/verify_item5_20261104.log`; `.scratch/verify_batch4_20261104.log`; `.scratch/verify_batch3_20261103.log`; `.scratch/trace_turn_20261103.log`; `.scratch/trace_cart_lock_20261103.log`.

## Phase 7 backlog (2026-10-28)

The durable checklist. Update the status here when an item lands; the checkpoint row above stays a summary.

| Item | Batch | Status | Notes |
|---|---|---|---|
| Multi-item extraction and merge | 2 | **DONE (code) 2026-10-28** | Every item in the message is processed. The old single existing-item branch returned early and dropped the rest; it now runs only for one item. Proof: webhook multi-item test. |
| Recipe plan-confirm-add | 2 | **DONE (code) 2026-10-28** | `plan_meal` read capability; model gives dish/servings/ingredient amounts; Python prices live and computes packs; Add all re-checks stock and writes all or none; Let me pick asks for numbers. Live route/tap unproven. |
| Stored plan, pack math, typed picker | 2 | **DONE (code) 2026-10-28** | Migration 005 adds `sessions.pending_plan` and a 30-minute expiry; the plan holds exact spins, prices and packs. `packs_for` maps g/kg, ml/l and pieces to whole packs with a fallback to the model's count. Add all, pick taps and number-shaped replies ("1 and 3") read the stored plan; picks add what is in stock and name the rest. Plan cleared after a write, on expiry, by the 24h scrub and by delete-my-data. Live tap unproven. |
| Existing-item quantity copy | 2 | **DONE (code) 2026-10-28** | "Add 1 more / Make total 1"; buttons add-more first. Proof: webhook test. |
| LLM queue/backoff for free-tier bursts | 2 | **DONE (code) 2026-10-28** | Shared Groq gate spaces calls and parks on 429 / zero-token headers; each model call has an 8s budget and a longer wait fails honestly. 7 queue tests. Live burst behavior not re-tested. |
| Batch item evaluation in one call | 2 | **DONE (code) 2026-10-28** | Multi-item turns make one evaluation call, not one per item; missing entries use deterministic rules with no extra call. A 4-item add is 2 model calls instead of 5. Live turn not measured. |
| List pickers that accept a typed number | 2 | **DONE (code) 2026-10-28** | Number-shaped text against a fresh plan picks those rows with no model call; text with words routes normally; an expired plan is never hijacked. Proof: 6 typed-picker webhook tests. |
| Message merge/queue for a rapid second text | 2 | **DONE (code) 2026-10-28** | The second message polls the per-user advisory lock for up to 12s, then runs against the fresh cart and history. Past that it is marked `concurrency_wait_timeout` and gets an honest resend copy. Proof: wait-then-add webhook test plus timeout route test. Live double-text unproven. |
| Full message in the model prompt | 2 | **DONE (code) 2026-10-28** | The evaluator prompt now carries the customer's whole message next to each extracted query, so brand, size and flavour hints reach the model. Proof: batch test asserts the message reaches the call. Live eval pending. |
| Grouped search for related items | 2 | **DONE (code), narrowed 2026-10-28** | Identical queries in one message share one search and one evaluation; quantities add ("milk and milk" → one line, qty 3). Cross-item grouping was rejected: one search returns a mixed candidate pool that starts the wrong product. Proof: one-search-count webhook test. |
| Receipt chunking over 1024 chars | 2 | **DONE (code) 2026-10-28** | A receipt over the 1024-char button-body limit is sent whole as a text message, then Pay/Clear follow in a short buttons message. Short receipts stay one message. `backend/channels/button_router.py:send_receipt`. Proof: two payload tests. Live long basket pending. |
| Coupons on every cart path | 3 | **DONE (code) 2026-10-28** | Text, buttons, plans, picks and reorder optimize; address switch optimizes at the new store. A coupon that changes items or quantities is refused. Proof: advocate guard tests plus the reorder savings test. |
| Savings line sent | 3 | **DONE (code) 2026-10-28** | Receipts carry `🎟️ Coupon (code): -₹X saved`; reorder and address-switch replies name the coupon and saving. Dead `savings_message` field removed. |
| Fee warning | 3 | **DONE (code) 2026-10-28** | When charges reach 35% of item value, the receipt adds one line with the amount and percent. The ADR 0009 Add Essentials buttons are not built. |
| Itemized bill (`get_order_details`) | 3 | **DONE (code) 2026-10-28** | `order_bill` read capability shows items, line items and total for the last or named order. Live bill waits for a real past order. |
| Support report (`report_error`) | 3 | **DONE (code) 2026-10-28** | `report_issue` (account) files with the order id and returns the reference link and support email. Live filing unproven. |
| Payment-method truth (UPI only) | 3 | **DONE (code) 2026-10-28** | Answer names UPI as what this build can use and lists COD/Swiggy Money as unusable. Proof: read-action test. |
| Store-open truth | 3 | **DONE (code) 2026-10-28** | Answer says there is no open/closed flag and uses the live cart as the honest signal: items adding means the store is taking orders. |
| Post-order add truth | 3 | **DONE (code) 2026-10-28** | `placed_order_add` says the placed order is locked and offers a new basket. |

## Scorecard and simplification (2026-10-28, merged 2026-10-31)

Merged 2026-10-31 in `a8e530c` (PR #3); Render is live on it. The ordered list of what is left lives in `STATUS.md` §8.

Two numbers, never mixed:

- **Offline** — `tests/test_scorecard.py`, 31 cases. The plan is handed to the pipeline, so it scores Python with the model out of the loop (the AI-down floor). **31/31 = 100%**, up from 28/31 before the three fixes below.
- **Live** — `scripts/scorecard_live.py`, 26 cases against the deployed webhook with the real model and real Swiggy. **2026-11-02 post-merge: 25/26 = 96.2% correct by intent** (13/13 + 12/13). The one real miss, "5 kg almonds", is fixed in `38dc084`; the single live case re-run passes 1/1 by adding the available 400 g and naming the shortfall instead of asking. **2026-11-03:** the first half of a full re-run scored 7/13 on pre-fix code because Swiggy refused cart reads/adds ("please review your cart"); after the error fix a live add returns HTTP 200 with the reason. A full 26-case run on the fixed code waits on the cart review.

Each finding was a broken rule, not a bad test sentence. Any message with the same shape hit it.

| Finding | Scope | Fix |
|---|---|---|
| A qualifier was dropped when the model is down — "brown bread" bought white bread | Every brand, variant or flavour request on the model-less path | **FIXED:** candidates are ranked by how many of the customer's words they match (`backend/agent/candidate_evaluator.py`). |
| A pack that did not fit the amount asked, even when an exact pack was already found — "2 kg atta" | Every "N kg / N g / N L" request whose first candidate is the wrong size | **FIXED:** the fewest exact packs are taken before any question (`backend/channels/turn_add.py`, `pack_plan`). |
| No split across pack sizes — "1.5 litres" could not become 1 L + 500 ml | Every amount that needs two packs | **FIXED:** `pack_plan` in `backend/agent/meal_planner.py` finds the fewest packs that add up exactly, capped at 12. |

| Work item | Status |
|---|---|
| Remove the keyword lists from candidate selection (`staple_terms`, `discretionary_hints`, `size_patterns`). One rule: unique best match wins, a tie takes Swiggy's first pick with a Change button, no match with several products shows the choices | **DONE (branch) 2026-10-28** — 85 lines out, 36 in |
| One write verb set: add / set / remove / clear. Delete `change_item`, `change_action`, the patch at `backend/agent/router.py:318` and the branch at `backend/agent/basket_actions.py:148` | **DONE (branch) 2026-10-29** — `set_item` and `remove_item` are the two new verbs; `change_action` is deleted from the schema, the prompt and every reader; the multi-item patch is gone and `handle_change_request` refuses several items with "one item at a time". 223 passed twice, ruff clean. Live: 10/10 verb cases, 0 unsafe, after three quota retries; `set_item` and `remove_item` are live-proven. |
| One plan object carried router → search → pick → write | QUEUED |
| Split the webhook turn into one module per capability group | **DONE (branch) 2026-10-29** — `turn_read.py`, `turn_address.py`, `turn_basket.py`, `turn_add.py`; `whatsapp.py` 1,434 → 926 lines. Pure moves, no logic change; 223 passed twice. |
| Receipt, buttons and approval write out of `run_turn` (move 4b) | **SKIPPED, Karan's call 2026-10-29** — it is the money path and buys no speed; only the file gets shorter. |
| Split `checkout_executor.py` (1,146 lines) | **SKIPPED, Karan's call 2026-10-29** — 16 cohesive functions, money path, cosmetic only. |
| Receipt folded from per-item outcomes, so an item cannot vanish | QUEUED |
| Skip the second model call when brand and size already match exactly | **DONE (code) 2026-11-04** — a unique exact brand+size match is resolved in Python; vague, ambiguous, missing-size and zero-address turns still call the evaluator. Proof: 3 new tests (sentinel proves no call for "Amul milk 500 ml"); `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_item5_20261104.log`. Live before/after waits for adds. |
| Full 40-case router eval after the four verbs | **DONE (branch) 2026-10-31** — 40/40 exact, 0 unsafe, 0 under-acted, 0 errors, avg 1312ms, p95 1735ms; raw `.scratch/eval_after_verbs.json`. |
| Production scorecard baseline and harness fix | **DONE 2026-10-31** — 25/26 by intent; the cash case now accepts cash/delivery/cod while still requiring UPI; raw `.scratch/scorecard_live.json`. |
| Live A/B on the same 26 cases before any merge | **DONE 2026-11-02 post-merge** — 25/26 by intent, same as the production baseline; case 21 clean with the COD checker fix. |
| Merge and deploy to production | **DONE 2026-10-31** — PR #3 merged fast-forward, Render live on `a8e530c`, `/health` 200; smoke reads 2/2 and add 1/1; set/remove hit a duplicate-name picker (labels fixed in code 2026-11-03). |
| Swiggy business errors and Next advisories | **DONE (code) 2026-11-03** — `success: false` raises `SwiggyToolError`; the webhook answers honestly with 200 instead of 500; Next 16.4.3 has 0 production advisories. Proof: 5 new tests; `verify.ps1 -Db` exit 0 (160 offline + 77 DB). |
| Truth fallbacks and turn trace | **DONE (code) 2026-11-03** — pay/unknown-button no-ops now tell the truth; one JSON trace payload per turn and per Swiggy/model call; evaluator reports `llm/fallback/rule`; 4 new tests; dead `hasattr` test and loose ruff pin removed. Proof: `verify.ps1 -Db` exit 0 (160 offline + 77 DB); `.scratch/trace_turn_20261103.log`. |
| Cart recovery, first-connect replay, 429 retry | **DONE (code) 2026-11-03** — cart-review errors return exact recovery steps on both paths; first-time text parks as `awaiting_link` and replays after login; 429/-32000 retries once with `Retry-After` capped at 5s, then fails honestly. Proof: 5 new tests; `verify.ps1 -Db` exit 0 (160 offline + 77 DB); live cart-lock copy in `.scratch/trace_cart_lock_20261103.log`. |
| Honest write-button taps, one session-cap helper | **DONE (code) 2026-11-03** — cart/plan/reorder/address/item/budget taps say "Nothing changed" with no database or unknown account; unknown buttons say stale; the three duplicated cap queries are `get_session_budget_cap`. Proof: 7 new tests; `verify.ps1 -Db` exit 0 (166 offline + 78 DB); `.scratch/verify_batch3_20261103.log`. |
| Dedupe money parser, plan decoder, token-to-client | **DONE (code) 2026-11-04** — `parse_price_to_paise` delegates to `rupees_to_paise`; `decode_pending_plan` replaces both stored-plan decoders; `resolve_user_client` replaces seven inline token-to-client builders; the receipt builder was already single. Five stale logs and the `proof-final/` and `proof-redesign/` folders deleted. Proof: 3 new tests; `verify.ps1 -Db` exit 0 (169 offline + 78 DB); `.scratch/verify_batch4_20261104.log`. |
| Exact brand+size skips the evaluator | **DONE (code) 2026-11-04** — one unique exact brand+size match in an add is resolved before the evaluator; vague, ambiguous, missing-size and zero-address turns still call it. Proof: 3 new tests including a sentinel; `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_item5_20261104.log`. |
| Cleanup — truth, dead code, over-engineering | **DONE (code) 2026-11-04** — invented tracking links and the default ETA removed; dead exception, constants, fields, wrapper and one-method class deleted; `delete my data` inlined; one max-cap setting; `migrate.py` reuses `verify_db.py`; pack math merged; site says 255 tests locally. Proof: `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_cleanup_20261104.log`. |
| Retest with different examples | **DONE 2026-11-04** — skip proven with Nandini, Aashirvaad and Maggi; ambiguous Lay's and size-less Amul still call the evaluator; confirmed copy has no default ETA or link; a real signed "where is my order?" turn returned the honest empty reply with no invented link. Proof: 5 new tests; `verify.ps1 -Db` exit 0 (177 offline + 78 DB); `.scratch/verify_retest_20261104.log`; `.scratch/live_retest_tracking.log`. |
| One provider — Gemini removed | **DONE 2026-11-04** — `_gemini_json`, the `GEMINI_*` settings, `google-genai` and the `gemini` eval choice are deleted; `complete_json` answers only through Groq; ADR 0012 amended and docs synced. Proof: `verify.ps1 -Db` exit 0 (177 offline + 78 DB); `.scratch/verify_gemini_removal_20261104.log`. |
| Pass 2 — live test honesty and a real bug | **DONE 2026-11-04** — case 3 accepts the truthful empty-basket payment answer; case 17 now asks for an item Swiggy does not sell; the remove-miss and ambiguity replies now say "and N more" instead of silently dropping lines. Two tests written red then green; site counts 255 → 257. Proof: `verify.ps1 -Db` exit 0 (179 offline + 78 DB); `.scratch/verify_pass2_20261104.log`. |

## Open proofs

| Proof | Status | Blocker |
|---|---|---|
| Full 26-case live scorecard | **DONE 2026-11-04, 25/26 (96.2%)** | Half one 12/13, half two 13/13. The miss was case 3's empty-cart payment expectation; case 21 proved the UPI list with items. Case 17 replaced because dragon fruit is now in stock. Raw: `.scratch/scorecard_live_20261104_1_13.json`, `.scratch/scorecard_live_20261104_14_26.json`. |
| Reaction drawn on a real handset | OPEN | Needs a real inbound wamid after deploy. |
| Live Groq route for "make pizza for 5" | OPEN | Real message on Render. |
| Live Add-all tap and receipt | OPEN | Tap after the recipe route works. |
| Live typed pick against a real plan | OPEN | Handset reply like "1 and 3" after a real plan card. |
| Live Change-item tap | OPEN | Handset tap. |
| Blue ticks and typing indicator | OPEN | Needs a real wamid, not a simulated one. |
| Live address add and delete | OPEN | One throwaway address on Karan's account. |
| Set/remove picker with duplicate item names | **DONE (code) 2026-11-03; tap OPEN** | Each line now shows its pack variant and quantity, and a follow-up can match the variant. A real handset tap is still unproven. |
| Gate 2 case 7 (reorder) | OPEN | Needs a past order. |
| Gate 2 case 8 (vague item tap) | OPEN | Live tap. |
| Phase 2 latency | **CLOSED 2026-10-28** | 40/40 live eval; avg 1574ms, p95 2265ms, max 3422ms. |
| Live 24h scrub after real traffic | OPEN | Needs a real row older than 24 hours; the backdated-row proof is green on `grocer_test`. |

## Order and dependencies

- 1 blocks 2–9. Do not run DB tests or live checkout before it is green.
- 3 blocks 4, 5 and 9. Money must be safe before post-payment and account work.
- 7 comes after 3–5 so coverage is proven on a safe base. It runs before 6 because these are live customer-facing defects.
- 6 must finish before 9. Data safety is a handoff gate, not an optional cleanup.
- 9 is last. Karan's real order is outside the build.

## Not in scope for v1

- One-time destination orders. Parked until Karan decides.
- COD and SwiggyPay. UPI only.
- Upsell and product recommendations.
- Any paid LLM tier or paid hosting.
- Bulk account operations beyond one throwaway test address.
