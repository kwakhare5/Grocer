# HANDOFF — Grocer — 2026-11-04

**Goal:** launch-ready v1. Checkout stays locked.
**Changes:** graphics + motion pass — eight ink feature marks, hero grocery cluster, four-node How route, safety lock, route draw, receipt print/stamp, button press, nav/feature underlines, Try reply crossfade, mascot hover. Palette and handset connect are already pushed; this pass is local only.
**Passing:** gate v7 — 182 offline + 81 DB, ruff, 9 routes; 0 overflow and 0 console errors at 1440/1024/768/390/360; route line 0 → 0.34 at 120ms → 1, nodes 0 → 1, bill item 0.96 at 150ms, stamp 0 → 1; reduced-motion and no-JS keep all content visible; no new dependencies.
**Next action:** review `http://localhost:3229`; say push to put the graphics on Vercel; add `public/demo.mp4`; then the remaining live journeys.
**Still broken:** graphics are not on Vercel until a push; demo video absent; live reconnect, address add/delete, 24h live scrub, typed plan, same-name picker, reactions/ticks and location pin remain open.

## Current truth

- Remote `main` is at `61022f6`; local commits `016374c` (docs) and the graphics commit are not pushed.
- Vercel serves the exact-palette landing without the new graphics.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Cart still holds the live test adds from the 25/26 scorecard. Clear it through the stored token when testing ends.
- Local `.env` uses the documented dummy WhatsApp number; use production for handset tests.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap.

## Proof files

- `.scratch/verify_landing_v7_20261104.log` — gate after graphics and motion.
- `.scratch/test_motion_3228.mjs` — route, bill, stamp, reduced-motion measurements.
- `.scratch/how_1440_v7.png`, `features_1440_v7.png`, `safety_1440_v7.png`, `how_390_v7.png` — latest section screenshots.
- `.scratch/test_graphics_3227.mjs` — no-JS and reduced-motion checks.
- `.scratch/test_ui_3219.mjs` — five-width overflow, console and screenshots.
