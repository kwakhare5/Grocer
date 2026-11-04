# HANDOFF — Grocer — 2026-11-04

Goal: finish the lean cleanup, clear the frozen cart with the stored token, and run the live scorecard in two halves. No order.
Changes: Gemini adapter, settings and `google-genai` dependency deleted; `complete_json` is Groq-only. Cart cleared through the stored token (0 items) and the first scorecard half ran 12/13, with real adds. Scorecard now redacts saved address lines from proof output; the first-half log and JSON were scrubbed.
Passing: `verify.ps1 -Db` exit 0 — 177 offline + 78 DB, ruff, Next 16.4.3 build; live half one 12/13 (reads 7/8, adds 5/5).
Next action: handset messages arrived at 11:23–11:24 IST, so run `python scripts/scorecard_live.py --start 14 --end 26` at or after 12:25 IST; the bot allows 20 messages per rolling hour and the last handset message was 11:24:30.
Unproven: live scorecard second half, handset taps, live OAuth reconnect, address add/delete, location-pin replay, reactions/blue ticks, 24h scrub. Checkout stays locked.

## Current truth

- Branch: `main` only, tip `a5c1ea9`. The one-provider cleanup and the scorecard redaction are in the working tree, not committed.
- Render: `/health` 200, `{"status":"healthy","database":"connected"}`. Vercel: 255-test build live.
- Tests: 177 offline + 78 DB = 255; 20 live-only deselected; 275 collected.
- Live scorecard first half: 12/13. Case 3 (payment options) returned "No payment methods are available" on an empty cart; the reply was truthful, the case expects `upi`.
- Cart: cleared to 0 before the run; the first half left milk x2, eggs, bread, paneer, gulab jamun and rice in it. No order placed.
- Checkout: `LIVE_CHECKOUT_ENABLED=false`. No real order has ever been placed.

## Decisions needed from Karan

1. Approve committing and pushing the one-provider cleanup plus scorecard redaction.
2. Run the second scorecard half at or after 12:25 IST (20-per-hour cap).
3. Handset taps: Add-all, Change item, typed pick, set/remove picker, OAuth reconnect, address add/delete, 24h scrub.
4. Decide when the first real order happens; checkout stays locked until then.

## Do next, in order

1. `python scripts/scorecard_live.py --start 14 --end 26` at or after 12:25 IST; log to `.scratch/scorecard_20261104_14_26.log`.
2. Clear the test cart through the stored token after the run if Karan wants it empty.
3. Handset proofs, live OAuth, address add/delete and the 24h scrub.
4. Phase 9 handoff, then Karan's first real order.

## Proof files

- `.scratch/verify_gemini_removal_20261104.log` — gate after one provider (177 offline + 78 DB, Next build).
- `.scratch/scorecard_live_20261104_1_13.json` — raw half-one rows, address lines redacted.
- `.scratch/scorecard_20261104_1_13_transcript.log` — readable half-one transcript, address lines redacted.
- `.scratch/live_clear_cart.py` — one-off clear through the stored token; result 0 items before and after.
- `.scratch/verify_lean_20261104.log`, `.scratch/verify_retest_20261104.log` — prior gates.
- `.scratch/live_retest_tracking.log` — real tracking turn, honest empty reply.
- `.scratch/trace_cart_lock_20261103.log`, `.scratch/trace_turn_20261103.log` — real signed turns.
- `.scratch/eval_after_verbs.json` — last 40/40 router eval.
- `.scratch/parked/oauth-state-cookie.patch` — unproven OAuth hardening.

## Operational notes

- **Message cap:** 20 per user per rolling hour, counted from `grocer.inbound_messages`; the 21st is warned, later ones dropped silently.
- **Groq:** free tier; do not run a router eval in the same window as the scorecard.
- **Render deploys:** `GET /v1/services/srv-dagm3fijnfac73e5iod0/deploys?limit=3`; wait for `live` on the exact tip.
- **Secrets:** environment only; never print keys, phone numbers, addresses, or tokens. Proof logs must not contain a saved address.

## Do not

- Do not place an order; checkout stays locked.
- Do not weaken or delete a test to improve the score.
- Do not bypass the 20-per-hour cap by editing production rows.
- Do not claim the full 26-case score until the second half runs.
