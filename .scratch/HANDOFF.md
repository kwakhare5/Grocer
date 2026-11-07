# HANDOFF — Grocer — 2026-11-07

**Goal:** fix the address display and the remaining data-hiding defects, then handset-check one message. Checkout stays locked.
**Changes:** coupon copy and reply are honest; disabled coupon tools are cached for one hour so cart writes stop retrying; empty payment list names UPI; live smoke redacts addresses and clears an empty-start cart; test count 290; live cart empty.
**Passing:** `verify.ps1 -Db` exit 0 — 188 offline + 82 DB, ruff, 9 routes; live reads OK; live router 5/5; live cart add → 6 UPI apps → cleared.
**Next action:** address truth fix (full line, no middle cut, long-message split) and view-basket uncap, after Karan's yes. Then push.
**Still broken:** address truncation in the list and switch/delete confirmations; long button replies can exceed 1,024; view basket caps at 20; coupon savings blocked by Swiggy; handset reconnect/address writes/ticks open; demo video missing.

## Current truth

- `main` at `a557c3a` is deployed on Render and Vercel. The coupon cache and doc counts are local commits, not pushed.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- The live cart is empty again.
- Cleanup deletion still needs Karan's explicit line naming the files.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap, coupon savings (account entitlement).

## Proof files

- `.scratch/verify_coupon_20261107.log` — full gate with the coupon cache.
- `.scratch/verify_fixes_20261107.log` — gate with the copy fixes.
- `.scratch/eval_router_groq_20261107_122217.json` — 5/5 live router cases.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width landing proof, byte-identical.
