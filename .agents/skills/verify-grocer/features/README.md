# Grocer Verification Feature Map

This directory is the maintained source for verifying the user-facing behavior of Grocer. Read the index before driving the concierge, then use the matching feature file as the recipe.

## Baseline Preconditions

- Launch Grocer server at `http://127.0.0.1:8000` via `uvicorn backend.main:app --port 8000`.
- Health check `http://127.0.0.1:8000/api/health` must return HTTP 200 with `status: "ok"`.
- Database connection to Supabase Postgres must be active and verified.
- Gemini API key and Swiggy credentials loaded from `.env`.

## Driving Conventions

- Drive conversational and button flows via the Simulator API (`POST /api/simulator/chat`).
- Use dedicated test customer sender ID (e.g., `wa:+919876543210_test`) for isolation.
- Fast button payloads dispatch in Python (<50ms) without LLM latency.
- Receipts must show transparent Rupee pricing (`₹`), broken down by items, fees, taxes, and coupon savings.

## Proof and Evidence Reporting

- Capture the exact JSON payload, response text, and interactive buttons for each feature drive.
- Save proof artifacts to `.scratch/verify-proof/` (e.g. `01-intake-proof.json`).
- Ensure proof artifacts persist after instance cleanup.

## Feature Index

| # | Feature | User Journey | Driving Spec |
|---|---|---|---|
| 01 | **Conversational Grocery Intake** | Texts shopping lists or recipes; receives itemized dark-store bill. | [01-conversational-intake.md](./01-conversational-intake.md) |
| 02 | **Wallet Advocate & Coupons** | Auto-applies best Swiggy coupons; suggests threshold staples. | [02-wallet-advocate-coupons.md](./02-wallet-advocate-coupons.md) |
| 03 | **Address Management** | 1-tap saved address selection or GPS pin; syncs dark store. | [03-address-management.md](./03-address-management.md) |
| 04 | **1-Tap Mobile UPI Checkout** | 3-lock safety gate; delivers clickable `upi://pay` deep links. | [04-one-tap-upi-checkout.md](./04-one-tap-upi-checkout.md) |
