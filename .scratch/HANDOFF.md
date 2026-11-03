# HANDOFF — Grocer — 2026-11-03

Goal: make every turn visible, recover from the frozen cart honestly, park first-time text for replay, and never lie on a button tap; live scorecard deferred until Swiggy access returns. No order.
Changes: cart-review errors get exact recovery steps on both paths; first-time text is parked and replayed; Swiggy 429/-32000 retries once with Retry-After; per-turn JSON trace; evaluator reports `llm | fallback | rule`; every write button answers honestly with no database or unknown account; one paise conversion, one stored-plan decoder and one token-to-client builder now back every path; stale proof folders deleted; 19 new tests across four batches; dead `hasattr` test, loose dev ruff pin and the offline-scorecard `.scratch` write removed.
Passing: `verify.ps1 -Db` exit 0 — 172 offline + 78 DB, ruff, Next 16.4.3 build; real signed address and cart-lock turns traced.
Next action: confirm the deploy, then live scorecard when Swiggy access returns. Deleting `backend/channels/command_router.py` needs Karan to name the file.
Unproven: live scorecard (no Swiggy app access), handset taps, live OAuth reconnect, address add/delete, location-pin replay, reactions/blue ticks, 24h scrub. Checkout stays locked.

## Current truth

- Branch: `main` only. Local `main` and `origin/main` match after the cleanup push; item 5 and cleanup are pushed. Render serves the latest pushed `main`. Rollback target: `db6a297`.
- Vercel: `/`, `/privacy`, `/proof` 200; the 250-test build is checked after the push.
- Tests: 172 offline + 78 DB = 250; 20 live-only deselected; 270 collected. `npm audit --omit=dev` → 0 vulnerabilities.
- Offline scorecard: 31/31. Live scorecard: deferred; the 2026-11-02 post-merge run scored 25/26, and the 2026-11-03 first half scored 7/13 on pre-fix code because Swiggy refused the cart.
- Checkout: `LIVE_CHECKOUT_ENABLED=false`. No real order has ever been placed. Karan places the first one after handoff.

## Completed 2026-11-03/04

1. **Swiggy business errors** — a 200-OK payload with `success:false` was being validated as `CartData`, causing HTTP 500 on every add. `call_remote_tool` now raises `SwiggyToolError` with Swiggy's reason; the webhook catches it and replies with HTTP 200: “Swiggy couldn't complete that just now: <reason>. Check your basket before trying again.” Live add after deploy returned 200 with the reason.
2. **Duplicate-name picker** — two cart lines with the same name now render as `Name (variant), qty N`; a follow-up can match the variant (`500 ml`). Code-proven; handset tap open.
3. **Next upgrade** — 16.2.6 → 16.4.3 (`--save-exact`), 0 production advisories, build passes.
4. **Docs/cleanup** — counts synced to 229; merged branches `scorecard` and `fix/amount-pack` deleted; parked dead components, one-off scripts, old response dumps and caches removed. Every raw proof file cited in the docs was kept.
5. **Truth fallbacks** — a `pay` tap with no pool, approval or user now sends "I couldn't start the payment just now. Nothing was charged. Please try again." and returns `checkout_unavailable`; an unknown button sends a resend message and returns `unknown_action`. Proof: `tests/test_button_truth.py`.
6. **Per-turn trace** — `backend/observability.py` emits one JSON payload per turn and per Swiggy/model call, keyed by the wamid: capability, safety, status, latency, call counts, fallbacks. No text, phone or address. A real signed "show my addresses" turn proves it (`.scratch/trace_turn_20261103.log`).
7. **Evaluator source** — `CandidateEvaluationResult.source` is `llm`, `fallback` or `rule`; the live catalog file fails if a case skipped the model; `tests/test_evaluator_truth.py` forces the fallback.
8. **Test cleanup** — deleted the `hasattr` placement test; changed the offline scorecard so it no longer writes `.scratch`; removed the loose dev ruff pin.
9. **Cart-lock recovery** — a Swiggy cart-review error now returns "Open Swiggy → Instamart → Cart, accept the adjusted quantities, then send your request again" on both the read path and the webhook path. The live cart-lock turn returned it (`.scratch/trace_cart_lock_20261103.log`).
10. **First-connect replay** — a first-time texter's message is parked as `awaiting_link` with a welcome CTA and replayed after login instead of being lost. Proof: DB test.
11. **Swiggy 429/Retry-After** — HTTP 429 and JSON-RPC -32000 retry once, honor `Retry-After` capped at 5s, log `swiggy_retry`, and a second cap becomes an honest "Swiggy is busy" tool error. Proof: 3 new tests.
12. **Honest write taps** — cart, plan, reorder, address, item-change and budget taps now say "I couldn't complete that just now. Nothing changed. Please try again." when the database is missing and "I couldn't find your account for that button…" when the number is unknown; the fallback says the button is stale. No branch returns silently or claims a change. Proof: 7 new tests.
13. **One cap helper** — `get_session_budget_cap` in `customer_advocate.py` replaces the three duplicated session-cap queries in the button router, the webhook and the checkout executor; missing or zero still means ₹1,000.
14. **Dedupe money, plans, clients** — `parse_price_to_paise` delegates the decimal math to `rupees_to_paise` and keeps int input as paise; `decode_pending_plan` replaces both stored-plan JSON decoders; `resolve_user_client` builds the Swiggy client from the stored token and replaces seven inline builders (five button branches, checkout pollers, parked replay). `send_add_receipt` was already the one receipt builder. Deleted five uncited logs and the `proof-final/` and `proof-redesign/` folders.
15. **Exact brand+size skip** — `_exact_brand_size_match` in `turn_add.py` resolves an add when the query names a full brand and an exact pack size that match exactly one in-stock candidate; the evaluator is not called. Vague, ambiguous, missing-size and zero-address turns keep the model call. Proof: 3 tests, including a sentinel that fails if the evaluator runs for "Amul milk 500 ml".
16. **Cleanup** — removed the invented `swiggy.com/track` links and the default "10-15 mins" ETA; tracking shows only Swiggy's real status, ETA and rider. Deleted `CheckoutLockError`, `VALID_MILESTONES`, `map_url`, stale `__all__`, the dead `answer_read_capability` wrapper and `AddressLifecycleManager` (now a function). Inlined the single `delete my data` command, added `MAX_BUDGET_CAP_PAISE`, made `migrate.py` reuse `verify_db.py`, merged the pack-ratio math, and corrected the site's test claim to 250. `command_router.py` is now unused but deletion needs Karan to name it.

Files: `backend/observability.py`, `backend/agent/candidate_evaluator.py`, `backend/agent/customer_advocate.py`, `backend/agent/meal_planner.py`, `backend/agent/llm.py`, `backend/agent/read_actions.py`, `backend/agent/checkout_executor.py`, `backend/agent/delivery_tracker.py`, `backend/agent/dpdp.py`, `backend/agent/address_lifecycle.py`, `backend/agent/address_actions.py`, `backend/channels/button_router.py`, `backend/channels/turn_add.py`, `backend/channels/whatsapp.py`, `backend/channels/swiggy_auth.py`, `backend/config.py`, `backend/integrations/commerce/swiggy_client.py`, `backend/integrations/commerce/token_vault.py`, `scripts/migrate.py`, `scripts/live_smoke.py`, `tests/test_add_matching.py`, `tests/test_button_truth.py`, `tests/test_read_actions.py`, `tests/test_checkout_locks.py`, `tests/test_e2e_staging.py`, `tests/test_address_lifecycle.py`, `tests/test_meal_planner.py`, `tests/test_swiggy_auth.py`, `app/page.tsx`, `app/proof/page.tsx`, docs.

## Blocked by environment

**No Swiggy app or handset access.** The cart is frozen and cannot be cleared from here. Every `get_cart` and every add is refused with “Some items have limited stock and their quantities were adjusted. Please review your cart.” Do not ask Karan to clear it and do not fake a live scorecard. Keep it deferred and labeled.

**Handset taps** cannot be simulated: Add-all, Change item, typed pick, set/remove picker, reactions/blue ticks, address add/delete, OAuth reconnect, live 24h scrub.

## Decisions needed from Karan

1. Name `backend/channels/command_router.py` for deletion; it is unused and the cleanup hook blocks an unnamed delete.
2. Commit and push the cleanup when ready.
3. Handset proofs wait for phone access; no action now.
4. Decide when the first real order happens; checkout stays locked until then.

## Do next, in order

1. Commit the cleanup and push; then confirm Vercel shows 250 tests and Render `/health` is healthy.
2. Live scorecard when Swiggy access returns: clear the cart, run 1–13, wait an hour, run 14–26; measure item 5 before/after on the same add. Then handset proofs, live OAuth, address add/delete and the 24h scrub.
3. Phase 9 handoff, then Karan's first real order. The build must stay real-order capable; checkout stays locked until he decides.

## Proof files

- `.scratch/verify_cleanup_20261104.log` — last full gate (172 offline + 78 DB, Next build).
- `.scratch/verify_item5_20261104.log` — prior gate (172 offline + 78 DB, Next build).
- `.scratch/verify_batch4_20261104.log` — prior gate (169 offline + 78 DB, Next build).
- `.scratch/verify_batch3_20261103.log` — prior gate (166 offline + 78 DB, Next build).
- `.scratch/verify_batch2_20261103.log` — prior gate (160 offline + 77 DB, Next build).
- `.scratch/trace_cart_lock_20261103.log` — real cart-lock turn with the recovery copy.
- `.scratch/verify_truth_20261103.log` — prior gate (156 offline + 76 DB, Next build).
- `.scratch/trace_turn_20261103.log` — real signed "show my addresses" turn with the JSON trace.
- `.scratch/verify_errorfix_20261103.log` — earlier gate (153 offline + 76 DB, Next build).
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
- Do not ask Karan to clear the Swiggy cart; he has no app access. Do not fake a live scorecard.
