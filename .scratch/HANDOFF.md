# HANDOFF — Grocer — 2026-11-07

**Goal:** finish the coupon/payment truth fixes, then run one handset message. Checkout stays locked.
**Changes:** landing coupon claim qualified; coupon read returns a plain unavailable reply; empty payment list names UPI; `live_smoke.py` redacts addresses, reads payment apps with a test item and clears an empty-start cart; test count 289; live cart left empty.
**Passing:** `verify.ps1 -Db` exit 0 — 187 offline + 82 DB, ruff, 9 routes; live reads OK; live router 5/5; live cart add → 6 UPI apps → cleared to 0 items / ₹0.
**Next action:** commit the fixes, then push on Karan's word. Then one WhatsApp message from him for the delivery layer.
**Still broken:** coupon savings blocked by Swiggy entitlement; handset reconnect/address writes/ticks open; demo video missing; LLM prompt trim deferred.

## Current truth

- `main` at `a557c3a` is deployed on Render and Vercel. The new fixes are local and uncommitted.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- The live cart is empty again after the cart sweep.
- The cleanup deletion was blocked by the host; it needs Karan's explicit instruction naming the files.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap, coupon savings (account entitlement).

## Proof files

- `.scratch/verify_fixes_20261107.log` — full gate after the copy and smoke fixes.
- `.scratch/eval_router_groq_20261107_122217.json` — 5/5 live router cases.
- `.scratch/verify_all_20261107.log` — gate before this round.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width landing proof, byte-identical.
