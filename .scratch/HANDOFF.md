# HANDOFF — Grocer — 2026-11-17

**Goal:** reconnect Swiggy, then re-run the handset proofs. Checkout stays locked.
**Changes:** docs truth pass, dead env keys removed, proof page corrected, cleanup done; Render database link restored, Supabase pg_cron keep-alive added, WhatsApp token replaced and verified end to end.
**Passing:** ruff clean; 191 offline + 82 DB tests; Next build 9 routes; live `/health` 200; live WhatsApp inbound 04:48 UTC answered with 200 and a real reply (2026-11-17).
**Next action:** reconnect Swiggy from the bot's link; confirm a real add and receipt, then the handset proofs.
**Still broken:** Swiggy refresh token dead (400), demo video, handset proofs open, coupons blocked by Swiggy entitlement.

## Current truth

- `main` = `279ad7a`, deployed, working tree clean.
- Render deploy `dep-dbttn72fngtc73a72pn0` live; `/health` 200, `environment: production`.
- `DATABASE_URL` on Render uses the working `aws-0-ap-south-1` pooler; old value in `.scratch/render_db_url_rollback.txt`.
- Keep-alive: Supabase `pg_cron` `grocer-keepalive` every 5 min via `pg_net`; daily `grocer-net-cleanup`.
- WhatsApp: new system-user token on Render and `.env`; webhook subscribed; last inbound `awaiting_link` because the Swiggy refresh token fails.
- Checkout locked (`LIVE_CHECKOUT_ENABLED=false`). No real order has ever been placed.

## Unproven

Live OAuth reconnect, address add/delete, the 24h live scrub, location-pin replay, reactions/blue ticks, typed plan pick, same-name picker, demo video, Gate 2 case 7 (needs a past order), coupon savings (account entitlement).

## Proof files

- `.scratch/gate_20261117.log` — ruff + 191 offline tests.
- `.scratch/gate_db2_20261117.log` — 82 DB tests (NO_PROXY cleared).
- `.scratch/build_20261117.log` — Next build, 9 routes.
- `.scratch/css_before/`, `.scratch/css_after/` — five-width landing proof.
