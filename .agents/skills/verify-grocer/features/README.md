# Grocer Verification Map

This directory is the maintained source for verifying user-facing behavior of Grocer on WhatsApp. Read this index before driving the app, then use the matching feature file as the recipe.

## Baseline Preconditions

- Backend server is running at `http://127.0.0.1:8000`.
- Supabase PostgreSQL has 9/9 tables present: `users`, `oauth_tokens`, `oauth_states`, `inbound_messages`, `sessions`, `approvals`, `checkouts`, `address_coords`, `schema_migrations`.
- `python scripts/drive_grocer.py doctor` exits 0.
- Test customer phone number: `919876543210`.

## Driving Conventions

- All simulated customer actions are sent to `/api/whatsapp/webhook` via `scripts/drive_grocer.py`.
- Payloads are signed with HMAC-SHA256 (`WHATSAPP_APP_SECRET`).
- Proof artifacts are saved to `.scratch/verification-proof/`.

## Features

- [Grocery Shopping & Concierge](./grocery-shopping.md) covers natural language grocery requests, vague staple auto-selection, conversational Q&A, and interactive receipt cards.
- [3-Lock Checkout & Payment](./checkout-3-lock.md) covers Lock 1 physical button authorization, Lock 2 price/stock re-verification, Lock 3 atomic CAS, and HTTPS payment bridge links.
- [Address Management & Onboarding](./address-management.md) covers WhatsApp GPS pin onboarding, address switching, and deletion guardrails during active delivery.
