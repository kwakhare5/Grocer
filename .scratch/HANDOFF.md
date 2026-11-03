# HANDOFF — Grocer — 2026-11-03

Goal: close the handset proofs and the live scorecard; the error/picker/Next work is live. No order.
Changes: Swiggy `success:false` errors now get an honest 200 reply (never a 500); set/remove picker labels include pack + qty; Next 16.4.3 with 0 advisories; 5 new tests; docs synced.
Passing: `verify.ps1 -Db` exit 0 — 153 offline + 76 DB, ruff, Next 16.4.3 build.
Next action: Karan accepts the adjusted cart in Swiggy, then run live scorecard cases 14–26 (an hour after the first half).
Unproven: full 26/26 run, handset taps, live OAuth reconnect, address add/delete, reactions/blue ticks, 24h scrub. Checkout stays locked.

## Current truth

- Branch: `main` only. Code fix `1468b16`; docs-only commits sit on top. Rollback target: `db6a297`.
- Render: live on the latest commit, `/health` 200. Vercel: `/`, `/privacy`, `/proof` 200; the page and proof say 229 tests.
- Tests: 153 offline + 76 DB = 229; 20 live-only deselected; 249 collected. `npm audit --omit=dev` → 0 vulnerabilities.
- Offline scorecard: 31/31. Live scorecard: 25/26 on 2026-11-02; the 2026-11-03 first half scored 7/13 on pre-fix code because Swiggy refused the cart.
- Checkout: `LIVE_CHECKOUT_ENABLED=false`. No real order has ever been placed. Karan places the first one after handoff.

## Completed 2026-11-03

1. **Swiggy business errors** — a 200-OK payload with `success:false` was being validated as `CartData`, causing HTTP 500 on every add. `call_remote_tool` now raises `SwiggyToolError` with Swiggy's reason; the webhook catches it and replies with HTTP 200: “Swiggy couldn't complete that just now: <reason>. Check your basket before trying again.” Live add after deploy returned 200 with the reason.
2. **Duplicate-name picker** — two cart lines with the same name now render as `Name (variant), qty N`; a follow-up can match the variant (`500 ml`). Code-proven; handset tap open.
3. **Next upgrade** — 16.2.6 → 16.4.3 (`--save-exact`), 0 production advisories, build passes.
4. **Docs/cleanup** — counts synced to 229; merged branches `scorecard` and `fix/amount-pack` deleted; parked dead components, one-off scripts, old response dumps and caches removed. Every raw proof file cited in the docs was kept.

Files: `backend/integrations/commerce/swiggy_client.py`, `backend/channels/whatsapp.py`, `backend/agent/basket_actions.py`, `tests/test_swiggy_client_errors.py`, `tests/test_whatsapp_webhook.py`, `tests/test_basket_actions.py`, `package.json`, `package-lock.json`, docs.

## Blocked on Karan

**Swiggy cart review.** Swiggy returns: “Some items have limited stock and their quantities were adjusted. Please review your cart.” Every `get_cart` and every add is refused until this is cleared. Open Swiggy, accept the adjusted cart, then tell the agent.

**Handset taps** cannot be simulated: Add-all, Change item, typed pick, set/remove picker, reactions/blue ticks, address add/delete, OAuth reconnect, live 24h scrub.

## Decisions needed from Karan

1. Accept the adjusted quantities in Swiggy so the cart works again.
2. Approve item 5 (skip the second model call) or leave it queued.
3. Pick a time for the handset proofs (Add-all, Change item, typed pick, set/remove, reactions, address add/delete, OAuth reconnect).
4. Decide when the first real order happens; checkout stays locked until then.

## Do next, in order

1. Karan accepts the adjusted cart in Swiggy.
2. Run the remaining live scorecard:
   `python scripts/scorecard_live.py --start 14 --end 26`
   The bot caps one number at 20 messages an hour.
3. For a full 26 on fixed code: run `--start 1 --end 13`, wait at least an hour, then 14–26. Never both halves in one hour.
4. Handset proofs with Karan. Check each reply and the orders/basket on screen, not just HTTP 200.
5. Item 5 (skip the second model call when brand and size match) — only after adds work, with Karan's approval and a fresh Groq token window. Row 4 is the before-number: 40/40, avg 1312ms.
6. Phase 9 handoff, then Karan's first real order. The build must stay real-order capable; checkout stays locked until he decides.

## Proof files

- `.scratch/verify_errorfix_20261103.log` — last full gate (153 offline + 76 DB, Next build).
- `.scratch/scorecard_final_1_13.log` — 2026-11-03 half-run (7/13, pre-fix code, Swiggy cart refusal).
- `.scratch/scorecard_live.json` — last single live add after the fix (HTTP 200, reason in the reply; the harness shows “(no reply found)” because a failed add turn is not written to session history).
- `.scratch/scorecard_live_20261030.json`, `.scratch/scorecard_post_merge_*.log` — earlier 25/26 evidence.
- `.scratch/eval_after_verbs.json` — last 40/40 router eval (avg 1312ms).
- `.scratch/parked/oauth-state-cookie.patch` — unproven OAuth hardening; proven login/callback routes are live.

## Operational notes

- **Render logs API:** `GET https://api.render.com/v1/logs?ownerId=<owner>&resource=srv-dagm3fijnfac73e5iod0&limit=100&direction=backward`. The key in `.env` is quoted; strip quotes. `resource` must be the plain service id.
- **Render deploys:** `GET /v1/services/srv-dagm3fijnfac73e5iod0/deploys?limit=3`; wait for `live` on the exact tip.
- **Groq:** free tier, 8k tokens/min and a rolling 200k/day. A 26-case scorecard costs about half a day; a 40-case router eval is another large block. Do not run both in one window.
- **Message cap:** 20 messages/hour/user. A 26-case run must be split into two halves at least an hour apart.
- **Database:** app data in `grocer`; tests only in `grocer_test`. Run DB tests with `verify.ps1 -Db`, never against the app DSN.
- **Deploy path:** push `main`; Render and Vercel auto-deploy. No other branch should exist.
- **Secrets:** environment only; never print keys, phone numbers, or addresses in docs or chat.

## Do not

- Do not place an order; checkout stays locked.
- Do not weaken or delete a test to make the score look better.
- Do not run live Swiggy writes beyond the allowed throwaway address.
- Do not claim the full 26-case score on fixed code until it is actually run.
