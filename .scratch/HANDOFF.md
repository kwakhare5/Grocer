# HANDOFF — Grocer — 2026-11-07

**Goal:** audit cleanup without behavior changes. Checkout stays locked.
**Changes:** three local commits on `chore/audit-cleanup` (unmerged): checkout settlement off the event loop; public webhook hooks removed; test-pool leak closed; button lookups/auth replies deduped and background sends tracked; docs truth pass with counts 286/185/81/20/92, UPI-only pay copy, honest fixture provenance, parked map/Send-to-Mom claims.
**Passing:** `verify.ps1 -Db` exit 0 — 185 offline + 81 DB, ruff, 9 routes; DB suite green; 0 leaked `grocer_test` connections.
**Next action:** decide whether to push/merge the branch, then run the live proofs (reconnect, address add/delete, 24h scrub, typed pick, same-name picker, reactions/ticks) and add the demo video. No push or merge until Karan says.
**Still broken:** live checkout, reconnect, address add/delete, 24h scrub, demo video; LLM simplification deferred.

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
