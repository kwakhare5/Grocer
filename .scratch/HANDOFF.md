# HANDOFF — Grocer — 2026-11-04

**Goal:** launch-ready v1, white Gumloop landing, website connect flow. No order.
**Changes:** landing rebuilt on white with Gumloop tokens and multi-colour accents (no italics, smaller type, new navbar); number-first website connect added (`/api/auth/whatsapp/start`, `connect <code>` webhook, Connect form); docs updated to the new ownership rule.
**Passing:** `verify.ps1 -Db` exit 0 — 182 offline + 81 DB, ruff, Next build with 8 routes (`.scratch/verify_final_20261104.log`); browser form test through the local backend returned a real signed code; five widths show zero overflow and no console errors.
**Next action:** Karan approves commit/push; then handset test of the connect code, live OAuth reconnect, address add/delete, the 24h scrub, the demo video, and his first real order.

## Current truth

- Branch `main`, tip `effcb83` pushed. Pass 2, the connect flow and the landing rebuild are uncommitted. Vercel still serves the old page.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.
- Cart still holds the live test adds from the 25/26 scorecard. Clear it through the stored token when testing ends.
- `gumloopDESIGN.md` stays at the repo root as the design source; it is untracked.

## Unproven

Handset connect code, live OAuth reconnect, address add/delete, the 24h scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker on a handset, demo video.

## Proof files

- `.scratch/verify_final_20261104.log` — final gate after the white rebuild and connect flow.
- `.scratch/landing_1440.png`, `landing_1024.png`, `landing_768.png`, `landing_390.png`, `landing_360.png` — final screenshots.
- `.scratch/connect_ready_390.png` — form success state with the real `wa.me` link.
- `.scratch/uvicorn_8011.log` — local backend 200 for the form request.
