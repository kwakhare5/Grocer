# HANDOFF — Grocer — 2026-11-07

**Goal:** structure cleanup without behavior changes. Checkout stays locked.
**Changes:** `chore/structure-cleanup` (unmerged): the conversational turn moved verbatim to `turn_pipeline.py`; media/connect/delete commands to `whatsapp_commands.py`; onboarding to `whatsapp_onboarding.py`; `whatsapp.py` 1,042 → 436 lines; both add paths share one pay-receipt builder; STATUS cut to 207 lines. `main` at `aa395f0` is deployed.
**Passing:** `verify.ps1 -Db` exit 0 — 185 offline + 81 DB, ruff, 9 routes; 286 collected.
**Next action:** decide whether to merge the structure branch, then run the live handset proofs. No push or merge until Karan says.
**Still broken:** live checkout, reconnect, address add/delete, 24h scrub, demo video; checkout split and LLM simplification remain deferred.

## Current truth

- Local `main` is `3aadf93`, one docs commit over origin `c16b924`. Audit fixes live on `chore/audit-cleanup`, unmerged and unpushed.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Cart still holds the live test adds from the 25/26 scorecard. Clear it through the stored token when testing ends.
- Local `.env` uses the documented dummy WhatsApp number; use production for handset tests.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap.

## Proof files

- `.scratch/verify_cleanup_20261104.log` — full gate after the copy/phone pass.
- `.scratch/shoot_3230.mjs` — five-width screenshots, reveal assertions, motion, reduced-motion, no-JS and disclaimer checks.
- `.scratch/final_1440.png`, `final_1024.png`, `final_768.png`, `final_390.png`, `final_360.png` — latest full pages, captured from production.
- `.scratch/final_hero_1440.png`, `final_phone_1440.png`, `final_facts_1440.png`, `final_demo_1440.png`, `final_safety_1440.png` — section crops.
- `.scratch/verify_landing_v7_20261104.log` — previous graphics/motion gate.
