# HANDOFF — Grocer — 2026-11-07

**Goal:** run the live handset proofs on the deployed build. Checkout stays locked.
**Changes:** structure cleanup merged to `main` and live at `a557c3a`: webhook 1,042 → 436 lines; turn, commands and onboarding split into their own modules; both add paths share one pay-receipt builder; checkout placement and settlement split; both pollers settle one row per transaction; unused `intent_app` and one duplicate CSS rule removed.
**Passing:** `verify.ps1 -Db` exit 0 — 185 offline + 82 DB, ruff, 9 routes; 287 collected; landing screenshots byte-identical at five widths; Render deploy `live` on `a557c3a`; Vercel `/proof` 287.
**Next action:** live handset proofs; send `connect` and finish OAuth first.
**Still broken:** live checkout, reconnect, address add/delete, 24h scrub, demo video; demo video needs Karan's recording.

## Current truth

- `main` at `a557c3a` is deployed on Render and Vercel.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Local `.env` uses the documented dummy WhatsApp number; use production for handset tests.
- `/health` reports `environment: development` on Render; the flag is display-only, but the dashboard should say `production`.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap.

## Proof files

- `.scratch/verify_all_20261107.log` — full gate after the checkout and landing work.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width before/after screenshots, byte-identical.
- `.scratch/verify_structure_final_20261107.log` — gate before this round.
- `.scratch/verify_structure_phase3_20261107.log` — webhook split gate.
