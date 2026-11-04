# HANDOFF — Grocer — 2026-11-04

**Goal:** launch-ready v1. Checkout stays locked.
**Changes:** copy cleanup + phone pass — hero rebuilt as a phone-style WhatsApp sample; connect form meta block removed; demo and Try disclaimers cut to four honesty anchors; four-fact strip; sample cap meter (₹187 of ₹1,000, 18.7%); black demo slate with REC chip; dead chat/button/receipt CSS removed. Previous graphics/motion pass is in the same unpushed stack.
**Passing:** `verify.ps1 -Db` exit 0 — 182 offline + 81 DB, ruff, 9 routes; 0 overflow, 0 console errors and 0 hidden reveals at 1440/1024/768/390/360; phone bubbles opacity 1, cap fill scaleX 0.187; reduced-motion and no-JS show all content; no repeated disclaimers.
**Next action:** review `http://localhost:3231`; say push to put the graphics + phone pass on Vercel; add `public/demo.mp4`; then the remaining live journeys.
**Still broken:** the local commits are not on Vercel or Render until a push; demo video absent; live reconnect, address add/delete, 24h live scrub, typed plan, same-name picker, reactions/ticks and location pin remain open.

## Current truth

- Remote `main` is `61022f6`; local `main` is ahead by the handset docs, graphics/motion and copy/phone commits. Vercel still serves the palette build without graphics or the phone mock.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Cart still holds the live test adds from the 25/26 scorecard. Clear it through the stored token when testing ends.
- Local `.env` uses the documented dummy WhatsApp number; use production for handset tests.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video, Gate 2 case 7 (needs a past order), case 8 live tap.

## Proof files

- `.scratch/verify_cleanup_20261104.log` — full gate after the copy/phone pass.
- `.scratch/shoot_3230.mjs` — five-width screenshots, reveal assertions, motion, reduced-motion, no-JS and disclaimer checks.
- `.scratch/final_1440.png`, `final_1024.png`, `final_768.png`, `final_390.png`, `final_360.png` — latest full pages.
- `.scratch/final_hero_1440.png`, `final_phone_1440.png`, `final_facts_1440.png`, `final_demo_1440.png`, `final_safety_1440.png` — section crops.
- `.scratch/verify_landing_v7_20261104.log` — previous graphics/motion gate.
