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
| 7 | Conversation quality and tool coverage | **IN PROGRESS — Batch 1 DONE (code) 2026-10-27** | Map all 20 tools to capabilities and safety classes. Fill gaps and give honest "not supported" replies. Trust pass done in Batch 1: honest AI-outage copy, 8s turn budget, read receipts and typing indicator, outcome-based message reactions with sparse card emojis, delta receipt with Swiggy's stock cap, existing-basket delta plus Keep only new / Change item, view basket, readable address card with switch buttons, deterministic vague-staple rule with a working Change button, real out-of-stock alternatives, no blind rank-1, decision logging at both LLM calls, idle-basket notice. Open: list pickers that accept a typed number, message merge/queue, full message to the model, recipe plan-confirm-add, grouped search, receipt chunking, coupons on every cart path, savings sent, fee warning, support report wiring. | Batch 1: `verify.ps1 -Db` exit 0, 108 offline + 47 DB on `grocer_test`, 175 collected. Dead-code cleanup (net -770 lines; 1,212 removed, 442 added) landed 2026-10-27. Live WhatsApp run per flow still open; reactions await a real inbound wamid. |
| 8 | Landing page and deploy | Pending | Rebuild per `DESIGN.md` Part B. No phone-entry form. Placeholder number only. Real link from env. Health-driven status, no fake badge. Render reconcile-on-wake verified. | `npm run build` plus a live smoke of the page and one WhatsApp read. |
| 9 | Handoff gate | Pending | Run every gate except a live order. Write a short WhatsApp test checklist for Karan. | Raw output for each gate; checklist in `STATUS.md`. Karan's own order is the final live proof. |

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
