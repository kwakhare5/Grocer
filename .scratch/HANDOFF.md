# HANDOFF — Grocer — 2026-11-17

**Goal:** set a fresh WhatsApp token, then re-run the handset proofs. Checkout stays locked.
**Changes:** docs truth pass, dead env keys removed, proof page corrected, cleanup done; Render database link restored and a Supabase pg_cron keep-alive added.
**Passing:** ruff clean; 191 offline + 82 DB tests; Next build 9 routes; live `/health` 200 with database connected (2026-11-17).
**Next action:** new WhatsApp access token on Render and `.env`; send one real message.
**Still broken:** WhatsApp sends (expired token), demo video, handset proofs open, coupons blocked by Swiggy entitlement.

## Current truth

- `main` = `279ad7a`, deployed, working tree clean.
- Render deploy `dep-dbtt6t0u01pc73d1oj6g` live; `/health` 200, `environment: production`.
- `DATABASE_URL` on Render now uses the working `aws-0-ap-south-1` pooler with the current password; old value in `.scratch/render_db_url_rollback.txt`.
- Keep-alive: Supabase `pg_cron` `grocer-keepalive` every 5 min via `pg_net`; first run succeeded; daily `grocer-net-cleanup`.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker, demo video, Gate 2 case 7 (needs a past order), coupon savings (account entitlement).

## Proof files

- `.scratch/gate_20261117.log` — ruff + 191 offline tests.
- `.scratch/gate_db2_20261117.log` — 82 DB tests (NO_PROXY cleared).
- `.scratch/build_20261117.log` — Next build, 9 routes.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width landing proof.
