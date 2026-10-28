---
name: verify-grocer
description: "Drives Grocer end-to-end the way a real WhatsApp customer and Meta Cloud API webhook does. Use whenever verifying conversational shopping, 3-lock checkout buttons, address geocoding, or database receipts on Grocer."
---

# Verify Grocer

Grocer is a grocery concierge running on WhatsApp, backed by FastAPI, Groq, Supabase PostgreSQL, and Swiggy Instamart. This skill launches the service, runs health doctor checks, drives customer journeys with signed HMAC-SHA256 WhatsApp webhook payloads, and captures database proof.

## Launch

Start the backend server on port 8000:

```powershell
# In workspace root (D:\Grocer-v5)
uvicorn backend.main:app --port 8000 --host 127.0.0.1
```

Ready indicator: terminal logs output `Uvicorn running on http://127.0.0.1:8000` and `Application startup complete.`

Teardown: stop the uvicorn process or kill the terminal task.

## Doctor

Run the read-only doctor check before driving any feature:

```powershell
python scripts/drive_grocer.py doctor --url http://127.0.0.1:8000
```

Doctor confirms:
1. Meta WhatsApp Webhook GET challenge verification (`200 OK` with valid hub challenge).
2. Supabase PostgreSQL connectivity and active schema (9/9 tables: `users`, `inbound_messages`, `oauth_tokens`, `oauth_states`, `sessions`, `approvals`, `checkouts`, `address_coords`, `schema_migrations`; migrations 001–010 applied; app queries run as the non-superuser `grocer_app`, with no CREATE and no ledger writes).
3. `/health` returns 200 only when the schema is migrated and the app role is active; during a DB outage it returns 503 instead of the process crashing.

If doctor exits non-zero, check `.env` credentials and database connection before attempting to drive.

## Drive

Drive user journeys using `scripts/drive_grocer.py`. The driver automatically signs payloads with HMAC-SHA256 (`WHATSAPP_APP_SECRET`) and dispatches to `/api/whatsapp/webhook`.

### 1. Inbound Text Message (Grocery Request / Intent)
```powershell
python scripts/drive_grocer.py send-text --phone 919876543210 --text "buy 1L amul milk and 6 eggs"
```

### 2. Interactive Button Tap (Pay / Clear Basket / Raise Limit)
```powershell
# Clear basket
python scripts/drive_grocer.py send-button --phone 919876543210 --button-id "cart:clear" --title "Clear Basket"

# 3-Lock Payment Authorization (Lock 1 Authority)
python scripts/drive_grocer.py send-button --phone 919876543210 --button-id "pay:<approval_id>" --title "Pay"
```

### 3. WhatsApp GPS Location Pin (Zero-Address Onboarding)
```powershell
python scripts/drive_grocer.py send-location --phone 919876543210 --lat 12.9279 --lng 77.6271
```

## Evidence

Capture database state and response payloads into `.scratch/verification-proof/`:

```powershell
# Inspect database state for test user
python scripts/drive_grocer.py inspect-db --phone 919876543210 > .scratch/verification-proof/db_state.txt
```

Proof standards:
1. Webhook returns HTTP 200 with status payload.
2. Inbound message is recorded in `grocer.inbound_messages` with status `'received'`.
3. Valid shopping requests create approval records in `grocer.approvals` with integer `to_pay_paise` and SHA-256 cart fingerprints.
4. Fast button taps (`cart:clear`, `pay:`) respond in <50ms without LLM lag.

## Cleanup

- Stop the running uvicorn process.
- Do not delete `.scratch/verification-proof/` so captured evidence survives teardown.

## Helpers

- `scripts/drive_grocer.py`: Command-line driver for HMAC signing, webhook dispatch, and DB inspection.
- `verify.ps1`: Universal project test runner (Ruff lint, 104 contract tests, Next.js production build).
