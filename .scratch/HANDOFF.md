# HANDOFF — Grocer — 2026-11-07

**Goal:** finish the audit leftovers without behavior changes. Checkout stays locked.
**Changes:** `chore/structure-cleanup` (unmerged, unpushed): webhook 1,042 → 436 lines; turn, commands and onboarding split into their own modules; both add paths share one pay-receipt builder; checkout placement and settlement split into `checkout_executor.py` + `checkout_settlement.py`; both pollers settle one row per transaction; unused `intent_app` and one duplicate CSS rule removed. `main` at `aa395f0` is deployed.
**Passing:** `verify.ps1 -Db` exit 0 — 185 offline + 82 DB, ruff, 9 routes; 287 collected; landing screenshots byte-identical at five widths.
**Next action:** live handset proofs (reconnect first), then the router prompt trim after the token budget resets, then merge on Karan's explicit go.
**Still broken:** live checkout, reconnect, address add/delete, 24h scrub, demo video; demo video needs Karan's recording.

## Current truth

- Local `main` is `aa395f0`, deployed on Render and Vercel. The structure branch is local only.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Local `.env` uses the documented dummy WhatsApp number; use production for handset tests.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap.

## Proof files

- `.scratch/verify_all_20261107.log` — full gate after the checkout and landing work.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width before/after screenshots, byte-identical.
- `.scratch/verify_structure_final_20261107.log` — gate before this round.
- `.scratch/verify_structure_phase3_20261107.log` — webhook split gate.
