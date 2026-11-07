# HANDOFF — Grocer — 2026-11-07

**Goal:** verify the deployed truth fixes, then handset-check one message. Checkout stays locked.
**Changes:** full Swiggy address lines in the list and confirmations; long read replies split into text plus buttons; View basket shows up to 60 items; coupon tools cached when disabled; verify-grocer skill synced; dead Gumloop note, Chrome profiles, probe scripts and both merged branches removed.
**Passing:** `verify.ps1 -Db` exit 0 — 191 offline + 82 DB, ruff, 9 routes; 293 collected; live reads OK; live router 5/5; live cart add → 6 UPI apps → cleared.
**Next action:** confirm the Render/Vercel deploy, then one handset message for the delivery layer.
**Still broken:** handset reconnect/address writes/ticks; coupon savings blocked by Swiggy; demo video missing.

## Current truth

- `main` carries four local commits on top of the live `a557c3a`: coupon truth, coupon cache, address/view truth, cleanup. The push and deploy verification are next.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- The live cart is empty again.
- `.scratch` is 22MB; only `main` remains; the repo and global `verify-grocer` skills match.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap, coupon savings (account entitlement).

## Proof files

- `.scratch/verify_address_truth_20261107.log` — full gate with the address/view/skill fixes.
- `.scratch/verify_coupon_20261107.log` — gate with the coupon cache.
- `.scratch/eval_router_groq_20261107_122217.json` — 5/5 live router cases.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width landing proof, byte-identical.
