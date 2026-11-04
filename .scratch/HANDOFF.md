# HANDOFF — Grocer — 2026-11-04

Goal: finish the lean cleanup, run the full live scorecard, and fix what it finds. No order.
Changes: Gemini adapter and `google-genai` deleted; cart cleared through the stored token; both scorecard halves run for 25/26. Pass 2 fixed the remove-miss truncation (now says "and N more") and corrected two live cases; site counts moved to 257. Scorecard redacts saved address lines.
Passing: `verify.ps1 -Db` exit 0 — 179 offline + 78 DB, ruff, Next 16.4.3 build; live scorecard 25/26 (12/13 + 13/13).
Next action: handset taps, live OAuth reconnect, address add/delete, the 24h scrub, then the demo video and Karan's first real order.
Unproven: handset taps, live OAuth reconnect, address add/delete, location-pin replay, reactions/blue ticks, 24h scrub, demo video. Checkout stays locked.

## Current truth

- Branch: `main` only, tip `effcb83`. Pass 2 (basket fix, tests, scorecard cases, site counts) is uncommitted. Not pushed.
- Render: `/health` 200, `{"status":"healthy","database":"connected"}`. Vercel: 255-test build live.
- Tests: 179 offline + 78 DB = 257; 20 live-only deselected; 277 collected.
- Live scorecard: 25/26 (96.2%). The miss was case 3's empty-cart payment expectation; case 21 proved UPI with items. Case 17 was replaced because dragon fruit is now in stock.
- Cart: cleared before the run, then the live adds left 14 items (~₹3.4k), including the pasta plan items from a handset session. No order placed.
- Checkout: `LIVE_CHECKOUT_ENABLED=false`. No real order has ever been placed.

## Decisions needed from Karan

1. Approve committing and pushing pass 2.
2. Handset taps: Add all, Let me pick → typed pick, Change item, same-name picker, quantity picker.
3. Handset taps: Add-all, Change item, typed pick, set/remove picker, OAuth reconnect, address add/delete, 24h scrub.
4. Decide when the first real order happens; checkout stays locked until then.

## Do next, in order

1. Handset taps, live OAuth reconnect, address add/delete and the 24h scrub.
2. Clear the test cart through the stored token when Karan is done testing.
3. Demo video, then Phase 9 handoff and Karan's first real order.

## Proof files

- `.scratch/verify_gemini_removal_20261104.log` — gate after one provider (177 offline + 78 DB, Next build).
- `.scratch/scorecard_live_20261104_1_13.json` — raw half-one rows, address lines redacted.
- `.scratch/scorecard_20261104_1_13_transcript.log` — readable half-one transcript, address lines redacted.
- `.scratch/scorecard_live_20261104_14_26.json` — raw half-two rows (13/13).
- `.scratch/verify_pass2_20261104.log` — gate after the basket fix (179 offline + 78 DB).
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
- Do not claim a perfect 26/26; the recorded live score is 25/26.
