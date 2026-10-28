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
| 8 | Landing page and deploy | **DONE (code) 2026-10-28; deploy pending** | Rebuilt per `DESIGN.md` Part B in plain language for customers and the Swiggy team: hero with one WhatsApp CTA, live/in-testing feature labels, how it works, safety, privacy, Swiggy strip, FAQ. No phone form, no health badge, no fake numbers, no test stats. OAuth card only for `?t=` or callback. Missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the CTA with a visible note; the placeholder is display-only. | `npm run build` pass; 1440px and real 360px emulation checked with no overflow; `?t=` card renders; CTA disabled without env, enabled with a test env. Vercel deploy and live page smoke still needed. |
| 9 | Handoff gate | **IN PROGRESS** | Checklist written in `STATUS.md` §10. Run every gate except a live order, then a short WhatsApp proof session with Karan. | Raw output for each gate; checklist results in `STATUS.md`. Checkout stays simulated; no order will be placed. |

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

## Open proofs

| Proof | Status | Blocker |
|---|---|---|
| Reaction drawn on a real handset | OPEN | Needs a real inbound wamid after deploy. |
| Live Groq route for "make pizza for 5" | OPEN | Real message on Render. |
| Live Add-all tap and receipt | OPEN | Tap after the recipe route works. |
| Live typed pick against a real plan | OPEN | Handset reply like "1 and 3" after a real plan card. |
| Live Change-item tap | OPEN | Handset tap. |
| Blue ticks and typing indicator | OPEN | Needs a real wamid, not a simulated one. |
| Live address add and delete | OPEN | One throwaway address on Karan's account. |
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
