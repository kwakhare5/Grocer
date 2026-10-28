# TASKS.md — Grocer v1 Fix Plan

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
| 2 | One brain (Groq) | **PARTIAL 2026-10-27** | Done: one adapter is the only LLM path, the second classification call is gone, direct Gemini calls are gone, the Gemini key is optional, JSON is validated as an object, one retry on transient errors. Proof: live 40-case eval 39/40 (97.5%), 0 unsafe writes, 0 errors. | Open: one read/read miss ("how long till my food arrives" → `store_info`) and per-call latency is not recorded by the harness. Re-run at the launch gate. |
| 3 | Checkout money core | **DONE (simulated) 2026-10-27** | Claim → attempt → call → record, each committed separately. CAS bound to approval + user. Snapshot required; timeout/5xx compares `get_orders`, one retry only; the payment poller reconciles crashed attempts. UPI sends `generateUPIQR` (or `intentApp`). Cap-raise re-opens the same receipt. Dedupe commits before the turn. | `verify.ps1 -Db` exit 0; 95 offline + 31 DB pass. Duplicate, concurrent, crash, timeout, unconfirmed and cap-raise tests: 0 duplicate orders, 0 unapproved orders. |
| 4 | Post-payment truth + Gate 2 | **DONE (code) 2026-10-27** | Real `track_order` with saved coordinates and a delivery-status fallback. Honest store/window answer. Tappable products for one-word requests like "milk". Pollers catch 401s per row, latch each order+milestone once (migration 004), poll every id in a split order, and confirm payments made while Render slept. Live smoke on the real account: reads, cart add/restore, 10/10 Groq routes, checkout lock. Migration 004 applied to the app database. | `verify.ps1 -Db` exit 0: 100 offline + 34 DB pass, ruff clean, Next build pass; 5 read tests + 3 poller tests. Open: Gate 2 case 8 needs a WhatsApp tap, case 7 needs a past order. |
| 5 | Account and address lifecycle | **DONE (code) 2026-10-27** | Grounding uses Swiggy's default address. Switch warns, clears and rebuilds at the new store. Delete guard runs on the real path. Typed-text add geocodes via `recommend_address(query=...)`. OAuth login only accepts a signed bot link. Park/replay runs after the callback. Also deleted the production WhatsApp mock branch and labeled scripted tests. | `verify.ps1 -Db` exit 0: 99 offline + 45 DB, ruff clean, Next build pass. Proof: 12 account tests + 3 webhook button tests. Open: live add/delete of the one throwaway address. |
| 6 | Privacy and data | Pending | Complete DPDP scrub and delete cascade. RLS or service-only access. Log redaction. CHECK constraints and `updated_at` triggers. | Test-schema scrub proof plus a live query after TTL. |
| 7 | Conversation quality and tool coverage | **IN PROGRESS — Batch 1 DONE (code) 2026-10-27; Batch 2 first slice DONE (code) 2026-10-28; Q3 AI load DONE (code) 2026-10-28; Q1/Q2 stored plan DONE (code) 2026-10-28** | Map all 20 tools to capabilities and safety classes. Fill gaps and give honest "not supported" replies. Trust pass done in Batch 1: honest AI-outage copy, 8s per-call budget, read receipts and typing indicator, outcome-based message reactions with sparse card emojis, delta receipt with Swiggy's stock cap, existing-basket delta plus Keep only new / Change item, view basket, readable address card with switch buttons, deterministic vague-staple rule with a working Change button, real out-of-stock alternatives, no blind rank-1, decision logging at both LLM calls, idle-basket notice. Batch 2 first slice: multi-item adds process every item (the old early return dropped the second item), the existing-item prompt is "Add 1 more / Make total 1", and recipe plans run as plan-confirm-add with a `plan_meal` capability, live pricing, Add all or Let me pick, and no write before a tap. Q3: shared Groq call gate and one batched evaluation per turn. Q1/Q2: the priced plan is stored in `sessions.pending_plan` for 30 minutes (migration 005); the model gives amounts and units and Python computes whole packs; Add all, Let me pick, and typed "1 and 3" replies all read the stored plan; a gone SKU is reported missing, never swapped. Open items are tracked in the Phase 7 backlog table below. | Gate after the Batch 3 first slice: `verify.ps1 -Db` exit 0, 137 offline + 61 DB on `grocer_test`, 218 collected. Live WhatsApp run per flow still open; reactions, the live Groq recipe route and a live plan tap await a real message. |
| 8 | Landing page and deploy | Pending | Rebuild per `DESIGN.md` Part B. No phone-entry form. Placeholder number only. Real link from env. Health-driven status, no fake badge. Render reconcile-on-wake verified. | `npm run build` plus a live smoke of the page and one WhatsApp read. |
| 9 | Handoff gate | Pending | Run every gate except a live order. Write a short WhatsApp test checklist for Karan. | Raw output for each gate; checklist in `STATUS.md`. Karan's own order is the final live proof. |

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
| Itemized bill (`get_order_details`) | 3 | OPEN | Needs a real past order for live proof. |
| Support report (`report_error`) | 3 | OPEN | Tool is not reachable from chat. |
| Payment-method truth (UPI only) | 3 | **DONE (code) 2026-10-28** | Answer names UPI as what this build can use and lists COD/Swiggy Money as unusable. Proof: read-action test. |
| Store-open truth | 3 | OPEN | "Is the store open" returns a cart quote, not yes/no. |
| Post-order add truth | 3 | OPEN | A placed order cannot change; say so, then offer a separate order. |

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
| Phase 2 latency | OPEN | Re-run the router eval with per-call latency. |

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
